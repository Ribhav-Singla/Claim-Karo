"""Claim conversation as a LangGraph graph (README §4). One Agent per WebSocket connection.

Layout of this file:
  1. state      - what the graph remembers between messages
  2. helpers    - small shared functions (send an event, speak a line, change step)
  3. nodes      - one function per job (greet, intake, match policy, ...)
  4. routers    - functions that decide which node runs next
  5. graph      - add nodes, add edges, compile
  6. Agent      - runs the graph once per client message and forwards its events

Every client message is one graph run. Sarvam STT runs before the graph and TTS after the
text is sent, so the chat works on text alone. Money math lives in services/rules.py.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

import db
from agent.lines import LINES, NO, PHOTO_LABEL, YES
from models import Evidence, Incident, Language, Policy, SessionState, Viability
from seed import load_wallet
from services import claude, rules, sarvam, settlement

log = logging.getLogger("agent")


# --- 1. state ----------------------------------------------------------------------------


class ClaimState(TypedDict, total=False):
    user_id: str
    session_id: str
    language: Language
    phase: SessionState  # which step of the claim we are on (INTAKE, VIABILITY, ...)
    inbox: dict[str, Any]  # the client message this run is handling

    incident: Incident  # facts Claude has extracted so far
    estimate_unknown: bool
    policy: Policy | None
    viability: Viability | None
    evidence: list[Evidence]
    retakes: dict[str, int]  # photo kind -> attempts so far


@dataclass
class Turn:
    """Data for one run only, never saved in the state (photo bytes are too big)."""

    photo: bytes = b""


# --- 2. helpers --------------------------------------------------------------------------


def send(event: dict) -> None:
    """Stream an event to the browser right away."""
    get_stream_writer()(event)


async def say(state: ClaimState, text: str) -> None:
    """Text first (always), then audio if TTS works."""
    await db.add_message(state["session_id"], "bot", text)
    send({"type": "bot_message", "text": text, "language": state["language"]})
    audio = await sarvam.synthesize(text, state["language"])
    if audio:
        send({"type": "audio", "data": audio, "mime": "audio/mpeg"})


async def set_phase(state: ClaimState, phase: SessionState) -> dict:
    await db.update_session(state["session_id"], phase, state["language"])
    send({"type": "state", "state": phase})
    return {"phase": phase}


def line(state: ClaimState, key: str, **kwargs: str) -> str:
    return LINES[key][state["language"]].format(**kwargs)


def photo_label(state: ClaimState, kind: str | None) -> str:
    return PHOTO_LABEL.get(kind or "", {}).get(state["language"], kind or "")


def read_decision(msg: dict) -> str | None:
    """Button decision, or a spoken/typed yes/no read as one."""
    if msg["type"] == "decision":
        return msg["decision"]
    if msg["type"] == "text":
        lowered = msg["text"].strip().lower()
        if any(w in lowered for w in NO):
            return "dont_claim"
        if any(w in lowered for w in YES):
            return "claim"
    return None


def intake_complete(incident: Incident, estimate_unknown: bool) -> bool:
    has_estimate = incident.estimated_repair_cost_inr is not None or estimate_unknown
    return bool(
        incident.vehicle_id
        and incident.incident_date
        and incident.description_english
        and has_estimate
    )


# What Claude reads off each kind of upload, for rules.verify_details to check.
READ_FIELDS: dict[str, set[str]] = {
    "damage_wide": {"number_plate_text"},
    "dl": {"licence_number", "licence_holder_name", "licence_valid_until"},
}


def mismatch_line(state: ClaimState, codes: list[str], details: dict) -> str:
    """Tell the user which detail didn't match the records and what to upload instead."""
    policy = state["policy"]
    assert policy is not None
    if "PLATE_NOT_READABLE" in codes:
        return line(state, "plate_not_readable")
    if "PLATE_MISMATCH" in codes:
        vehicle = load_wallet().vehicles[policy.vehicle_id]
        return line(
            state,
            "plate_mismatch",
            seen=details["number_plate_text"],
            expected=vehicle.vehicle_number,
        )
    if "DL_NUMBER_MISMATCH" in codes or "DL_NAME_MISMATCH" in codes:
        return line(state, "dl_mismatch", last4=policy.driving_licence_number[-4:])
    if "DL_EXPIRED_ON_INCIDENT_DATE" in codes:
        return line(state, "dl_expired")
    return line(state, "dl_not_readable")


def next_photo_kind(state: ClaimState) -> str | None:
    policy = state["policy"]
    assert policy is not None
    vehicle = load_wallet().vehicles[policy.vehicle_id]
    done = {e.evidence_type for e in state["evidence"] if e.is_accepted}
    pending = [k for k in rules.required_photo_kinds(policy, vehicle) if k not in done]
    return pending[0] if pending else None


# --- 3. nodes ----------------------------------------------------------------------------


async def receive_message(state: ClaimState):
    msg = state["inbox"]
    if msg["type"] != "text":
        return {}

    # save what the user said; a voice message also tells us the language they spoke
    await db.add_message(state["session_id"], "user", msg["text"])
    if msg.get("language"):
        return {"language": msg["language"]}
    return {}


async def greet_user(state: ClaimState):
    user = load_wallet().users[state["user_id"]]
    await db.create_session(state["session_id"], user.id, "INTAKE", state["language"])

    update = await set_phase(state, "INTAKE")
    await say(state, line(state, "greeting", name=user.full_name.split()[0]))
    return update


async def collect_incident(state: ClaimState):
    send({"type": "bot_thinking"})
    text = state["inbox"]["text"]
    incident = state["incident"].model_copy(deep=True)
    vehicles = load_wallet().vehicles_for(state["user_id"])

    # Claude extracts the facts from what the user said
    result = await claude.extract_incident(incident, text, vehicles, state["language"])

    # merge the new facts into the incident and show each new field on screen
    if incident.description_user_language is None:
        incident.description_user_language = text
    updates = result.model_dump(
        exclude={"clarifying_question", "reply_to_user", "estimate_unknown", "risk_flags"},
        exclude_none=True,
    )
    if result.vehicle_id and result.vehicle_id not in {v.id for v in vehicles}:
        updates.pop("vehicle_id")
    if result.risk_flags:
        updates["risk_flags"] = sorted(set(incident.risk_flags) | set(result.risk_flags))
    for name, value in updates.items():
        if getattr(incident, name) != value:
            setattr(incident, name, value)
            send({"type": "field", "name": name, "value": value})

    estimate_unknown = state["estimate_unknown"] or result.estimate_unknown
    await db.save_incident(state["session_id"], incident)
    update = {"incident": incident, "estimate_unknown": estimate_unknown}

    # still missing something: ask, and wait for the next message
    if result.clarifying_question or not intake_complete(incident, estimate_unknown):
        await say(state, result.clarifying_question or result.reply_to_user)
        return update

    return update | await set_phase(state, "MATCH_POLICY")


async def find_policy(state: ClaimState):
    policies = load_wallet().policies_for(state["user_id"])
    policy = rules.match_policy(state["incident"], policies)

    if policy is None:
        update = await set_phase(state, "NO_COVER")
        await say(state, line(state, "no_cover"))
        return update

    send(
        {
            "type": "policy_matched",
            "policy_id": policy.id,
            "insurer_name": policy.insurer_name,
            "policy_number": policy.policy_number,
            "coverage_type": policy.coverage_type,
            "no_claim_bonus_pct": policy.no_claim_bonus_pct,
            "deductible_inr": policy.compulsory_deductible_inr + policy.voluntary_deductible_inr,
            "add_on_covers": policy.add_on_covers,
        }
    )
    return {"policy": policy}


async def check_viability(state: ClaimState):
    incident, policy = state["incident"], state["policy"]
    assert policy is not None
    vehicle = load_wallet().vehicles[policy.vehicle_id]

    # rules compute the numbers, Claude only explains them
    verdict = rules.viability(incident, policy, vehicle)
    await db.save_incident(state["session_id"], incident, policy.id, verdict)
    update = await set_phase(state, "NO_COVER" if verdict.verdict == "not_covered" else "VIABILITY")
    send({"type": "viability", **verdict.model_dump()})

    send({"type": "bot_thinking"})
    reply = await claude.explain_verdict(
        verdict, policy, incident.estimated_repair_cost_inr, state["language"]
    )
    await say(state, reply)
    return update | {"viability": verdict}


async def handle_decision(state: ClaimState):
    phase, decision = state["phase"], read_decision(state["inbox"])

    if phase == "VIABILITY" and decision == "claim":
        update = await set_phase(state, "EVIDENCE")
        kind = next_photo_kind(state)
        await say(state, line(state, "ask_photo", kind=photo_label(state, kind)))
        return update

    if phase == "VIABILITY" and decision == "dont_claim":
        update = await set_phase(state, "ADVISED_NO_CLAIM")
        await say(state, line(state, "advised_no_claim"))
        return update

    if phase == "FORM_REVIEW" and decision == "file":
        try:
            ref = await db.file_claim(state["session_id"])
        except db.DocumentsNotVerified:
            await say(state, line(state, "not_verified"))
            return {}
        if ref is None:  # already filed from the dashboard
            return {}
        update = await set_phase(state, "FILED")
        send({"type": "filed", "claim_reference_number": ref})
        await say(state, line(state, "filed", ref=ref))
        return update

    return {}  # a decision that doesn't fit this step is ignored


async def nudge_user(state: ClaimState):
    """The message doesn't fit this step: tell the user what we need."""
    key = "upload_photo" if state["phase"] == "EVIDENCE" else "use_buttons"
    await say(state, line(state, key))
    return {}


async def grade_photo(state: ClaimState, runtime: Runtime[Turn]):
    kind = next_photo_kind(state)
    if kind is None:
        return {}
    msg = state["inbox"]

    send({"type": "bot_thinking"})
    grade = await claude.grade_damage_photo(
        runtime.context.photo, msg["mime"], kind, state["language"]
    )
    policy = state["policy"]
    assert policy is not None
    vehicle = load_wallet().vehicles[policy.vehicle_id]

    # the plate / licence read off the photo must match the vehicle and the policy's records
    details = grade.model_dump(mode="json", include=READ_FIELDS.get(kind, set()))
    mismatches = rules.verify_details(kind, details, vehicle, policy, state["incident"])
    attempts = state["retakes"].get(kind, 0)
    # A second attempt with decent confidence passes on photo quality, so the demo can't get
    # stuck; a detail that doesn't match the records never passes.
    accepted = not mismatches and (grade.accepted or (attempts >= 1 and grade.confidence >= 0.6))
    retake = None
    if not accepted:
        retake = (
            mismatch_line(state, mismatches, details)
            if mismatches
            else grade.retake_instruction or line(state, "upload_photo")
        )

    evidence = Evidence(
        id=msg["photo_id"],
        evidence_type=kind,
        file_path="",
        is_accepted=accepted,
        quality_issues=[] if accepted else list(grade.issues),
        ai_confidence_score=grade.confidence,
        extracted_details=details,
        detail_mismatches=mismatches,
    )
    await db.add_evidence(state["session_id"], evidence)
    send(
        {
            "type": "photo_graded",
            "photo_id": msg["photo_id"],
            "evidence_type": kind,
            "is_accepted": accepted,
            "quality_issues": evidence.quality_issues,
            "detail_mismatches": mismatches,
            "retake_instruction": retake,
        }
    )
    update = {
        "evidence": [*state["evidence"], evidence],
        "retakes": state["retakes"] | {kind: attempts + 1},
    }

    if retake:
        await say(state, retake)
        return update

    next_kind = next_photo_kind(state | update)
    if next_kind:
        await say(state, line(state, "next_photo", kind=photo_label(state, next_kind)))
        return update

    return update | await set_phase(state, "FORM_REVIEW")


async def review_form(state: ClaimState):
    incident, policy, verdict = state["incident"], state["policy"], state["viability"]
    assert policy is not None
    send({"type": "bot_thinking"})

    user = load_wallet().users[state["user_id"]]
    vehicle = load_wallet().vehicles[policy.vehicle_id]
    ctype = rules.claim_type(incident, policy) or "own_damage"
    required = rules.required_documents(incident, policy)
    missing = rules.missing_documents(incident, policy, state["evidence"])
    cashless = rules.is_cashless(incident, policy)
    est = settlement.estimate(ctype, cashless, docs_complete=not missing)

    form = {
        "policyholder": user.full_name,
        "phone_number": user.phone_number,
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
    checklist = {code: code not in missing for code in required}
    await db.save_claim(
        state["session_id"], policy.id, ctype, form, checklist, (est.min_days, est.max_days)
    )
    send({"type": "form_ready", "form": form})
    send({"type": "missing_docs", "docs": missing})
    send({"type": "settlement", **est.model_dump()})

    reply = await claude.summarise_claim(form, missing, est.model_dump(), state["language"])
    await say(state, reply)
    return {}


# --- 4. routers --------------------------------------------------------------------------


def route_message(
    state: ClaimState,
) -> Literal["start", "incident", "decision", "photo", "other"]:
    msg, phase = state["inbox"], state["phase"]

    if msg["type"] == "start":
        return "start"
    if msg["type"] == "text" and phase == "INTAKE":
        return "incident"
    if msg["type"] == "text" and phase == "VIABILITY" and read_decision(msg):
        return "decision"
    if msg["type"] == "decision":
        return "decision"
    if msg["type"] == "photo" and phase == "EVIDENCE":
        return "photo"
    return "other"


def route_intake(state: ClaimState) -> Literal["complete", "ask_more"]:
    return "complete" if state["phase"] == "MATCH_POLICY" else "ask_more"


def route_policy(state: ClaimState) -> Literal["found", "not_found"]:
    return "found" if state["phase"] == "MATCH_POLICY" else "not_found"


def route_photo(state: ClaimState) -> Literal["all_done", "need_more"]:
    return "all_done" if state["phase"] == "FORM_REVIEW" else "need_more"


# --- 5. graph ----------------------------------------------------------------------------

graph = StateGraph(ClaimState, context_schema=Turn)

graph.add_node("receive", receive_message)
graph.add_node("greet", greet_user)
graph.add_node("intake", collect_incident)
graph.add_node("match_policy", find_policy)
graph.add_node("viability", check_viability)
graph.add_node("decide", handle_decision)
graph.add_node("photo", grade_photo)
graph.add_node("form_review", review_form)
graph.add_node("nudge", nudge_user)

graph.add_edge(START, "receive")
graph.add_conditional_edges(
    "receive",
    route_message,
    {
        "start": "greet",
        "incident": "intake",
        "decision": "decide",
        "photo": "photo",
        "other": "nudge",
    },
)
graph.add_conditional_edges("intake", route_intake, {"complete": "match_policy", "ask_more": END})
graph.add_conditional_edges("match_policy", route_policy, {"found": "viability", "not_found": END})
graph.add_conditional_edges("photo", route_photo, {"all_done": "form_review", "need_more": END})

graph.add_edge("greet", END)
graph.add_edge("viability", END)
graph.add_edge("decide", END)
graph.add_edge("form_review", END)
graph.add_edge("nudge", END)

# The checkpointer remembers each conversation's state between messages (thread = session).
# In-process for now; swap for AsyncPostgresSaver to let a dropped socket resume its session.
checkpointer = InMemorySaver(
    serde=JsonPlusSerializer(
        allowed_msgpack_modules=[
            ("models", "Incident"),
            ("models", "Policy"),
            ("models", "Viability"),
            ("models", "Evidence"),
        ]
    )
)
workflow = graph.compile(checkpointer=checkpointer)


# --- 6. Agent ----------------------------------------------------------------------------

Emit = Callable[[dict], Awaitable[None]]


class Agent:
    """One per WebSocket. Each method turns a client message into one run of the workflow."""

    def __init__(self, user_id: str, language: Language, emit: Emit):
        self.emit = emit
        self.session_id = uuid.uuid4().hex
        self.config = {"configurable": {"thread_id": self.session_id}}
        self.initial_state: ClaimState = {
            "user_id": user_id,
            "session_id": self.session_id,
            "language": language,
            "phase": "INTAKE",
            "incident": Incident(session_id=self.session_id, user_id=user_id),
            "estimate_unknown": False,
            "policy": None,
            "viability": None,
            "evidence": [],
            "retakes": {},
        }

    async def start(self) -> None:
        await self.run(self.initial_state | {"inbox": {"type": "start"}})

    async def on_text(self, text: str) -> None:
        await self.run({"inbox": {"type": "text", "text": text}})

    async def on_audio(self, audio: bytes, mime: str) -> None:
        # speech -> text happens here, outside the graph; if Sarvam fails the user types
        try:
            text, lang = await sarvam.transcribe(audio, mime)
        except Exception as e:  # noqa: BLE001 - any STT failure falls back to typing
            log.warning("stt failed: %s", e)
            await self.emit({"type": "stt_failed"})
            return
        if not text.strip():
            await self.emit({"type": "stt_failed"})
            return
        await self.emit({"type": "transcript", "text": text, "language": lang})
        await self.run({"inbox": {"type": "text", "text": text, "language": lang}})

    async def on_photo(self, image: bytes, mime: str, photo_id: str) -> None:
        msg = {"type": "photo", "mime": mime, "photo_id": photo_id}
        await self.run({"inbox": msg}, Turn(photo=image))

    async def on_decision(self, decision: str) -> None:
        await self.run({"inbox": {"type": "decision", "decision": decision}})

    async def close(self) -> None:
        await checkpointer.adelete_thread(self.session_id)

    async def run(self, update: dict, turn: Turn | None = None) -> None:
        """Run the workflow once and forward every event it sends to the browser."""
        async for event in workflow.astream(
            update, self.config, stream_mode="custom", context=turn or Turn()
        ):
            await self.emit(event)
