"""Sarvam speech APIs: STT (saaras) and TTS (bulbul). Docs: https://docs.sarvam.ai"""

from __future__ import annotations

import logging
import os
import time

import httpx

from models import Language

log = logging.getLogger("sarvam")

BASE_URL = "https://api.sarvam.ai"
STT_MODEL = "saaras:v4"
TTS_MODEL = "bulbul:v3"
LANG_CODE = {"hi": "hi-IN", "en": "en-IN"}


def _headers() -> dict[str, str]:
    return {"api-subscription-key": os.getenv("SARVAM_API_KEY", "")}


async def transcribe(audio: bytes, mime: str) -> tuple[str, Language]:
    """Return (transcript, detected language). Raises on failure or timeout."""
    ext = "webm" if "webm" in mime else "wav"
    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=8) as client:
        r = await client.post(
            f"{BASE_URL}/speech-to-text",
            headers=_headers(),
            files={"file": (f"audio.{ext}", audio, mime.split(";")[0])},
            data={"model": STT_MODEL, "language_code": "unknown"},
        )
    r.raise_for_status()
    body = r.json()
    log.info("stt ok in %.2fs (%s)", time.perf_counter() - start, body.get("language_code"))
    lang: Language = "en" if (body.get("language_code") or "").startswith("en") else "hi"
    return body["transcript"], lang


async def synthesize(text: str, language: Language) -> str | None:
    """Return base64 mp3, or None if TTS is not configured or fails (text is always shown)."""
    if not os.getenv("SARVAM_API_KEY"):
        return None
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{BASE_URL}/text-to-speech",
                headers=_headers(),
                json={
                    "text": text[:2500],
                    "language_code": LANG_CODE[language],
                    "model": TTS_MODEL,
                    "speaker": os.getenv("SARVAM_TTS_SPEAKER") or "shubh",
                    "output_audio_codec": "mp3",
                },
            )
        r.raise_for_status()
        log.info("tts ok in %.2fs", time.perf_counter() - start)
        return r.json()["audios"][0]
    except (httpx.HTTPError, KeyError, IndexError) as e:
        log.warning("tts failed: %s", e)
        return None

