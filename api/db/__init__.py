"""Postgres persistence (asyncpg). Schema in db/schema.sql; connection from DATABASE_URL.

The agent keeps working state in memory and writes through to these tables so every
conversation can be inspected in CloudBeaver (http://localhost:8978).
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
from datetime import date
from pathlib import Path

import asyncpg

from models import Evidence, Incident, Viability
from seed import load_wallet
from services import rules

SCHEMA = Path(__file__).with_name("schema.sql")
# One pool per event loop: on Windows LiveKit runs each call in its own thread and loop, and
# an asyncpg pool only works on the loop that created it.
_pools: dict[asyncio.AbstractEventLoop, asyncpg.Pool] = {}


class DocumentsNotVerified(Exception):
    """Filing refused: these uploads have no accepted copy that matches the records."""

    def __init__(self, kinds: list[str]):
        super().__init__(f"documents not verified: {', '.join(kinds)}")
        self.kinds = kinds


async def _init_conn(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


def pool() -> asyncpg.Pool:
    try:
        return _pools[asyncio.get_running_loop()]
    except KeyError:
        raise RuntimeError("db.init() has not been called on this event loop") from None


async def init() -> None:
    new_pool = await asyncpg.create_pool(os.environ["DATABASE_URL"], init=_init_conn)
    _pools[asyncio.get_running_loop()] = new_pool
    async with new_pool.acquire() as conn:
        await conn.execute(SCHEMA.read_text(encoding="utf-8"))
        await _seed_wallet(conn)


async def close() -> None:
    if (old_pool := _pools.pop(asyncio.get_running_loop(), None)) is not None:
        await old_pool.close()


async def _seed_wallet(conn: asyncpg.Connection) -> None:
    wallet = load_wallet()
    await conn.executemany(
        """INSERT INTO documents (document_code, name_english, name_hindi) VALUES ($1, $2, $3)
           ON CONFLICT (document_code) DO UPDATE SET name_english = $2, name_hindi = $3""",
        [(d.document_code, d.name_english, d.name_hindi) for d in wallet.documents.values()],
    )
    await conn.executemany(
        """INSERT INTO users (id, full_name, preferred_language, phone_number)
           VALUES ($1, $2, $3, $4)
           ON CONFLICT (id) DO UPDATE SET full_name = $2, preferred_language = $3,
               phone_number = $4""",
        [(u.id, u.full_name, u.preferred_language, u.phone_number) for u in wallet.users.values()],
    )
    await conn.executemany(
        """INSERT INTO vehicles (id, user_id, vehicle_type, vehicle_number, brand, model,
               manufacture_year)
           VALUES ($1, $2, $3, $4, $5, $6, $7)
           ON CONFLICT (id) DO UPDATE SET user_id = $2, vehicle_type = $3, vehicle_number = $4,
               brand = $5, model = $6, manufacture_year = $7""",
        [
            (
                v.id,
                v.user_id,
                v.vehicle_type,
                v.vehicle_number,
                v.brand,
                v.model,
                v.manufacture_year,
            )
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
        """INSERT INTO sessions (id, user_id, conversation_stage, conversation_language)
           VALUES ($1, $2, $3, $4)""",
        session_id,
        user_id,
        state,
        language,
    )


async def update_session(session_id: str, state: str, language: str) -> None:
    await pool().execute(
        """UPDATE sessions SET conversation_stage = $2, conversation_language = $3,
               updated_at = now()
           WHERE id = $1""",
        session_id,
        state,
        language,
    )


async def add_message(session_id: str, role: str, text: str) -> None:
    await pool().execute(
        "INSERT INTO messages (session_id, sender_role, message_text) VALUES ($1, $2, $3)",
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
               incident_location, description_english, description_user_language,
               third_party_involved, third_party_property_damaged, anyone_injured,
               estimated_repair_cost_inr, garage_name, police_report_filed, risk_flags,
               claim_recommendation, viability_assessment)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
           ON CONFLICT (session_id) DO UPDATE SET
               vehicle_id = $3, policy_id = $4, incident_date = $5, incident_location = $6,
               description_english = $7, description_user_language = $8,
               third_party_involved = $9, third_party_property_damaged = $10,
               anyone_injured = $11, estimated_repair_cost_inr = $12, garage_name = $13,
               police_report_filed = $14, risk_flags = $15, claim_recommendation = $16,
               viability_assessment = $17, updated_at = now()""",
        session_id,
        i.user_id,
        i.vehicle_id,
        policy_id,
        i.incident_date,
        i.incident_location,
        i.description_english,
        i.description_user_language,
        i.third_party_involved,
        i.third_party_property_damaged,
        i.anyone_injured,
        i.estimated_repair_cost_inr,
        i.garage_name,
        i.police_report_filed,
        i.risk_flags,
        viability.verdict if viability else None,
        viability.model_dump() if viability else None,
    )


async def add_evidence(session_id: str, e: Evidence) -> None:
    await pool().execute(
        """INSERT INTO evidence (id, session_id, evidence_type, is_accepted, quality_issues,
               ai_confidence_score, extracted_details, detail_mismatches)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
        e.id,
        session_id,
        e.evidence_type,
        e.is_accepted,
        e.quality_issues,
        e.ai_confidence_score,
        e.extracted_details,
        e.detail_mismatches,
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
            """INSERT INTO claims (session_id, policy_id, claim_type, claim_form_data,
                   expected_settlement_days_min, expected_settlement_days_max)
               VALUES ($1, $2, $3, $4, $5, $6)
               ON CONFLICT (session_id) DO UPDATE SET claim_type = $3, claim_form_data = $4,
                   expected_settlement_days_min = $5, expected_settlement_days_max = $6""",
            session_id,
            policy_id,
            claim_type,
            form,
            *days,
        )
        await conn.execute("DELETE FROM claim_documents WHERE session_id = $1", session_id)
        await conn.executemany(
            """INSERT INTO claim_documents (session_id, document_code, is_provided)
               VALUES ($1, $2, $3)""",
            [(session_id, code, provided) for code, provided in documents.items()],
        )


async def file_claim(session_id: str) -> str | None:
    """File a draft claim and return its new reference number (None if it isn't a draft).

    Raises DocumentsNotVerified unless the number plate photo and the driving licence match
    the records; this is the one gate both the chat and the dashboard go through.
    """
    reference_number = f"CK-{date.today():%y%m%d}-{secrets.token_hex(3).upper()}"
    async with pool().acquire() as conn, conn.transaction():
        policy_id = await conn.fetchval(
            """SELECT policy_id FROM claims
               WHERE session_id = $1 AND claim_status = 'draft' FOR UPDATE""",
            session_id,
        )
        if policy_id is None:
            return None
        verified = await conn.fetch(
            """SELECT DISTINCT evidence_type FROM evidence
               WHERE session_id = $1 AND is_accepted AND detail_mismatches = '[]'""",
            session_id,
        )
        policy = load_wallet().policies[policy_id]
        vehicle = load_wallet().vehicles[policy.vehicle_id]
        missing = rules.unverified_kinds(
            rules.required_photo_kinds(policy, vehicle), {r["evidence_type"] for r in verified}
        )
        if missing:
            raise DocumentsNotVerified(missing)
        filed = await conn.fetchval(
            """UPDATE claims SET claim_status = 'filed', claim_reference_number = $2,
                   filed_at = now()
               WHERE session_id = $1 AND claim_status = 'draft'
               RETURNING claim_reference_number""",
            session_id,
            reference_number,
        )
        if filed:
            await conn.execute(
                """UPDATE sessions SET conversation_stage = 'FILED', updated_at = now()
                   WHERE id = $1""",
                session_id,
            )
    return filed


async def user_policies(user_id: str) -> list[dict]:
    """Every policy the user holds, with its vehicle and the documents a claim on it needs."""
    rows = await pool().fetch(
        """SELECT p.id, p.insurer_name, p.policy_number, p.coverage_type,
                  p.coverage_start_date, p.coverage_end_date, p.insured_declared_value_inr,
                  p.no_claim_bonus_pct, p.add_on_covers,
                  p.compulsory_deductible_inr + p.voluntary_deductible_inr AS deductible_inr,
                  jsonb_build_object('id', v.id, 'vehicle_type', v.vehicle_type,
                                     'vehicle_number', v.vehicle_number, 'brand', v.brand,
                                     'model', v.model, 'manufacture_year', v.manufacture_year)
                      AS vehicle,
                  coalesce(jsonb_agg(jsonb_build_object('document_code', d.document_code,
                                                        'name_english', d.name_english,
                                                        'name_hindi', d.name_hindi)
                                     ORDER BY d.name_english)
                               FILTER (WHERE d.document_code IS NOT NULL),
                           '[]') AS required_documents
           FROM policies p
           JOIN vehicles v ON v.id = p.vehicle_id
           LEFT JOIN policy_required_documents r ON r.policy_id = p.id
           LEFT JOIN documents d ON d.document_code = r.document_code
           WHERE p.user_id = $1
           GROUP BY p.id, v.id
           ORDER BY p.coverage_end_date DESC""",
        user_id,
    )
    return [dict(r) for r in rows]


async def user_claims(user_id: str) -> list[dict]:
    """The user's claims, newest first, with enough to list them."""
    rows = await pool().fetch(
        """SELECT c.session_id, c.claim_status, c.claim_reference_number, c.claim_type,
                  c.drafted_at, c.filed_at, c.expected_settlement_days_min,
                  c.expected_settlement_days_max,
                  p.insurer_name, p.policy_number, v.brand, v.model, v.vehicle_number,
                  i.incident_date, i.estimated_repair_cost_inr, i.claim_recommendation,
                  (c.claim_form_data ->> 'expected_payout_inr')::int AS expected_payout_inr,
                  (SELECT count(*) FROM claim_documents cd
                   WHERE cd.session_id = c.session_id AND NOT cd.is_provided)
                      AS documents_missing
           FROM claims c
           JOIN sessions s ON s.id = c.session_id
           JOIN policies p ON p.id = c.policy_id
           JOIN vehicles v ON v.id = p.vehicle_id
           LEFT JOIN incidents i ON i.session_id = c.session_id
           WHERE s.user_id = $1
           ORDER BY c.drafted_at DESC""",
        user_id,
    )
    return [dict(r) for r in rows]


async def claim_detail(user_id: str, session_id: str) -> dict | None:
    """One claim with its checklist, verdict, photos and conversation (None if not the user's)."""
    async with pool().acquire() as conn:
        claim = await conn.fetchrow(
            """SELECT c.session_id, c.claim_status, c.claim_reference_number, c.claim_type,
                      c.claim_form_data, c.expected_settlement_days_min,
                      c.expected_settlement_days_max, c.drafted_at, c.filed_at,
                      i.claim_recommendation, i.viability_assessment
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
            """SELECT d.document_code, d.name_english, d.name_hindi, cd.is_provided
               FROM claim_documents cd JOIN documents d ON d.document_code = cd.document_code
               WHERE cd.session_id = $1
               ORDER BY cd.is_provided, d.name_english""",
            session_id,
        )
        evidence = await conn.fetch(
            """SELECT id, evidence_type, is_accepted, quality_issues, ai_confidence_score,
                      detail_mismatches, uploaded_at
               FROM evidence WHERE session_id = $1 ORDER BY uploaded_at""",
            session_id,
        )
        messages = await conn.fetch(
            """SELECT sender_role, message_text, sent_at FROM messages
               WHERE session_id = $1 ORDER BY id""",
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
            r"""SELECT id, full_name, preferred_language, phone_number FROM users
               WHERE right(regexp_replace(phone_number, '\D', '', 'g'), 10) = $1""",
            mobile,
        )
        if user is None:
            return None
        rows = await conn.fetch(
            """SELECT v.id, v.vehicle_type, v.vehicle_number, v.brand, v.model,
                      v.manufacture_year, p.id AS policy_id, p.insurer_name, p.policy_number,
                      p.coverage_type, p.no_claim_bonus_pct, p.coverage_end_date,
                      p.insured_declared_value_inr, p.add_on_covers
               FROM vehicles v LEFT JOIN policies p ON p.vehicle_id = v.id
               WHERE v.user_id = $1 ORDER BY v.id""",
            user["id"],
        )
    vehicles = []
    for r in rows:
        vehicle = {
            k: r[k]
            for k in ("id", "vehicle_type", "vehicle_number", "brand", "model", "manufacture_year")
        }
        vehicle["policy"] = (
            {
                k: r[k]
                for k in (
                    "insurer_name",
                    "policy_number",
                    "coverage_type",
                    "no_claim_bonus_pct",
                    "coverage_end_date",
                    "insured_declared_value_inr",
                    "add_on_covers",
                )
            }
            | {"id": r["policy_id"]}
            if r["policy_id"]
            else None
        )
        vehicles.append(vehicle)
    return {**dict(user), "vehicles": vehicles}
