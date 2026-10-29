"""Claude's photo and document grading, plus the persona shared with the voice agent.

The conversation itself runs through the LiveKit agent's LLM (agent/claim_agent.py). Grading
is one structured-output request validated by Pydantic; Sonnet 5.5 rejects forced
tool_choice, so we use structured outputs (`messages.parse`) instead of tool use.
"""

from __future__ import annotations

import base64
import logging
import os
import time
from datetime import date
from typing import Literal, TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from models import Language

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
