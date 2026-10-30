"""The claim's working state for one conversation (the AgentSession's userdata)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field

from livekit import rtc

import db
from agent.lines import LINES, PHOTO_LABEL
from models import Evidence, Incident, Language, Policy, SessionState, User, Vehicle, Viability
from seed import load_wallet
from services import rules

STATE_TOPIC = "claim.state"


@dataclass
class Claim:
    """Everything the session knows about this claim."""

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
        done = {e.evidence_type for e in self.evidence if e.is_accepted}
        pending = rules.required_photo_kinds(self.policy)
        return next((k for k in pending if k not in done), None)

    def restore(self, saved: dict) -> None:
        """Pick a claim up from what db.load_session saved, to continue where it was left."""
        self.stage = saved["stage"]
        row = saved["incident"] or {"session_id": self.session_id, "user_id": self.user.id}
        self.incident = Incident(**{k: v for k, v in row.items() if k in Incident.model_fields})
        wallet = load_wallet()
        self.policy = wallet.policies.get(row.get("policy_id") or "")
        if row.get("viability_assessment"):
            self.viability = Viability(**row["viability_assessment"])
        self.evidence = [Evidence(**e, file_path="") for e in saved["evidence"]]
        for e in self.evidence:
            self.retakes[e.evidence_type] = self.retakes.get(e.evidence_type, 0) + 1
            self.photos[e.id] = {
                "status": "accepted" if e.is_accepted else "retake",
                "evidence_type": e.evidence_type,
                "quality_issues": e.quality_issues + e.detail_mismatches,
            }
        if claim := saved["claim"]:
            self.form = claim["claim_form_data"]
            self.missing_docs = saved["missing_docs"]
            self.settlement = {
                "min_days": claim["expected_settlement_days_min"],
                "max_days": claim["expected_settlement_days_max"],
                "route": self.form.get("route"),
                "docs_complete": not self.missing_docs,
            }
            self.reference = claim["claim_reference_number"]

    async def start_over(self) -> None:
        """Forget the current claim and begin a new one in the same conversation."""
        self.session_id = uuid.uuid4().hex
        self.stage = "INTAKE"
        self.incident = Incident(session_id=self.session_id, user_id=self.user.id)
        self.estimate_unknown = False
        self.policy = self.viability = None
        self.evidence, self.photos, self.retakes = [], {}, {}
        self.form = self.missing_docs = self.settlement = self.reference = None
        await db.create_session(self.session_id, self.user.id, self.stage, self.language)

    async def set_stage(self, stage: SessionState) -> None:
        self.stage = stage
        await db.update_session(self.session_id, stage, self.language)

    def progress(self) -> dict:
        """Where the claim stands, for the user asking what's left to do."""
        next_photo = self.next_photo_kind() if self.policy else None
        return {
            "step": self.stage,
            "facts_recorded": self.incident.model_dump(
                mode="json", exclude_none=True, exclude={"id", "session_id", "user_id"}
            ),
            "verdict": self.viability and self.viability.model_dump(),
            "photos_accepted": [e.evidence_type for e in self.evidence if e.is_accepted],
            "next_photo_needed": next_photo and self.photo_label(next_photo),
            "missing_documents": self.missing_docs
            and load_wallet().document_names(self.missing_docs),
            "settlement_estimate": self.settlement,
            "reference_number": self.reference,
        }

    async def publish(self) -> None:
        """Send the whole claim to the browser; the side panel renders the latest snapshot."""
        p = self.policy
        snapshot = {
            "sessionId": self.session_id,  # changes when the user starts a new claim
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
                "deductible_inr": rules.deductible(p),
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
