"""Postgres persistence (asyncpg). Schema in db/schema.sql; connection from DATABASE_URL.

The agent keeps working state in memory and writes through to these tables so every
conversation can be inspected in CloudBeaver (http://localhost:8978).
"""

from __future__ import annotations

import json
import os
import secrets
from datetime import date
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
        """INSERT INTO documents (code, name_en, name_hi) VALUES ($1, $2, $3)
           ON CONFLICT (code) DO UPDATE SET name_en = $2, name_hi = $3""",
        [(d.code, d.name_en, d.name_hi) for d in wallet.documents.values()],
    )
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
    # required_documents lives in its own table, so it is left out of the policies row.
    rows = [p.model_dump(exclude={"required_documents"}) for p in wallet.policies.values()]
    columns = list(rows[0].keys())
    placeholders = ", ".join(f"${i}" for i in range(1, len(columns) + 1))
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns if c != "id")
    await conn.executemany(
        f"""INSERT INTO policies ({", ".join(columns)}) VALUES ({placeholders})
            ON CONFLICT (id) DO UPDATE SET {updates}""",
        [tuple(r.values()) for r in rows],
    )
    async with conn.transaction():
        await conn.execute(
            "DELETE FROM policy_required_documents WHERE policy_id = ANY($1)",
            list(wallet.policies),
        )
        await conn.executemany(
            "INSERT INTO policy_required_documents (policy_id, document_code) VALUES ($1, $2)",
            [
                (p.id, code)
                for p in wallet.policies.values()
                for code in dict.fromkeys(p.required_documents)
            ],
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
    documents: dict[str, bool],
    days: tuple[int, int],
) -> None:
    """Save the draft claim and its document checklist ({document code: provided})."""
    async with pool().acquire() as conn, conn.transaction():
        await conn.execute(
            """INSERT INTO claims (session_id, policy_id, claim_type, form,
                   settlement_days_min, settlement_days_max)
               VALUES ($1, $2, $3, $4, $5, $6)
               ON CONFLICT (session_id) DO UPDATE SET claim_type = $3, form = $4,
                   settlement_days_min = $5, settlement_days_max = $6""",
            session_id,
            policy_id,
            claim_type,
            form,
            *days,
        )
        await conn.execute("DELETE FROM claim_documents WHERE session_id = $1", session_id)
        await conn.executemany(
            """INSERT INTO claim_documents (session_id, document_code, provided)
               VALUES ($1, $2, $3)""",
            [(session_id, code, provided) for code, provided in documents.items()],
        )


async def file_claim(session_id: str) -> str | None:
    """File a draft claim and return its new reference number (None if it isn't a draft)."""
    reference_no = f"CK-{date.today():%y%m%d}-{secrets.token_hex(3).upper()}"
    async with pool().acquire() as conn, conn.transaction():
        filed = await conn.fetchval(
            """UPDATE claims SET status = 'filed', reference_no = $2, filed_at = now()
               WHERE session_id = $1 AND status = 'draft'
               RETURNING reference_no""",
            session_id,
            reference_no,
        )
        if filed:
            await conn.execute(
                "UPDATE sessions SET state = 'FILED', updated_at = now() WHERE id = $1",
                session_id,
            )
    return filed


async def user_policies(user_id: str) -> list[dict]:
    """Every policy the user holds, with its vehicle and the documents a claim on it needs."""
    rows = await pool().fetch(
        """SELECT p.id, p.insurer, p.policy_no, p.cover_type, p.period_start, p.period_end,
                  p.idv_inr, p.ncb_pct, p.addons,
                  p.compulsory_deductible_inr + p.voluntary_deductible_inr AS deductible_inr,
                  jsonb_build_object('id', v.id, 'type', v.type, 'reg_no', v.reg_no,
                                     'make_model', v.make_model, 'year', v.year) AS vehicle,
                  coalesce(jsonb_agg(jsonb_build_object('code', d.code, 'name_en', d.name_en,
                                                        'name_hi', d.name_hi)
                                     ORDER BY d.name_en) FILTER (WHERE d.code IS NOT NULL),
                           '[]') AS required_documents
           FROM policies p
           JOIN vehicles v ON v.id = p.vehicle_id
           LEFT JOIN policy_required_documents r ON r.policy_id = p.id
           LEFT JOIN documents d ON d.code = r.document_code
           WHERE p.user_id = $1
           GROUP BY p.id, v.id
           ORDER BY p.period_end DESC""",
        user_id,
    )
    return [dict(r) for r in rows]


async def user_claims(user_id: str) -> list[dict]:
    """The user's claims, newest first, with enough to list them."""
    rows = await pool().fetch(
        """SELECT c.session_id, c.status, c.reference_no, c.claim_type, c.created_at,
                  c.filed_at, c.settlement_days_min, c.settlement_days_max,
                  p.insurer, p.policy_no, v.make_model, v.reg_no,
                  i.incident_date, i.estimated_damage_inr, i.verdict,
                  (c.form ->> 'expected_payout_inr')::int AS expected_payout_inr,
                  (SELECT count(*) FROM claim_documents cd
                   WHERE cd.session_id = c.session_id AND NOT cd.provided) AS documents_missing
           FROM claims c
           JOIN sessions s ON s.id = c.session_id
           JOIN policies p ON p.id = c.policy_id
           JOIN vehicles v ON v.id = p.vehicle_id
           LEFT JOIN incidents i ON i.session_id = c.session_id
           WHERE s.user_id = $1
           ORDER BY c.created_at DESC""",
        user_id,
    )
    return [dict(r) for r in rows]


async def claim_detail(user_id: str, session_id: str) -> dict | None:
    """One claim with its checklist, verdict, photos and conversation (None if not the user's)."""
    async with pool().acquire() as conn:
        claim = await conn.fetchrow(
            """SELECT c.session_id, c.status, c.reference_no, c.claim_type, c.form,
                      c.settlement_days_min, c.settlement_days_max, c.created_at, c.filed_at,
                      i.verdict, i.viability
               FROM claims c
               JOIN sessions s ON s.id = c.session_id
               LEFT JOIN incidents i ON i.session_id = c.session_id
               WHERE c.session_id = $1 AND s.user_id = $2""",
            session_id,
            user_id,
        )
        if claim is None:
            return None
        documents = await conn.fetch(
            """SELECT d.code, d.name_en, d.name_hi, cd.provided
               FROM claim_documents cd JOIN documents d ON d.code = cd.document_code
               WHERE cd.session_id = $1
               ORDER BY cd.provided, d.name_en""",
            session_id,
        )
        evidence = await conn.fetch(
            """SELECT id, kind, accepted, issues, confidence, created_at FROM evidence
               WHERE session_id = $1 ORDER BY created_at""",
            session_id,
        )
        messages = await conn.fetch(
            "SELECT role, text, created_at FROM messages WHERE session_id = $1 ORDER BY id",
            session_id,
        )
    return {
        **dict(claim),
        "documents": [dict(r) for r in documents],
        "evidence": [dict(r) for r in evidence],
        "messages": [dict(r) for r in messages],
    }


async def find_user_by_phone(mobile: str) -> dict | None:
    """Look up a wallet user by the last 10 digits of their phone, with vehicles + policies."""
    async with pool().acquire() as conn:
        user = await conn.fetchrow(
            r"""SELECT id, name, language, phone FROM users
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
