"""Conversation state machine (README §4). One Agent per WebSocket connection.

Each handler does one job and pushes events to the browser through `emit`.
Money math lives in services/rules.py; Claude only extracts and explains.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from collections.abc import Awaitable, Callable
from datetime import date

import db
from models import Evidence, Incident, Language, Policy, SessionState, Viability
from seed import load_wallet
from services import claude, rules, sarvam, settlement

log = logging.getLogger("agent")

Emit = Callable[[dict], Awaitable[None]]

# Fixed bot lines, so the common prompts never wait on Claude.
LINES: dict[str, dict[Language, str]] = {
    "greeting": {
        "hi": "नमस्ते {name}! मैं Claim Karo हूँ। बताइए, आपकी गाड़ी के साथ क्या हुआ?",
        "en": "Hi {name}! I'm Claim Karo. Tell me what happened to your vehicle.",
    },
    "no_cover": {
        "hi": "माफ़ कीजिए, इस गाड़ी के लिए इस नुकसान पर आपकी पॉलिसी में कवर नहीं है।",
        "en": "Sorry, none of your policies cover this damage for this vehicle.",
    },
    "ask_photo": {
        "hi": "ठीक है, claim शुरू करते हैं। कृपया {kind} की फ़ोटो अपलोड करें।",
        "en": "Great, let's start the claim. Please upload a photo: {kind}.",
    },
    "next_photo": {
        "hi": "फ़ोटो ठीक है। अब {kind} की फ़ोटो अपलोड करें।",
        "en": "Got it. Now please upload a photo: {kind}.",
    },
    "advised_no_claim": {
        "hi": "ठीक है, claim नहीं करते। आपका No-Claim Bonus सुरक्षित है। ध्यान रखिए!",
        "en": "Okay, no claim then. Your No-Claim Bonus stays safe. Take care!",
    },
    "filed": {
        "hi": "आपका claim फ़ाइल हो गया। रेफ़रेंस नंबर {ref} है।",
        "en": "Your claim is filed. Your reference number is {ref}.",
    },
    "use_buttons": {
        "hi": "कृपया नीचे दिए बटन से चुनें।",
        "en": "Please choose using the buttons below.",
    },
    "upload_photo": {
        "hi": "कृपया फ़ोटो अपलोड करें।",
        "en": "Please upload the photo.",
    },
}

PHOTO_LABEL: dict[str, dict[Language, str]] = {
    "damage_wide": {
        "hi": "पूरी गाड़ी, नुकसान और नंबर प्लेट साफ़ दिखे",
        "en": "the whole vehicle with the damage and number plate visible",
    },
    "odometer": {"hi": "ओडोमीटर रीडिंग", "en": "the odometer reading"},
}

YES = ("haan", "han", "ha", "yes", "ok", "okay", "claim karo", "file", "हाँ", "हां", "जी")
NO = ("nahi", "nahin", "no", "mat", "नहीं", "ना")


class Agent:
    def __init__(self, user_id: str, language: Language, emit: Emit):
        self.wallet = load_wallet()
        self.user = self.wallet.users[user_id]
        self.vehicles = self.wallet.vehicles_for(user_id)
        self.language: Language = language
        self.emit = emit
        self.state: SessionState = "INTAKE"
        self.session_id = uuid.uuid4().hex
        self.incident = Incident(session_id=self.session_id, user_id=user_id)
        self.estimate_unknown = False
        self.policy: Policy | None = None
        self.viability: Viability | None = None
        self.evidence: list[Evidence] = []
        self.retakes: dict[str, int] = {}

    # --- inputs --------------------------------------------------------------------------

    async def start(self) -> None:
        await db.create_session(self.session_id, self.user.id, self.state, self.language)
        await self._set_state("INTAKE")
        await self.say(self._line("greeting", name=self.user.name.split()[0]))

    async def on_text(self, text: str) -> None:
        await db.add_message(self.session_id, "user", text)
        if self.state == "INTAKE":
            await self._intake(text)
        elif self.state == "VIABILITY":
            lowered = text.strip().lower()
            if any(w in lowered for w in NO):
                await self.on_decision("dont_claim")
            elif any(w in lowered for w in YES):
                await self.on_decision("claim")
            else:
                await self.say(self._line("use_buttons"))
        elif self.state == "EVIDENCE":
            await self.say(self._line("upload_photo"))
        else:
            await self.say(self._line("use_buttons"))

    async def on_audio(self, audio: bytes, mime: str) -> None:
        try:
            text, lang = await sarvam.transcribe(audio, mime)
        except Exception as e:  # noqa: BLE001 - any STT failure falls back to typing
            log.warning("stt failed: %s", e)
            await self.emit({"type": "stt_failed"})
            return
        if not text.strip():
            await self.emit({"type": "stt_failed"})
            return
        self.language = lang
        await self.emit({"type": "transcript", "text": text, "language": lang})
        await self.on_text(text)

    async def on_photo(self, image: bytes, mime: str, photo_id: str) -> None:
        if self.state != "EVIDENCE":
            await self.say(self._line("use_buttons"))
            return
        kind = self._next_photo_kind()
        if kind is None:
            return
        await self.emit({"type": "bot_thinking"})
        grade = await claude.grade_damage_photo(image, mime, kind, self.language)
        attempts = self.retakes.get(kind, 0)
        # Second attempt with decent confidence is accepted, so the demo can't get stuck.
        accepted = grade.accepted or (attempts >= 1 and grade.confidence >= 0.6)
        self.retakes[kind] = attempts + 1
        evidence = Evidence(
            id=photo_id,
            kind=kind,
            file_path="",
            accepted=accepted,
            issues=[] if accepted else list(grade.issues),
            confidence=grade.confidence,
        )
        self.evidence.append(evidence)
        await db.add_evidence(self.session_id, evidence)
        await self.emit(
            {
                "type": "photo_graded",
                "photo_id": photo_id,
                "kind": kind,
                "accepted": accepted,
                "issues": evidence.issues,
                "retake_instruction": None if accepted else grade.retake_instruction,
            }
        )
        if not accepted:
            await self.say(grade.retake_instruction or self._line("upload_photo"))
            return
        next_kind = self._next_photo_kind()
        if next_kind:
            await self.say(self._line("next_photo", kind=self._photo_label(next_kind)))
        else:
            await self._form_review()

    async def on_decision(self, decision: str) -> None:
        if self.state == "VIABILITY" and decision == "claim":
            await self._set_state("EVIDENCE")
            kind = self._next_photo_kind()
            await self.say(self._line("ask_photo", kind=self._photo_label(kind)))
        elif self.state == "VIABILITY" and decision == "dont_claim":
            await self._set_state("ADVISED_NO_CLAIM")
            await self.say(self._line("advised_no_claim"))
        elif self.state == "FORM_REVIEW" and decision == "file":
            ref = f"CK-{date.today():%y%m%d}-{secrets.token_hex(3).upper()}"
            await db.file_claim(self.session_id, ref)
            await self._set_state("FILED")
            await self.emit({"type": "filed", "reference_no": ref})
            await self.say(self._line("filed", ref=ref))

    # --- states --------------------------------------------------------------------------

    async def _intake(self, text: str) -> None:
        await self.emit({"type": "bot_thinking"})
        result = await claude.extract_incident(self.incident, text, self.vehicles, self.language)

        if self.incident.description_original is None:
            self.incident.description_original = text
        updates = result.model_dump(
            exclude={"clarifying_question", "reply_to_user", "estimate_unknown", "flags"},
            exclude_none=True,
        )
        if result.vehicle_id and result.vehicle_id not in {v.id for v in self.vehicles}:
            updates.pop("vehicle_id")
        if result.flags:
            updates["flags"] = sorted(set(self.incident.flags) | set(result.flags))
        for name, value in updates.items():
            if getattr(self.incident, name) != value:
                setattr(self.incident, name, value)
                await self.emit({"type": "field", "name": name, "value": value})
        self.estimate_unknown = self.estimate_unknown or result.estimate_unknown
        await db.save_incident(self.session_id, self.incident)

        if result.clarifying_question or not self._intake_complete():
            await self.say(result.clarifying_question or result.reply_to_user)
            return
        await self._match_policy()

    def _intake_complete(self) -> bool:
        i = self.incident
        has_estimate = i.estimated_damage_inr is not None or self.estimate_unknown
        return bool(i.vehicle_id and i.incident_date and i.description_en and has_estimate)

    async def _match_policy(self) -> None:
        await self._set_state("MATCH_POLICY")
        policy = rules.match_policy(self.incident, self.wallet.policies_for(self.user.id))
        if policy is None:
            await self._set_state("NO_COVER")
            await self.say(self._line("no_cover"))
            return
        self.policy = policy
        await self.emit(
            {
                "type": "policy_matched",
                "policy_id": policy.id,
                "insurer": policy.insurer,
                "policy_no": policy.policy_no,
                "cover_type": policy.cover_type,
                "ncb_pct": policy.ncb_pct,
                "deductible_inr": policy.compulsory_deductible_inr
                + policy.voluntary_deductible_inr,
                "addons": policy.addons,
            }
        )
        await self._viability()

    async def _viability(self) -> None:
        assert self.policy is not None
        vehicle = self.wallet.vehicles[self.policy.vehicle_id]
        self.viability = rules.viability(self.incident, self.policy, vehicle)
        await db.save_incident(self.session_id, self.incident, self.policy.id, self.viability)
        await self._set_state(
            "NO_COVER" if self.viability.verdict == "not_covered" else "VIABILITY"
        )
        await self.emit({"type": "viability", **self.viability.model_dump()})
        await self.emit({"type": "bot_thinking"})
        reply = await claude.explain_verdict(
            self.viability, self.policy, self.incident.estimated_damage_inr, self.language
        )
        await self.say(reply)

    async def _form_review(self) -> None:
        assert self.policy is not None
        await self._set_state("FORM_REVIEW")
        await self.emit({"type": "bot_thinking"})
        vehicle = self.wallet.vehicles[self.policy.vehicle_id]
        ctype = rules.claim_type(self.incident, self.policy) or "own_damage"
        missing = rules.missing_documents(self.incident, self.policy, self.evidence)
        cashless = rules.is_cashless(self.incident, self.policy)
        est = settlement.estimate(ctype, cashless, docs_complete=not missing)
        form = {
            "policyholder": self.user.name,
            "phone": self.user.phone,
            "insurer": self.policy.insurer,
            "policy_no": self.policy.policy_no,
            "vehicle": f"{vehicle.make_model} ({vehicle.reg_no})",
            "claim_type": ctype,
            "incident_date": str(self.incident.incident_date),
            "location": self.incident.location,
            "description": self.incident.description_en,
            "estimated_damage_inr": self.incident.estimated_damage_inr,
            "expected_payout_inr": self.viability.insurer_payout_inr if self.viability else None,
            "garage": self.incident.garage_name,
            "route": est.route,
        }
        await db.save_claim(
            self.session_id, self.policy.id, ctype, form, missing, (est.min_days, est.max_days)
        )
        await self.emit({"type": "form_ready", "form": form})
        await self.emit({"type": "missing_docs", "docs": missing})
        await self.emit({"type": "settlement", **est.model_dump()})
        reply = await claude.summarise_claim(form, missing, est.model_dump(), self.language)
        await self.say(reply)

    # --- helpers -------------------------------------------------------------------------

    async def say(self, text: str) -> None:
        """Text first (always), then audio if TTS works."""
        await db.add_message(self.session_id, "bot", text)
        await self.emit({"type": "bot_message", "text": text, "language": self.language})
        audio = await sarvam.synthesize(text, self.language)
        if audio:
            await self.emit({"type": "audio", "data": audio, "mime": "audio/mpeg"})

    async def _set_state(self, state: SessionState) -> None:
        self.state = state
        await db.update_session(self.session_id, state, self.language)
        await self.emit({"type": "state", "state": state})

    def _line(self, key: str, **kwargs: str) -> str:
        return LINES[key][self.language].format(**kwargs)

    def _next_photo_kind(self) -> str | None:
        assert self.policy is not None
        vehicle = self.wallet.vehicles[self.policy.vehicle_id]
        done = {e.kind for e in self.evidence if e.accepted}
        pending = [k for k in rules.required_photo_kinds(self.incident, vehicle) if k not in done]
        return pending[0] if pending else None

    def _photo_label(self, kind: str | None) -> str:
        return PHOTO_LABEL.get(kind or "", {}).get(self.language, kind or "")
