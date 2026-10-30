"""Claim conversation as a LiveKit voice agent (README §4). One session per LiveKit room.

LiveKit runs the call: WebRTC audio, voice activity and turn detection, and
typed chat (topic lk.chat). Sarvam turns speech into text and back, and Claude runs the
conversation by calling the tools on ClaimAgent. Rules decide, Claude explains: every
number Claude says comes from services/rules.py through a tool result.

    state.py   Claim: the claim's working state, sent to the browser on "claim.state"
    prompt.py  the system instructions
    tools.py   ClaimAgent and the tools Claude calls
    this file  photo grading, language, and the worker that starts each session

Photos arrive as byte streams on the "photo" topic and are graded outside the LLM.

Run (with livekit-server up):  python -m agent.claim_agent dev
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from livekit import rtc  # noqa: E402
from livekit.agents import (  # noqa: E402
    AgentServer,
    AgentSession,
    ChatContext,
    JobContext,
    JobProcess,
    cli,
    inference,
)
from livekit.agents.utils import is_given  # noqa: E402
from livekit.plugins import anthropic, sarvam, silero  # noqa: E402

import db  # noqa: E402
from agent import AGENT_NAME  # noqa: E402
from agent.state import Claim  # noqa: E402
from agent.tools import ClaimAgent  # noqa: E402
from models import Evidence, Incident, Language  # noqa: E402
from seed import load_wallet  # noqa: E402
from services import claude, rules, settlement  # noqa: E402

log = logging.getLogger("agent")

PHOTO_TOPIC = "photo"

# What Claude reads off each kind of upload, for rules.verify_details to check.
READ_FIELDS: dict[str, set[str]] = {
    "damage_wide": {"number_plate_text"},
    "dl": {"licence_number", "licence_holder_name", "licence_valid_until"},
}


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

    # the browser's token carries who is calling, the language, and any claim to resume
    # (main.livekit_token)
    participant = await ctx.wait_for_participant()
    user = load_wallet().users[participant.attributes["user_id"]]
    language: Language = "en" if participant.attributes.get("language") == "en" else "hi"
    resume_id = participant.attributes.get("resume_session_id")
    saved = await db.load_session(user.id, resume_id) if resume_id else None
    history: ChatContext | None = None
    if saved and resume_id and rules.is_resumable(saved["stage"]):
        claim = Claim(user=user, session_id=resume_id, language=language, room=ctx.room)
        claim.restore(saved)
        await db.update_session(claim.session_id, claim.stage, language)
        history = ChatContext()  # so Claude remembers what was said before
        for m in saved["messages"]:
            role = "user" if m["sender_role"] == "user" else "assistant"
            history.add_message(role=role, content=m["message_text"])
    else:
        claim = Claim(user=user, session_id=uuid.uuid4().hex, language=language, room=ctx.room)
        claim.incident = Incident(session_id=claim.session_id, user_id=user.id)
        await db.create_session(claim.session_id, user.id, "INTAKE", language)

    session = AgentSession[Claim](
        stt=sarvam.STT(language="unknown", model=os.getenv("SARVAM_STT_MODEL", "saaras:v4")),
        llm=ClaudeLLM(model=claude.MODEL),
        # The male voice Shubh by default; plain "shubh" exists only on bulbul:v3.
        tts=sarvam.TTS(
            target_language_code=f"{language}-IN",
            model=os.getenv("SARVAM_TTS_MODEL", "bulbul:v3"),
            speaker=os.getenv("SARVAM_TTS_SPEAKER", "shubh"),
            # Below 1.0 so the voice sounds calm and unhurried, like a person on a call.
            pace=float(os.getenv("SARVAM_TTS_PACE", "0.85")),
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

    await session.start(room=ctx.room, agent=ClaimAgent(claim, history))
    await claim.publish()
    if not (saved and saved["messages"] and history):  # new, or resumed before anyone spoke
        session.say(claim.line("greeting", name=user.full_name.split()[0]))
    else:
        session.generate_reply(
            instructions="The user has come back to continue this claim. In at most two short "
            "sentences, say where it stands and ask for the next thing needed."
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    cli.run_app(server)
