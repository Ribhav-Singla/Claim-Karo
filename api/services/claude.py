"""Claude calls. Each function is one structured-output request validated by Pydantic.

Rules decide, Claude explains: every number Claude mentions comes in through the prompt.
Sonnet 5.5 rejects forced tool_choice and custom temperature, so we use structured
outputs (`messages.parse`) instead of tool use.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from datetime import date
from typing import Literal, TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from models import Incident, Language, Policy, Vehicle, Viability

log = logging.getLogger("claude")
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
_client = anthropic.AsyncAnthropic()

SYSTEM = """You are Claim Karo, a friendly motor-insurance claim assistant inside Paytm.
Users are Indian two-wheeler and car owners describing an accident.
Never invent policy numbers, amounts, dates or terms: use only numbers given to you.
Replies are read aloud by a TTS engine, so keep them short (max 3 sentences), no markdown,
no bullet points. Write rupee amounts like "₹4,200".
Language: when asked for Hindi ("hi"), write natural conversational Hindi in Devanagari
(Hinglish-friendly, common English words like claim, policy, bonus are fine; avoid heavy
Sanskritised Hindi). When asked for English ("en"), write simple Indian English."""

LANG_NAME = {"hi": "Hindi", "en": "English"}
T = TypeVar("T", bound=BaseModel)


async def _parse(output: type[T], content: list[dict] | str, task: str) -> T:
    """One structured-output call with a single retry on validation failure."""
    for attempt in range(2):
        start = time.perf_counter()
        try:
            response = await _client.messages.parse(
                model=MODEL,
                max_tokens=4000,
                system=SYSTEM,
                output_config={"effort": "low"},
                messages=[{"role": "user", "content": content}],
                output_format=output,
            )
            log.info("%s ok in %.2fs", task, time.perf_counter() - start)
            if response.parsed_output is None:
                raise ValueError(f"no parsed output (stop_reason={response.stop_reason})")
            return response.parsed_output
        except (ValidationError, ValueError) as e:
            log.warning("%s attempt %d failed: %s", task, attempt + 1, e)
            if attempt == 1:
                raise
    raise RuntimeError("unreachable")


# --- extract_incident -------------------------------------------------------------------


class ExtractedIncident(BaseModel):
    vehicle_id: str | None
    incident_date: date | None
    incident_location: str | None
    description_english: str | None
    third_party_involved: bool | None
    third_party_property_damaged: bool | None
    anyone_injured: bool | None
    estimated_repair_cost_inr: int | None
    estimate_unknown: bool
    garage_name: str | None
    police_report_filed: bool | None
    risk_flags: list[
        Literal["drunk_driving", "no_valid_dl", "commercial_use", "theft", "hit_and_run"]
    ]
    clarifying_question: str | None
    reply_to_user: str


async def extract_incident(
    incident: Incident, utterance: str, vehicles: list[Vehicle], language: Language
) -> ExtractedIncident:
    vehicle_list = "\n".join(
        f'- id "{v.id}": {v.brand} {v.model} ({v.vehicle_type}), reg {v.vehicle_number}'
        for v in vehicles
    )
    prompt = f"""Task: extract a motor accident incident from the user's latest message.
Today is {date.today().isoformat()} (resolve "kal"/"yesterday"/"last night" against it).

User's vehicles:
{vehicle_list}

Incident so far (JSON): {incident.model_dump_json(exclude_none=True)}

Latest user message: "{utterance}"

Rules:
- Return only what this message adds or changes; use null for anything not mentioned.
- vehicle_id must be one of the ids above; pick it from make/model/type/reg mentioned.
  If the user has only one vehicle of the mentioned type, pick that.
- description_english: one-line English summary of the whole incident so far.
- estimated_repair_cost_inr: integer rupees ("4200", "4.2k", "chaar hazaar do sau" -> 4200).
- estimate_unknown: true only if the user says they don't know the cost ("pata nahi").
- Required to proceed: vehicle, incident date, what happened, and a damage estimate
  (or estimate_unknown). If anything required is still missing after merging with the
  incident so far, set clarifying_question to ONE short question for the most important
  missing item, and make reply_to_user that question. Otherwise clarifying_question is
  null and reply_to_user is a one-line acknowledgement.
- reply_to_user must be in {LANG_NAME[language]}."""
    return await _parse(ExtractedIncident, prompt, "extract_incident")


# --- explain_verdict ---------------------------------------------------------------------


class Reply(BaseModel):
    reply_to_user: str


async def explain_verdict(
    viability: Viability, policy: Policy, estimate: int | None, language: Language
) -> str:
    prompt = f"""Task: explain the claim viability verdict to the user.
Language: {LANG_NAME[language]}.

Policy: {policy.insurer_name}, NCB {policy.no_claim_bonus_pct}%,
addons {policy.add_on_covers or "none"}.
Damage estimate: {f"₹{estimate:,}" if estimate is not None else "not known yet"}
Computed result (JSON, already final, do not recompute):
{viability.model_dump_json()}

Explain in max 3 short sentences: what the insurer would pay, what they would lose in
No-Claim Bonus (use the 3-year total), and the recommendation. If estimate_pending, say
claiming makes sense only above breakeven_estimate_inr and ask for the garage estimate.
If not_covered, say why from the reason codes. End by asking whether they want to file
the claim (unless not_covered)."""
    return (await _parse(Reply, prompt, "explain_verdict")).reply_to_user


# --- grade_damage_photo ------------------------------------------------------------------

IssueCode = Literal[
    "BLURRY",
    "TOO_DARK",
    "PLATE_NOT_VISIBLE",
    "DAMAGE_NOT_VISIBLE",
    "TOO_FAR",
    "TOO_CLOSE",
    "WRONG_SUBJECT",
    "TEXT_ILLEGIBLE",
]

CHECKLIST = {
    "damage_wide": "whole vehicle visible, damaged area in frame, number plate legible",
    "damage_close": "damage fills at least 30% of the frame, in focus",
    "number_plate": "number plate legible",
    "odometer": "odometer reading legible",
    "garage_estimate": "document, itemised, total and date legible",
    "dl": "front of a driving licence; licence number, holder name and validity date legible",
}


class PhotoGrade(BaseModel):
    accepted: bool
    issues: list[IssueCode]
    confidence: float
    retake_instruction: str | None
    damage_observed: str
    # Read off the photo so rules.verify_details can compare them with the records.
    number_plate_text: str | None
    licence_number: str | None
    licence_holder_name: str | None
    licence_valid_until: date | None


async def grade_damage_photo(
    image: bytes, media_type: str, expected_kind: str, language: Language
) -> PhotoGrade:
    content = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": base64.standard_b64encode(image).decode(),
            },
        },
        {
            "type": "text",
            "text": f"""Task: grade this photo for an insurance surveyor.
Expected shot: {expected_kind} ({CHECKLIST.get(expected_kind, "")}).
Set accepted=false with issue codes if it fails the requirement. confidence is 0-1.
retake_instruction: one short sentence in {LANG_NAME[language]} telling the user how to
retake (null if accepted). damage_observed: short English description of visible damage.
number_plate_text: the vehicle's registration number exactly as printed on its number plate
(null if no plate is legible). For a driving licence: licence_number, licence_holder_name and
licence_valid_until (YYYY-MM-DD, non-transport validity); null for any other shot. Copy what
is printed; never guess unclear characters, use null instead.""",
        },
    ]
    return await _parse(PhotoGrade, content, "grade_damage_photo")


# --- summarise_claim ---------------------------------------------------------------------


async def summarise_claim(
    form: dict, missing_docs: list[str], settlement: dict, language: Language
) -> str:
    prompt = f"""Task: summarise the pre-filled claim for the user before they file it.
Language: {LANG_NAME[language]}.
Claim form: {json.dumps(form, default=str, ensure_ascii=False)}
Missing documents: {missing_docs or "none"}
Settlement estimate: {settlement}
In max 3 sentences: confirm the claim is ready, name any missing documents, give the
settlement time, and ask them to tap "File claim"."""
    return (await _parse(Reply, prompt, "summarise_claim")).reply_to_user
