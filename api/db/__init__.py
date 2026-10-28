"""Postgres persistence (asyncpg). Schema in db/schema.sql; connection from DATABASE_URL.

The agent keeps working state in memory and writes through to these tables so every
conversation can be inspected in CloudBeaver (http://localhost:8978).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import asyncpg

from models import Evidence, Incident, Viability
from seed import load_wallet

SCHEMA = Path(__file__).with_name("schema.sql")
_pool: asyncpg.Pool | None = None


async def _init_conn(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("db.init() has not been called")
    return _pool


async def init() -> None:
    global _pool
    _pool = await asyncpg.create_pool(os.environ["DATABASE_URL"], init=_init_conn)
    async with _pool.acquire() as conn:
        await conn.execute(SCHEMA.read_text(encoding="utf-8"))
        await _seed_wallet(conn)


async def close() -> None:
    if _pool is not None:
        await _pool.close()


async def _seed_wallet(conn: asyncpg.Connection) -> None:
    wallet = load_wallet()
    await conn.executemany(
        """INSERT INTO users (id, name, language, phone) VALUES ($1, $2, $3, $4)
           ON CONFLICT (id) DO UPDATE SET name = $2, language = $3, phone = $4""",
        [(u.id, u.name, u.language, u.phone) for u in wallet.users.values()],
    )
    await conn.executemany(
        """INSERT INTO vehicles (id, user_id, type, reg_no, make_model, year)
           VALUES ($1, $2, $3, $4, $5, $6)
           ON CONFLICT (id) DO UPDATE SET user_id = $2, type = $3, reg_no = $4,
               make_model = $5, year = $6""",
        [
            (v.id, v.user_id, v.type, v.reg_no, v.make_model, v.year)
            for v in wallet.vehicles.values()
        ],
    )
    columns = list(next(iter(wallet.policies.values())).model_dump().keys())
    placeholders = ", ".join(f"${i}" for i in range(1, len(columns) + 1))
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns if c != "id")
    await conn.executemany(
        f"""INSERT INTO policies ({", ".join(columns)}) VALUES ({placeholders})
            ON CONFLICT (id) DO UPDATE SET {updates}""",
        [tuple(p.model_dump().values()) for p in wallet.policies.values()],
    )


async def create_session(session_id: str, user_id: str, state: str, language: str) -> None:
    await pool().execute(
        "INSERT INTO sessions (id, user_id, state, language) VALUES ($1, $2, $3, $4)",
        session_id,
        user_id,
        state,
        language,
    )


async def update_session(session_id: str, state: str, language: str) -> None:
    await pool().execute(
        "UPDATE sessions SET state = $2, language = $3, updated_at = now() WHERE id = $1",
        session_id,
        state,
        language,
    )


async def add_message(session_id: str, role: str, text: str) -> None:
    await pool().execute(
        "INSERT INTO messages (session_id, role, text) VALUES ($1, $2, $3)",
        session_id,
        role,
        text,
    )


async def save_incident(
    session_id: str,
    incident: Incident,
    policy_id: str | None = None,
    viability: Viability | None = None,
) -> None:
    i = incident
    await pool().execute(
        """INSERT INTO incidents (session_id, user_id, vehicle_id, policy_id, incident_date,
               location, description_en, description_original, third_party_involved,
               third_party_damage, injuries, estimated_damage_inr, garage_name,
               police_report_filed, flags, verdict, viability)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
           ON CONFLICT (session_id) DO UPDATE SET
               vehicle_id = $3, policy_id = $4, incident_date = $5, location = $6,
               description_en = $7, description_original = $8, third_party_involved = $9,
               third_party_damage = $10, injuries = $11, estimated_damage_inr = $12,
               garage_name = $13, police_report_filed = $14, flags = $15, verdict = $16,
               viability = $17, updated_at = now()""",
        session_id,
        i.user_id,
        i.vehicle_id,
        policy_id,
        i.incident_date,
        i.location,
        i.description_en,
        i.description_original,
        i.third_party_involved,
        i.third_party_damage,
        i.injuries,
        i.estimated_damage_inr,
        i.garage_name,
        i.police_report_filed,
        i.flags,
        viability.verdict if viability else None,
        viability.model_dump() if viability else None,
    )


async def add_evidence(session_id: str, e: Evidence) -> None:
    await pool().execute(
        """INSERT INTO evidence (id, session_id, kind, accepted, issues, confidence)
           VALUES ($1, $2, $3, $4, $5, $6)""",
        e.id,
        session_id,
        e.kind,
        e.accepted,
        e.issues,
        e.confidence,
    )


async def save_claim(
    session_id: str,
    policy_id: str,
    claim_type: str,
    form: dict,
    missing_docs: list[str],
    days: tuple[int, int],
) -> None:
    await pool().execute(
        """INSERT INTO claims (session_id, policy_id, claim_type, form, missing_docs,
               settlement_days_min, settlement_days_max)
           VALUES ($1, $2, $3, $4, $5, $6, $7)
           ON CONFLICT (session_id) DO UPDATE SET claim_type = $3, form = $4,
               missing_docs = $5, settlement_days_min = $6, settlement_days_max = $7""",
        session_id,
        policy_id,
        claim_type,
        form,
        missing_docs,
        *days,
    )


async def file_claim(session_id: str, reference_no: str) -> None:
    await pool().execute(
        """UPDATE claims SET status = 'filed', reference_no = $2, filed_at = now()
           WHERE session_id = $1""",
        session_id,
        reference_no,
    )


async def find_user_by_phone(mobile: str) -> dict | None:
    """Look up a wallet user by the last 10 digits of their phone, with vehicles + policies."""
    async with pool().acquire() as conn:
        user = await conn.fetchrow(
            """SELECT id, name, language, phone FROM users
               WHERE right(regexp_replace(phone, '\D', '', 'g'), 10) = $1""",
            mobile,
        )
        if user is None:
            return None
        rows = await conn.fetch(
            """SELECT v.id, v.type, v.reg_no, v.make_model, v.year,
                      p.id AS policy_id, p.insurer, p.policy_no, p.cover_type, p.ncb_pct,
                      p.period_end, p.idv_inr, p.addons
               FROM vehicles v LEFT JOIN policies p ON p.vehicle_id = v.id
               WHERE v.user_id = $1 ORDER BY v.id""",
            user["id"],
        )
    vehicles = []
    for r in rows:
        vehicle = {k: r[k] for k in ("id", "type", "reg_no", "make_model", "year")}
        vehicle["policy"] = (
            {
                k: r[k]
                for k in (
                    "insurer",
                    "policy_no",
                    "cover_type",
                    "ncb_pct",
                    "period_end",
                    "idv_inr",
                    "addons",
                )
            }
            | {"id": r["policy_id"]}
            if r["policy_id"]
            else None
        )
        vehicles.append(vehicle)
    return {**dict(user), "vehicles": vehicles}
