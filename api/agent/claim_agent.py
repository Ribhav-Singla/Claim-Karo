"""Claim conversation as a LiveKit voice agent (README §4). One session per LiveKit room.

LiveKit runs the call: WebRTC audio, voice activity and turn detection, and
typed chat (topic lk.chat). Sarvam turns speech into text and back, and Claude runs the
conversation by calling the tools on ClaimAgent. Rules decide, Claude explains: every
number Claude says comes from services/rules.py through a tool result.

Photos arrive as byte streams on the "photo" topic and are graded outside the LLM. After
every change the claim is sent to the browser as one JSON snapshot on "claim.state".

Run (with livekit-server up):  python -m agent.claim_agent dev
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from dotenv import load_dotenv

load_dotenv()

from livekit import rtc  # noqa: E402
from livekit.agents import (  # noqa: E402
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    ToolError,
    cli,
    function_tool,
    inference,
)
from livekit.agents.utils import is_given  # noqa: E402
from livekit.plugins import anthropic, sarvam, silero  # noqa: E402

import db  # noqa: E402
from agent import AGENT_NAME  # noqa: E402
from agent.lines import LINES, PHOTO_LABEL  # noqa: E402
from models import (  # noqa: E402
    Evidence,
    Incident,
    Language,
    Policy,
    SessionState,
    User,
    Vehicle,
    Viability,
)
from seed import load_wallet  # noqa: E402
from services import claude, rules, settlement  # noqa: E402

log = logging.getLogger("agent")

STATE_TOPIC = "claim.state"
PHOTO_TOPIC = "photo"
RiskFlag = Literal["drunk_driving", "no_valid_dl", "commercial_use", "theft", "hit_and_run"]

# What Claude reads off each kind of upload, for rules.verify_details to check.
READ_FIELDS: dict[str, set[str]] = {
    "damage_wide": {"number_plate_text"},
    "dl": {"licence_number", "licence_holder_name", "licence_valid_until"},
}


# --- claim state -------------------------------------------------------------------------


@dataclass
class Claim:
    """Everything the session knows about this claim (the AgentSession's userdata)."""

    user: User
    session_id: str
    language: Language
    room: rtc.Room
    stage: SessionState = "INTAKE"
    incident: Incident = field(default_factory=Incident)
    estimate_unknown: bool = False
    policy: Policy | None = None
    viability: Viability | None = None
    evidence: list[Evidence] = field(default_factory=list)
    photos: dict[str, dict] = field(default_factory=dict)  # photo id -> status shown in the UI
    retakes: dict[str, int] = field(default_factory=dict)  # photo kind -> attempts so far
    form: dict | None = None
    missing_docs: list[str] | None = None
    settlement: dict | None = None
    reference: str | None = None

    @property
    def vehicles(self) -> list[Vehicle]:
        return load_wallet().vehicles_for(self.user.id)

    def line(self, key: str, **kwargs: str) -> str:
        return LINES[key][self.language].format(**kwargs)

    def photo_label(self, kind: str) -> str:
        return PHOTO_LABEL.get(kind, {}).get(self.language, kind)

    def next_photo_kind(self) -> str | None:
        assert self.policy is not None
        vehicle = load_wallet().vehicles[self.policy.vehicle_id]
        done = {e.evidence_type for e in self.evidence if e.is_accepted}
        pending = rules.required_photo_kinds(self.policy, vehicle)
        return next((k for k in pending if k not in done), None)

    async def set_stage(self, stage: SessionState) -> None:
        self.stage = stage
        await db.update_session(self.session_id, stage, self.language)

    async def publish(self) -> None:
        """Send the whole claim to the browser; the side panel renders the latest snapshot."""
        p = self.policy
        snapshot = {
            "state": self.stage,
            "fields": self.incident.model_dump(
                mode="json", exclude_none=True, exclude={"id", "session_id", "user_id"}
            ),
            "policy": p
            and {
                "policy_id": p.id,
                "insurer_name": p.insurer_name,
                "policy_number": p.policy_number,
                "coverage_type": p.coverage_type,
                "no_claim_bonus_pct": p.no_claim_bonus_pct,
                "deductible_inr": p.compulsory_deductible_inr + p.voluntary_deductible_inr,
                "add_on_covers": p.add_on_covers,
            },
            "viability": self.viability and self.viability.model_dump(),
            "photos": self.photos,
            "form": self.form,
            "missingDocs": self.missing_docs,
            "settlement": self.settlement,
            "referenceNo": self.reference,
        }
        await self.room.local_participant.send_text(json.dumps(snapshot), topic=STATE_TOPIC)


def instructions(claim: Claim) -> str:
    vehicles = "\n".join(
        f'- id "{v.id}": {v.brand} {v.model} ({v.vehicle_type}), reg {v.vehicle_number}'
        for v in claim.vehicles
    )
    return f"""{claude.SYSTEM}

You are on a call with {claim.user.full_name}. Today is {date.today().isoformat()}.
Their vehicles:
{vehicles}

How the claim goes:
1. Find out what happened. Every time the user gives facts about the incident, call
   record_incident with what they told you. You need the vehicle, the date, what happened,
   and a damage estimate (or that they don't know it). Ask ONE short question at a time
   for whatever record_incident says is still missing.
2. When record_incident returns a verdict, explain it in at most 3 short sentences: what
   the insurer would pay, the No-Claim Bonus lost over 3 years, and your recommendation.
   Unless it is not covered, ask whether they want to file the claim.
3. If they want to claim, call start_claim; if not, call decline_claim. Then say what the
   tool result tells you to.
4. Photos are uploaded with the camera button. You can't see them; the system checks
   each one and tells the user the result itself. Don't comment on photos you weren't told
   about.
5. When the claim form is ready and the user says to file it, call file_claim.

Reply in the language the user last used: Hindi in Devanagari, or English. Never write
Hindi in Latin letters ("Afsos hai"): the voice reads it badly. Only use numbers that came
from a tool result."""


# --- the agent ---------------------------------------------------------------------------


class ClaimAgent(Agent):
    def __init__(self, claim: Claim) -> None:
        super().__init__(instructions=instructions(claim))

    @function_tool()
    async def record_incident(
        self,
        context: RunContext[Claim],
        vehicle_id: str | None = None,
        incident_date: str | None = None,
        incident_location: str | None = None,
        description_english: str | None = None,
        third_party_involved: bool | None = None,
        third_party_property_damaged: bool | None = None,
        anyone_injured: bool | None = None,
        estimated_repair_cost_inr: int | None = None,
        estimate_unknown: bool | None = None,
        garage_name: str | None = None,
        police_report_filed: bool | None = None,
        risk_flags: list[RiskFlag] | None = None,
    ) -> str:
        """Save facts about the accident. Pass only what the user has said; leave the rest null.

        Args:
            vehicle_id: One of the user's vehicle ids.
            incident_date: YYYY-MM-DD; resolve "kal"/"yesterday" against today.
            incident_location: Where it happened.
            description_english: One-line English summary of the whole incident so far.
            third_party_involved: Another person or vehicle was involved.
            third_party_property_damaged: Someone else's vehicle or property was damaged.
            anyone_injured: Anyone was hurt.
            estimated_repair_cost_inr: Repair cost in rupees ("4.2k" -> 4200).
            estimate_unknown: True only if the user says they don't know the cost.
            garage_name: Garage doing the repair.
            police_report_filed: Whether an FIR was filed.
            risk_flags: drunk_driving, no_valid_dl, commercial_use, theft, hit_and_run.
        """
        claim = context.userdata
        if claim.stage not in ("INTAKE", "VIABILITY"):
            raise ToolError("The incident can't be changed at this step.")

        updates: dict[str, Any] = {
            k: v
            for k, v in {
                "vehicle_id": vehicle_id,
                "incident_location": incident_location,
                "description_english": description_english,
                "third_party_involved": third_party_involved,
                "third_party_property_damaged": third_party_property_damaged,
                "anyone_injured": anyone_injured,
                "estimated_repair_cost_inr": estimated_repair_cost_inr,
                "garage_name": garage_name,
                "police_report_filed": police_report_filed,
            }.items()
            if v is not None
        }
        if vehicle_id is not None and vehicle_id not in {v.id for v in claim.vehicles}:
            raise ToolError(f"Unknown vehicle_id {vehicle_id!r}; use one of the listed ids.")
        if incident_date is not None:
            try:
                updates["incident_date"] = date.fromisoformat(incident_date)
            except ValueError:
                raise ToolError("incident_date must be YYYY-MM-DD.") from None
        if risk_flags:
            updates["risk_flags"] = sorted(set(claim.incident.risk_flags) | set(risk_flags))

        incident = claim.incident.model_copy(update=updates)
        claim.incident = incident
        claim.estimate_unknown = claim.estimate_unknown or bool(estimate_unknown)
        await db.save_incident(claim.session_id, incident)

        missing = [
            name
            for name, ok in [
                ("vehicle", incident.vehicle_id),
                ("date", incident.incident_date),
                ("what happened", incident.description_english),
                (
                    "damage estimate",
                    incident.estimated_repair_cost_inr is not None or claim.estimate_unknown,
                ),
            ]
            if not ok
        ]
        if missing:
            await claim.publish()
            return f"Saved. Still needed: {', '.join(missing)}."

        # everything required is known: match the policy and run the numbers
        policy = rules.match_policy(incident, load_wallet().policies_for(claim.user.id))
        if policy is None:
            await claim.set_stage("NO_COVER")
            await claim.publish()
            return "No policy covers this. Tell the user, kindly, in one sentence."
        claim.policy = policy
        vehicle = load_wallet().vehicles[policy.vehicle_id]
        claim.viability = rules.viability(incident, policy, vehicle)
        await db.save_incident(claim.session_id, incident, policy.id, claim.viability)
        covered = claim.viability.verdict != "not_covered"
        await claim.set_stage("VIABILITY" if covered else "NO_COVER")
        await claim.publish()
        return json.dumps(
            {
                "policy": f"{policy.insurer_name}, NCB {policy.no_claim_bonus_pct}%, "
                f"add-ons {policy.add_on_covers or 'none'}",
                "verdict (final, do not recompute)": claim.viability.model_dump(),
                "note": "If estimate_pending, say claiming makes sense only above "
                "breakeven_estimate_inr and ask for the garage estimate. If not_covered, "
                "say why from the reason codes.",
            }
        )

    @function_tool()
    async def start_claim(self, context: RunContext[Claim]) -> str:
        """The user wants to file the claim after hearing the verdict."""
        claim = context.userdata
        if claim.stage != "VIABILITY":
            raise ToolError("There is no verdict to act on yet.")
        await claim.set_stage("EVIDENCE")
        await claim.publish()
        kind = claim.next_photo_kind()
        return f"Say exactly: {claim.line('ask_photo', kind=claim.photo_label(kind or ''))}"

    @function_tool()
    async def decline_claim(self, context: RunContext[Claim]) -> str:
        """The user decided not to file the claim."""
        claim = context.userdata
        if claim.stage != "VIABILITY":
            raise ToolError("There is no verdict to act on yet.")
        await claim.set_stage("ADVISED_NO_CLAIM")
        await claim.publish()
        return f"Say exactly: {claim.line('advised_no_claim')}"

    @function_tool()
    async def file_claim(self, context: RunContext[Claim]) -> str:
        """File the reviewed claim with the insurer, once the user confirms."""
        claim = context.userdata
        if claim.stage != "FORM_REVIEW":
            raise ToolError("The claim form isn't ready yet.")
        context.disallow_interruptions()
        try:
            reference = await db.file_claim(claim.session_id)
        except db.DocumentsNotVerified:
            raise ToolError(claim.line("not_verified")) from None
        if reference is None:  # already filed from the dashboard
            raise ToolError("This claim is already filed.")
        claim.reference = reference
        await claim.set_stage("FILED")
        await claim.publish()
        return f"Say exactly: {claim.line('filed', ref=reference)}"


# --- photos (graded outside the LLM) -----------------------------------------------------


def mismatch_line(claim: Claim, codes: list[str], details: dict) -> str:
    """Tell the user which detail didn't match the records and what to upload instead."""
    policy = claim.policy
    assert policy is not None
    if "PLATE_NOT_READABLE" in codes:
        return claim.line("plate_not_readable")
    if "PLATE_MISMATCH" in codes:
        vehicle = load_wallet().vehicles[policy.vehicle_id]
        return claim.line(
            "plate_mismatch", seen=details["number_plate_text"], expected=vehicle.vehicle_number
        )
    if "DL_NUMBER_MISMATCH" in codes or "DL_NAME_MISMATCH" in codes:
        return claim.line("dl_mismatch", last4=policy.driving_licence_number[-4:])
    if "DL_EXPIRED_ON_INCIDENT_DATE" in codes:
        return claim.line("dl_expired")
    return claim.line("dl_not_readable")


async def on_photo(session: AgentSession[Claim], image: bytes, photo_id: str, mime: str) -> None:
    claim = session.userdata
    kind = claim.next_photo_kind() if claim.stage == "EVIDENCE" else None
    if kind is None:
        return
    claim.photos[photo_id] = {"status": "grading"}
    await claim.publish()

    policy = claim.policy
    assert policy is not None
    grade = await claude.grade_damage_photo(image, mime, kind, claim.language)
    # the plate / licence read off the photo must match the vehicle and the policy's records
    details = grade.model_dump(mode="json", include=READ_FIELDS.get(kind, set()))
    vehicle = load_wallet().vehicles[policy.vehicle_id]
    mismatches = rules.verify_details(kind, details, vehicle, policy, claim.incident)
    attempts = claim.retakes.get(kind, 0)
    # A second attempt with decent confidence passes on photo quality, so the demo can't get
    # stuck; a detail that doesn't match the records never passes.
    accepted = not mismatches and (grade.accepted or (attempts >= 1 and grade.confidence >= 0.6))

    evidence = Evidence(
        id=photo_id,
        evidence_type=kind,
        file_path="",
        is_accepted=accepted,
        quality_issues=[] if accepted else list(grade.issues),
        ai_confidence_score=grade.confidence,
        extracted_details=details,
        detail_mismatches=mismatches,
    )
    await db.add_evidence(claim.session_id, evidence)
    claim.evidence.append(evidence)
    claim.retakes[kind] = attempts + 1
    claim.photos[photo_id] = {
        "status": "accepted" if accepted else "retake",
        "evidence_type": kind,
        "quality_issues": evidence.quality_issues + mismatches,
    }

    if not accepted:
        await claim.publish()
        retake = mismatch_line(claim, mismatches, details) if mismatches else None
        session.say(retake or grade.retake_instruction or claim.line("upload_photo"))
        return

    next_kind = claim.next_photo_kind()
    if next_kind:
        await claim.publish()
        session.say(claim.line("next_photo", kind=claim.photo_label(next_kind)))
        return

    await review_form(claim)
    session.generate_reply(
        instructions=f"""The claim form is ready: {json.dumps(claim.form, ensure_ascii=False)}.
Missing documents: {claim.missing_docs or "none"}. Settlement estimate: {claim.settlement}.
In at most 3 sentences: confirm the claim is ready, name any missing documents, give the
settlement time, and ask whether to file it now."""
    )


async def review_form(claim: Claim) -> None:
    """Fill in the claim form and its document checklist once every photo is in."""
    incident, policy, verdict = claim.incident, claim.policy, claim.viability
    assert policy is not None
    vehicle = load_wallet().vehicles[policy.vehicle_id]
    ctype = rules.claim_type(incident, policy) or "own_damage"
    required = rules.required_documents(incident, policy)
    missing = rules.missing_documents(incident, policy, claim.evidence)
    est = settlement.estimate(ctype, rules.is_cashless(incident, policy), not missing)

    claim.form = {
        "policyholder": claim.user.full_name,
        "phone_number": claim.user.phone_number,
        "insurer_name": policy.insurer_name,
        "policy_number": policy.policy_number,
        "vehicle": f"{vehicle.brand} {vehicle.model} ({vehicle.vehicle_number})",
        "claim_type": ctype,
        "incident_date": str(incident.incident_date),
        "incident_location": incident.incident_location,
        "description": incident.description_english,
        "estimated_repair_cost_inr": incident.estimated_repair_cost_inr,
        "expected_payout_inr": verdict.insurer_payout_inr if verdict else None,
        "garage": incident.garage_name,
        "route": est.route,
    }
    claim.missing_docs = missing
    claim.settlement = est.model_dump()
    checklist = {code: code not in missing for code in required}
    await db.save_claim(
        claim.session_id, policy.id, ctype, claim.form, checklist, (est.min_days, est.max_days)
    )
    await claim.set_stage("FORM_REVIEW")
    await claim.publish()


# --- language ----------------------------------------------------------------------------


class ClaudeLLM(anthropic.LLM):
    """Claude at low effort: short spoken replies don't need long thinking."""

    def chat(self, **kwargs: Any):  # type: ignore[override]
        extra = kwargs.get("extra_kwargs")
        kwargs["extra_kwargs"] = {
            **(extra if is_given(extra) and extra else {}),
            "output_config": {"effort": "low"},
        }
        return super().chat(**kwargs)


def follow_language(session: AgentSession[Claim], language: Language) -> None:
    """Reply (and grade photos) in the language the user last spoke or typed."""
    claim = session.userdata
    if language == claim.language:
        return
    claim.language = language
    session.tts.update_options(target_language_code=f"{language}-IN")  # type: ignore[union-attr]


def is_hindi(text: str) -> bool:
    return any("ऀ" <= ch <= "ॿ" for ch in text)


# --- server ------------------------------------------------------------------------------


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load()


server = AgentServer(setup_fnc=prewarm)


@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: JobContext) -> None:
    await db.init()
    ctx.add_shutdown_callback(db.close)

    # the browser's token carries who is calling and in which language (main.livekit_token)
    participant = await ctx.wait_for_participant()
    user = load_wallet().users[participant.attributes["user_id"]]
    language: Language = "en" if participant.attributes.get("language") == "en" else "hi"
    claim = Claim(user=user, session_id=uuid.uuid4().hex, language=language, room=ctx.room)
    claim.incident = Incident(session_id=claim.session_id, user_id=user.id)
    await db.create_session(claim.session_id, user.id, "INTAKE", language)

    session = AgentSession[Claim](
        stt=sarvam.STT(language="unknown", model=os.getenv("SARVAM_STT_MODEL", "saaras:v4")),
        llm=ClaudeLLM(model=claude.MODEL),
        tts=sarvam.TTS(
            target_language_code=f"{language}-IN",
            model=os.getenv("SARVAM_TTS_MODEL", "bulbul:v3"),
            speaker=os.getenv("SARVAM_TTS_SPEAKER") or None,
        ),
        vad=ctx.proc.userdata["vad"],
        turn_handling={
            "turn_detection": inference.TurnDetector(version="v1-mini"),
            # On laptop speakers the mic hears the bot; with barge-in that echo cut the bot
            # off and it answered its own words. While it speaks, STT gets silence instead.
            "interruption": {"enabled": False},
        },
        userdata=claim,
        max_tool_steps=5,
    )

    @session.on("user_input_transcribed")
    def _on_transcript(ev) -> None:
        if ev.is_final and ev.language:
            follow_language(session, "en" if str(ev.language).startswith("en") else "hi")

    background: set[asyncio.Task] = set()

    def run_in_background(coro) -> None:
        task = asyncio.create_task(coro)
        background.add(task)
        task.add_done_callback(background.discard)
        task.add_done_callback(
            lambda t: (
                t.cancelled()
                or t.exception()
                and log.error("background task failed", exc_info=t.exception())
            )
        )

    @session.on("conversation_item_added")
    def _on_item(ev) -> None:
        item = ev.item
        text = getattr(item, "text_content", None)
        if getattr(item, "role", None) == "user" and text:
            run_in_background(db.add_message(claim.session_id, "user", text))
            if claim.incident.description_user_language is None:
                claim.incident.description_user_language = text  # the user's own first words
            if is_hindi(text):
                follow_language(session, "hi")
        elif getattr(item, "role", None) == "assistant" and text:
            run_in_background(db.add_message(claim.session_id, "bot", text))

    def _on_photo_stream(reader: rtc.ByteStreamReader, _identity: str) -> None:
        async def read() -> None:
            image = b"".join([chunk async for chunk in reader])
            photo_id = os.path.splitext(os.path.basename(reader.info.name))[0]
            try:
                await on_photo(session, image, photo_id, reader.info.mime_type or "image/jpeg")
            except Exception:
                log.exception("photo grading failed")
                session.say(claim.line("upload_photo"))

        run_in_background(read())

    ctx.room.register_byte_stream_handler(PHOTO_TOPIC, _on_photo_stream)

    await session.start(room=ctx.room, agent=ClaimAgent(claim))
    await claim.publish()
    session.say(claim.line("greeting", name=user.full_name.split()[0]))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    cli.run_app(server)
