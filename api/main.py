"""FastAPI app: one WebSocket per conversation. Run: uvicorn main:app --reload

Client -> server messages (JSON):
  {"type": "text", "text": "..."}
  {"type": "audio", "data": "<base64>", "mime": "audio/webm"}
  {"type": "photo", "data": "<base64>", "mime": "image/jpeg", "photo_id": "..."}
  {"type": "decision", "decision": "claim" | "dont_claim" | "file"}
Server -> client: {"type": <event>, ...} as listed in README §9.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import re
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect  # noqa: E402
from fastapi.encoders import jsonable_encoder  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

import db  # noqa: E402
from agent.graph import Agent  # noqa: E402
from agent.lines import FILLERS  # noqa: E402
from seed import load_wallet  # noqa: E402
from services import sarvam  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
log = logging.getLogger("ws")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await db.init()
    yield
    await db.close()


app = FastAPI(title="Claim Karo", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/users/lookup")
async def lookup_user(phone: str) -> dict:
    """Login stand-in: find the Paytm wallet user by mobile number."""
    mobile = re.sub(r"\D", "", phone)[-10:]
    if len(mobile) != 10:
        raise HTTPException(400, "Enter a 10-digit mobile number")
    user = await db.find_user_by_phone(mobile)
    if user is None:
        raise HTTPException(404, "No Paytm account found for this number")
    return user


def _known_user(user_id: str) -> None:
    if user_id not in load_wallet().users:
        raise HTTPException(404, "Unknown user")


@app.get("/users/{user_id}/dashboard")
async def dashboard(user_id: str) -> dict:
    """The user's policies (with required documents) and claims, for the dashboard."""
    _known_user(user_id)
    return {
        "policies": await db.user_policies(user_id),
        "claims": await db.user_claims(user_id),
    }


@app.get("/users/{user_id}/claims/{session_id}")
async def claim_detail(user_id: str, session_id: str) -> dict:
    _known_user(user_id)
    claim = await db.claim_detail(user_id, session_id)
    if claim is None:
        raise HTTPException(404, "Claim not found")
    return claim


@app.post("/users/{user_id}/claims/{session_id}/file")
async def file_claim(user_id: str, session_id: str) -> dict:
    """File a draft claim from the dashboard, without going back to the conversation."""
    _known_user(user_id)
    claim = await db.claim_detail(user_id, session_id)
    if claim is None:
        raise HTTPException(404, "Claim not found")
    if claim["claim_status"] != "draft":
        raise HTTPException(409, "This claim is already filed")
    try:
        reference_number = await db.file_claim(session_id)
    except db.DocumentsNotVerified:
        raise HTTPException(
            409,
            "Can't file yet: the vehicle photo and driving licence must match your policy "
            "records. Continue the claim in chat to upload them.",
        ) from None
    if reference_number is None:
        raise HTTPException(409, "This claim is already filed")
    return {"claim_reference_number": reference_number}


_filler_audio: dict[str, list[str]] = {}


@app.get("/voice/fillers")
async def voice_fillers(language: str = "hi") -> dict:
    """Short "okay…" clips in the bot's voice for the call screen; synthesized once, then cached."""
    if language not in FILLERS:
        raise HTTPException(400, "language must be hi or en")
    if language not in _filler_audio:
        clips = await asyncio.gather(*(sarvam.synthesize(t, language) for t in FILLERS[language]))
        ready = [c for c in clips if c]
        if not ready:
            return {"clips": [], "mime": "audio/mpeg"}  # TTS down: don't cache, try next call
        _filler_audio[language] = ready
    return {"clips": _filler_audio[language], "mime": "audio/mpeg"}


@app.websocket("/ws")
async def conversation(ws: WebSocket, user_id: str, language: str = "hi") -> None:
    await ws.accept()
    wallet = load_wallet()
    if user_id not in wallet.users or language not in ("hi", "en"):
        await ws.send_json({"type": "error", "code": "bad_request", "message": "unknown user"})
        await ws.close()
        return

    async def emit(event: dict) -> None:
        await ws.send_json(jsonable_encoder(event))

    agent = Agent(user_id, language, emit)  # type: ignore[arg-type]
    lock = asyncio.Lock()  # one turn at a time, in arrival order

    async def handle(msg: dict) -> None:
        async with lock:
            try:
                match msg.get("type"):
                    case "text":
                        await agent.on_text(msg["text"])
                    case "audio":
                        await agent.on_audio(base64.b64decode(msg["data"]), msg["mime"])
                    case "photo":
                        await agent.on_photo(
                            base64.b64decode(msg["data"]), msg["mime"], msg["photo_id"]
                        )
                    case "decision":
                        await agent.on_decision(msg["decision"])
            except WebSocketDisconnect:
                pass
            except Exception as e:  # noqa: BLE001 - report to the client, keep the socket open
                log.exception("turn failed")
                await ws.send_json({"type": "error", "code": "turn_failed", "message": str(e)})
            await turn_done()

    async def turn_done() -> None:
        # every message and audio clip of the turn has been sent; the call screen may listen again
        try:
            await emit({"type": "turn_done"})
        except (WebSocketDisconnect, RuntimeError):
            pass

    await agent.start()
    await turn_done()
    tasks: set[asyncio.Task] = set()
    try:
        while True:
            task = asyncio.create_task(handle(await ws.receive_json()))
            tasks.add(task)
            task.add_done_callback(tasks.discard)
    except WebSocketDisconnect:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        await agent.close()  # drop the in-memory checkpoint once no turn can write to it
