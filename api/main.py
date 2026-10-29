"""FastAPI app: wallet lookup, dashboard, filing, and LiveKit tokens.

Run: uvicorn main:app --reload. The conversation itself runs in the LiveKit agent
(agent/claim_agent.py); the browser joins its room with a token from POST /livekit/token.
"""

from __future__ import annotations

import os
import re
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from livekit import api  # noqa: E402
from livekit.protocol.agent_dispatch import RoomAgentDispatch  # noqa: E402
from livekit.protocol.room import RoomConfiguration  # noqa: E402

import db  # noqa: E402
from agent import AGENT_NAME  # noqa: E402
from seed import load_wallet  # noqa: E402


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


@app.post("/livekit/token")
async def livekit_token(user_id: str, language: str = "hi") -> dict:
    """Credentials for a new claim conversation: a fresh room with the claim agent in it."""
    _known_user(user_id)
    user = load_wallet().users[user_id]
    room = f"claim-{user_id}-{uuid.uuid4().hex[:8]}"
    token = (
        api.AccessToken()  # LIVEKIT_API_KEY / LIVEKIT_API_SECRET
        .with_identity(user_id)
        .with_name(user.full_name)
        # the agent reads who is calling, and in which language to start, from these
        .with_attributes({"user_id": user_id, "language": "en" if language == "en" else "hi"})
        .with_grants(api.VideoGrants(room_join=True, room=room))
        .with_room_config(RoomConfiguration(agents=[RoomAgentDispatch(agent_name=AGENT_NAME)]))
        .to_jwt()
    )
    return {"server_url": os.environ["LIVEKIT_URL"], "participant_token": token}
