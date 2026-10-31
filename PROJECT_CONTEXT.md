# Claim Karo — Complete Project Context (for rebuilding from scratch)

> **Purpose of this file.** Hand this single file to a coding agent (Claude Code or similar) on
> another machine and it can rebuild the project byte-for-byte. Part 1 explains every module,
> every rule and every design decision. Part 2 contains the **verbatim contents of every text
> file in the repository**. When Part 1 and Part 2 disagree, Part 2 (the source) wins.
>
> **Instruction to the rebuilding agent:** recreate the directory tree in §1.3, write every file
> in Part 2 exactly as shown (same path, same content, UTF-8, LF line endings), then follow §11
> to install and run. Do not "improve" anything unless asked; the goal is an identical build.
>
> Generated on 2026-10-31 from git commit `e572c73` on branch `main`.

---

## Part 1 — Analysis

### 1. What the project is

**Claim Karo** is a hackathon prototype (Paytm "Build for India" AI Hackathon, Track 2:
AI-Powered Financial Journeys) of a **voice-first motor-insurance claim assistant**. A user logs
in with a (synthetic) mobile number, describes a two-wheeler or car accident in Hindi or
English by voice or text, and an AI agent:

1. extracts a structured incident via tool calls,
2. matches the applicable motor policy from the user's synthetic "Paytm wallet",
3. runs a deterministic **claim viability check** (deductible, depreciation, IDV cap,
   No-Claim-Bonus loss over 3 years, exclusions) and tells the user whether filing is worth it,
4. grades uploaded photos (vehicle + damage + plate, driving licence) with Claude vision and
   verifies the plate / licence against the policy records with plain code,
5. pre-fills a claim form, lists missing documents, estimates settlement days,
6. files the claim and returns a reference number,
7. speaks every reply via TTS in the user's language.

The guiding principle, repeated in every module: **"Rules decide, Claude explains."** All money
math lives in `api/services/rules.py` (pure Python). Claude only narrates numbers it receives
from tool results and only reads photos.

#### 1.1 Technology stack (exact versions)

| Layer | Technology | Version / notes |
|---|---|---|
| Frontend | Next.js (App Router), React, Tailwind v4 | `next 16.4.3`, `react 19.3.1`, `tailwindcss 4.3.3`, `@tailwindcss/postcss 4.3.3`, TypeScript 5 |
| Realtime | LiveKit client + React components | `livekit-client 2.23.0`, `@livekit/components-react 2.9.24` |
| Backend API | FastAPI + uvicorn, asyncpg | `fastapi>=0.115`, `uvicorn[standard]>=0.30`, `asyncpg>=0.30`, `pydantic>=2.7` |
| Voice agent | LiveKit Agents (Python) | `livekit-agents==1.8.10` with plugins `anthropic`, `sarvam`, `silero`, `turn-detector` all `==1.8.10`; `livekit-api==1.2.2` |
| LLM | Claude via `anthropic>=1.0` SDK | model from `CLAUDE_MODEL` (default `claude-sonnet-5-5`), effort `low`, structured outputs via `messages.parse` |
| STT / TTS | Sarvam AI via LiveKit plugin | STT `saaras:v4` with `language="unknown"` (auto Hindi/English); TTS `bulbul:v4-flash`, speaker `ishita_enhi_customer`, pace `1.0` |
| Database | PostgreSQL 17 (Docker) | `postgres:17-alpine`, host port **5433**, db/user/pass `claim_karo` / `claimkaro` / `claimkaro` |
| DB UI | CloudBeaver (Docker) | `dbeaver/cloudbeaver:latest` on :8978, anonymous access, admin `cbadmin` / `ClaimKaro123` |
| Media server | LiveKit server (Docker) | `livekit/livekit-server:v1.13.11`, `--dev` mode, key `devkey` / secret `secret`, ports 7880 (ws), 7881 (tcp), 7882/udp |
| Runtime | Python 3.13 (3.11+ ok), Node 22 | machine used: Python 3.13.7, Node v22.18.0 |
| Lint / test | ruff (line-length 100, py311, rules E F I UP B), pytest | `pyproject.toml`; **no tests directory exists in the repo** despite README mentioning one |

#### 1.2 Out of scope (deliberately not built)

Health/non-motor insurance, real insurer or Paytm APIs, real auth, WhatsApp, full-duplex voice
with barge-in, native mobile apps, post-filing status tracking (pitch-only; the UI just shows a
"Status tracking on" line).

#### 1.3 Repository tree (every tracked file)

```
Claim-Karo/
├── .gitignore
├── README.md                     # spec / architecture doc (verbatim in Part 2)
├── CALCULATION.md                # worked examples of the viability maths
├── CHECKS.md                     # document / photo verification checks
├── PITCH.md                      # pitch script
├── docker-compose.yml            # postgres + livekit + cloudbeaver(+init)
├── docker/cloudbeaver/
│   ├── data-sources.json         # preset CloudBeaver connection
│   └── data-sources-permissions.json
├── start.ps1 / stop.ps1          # Windows start/stop
├── start.sh  / stop.sh           # macOS/Linux start/stop
├── api/
│   ├── .env.example
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── main.py                   # FastAPI app + LiveKit token endpoint
│   ├── models.py                 # Pydantic v2 models
│   ├── seed.py                   # loads data/*.json into a Wallet
│   ├── agent/
│   │   ├── __init__.py           # AGENT_NAME = "claim-karo"
│   │   ├── claim_agent.py        # LiveKit worker entrypoint, photo grading, language
│   │   ├── lines.py              # fixed bot lines (hi/en) + photo labels
│   │   ├── prompt.py             # system instructions builder
│   │   ├── state.py              # Claim dataclass (session userdata) + publish()
│   │   └── tools.py              # ClaimAgent with 9 function tools
│   ├── db/
│   │   ├── __init__.py           # asyncpg pool + all queries
│   │   └── schema.sql            # idempotent DDL
│   ├── services/
│   │   ├── __init__.py           # empty
│   │   ├── claude.py             # SYSTEM persona + grade_damage_photo (vision)
│   │   ├── rules.py              # ALL money / matching / verification logic
│   │   └── settlement.py         # settlement-days lookup
│   ├── data/
│   │   ├── users.json            # 3 users, 6 vehicles
│   │   ├── policies.json         # 6 policies
│   │   ├── documents.json        # 5 document codes with en/hi names
│   │   ├── settlement_table.json
│   │   ├── u_babu/               # 6 PNG test photos (binary, not in this file)
│   │   ├── u_nadarajan/          # 5 PNG test photos
│   │   └── u_sahayasaila/        # 2 PNG + 2 JPG test photos
│   └── static/audio/.gitkeep     # empty dir placeholder
└── web/
    ├── .env.example
    ├── package.json
    ├── package-lock.json         # NOT reproduced (2,037 lines); regenerate with npm install
    ├── tsconfig.json
    ├── tsconfig.tsbuildinfo      # build artefact, NOT reproduced
    ├── postcss.config.mjs
    ├── app/
    │   ├── globals.css           # Tailwind v4 theme tokens
    │   ├── layout.tsx
    │   └── page.tsx              # login → dashboard ↔ conversation
    ├── components/
    │   ├── Chat.tsx
    │   ├── ClaimPanel.tsx
    │   ├── Dashboard.tsx
    │   └── Login.tsx
    └── lib/
        ├── api.ts                # REST client + types
        ├── format.ts             # date / label / verdict styles
        ├── media.ts              # client-side image shrink
        └── useClaim.ts           # LiveKit hook → ClaimState
```

**Binary files not included here:** the test photos under `api/data/u_*/`. They are only used
manually (uploaded through the UI as evidence) and are not read by any code. Copy them
separately or use your own photos. What each set contains (from the README): Babu Khan's DL,
rear plate `MH49BH1512`, a burnt Ertiga, and a wrong-vehicle car plated `23BH4589AZ`;
Nadarajan G's DL, MT-15 damage with detached plate, Hector rear damage plate `DL12TC0271`;
Sahayasaila T's Pulsar damage (plate partly readable), DL, Dzire rear damage.

Ignored / generated (never commit): `api/.env`, `api/.venv/`, `__pycache__/`, `.pytest_cache/`,
`.ruff_cache/`, `web/node_modules/`, `web/.next/`, `web/next-env.d.ts`, `web/.env.local`,
`logs/`, `.pids`, `api/static/audio/*.mp3`.

---

### 2. Architecture and runtime topology

```
Browser (Next.js :3000)
  │  REST  ──────────────────────────────►  FastAPI (:8000)  ──► Postgres (:5433)
  │  POST /livekit/token                        │ db.init(): apply schema.sql + seed wallet
  │                                             │ dashboard / claim detail / file / delete
  │  WebRTC + data streams
  ▼
LiveKit server (:7880, docker, --dev)
  ▲  room "claim-<user_id>-<8 hex>" ; RoomAgentDispatch(agent_name="claim-karo")
  │
LiveKit agent worker  (python -m agent.claim_agent dev)
  AgentSession: Silero VAD + TurnDetector v1-mini, Sarvam STT/TTS, Claude LLM (effort low)
  tools → services/rules.py, db ; photos (byte stream "photo") → services/claude.py vision
  publishes claim snapshot on text-stream topic "claim.state"
```

Four processes run locally: Docker (postgres, livekit, cloudbeaver), uvicorn API, the agent
worker, and `next start`. **Both** the API and the agent call `db.init()` on start, so both
apply `schema.sql` and reseed the wallet tables (idempotent upserts).

**One LiveKit room = one conversation.** The browser never talks to the agent over HTTP; all
chat, audio, photos and state flow through the room:

| Topic | Direction | Payload |
|---|---|---|
| `lk.chat` | browser → agent | typed text; also the three decision buttons (sent as canned sentences) |
| `lk.transcription` | agent → browser | user transcripts and agent replies (rendered by `useSessionMessages`) |
| `photo` | browser → agent | byte stream; file name `<uuid>.jpg`, mime `image/jpeg` |
| `claim.state` | agent → browser | JSON snapshot of the whole claim after every change |

Participant **attributes** in the JWT carry `user_id`, `language` (`hi`/`en`) and optionally
`resume_session_id`; the agent reads them from `participant.attributes`.

#### 2.1 Design decisions (from README §3, enforced in code)

1. Claude leads the conversation but every state transition goes through a tool that checks
   the current stage and raises `ToolError` if out of order.
2. All money math in `rules.py`; Claude never computes deductible/NCB/payout.
3. Policies are hand-written JSON, not PDFs.
4. One Claude model for both chat (via LiveKit Anthropic plugin, `output_config.effort=low`)
   and photo grading (`client.messages.parse` with a Pydantic `output_format`, one retry).
   Tools are never forced (`tool_choice` not set) because Sonnet 5.5 rejects forced tool choice.
5. STT auto-detects language; the agent switches reply + TTS language to whatever the user
   last used.
6. Hands-free mic toggle, **interruptions disabled** (`"interruption": {"enabled": False}`)
   because laptop speakers echo the bot into the mic.
7. Every bot utterance is shown as text; voice is additive.
8. Synthetic data only.

---

### 3. Data model

#### 3.1 Pydantic models (`api/models.py`)

Type aliases: `Language = "hi"|"en"`, `VehicleType = "2W"|"4W"`,
`CoverType = "comprehensive"|"third_party_only"`, `NcbPct = 0|20|25|35|45|50`,
`Addon = "zero_dep"|"ncb_protect"|"engine_protect"|"rsa"|"consumables"`,
`ClaimType = "own_damage"|"third_party"|"both"`,
`Verdict = "claim"|"dont_claim"|"borderline"|"not_covered"`,
`EvidenceKind = "damage_wide"|"damage_close"|"number_plate"|"odometer"|"garage_estimate"|"dl"|"rc"`,
`SessionState = INTAKE|MATCH_POLICY|VIABILITY|EVIDENCE|FORM_REVIEW|FILED|NO_COVER|ADVISED_NO_CLAIM|CANCELLED`.

Models: `Document`, `User`, `Vehicle`, `Policy` (includes the DL number / holder name / valid-until
given at issuance), `Incident` (all optional, booleans default False, `risk_flags: list[str]`),
`Viability` (payout, deductible, depreciation, ncb_loss_year1, ncb_loss_total, verdict, reasons,
ncb_protected, estimate_pending=False, breakeven_estimate_inr=None), `Settlement`, `Evidence`
(with `extracted_details: dict` and `detail_mismatches: list[str]`), `Claim`, `Session`.

#### 3.2 Seed wallet (`api/seed.py`, `api/data/*.json`)

`load_wallet()` is `lru_cache`d and returns a `Wallet(users, vehicles, policies, documents)` keyed
by id, with helpers `vehicles_for(user_id)`, `policies_for(user_id)`,
`document_names(codes)` (English names, falls back to the code).

Three users (login = last 10 digits of phone):

| user id | name | lang | phone | vehicles |
|---|---|---|---|---|
| `u_babu` | Babu Khan | hi | +91-90000-11111 | `v_babu_bike` Bajaj Pulsar 150 2021 `MH49BH1512` (2W); `v_babu_car` Maruti Suzuki Ertiga ZXi 2022 `HR52H9260` (4W) |
| `u_nadarajan` | Nadarajan G | en | +91-90000-22222 | `v_nadarajan_bike` Yamaha MT-15 2022 `TG153335`; `v_nadarajan_car` MG Hector Sharp 2021 `DL12TC0271` |
| `u_sahayasaila` | Sahayasaila T | en | +91-90000-33333 | `v_sahayasaila_bike` Bajaj Pulsar NS200 2020 `TN12B5422`; `v_sahayasaila_car` Maruti Suzuki Swift Dzire LXi 2015 `TN12C0455` |

Six policies, all `comprehensive`, all `excluded_conditions = [drunk_driving, no_valid_dl,
commercial_use]`, all `required_documents = ["dl"]`, each with 4 cashless garage names:

| policy id | insurer / number | vehicle | period | IDV | OD premium | NCB | ded. comp+vol | add-ons | DL on file |
|---|---|---|---|---|---|---|---|---|---|
| POL-BABU-2W | HDFC ERGO `HDFC/2W/2026/0048213` | v_babu_bike | 2026-03-15 → 2027-03-14 | 62,000 | 2,400 | 35 | 100 + 500 | none | `MH03 20080022135`, Babu Khan, 2027-01-23 |
| POL-BABU-4W | Bajaj General `BJAZ/PC/2026/0072641` | v_babu_car | 2026-04-01 → 2027-03-31 | 780,000 | 15,500 | 20 | 1000 + 0 | zero_dep, rsa | same |
| POL-NADARAJAN-2W | Care Insurance `CARE/2W/2026/0558120` | v_nadarajan_bike | 2026-05-20 → 2027-05-19 | 105,000 | 2,800 | 25 | 100 + 0 | zero_dep | `PY01 19830001268`, Nadarajan G, 2028-09-05 |
| POL-NADARAJAN-4W | HDFC ERGO `HDFC/PC/2026/1192874` | v_nadarajan_car | 2026-01-10 → 2027-01-09 | 1,150,000 | 18,000 | 50 | 1000 + 0 | ncb_protect, rsa | same |
| POL-SAHAYASAILA-2W | Aditya Birla `ABHI/2W/2026/0061905` | v_sahayasaila_bike | 2026-02-01 → 2027-01-31 | 85,000 | 2,600 | 45 | 100 + 0 | none | `TN21X20080011684`, Sahayasaila T, 2028-12-07 |
| POL-SAHAYASAILA-4W | Bajaj General `BJAZ/PC/2026/0072655` | v_sahayasaila_car | 2026-04-01 → 2027-03-31 | 260,000 | 6,500 | 25 | 1000 + 0 | rsa | same |

Documents catalogue: `rc`, `dl`, `policy_copy`, `garage_estimate`, `fir` (English + Hindi names).

Settlement table key = `claim_type|route|docs_complete` → `[min_days, max_days]`; entries
starting with `_` are ignored. e.g. `own_damage|cashless|true → [7, 9]`,
`own_damage|reimbursement|false → [18, 25]`, `third_party|*|true → [30, 90]`.

#### 3.3 Postgres schema (`api/db/schema.sql`)

All `CREATE TABLE IF NOT EXISTS`. Wallet tables `users`, `vehicles`, `policies` (jsonb for
`add_on_covers`, `excluded_conditions`, `cashless_garage_names`; `required_documents` is **not**
a column), `documents`, `policy_required_documents(policy_id, document_code)`.
Conversation tables: `sessions(id text PK, user_id, conversation_stage, conversation_language,
started_at, updated_at)`, `messages(id bigserial, session_id, sender_role 'user'|'bot',
message_text, sent_at)`, `incidents(session_id PK, ..., risk_flags jsonb, claim_recommendation
text, viability_assessment jsonb, updated_at)`, `evidence(id text PK, session_id, evidence_type,
is_accepted, quality_issues jsonb, ai_confidence_score real, extracted_details jsonb,
detail_mismatches jsonb, uploaded_at)`, `claims(session_id PK, policy_id, claim_type,
claim_status 'draft'|'filed', claim_form_data jsonb, expected_settlement_days_min/max,
claim_reference_number unique, drafted_at, filed_at)`, `claim_documents(session_id,
document_code, is_provided)`. Child tables cascade on session delete.

#### 3.4 DB layer (`api/db/__init__.py`) — behaviours that matter

- **One asyncpg pool per event loop** (`_pools: dict[loop, Pool]`): on Windows LiveKit runs each
  job in its own thread/loop. `pool()` raises if `init()` wasn't called on this loop.
- `_init_conn` registers a jsonb codec (`json.dumps`/`json.loads`).
- `init()` creates the pool, executes `schema.sql`, then `_seed_wallet` upserts documents, users,
  vehicles, policies (columns derived dynamically from `Policy.model_dump(exclude={"required_documents"})`)
  and rewrites `policy_required_documents`.
- `create_session`, `update_session`, `add_message`, `save_incident` (upsert on session_id;
  stores `viability.verdict` as `claim_recommendation` and `viability.model_dump()` as jsonb),
  `add_evidence`, `save_claim` (upsert claim + replace checklist in one transaction).
- `file_claim(session_id)`: reference number `CK-<yymmdd>-<6 upper hex>`; in a transaction,
  `SELECT ... FOR UPDATE` the draft (return `None` if none), collect `DISTINCT evidence_type`
  where `is_accepted AND detail_mismatches = '[]'`, compute
  `rules.unverified_kinds(rules.required_photo_kinds(policy), verified)`; if any → raise
  `DocumentsNotVerified(kinds)`; else mark filed, set `sessions.conversation_stage='FILED'`.
  **This is the single filing gate for both chat and dashboard.**
- `cancel_claim`: delete the draft claim row, set stage `CANCELLED` (conversation kept).
- `user_policies`: policies + vehicle json + aggregated required documents, ordered by end date desc.
- `user_claims`: every session with ≥1 user message and stage ≠ CANCELLED, joined to incident,
  vehicle, policy, claim; adds `last_activity_at`, `first_user_message`, `expected_payout_inr`
  (claim form value, else viability payout), `documents_missing` count, and the action flags
  `resumable = rules.is_resumable(stage)`, `deletable = rules.is_cancellable(stage)`.
  Ordered by `last_activity_at DESC NULLS LAST`.
- `delete_claim`: `DELETE FROM sessions` (cascades).
- `load_session(user_id, session_id)`: stage, incident row, evidence rows, claim row, missing
  doc codes, messages — for the agent to resume.
- `claim_detail`: the `user_claims` columns + `claim_form_data` + documents checklist (with
  names) + evidence + messages, for the dashboard.
- `find_user_by_phone(mobile)`: matches `right(regexp_replace(phone_number,'\D','','g'),10)`;
  returns user + vehicles each with nested `policy` summary or `null`.

---

### 4. Rules engine (`api/services/rules.py`) — every formula

Constants: `NCB_LADDER=[0,20,25,35,45,50]`, `POST_CLAIM_LADDER=[20,25]`,
`BORDERLINE_MULTIPLIER=1.25`, `DEPRECIATION_BY_AGE=[(6,0),(12,5),(24,10),(36,15),(48,25),(60,35)]`
(upper bound exclusive, months), `DEPRECIATION_MAX_PCT=45`, `WALLET_DOCS={policy_copy, rc}`,
`FIR_FLAGS={theft, hit_and_run}`, `VERIFIED_KINDS=("damage_wide","dl")`.

| Function | Logic |
|---|---|
| `_has_own_damage(i)` | `estimated_repair_cost_inr != 0 or "theft" in risk_flags` (None counts as own damage) |
| `_has_third_party_liability(i)` | `third_party_property_damaged or anyone_injured` |
| `claim_type(i, p)` | own = own damage AND policy comprehensive; tp = liability → `both` / `own_damage` / `third_party` / `None` |
| `missing_incident_facts(i, estimate_unknown)` | returns the human labels among `vehicle`, `date`, `what happened`, `damage estimate` that are still unknown (estimate satisfied if value known or `estimate_unknown`) |
| `is_cancellable(stage)` | `stage != "FILED"` |
| `is_resumable(stage)` | stage in INTAKE, VIABILITY, EVIDENCE, FORM_REVIEW |
| `deductible(p)` | compulsory + voluntary |
| `is_active(p, on)` | start ≤ on ≤ end |
| `match_policy(i, policies)` | needs vehicle_id and date; first policy with same vehicle, active on the date, and `claim_type` not None |
| `fir_required(i)` | third-party liability OR any of theft / hit_and_run flags |
| `is_cashless(i, p)` | garage_name (casefold, strip) equals one of policy's cashless garages |
| `vehicle_age_months(v, as_of)` | `max(0, (as_of.year - manufacture_year)*12 + as_of.month - 1)` (from 1 Jan of model year) |
| `depreciation_pct(months)` | first bracket where months < bound, else 45 |
| `next_ncb(pct)` | next rung on ladder, capped at 50 |
| `ncb_loss(p)` | if `ncb_protect` → (0,0). year1 = premium × ncb // 100. total = year1 + Σ over `POST_CLAIM_LADDER` [20,25]: climb `no_claim = next_ncb(no_claim)` and add `premium × max(0, no_claim − after_claim) // 100` |
| `_breakeven_estimate(ded, dep, loss)` | `(loss + ded) * 100 // (100 − dep) + 1` |
| `viability(i, p, v, as_of=None)` | see below |
| `what_if(i, cost, policies, vehicles, today)` | copy incident with new cost (and date=today if none), match policy, run viability; None if no policy |
| `policy_summary(p, v, doc_names, today)` | dict for `get_my_policies` tool |
| `required_documents(i, p)` | policy list + `fir` if `fir_required`, de-duplicated |
| `missing_documents(i, p, evidence)` | have = accepted evidence types ∪ WALLET_DOCS; + `garage_estimate` if uploaded or cashless; + `fir` if `police_report_filed`; return required − have |
| `required_photo_kinds(p)` | `["damage_wide"]` + `"dl"` if policy requires `dl` (no separate plate or odometer shot) |
| `_normalise_id(s)` | upper-case, strip everything except A-Z0-9 |
| `_name_tokens(s)` | casefold, keep letters/spaces, split to set |
| `verify_details(kind, details, v, p, i)` | **damage_wide**: no `number_plate_text` → `[PLATE_NOT_READABLE]`; normalised ≠ vehicle reg → `[PLATE_MISMATCH]`. **dl**: no `licence_number` → `[DL_NOT_READABLE]`; else collect `DL_NUMBER_MISMATCH` (normalised ≠ policy DL), `DL_NAME_MISMATCH` (token sets: neither is subset of the other, or empty), `DL_VALIDITY_NOT_READABLE` (no date) or `DL_EXPIRED_ON_INCIDENT_DATE` (valid_until < incident date or today). Other kinds → `[]` |
| `unverified_kinds(required, verified)` | required kinds that are in `VERIFIED_KINDS` and not in verified |

**`viability()` step by step** (reasons are machine codes appended in this order):

1. `excluded = risk_flags ∩ policy.excluded_conditions`; if any → reasons `EXCLUSION_<FLAG>`,
   verdict `not_covered`, all numbers 0.
2. `ctype = claim_type()`; None → `NO_APPLICABLE_COVER`, `not_covered`.
3. If `fir_required` → add `FIR_REQUIRED`.
4. `ctype == "third_party"` → `THIRD_PARTY_LIABILITY` (+ `OWN_DAMAGE_NOT_COVERED` if own damage
   exists) and verdict `claim` with zero numbers (insurer pays the third party directly).
5. `ctype == "both"` → add `THIRD_PARTY_ALSO_INVOLVED`.
6. `(y1, total) = ncb_loss(policy)`; if protected → `NCB_PROTECTED`.
7. `as_of = as_of or incident_date or today`; `dep_pct = 0 if zero_dep else depreciation_pct(age)`;
   `breakeven = _breakeven_estimate(deductible, dep_pct, total)`.
8. If estimate is None → `ESTIMATE_PENDING`, verdict `borderline`, `estimate_pending=True`,
   payout/depreciation 0, y1/total/breakeven filled.
9. `assessed = min(estimate, IDV)` (reason `ESTIMATE_CAPPED_AT_IDV` if capped);
   `depreciation = assessed * dep_pct // 100` (reason `ZERO_DEP_APPLIED` or
   `DEPRECIATION_APPLIED` if >0); `payout = max(0, assessed − depreciation − deductible)`.
10. Verdict: payout == 0 → `PAYOUT_BELOW_DEDUCTIBLE`, `dont_claim`; payout ≤ total →
    `NCB_LOSS_EXCEEDS_PAYOUT`, `dont_claim`; payout ≤ total × 1.25 →
    `PAYOUT_CLOSE_TO_NCB_LOSS`, `borderline`; else `PAYOUT_EXCEEDS_NCB_LOSS`, `claim`.

Worked checks (must reproduce exactly):
- Babu's Pulsar, ₹4,200, incident 2026-10-30: age 69 months → 45 %; deductible 600;
  depreciation 1,890; payout **1,710**; NCB loss 840 / 600 / 600 = **2,040**; `dont_claim`;
  breakeven 4,801.
- Babu's Ertiga (zero_dep), ₹6,500: payout 5,500; NCB loss 3,100 + 775 + 1,550 = 5,425;
  `borderline`; breakeven 6,426.
- Nadarajan's Hector (ncb_protect), ₹38,000, 2021 car in Oct 2026: 45 % depreciation 17,100;
  payout 19,900; NCB loss 0 → `claim`.

---

### 5. Settlement (`api/services/settlement.py`)

`estimate(claim_type, cashless, docs_complete) -> Settlement(min_days, max_days, route,
docs_complete)`; route is `"cashless"` or `"reimbursement"`; key lookup described in §3.2.

---

### 6. Claude service (`api/services/claude.py`)

- `MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")`, `AsyncAnthropic()` client.
- `SYSTEM` persona (verbatim in Part 2): Claim Karo inside Paytm, never invent numbers, ≤3
  sentences, no markdown, rupee format `₹4,200`, Hindi in Devanagari (Hinglish-friendly),
  simple Indian English. This same string is the head of the agent's instructions.
- `_parse(output_model, content, task)`: `messages.parse(model, max_tokens=4000,
  system=SYSTEM, output_config={"effort":"low"}, messages=[user content],
  output_format=output_model)`; raises if `parsed_output` is None; **retries once** on
  `ValidationError`/`ValueError`; logs latency.
- `IssueCode` enum: BLURRY, TOO_DARK, PLATE_NOT_VISIBLE, DAMAGE_NOT_VISIBLE, TOO_FAR,
  TOO_CLOSE, WRONG_SUBJECT, TEXT_ILLEGIBLE.
- `CHECKLIST` per kind (damage_wide: whole vehicle, damage in frame, plate legible; dl: front of
  licence with number, holder, validity legible; etc.).
- `PhotoGrade` model: `accepted, issues, confidence, retake_instruction|None, damage_observed,
  number_plate_text|None, licence_number|None, licence_holder_name|None, licence_valid_until: date|None`.
- `grade_damage_photo(image_bytes, media_type, expected_kind, language)`: one image block
  (base64) + a text task block that names the expected shot, asks for issue codes, a one-sentence
  retake instruction in the user's language, and the plate / licence fields copied exactly
  ("never guess unclear characters, use null").

---

### 7. The voice agent (`api/agent/`)

#### 7.1 `state.py` — `Claim` dataclass (AgentSession userdata)

Fields: `user, session_id, language, room, stage="INTAKE", incident=Incident(),
estimate_unknown=False, policy, viability, evidence: list[Evidence], photos: dict[id → {status,
evidence_type, quality_issues}], retakes: dict[kind → attempts], form, missing_docs, settlement,
reference`.

- `vehicles` property → wallet vehicles for the user.
- `line(key, **kw)` → `LINES[key][language].format(**kw)`; `photo_label(kind)`.
- `next_photo_kind()` → first of `rules.required_photo_kinds(policy)` not yet accepted.
- `restore(saved)` → rebuild from `db.load_session` output (incident from row filtered to model
  fields, policy from wallet, viability from jsonb, evidence with `file_path=""`, retake counts,
  photo statuses with `quality_issues + detail_mismatches`, form/missing/settlement/reference).
- `start_over()` → new `uuid4().hex` session id, reset everything, `db.create_session`.
- `set_stage(stage)` → set + `db.update_session`.
- `progress()` → dict for the `get_claim_progress` tool.
- `publish()` → sends JSON on topic `claim.state`:
  `{sessionId, state, fields (incident minus id/session_id/user_id, exclude_none), policy
  {policy_id, insurer_name, policy_number, coverage_type, no_claim_bonus_pct, deductible_inr,
  add_on_covers} | null, viability | null, photos, form, missingDocs, settlement, referenceNo}`.

#### 7.2 `lines.py` — fixed lines (hi / en)

Keys: `greeting` ("नमस्ते {name}! मैं Claim Karo हूँ…" / "Hi {name}! I'm Claim Karo…"),
`no_cover`, `ask_photo` ({kind}), `next_photo` ({kind}), `advised_no_claim`, `filed` ({ref},
promises status tracking), `use_buttons`, `upload_photo`, `plate_not_readable`,
`plate_mismatch` ({seen}, {expected}), `dl_not_readable`, `dl_mismatch` ({last4}),
`dl_expired`, `not_verified`. Hindi lines use **feminine** verb forms (the TTS voice is female).
`PHOTO_LABEL` for `damage_wide`, `odometer`, `dl`.

#### 7.3 `prompt.py` — system instructions

`instructions(claim)` = `claude.SYSTEM` + caller name + today's date + a bullet list of the user's
vehicles (`id "<id>": brand model (type), reg <number>`) + the 6-step flow (call `record_incident`
every time facts arrive, ask ONE question at a time for what the tool says is missing; explain
the verdict in ≤3 sentences incl. 3-4 days in service centre and the ₹1,000 file charge being
free through Paytm; `start_claim` / `decline_claim`; photos are handled by the system; `file_claim`
when the user says so; `cancel_claim` to drop or switch vehicle) + read-only question tools
(`get_my_policies`, `estimate_payout`, `get_claim_progress`, `get_past_claims`) + the "why buy
through Paytm" talking points + language rules (reply in the user's last language, Hindi only in
Devanagari, speak as a woman in Hindi, only numbers from tool results).

#### 7.4 `tools.py` — `ClaimAgent(Agent)` with 9 `@function_tool`s

Stage-guarded (mutating):

| Tool | Allowed stages | Effect | Returns to Claude |
|---|---|---|---|
| `record_incident(vehicle_id?, incident_date?, incident_location?, description_english?, third_party_involved?, third_party_property_damaged?, anyone_injured?, estimated_repair_cost_inr?, estimate_unknown?, garage_name?, police_report_filed?, risk_flags?)` | INTAKE, VIABILITY | validates vehicle id and ISO date; merges non-null fields; unions risk flags; `db.save_incident`; if facts missing → publish + `"Saved. Still needed: …"`. Else `match_policy`; none → stage NO_COVER + "No policy covers this…". Else compute `viability`, save with policy id, stage VIABILITY (or NO_COVER if verdict not_covered), publish. | JSON `{policy: "<insurer>, NCB x%, add-ons [...]", "verdict (final, do not recompute)": viability dict, note}` where note tells Claude to congratulate (if covered), mention 3-4 days + free ₹1,000 charge, and how to handle estimate_pending / not_covered |
| `start_claim()` | VIABILITY | stage EVIDENCE, publish | `"Say exactly: " + ask_photo line` |
| `decline_claim()` | VIABILITY | stage ADVISED_NO_CLAIM, publish | `"Say exactly: " + advised_no_claim` |
| `file_claim()` | FORM_REVIEW | `context.disallow_interruptions()`; `db.file_claim`; `DocumentsNotVerified` → ToolError(not_verified line); None → "already filed"; else set reference, stage FILED, publish | `"Say exactly: " + filed line` |
| `cancel_claim()` | any | if cancellable → `db.cancel_claim`; `claim.start_over()`; publish | "Cancelled. A new claim has started." (or note that the earlier filed claim stays with the insurer) |

Read-only: `get_my_policies()` (list of `rules.policy_summary`), `estimate_payout(cost,
vehicle_id?)` (→ `rules.what_if`, "hypothetical (claim unchanged)"), `get_claim_progress()`,
`get_past_claims()` (→ `db.user_claims`). Helper `_to_json` always returns a JSON **object**
(never an array) with `ensure_ascii=False, default=str` because the LiveKit Anthropic plugin
turns a JSON array tool result into content blocks the API rejects.

#### 7.5 `claim_agent.py` — worker, photos, language

- `load_dotenv()` first. `AGENT_NAME = "claim-karo"`; `PHOTO_TOPIC = "photo"`.
- `READ_FIELDS = {damage_wide: {number_plate_text}, dl: {licence_number, licence_holder_name,
  licence_valid_until}}`.
- `mismatch_line(claim, codes, details)` → picks the fixed line for PLATE_NOT_READABLE /
  PLATE_MISMATCH (with seen/expected) / DL_NUMBER_MISMATCH or DL_NAME_MISMATCH (last 4 of DL on
  file) / DL_EXPIRED_ON_INCIDENT_DATE / else dl_not_readable.
- **`on_photo(session, image, photo_id, mime)`**: ignore unless stage EVIDENCE and a kind is
  pending; mark `{status: "grading"}` + publish; `grade_damage_photo`; `details =
  grade.model_dump(mode="json", include=READ_FIELDS[kind])`; `mismatches = verify_details(...)`;
  `attempts = retakes[kind]`; **`accepted = not mismatches and (grade.accepted or (attempts >= 1
  and grade.confidence >= 0.6))`** (second attempt passes on quality alone; a mismatch never
  passes); build `Evidence` (quality_issues empty if accepted), `db.add_evidence`, append,
  increment retakes, set photo status (`accepted`/`retake`, quality_issues + mismatches).
  Not accepted → publish, `session.say(mismatch line or grade.retake_instruction or
  upload_photo)`. Accepted and another kind pending → publish, say `next_photo`. All done →
  `review_form(claim)` then `session.generate_reply(instructions=...)` asking Claude to confirm
  the form, name missing docs, give settlement time and ask whether to file.
- **`review_form(claim)`**: `ctype = claim_type or "own_damage"`; `required_documents`;
  `missing_documents`; `settlement.estimate(ctype, is_cashless, not missing)`; `claim.form =
  {policyholder, phone_number, insurer_name, policy_number, vehicle "brand model (reg)",
  claim_type, incident_date (str), incident_location, description, estimated_repair_cost_inr,
  expected_payout_inr, garage, route}`; `missing_docs`; `settlement = est.model_dump()`;
  checklist `{code: code not in missing}`; `db.save_claim`; stage FORM_REVIEW; publish.
- `ClaudeLLM(anthropic.LLM)` overrides `chat()` to inject `extra_kwargs.output_config =
  {"effort": "low"}` (merging any existing extra kwargs via `is_given`).
- `follow_language(session, lang)`: if changed, set `claim.language` and
  `session.tts.update_options(target_language_code=f"{lang}-IN")`.
- `is_hindi(text)`: any char in Devanagari block U+0900–U+097F.
- `prewarm(proc)`: `proc.userdata["vad"] = silero.VAD.load()`; `server = AgentServer(setup_fnc=prewarm)`.
- **`entrypoint(ctx)`** decorated `@server.rtc_session(agent_name=AGENT_NAME)`:
  1. `db.init()`, shutdown callback `db.close`.
  2. `participant = await ctx.wait_for_participant()`; user from `attributes["user_id"]`;
     language `en` iff attribute == "en" else `hi`; `resume_session_id` optional.
  3. If resuming and `rules.is_resumable(saved stage)`: build `Claim`, `restore(saved)`,
     `db.update_session`, and build a `ChatContext` from saved messages (user→"user",
     bot→"assistant"). Else new `Claim` with `uuid4().hex`, `db.create_session(..., "INTAKE", lang)`.
  4. `AgentSession[Claim](stt=sarvam.STT(language="unknown", model=SARVAM_STT_MODEL|saaras:v4),
     llm=ClaudeLLM(model=claude.MODEL), tts=sarvam.TTS(target_language_code=f"{lang}-IN",
     model=SARVAM_TTS_MODEL|bulbul:v4-flash, speaker=SARVAM_TTS_SPEAKER|ishita_enhi_customer,
     pace=float(SARVAM_TTS_PACE|1.0)), vad=prewarmed, turn_handling={"turn_detection":
     inference.TurnDetector(version="v1-mini"), "interruption": {"enabled": False}},
     userdata=claim, max_tool_steps=5)`.
  5. Event `user_input_transcribed`: if final and language present → `follow_language("en" if
     startswith("en") else "hi")`.
  6. Event `conversation_item_added`: user text → background `db.add_message(...,"user")`, set
     `description_user_language` if first, `follow_language("hi")` if Devanagari; assistant text
     → `db.add_message(...,"bot")`. Background tasks are tracked in a set with error logging.
  7. `ctx.room.register_byte_stream_handler("photo", handler)`: read all chunks, photo id =
     file name without extension, call `on_photo`; on exception log and say `upload_photo`.
  8. `await session.start(room=ctx.room, agent=ClaimAgent(claim, history))`; `claim.publish()`;
     if new (or resumed with no history) → `session.say(greeting with first name)`; else
     `generate_reply` "The user has come back… say where it stands and ask for the next thing".
- `__main__`: `logging.basicConfig(INFO)`, `cli.run_app(server)`. Run with
  `python -m agent.claim_agent dev` from `api/`.

#### 7.6 State machine (as implemented)

```
INTAKE ──record_incident (all facts)──► VIABILITY ──start_claim──► EVIDENCE ──(all photos ok)──► FORM_REVIEW ──file_claim──► FILED
  │                                        │
  │ (no policy / not_covered) ──► NO_COVER │ decline_claim ──► ADVISED_NO_CLAIM
  └── cancel_claim at any stage before FILED ──► CANCELLED (and a fresh INTAKE session starts)
```
`MATCH_POLICY` exists in the type and the UI stepper but the agent never sets it (matching
happens inside `record_incident`). `record_incident` is also allowed in VIABILITY so the user
can correct facts before deciding.

---

### 8. FastAPI (`api/main.py`)

`load_dotenv()` first. Lifespan: `db.init()` / `db.close()`. CORS from `CORS_ORIGINS`
(default `http://localhost:3000`), all methods/headers.

| Route | Behaviour |
|---|---|
| `GET /users/lookup?phone=` | strip non-digits, last 10; 400 if not 10 digits; `db.find_user_by_phone`; 404 "No Paytm account found for this number" |
| `GET /users/{user_id}/dashboard` | 404 if user not in wallet; `{policies: db.user_policies, claims: db.user_claims}` |
| `GET /users/{user_id}/claims/{session_id}` | `db.claim_detail` or 404 |
| `POST /users/{user_id}/claims/{session_id}/file` | 404 unknown; 409 if `claim_status` is null ("isn't ready… Continue it in chat"), 409 if not draft ("already filed"); `db.file_claim`; 409 on `DocumentsNotVerified` ("…vehicle photo and driving licence must match…"); 409 if None; `{claim_reference_number}` |
| `DELETE /users/{user_id}/claims/{session_id}` | 404; 409 if not `deletable`; `db.delete_claim`; `{deleted: id}` |
| `POST /livekit/token?user_id&language=hi&session_id?` | 404 unknown user; attributes `{user_id, language}`; with session_id: 409 unless claim exists and `resumable`, adds `resume_session_id`; room `claim-{user_id}-{8 hex}`; `AccessToken().with_identity(user_id).with_name(full_name).with_attributes(attrs).with_grants(VideoGrants(room_join=True, room=room)).with_room_config(RoomConfiguration(agents=[RoomAgentDispatch(agent_name="claim-karo")])).to_jwt()`; returns `{server_url: LIVEKIT_URL, participant_token}` |

---

### 9. Frontend (`web/`)

Next.js App Router, single client page, Tailwind v4 with theme tokens in `globals.css`:
`navy #002e6e`, `navy-soft #e8eef7`, `sky #00baf2`, `sky-dark #0098c7`, `sky-soft #e6f8fe`,
`canvas #f4f6fa`, `ink #101828`, `muted #667085`, `line #e4e7ec`; font Inter (next/font) with
Noto Sans Devanagari fallback; `.animate-fadein` keyframe. `layout.tsx` sets title "Claim Karo".

#### 9.1 `lib/api.ts`
`API_URL = NEXT_PUBLIC_API_URL ?? http://localhost:8000`. Types `PolicySummary`, `WalletVehicle`,
`Profile`, `DocumentName`, `ClaimDocument`, `Verdict`, `WalletPolicy`, `Stage`, `ClaimSummary`,
`DashboardData`, `ClaimDetail`. `request<T>()` wraps fetch, throws "Can't reach the server…" on
network error and `body.detail` on non-OK. Functions `lookupUser`, `fetchDashboard`, `fetchClaim`,
`fetchLiveKitToken(userId, language, resumeId)` → `{serverUrl, participantToken}`, `deleteClaim`,
`fileClaim`.

#### 9.2 `lib/useClaim.ts` (the LiveKit hook)
Uses `useSessionContext`, `useAgent`, `useSessionMessages`, `useLocalParticipant`,
`useTextStream("claim.state")`. Latest text stream → `Snapshot` (or `EMPTY`). Messages: map
`chat.messages` (`userTranscript` or local `chatMessage` → user, else bot), drop blank; prepend
`history` for resumed claims. `status`: not connected → `closed` if there were live messages
else `connecting`; agent not connected → `connecting`; agent thinking or sending → `thinking`;
else `idle`. `photos`: previews keyed by id, filtered to the current `snapshot.sessionId`,
merged with snapshot statuses (default `grading`). `speaking = agent.state === "speaking"`,
`micOn`. Actions: `sendText` (chat.send), `sendPhoto` (uuid id, `shrinkImage`, store preview,
`localParticipant.sendFile(new File([blob], "<id>.jpg"), {topic:"photo", mimeType:"image/jpeg"})`),
`decide("claim"|"dont_claim"|"file")` sends the canned `DECISION_TEXT` sentence in the current
language, `setMic(on)` → `setMicrophoneEnabled(on, {echoCancellation, noiseSuppression,
autoGainControl, voiceIsolation})`. Export `rupees(n)` → `₹` + en-IN locale or `—`.

#### 9.3 `lib/media.ts`
`shrinkImage(file)` → canvas resize to max 1600 px, JPEG 0.85, returns `{blob, preview dataURL}`.

#### 9.4 `lib/format.ts`
`formatDate` (en-IN, `d MMM yyyy`), `label` (underscores → spaces, capitalise first), `VERDICT`
map: claim "Worth claiming" (emerald), dont_claim "Better not to claim" (amber), borderline
"Borderline" (yellow), not_covered "Not covered" (red).

#### 9.5 `app/page.tsx`
State: `profile`, `language` (default `hi`, set from profile on login), `chat: {run, resumeId} |
null` (null = dashboard), `currentSession` ref. `openChat(resumeId)` bumps `run` so `<Session
key=…>` remounts. `switchLanguage` reconnects on the same claim (`resumeId = currentSession`).
`Session` builds `TokenSource.custom(() => fetchLiveKitToken(...))`, `useSession`, starts with
mic disabled, ends on unmount, wraps `SessionProvider` + `RoomAudioRenderer` + `Conversation`.
`Conversation` fetches history for a resumed claim, calls `useClaim`, reports `sessionId`
upward, renders `Chat` + `ClaimPanel` in a two-column grid (`md:grid-cols-[1fr_380px]`).
Header: CK logo (back to dashboard), nav "My claims" / "New claim|Continuing claim", mobile
"My claims" pill, language toggle हिंदी/EN, "+ New claim", `ProfileMenu` (initials avatar,
masked phone `+91 ••••• 12345`, Log out → `setProfile(null)`). Main shows `Login` → `Dashboard`
→ `Session`.

#### 9.6 Components
- **Login.tsx**: +91 prefix, numeric input limited to 10 digits, submit → `lookupUser`, errors
  inline, footer "Prototype with synthetic data…".
- **Chat.tsx**: header with status dot/text (Connecting…/Disconnected/Speaking…/Thinking…/
  Listening…/Online); scrollable message list that auto-pins to bottom unless the user scrolled
  up (threshold 80 px); bouncing-dots "thinking" indicator until the bot's reply starts;
  decision buttons **File claim / Don't claim** shown only in stage `VIABILITY`; camera upload
  button (accept image/*, capture environment) only in `EVIDENCE`; text input + send; mic toggle
  button (red with ring + ping when talking and bot speaking). Inline SVG icons.
- **ClaimPanel.tsx**: stepper (Details / Policy / Verdict / Photos / Review / Filed, mapped from
  states); verdict card (label, "Insurer pays", "No-Claim Bonus lost over 3 years", breakeven
  hint when estimate pending); Incident card (field labels map, hides false/empty, formats
  vehicle name from profile, rupees, dates); Matched policy card (chips: cover type, NCB %,
  deductible, add-ons); Photos grid (3 cols, caption Accepted/Retake/Checking…); Claim form card
  (rows, "Documents needed" amber box with `DOC_LABELS`, settlement line, reference number box
  with "Status tracking on", or **File claim** button only in `FORM_REVIEW` and when idle).
- **Dashboard.tsx**: loads `/dashboard`; groups claims into In progress (`resumable`), Filed,
  Closed; `ClaimRow` (vehicle, title = description or first user message, stage pill with
  `STAGE` labels/tones, expected payout or last-activity "time ago", compact delete with inline
  confirm "Delete for good?", "Continue →"); right-hand sticky `ClaimDetailPanel` (header with
  reference box if filed, else guidance text + File claim (draft) / Continue claim (resumable)
  + Delete; verdict card; Documents checklist (✓ Have it / ! Needed, names in current language);
  Claim form rows (hides policyholder/phone); "Photos checked" list with retake reasons;
  collapsible Conversation); `PolicyCard` per wallet policy (vehicle, type pill, insurer, valid
  till (red if expired), NCB, IDV + deductible if comprehensive, add-on chips, documents for a
  claim); note for uninsured vehicles.

---

### 10. Infra and scripts

- **docker-compose.yml** (project name `claim-karo`): `postgres` (healthcheck pg_isready),
  `livekit` (`--dev --bind 0.0.0.0 --node-ip 127.0.0.1`), `cloudbeaver-init` (busybox copies
  `docker/cloudbeaver/*.json` into the workspace volume on first run only), `cloudbeaver`
  (depends on healthy postgres + completed init; env `CB_SERVER_NAME`, `CB_SERVER_URL`,
  `CB_ADMIN_NAME`, `CB_ADMIN_PASSWORD`, `CLOUDBEAVER_APP_ANONYMOUS_ACCESS_ENABLED=true`).
  Volumes `pgdata`, `cbworkspace`.
- **start.ps1 [-KeepData]** / **start.sh [--keep-data]**: refuse if `.pids` exists; `docker
  compose up -d --wait postgres cloudbeaver livekit`; unless keep-data, `DROP SCHEMA public
  CASCADE; CREATE SCHEMA public;` via psql in the container; copy `.env.example` → `.env` if
  missing; create venv (`py -3.13` / python3.13 or python3 ≥ 3.11); if `import livekit.agents`
  fails → `pip install -r requirements.txt` and `python -m livekit.agents download-files`; `npm
  install` if no node_modules; `npm run build`; launch uvicorn (`main:app --reload --port 8000`),
  agent (`python -m agent.claim_agent dev`), `npm run start` — each in its own PowerShell window
  (Windows) or nohup with logs in `logs/{api,agent,web}.log` (bash); write PIDs to `.pids`.
- **stop.ps1 [-Reset]** / **stop.sh [--reset]**: kill PIDs (taskkill /T /F or kill), remove
  `.pids`, `docker compose down` (or `down -v` with reset).
- **api/.env.example**: `ANTHROPIC_API_KEY`, `SARVAM_API_KEY`, `CLAUDE_MODEL=claude-sonnet-5-5`,
  `SARVAM_STT_MODEL=saaras:v4`, `SARVAM_TTS_MODEL=bulbul:v4-flash`,
  `SARVAM_TTS_SPEAKER=ishita_enhi_customer`, `SARVAM_TTS_PACE=1.0`,
  `DATABASE_URL=postgresql://claimkaro:claimkaro@localhost:5433/claim_karo`,
  `LIVEKIT_URL=ws://localhost:7880`, `LIVEKIT_API_KEY=devkey`, `LIVEKIT_API_SECRET=secret`.
- **web/.env.example**: `NEXT_PUBLIC_WS_URL` (legacy, unused) and `NEXT_PUBLIC_API_URL`.

---

### 11. How to rebuild and run

1. Create the tree from §1.3 and write every file from Part 2 verbatim.
2. Copy the test photos (optional).
3. Install Docker Desktop, Python 3.13 (or 3.11+), Node 22.
4. `cd api && py -3.13 -m venv .venv && .venv/Scripts/pip install -r requirements.txt && .venv/Scripts/python -m livekit.agents download-files`
5. `cd web && npm install` (regenerates `package-lock.json`).
6. `cp api/.env.example api/.env` and fill `ANTHROPIC_API_KEY` and `SARVAM_API_KEY`.
7. `.\start.ps1` (Windows) or `./start.sh` (macOS/Linux). Open http://localhost:3000, log in
   with `9000011111` (Babu, Hindi), `9000022222` (Nadarajan, English) or `9000033333`.
8. Demo scenario 1 (Hindi, don't claim): "Signal pe bike ko taxi ne maar diya, ₹4,200 ka
   kharcha bata raha hai mechanic." Scenario 2 (English, claim): "Someone hit the back of my
   Hector, garage says ₹38,000", then upload the Hector photo (plate DL12TC0271) and the DL.

---

### 12. Gotchas, discrepancies and known gaps (read before changing anything)

1. **README vs code drift.** The README (written as the day-1 spec) still mentions things that
   do not exist in the repo: `api/tests/test_rules.py`, `api/scripts/pregen_audio.py`,
   `docs/DEMO_SCENARIOS.md`, `docs/pitch/*.pptx`, `state_machine.py`, WebSocket transport, test
   users "Ravi/Priya", folders `api/data/case1..3` (actual: `u_babu`, `u_nadarajan`,
   `u_sahayasaila`), and TTS default `bulbul:v3` / speaker `shubh` (actual code default:
   `bulbul:v4-flash` / `ishita_enhi_customer`, a female voice, hence feminine Hindi lines).
   PITCH.md numbers (₹2,130 / ₹2,550 / ₹37,000 / ₹14,000) are narrative, not what the engine
   outputs for the seed data. Treat the **code** as truth.
2. The `web/.env.example` `NEXT_PUBLIC_WS_URL` is unused (left over from the WebSocket design).
3. Evidence `file_path` is always `""`; photo bytes are never stored, only the grade.
4. A DL that was expired on the incident date can never be accepted, so the claim is stuck in
   EVIDENCE; the user can only cancel (documented in CHECKS.md).
5. Filing from the dashboard and from chat both go through `db.file_claim`, which re-checks
   that `damage_wide` and `dl` have an accepted, mismatch-free evidence row.
6. `_to_json` must return an object, never a list (LiveKit Anthropic plugin quirk).
7. On Windows each LiveKit job runs on its own loop, hence the per-loop asyncpg pool map.
8. Interruptions are disabled; the mic is user-toggled; browser echo cancellation is on.
9. `record_incident` treats an estimate of exactly `0` as "no own damage"; `None` still counts
   as own damage with `estimate_pending`.
10. `next.config.*` does not exist; defaults are used. `next-env.d.ts` is generated.
11. Both the API and the agent apply `schema.sql` and reseed on start; `start.ps1` additionally
    drops the schema unless `-KeepData`.

---

## Part 2 — Verbatim source of every text file

Each file below is reproduced exactly (UTF-8). Fences use four backticks so that the three-backtick
fences inside the Markdown files survive. Create each file at the path shown in its heading.

### File index

- `.gitignore`
- `CALCULATION.md`
- `CHECKS.md`
- `PITCH.md`
- `README.md`
- `docker-compose.yml`
- `docker/cloudbeaver/data-sources-permissions.json`
- `docker/cloudbeaver/data-sources.json`
- `start.ps1`
- `start.sh`
- `stop.ps1`
- `stop.sh`
- `api/.env.example`
- `api/agent/__init__.py`
- `api/agent/claim_agent.py`
- `api/agent/lines.py`
- `api/agent/prompt.py`
- `api/agent/state.py`
- `api/agent/tools.py`
- `api/data/documents.json`
- `api/data/policies.json`
- `api/data/settlement_table.json`
- `api/data/users.json`
- `api/db/__init__.py`
- `api/db/schema.sql`
- `api/main.py`
- `api/models.py`
- `api/pyproject.toml`
- `api/requirements.txt`
- `api/seed.py`
- `api/services/__init__.py`
- `api/services/claude.py`
- `api/services/rules.py`
- `api/services/settlement.py`
- `api/static/audio/.gitkeep`
- `web/.env.example`
- `web/app/globals.css`
- `web/app/layout.tsx`
- `web/app/page.tsx`
- `web/components/Chat.tsx`
- `web/components/ClaimPanel.tsx`
- `web/components/Dashboard.tsx`
- `web/components/Login.tsx`
- `web/lib/api.ts`
- `web/lib/format.ts`
- `web/lib/media.ts`
- `web/lib/useClaim.ts`
- `web/package.json`
- `web/postcss.config.mjs`
- `web/tsconfig.json`

---

### `.gitignore`

````text
# Python
__pycache__/
*.pyc
.venv/
.pytest_cache/
.ruff_cache/

# Secrets / runtime
.env
*.db
logs/

# Node
node_modules/
web/.next/
web/next-env.d.ts
web/.env.local

# Generated TTS cache (pre-generated lines are committed under static/audio/pregen/)
api/static/audio/*.mp3
!api/static/audio/pregen/

# start.ps1 process ids
.pids
````

### `CALCULATION.md`

````markdown
# How Claim Karo decides "claim or don't claim"

Claim Karo answers one question: **is the money the insurer pays more than the
No-Claim Bonus (NCB) you lose by claiming?**

All of the maths lives in [`api/services/rules.py`](api/services/rules.py). The AI never
calculates anything; it only explains the result. All amounts are whole rupees, and
every division rounds down.

---

## 1. Inputs

| Input | Where it comes from |
|---|---|
| Repair estimate | What the user says the garage quoted |
| Own-damage (OD) premium | Policy |
| Current NCB % | Policy |
| Compulsory + voluntary deductible | Policy |
| Insured Declared Value (IDV) | Policy |
| Add-ons (`zero_dep`, `ncb_protect`) | Policy |
| Vehicle manufacture year | Vehicle |
| Incident date | User |

---

## 2. Formulas

### 2.1 Deductible

```
deductible = compulsory_deductible + voluntary_deductible
```

### 2.2 Depreciation %

Vehicle age is counted from 1 January of the manufacture year:

```
age_months = (incident_year − manufacture_year) × 12 + (incident_month − 1)
```

| Age (months) | < 6 | < 12 | < 24 | < 36 | < 48 | < 60 | 60 or more |
|---|---|---|---|---|---|---|---|
| Depreciation | 0% | 5% | 10% | 15% | 25% | 35% | 45% |

With the **`zero_dep`** add-on, depreciation is always **0%**.

### 2.3 Insurer payout

```
assessed     = min(repair_estimate, IDV)
depreciation = assessed × dep% ÷ 100
payout       = max(0, assessed − depreciation − deductible)
```

### 2.4 NCB loss over 3 years

Claiming resets the NCB to 0%. The loss is counted over the next three renewals.

- **Without a claim** the NCB keeps climbing the ladder:
  `0% → 20% → 25% → 35% → 45% → 50%` (it stops at 50%).
- **After a claim** it starts again from 0% and is only **20%** in year 2 and **25%** in
  year 3.

```
Year 1 loss = premium × current_NCB% ÷ 100
Year 2 loss = premium × (next_step(current_NCB%)  − 20%) ÷ 100
Year 3 loss = premium × (next_step(next_step(..)) − 25%) ÷ 100

NCB loss (3 years) = Year 1 + Year 2 + Year 3
```

`next_step` means one rung up the ladder (for example 20% → 25%, 25% → 35%).

With the **`ncb_protect`** add-on, the NCB loss is **₹0**.

### 2.5 Verdict

| Condition | Verdict |
|---|---|
| payout = 0 | `dont_claim` |
| payout ≤ NCB loss | `dont_claim` |
| payout ≤ NCB loss × 1.25 | `borderline` (the gain is too small to be clearly worth it) |
| otherwise | `claim` |

### 2.6 Breakeven estimate

This is the smallest repair bill at which the payout beats the NCB loss. It comes from
solving `estimate × (100 − dep%) ÷ 100 − deductible > NCB loss` for the estimate:

```
breakeven = (NCB_loss + deductible) × 100 ÷ (100 − dep%) + 1
```

The `+ 1` is there because the payout has to be strictly greater than the loss.

The breakeven is where claiming *starts* to pay. The verdict only becomes `claim` once
the payout is more than 1.25 × the NCB loss.

---

## 3. Worked example: Babu Khan's Ertiga, repair bill ₹6,500

Policy `POL-BABU-4W` (Bajaj General Insurance):

| Input | Value |
|---|---|
| Vehicle | Maruti Suzuki Ertiga ZXi (2022), `HR52H9260` |
| OD premium | ₹15,500 |
| Current NCB | 20% |
| Deductible | ₹1,000 compulsory + ₹0 voluntary |
| IDV | ₹7,80,000 |
| Add-ons | `zero_dep`, `rsa` |
| Repair estimate | ₹6,500 |

### Step 1: Deductible

```
deductible = 1,000 + 0 = ₹1,000
```

### Step 2: Depreciation

The policy has `zero_dep`, so:

```
dep% = 0%   (the car's age doesn't matter)
```

### Step 3: Payout

```
assessed     = min(6,500, 7,80,000) = ₹6,500
depreciation = 6,500 × 0 ÷ 100      = ₹0
payout       = 6,500 − 0 − 1,000    = ₹5,500
```

### Step 4: NCB loss

| Year | NCB without a claim | NCB after a claim | Gap | Loss = ₹15,500 × gap |
|---|---|---|---|---|
| 1 | 20% | 0% | 20% | **₹3,100** |
| 2 | 25% | 20% | 5% | **₹775** |
| 3 | 35% | 25% | 10% | **₹1,550** |
| | | | **Total** | **₹5,425** |

```
NCB loss = 3,100 + 775 + 1,550 = ₹5,425
```

> **Common mistake:** leaving out year 2 gives 3,100 + 1,550 = ₹4,650. Year 2 still
> costs ₹775, because without a claim the NCB would have been 25%, but after a claim it
> is only 20%.

### Step 5: Verdict

```
payout ≤ NCB loss ?          5,500 ≤ 5,425           → no
payout ≤ NCB loss × 1.25 ?   5,500 ≤ 6,781.25        → yes
```

**Verdict: `borderline`.** Claiming gains only 5,500 − 5,425 = **₹75**.

### Step 6: Breakeven

```
breakeven = (5,425 + 1,000) × 100 ÷ (100 − 0) + 1
          = 6,425 + 1
          = ₹6,426
```

At ₹6,426 the payout is ₹5,426, just ₹1 more than the NCB loss. The ₹6,500 bill is only
a little above this, which is why the verdict is borderline.

For the verdict to become `claim`, the payout must be more than ₹6,781.25, which needs
a repair bill of at least **₹7,782**.

### What the user hears

> Your insurer would pay ₹5,500, but you'd lose ₹5,425 of No-Claim Bonus over 3 years,
> so it's borderline. If you claim, the car may stay at the service centre for 3-4
> days, and the ₹1,000 file charge is free because you bought the policy through Paytm.

---

## 4. Second example, with depreciation: Babu Khan's Pulsar, bill ₹4,200

Policy `POL-BABU-2W`: OD premium ₹2,400, NCB 35%, deductible ₹100 + ₹500 voluntary,
no add-ons. Bajaj Pulsar 150, made in 2021, incident on 30 Oct 2026.

```
age_months   = (2026 − 2021) × 12 + (10 − 1) = 69     → 45% depreciation
deductible   = 100 + 500                     = ₹600
depreciation = 4,200 × 45 ÷ 100              = ₹1,890
payout       = 4,200 − 1,890 − 600           = ₹1,710
```

| Year | NCB without a claim | NCB after a claim | Gap | Loss = ₹2,400 × gap |
|---|---|---|---|---|
| 1 | 35% | 0% | 35% | ₹840 |
| 2 | 45% | 20% | 25% | ₹600 |
| 3 | 50% | 25% | 25% | ₹600 |
| | | | **Total** | **₹2,040** |

```
payout ≤ NCB loss ?   1,710 ≤ 2,040   → yes  →  dont_claim
breakeven = (2,040 + 600) × 100 ÷ (100 − 45) + 1 = 264,000 ÷ 55 + 1 = ₹4,801
```

**Verdict: `dont_claim`.** Claiming would cost Babu ₹330 more in lost bonus than the
insurer pays.

---

## 5. Where each formula lives in the code

| Formula | Function in `api/services/rules.py` |
|---|---|
| Deductible | `deductible()` |
| Vehicle age | `vehicle_age_months()` |
| Depreciation % | `depreciation_pct()` |
| NCB ladder step | `next_ncb()` |
| NCB loss | `ncb_loss()` |
| Breakeven | `_breakeven_estimate()` |
| Payout and verdict | `viability()` |
| "What if the bill is ₹X?" | `what_if()` |
````

### `CHECKS.md`

````markdown
# Claim checks

What Claim Karo checks before a claim can be filed. Claude only reads the photos; every
comparison is plain code in `api/services/rules.py`.

## Document checks (`rules.verify_details`)

Each upload is compared with the records saved when the policy was issued.

| # | Check | Photo | Fails with |
|---|---|---|---|
| 1 | Number plate = the insured vehicle's registration (spaces, dashes and case ignored) | Whole vehicle with damage | `PLATE_MISMATCH`, `PLATE_NOT_READABLE` |
| 2 | Licence number = the licence on the policy | Driving licence | `DL_NUMBER_MISMATCH`, `DL_NOT_READABLE` |
| 3 | Licence holder's name matches (word order free; one name may contain the other) | Driving licence | `DL_NAME_MISMATCH` |
| 4 | Licence valid on the accident date | Driving licence | `DL_EXPIRED_ON_INCIDENT_DATE`, `DL_VALIDITY_NOT_READABLE` |

- A photo that fails any of these is rejected and the user is told what didn't match. A
  retake is never accepted with a mismatch.
- Filing is checked again in `db.file_claim`: it refuses unless the vehicle photo and the
  licence are accepted with no mismatches. This covers filing from both the chat and the
  dashboard.

## Other checks

- **Photo quality** (Claude vision): blurry, too dark, plate or damage not visible, wrong
  subject. A second attempt with confidence ≥ 0.6 passes on quality alone.
- **Policy match** (`rules.match_policy`): same vehicle, accident date within the cover
  period, and the policy covers this kind of damage.
- **Exclusions** (`rules.viability`): conditions such as drunk driving, no valid licence or
  commercial use make the claim "not covered".

## Known gap

A licence that had expired on the accident date can't be fixed by uploading again, so the
claim stays at the photo step. The user can only cancel it.
````

### `PITCH.md`

````markdown
# Claim Karo — Paytm Build for India Pitch

## Title Slide

### Claim Karo
### Know before you claim.

**Your insurance companion inside Paytm — from accident to settlement**  
Track 2: AI-Powered Financial Journeys  
Team Claim Karo

---

## Stage Pitch

### The problem

Imagine your bike is damaged in an accident. The repair will cost ₹4,200.

You open your insurance app and are hit with policy terms, forms, document lists,
photo rules, and one question nobody answers for you:

**Should I even file this claim?**

Insurance apps help you *submit* a claim. None of them tell you whether claiming
is worth it. A small claim can shrink to almost nothing after deductibles and
depreciation, and still cost you your No-Claim Bonus for years.

And once you do file, you are left alone: calling the insurer, refreshing portals,
wondering what is happening with your money.

For millions of first-time insurance buyers in India, this is where trust breaks.

### The solution

Meet **Claim Karo** — a voice-first insurance assistant that lives inside Paytm.

The customer just speaks, in Hindi or English, about what happened. Claim Karo:

- Understands the accident through a natural conversation
- Finds the right policy already sitting in the customer's Paytm wallet
- **Congratulates them for being protected through Paytm**
- Calculates the real payout: deductible, depreciation, IDV, exclusions
- Shows the No-Claim Bonus they would lose
- Tells them honestly whether to claim, not claim, or think it over
- Checks every photo the way a surveyor would, and asks for a retake if needed
- Fills in the claim form live
- Flags missing documents
- Estimates the settlement time
- Files the claim in one tap
- **Keeps tracking the claim and tells them every time the status changes**

### Demo 1: When not to claim

Meet Ravi.

He says in Hindi:

> "Signal pe bike ko taxi ne maar diya. Mechanic ₹4,200 bata raha hai."

Claim Karo finds his motor policy in his Paytm wallet in seconds:

> "Badhai ho Ravi! Aapki bike Paytm se li gayi policy se insured hai — aapne sahi
> choice ki thi."

Then it does the maths. The payout after depreciation and deductibles is ₹2,130.
But filing would cost Ravi about ₹2,550 in lost No-Claim Bonus over the next three
years. So Claim Karo tells him:

> "Aapke liye claim karna financially beneficial nahi hai. Aapka No-Claim Bonus
> surakshit hai."

Ravi saves money **and** leaves trusting Paytm more than when he came in.

**Claim Karo does not just process claims. It protects customers from expensive
decisions.**

### Demo 2: When to claim

Now meet Priya.

> "I hit a divider. The garage says ₹38,000."

Claim Karo matches her policy:

> "Great news, Priya — your car is covered by the policy you bought on Paytm, with
> zero-depreciation cover. You made the right choice."

The numbers:

- Expected payout: ₹37,000
- No-Claim Bonus at stake: ₹14,000

The recommendation is clear: **claim.**

Priya uploads a damage photo. Claim Karo spots that the number plate isn't
visible and asks her to retake it. After the right photo, the claim form
fills itself. It flags the missing driving licence,
estimates a cashless settlement in 7 to 9 days, and Priya files with one tap.

Then Claim Karo closes with:

> "Your claim is filed. Don't worry — I'll keep checking its status and let you
> know every time something changes."

Priya doesn't need to chase anyone. Paytm has her back until the money arrives.

### Demo 3: "Why should I get my policy from Paytm?"

Customers often ask this before they buy or renew. Claim Karo answers right
inside the conversation:

> "Paytm se policy lene ka sabse bada fayda yeh hai ki jab accident hota hai, aap
> akele nahi hote. Aap bas boliye kya hua, main bataunga claim karna chahiye ya
> nahi, form khud bharunga, aur claim file hone ke baad status bhi dekhta
> rahunga."

> "With a Paytm policy, you get more than cover. When something goes wrong, I
> help you decide whether to claim, fill in the form for you, and keep you
> updated until it's settled. All in the app you already use every day."

The benefits Claim Karo highlights:

- **One app for everything.** Policy, vehicle details, documents, claims and
  payout all in the Paytm app the customer already trusts.
- **Claim help built in.** Every policy bought on Paytm comes with Claim Karo:
  voice guidance in Hindi or English, from the accident to the settlement.
- **Honest advice, not just a form.** Paytm tells you when *not* to claim, so you
  keep your No-Claim Bonus and pay less at renewal.
- **No paperwork hunting.** The policy is already in the wallet. No searching
  emails or PDFs when you need it most.
- **Easy payments and renewals.** Pay with UPI or the Paytm wallet in seconds, and
  get reminded before the policy expires.
- **Compare before you buy.** See plans and add-ons like zero-depreciation side
  by side, with a plain explanation of what each one means for your claim.
- **Status updates.** After filing, the customer doesn't chase the insurer. Paytm
  keeps them informed.

This is the moment where Claim Karo turns a support conversation into a sales
conversation: the best argument for buying insurance on Paytm is how well
Paytm takes care of you when you claim.

## Why this matters for Paytm

### More audience

- **New users through word of mouth.** A customer who was told "don't claim, you'll
  save ₹2,500" tells their friends. Honest advice is the best marketing.
- **Insurance buyers come to Paytm.** "Buy your policy on Paytm and get Claim Karo
  for free" is a reason to choose Paytm over any other insurance channel.
- **Hindi-first, voice-first.** It reaches the next hundred million users: people
  who can't, or don't want to, fill English forms.
- **Repeat visits.** Status updates bring the customer back to Paytm again and
  again during the settlement period, not once a year at renewal.

### More business

- **Higher policy sales and renewals.** Customers who had a good claim experience
  renew on the platform that helped them.
- **Cross-sell moments.** A settled claim is the right time to offer add-ons such as
  zero-depreciation, a top-up, or a repair loan from Paytm.
- **Payouts land in Paytm.** Settlement money flows into the Paytm wallet or bank,
  increasing balances and transactions.
- **Partner value.** Insurers get complete, verified claims and fewer calls,
  which makes Paytm the distribution partner they want to work with.

### More trust

- Every customer hears "you made the right choice with Paytm" at the moment they
  need help the most.
- Transparent numbers, and the honesty to say "don't claim", build trust that
  carries over to payments, lending, and investments.

## Benefits

### For customers

- Talk instead of filling forms, in Hindi or English
- Know the real payout before deciding
- Never lose a No-Claim Bonus on a claim that wasn't worth it
- Photos and documents right the first time
- One-tap filing
- Status updates without chasing the insurer

### For insurers and partners

- Fewer incomplete or rejected submissions
- Verified evidence: plate and licence checked against policy records
- Less manual back-and-forth
- Faster processing and happier customers

### For Paytm

- New users and higher engagement
- More insurance sales and renewals
- Natural cross-sell for insurance, lending, and payments
- A trusted, reusable AI layer for other complex financial journeys

## Technology Stack

- **Next.js** for the customer experience
- **FastAPI and Python** for backend services
- **LiveKit** for real-time voice conversations
- **Sarvam AI** for Hindi-English speech recognition and text-to-speech
- **Claude** for understanding the incident, explaining results, and reading photos
- **PostgreSQL** for claims, policies, evidence, and session state
- A deterministic **Python rules engine** for payout, deductible, depreciation,
  exclusions, and No-Claim Bonus

### Rules decide. AI explains.

The AI never invents a number. Every rupee the customer hears comes from the
rules engine.

## Unique Selling Proposition

**Financially honest claim guidance, inside the app people already trust.**

Claim Karo recommends one of:

- **Claim**
- **Don't claim**
- **Borderline — review the numbers**
- **Not covered**

And it stays with the customer from the first sentence to the final settlement:
voice, two languages, photo verification, a live claim form, one-tap filing, and
status tracking in one journey.

## Business Model

A B2B2C insurance intelligence layer, distributed through Paytm:

- Per-claim fees from insurers
- SaaS licensing for insurers and brokers
- API access for embedded insurance partners
- Premium assisted-claim services
- Revenue share on Paytm insurance distribution, renewals, and cross-sell

## Closing

Insurance should not feel like paperwork. It should feel like a friend who
understands your situation, tells you the truth, and doesn't leave until the job
is done.

With Claim Karo, every Paytm customer knows:

- That they made the right choice by insuring with Paytm
- What their policy covers
- What they will actually receive
- Which documents they need
- How long it will take
- Whether they should claim at all

And once they file, they hear the words every customer wants to hear:

> **"Don't worry — I'll keep checking your claim and let you know."**

### Claim Karo: Know before you claim.

Thank you.

## Suggested Final Slide

### Claim Karo
**Your insurance companion inside Paytm**

**Speak. Understand. Decide. Claim. Relax.**

**Track 2 — AI-Powered Financial Journeys**  
Built with Claude + Sarvam AI + LiveKit
````

### `README.md`

````markdown
# Claim Karo — Motor Insurance Claims in Conversation

> Paytm "Build for India" AI Hackathon · Track 2: AI-Powered Financial Journeys
> Team: Claim Karo (2 people) · Build window: 4 days · Finals: 31 Oct 2026, Paytm Noida

This README is the single source of truth for scope, architecture and conventions.
Claude Code: read this fully before writing any code. If something here conflicts with
a later instruction in chat, the chat instruction wins, but update this file to match.

---

## 1. What we are building

A voice-first web app where a user describes a **motor** (two-wheeler or car) accident in
Hindi or English, uploads damage photos, and an AI agent:

1. Extracts a structured incident from the conversation.
2. Matches the applicable motor policy from the user's (synthetic) Paytm wallet.
3. Runs a **claim viability check** — deductible, No-Claim Bonus (NCB) loss, IDV cap,
   exclusions — and tells the user in plain language whether filing is worth it.
4. Grades uploaded damage photos against surveyor requirements and asks for retakes.
5. Pre-fills the claim form live on screen, lists missing documents.
6. Estimates settlement time.
7. Speaks every step back to the user via TTS in their language.

**Out of scope (do not build):** health/any non-motor insurance, real insurer APIs, real
Paytm data, login/auth, WhatsApp channel, full-duplex voice, mobile native apps,
post-filing follow-up agent (pitch only).

### The headline feature, explained

Every claim-free year earns the policyholder a discount on next year's own-damage (OD)
premium: 20% → 25% → 35% → 45% → 50%. Filing any OD claim resets it to 0%.

So for a ₹4,000 scrape with a ₹1,000 deductible and a 35% NCB on a ₹10,000 OD premium:

- Insurer pays: 4,000 − 1,000 = **₹3,000**
- NCB lost next year: 35% × 10,000 = **₹3,500** (plus the forfeited step-up in later years)

Net: the user is worse off by claiming. For a ₹38,000 collision the same math says claim.
The agent does this math (deterministically, in Python) and explains it (via Claude).
If the policy has an **NCB Protect** add-on, the verdict flips to "claim" for small claims.

---

## 2. Feature scope by priority

| Priority | Feature | Owner |
|---|---|---|
| P0 | Hands-free voice intake (LiveKit + Sarvam STT) + text fallback | B |
| P0 | Incident extraction to structured JSON (Claude, structured output) | A |
| P0 | Policy matching from synthetic wallet | A |
| P0 | Viability rules engine + Claude explanation in user's language | A |
| P0 | Photo upload + vision grading with retake guidance | A/B |
| P0 | Live claim-form panel that fills as fields arrive (LiveKit `claim.state`) | B |
| P0 | Missing-document checklist | A |
| P0 | Settlement estimate (lookup table) | A |
| P0 | TTS replies (Sarvam) with pre-generated audio for fixed lines | B |
| P1 | Own-damage vs third-party routing, FIR-needed logic | A |
| P1 | Consistency check: described impact vs photo damage vs garage estimate | A |
| P2 | Third-party damage demo journey | — |
| Pitch only | Post-filing SLA tracking, Ombudsman escalation, WhatsApp | — |

Do not start a P1 item until every P0 item works end to end in Scenario 1.

---

## 3. Architecture

```
┌──────────────────────────────── Browser (Next.js) ──────────────────────────────┐
│  Chat column                          │  Claim panel                            │
│  - bot/user bubbles (text always)     │  - form fields animate in as found      │
│  - hands-free talk (mic toggle)       │  - photo thumbnails with ✓ / retake     │
│  - photo upload                       │  - viability verdict card               │
│  - LiveKit plays the agent's voice    │  - missing docs, settlement estimate    │
└───────────────┬───────────────────────┴──────────────────────┬──────────────────┘
   POST /livekit/token (REST)  │  WebRTC room: mic audio, lk.chat text, "photo" bytes ⇄
                               │  agent audio, lk.transcription, "claim.state" snapshots
┌──────────────────────────────┴──── LiveKit server (Docker, :7880) ─────────────────┐
└──────────────────────────────┬─────────────────────────────────────────────────────┘
┌──────────────────────────────┴──── Voice agent (agent/claim_agent.py) ─────────────┐
│  AgentSession: Silero VAD + turn detector, Sarvam STT/TTS, Claude LLM + tools       │
│  tools → services/rules.py (money), db (Postgres); photos → claude.py (vision)      │
└──────────────────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────── FastAPI backend (main.py) ───────────────────────┐
│  wallet lookup, dashboard, file-from-dashboard, LiveKit tokens                    │
│  db/  asyncpg, schema.sql (applied on startup)   data/  policies.json users.json  │
└──────────────────────────────────────────────────────────────────────────────────┘
        │ Claude API (text + vision)   │ Sarvam API (streaming STT + TTS)   │ Postgres (Docker)
                                                                        ▲ CloudBeaver :8978
```

### Design decisions (do not relitigate)

1. **A LiveKit voice agent whose tools enforce the steps.** LiveKit Agents runs the call
   (WebRTC audio, voice activity and turn detection, interruptions, typed chat). Claude
   leads the conversation, but every step goes through a tool (`record_incident`,
   `start_claim`, `decline_claim`, `file_claim`) that checks the current stage and refuses
   out-of-order calls; photos are graded outside the LLM; filing is gated in `db.file_claim`.
2. **Rules decide, Claude explains.** All money math lives in `services/rules.py` and is
   unit-tested. Claude receives the computed numbers and writes the explanation. Claude
   never computes deductibles, NCB or payouts.
3. **Policies are hand-written structured JSON**, not PDFs in a vector store.
4. **One model**: Claude (`CLAUDE_MODEL`) runs the conversation through the LiveKit
   Anthropic plugin at low effort, and grades photos with structured outputs
   (`client.messages.parse` with a Pydantic `output_format`; retry once on validation
   failure). Sonnet 5.5 rejects forced `tool_choice`, so tools are never forced.
5. **Language flow**: Sarvam STT auto-detects Hindi/English; the agent replies in the
   language the user last spoke or typed, and switches the TTS language to match.
6. **Transport**: **one LiveKit room per conversation.** `POST /livekit/token` creates the
   room and dispatches the `claim-karo` agent into it. Typed chat uses `lk.chat`, replies
   arrive as `lk.transcription`, photos as byte streams on `photo`, and the agent sends the
   whole claim as one JSON snapshot on `claim.state` after every change. Working state
   lives in the agent session and is written through to Postgres.
7. **Hands-free, no barge-in.** The mic is off until the user taps it; LiveKit decides when
   the user has finished. While the bot speaks, the mic audio is not transcribed: on laptop
   speakers the mic hears the bot, and that echo would otherwise interrupt it.
8. **Text is always visible.** Every bot utterance is rendered as text; voice is additive.
9. **Synthetic data only.** Nothing calls a real insurer or Paytm.

---

## 4. Agent state machine

```
INTAKE ──► MATCH_POLICY ──► VIABILITY ──► EVIDENCE ──► FORM_REVIEW ──► FILED
   ▲            │               │                                        
   └── ask ─────┘   (no policy) │ (user chooses not to claim) ──► ADVISED_NO_CLAIM
                    └──► NO_COVER
```

| State | Input | Does | Claude call | Tool / trigger | Next |
|---|---|---|---|---|---|
| `INTAKE` | user utterance | Extract/merge `Incident`. If required fields missing, ask one targeted question. | conversation LLM | `record_incident` | self (ask) or `MATCH_POLICY` |
| `MATCH_POLICY` | Incident | Filter user's policies by vehicle reg + date in period + cover type. | none (rules) | inside `record_incident` | `VIABILITY` or `NO_COVER` |
| `VIABILITY` | Incident + Policy | `rules.viability()` → numbers + verdict. Claude explains in user language. Ask "claim karna hai?" | conversation LLM | `start_claim` / `decline_claim` | `EVIDENCE` (yes) / `ADVISED_NO_CLAIM` (no) |
| `EVIDENCE` | photo | `vision.grade_photo()` against checklist. Retake or accept. Loop until required shots present. | `grade_damage_photo` (vision) | `photo` byte stream | self or `FORM_REVIEW` |
| `FORM_REVIEW` | — | Assemble `ClaimForm`, compute missing docs, settlement estimate. Read summary aloud. | conversation LLM | after the last photo | `FILED` on user tap |
| `FILED` | user tap | Persist, show reference number. | none | `file_claim` | end |

Required `Incident` fields to leave `INTAKE`: `vehicle_ref` (or vehicle type if only one
in wallet), `incident_date`, `description`, `estimated_repair_cost_inr` (can be "unknown" →
agent asks for garage estimate or lets user say "pata nahi" and proceeds with
`VIABILITY` in "estimate pending" mode).

---

## 5. Data model

Stored in Postgres (`api/db/schema.sql`, tables listed in §11); Pydantic models in `models.py`. Synthetic seed data in `data/`.

```python
class User:           id, full_name, preferred_language ("hi"|"en"), phone_number
class Vehicle:
    id, user_id, vehicle_type ("2W"|"4W")
    vehicle_number                       # registration (number plate)
    brand, model, manufacture_year
class Policy:
    id, user_id, vehicle_id, insurer_name, policy_number
    coverage_type: "comprehensive" | "third_party_only"
    coverage_start_date, coverage_end_date
    insured_declared_value_inr: int      # IDV
    own_damage_premium_inr: int          # base for NCB math
    no_claim_bonus_pct: 0|20|25|35|45|50
    compulsory_deductible_inr: int       # 100 (2W) / 1000–2000 (4W) typical
    voluntary_deductible_inr: int
    add_on_covers: list["zero_dep"|"ncb_protect"|"engine_protect"|"rsa"|"consumables"]
    excluded_conditions: list[str]       # e.g. "drunk_driving","no_valid_dl","commercial_use"
    required_documents: list[str]        # e.g. "rc","dl","policy_copy","garage_estimate","fir"
    cashless_garage_names: list[str]
    driving_licence_number, driving_licence_holder_name, driving_licence_valid_until
                                         # DL given at policy issuance; the claim's DL upload must match
class Incident:
    id, session_id, user_id, vehicle_id
    incident_date, incident_location, description_english, description_user_language
    third_party_involved: bool, third_party_property_damaged: bool, anyone_injured: bool
    estimated_repair_cost_inr: int | None, garage_estimate_uploaded: bool
    police_report_filed: bool | None
    garage_name: str | None              # in policy.cashless_garage_names → cashless route
    risk_flags: list[str]                # "drunk_driving","no_valid_dl","commercial_use",
                                         # "theft","hit_and_run" — matched against exclusions / FIR rules
class Viability:
    insurer_payout_inr, deductible_inr, depreciation_inr,
    ncb_loss_year1_inr, ncb_loss_total_inr
    verdict: "claim" | "dont_claim" | "borderline" | "not_covered"
    reasons: list[str]                   # machine codes, e.g. "NCB_LOSS_EXCEEDS_PAYOUT"
    ncb_protected: bool
    estimate_pending: bool               # no damage estimate yet; numbers are zero
class Evidence:
    id, claim_id
    evidence_type ("damage_wide"|"damage_close"|"number_plate"|"odometer"|"garage_estimate"|"dl"|"rc")
    file_path, is_accepted: bool, quality_issues: list[str], ai_confidence_score: float
    extracted_details: dict              # number plate / DL fields read off the photo
    detail_mismatches: list[str]         # rules.verify_details: PLATE_MISMATCH, DL_NUMBER_MISMATCH, ...
                                         # any mismatch rejects the upload; filing needs a matching
                                         # vehicle photo and DL (db.file_claim refuses otherwise)
class Claim:
    id, incident_id, policy_id, claim_type ("own_damage"|"third_party"|"both")
    claim_status: "draft"|"filed", claim_form_data: dict
    documents: {document_code: is_provided}   # checklist, stored in claim_documents
    expected_settlement_days_min, expected_settlement_days_max, claim_reference_number
class Session:
    id, user_id, conversation_stage, conversation_language, history: list[dict], started_at
```

### Synthetic seed data

`api/data/users.json` (users + vehicles) and `api/data/policies.json`:

Three users, one per folder in `api/data/case1..3`, built from the DL, plate and damage
photos there so those images can be uploaded as test evidence. Every policy is comprehensive
and requires only the driving licence (`dl`).

| # | Policy | Vehicle | Key terms | Test images |
|---|---|---|---|---|
| 1 | `POL-BABU-2W` | Babu Khan's Bajaj Pulsar 150 (2021), `MH49BH1512` | NCB 35%, OD premium ₹2,400, deductibles ₹100 + ₹500 voluntary, no add-ons | `case1`: DL, rear plate |
| 2 | `POL-BABU-4W` | Babu Khan's Maruti Ertiga (2022), `HR52H9260` | NCB 20%, OD premium ₹15,500, deductible ₹1,000, `zero_dep`, `rsa` | `case1`: burnt Ertiga (the `23BH4589AZ` car is a wrong-vehicle test) |
| 3 | `POL-NADARAJAN-2W` | Nadarajan G's Yamaha MT-15 (2022), `TG153335` | NCB 25%, OD premium ₹2,800, deductible ₹100, `zero_dep` | `case2`: DL, MT-15 damage, detached plate |
| 4 | `POL-NADARAJAN-4W` | Nadarajan G's MG Hector (2021), `DL12TC0271` | NCB 50%, OD premium ₹18,000, deductible ₹1,000, `ncb_protect`, `rsa` | `case2`: Hector rear damage |
| 5 | `POL-SAHAYASAILA-2W` | Sahayasaila T's Bajaj Pulsar NS200 (2020), `TN12B5422` | NCB 45%, OD premium ₹2,600, deductible ₹100, no add-ons | `case3`: Pulsar damage (plate only partly readable) |
| 6 | `POL-SAHAYASAILA-4W` | Sahayasaila T's Maruti Swift Dzire (2015), `TN12C0455` | NCB 25%, OD premium ₹6,500, deductible ₹1,000, `rsa` | `case3`: DL, Dzire rear damage |

---

## 6. Rules engine (`services/rules.py`)

Pure functions, no I/O, 100% unit-tested. All amounts in integer INR.

```python
def match_policy(incident, policies) -> Policy | None
def claim_type(incident, policy) -> "own_damage"|"third_party"|"both"|None
def fir_required(incident) -> bool            # third-party injury/damage, theft, hit-and-run
def viability(incident, policy, vehicle, as_of=None) -> Viability
def is_cashless(incident, policy) -> bool
def missing_documents(incident, policy, evidence) -> list[str]
def required_photo_kinds(incident, vehicle) -> list[str]
```

`match_policy` returns a policy only if the vehicle matches, the incident date is in the
policy period, **and** `claim_type()` is not `None` (so own damage on a third-party-only
policy → `NO_COVER`).

Viability logic (v1):

```
assessed      = min(estimate, idv)
depreciation  = 0 if zero_dep in addons else assessed * depreciation_factor(vehicle age)
payout        = max(0, assessed - depreciation - compulsory_deductible - voluntary_deductible)
                (depreciation is applied before deductibles, as surveyors do)
ncb_loss_y1   = 0 if "ncb_protect" in addons else od_premium * ncb_pct / 100
ncb_loss_tot  = ncb_loss_y1 + forfeited step-up over next 2 years:
                  Σ (no-claim ladder − post-claim ladder) × od_premium for years 2 and 3
                  e.g. from 35%: years 2–3 are 45/50 without a claim vs 20/25 after one
verdict:
  not_covered   if exclusion hit or no applicable cover for the claim type
  dont_claim    if payout <= ncb_loss_tot
  borderline    if payout <= ncb_loss_tot * 1.25
  claim         otherwise
reasons: machine codes only; Claude turns them into language.
```

Depreciation (IRDAI standard, simplified to one blended factor by vehicle age, measured
from 1 Jan of the model year): 0–6m 0%, 6m–1y 5%, 1–2y 10%, 2–3y 15%, 3–4y 25%,
4–5y 35%, 5y+ 45%.

Settlement estimate (`data/settlement_table.json`, `services/settlement.py`): keyed by
`(claim_type, cashless|reimbursement, docs_complete: bool)` → `[min_days, max_days]`.

Documents: `policy_copy` and `rc` are auto-satisfied from the wallet. `garage_estimate`
is waived on the cashless route (the network garage submits it). `fir` is added whenever
`fir_required()`.

Required photos: `damage_wide` (must show the number plate) for every vehicle, plus `dl`
when the policy requires it. No odometer photo is asked for.

---

## 7. Claude calls (`services/claude.py`)

All calls use structured outputs: one Pydantic output model per function, effort `low`
for latency. System prompt is shared; each state passes a small task block.

| Function | Input | Output schema (abridged) |
|---|---|---|
| `extract_incident` | prior `Incident` JSON + new utterance + user vehicles | `Incident` fields (nullable) + `clarifying_question: str\|null` + `reply_to_user: str` |
| `explain_verdict` | `Viability` + policy summary + language | `reply_to_user: str` (in user language, ≤ 3 sentences, mention rupee numbers) |
| `grade_damage_photo` | image + `expected_kind` + checklist | `kind_detected`, `accepted: bool`, `issues: [codes]`, `retake_instruction: str`, `damage_observed: str` |
| `summarise_claim` | `ClaimForm` + missing docs + settlement | `reply_to_user: str` |
| `check_consistency` (P1) | incident description + damage_observed + estimate | `consistent: bool`, `flags: [str]`, `question_for_user: str\|null` |

Prompting rules:

- Claude must **never** invent policy numbers, amounts, or terms. All numbers come in via
  the tool input; the system prompt says so explicitly.
- `reply_to_user` must be in `session.language`; for `hi` use natural Hinglish-friendly
  Devanagari (the TTS handles Devanagari; avoid heavy Sanskritised Hindi).
- Keep replies short: the TTS reads them aloud.

Photo checklist for `grade_damage_photo` (surveyor requirements):

- `damage_wide`: whole vehicle visible, damage area in frame
- `damage_close`: damage fills ≥ 30% of frame, in focus
- `number_plate`: plate legible
- `odometer`: reading legible
- `garage_estimate`: document, itemised, total and date legible
- Generic issue codes: `BLURRY`, `TOO_DARK`, `PLATE_NOT_VISIBLE`, `DAMAGE_NOT_VISIBLE`,
  `TOO_FAR`, `TOO_CLOSE`, `WRONG_SUBJECT`, `TEXT_ILLEGIBLE`

---

## 8. Sarvam integration (LiveKit plugin `livekit-plugins-sarvam`)

- **STT**: streaming `saaras:v4` (`SARVAM_STT_MODEL`) with `language="unknown"`, so Hindi
  and English are auto-detected; the detected language steers the reply language.
- **TTS**: streaming `SARVAM_TTS_MODEL` (default `bulbul:v3`) with `SARVAM_TTS_SPEAKER`
  (default `shubh`, the male voice; plain `shubh` exists only on `bulbul:v3`);
  `target_language_code` follows the user (`hi-IN`/`en-IN`).

---

## 9. API contract

```
GET /users/lookup?phone=9000011111       login stand-in: wallet user + vehicles + policies
                                         (matches the last 10 digits; 404 if unknown)
GET  /users/{user_id}/dashboard          policies (with vehicle + required documents) and
                                         every claim conversation from its first message
                                         (most recently active first), each with its stage,
                                         resumable and deletable
GET  /users/{user_id}/claims/{session_id}       one claim: stage, verdict, photos, conversation;
                                                form + document checklist once it reached review
POST /users/{user_id}/claims/{session_id}/file  file a draft; {claim_reference_number}
                                                (409 if not at review yet, filed, or documents
                                                don't match)
DELETE /users/{user_id}/claims/{session_id}     delete a claim and its whole conversation
                                                (409 once filed)
POST /livekit/token?user_id=u_babu&language=hi[&session_id=…]
                                                {server_url, participant_token}: a new room with
                                                the claim-karo agent in it; with session_id the
                                                agent resumes that claim (state + chat history)
```

LiveKit room topics (one room = one conversation):

```
lk.chat          browser → agent   typed text (and the claim / don't-claim / file buttons)
lk.transcription agent → browser   what the user said and what the agent says
photo            browser → agent   byte stream; file name "<photo id>.jpg"
claim.state      agent → browser   JSON snapshot after every change:
                 {sessionId, state, fields, policy, viability, photos: {<id>: {status, evidence_type,
                  quality_issues}}, form, missingDocs, settlement, referenceNo}
```

---

## 10. Frontend (`web/`)

Next.js (App Router) + Tailwind v4. Single page with two views after login, the dashboard
and the claim conversation; two columns on desktop, stacked on mobile.

Paytm-inspired theme (navy `#002E6E`, cyan `#00BAF2`), tokens in `app/globals.css`.

- `components/Login.tsx` — mobile-number entry (+91), calls `/users/lookup`. Test numbers:
  9000011111 (Ravi, Hindi) and 9000022222 (Priya, English).
- `app/page.tsx` — header (My claims tab, language toggle, New claim, profile menu with log
  out on the avatar), then the dashboard (after login) or the conversation (new or resumed;
  a resumed claim shows its earlier messages above the live ones).
- `components/Dashboard.tsx` — claims grouped In progress / Filed / Closed, each with
  Continue (resume in chat) and Delete (until filed); the selected claim's details (verdict,
  document checklist, form, photos, conversation; File claim once at review), and the
  user's policies with the documents a claim on each needs.
- `components/Chat.tsx` — messages, tap-to-talk mic, text input, photo upload in
  `EVIDENCE` (resized to 1600px JPEG), claim / don't-claim buttons; the mic button turns hands-free talking on and off.
- `components/ClaimPanel.tsx` — progress stepper, verdict card, the user's vehicles and
  policies (until one is matched), incident fields, policy, verdict card, photo grid with
  ✓ / retake, claim form, missing docs, settlement, File claim button.
- `lib/useClaim.ts` — the LiveKit session's messages, agent state, mic, photo upload and the
  latest `claim.state` snapshot, as one `ClaimState`.

Never block the UI on audio; text appears first.

---

## 11. Repo structure

```
claim-karo/
├── README.md                   ← this file
├── docker-compose.yml          # Postgres 17 + CloudBeaver + LiveKit server
├── docker/cloudbeaver/         # preset CloudBeaver connection (copied in on first run)
├── start.ps1 / stop.ps1        # start / stop everything
├── api/
│   ├── main.py                 # FastAPI app + LiveKit token endpoint
│   ├── db/                     # __init__.py (asyncpg queries), schema.sql
│   ├── agent/claim_agent.py    # LiveKit voice agent: tools, photo grading, state
│   ├── services/               # claude.py rules.py settlement.py
│   ├── models.py               # Pydantic
│   ├── seed.py                 # loads data/*.json into models
│   ├── data/                   # users.json policies.json settlement_table.json
│   ├── static/audio/           # pre-generated TTS
│   ├── scripts/pregen_audio.py
│   └── tests/test_rules.py
├── web/                        # Next.js app
│   ├── app/                    # layout.tsx page.tsx globals.css
│   ├── components/             # Chat.tsx ClaimPanel.tsx Dashboard.tsx Login.tsx
│   └── lib/                    # useClaim.ts api.ts format.ts media.ts
└── docs/
    ├── DEMO_SCENARIOS.md
    └── pitch/Claim_Karo_Pitch.pptx
```

Env vars (`api/.env`): `ANTHROPIC_API_KEY`, `SARVAM_API_KEY`, `CLAUDE_MODEL`,
`SARVAM_STT_MODEL`, `SARVAM_TTS_MODEL`, `SARVAM_TTS_SPEAKER`, `DATABASE_URL`,
`LIVEKIT_URL` / `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` (dev server: `ws://localhost:7880`,
`devkey`, `secret`), `CORS_ORIGINS` (optional). Web (`web/.env.local`, optional):
`NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).

### Running locally

Needs Docker Desktop, Python 3.13 (`py` launcher) and Node 22.

```
.\start.ps1            # Docker, empty the database, frontend production build, then API, agent and web
                       # (next start) in their own windows; the API recreates the tables and reseeds
.\start.ps1 -KeepData  # same, but keep sessions and claims from earlier runs
.\stop.ps1             # stop everything (data stays until the next .\start.ps1)
.\stop.ps1 -Reset      # stop everything and delete the database + CloudBeaver volumes
```

The first run creates `api/.venv`, `api/.env` and `web/node_modules`.

| Service | URL | Login |
|---|---|---|
| App | http://localhost:3000 | — |
| API | http://localhost:8000 | — |
| LiveKit | ws://localhost:7880 (agent worker: `python -m agent.claim_agent dev` in `api/`) | `devkey` / `secret` |
| CloudBeaver | http://localhost:8978 | opens anonymously with the `Claim Karo (Postgres)` connection; admin `cbadmin` / `ClaimKaro123` |
| Postgres | `localhost:5433`, db `claim_karo` | `claimkaro` / `claimkaro` |

Tables: `users`, `vehicles`, `policies`, `policy_required_documents`, `documents`
(catalog with English/Hindi names) — all copied from `data/*.json` on every start —
`sessions`, `messages`, `incidents` (with verdict + viability JSON), `evidence`, `claims`,
`claim_documents` (each claim's document checklist).
All credentials are local-dev only.

### Running the backend tests

```
cd api
py -3.13 -m venv .venv          # or python3.11+ -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # .venv/bin/pip on macOS/Linux
.venv/Scripts/python -m pytest
```

---

## 12. Demo scenarios (build exactly these)

**Scenario 1 — Two-wheeler scrape, Hindi, advise not to claim**
User (Babu Khan): "Signal pe bike ko taxi ne maar diya, ₹4,200 ka kharcha bata raha hai
mechanic."
→ policy 1 matched → ₹4,200 − 45% depreciation (₹1,890) − ₹600 deductibles = payout
**₹1,710**; NCB loss ₹840 next year, **₹2,040** over three years → `dont_claim`
→ agent explains in Hindi and recommends paying out of pocket; offers to file anyway.

**Scenario 2 — Car rear-ended, English, claim worth filing**
User (Nadarajan G): "Someone hit the back of my Hector, garage says ₹38,000."
→ policy 4 (`ncb_protect`) → ₹38,000 − 45% depreciation (₹17,100) − ₹1,000 = payout
**₹19,900** vs NCB loss ₹0 → `claim`
→ EVIDENCE: `case2` Hector photo (plate `DL12TC0271`) → `case2` DL
→ form pre-filled → File → reference number.

**Scenario 3 (P2) — Third-party damage**: user hit someone else's car; agent routes to
third-party cover, says FIR is required, explains own-damage portion separately.

Record a screen + audio video of Scenarios 1 and 2 on Day 4 as a fallback.

---

## 13. 4-day plan

| Day | Person A (backend / agent) | Person B (frontend / voice) |
|---|---|---|
| 1 | Seed data; `models.py`; `rules.py` + tests; settlement table | Next.js skeleton; `MicButton` recording; Sarvam STT/TTS wrappers against a stub; `pregen_audio.py` |
| 2 | `state_machine.py` INTAKE → VIABILITY; `claude.py` extract + explain; WebSocket | `useClaimSocket` reducer; `ClaimPanel` fields animating; audio queue |
| 3 | EVIDENCE + vision grading; FORM_REVIEW; missing docs | Photo upload + `EvidenceGrid`; integration; Scenario 1 end to end |
| 4 | Scenario 2 end to end; P1 if time; latency tuning | Polish, error states, rehearsal, fallback recordings |

Definition of done for Day 3: Scenario 1 runs start to finish on a fresh session with
voice in and voice out, no console errors.

---

## 14. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Hindi STT misses rupee amounts / dates | Show transcript, let user correct by text; Claude extraction tolerates Hinglish numerals |
| Vision grading inconsistent | Low temperature; strict issue-code enum; accept on second attempt if confidence ≥ 0.6; manual "accept anyway" button hidden behind long-press for demo emergencies |
| Claude invents amounts | Numbers only via tool input; Pydantic validation; unit test that explanation contains the exact rupee figures passed in |
| Latency > 4 s per turn | Pre-generated audio; sentence-level TTS; show fields streaming before the reply; Sonnet not Opus |
| Venue Wi-Fi / API outage | Local fallback recordings; text fallback; cached TTS for both scenarios |
| Scope creep | Anything not in Section 2 P0 waits until Scenario 1 is done |

---

## 15. Conventions

- Python 3.11+, `ruff` formatting, type hints everywhere, Pydantic v2.
- No business logic in `main.py`; it calls the agent graph; graph nodes call services.
- Every Claude tool has a fixture test with a canned response.
- Commit small and often; `main` must always run Scenario 1.
- Log every Claude/Sarvam call with latency to `logs/` — we will tune from this.
````

### `docker-compose.yml`

````yaml
# Local infra: Postgres, CloudBeaver (DBeaver in the browser) and the LiveKit media server.
# Started by start.ps1.
name: claim-karo

services:
  postgres:
    image: postgres:17-alpine
    environment:
      POSTGRES_DB: claim_karo
      POSTGRES_USER: claimkaro
      POSTGRES_PASSWORD: claimkaro
    ports:
      - "5433:5432" # 5433 on the host so it never clashes with a local Postgres
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U claimkaro -d claim_karo"]
      interval: 2s
      timeout: 3s
      retries: 30

  # WebRTC media server for the voice agent, dev mode (API key devkey, secret secret).
  # --node-ip makes it advertise localhost, so the browser and the agent on the host reach it.
  livekit:
    image: livekit/livekit-server:v1.13.11
    command: --dev --bind 0.0.0.0 --node-ip 127.0.0.1
    ports:
      - "7880:7880" # signalling (WebSocket)
      - "7881:7881" # media over TCP
      - "7882:7882/udp" # media over UDP

  # Copies the preset connection into CloudBeaver's workspace on first run only.
  # CloudBeaver rewrites these files (it encrypts the password), so they live in a volume.
  cloudbeaver-init:
    image: busybox:1.37
    command: >
      sh -c "mkdir -p /ws/GlobalConfiguration/.dbeaver &&
             [ -f /ws/GlobalConfiguration/.dbeaver/data-sources.json ] ||
             cp /seed/*.json /ws/GlobalConfiguration/.dbeaver/"
    volumes:
      - ./docker/cloudbeaver:/seed:ro
      - cbworkspace:/ws

  cloudbeaver:
    image: dbeaver/cloudbeaver:latest
    depends_on:
      postgres:
        condition: service_healthy
      cloudbeaver-init:
        condition: service_completed_successfully
    environment:
      CB_SERVER_NAME: Claim Karo
      CB_SERVER_URL: http://localhost:8978/
      CB_ADMIN_NAME: cbadmin
      CB_ADMIN_PASSWORD: ClaimKaro123
      CLOUDBEAVER_APP_ANONYMOUS_ACCESS_ENABLED: "true"
    ports:
      - "8978:8978"
    volumes:
      - cbworkspace:/opt/cloudbeaver/workspace

volumes:
  pgdata:
  cbworkspace:
````

### `docker/cloudbeaver/data-sources-permissions.json`

````json
{
  "claimkaro-postgres": ["user"]
}
````

### `docker/cloudbeaver/data-sources.json`

````json
{
  "folders": {},
  "connections": {
    "claimkaro-postgres": {
      "provider": "postgresql",
      "driver": "postgres-jdbc",
      "name": "Claim Karo (Postgres)",
      "save-password": true,
      "read-only": false,
      "configuration": {
        "host": "postgres",
        "port": "5432",
        "database": "claim_karo",
        "configurationType": "MANUAL",
        "auth-model": "native",
        "auth-properties": {
          "userName": "claimkaro",
          "userPassword": "claimkaro"
        }
      }
    }
  }
}
````

### `start.ps1`

````powershell
# Starts everything: Postgres + CloudBeaver + LiveKit (Docker), FastAPI backend, the LiveKit
# voice agent, and the Next.js frontend.
# Every start wipes the database; the backend then recreates the tables and reseeds them.
# Usage: .\start.ps1             fresh database every time
#        .\start.ps1 -KeepData   keep sessions and claims from earlier runs
#        (stop with .\stop.ps1)
param([switch]$KeepData)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$api = Join-Path $root "api"
$web = Join-Path $root "web"
$pidFile = Join-Path $root ".pids"

if (Test-Path $pidFile) {
    Write-Host "Already running (found .pids). Run .\stop.ps1 first." -ForegroundColor Yellow
    exit 1
}

# 1. Docker: Postgres + CloudBeaver + LiveKit media server
Write-Host "Starting Postgres, CloudBeaver and LiveKit..." -ForegroundColor Cyan
docker compose -f (Join-Path $root "docker-compose.yml") up -d --wait postgres cloudbeaver livekit
if ($LASTEXITCODE -ne 0) { throw "docker compose failed. Is Docker Desktop running?" }

# Fresh data: drop every table. The backend applies db/schema.sql and copies data/*.json
# back in when it starts (step 4), so this only has to empty the database.
if ($KeepData) {
    Write-Host "Keeping existing data (-KeepData)." -ForegroundColor Yellow
} else {
    Write-Host "Deleting old data..." -ForegroundColor Cyan
    docker compose -f (Join-Path $root "docker-compose.yml") exec -T postgres `
        psql -v ON_ERROR_STOP=1 -q -U claimkaro -d claim_karo `
        -c "SET client_min_messages = warning; DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
    if ($LASTEXITCODE -ne 0) { throw "Could not reset the database." }
}

# 2. First-run setup
if (-not (Test-Path (Join-Path $api ".env"))) {
    Copy-Item (Join-Path $api ".env.example") (Join-Path $api ".env")
    Write-Host "Created api\.env - add your ANTHROPIC_API_KEY and SARVAM_API_KEY." -ForegroundColor Yellow
}
$python = Join-Path $api ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Creating Python venv..." -ForegroundColor Cyan
    py -3.13 -m venv (Join-Path $api ".venv")
}
# Also covers venvs created before the LiveKit agent existed.
& $python -c "import livekit.agents" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing backend packages..." -ForegroundColor Cyan
    & $python -m pip install -q -r (Join-Path $api "requirements.txt")
    # turn-detector and VAD model weights, so the first call doesn't wait for a download
    Push-Location $api; & $python -m livekit.agents download-files; Pop-Location
}
if (-not (Test-Path (Join-Path $web "node_modules"))) {
    Write-Host "Installing frontend packages..." -ForegroundColor Cyan
    Push-Location $web; npm install; Pop-Location
}

# 3. Production build of the frontend (NEXT_PUBLIC_* env vars are baked in here)
Write-Host "Building frontend..." -ForegroundColor Cyan
Push-Location $web
npm run build
$buildExit = $LASTEXITCODE
Pop-Location
if ($buildExit -ne 0) { throw "Frontend build failed. Fix the errors above and run .\start.ps1 again." }

# 4. Backend, voice agent and frontend, each in its own window so logs stay visible.
#    The backend creates the tables and seeds users, vehicles, policies and documents on startup.
$backend = Start-Process powershell -PassThru -WorkingDirectory $api -ArgumentList @(
    "-NoExit", "-Command",
    "`$Host.UI.RawUI.WindowTitle = 'Claim Karo API'; & '$python' -m uvicorn main:app --reload --port 8000"
)
$agent = Start-Process powershell -PassThru -WorkingDirectory $api -ArgumentList @(
    "-NoExit", "-Command",
    "`$Host.UI.RawUI.WindowTitle = 'Claim Karo Agent'; & '$python' -m agent.claim_agent dev"
)
$frontend = Start-Process powershell -PassThru -WorkingDirectory $web -ArgumentList @(
    "-NoExit", "-Command",
    "`$Host.UI.RawUI.WindowTitle = 'Claim Karo Web'; npm run start"
)
"$($backend.Id)`n$($agent.Id)`n$($frontend.Id)" | Set-Content $pidFile

Write-Host ""
Write-Host "Claim Karo is starting:" -ForegroundColor Green
Write-Host "  App          http://localhost:3000"
Write-Host "  API          http://localhost:8000"
Write-Host "  LiveKit      ws://localhost:7880  (dev keys devkey / secret; voice agent 'claim-karo')"
Write-Host "  CloudBeaver  http://localhost:8978  (connection 'Claim Karo (Postgres)'; admin cbadmin / ClaimKaro123)"
Write-Host "  Postgres     localhost:5433  db claim_karo  user claimkaro / claimkaro"
Write-Host "Stop everything with .\stop.ps1"
````

### `start.sh`

````bash
#!/usr/bin/env bash
set -Eeuo pipefail

# Starts the local Claim Karo stack on macOS (including Apple Silicon).
# Usage:
#   ./start.sh             Reset the database before starting
#   ./start.sh --keep-data Keep existing database data

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API="$ROOT/api"
WEB="$ROOT/web"
PID_FILE="$ROOT/.pids"
LOG_DIR="$ROOT/logs"
COMPOSE_FILE="$ROOT/docker-compose.yml"
KEEP_DATA=false

if [[ "${1:-}" == "--keep-data" ]]; then
    KEEP_DATA=true
elif [[ $# -ne 0 ]]; then
    echo "Usage: $0 [--keep-data]" >&2
    exit 2
fi

if [[ -f "$PID_FILE" ]]; then
    echo "Already running (found .pids). Run ./stop.sh first." >&2
    exit 1
fi

command -v docker >/dev/null || { echo "Docker is required. Start Docker Desktop and try again." >&2; exit 1; }
command -v npm >/dev/null || { echo "Node.js and npm are required." >&2; exit 1; }

if command -v python3.13 >/dev/null; then
    PYTHON="$(command -v python3.13)"
elif command -v python3 >/dev/null; then
    PYTHON="$(command -v python3)"
else
    echo "Python 3.11+ is required." >&2
    exit 1
fi

if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
    echo "Python 3.11+ is required (found $("$PYTHON" --version))." >&2
    exit 1
fi

echo "Starting Postgres, CloudBeaver and LiveKit..."
docker compose -f "$COMPOSE_FILE" up -d --wait postgres cloudbeaver livekit

if [[ "$KEEP_DATA" == true ]]; then
    echo "Keeping existing data (--keep-data)."
else
    echo "Deleting old data..."
    docker compose -f "$COMPOSE_FILE" exec -T postgres \
        psql -v ON_ERROR_STOP=1 -q -U claimkaro -d claim_karo \
        -c "SET client_min_messages = warning; DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
fi

if [[ ! -f "$API/.env" ]]; then
    cp "$API/.env.example" "$API/.env"
    echo "Created api/.env - add your ANTHROPIC_API_KEY and SARVAM_API_KEY."
fi

VENV="$API/.venv"
PYTHON_BIN="$VENV/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Creating Python virtual environment..."
    "$PYTHON" -m venv "$VENV"
fi

if ! "$PYTHON_BIN" -c 'import livekit.agents' >/dev/null 2>&1; then
    echo "Installing backend packages..."
    "$PYTHON_BIN" -m pip install -q -r "$API/requirements.txt"
    (cd "$API" && "$PYTHON_BIN" -m livekit.agents download-files)
fi

if [[ ! -d "$WEB/node_modules" ]]; then
    echo "Installing frontend packages..."
    (cd "$WEB" && npm install)
fi

echo "Building frontend..."
(cd "$WEB" && npm run build)

mkdir -p "$LOG_DIR"

(cd "$API" && exec nohup "$PYTHON_BIN" -m uvicorn main:app --reload --port 8000) \
    >"$LOG_DIR/api.log" 2>&1 &
BACKEND_PID=$!

(cd "$API" && exec nohup "$PYTHON_BIN" -m agent.claim_agent dev) \
    >"$LOG_DIR/agent.log" 2>&1 &
AGENT_PID=$!

(cd "$WEB" && exec nohup npm run start) \
    >"$LOG_DIR/web.log" 2>&1 &
FRONTEND_PID=$!

printf '%s\n' "$BACKEND_PID" "$AGENT_PID" "$FRONTEND_PID" > "$PID_FILE"

echo
echo "Claim Karo is starting:"
echo "  App          http://localhost:3000"
echo "  API          http://localhost:8000"
echo "  LiveKit      ws://localhost:7880  (dev keys devkey / secret; voice agent 'claim-karo')"
echo "  CloudBeaver  http://localhost:8978  (connection 'Claim Karo (Postgres)'; admin cbadmin / ClaimKaro123)"
echo "  Postgres     localhost:5433  db claim_karo  user claimkaro / claimkaro"
echo "  Logs         $LOG_DIR/{api,agent,web}.log"
echo "Stop everything with ./stop.sh"
````

### `stop.ps1`

````powershell
# Stops what start.ps1 started. Data in Postgres is kept (Docker volume).
# Usage: .\stop.ps1          stop everything
#        .\stop.ps1 -Reset   also delete the database and CloudBeaver volumes
param([switch]$Reset)
$root = $PSScriptRoot
$pidFile = Join-Path $root ".pids"

if (Test-Path $pidFile) {
    foreach ($id in Get-Content $pidFile) {
        if ($id) {
            # /T kills the whole tree (uvicorn reloader, agent worker, node server) in that window
            taskkill /T /F /PID $id 2>$null | Out-Null
        }
    }
    Remove-Item $pidFile
    Write-Host "Stopped backend, voice agent and frontend." -ForegroundColor Green
} else {
    Write-Host "No .pids file: backend/agent/frontend not started by start.ps1." -ForegroundColor Yellow
}

$compose = Join-Path $root "docker-compose.yml"
if ($Reset) {
    docker compose -f $compose down -v
    Write-Host "Stopped containers and deleted volumes." -ForegroundColor Green
} else {
    docker compose -f $compose down
    Write-Host "Stopped containers (data kept)." -ForegroundColor Green
}
````

### `stop.sh`

````bash
#!/usr/bin/env bash
set -Eeuo pipefail

# Stops the macOS processes started by start.sh.
# Usage:
#   ./stop.sh         Stop services and keep database data
#   ./stop.sh --reset Stop services and delete database volumes

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$ROOT/.pids"
COMPOSE_FILE="$ROOT/docker-compose.yml"

if [[ "${1:-}" != "" && "${1:-}" != "--reset" ]]; then
    echo "Usage: $0 [--reset]" >&2
    exit 2
fi

if [[ -f "$PID_FILE" ]]; then
    while IFS= read -r pid; do
        if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done < "$PID_FILE"
    rm -f "$PID_FILE"
    echo "Stopped backend, voice agent and frontend."
else
    echo "No .pids file: backend/agent/frontend not started by start.sh."
fi

if [[ "${1:-}" == "--reset" ]]; then
    docker compose -f "$COMPOSE_FILE" down -v
    echo "Stopped containers and deleted volumes."
else
    docker compose -f "$COMPOSE_FILE" down
    echo "Stopped containers (data kept)."
fi
````

### `api/.env.example`

````text
ANTHROPIC_API_KEY=
SARVAM_API_KEY=
CLAUDE_MODEL=claude-sonnet-5-5
SARVAM_STT_MODEL=saaras:v4
SARVAM_TTS_MODEL=bulbul:v4-flash
SARVAM_TTS_SPEAKER=ishita_enhi_customer
# Speaking speed: 1.0 is normal; lower is slower (0.5-2.0 on bulbul:v4-flash)
SARVAM_TTS_PACE=1.0
DATABASE_URL=postgresql://claimkaro:claimkaro@localhost:5433/claim_karo
# LiveKit media server (docker-compose service, dev mode)
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
````

### `api/agent/__init__.py`

````python
"""The claim conversation: a LiveKit voice agent (claim_agent.py) and its fixed lines."""

# main.livekit_token dispatches the agent registered under this name into each new room.
AGENT_NAME = "claim-karo"
````

### `api/agent/claim_agent.py`

````python
"""Claim conversation as a LiveKit voice agent (README §4). One session per LiveKit room.

LiveKit runs the call: WebRTC audio, voice activity and turn detection, and
typed chat (topic lk.chat). Sarvam turns speech into text and back, and Claude runs the
conversation by calling the tools on ClaimAgent. Rules decide, Claude explains: every
number Claude says comes from services/rules.py through a tool result.

    state.py   Claim: the claim's working state, sent to the browser on "claim.state"
    prompt.py  the system instructions
    tools.py   ClaimAgent and the tools Claude calls
    this file  photo grading, language, and the worker that starts each session

Photos arrive as byte streams on the "photo" topic and are graded outside the LLM.

Run (with livekit-server up):  python -m agent.claim_agent dev
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from livekit import rtc  # noqa: E402
from livekit.agents import (  # noqa: E402
    AgentServer,
    AgentSession,
    ChatContext,
    JobContext,
    JobProcess,
    cli,
    inference,
)
from livekit.agents.utils import is_given  # noqa: E402
from livekit.plugins import anthropic, sarvam, silero  # noqa: E402

import db  # noqa: E402
from agent import AGENT_NAME  # noqa: E402
from agent.state import Claim  # noqa: E402
from agent.tools import ClaimAgent  # noqa: E402
from models import Evidence, Incident, Language  # noqa: E402
from seed import load_wallet  # noqa: E402
from services import claude, rules, settlement  # noqa: E402

log = logging.getLogger("agent")

PHOTO_TOPIC = "photo"

# What Claude reads off each kind of upload, for rules.verify_details to check.
READ_FIELDS: dict[str, set[str]] = {
    "damage_wide": {"number_plate_text"},
    "dl": {"licence_number", "licence_holder_name", "licence_valid_until"},
}


# --- photos (graded outside the LLM) -----------------------------------------------------


def mismatch_line(claim: Claim, codes: list[str], details: dict) -> str:
    """Tell the user which detail didn't match the records and what to upload instead."""
    policy = claim.policy
    assert policy is not None
    if "PLATE_NOT_READABLE" in codes:
        return claim.line("plate_not_readable")
    if "PLATE_MISMATCH" in codes:
        vehicle = load_wallet().vehicles[policy.vehicle_id]
        return claim.line(
            "plate_mismatch", seen=details["number_plate_text"], expected=vehicle.vehicle_number
        )
    if "DL_NUMBER_MISMATCH" in codes or "DL_NAME_MISMATCH" in codes:
        return claim.line("dl_mismatch", last4=policy.driving_licence_number[-4:])
    if "DL_EXPIRED_ON_INCIDENT_DATE" in codes:
        return claim.line("dl_expired")
    return claim.line("dl_not_readable")


async def on_photo(session: AgentSession[Claim], image: bytes, photo_id: str, mime: str) -> None:
    claim = session.userdata
    kind = claim.next_photo_kind() if claim.stage == "EVIDENCE" else None
    if kind is None:
        return
    claim.photos[photo_id] = {"status": "grading"}
    await claim.publish()

    policy = claim.policy
    assert policy is not None
    grade = await claude.grade_damage_photo(image, mime, kind, claim.language)
    # the plate / licence read off the photo must match the vehicle and the policy's records
    details = grade.model_dump(mode="json", include=READ_FIELDS.get(kind, set()))
    vehicle = load_wallet().vehicles[policy.vehicle_id]
    mismatches = rules.verify_details(kind, details, vehicle, policy, claim.incident)
    attempts = claim.retakes.get(kind, 0)
    # A second attempt with decent confidence passes on photo quality, so the demo can't get
    # stuck; a detail that doesn't match the records never passes.
    accepted = not mismatches and (grade.accepted or (attempts >= 1 and grade.confidence >= 0.6))

    evidence = Evidence(
        id=photo_id,
        evidence_type=kind,
        file_path="",
        is_accepted=accepted,
        quality_issues=[] if accepted else list(grade.issues),
        ai_confidence_score=grade.confidence,
        extracted_details=details,
        detail_mismatches=mismatches,
    )
    await db.add_evidence(claim.session_id, evidence)
    claim.evidence.append(evidence)
    claim.retakes[kind] = attempts + 1
    claim.photos[photo_id] = {
        "status": "accepted" if accepted else "retake",
        "evidence_type": kind,
        "quality_issues": evidence.quality_issues + mismatches,
    }

    if not accepted:
        await claim.publish()
        retake = mismatch_line(claim, mismatches, details) if mismatches else None
        session.say(retake or grade.retake_instruction or claim.line("upload_photo"))
        return

    next_kind = claim.next_photo_kind()
    if next_kind:
        await claim.publish()
        session.say(claim.line("next_photo", kind=claim.photo_label(next_kind)))
        return

    await review_form(claim)
    session.generate_reply(
        instructions=f"""The claim form is ready: {json.dumps(claim.form, ensure_ascii=False)}.
Missing documents: {claim.missing_docs or "none"}. Settlement estimate: {claim.settlement}.
In at most 3 sentences: confirm the claim is ready, name any missing documents, give the
settlement time, and ask whether to file it now."""
    )


async def review_form(claim: Claim) -> None:
    """Fill in the claim form and its document checklist once every photo is in."""
    incident, policy, verdict = claim.incident, claim.policy, claim.viability
    assert policy is not None
    vehicle = load_wallet().vehicles[policy.vehicle_id]
    ctype = rules.claim_type(incident, policy) or "own_damage"
    required = rules.required_documents(incident, policy)
    missing = rules.missing_documents(incident, policy, claim.evidence)
    est = settlement.estimate(ctype, rules.is_cashless(incident, policy), not missing)

    claim.form = {
        "policyholder": claim.user.full_name,
        "phone_number": claim.user.phone_number,
        "insurer_name": policy.insurer_name,
        "policy_number": policy.policy_number,
        "vehicle": f"{vehicle.brand} {vehicle.model} ({vehicle.vehicle_number})",
        "claim_type": ctype,
        "incident_date": str(incident.incident_date),
        "incident_location": incident.incident_location,
        "description": incident.description_english,
        "estimated_repair_cost_inr": incident.estimated_repair_cost_inr,
        "expected_payout_inr": verdict.insurer_payout_inr if verdict else None,
        "garage": incident.garage_name,
        "route": est.route,
    }
    claim.missing_docs = missing
    claim.settlement = est.model_dump()
    checklist = {code: code not in missing for code in required}
    await db.save_claim(
        claim.session_id, policy.id, ctype, claim.form, checklist, (est.min_days, est.max_days)
    )
    await claim.set_stage("FORM_REVIEW")
    await claim.publish()


# --- language ----------------------------------------------------------------------------


class ClaudeLLM(anthropic.LLM):
    """Claude at low effort: short spoken replies don't need long thinking."""

    def chat(self, **kwargs: Any):  # type: ignore[override]
        extra = kwargs.get("extra_kwargs")
        kwargs["extra_kwargs"] = {
            **(extra if is_given(extra) and extra else {}),
            "output_config": {"effort": "low"},
        }
        return super().chat(**kwargs)


def follow_language(session: AgentSession[Claim], language: Language) -> None:
    """Reply (and grade photos) in the language the user last spoke or typed."""
    claim = session.userdata
    if language == claim.language:
        return
    claim.language = language
    session.tts.update_options(target_language_code=f"{language}-IN")  # type: ignore[union-attr]


def is_hindi(text: str) -> bool:
    return any("ऀ" <= ch <= "ॿ" for ch in text)


# --- server ------------------------------------------------------------------------------


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load()


server = AgentServer(setup_fnc=prewarm)


@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: JobContext) -> None:
    await db.init()
    ctx.add_shutdown_callback(db.close)

    # the browser's token carries who is calling, the language, and any claim to resume
    # (main.livekit_token)
    participant = await ctx.wait_for_participant()
    user = load_wallet().users[participant.attributes["user_id"]]
    language: Language = "en" if participant.attributes.get("language") == "en" else "hi"
    resume_id = participant.attributes.get("resume_session_id")
    saved = await db.load_session(user.id, resume_id) if resume_id else None
    history: ChatContext | None = None
    if saved and resume_id and rules.is_resumable(saved["stage"]):
        claim = Claim(user=user, session_id=resume_id, language=language, room=ctx.room)
        claim.restore(saved)
        await db.update_session(claim.session_id, claim.stage, language)
        history = ChatContext()  # so Claude remembers what was said before
        for m in saved["messages"]:
            role = "user" if m["sender_role"] == "user" else "assistant"
            history.add_message(role=role, content=m["message_text"])
    else:
        claim = Claim(user=user, session_id=uuid.uuid4().hex, language=language, room=ctx.room)
        claim.incident = Incident(session_id=claim.session_id, user_id=user.id)
        await db.create_session(claim.session_id, user.id, "INTAKE", language)

    session = AgentSession[Claim](
        stt=sarvam.STT(language="unknown", model=os.getenv("SARVAM_STT_MODEL", "saaras:v4")),
        llm=ClaudeLLM(model=claude.MODEL),
        # bulbul:v4-flash is Sarvam's low-latency streaming model. Its voice names carry the
        # language: Ishita "enhi" speaks both Hindi and English, in a customer-support style.
        tts=sarvam.TTS(
            target_language_code=f"{language}-IN",
            model=os.getenv("SARVAM_TTS_MODEL", "bulbul:v4-flash"),
            speaker=os.getenv("SARVAM_TTS_SPEAKER", "ishita_enhi_customer"),
            pace=float(os.getenv("SARVAM_TTS_PACE", "1.0")),
        ),
        vad=ctx.proc.userdata["vad"],
        turn_handling={
            "turn_detection": inference.TurnDetector(version="v1-mini"),
            # On laptop speakers the mic hears the bot; with barge-in that echo cut the bot
            # off and it answered its own words. While it speaks, STT gets silence instead.
            "interruption": {"enabled": False},
        },
        userdata=claim,
        max_tool_steps=5,
    )

    @session.on("user_input_transcribed")
    def _on_transcript(ev) -> None:
        if ev.is_final and ev.language:
            follow_language(session, "en" if str(ev.language).startswith("en") else "hi")

    background: set[asyncio.Task] = set()

    def run_in_background(coro) -> None:
        task = asyncio.create_task(coro)
        background.add(task)
        task.add_done_callback(background.discard)
        task.add_done_callback(
            lambda t: (
                t.cancelled()
                or t.exception()
                and log.error("background task failed", exc_info=t.exception())
            )
        )

    @session.on("conversation_item_added")
    def _on_item(ev) -> None:
        item = ev.item
        text = getattr(item, "text_content", None)
        if getattr(item, "role", None) == "user" and text:
            run_in_background(db.add_message(claim.session_id, "user", text))
            if claim.incident.description_user_language is None:
                claim.incident.description_user_language = text  # the user's own first words
            if is_hindi(text):
                follow_language(session, "hi")
        elif getattr(item, "role", None) == "assistant" and text:
            run_in_background(db.add_message(claim.session_id, "bot", text))

    def _on_photo_stream(reader: rtc.ByteStreamReader, _identity: str) -> None:
        async def read() -> None:
            image = b"".join([chunk async for chunk in reader])
            photo_id = os.path.splitext(os.path.basename(reader.info.name))[0]
            try:
                await on_photo(session, image, photo_id, reader.info.mime_type or "image/jpeg")
            except Exception:
                log.exception("photo grading failed")
                session.say(claim.line("upload_photo"))

        run_in_background(read())

    ctx.room.register_byte_stream_handler(PHOTO_TOPIC, _on_photo_stream)

    await session.start(room=ctx.room, agent=ClaimAgent(claim, history))
    await claim.publish()
    if not (saved and saved["messages"] and history):  # new, or resumed before anyone spoke
        session.say(claim.line("greeting", name=user.full_name.split()[0]))
    else:
        session.generate_reply(
            instructions="The user has come back to continue this claim. In at most two short "
            "sentences, say where it stands and ask for the next thing needed."
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    cli.run_app(server)
````

### `api/agent/lines.py`

````python
"""Fixed bot lines, so the common prompts never wait on Claude."""

from __future__ import annotations

from models import Language

LINES: dict[str, dict[Language, str]] = {
    "greeting": {
        "hi": "नमस्ते {name}! मैं Claim Karo हूँ। बताइए, मैं आपकी क्या मदद कर सकती हूँ?",
        "en": "Hi {name}! I'm Claim Karo. How can I help you today?",
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
        "hi": (
            "आपका claim फ़ाइल हो गया। रेफ़रेंस नंबर {ref} है। चिंता मत कीजिए, मैं आपके claim "
            "का स्टेटस देखती रहूँगी और हर अपडेट आपको बताऊँगी।"
        ),
        "en": (
            "Your claim is filed. Your reference number is {ref}. Don't worry, I'll keep "
            "checking your claim's status and let you know every time it changes."
        ),
    },
    "use_buttons": {
        "hi": "कृपया नीचे दिए बटन से चुनें।",
        "en": "Please choose using the buttons below.",
    },
    "upload_photo": {
        "hi": "कृपया फ़ोटो अपलोड करें।",
        "en": "Please upload the photo.",
    },
    "plate_not_readable": {
        "hi": "नंबर प्लेट साफ़ नहीं पढ़ी जा रही। कृपया ऐसी फ़ोटो लें जिसमें नंबर प्लेट साफ़ दिखे।",
        "en": "I can't read the number plate. Please retake the photo with the plate visible.",
    },
    "plate_mismatch": {
        "hi": (
            "फ़ोटो में नंबर प्लेट {seen} है, पर आपकी बीमित गाड़ी का नंबर {expected} है। "
            "कृपया इसी गाड़ी की फ़ोटो अपलोड करें।"
        ),
        "en": (
            "The plate in this photo reads {seen}, but your insured vehicle is {expected}. "
            "Please upload a photo of that vehicle."
        ),
    },
    "dl_not_readable": {
        "hi": "लाइसेंस साफ़ नहीं पढ़ा जा रहा। कृपया लाइसेंस के सामने की तरफ़ की साफ़ फ़ोटो भेजें।",
        "en": "I can't read the licence. Please upload a sharp photo of the front of your licence.",
    },
    "dl_mismatch": {
        "hi": (
            "यह लाइसेंस पॉलिसी लेते समय दिए गए लाइसेंस (नंबर के आख़िरी अंक {last4}) से "
            "मेल नहीं खाता। कृपया वही लाइसेंस अपलोड करें।"
        ),
        "en": (
            "This licence doesn't match the one given when the policy was issued "
            "(number ending {last4}). Please upload that licence."
        ),
    },
    "dl_expired": {
        "hi": "यह लाइसेंस दुर्घटना की तारीख़ पर वैध नहीं था, इसलिए claim फ़ाइल नहीं हो सकता।",
        "en": "This licence wasn't valid on the date of the accident, so the claim can't be filed.",
    },
    "not_verified": {
        "hi": "claim फ़ाइल करने से पहले गाड़ी की फ़ोटो और ड्राइविंग लाइसेंस पॉलिसी से मेल खाने चाहिए।",
        "en": "Before filing, the vehicle photo and driving licence must match your policy.",
    },
}

PHOTO_LABEL: dict[str, dict[Language, str]] = {
    "damage_wide": {
        "hi": "पूरी गाड़ी, नुकसान और नंबर प्लेट साफ़ दिखे",
        "en": "the whole vehicle with the damage and number plate visible",
    },
    "odometer": {"hi": "ओडोमीटर रीडिंग", "en": "the odometer reading"},
    "dl": {"hi": "ड्राइविंग लाइसेंस (सामने की तरफ़)", "en": "your driving licence (front side)"},
}
````

### `api/agent/prompt.py`

````python
"""The voice agent's system instructions: persona, the user's vehicles, and the claim flow."""

from __future__ import annotations

from datetime import date

from agent.state import Claim
from services import claude


def instructions(claim: Claim) -> str:
    vehicles = "\n".join(
        f'- id "{v.id}": {v.brand} {v.model} ({v.vehicle_type}), reg {v.vehicle_number}'
        for v in claim.vehicles
    )
    return f"""{claude.SYSTEM}

You are on a call with {claim.user.full_name}. Today is {date.today().isoformat()}.
Their vehicles:
{vehicles}

How the claim goes:
1. Find out what happened. Every time the user gives facts about the incident, call
   record_incident with what they told you. You need the vehicle, the date, what happened,
   and a damage estimate (or that they don't know it). Ask ONE short question at a time
   for whatever record_incident says is still missing.
2. When record_incident returns a verdict, explain it in at most 3 short sentences: what
   the insurer would pay, the No-Claim Bonus lost over 3 years, and your recommendation.
   Unless it is not covered, also say in one sentence each: if they claim, the vehicle may
   have to stay in the service centre for 3-4 days; and the ₹1,000 file charge is free
   for them because they bought the policy through Paytm. Then ask whether they want to
   file the claim.
3. If they want to claim, call start_claim; if not, call decline_claim. Then say what the
   tool result tells you to.
4. Photos are uploaded with the camera button. You can't see them; the system checks
   each one and tells the user the result itself. Don't comment on photos you weren't told
   about.
5. When the claim form is ready and the user says to file it, call file_claim.
6. If the user wants to stop this claim, or to claim for a different vehicle or incident
   instead, call cancel_claim at any step, then record_incident with the new facts.

If a tool refuses, tell the user in one sentence what they can do instead. Never ask them to
call back later.

The user may ask questions at any step; answer them with these tools, briefly, then go back
to where the claim was:
- their policies, cover, NCB, deductible, exclusions, cashless garages: get_my_policies
- "what if the repair costs X?": estimate_payout (it does not change the claim)
- what's left, what's pending, what happens next: get_claim_progress
- an earlier claim: get_past_claims

If the user asks why they should buy or renew their policy through Paytm, answer warmly in
2-3 short sentences using only these points:
- Their policy, vehicle and claims are all in the Paytm app they already use; no searching
  emails or PDFs when something goes wrong.
- Every Paytm policy comes with you, Claim Karo: help in Hindi or English from the accident
  to filing.
- You tell them honestly whether a claim is worth it, so they don't lose their No-Claim
  Bonus on a small claim.
- You check the photos, fill in the claim form and list the missing documents for them.
- After filing, you keep tracking the claim's status and let them know when it changes.
Don't promise discounts, prices or anything not listed here.

Reply in the language the user last used: Hindi in Devanagari, or English. Never write
Hindi in Latin letters ("Afsos hai"): the voice reads it badly. The voice is a woman's, so
in Hindi speak as a woman ("देखती हूँ", "समझ गई", "बताऊँगी"). Only use numbers that came
from a tool result."""
````

### `api/agent/state.py`

````python
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
````

### `api/agent/tools.py`

````python
"""The tools Claude calls. The first five move the claim forward (or drop it) and each checks
the current stage, so Claude can't skip a step; the rest answer the user's questions at any
step and change nothing. Every number they return comes from the wallet, services/rules.py
or the db."""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Literal

from livekit.agents import Agent, ChatContext, RunContext, ToolError, function_tool

import db
from agent.prompt import instructions
from agent.state import Claim
from seed import load_wallet
from services import rules

RiskFlag = Literal["drunk_driving", "no_valid_dl", "commercial_use", "theft", "hit_and_run"]


class ClaimAgent(Agent):
    def __init__(self, claim: Claim, chat_ctx: ChatContext | None = None) -> None:
        # chat_ctx: the earlier conversation, when the user resumes a claim
        super().__init__(instructions=instructions(claim), chat_ctx=chat_ctx)

    @function_tool()
    async def record_incident(
        self,
        context: RunContext[Claim],
        vehicle_id: str | None = None,
        incident_date: str | None = None,
        incident_location: str | None = None,
        description_english: str | None = None,
        third_party_involved: bool | None = None,
        third_party_property_damaged: bool | None = None,
        anyone_injured: bool | None = None,
        estimated_repair_cost_inr: int | None = None,
        estimate_unknown: bool | None = None,
        garage_name: str | None = None,
        police_report_filed: bool | None = None,
        risk_flags: list[RiskFlag] | None = None,
    ) -> str:
        """Save facts about the accident. Pass only what the user has said; leave the rest null.

        Args:
            vehicle_id: One of the user's vehicle ids.
            incident_date: YYYY-MM-DD; resolve "kal"/"yesterday" against today.
            incident_location: Where it happened.
            description_english: One-line English summary of the whole incident so far.
            third_party_involved: Another person or vehicle was involved.
            third_party_property_damaged: Someone else's vehicle or property was damaged.
            anyone_injured: Anyone was hurt.
            estimated_repair_cost_inr: Repair cost in rupees ("4.2k" -> 4200).
            estimate_unknown: True only if the user says they don't know the cost.
            garage_name: Garage doing the repair.
            police_report_filed: Whether an FIR was filed.
            risk_flags: drunk_driving, no_valid_dl, commercial_use, theft, hit_and_run.
        """
        claim = context.userdata
        if claim.stage not in ("INTAKE", "VIABILITY"):
            raise ToolError(
                "This claim is past the details step. For a different vehicle or incident, "
                "call cancel_claim first, then record_incident."
            )

        updates: dict[str, Any] = {
            k: v
            for k, v in {
                "vehicle_id": vehicle_id,
                "incident_location": incident_location,
                "description_english": description_english,
                "third_party_involved": third_party_involved,
                "third_party_property_damaged": third_party_property_damaged,
                "anyone_injured": anyone_injured,
                "estimated_repair_cost_inr": estimated_repair_cost_inr,
                "garage_name": garage_name,
                "police_report_filed": police_report_filed,
            }.items()
            if v is not None
        }
        if vehicle_id is not None and vehicle_id not in {v.id for v in claim.vehicles}:
            raise ToolError(f"Unknown vehicle_id {vehicle_id!r}; use one of the listed ids.")
        if incident_date is not None:
            try:
                updates["incident_date"] = date.fromisoformat(incident_date)
            except ValueError:
                raise ToolError("incident_date must be YYYY-MM-DD.") from None
        if risk_flags:
            updates["risk_flags"] = sorted(set(claim.incident.risk_flags) | set(risk_flags))

        incident = claim.incident.model_copy(update=updates)
        claim.incident = incident
        claim.estimate_unknown = claim.estimate_unknown or bool(estimate_unknown)
        await db.save_incident(claim.session_id, incident)

        missing = rules.missing_incident_facts(incident, claim.estimate_unknown)
        if missing:
            await claim.publish()
            return f"Saved. Still needed: {', '.join(missing)}."

        # everything required is known: match the policy and run the numbers
        policy = rules.match_policy(incident, load_wallet().policies_for(claim.user.id))
        if policy is None:
            await claim.set_stage("NO_COVER")
            await claim.publish()
            return "No policy covers this. Tell the user, kindly, in one sentence."
        claim.policy = policy
        vehicle = load_wallet().vehicles[policy.vehicle_id]
        claim.viability = rules.viability(incident, policy, vehicle)
        await db.save_incident(claim.session_id, incident, policy.id, claim.viability)
        covered = claim.viability.verdict != "not_covered"
        await claim.set_stage("VIABILITY" if covered else "NO_COVER")
        await claim.publish()
        note = (
            "If estimate_pending, say claiming makes sense only above breakeven_estimate_inr "
            "and ask for the garage estimate. If not_covered, say why from the reason codes."
        )
        if covered:
            note = (
                "Start with one short sentence congratulating the user: their vehicle is "
                "covered by the policy they bought through Paytm, so they made the right "
                "choice. Then explain the verdict, mention the 3-4 days in the service "
                "centre and that the ₹1,000 file charge is free through Paytm. " + note
            )
        return json.dumps(
            {
                "policy": f"{policy.insurer_name}, NCB {policy.no_claim_bonus_pct}%, "
                f"add-ons {policy.add_on_covers or 'none'}",
                "verdict (final, do not recompute)": claim.viability.model_dump(),
                "note": note,
            }
        )

    @function_tool()
    async def start_claim(self, context: RunContext[Claim]) -> str:
        """The user wants to file the claim after hearing the verdict."""
        claim = context.userdata
        if claim.stage != "VIABILITY":
            raise ToolError("There is no verdict to act on yet.")
        await claim.set_stage("EVIDENCE")
        await claim.publish()
        kind = claim.next_photo_kind()
        return f"Say exactly: {claim.line('ask_photo', kind=claim.photo_label(kind or ''))}"

    @function_tool()
    async def decline_claim(self, context: RunContext[Claim]) -> str:
        """The user decided not to file the claim after hearing the verdict."""
        claim = context.userdata
        if claim.stage != "VIABILITY":
            raise ToolError(
                f"The claim is at step {claim.stage}, not the verdict. To drop it, call "
                "cancel_claim."
            )
        await claim.set_stage("ADVISED_NO_CLAIM")
        await claim.publish()
        return f"Say exactly: {claim.line('advised_no_claim')}"

    @function_tool()
    async def file_claim(self, context: RunContext[Claim]) -> str:
        """File the reviewed claim with the insurer, once the user confirms."""
        claim = context.userdata
        if claim.stage != "FORM_REVIEW":
            raise ToolError("The claim form isn't ready yet.")
        context.disallow_interruptions()
        try:
            reference = await db.file_claim(claim.session_id)
        except db.DocumentsNotVerified:
            raise ToolError(claim.line("not_verified")) from None
        if reference is None:  # already filed from the dashboard
            raise ToolError("This claim is already filed.")
        claim.reference = reference
        await claim.set_stage("FILED")
        await claim.publish()
        return f"Say exactly: {claim.line('filed', ref=reference)}"

    @function_tool()
    async def cancel_claim(self, context: RunContext[Claim]) -> str:
        """Drop the current claim at any step before it is filed and start a new one, e.g.
        when the user wants to stop this claim or claim for a different vehicle instead.
        Then record the new incident's facts with record_incident."""
        claim = context.userdata
        filed_reference = claim.reference
        if rules.is_cancellable(claim.stage):
            await db.cancel_claim(claim.session_id)
        await claim.start_over()
        await claim.publish()
        if filed_reference:
            return (
                f"The earlier claim was already filed (reference {filed_reference}) and stays "
                "with the insurer. A new claim has started."
            )
        return "Cancelled. A new claim has started."

    # --- questions the user can ask at any step (read-only) -------------------------------

    @function_tool()
    async def get_my_policies(self, context: RunContext[Claim]) -> str:
        """The user's insurance policies: insurer, policy number, vehicle, cover, validity,
        IDV, No-Claim Bonus, deductible, add-ons, exclusions, documents a claim needs, and
        cashless garages. Use when the user asks about their policy or coverage."""
        wallet = load_wallet()
        policies = [
            rules.policy_summary(
                p,
                wallet.vehicles[p.vehicle_id],
                wallet.document_names(p.required_documents),
                date.today(),
            )
            for p in wallet.policies_for(context.userdata.user.id)
        ]
        return _to_json({"policies": policies})

    @function_tool()
    async def estimate_payout(
        self,
        context: RunContext[Claim],
        estimated_repair_cost_inr: int,
        vehicle_id: str | None = None,
    ) -> str:
        """What-if: what the insurer would pay and the No-Claim Bonus lost for a given repair
        cost, without changing the claim. Use when the user asks "what if it costs X?".

        Args:
            estimated_repair_cost_inr: The repair cost to try, in rupees.
            vehicle_id: Which vehicle; defaults to the one in this claim.
        """
        claim = context.userdata
        vehicle_id = vehicle_id or claim.incident.vehicle_id
        if vehicle_id is None:
            raise ToolError("Ask which vehicle first.")
        if vehicle_id not in {v.id for v in claim.vehicles}:
            raise ToolError(f"Unknown vehicle_id {vehicle_id!r}.")
        wallet = load_wallet()
        verdict = rules.what_if(
            claim.incident.model_copy(update={"vehicle_id": vehicle_id}),
            estimated_repair_cost_inr,
            wallet.policies_for(claim.user.id),
            wallet.vehicles,
            date.today(),
        )
        if verdict is None:
            return "No active policy covers this vehicle for this damage."
        return _to_json({"hypothetical (claim unchanged)": verdict.model_dump()})

    @function_tool()
    async def get_claim_progress(self, context: RunContext[Claim]) -> str:
        """Where this claim stands: current step, facts recorded, verdict, photos still
        needed, missing documents, settlement time and reference number. Use when the user
        asks what's left, what's pending, or what happens next."""
        return _to_json(context.userdata.progress())

    @function_tool()
    async def get_past_claims(self, context: RunContext[Claim]) -> str:
        """The user's earlier claims, newest first: status (draft or filed), reference number,
        vehicle, incident date, expected payout, settlement days and documents missing. Use
        when the user asks about a previous claim."""
        claims = await db.user_claims(context.userdata.user.id)
        return _to_json({"claims": claims}) if claims else "The user has no earlier claims."


def _to_json(value: dict) -> str:
    # Always an object: the LiveKit Anthropic plugin sends a JSON *array* tool result to
    # Claude as content blocks, which the API rejects ("tool_result.content.0.type").
    return json.dumps(value, ensure_ascii=False, default=str)  # default: dates from the db
````

### `api/data/documents.json`

````json
[
  {
    "document_code": "rc",
    "name_english": "Registration certificate (RC)",
    "name_hindi": "रजिस्ट्रेशन सर्टिफ़िकेट (RC)"
  },
  {
    "document_code": "dl",
    "name_english": "Driving licence",
    "name_hindi": "ड्राइविंग लाइसेंस"
  },
  {
    "document_code": "policy_copy",
    "name_english": "Policy copy",
    "name_hindi": "पॉलिसी की कॉपी"
  },
  {
    "document_code": "garage_estimate",
    "name_english": "Garage estimate",
    "name_hindi": "गैराज का एस्टिमेट"
  },
  {
    "document_code": "fir",
    "name_english": "FIR copy",
    "name_hindi": "FIR की कॉपी"
  }
]
````

### `api/data/policies.json`

````json
[
  {
    "id": "POL-BABU-2W",
    "user_id": "u_babu",
    "driving_licence_number": "MH03 20080022135",
    "driving_licence_holder_name": "Babu Khan",
    "driving_licence_valid_until": "2027-01-23",
    "vehicle_id": "v_babu_bike",
    "insurer_name": "HDFC ERGO General Insurance",
    "policy_number": "HDFC/2W/2026/0048213",
    "coverage_type": "comprehensive",
    "coverage_start_date": "2026-03-15",
    "coverage_end_date": "2027-03-14",
    "insured_declared_value_inr": 62000,
    "own_damage_premium_inr": 2400,
    "no_claim_bonus_pct": 35,
    "compulsory_deductible_inr": 100,
    "voluntary_deductible_inr": 500,
    "add_on_covers": [],
    "excluded_conditions": ["drunk_driving", "no_valid_dl", "commercial_use"],
    "required_documents": ["dl"],
    "cashless_garage_names": [
      "Govandi Bajaj Service Mumbai",
      "Chembur Bajaj Auto Care",
      "Kurla Two Wheeler Works",
      "Ghatkopar Bajaj Probiking"
    ]
  },
  {
    "id": "POL-BABU-4W",
    "user_id": "u_babu",
    "driving_licence_number": "MH03 20080022135",
    "driving_licence_holder_name": "Babu Khan",
    "driving_licence_valid_until": "2027-01-23",
    "vehicle_id": "v_babu_car",
    "insurer_name": "Bajaj General Insurance",
    "policy_number": "BJAZ/PC/2026/0072641",
    "coverage_type": "comprehensive",
    "coverage_start_date": "2026-04-01",
    "coverage_end_date": "2027-03-31",
    "insured_declared_value_inr": 780000,
    "own_damage_premium_inr": 15500,
    "no_claim_bonus_pct": 20,
    "compulsory_deductible_inr": 1000,
    "voluntary_deductible_inr": 0,
    "add_on_covers": ["zero_dep", "rsa"],
    "excluded_conditions": ["drunk_driving", "no_valid_dl", "commercial_use"],
    "required_documents": ["dl"],
    "cashless_garage_names": [
      "Chembur Maruti Arena Service",
      "Kurla Maruti Service Centre",
      "Vikhroli Auto Hub",
      "Sion Car Care Mumbai"
    ]
  },
  {
    "id": "POL-NADARAJAN-2W",
    "user_id": "u_nadarajan",
    "driving_licence_number": "PY01 19830001268",
    "driving_licence_holder_name": "Nadarajan G",
    "driving_licence_valid_until": "2028-09-05",
    "vehicle_id": "v_nadarajan_bike",
    "insurer_name": "Care Insurance",
    "policy_number": "CARE/2W/2026/0558120",
    "coverage_type": "comprehensive",
    "coverage_start_date": "2026-05-20",
    "coverage_end_date": "2027-05-19",
    "insured_declared_value_inr": 105000,
    "own_damage_premium_inr": 2800,
    "no_claim_bonus_pct": 25,
    "compulsory_deductible_inr": 100,
    "voluntary_deductible_inr": 0,
    "add_on_covers": ["zero_dep"],
    "excluded_conditions": ["drunk_driving", "no_valid_dl", "commercial_use"],
    "required_documents": ["dl"],
    "cashless_garage_names": [
      "Puducherry Yamaha Service Point",
      "Mudaliarpet Yamaha Care",
      "Lawspet Two Wheeler Clinic",
      "Villianur Bike Works"
    ]
  },
  {
    "id": "POL-NADARAJAN-4W",
    "user_id": "u_nadarajan",
    "driving_licence_number": "PY01 19830001268",
    "driving_licence_holder_name": "Nadarajan G",
    "driving_licence_valid_until": "2028-09-05",
    "vehicle_id": "v_nadarajan_car",
    "insurer_name": "HDFC ERGO General Insurance",
    "policy_number": "HDFC/PC/2026/1192874",
    "coverage_type": "comprehensive",
    "coverage_start_date": "2026-01-10",
    "coverage_end_date": "2027-01-09",
    "insured_declared_value_inr": 1150000,
    "own_damage_premium_inr": 18000,
    "no_claim_bonus_pct": 50,
    "compulsory_deductible_inr": 1000,
    "voluntary_deductible_inr": 0,
    "add_on_covers": ["ncb_protect", "rsa"],
    "excluded_conditions": ["drunk_driving", "no_valid_dl", "commercial_use"],
    "required_documents": ["dl"],
    "cashless_garage_names": [
      "MG Puducherry Service Centre",
      "Puducherry Auto Body Works",
      "ECR Car Care Puducherry",
      "Reddiarpalayam Motors"
    ]
  },
  {
    "id": "POL-SAHAYASAILA-2W",
    "user_id": "u_sahayasaila",
    "driving_licence_number": "TN21X20080011684",
    "driving_licence_holder_name": "Sahayasaila T",
    "driving_licence_valid_until": "2028-12-07",
    "vehicle_id": "v_sahayasaila_bike",
    "insurer_name": "Aditya Birla Insurance",
    "policy_number": "ABHI/2W/2026/0061905",
    "coverage_type": "comprehensive",
    "coverage_start_date": "2026-02-01",
    "coverage_end_date": "2027-01-31",
    "insured_declared_value_inr": 85000,
    "own_damage_premium_inr": 2600,
    "no_claim_bonus_pct": 45,
    "compulsory_deductible_inr": 100,
    "voluntary_deductible_inr": 0,
    "add_on_covers": [],
    "excluded_conditions": ["drunk_driving", "no_valid_dl", "commercial_use"],
    "required_documents": ["dl"],
    "cashless_garage_names": [
      "Porur Bajaj Service Chennai",
      "Poonamallee Bajaj Care",
      "Valasaravakkam Bike Point",
      "Vadapalani Two Wheeler Works"
    ]
  },
  {
    "id": "POL-SAHAYASAILA-4W",
    "user_id": "u_sahayasaila",
    "driving_licence_number": "TN21X20080011684",
    "driving_licence_holder_name": "Sahayasaila T",
    "driving_licence_valid_until": "2028-12-07",
    "vehicle_id": "v_sahayasaila_car",
    "insurer_name": "Bajaj General Insurance",
    "policy_number": "BJAZ/PC/2026/0072655",
    "coverage_type": "comprehensive",
    "coverage_start_date": "2026-04-01",
    "coverage_end_date": "2027-03-31",
    "insured_declared_value_inr": 260000,
    "own_damage_premium_inr": 6500,
    "no_claim_bonus_pct": 25,
    "compulsory_deductible_inr": 1000,
    "voluntary_deductible_inr": 0,
    "add_on_covers": ["rsa"],
    "excluded_conditions": ["drunk_driving", "no_valid_dl", "commercial_use"],
    "required_documents": ["dl"],
    "cashless_garage_names": [
      "Poonamallee Maruti Service Centre",
      "Chennai Auto Care Porur",
      "Guindy Maruti Arena Service",
      "Koyambedu Car Clinic"
    ]
  }
]
````

### `api/data/settlement_table.json`

````json
{
  "_comment": "key = claim_type|route|docs_complete -> [min_days, max_days]. Synthetic, tuned for the demo.",
  "own_damage|cashless|true": [7, 9],
  "own_damage|cashless|false": [12, 14],
  "own_damage|reimbursement|true": [10, 15],
  "own_damage|reimbursement|false": [18, 25],
  "third_party|cashless|true": [30, 90],
  "third_party|cashless|false": [45, 120],
  "third_party|reimbursement|true": [30, 90],
  "third_party|reimbursement|false": [45, 120],
  "both|cashless|true": [10, 14],
  "both|cashless|false": [15, 21],
  "both|reimbursement|true": [14, 21],
  "both|reimbursement|false": [21, 30]
}
````

### `api/data/users.json`

````json
{
  "users": [
    {
      "id": "u_babu",
      "full_name": "Babu Khan",
      "preferred_language": "hi",
      "phone_number": "+91-90000-11111"
    },
    {
      "id": "u_nadarajan",
      "full_name": "Nadarajan G",
      "preferred_language": "en",
      "phone_number": "+91-90000-22222"
    },
    {
      "id": "u_sahayasaila",
      "full_name": "Sahayasaila T",
      "preferred_language": "en",
      "phone_number": "+91-90000-33333"
    }
  ],
  "vehicles": [
    {
      "id": "v_babu_bike",
      "user_id": "u_babu",
      "vehicle_type": "2W",
      "vehicle_number": "MH49BH1512",
      "brand": "Bajaj",
      "model": "Pulsar 150",
      "manufacture_year": 2021
    },
    {
      "id": "v_babu_car",
      "user_id": "u_babu",
      "vehicle_type": "4W",
      "vehicle_number": "HR52H9260",
      "brand": "Maruti Suzuki",
      "model": "Ertiga ZXi",
      "manufacture_year": 2022
    },
    {
      "id": "v_nadarajan_bike",
      "user_id": "u_nadarajan",
      "vehicle_type": "2W",
      "vehicle_number": "TG153335",
      "brand": "Yamaha",
      "model": "MT-15",
      "manufacture_year": 2022
    },
    {
      "id": "v_nadarajan_car",
      "user_id": "u_nadarajan",
      "vehicle_type": "4W",
      "vehicle_number": "DL12TC0271",
      "brand": "MG",
      "model": "Hector Sharp",
      "manufacture_year": 2021
    },
    {
      "id": "v_sahayasaila_bike",
      "user_id": "u_sahayasaila",
      "vehicle_type": "2W",
      "vehicle_number": "TN12B5422",
      "brand": "Bajaj",
      "model": "Pulsar NS200",
      "manufacture_year": 2020
    },
    {
      "id": "v_sahayasaila_car",
      "user_id": "u_sahayasaila",
      "vehicle_type": "4W",
      "vehicle_number": "TN12C0455",
      "brand": "Maruti Suzuki",
      "model": "Swift Dzire LXi",
      "manufacture_year": 2015
    }
  ]
}
````

### `api/db/__init__.py`

````python
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
        missing = rules.unverified_kinds(
            rules.required_photo_kinds(policy), {r["evidence_type"] for r in verified}
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


async def cancel_claim(session_id: str) -> None:
    """Drop a claim before it is filed: the conversation is kept, marked CANCELLED, and its
    unfiled draft is removed so it can't be filed from the dashboard."""
    async with pool().acquire() as conn, conn.transaction():
        await conn.execute(
            "DELETE FROM claims WHERE session_id = $1 AND claim_status = 'draft'", session_id
        )
        await conn.execute(
            """UPDATE sessions SET conversation_stage = 'CANCELLED', updated_at = now()
               WHERE id = $1""",
            session_id,
        )


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


def _with_actions(row: asyncpg.Record) -> dict:
    """A claim row plus what the user may do with it, by the rules."""
    stage = row["conversation_stage"]
    return dict(row) | {
        "resumable": rules.is_resumable(stage),
        "deletable": rules.is_cancellable(stage),
    }


# Every claim is listed from its first message, not only once a draft exists.
_CLAIM_COLUMNS = """s.id AS session_id, s.conversation_stage, s.started_at,
       (SELECT max(m.sent_at) FROM messages m WHERE m.session_id = s.id) AS last_activity_at,
       (SELECT m.message_text FROM messages m WHERE m.session_id = s.id AND m.sender_role = 'user'
        ORDER BY m.id LIMIT 1) AS first_user_message,
       c.claim_status, c.claim_reference_number, c.claim_type, c.drafted_at, c.filed_at,
       c.expected_settlement_days_min, c.expected_settlement_days_max,
       v.brand, v.model, v.vehicle_number, p.insurer_name, p.policy_number,
       i.incident_date, i.description_english,
       i.estimated_repair_cost_inr, i.claim_recommendation, i.viability_assessment,
       coalesce((c.claim_form_data ->> 'expected_payout_inr')::int,
                (i.viability_assessment ->> 'insurer_payout_inr')::int) AS expected_payout_inr,
       (SELECT count(*) FROM claim_documents cd
        WHERE cd.session_id = s.id AND NOT cd.is_provided) AS documents_missing"""
_CLAIM_JOINS = """FROM sessions s
       LEFT JOIN incidents i ON i.session_id = s.id
       LEFT JOIN vehicles v ON v.id = i.vehicle_id
       LEFT JOIN policies p ON p.id = i.policy_id
       LEFT JOIN claims c ON c.session_id = s.id"""


async def user_claims(user_id: str) -> list[dict]:
    """Every claim conversation the user has started, most recently active first: in progress,
    closed or filed. Cancelled ones, and ones where the user never said anything, are left out."""
    rows = await pool().fetch(
        f"""SELECT {_CLAIM_COLUMNS}
            {_CLAIM_JOINS}
            WHERE s.user_id = $1 AND s.conversation_stage <> 'CANCELLED'
              AND EXISTS (SELECT 1 FROM messages m
                          WHERE m.session_id = s.id AND m.sender_role = 'user')
            ORDER BY last_activity_at DESC NULLS LAST""",
        user_id,
    )
    return [_with_actions(r) for r in rows]


async def delete_claim(session_id: str) -> None:
    """Delete a claim conversation and everything in it (messages, incident, photos, draft)."""
    await pool().execute("DELETE FROM sessions WHERE id = $1", session_id)


async def load_session(user_id: str, session_id: str) -> dict | None:
    """Everything saved for one conversation, for the agent to resume it (None if not theirs)."""
    async with pool().acquire() as conn:
        session = await conn.fetchrow(
            """SELECT conversation_stage, conversation_language FROM sessions
               WHERE id = $1 AND user_id = $2""",
            session_id,
            user_id,
        )
        if session is None:
            return None
        incident = await conn.fetchrow("SELECT * FROM incidents WHERE session_id = $1", session_id)
        evidence = await conn.fetch(
            """SELECT id, evidence_type, is_accepted, quality_issues, ai_confidence_score,
                      extracted_details, detail_mismatches
               FROM evidence WHERE session_id = $1 ORDER BY uploaded_at""",
            session_id,
        )
        claim = await conn.fetchrow(
            """SELECT claim_form_data, expected_settlement_days_min,
                      expected_settlement_days_max, claim_reference_number
               FROM claims WHERE session_id = $1""",
            session_id,
        )
        missing = await conn.fetch(
            """SELECT document_code FROM claim_documents
               WHERE session_id = $1 AND NOT is_provided""",
            session_id,
        )
        messages = await conn.fetch(
            "SELECT sender_role, message_text FROM messages WHERE session_id = $1 ORDER BY id",
            session_id,
        )
    return {
        "stage": session["conversation_stage"],
        "incident": dict(incident) if incident else None,
        "evidence": [dict(r) for r in evidence],
        "claim": dict(claim) if claim else None,
        "missing_docs": [r["document_code"] for r in missing],
        "messages": [dict(r) for r in messages],
    }


async def claim_detail(user_id: str, session_id: str) -> dict | None:
    """One claim with its checklist, verdict, photos and conversation (None if not the user's).
    The draft fields (form, checklist, settlement) are null until the claim reaches review."""
    async with pool().acquire() as conn:
        claim = await conn.fetchrow(
            f"""SELECT {_CLAIM_COLUMNS}, c.claim_form_data
                {_CLAIM_JOINS}
                WHERE s.id = $1 AND s.user_id = $2""",
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
        **_with_actions(claim),
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
````

### `api/db/schema.sql`

````sql
-- Applied on every backend start; every statement is idempotent.

-- Synthetic wallet, copied from data/*.json on startup (the JSON stays the source of truth).
CREATE TABLE IF NOT EXISTS users (
    id                  text PRIMARY KEY,
    full_name           text NOT NULL,
    preferred_language  text NOT NULL,
    phone_number        text NOT NULL
);

CREATE TABLE IF NOT EXISTS vehicles (
    id                text PRIMARY KEY,
    user_id           text NOT NULL REFERENCES users(id),
    vehicle_type      text NOT NULL,              -- '2W' | '4W'
    vehicle_number    text NOT NULL,              -- registration (number plate)
    brand             text NOT NULL,
    model             text NOT NULL,
    manufacture_year  int  NOT NULL
);

CREATE TABLE IF NOT EXISTS policies (
    id                          text PRIMARY KEY,
    user_id                     text NOT NULL REFERENCES users(id),
    vehicle_id                  text NOT NULL REFERENCES vehicles(id),
    insurer_name                text NOT NULL,
    policy_number               text NOT NULL,
    coverage_type               text NOT NULL,
    coverage_start_date         date NOT NULL,
    coverage_end_date           date NOT NULL,
    insured_declared_value_inr  int  NOT NULL,
    own_damage_premium_inr      int  NOT NULL,
    no_claim_bonus_pct          int  NOT NULL,
    compulsory_deductible_inr   int  NOT NULL,
    voluntary_deductible_inr    int  NOT NULL,
    add_on_covers               jsonb NOT NULL DEFAULT '[]',
    excluded_conditions         jsonb NOT NULL DEFAULT '[]',
    cashless_garage_names       jsonb NOT NULL DEFAULT '[]',
    -- Driving licence submitted when the policy was issued; a claim's DL upload must match it.
    driving_licence_number       text NOT NULL,
    driving_licence_holder_name  text NOT NULL,
    driving_licence_valid_until  date NOT NULL
);

-- Every document an insurer can ask for (copied from data/documents.json on startup).
-- Codes match services/rules.py and evidence types.
CREATE TABLE IF NOT EXISTS documents (
    document_code  text PRIMARY KEY,
    name_english   text NOT NULL,
    name_hindi     text NOT NULL
);

-- Documents each policy asks for on every claim (copied from data/policies.json on startup).
CREATE TABLE IF NOT EXISTS policy_required_documents (
    policy_id      text NOT NULL REFERENCES policies(id) ON DELETE CASCADE,
    document_code  text NOT NULL REFERENCES documents(document_code),
    PRIMARY KEY (policy_id, document_code)
);

-- One row per WebSocket conversation.
CREATE TABLE IF NOT EXISTS sessions (
    id                     text PRIMARY KEY,
    user_id                text NOT NULL REFERENCES users(id),
    conversation_stage     text NOT NULL,
    conversation_language  text NOT NULL,
    started_at             timestamptz NOT NULL DEFAULT now(),
    updated_at             timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
    id            bigserial PRIMARY KEY,
    session_id    text NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    sender_role   text NOT NULL,              -- 'user' | 'bot'
    message_text  text NOT NULL,
    sent_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS incidents (
    session_id                    text PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    user_id                       text NOT NULL REFERENCES users(id),
    vehicle_id                    text REFERENCES vehicles(id),
    policy_id                     text REFERENCES policies(id),
    incident_date                 date,
    incident_location             text,
    description_english           text,
    description_user_language     text,
    third_party_involved          boolean NOT NULL DEFAULT false,
    third_party_property_damaged  boolean NOT NULL DEFAULT false,
    anyone_injured                boolean NOT NULL DEFAULT false,
    estimated_repair_cost_inr     int,
    garage_name                   text,
    police_report_filed           boolean,
    risk_flags                    jsonb NOT NULL DEFAULT '[]',
    claim_recommendation          text,
    viability_assessment          jsonb,
    updated_at                    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS evidence (
    id                   text PRIMARY KEY,
    session_id           text NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    evidence_type        text NOT NULL,
    is_accepted          boolean NOT NULL,
    quality_issues       jsonb NOT NULL DEFAULT '[]',
    ai_confidence_score  real NOT NULL DEFAULT 0,
    extracted_details    jsonb NOT NULL DEFAULT '{}',  -- plate / DL fields read from the photo
    detail_mismatches    jsonb NOT NULL DEFAULT '[]',  -- where they differ from the records
    uploaded_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS claims (
    session_id                     text PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    policy_id                      text NOT NULL REFERENCES policies(id),
    claim_type                     text NOT NULL,
    claim_status                   text NOT NULL DEFAULT 'draft',   -- 'draft' | 'filed'
    claim_form_data                jsonb NOT NULL,
    expected_settlement_days_min   int,
    expected_settlement_days_max   int,
    claim_reference_number         text UNIQUE,
    drafted_at                     timestamptz NOT NULL DEFAULT now(),
    filed_at                       timestamptz
);

-- One claim's document checklist: every document it needs, and whether we already have it.
CREATE TABLE IF NOT EXISTS claim_documents (
    session_id     text NOT NULL REFERENCES claims(session_id) ON DELETE CASCADE,
    document_code  text NOT NULL REFERENCES documents(document_code),
    is_provided    boolean NOT NULL DEFAULT false,
    PRIMARY KEY (session_id, document_code)
);
````

### `api/main.py`

````python
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
    if claim["claim_status"] is None:
        raise HTTPException(409, "This claim isn't ready to file yet. Continue it in chat.")
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


@app.delete("/users/{user_id}/claims/{session_id}")
async def delete_claim(user_id: str, session_id: str) -> dict:
    """Delete a claim the user no longer wants, with its whole conversation (not once filed)."""
    _known_user(user_id)
    claim = await db.claim_detail(user_id, session_id)
    if claim is None:
        raise HTTPException(404, "Claim not found")
    if not claim["deletable"]:
        raise HTTPException(409, "A filed claim is with the insurer and can't be deleted")
    await db.delete_claim(session_id)
    return {"deleted": session_id}


@app.post("/livekit/token")
async def livekit_token(user_id: str, language: str = "hi", session_id: str | None = None) -> dict:
    """Credentials for a claim conversation: a fresh room with the claim agent in it. With
    session_id, the agent picks that claim up where it was left."""
    _known_user(user_id)
    attributes = {"user_id": user_id, "language": "en" if language == "en" else "hi"}
    if session_id:
        claim = await db.claim_detail(user_id, session_id)
        if claim is None or not claim["resumable"]:
            raise HTTPException(409, "This claim can't be continued")
        attributes["resume_session_id"] = session_id
    user = load_wallet().users[user_id]
    room = f"claim-{user_id}-{uuid.uuid4().hex[:8]}"
    token = (
        api.AccessToken()  # LIVEKIT_API_KEY / LIVEKIT_API_SECRET
        .with_identity(user_id)
        .with_name(user.full_name)
        # the agent reads who is calling, the language, and any claim to resume from these
        .with_attributes(attributes)
        .with_grants(api.VideoGrants(room_join=True, room=room))
        .with_room_config(RoomConfiguration(agents=[RoomAgentDispatch(agent_name=AGENT_NAME)]))
        .to_jwt()
    )
    return {"server_url": os.environ["LIVEKIT_URL"], "participant_token": token}
````

### `api/models.py`

````python
"""Pydantic v2 models shared by the API, voice agent and services. See README §5."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Language = Literal["hi", "en"]
VehicleType = Literal["2W", "4W"]
CoverType = Literal["comprehensive", "third_party_only"]
NcbPct = Literal[0, 20, 25, 35, 45, 50]
Addon = Literal["zero_dep", "ncb_protect", "engine_protect", "rsa", "consumables"]
ClaimType = Literal["own_damage", "third_party", "both"]
Verdict = Literal["claim", "dont_claim", "borderline", "not_covered"]
EvidenceKind = Literal[
    "damage_wide", "damage_close", "number_plate", "odometer", "garage_estimate", "dl", "rc"
]
SessionState = Literal[
    "INTAKE",
    "MATCH_POLICY",
    "VIABILITY",
    "EVIDENCE",
    "FORM_REVIEW",
    "FILED",
    "NO_COVER",
    "ADVISED_NO_CLAIM",
    "CANCELLED",
]


class Document(BaseModel):
    document_code: str
    name_english: str
    name_hindi: str


class User(BaseModel):
    id: str
    full_name: str
    preferred_language: Language
    phone_number: str


class Vehicle(BaseModel):
    id: str
    user_id: str
    vehicle_type: VehicleType
    vehicle_number: str  # registration (number plate)
    brand: str
    model: str
    manufacture_year: int


class Policy(BaseModel):
    id: str
    user_id: str
    vehicle_id: str
    insurer_name: str
    policy_number: str
    coverage_type: CoverType
    coverage_start_date: date
    coverage_end_date: date
    insured_declared_value_inr: int
    own_damage_premium_inr: int
    no_claim_bonus_pct: NcbPct
    compulsory_deductible_inr: int
    voluntary_deductible_inr: int = 0
    add_on_covers: list[Addon] = Field(default_factory=list)
    excluded_conditions: list[str] = Field(default_factory=list)
    required_documents: list[str] = Field(default_factory=list)
    cashless_garage_names: list[str] = Field(default_factory=list)
    # Driving licence submitted at policy issuance; the claim's DL upload must match it.
    driving_licence_number: str
    driving_licence_holder_name: str
    driving_licence_valid_until: date


class Incident(BaseModel):
    id: str | None = None
    session_id: str | None = None
    user_id: str | None = None
    vehicle_id: str | None = None
    incident_date: date | None = None
    incident_location: str | None = None
    description_english: str | None = None
    description_user_language: str | None = None
    third_party_involved: bool = False
    third_party_property_damaged: bool = False
    anyone_injured: bool = False
    estimated_repair_cost_inr: int | None = None
    garage_estimate_uploaded: bool = False
    police_report_filed: bool | None = None
    garage_name: str | None = None
    # Exclusion / FIR triggers: drunk_driving, no_valid_dl, commercial_use, theft, hit_and_run
    risk_flags: list[str] = Field(default_factory=list)


class Viability(BaseModel):
    insurer_payout_inr: int
    deductible_inr: int
    depreciation_inr: int
    ncb_loss_year1_inr: int
    ncb_loss_total_inr: int
    verdict: Verdict
    reasons: list[str]
    ncb_protected: bool
    estimate_pending: bool = False
    # Damage estimate at which payout equals the NCB loss; above this, claiming starts to pay.
    breakeven_estimate_inr: int | None = None


class Settlement(BaseModel):
    min_days: int
    max_days: int
    route: Literal["cashless", "reimbursement"]
    docs_complete: bool


class Evidence(BaseModel):
    id: str
    claim_id: str | None = None
    evidence_type: EvidenceKind
    file_path: str
    is_accepted: bool
    quality_issues: list[str] = Field(default_factory=list)
    ai_confidence_score: float = 0.0
    extracted_details: dict = Field(default_factory=dict)  # plate / DL fields read from the photo
    detail_mismatches: list[str] = Field(default_factory=list)  # codes from rules.verify_details


class Claim(BaseModel):
    id: str
    incident_id: str
    policy_id: str
    claim_type: ClaimType
    claim_status: Literal["draft", "filed"] = "draft"
    claim_form_data: dict = Field(default_factory=dict)
    missing_docs: list[str] = Field(default_factory=list)
    expected_settlement_days_min: int | None = None
    expected_settlement_days_max: int | None = None
    claim_reference_number: str | None = None


class Session(BaseModel):
    id: str
    user_id: str
    conversation_stage: SessionState = "INTAKE"
    conversation_language: Language
    history: list[dict] = Field(default_factory=list)
    started_at: datetime
````

### `api/pyproject.toml`

````toml
[project]
name = "claim-karo-api"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
````

### `api/requirements.txt`

````text
anthropic>=1.0
fastapi>=0.115
uvicorn[standard]>=0.30
httpx>=0.27
python-dotenv>=1.0
pydantic>=2.7
asyncpg>=0.30
pytest>=8
ruff>=0.5
livekit-agents==1.8.10
livekit-plugins-anthropic==1.8.10
livekit-plugins-sarvam==1.8.10
livekit-plugins-silero==1.8.10
livekit-plugins-turn-detector==1.8.10
livekit-api==1.2.2
````

### `api/seed.py`

````python
"""Load the synthetic wallet (users, vehicles, policies, documents) from data/*.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from models import Document, Policy, User, Vehicle

DATA_DIR = Path(__file__).resolve().parent / "data"


class Wallet(BaseModel):
    users: dict[str, User]
    vehicles: dict[str, Vehicle]
    policies: dict[str, Policy]
    documents: dict[str, Document]

    def vehicles_for(self, user_id: str) -> list[Vehicle]:
        return [v for v in self.vehicles.values() if v.user_id == user_id]

    def policies_for(self, user_id: str) -> list[Policy]:
        return [p for p in self.policies.values() if p.user_id == user_id]

    def document_names(self, codes: list[str]) -> list[str]:
        return [self.documents[c].name_english if c in self.documents else c for c in codes]


@lru_cache(maxsize=1)
def load_wallet(data_dir: Path = DATA_DIR) -> Wallet:
    users_raw = json.loads((data_dir / "users.json").read_text(encoding="utf-8"))
    policies_raw = json.loads((data_dir / "policies.json").read_text(encoding="utf-8"))
    documents_raw = json.loads((data_dir / "documents.json").read_text(encoding="utf-8"))
    return Wallet(
        users={u["id"]: User(**u) for u in users_raw["users"]},
        vehicles={v["id"]: Vehicle(**v) for v in users_raw["vehicles"]},
        policies={p["id"]: Policy(**p) for p in policies_raw},
        documents={d["document_code"]: Document(**d) for d in documents_raw},
    )
````

### `api/services/__init__.py`

*(empty file)*

### `api/services/claude.py`

````python
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
````

### `api/services/rules.py`

````python
"""Deterministic claim rules. Pure functions, no I/O. All amounts are integer INR.

Rules decide, Claude explains: nothing in here calls a model, and nothing outside here
computes money. See README §6 for the spec these functions implement.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date

from models import ClaimType, Evidence, Incident, Policy, Vehicle, Viability

NCB_LADDER: list[int] = [0, 20, 25, 35, 45, 50]
# NCB you climb back to in renewal years 2 and 3 after a claim resets you to 0%.
POST_CLAIM_LADDER: list[int] = [20, 25]
BORDERLINE_MULTIPLIER = 1.25

# (max vehicle age in months, exclusive) -> blended depreciation %
DEPRECIATION_BY_AGE: list[tuple[int, int]] = [
    (6, 0),
    (12, 5),
    (24, 10),
    (36, 15),
    (48, 25),
    (60, 35),
]
DEPRECIATION_MAX_PCT = 45

# Documents the wallet already holds, so the user never has to upload them.
WALLET_DOCS: frozenset[str] = frozenset({"policy_copy", "rc"})
FIR_FLAGS: frozenset[str] = frozenset({"theft", "hit_and_run"})
# Uploads whose details must match the records before a claim can be filed.
VERIFIED_KINDS: tuple[str, ...] = ("damage_wide", "dl")


def _has_own_damage(incident: Incident) -> bool:
    # An unknown estimate still means the user's own vehicle was damaged.
    return incident.estimated_repair_cost_inr != 0 or "theft" in incident.risk_flags


def _has_third_party_liability(incident: Incident) -> bool:
    return incident.third_party_property_damaged or incident.anyone_injured


def claim_type(incident: Incident, policy: Policy) -> ClaimType | None:
    own = _has_own_damage(incident) and policy.coverage_type == "comprehensive"
    tp = _has_third_party_liability(incident)
    if own and tp:
        return "both"
    if own:
        return "own_damage"
    if tp:
        return "third_party"
    return None


def missing_incident_facts(incident: Incident, estimate_unknown: bool) -> list[str]:
    """What the conversation still has to find out before the verdict can be worked out."""
    known = {
        "vehicle": incident.vehicle_id is not None,
        "date": incident.incident_date is not None,
        "what happened": bool(incident.description_english),
        "damage estimate": incident.estimated_repair_cost_inr is not None or estimate_unknown,
    }
    return [fact for fact, ok in known.items() if not ok]


def is_cancellable(stage: str) -> bool:
    """A claim can be dropped (or deleted) at any step until it is filed; then it is with the
    insurer."""
    return stage != "FILED"


def is_resumable(stage: str) -> bool:
    """A claim can be picked up again while it still has a step left to do."""
    return stage in ("INTAKE", "VIABILITY", "EVIDENCE", "FORM_REVIEW")


def deductible(policy: Policy) -> int:
    return policy.compulsory_deductible_inr + policy.voluntary_deductible_inr


def is_active(policy: Policy, on: date) -> bool:
    return policy.coverage_start_date <= on <= policy.coverage_end_date


def match_policy(incident: Incident, policies: list[Policy]) -> Policy | None:
    if incident.vehicle_id is None or incident.incident_date is None:
        return None
    for policy in policies:
        if policy.vehicle_id != incident.vehicle_id:
            continue
        if not is_active(policy, incident.incident_date):
            continue
        if claim_type(incident, policy) is None:
            continue
        return policy
    return None


def fir_required(incident: Incident) -> bool:
    return _has_third_party_liability(incident) or bool(FIR_FLAGS & set(incident.risk_flags))


def is_cashless(incident: Incident, policy: Policy) -> bool:
    if not incident.garage_name:
        return False
    wanted = incident.garage_name.strip().casefold()
    return any(g.strip().casefold() == wanted for g in policy.cashless_garage_names)


def vehicle_age_months(vehicle: Vehicle, as_of: date) -> int:
    # Only the model year is known, so age is measured from 1 Jan of that year.
    return max(0, (as_of.year - vehicle.manufacture_year) * 12 + as_of.month - 1)


def depreciation_pct(age_months: int) -> int:
    for max_age, pct in DEPRECIATION_BY_AGE:
        if age_months < max_age:
            return pct
    return DEPRECIATION_MAX_PCT


def next_ncb(pct: int) -> int:
    idx = NCB_LADDER.index(pct)
    return NCB_LADDER[min(idx + 1, len(NCB_LADDER) - 1)]


def ncb_loss(policy: Policy) -> tuple[int, int]:
    """Return (year-1 loss, 3-year total loss) from filing an OD claim now.

    Year 1 values the NCB the user currently holds (README §1). Years 2-3 add the
    forfeited step-up: the no-claim ladder continuing from today vs climbing back from 0.
    """
    if "ncb_protect" in policy.add_on_covers:
        return 0, 0
    premium = policy.own_damage_premium_inr
    year1 = premium * policy.no_claim_bonus_pct // 100
    total = year1
    no_claim = policy.no_claim_bonus_pct
    for after_claim in POST_CLAIM_LADDER:
        no_claim = next_ncb(no_claim)
        total += premium * max(0, no_claim - after_claim) // 100
    return year1, total


def _breakeven_estimate(deductible: int, dep_pct: int, ncb_loss_total: int) -> int:
    # Smallest estimate where payout > ncb_loss_total: est * (100 - dep) / 100 - ded > loss.
    return (ncb_loss_total + deductible) * 100 // (100 - dep_pct) + 1


def viability(
    incident: Incident, policy: Policy, vehicle: Vehicle, as_of: date | None = None
) -> Viability:
    policy_deductible = deductible(policy)
    ncb_protected = "ncb_protect" in policy.add_on_covers
    reasons: list[str] = []

    def result(verdict, payout=0, depreciation=0, y1=0, total=0, **extra) -> Viability:
        return Viability(
            insurer_payout_inr=payout,
            deductible_inr=policy_deductible,
            depreciation_inr=depreciation,
            ncb_loss_year1_inr=y1,
            ncb_loss_total_inr=total,
            verdict=verdict,
            reasons=reasons,
            ncb_protected=ncb_protected,
            **extra,
        )

    excluded = [f for f in incident.risk_flags if f in policy.excluded_conditions]
    if excluded:
        reasons.extend(f"EXCLUSION_{f.upper()}" for f in excluded)
        return result("not_covered")

    ctype = claim_type(incident, policy)
    if ctype is None:
        reasons.append("NO_APPLICABLE_COVER")
        return result("not_covered")
    if fir_required(incident):
        reasons.append("FIR_REQUIRED")
    if ctype == "third_party":
        # Insurer pays the third party directly; there is no own-damage payout to weigh.
        reasons.append("THIRD_PARTY_LIABILITY")
        if _has_own_damage(incident):
            reasons.append("OWN_DAMAGE_NOT_COVERED")
        return result("claim")
    if ctype == "both":
        reasons.append("THIRD_PARTY_ALSO_INVOLVED")

    y1, total = ncb_loss(policy)
    if ncb_protected:
        reasons.append("NCB_PROTECTED")

    as_of = as_of or incident.incident_date or date.today()
    zero_dep = "zero_dep" in policy.add_on_covers
    dep_pct = 0 if zero_dep else depreciation_pct(vehicle_age_months(vehicle, as_of))
    breakeven = _breakeven_estimate(policy_deductible, dep_pct, total)

    if incident.estimated_repair_cost_inr is None:
        reasons.append("ESTIMATE_PENDING")
        return result(
            "borderline",
            y1=y1,
            total=total,
            estimate_pending=True,
            breakeven_estimate_inr=breakeven,
        )

    assessed = incident.estimated_repair_cost_inr
    if assessed > policy.insured_declared_value_inr:
        assessed = policy.insured_declared_value_inr
        reasons.append("ESTIMATE_CAPPED_AT_IDV")
    depreciation = assessed * dep_pct // 100
    if zero_dep:
        reasons.append("ZERO_DEP_APPLIED")
    elif depreciation:
        reasons.append("DEPRECIATION_APPLIED")
    payout = max(0, assessed - depreciation - policy_deductible)

    if payout == 0:
        reasons.append("PAYOUT_BELOW_DEDUCTIBLE")
        verdict = "dont_claim"
    elif payout <= total:
        reasons.append("NCB_LOSS_EXCEEDS_PAYOUT")
        verdict = "dont_claim"
    elif payout <= total * BORDERLINE_MULTIPLIER:
        reasons.append("PAYOUT_CLOSE_TO_NCB_LOSS")
        verdict = "borderline"
    else:
        reasons.append("PAYOUT_EXCEEDS_NCB_LOSS")
        verdict = "claim"

    return result(
        verdict,
        payout=payout,
        depreciation=depreciation,
        y1=y1,
        total=total,
        breakeven_estimate_inr=breakeven,
    )


def what_if(
    incident: Incident,
    estimated_repair_cost_inr: int,
    policies: list[Policy],
    vehicles: dict[str, Vehicle],
    today: date,
) -> Viability | None:
    """The verdict for a different repair cost, leaving the real incident unchanged.
    None if no policy covers it. An incident with no date yet is priced as of today."""
    hypothetical = incident.model_copy(
        update={
            "estimated_repair_cost_inr": estimated_repair_cost_inr,
            "incident_date": incident.incident_date or today,
        }
    )
    policy = match_policy(hypothetical, policies)
    if policy is None:
        return None
    return viability(hypothetical, policy, vehicles[policy.vehicle_id])


def policy_summary(
    policy: Policy, vehicle: Vehicle, document_names: list[str], today: date
) -> dict:
    """What the user can be told about one of their policies."""
    return {
        "policy_id": policy.id,
        "insurer": policy.insurer_name,
        "policy_number": policy.policy_number,
        "vehicle": f"{vehicle.brand} {vehicle.model} ({vehicle.vehicle_number})",
        "cover": policy.coverage_type,
        "valid": f"{policy.coverage_start_date} to {policy.coverage_end_date}",
        "active_today": is_active(policy, today),
        "insured_declared_value_inr": policy.insured_declared_value_inr,
        "no_claim_bonus_pct": policy.no_claim_bonus_pct,
        "deductible_inr": deductible(policy),
        "add_on_covers": policy.add_on_covers,
        "not_covered_if": policy.excluded_conditions,
        "documents_for_a_claim": document_names,
        "cashless_garages": policy.cashless_garage_names,
    }


def required_documents(incident: Incident, policy: Policy) -> list[str]:
    """Every document this claim needs: the policy's list, plus an FIR if the incident needs one."""
    required = list(policy.required_documents)
    if fir_required(incident) and "fir" not in required:
        required.append("fir")
    return list(dict.fromkeys(required))


def missing_documents(incident: Incident, policy: Policy, evidence: list[Evidence]) -> list[str]:
    have = {e.evidence_type for e in evidence if e.is_accepted} | WALLET_DOCS
    if incident.garage_estimate_uploaded or is_cashless(incident, policy):
        have.add("garage_estimate")
    if incident.police_report_filed:
        have.add("fir")

    return [doc for doc in required_documents(incident, policy) if doc not in have]


def required_photo_kinds(policy: Policy) -> list[str]:
    # damage_wide is read for the number plate too, so no separate number_plate shot.
    kinds = ["damage_wide"]
    if "dl" in policy.required_documents:
        kinds.append("dl")
    return kinds


def _normalise_id(text: str) -> str:
    # "UP16 AB-4521" and "up16ab4521" are the same registration / licence number.
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def _name_tokens(name: str) -> set[str]:
    return set(re.sub(r"[^a-z ]", " ", name.casefold()).split())


def verify_details(
    kind: str, details: dict, vehicle: Vehicle, policy: Policy, incident: Incident
) -> list[str]:
    """Mismatch codes between what was read off an upload and the records; [] if all match.

    damage_wide: the number plate must be the insured vehicle's registration.
    dl: the licence must be the one submitted at policy issuance, valid on the incident date.
    """
    if kind == "damage_wide":
        plate = details.get("number_plate_text")
        if not plate:
            return ["PLATE_NOT_READABLE"]
        if _normalise_id(plate) != _normalise_id(vehicle.vehicle_number):
            return ["PLATE_MISMATCH"]
        return []

    if kind == "dl":
        number = details.get("licence_number")
        if not number:
            return ["DL_NOT_READABLE"]
        codes = []
        if _normalise_id(number) != _normalise_id(policy.driving_licence_number):
            codes.append("DL_NUMBER_MISMATCH")
        # Word order and middle names vary between documents, so one name may contain the other.
        read = _name_tokens(details.get("licence_holder_name") or "")
        on_file = _name_tokens(policy.driving_licence_holder_name)
        if not read or not (read <= on_file or on_file <= read):
            codes.append("DL_NAME_MISMATCH")
        valid_until = details.get("licence_valid_until")
        if not valid_until:
            codes.append("DL_VALIDITY_NOT_READABLE")
        elif date.fromisoformat(valid_until) < (incident.incident_date or date.today()):
            codes.append("DL_EXPIRED_ON_INCIDENT_DATE")
        return codes

    return []


def unverified_kinds(required_kinds: Iterable[str], verified: set[str]) -> list[str]:
    """Required uploads still lacking an accepted copy whose details match the records."""
    return [k for k in required_kinds if k in VERIFIED_KINDS and k not in verified]
````

### `api/services/settlement.py`

````python
"""Settlement-time estimate from a static lookup table (data/settlement_table.json)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from models import ClaimType, Settlement

TABLE_PATH = Path(__file__).resolve().parent.parent / "data" / "settlement_table.json"


@lru_cache(maxsize=1)
def load_table(path: Path = TABLE_PATH) -> dict[str, list[int]]:
    with path.open(encoding="utf-8") as f:
        return {k: v for k, v in json.load(f).items() if not k.startswith("_")}


def estimate(claim_type: ClaimType, cashless: bool, docs_complete: bool) -> Settlement:
    route = "cashless" if cashless else "reimbursement"
    key = f"{claim_type}|{route}|{str(docs_complete).lower()}"
    min_days, max_days = load_table()[key]
    return Settlement(
        min_days=min_days, max_days=max_days, route=route, docs_complete=docs_complete
    )
````

### `api/static/audio/.gitkeep`

*(empty file)*

### `web/.env.example`

````text
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
NEXT_PUBLIC_API_URL=http://localhost:8000
````

### `web/app/globals.css`

````css
@import "tailwindcss";

/* Paytm-inspired palette: deep navy + cyan on a soft grey canvas */
@theme {
  --color-navy: #002e6e;
  --color-navy-soft: #e8eef7;
  --color-sky: #00baf2;
  --color-sky-dark: #0098c7;
  --color-sky-soft: #e6f8fe;
  --color-canvas: #f4f6fa;
  --color-ink: #101828;
  --color-muted: #667085;
  --color-line: #e4e7ec;
  --font-sans: var(--font-inter), "Noto Sans Devanagari", ui-sans-serif, system-ui, sans-serif;
}

body {
  background: var(--color-canvas);
  color: var(--color-ink);
}

@keyframes fadein {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: none; }
}
.animate-fadein { animation: fadein 0.35s ease both; }
````

### `web/app/layout.tsx`

````tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Claim Karo",
  description: "Motor insurance claims in conversation",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
````

### `web/app/page.tsx`

````tsx
"use client";

import { RoomAudioRenderer, SessionProvider, useSession } from "@livekit/components-react";
import { TokenSource } from "livekit-client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Chat from "@/components/Chat";
import ClaimPanel from "@/components/ClaimPanel";
import Dashboard from "@/components/Dashboard";
import Login from "@/components/Login";
import { fetchClaim, fetchLiveKitToken, type Profile } from "@/lib/api";
import { useClaim, type Language, type Message } from "@/lib/useClaim";

type SessionProps = {
  profile: Profile;
  language: Language;
  resumeId: string | null; // continue this claim instead of starting a new one
  onSessionId: (id: string) => void;
};

// One claim conversation = one LiveKit room with the claim agent in it.
function Session({ profile, language, resumeId, onSessionId }: SessionProps) {
  const tokenSource = useMemo(
    () => TokenSource.custom(() => fetchLiveKitToken(profile.id, language, resumeId)),
    [profile.id, language, resumeId],
  );
  const session = useSession(tokenSource);
  const { start, end } = session;

  useEffect(() => {
    // the mic stays off until the user taps it
    start({ tracks: { microphone: { enabled: false } } }).catch(() => {});
    return () => {
      end();
    };
  }, [start, end]);

  return (
    <SessionProvider session={session}>
      <RoomAudioRenderer />
      <Conversation profile={profile} language={language} resumeId={resumeId} onSessionId={onSessionId} />
    </SessionProvider>
  );
}

function Conversation({ profile, language, resumeId, onSessionId }: SessionProps) {
  // a resumed claim shows what was said before, above the live conversation
  const [history, setHistory] = useState<Message[]>([]);
  useEffect(() => {
    if (!resumeId) return;
    let live = true;
    fetchClaim(profile.id, resumeId)
      .then((c) => {
        if (!live) return;
        setHistory(
          c.messages.map((m, i) => ({ id: `history-${i}`, role: m.sender_role, text: m.message_text })),
        );
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [profile.id, resumeId]);

  const { state, sendText, sendPhoto, decide, setMic } = useClaim(language, history);
  useEffect(() => {
    if (state.sessionId) onSessionId(state.sessionId);
  }, [state.sessionId, onSessionId]);

  return (
    <div className="grid gap-4 py-4 md:h-[calc(100dvh-4rem)] md:grid-cols-[1fr_380px]">
      <Chat state={state} onText={sendText} onPhoto={sendPhoto} onDecide={decide} setMic={setMic} />
      <ClaimPanel state={state} profile={profile} onFile={() => decide("file")} />
    </div>
  );
}

const maskPhone = (phone: string) => {
  const digits = phone.replace(/\D/g, "").slice(-10);
  return `+91 ••••• ${digits.slice(-5)}`;
};

const initials = (name: string) =>
  name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

// Name and phone behind the avatar, with log out; opens on hover, or on tap / keyboard focus.
function ProfileMenu({ profile, onLogout }: { profile: Profile; onLogout: () => void }) {
  return (
    <div className="group relative">
      <button
        className="flex items-center gap-2 rounded-full p-0.5 pr-2 transition hover:bg-canvas focus:bg-canvas focus:outline-none"
        aria-haspopup="menu"
        aria-label={`Account: ${profile.full_name}`}
      >
        <span className="grid h-8 w-8 place-items-center rounded-full bg-navy text-xs font-semibold text-white">
          {initials(profile.full_name)}
        </span>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-muted transition group-hover:rotate-180 group-focus-within:rotate-180">
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>
      {/* pt-2 bridges the gap so the menu stays open while the pointer moves onto it */}
      <div className="invisible absolute right-0 top-full z-20 pt-2 opacity-0 transition group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100">
        <div role="menu" className="w-60 overflow-hidden rounded-2xl border border-line bg-white shadow-lg">
          <div className="flex items-center gap-3 px-4 py-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-sky-soft text-sm font-semibold text-navy">
              {initials(profile.full_name)}
            </span>
            <div className="min-w-0 leading-tight">
              <p className="truncate text-sm font-semibold text-ink">{profile.full_name}</p>
              <p className="text-xs text-muted">{maskPhone(profile.phone_number)}</p>
            </div>
          </div>
          <div className="border-t border-line p-1.5">
            <button
              role="menuitem"
              onClick={onLogout}
              className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-sm text-ink transition hover:bg-red-50 hover:text-red-700"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
              </svg>
              Log out
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

type OpenChat = { run: number; resumeId: string | null };

export default function Home() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [language, setLanguage] = useState<Language>("hi");
  const [chat, setChat] = useState<OpenChat | null>(null); // null: the dashboard is showing
  const currentSession = useRef<string | null>(null); // the claim the open chat is on

  function login(p: Profile) {
    setProfile(p);
    setLanguage(p.preferred_language);
    setChat(null);
  }

  function openChat(resumeId: string | null) {
    currentSession.current = resumeId;
    setChat((c) => ({ run: (c?.run ?? 0) + 1, resumeId }));
  }

  function switchLanguage(l: Language) {
    setLanguage(l);
    // reconnecting in the new language carries on with the same claim
    if (chat) setChat({ run: chat.run + 1, resumeId: currentSession.current });
  }

  const onSessionId = useCallback((id: string) => {
    currentSession.current = id;
  }, []);

  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-10 border-b border-line bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-4 px-4">
          <button onClick={() => profile && setChat(null)} className="flex items-center gap-2" aria-label="Claim Karo home">
            <div className="grid h-8 w-8 place-items-center rounded-lg bg-navy text-sm font-bold text-white">CK</div>
            <span className="text-lg font-semibold tracking-tight text-navy">
              Claim<span className="text-sky">Karo</span>
            </span>
          </button>

          {profile && (
            <>
              <nav className="ml-2 hidden items-center gap-1 sm:flex" aria-label="Main">
                {[
                  { label: "My claims", active: !chat, onClick: () => setChat(null) },
                  ...(chat ? [{ label: chat.resumeId ? "Continuing claim" : "New claim", active: true, onClick: () => {} }] : []),
                ].map((item) => (
                  <button
                    key={item.label}
                    onClick={item.onClick}
                    aria-current={item.active ? "page" : undefined}
                    className={`relative rounded-lg px-3 py-2 text-sm font-medium transition ${
                      item.active ? "text-navy" : "text-muted hover:bg-canvas hover:text-ink"
                    }`}
                  >
                    {item.label}
                    {item.active && <span className="absolute inset-x-3 -bottom-[13px] h-0.5 rounded-full bg-sky" />}
                  </button>
                ))}
              </nav>

              <div className="ml-auto flex items-center gap-2 sm:gap-3">
                {chat && (
                  <button
                    onClick={() => setChat(null)}
                    className="rounded-full border border-line px-3 py-1.5 text-xs font-medium text-ink transition hover:border-sky sm:hidden"
                  >
                    My claims
                  </button>
                )}
                <div className="flex rounded-full bg-canvas p-0.5 text-xs font-medium" role="group" aria-label="Language">
                  {(["hi", "en"] as const).map((l) => (
                    <button
                      key={l}
                      onClick={() => switchLanguage(l)}
                      aria-pressed={language === l}
                      className={`rounded-full px-3 py-1 transition ${
                        language === l ? "bg-white text-navy shadow-sm" : "text-muted hover:text-ink"
                      }`}
                    >
                      {l === "hi" ? "हिंदी" : "EN"}
                    </button>
                  ))}
                </div>
                {!chat && (
                  <button
                    onClick={() => openChat(null)}
                    className="hidden items-center gap-1.5 rounded-full bg-sky px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-sky-dark sm:flex"
                  >
                    <span className="text-base leading-none">+</span> New claim
                  </button>
                )}
                <ProfileMenu profile={profile} onLogout={() => setProfile(null)} />
              </div>
            </>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4">
        {profile && chat ? (
          <Session
            key={`${profile.id}-${chat.run}`}
            profile={profile}
            language={language}
            resumeId={chat.resumeId}
            onSessionId={onSessionId}
          />
        ) : profile ? (
          <Dashboard
            profile={profile}
            language={language}
            onNewClaim={() => openChat(null)}
            onResume={(id) => openChat(id)}
          />
        ) : (
          <Login onLogin={login} />
        )}
      </main>
    </div>
  );
}
````

### `web/components/Chat.tsx`

````tsx
"use client";

import { useLayoutEffect, useRef, useState } from "react";
import type { ClaimState } from "@/lib/useClaim";

type Props = {
  state: ClaimState;
  onText: (text: string) => void;
  onPhoto: (file: File) => void;
  onDecide: (d: "claim" | "dont_claim" | "file") => void;
  setMic: (on: boolean) => Promise<unknown>;
};

export default function Chat({ state, onText, onPhoto, onDecide, setMic }: Props) {
  const [text, setText] = useState("");
  const talking = state.micOn; // hands-free: the mic stays open until the user taps it again
  const list = useRef<HTMLDivElement>(null);
  const pinned = useRef(true); // the user is at the bottom of the chat
  const fileInput = useRef<HTMLInputElement>(null);
  const busy = state.status !== "idle";
  const lastMessage = state.messages[state.messages.length - 1];
  // dots until the bot's reply starts streaming in, then the reply bubble takes their place
  const showThinking = state.status === "thinking" && lastMessage?.role !== "bot";

  // Follow the reply as it streams in, without animation and without scrolling the page;
  // smooth-scrolling on every word made the chat shake. Leave it alone if the user scrolled up.
  useLayoutEffect(() => {
    const el = list.current;
    if (el && pinned.current) el.scrollTop = el.scrollHeight;
  }, [state.messages, showThinking]);

  // tap the mic to talk hands-free: LiveKit hears when you've finished; tap again to stop
  function toggleMic() {
    setMic(!state.micOn).catch(() => alert("Microphone not available. Please type instead."));
  }

  function pickPhoto(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (file) onPhoto(file);
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim() || state.status === "connecting" || state.status === "closed") return;
    onText(text.trim());
    setText("");
  }

  const s = state.state;
  const status =
    state.status === "connecting" ? "Connecting…"
    : state.status === "closed" ? "Disconnected"
    : state.speaking ? "Speaking…"
    : state.status === "thinking" ? "Thinking…"
    : talking ? "Listening…"
    : "Online";

  return (
    <section className="flex min-h-[70dvh] flex-col overflow-hidden rounded-2xl border border-line bg-white shadow-sm md:h-full md:min-h-0">
      <div className="flex items-center gap-3 border-b border-line px-5 py-3">
        <div className="grid h-9 w-9 place-items-center rounded-full bg-navy text-xs font-bold text-white">CK</div>
        <div className="leading-tight">
          <p className="text-sm font-semibold text-ink">Claim assistant</p>
          <p className="flex items-center gap-1.5 text-xs text-muted">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                state.status === "closed" ? "bg-red-500"
                : state.status === "connecting" ? "bg-amber-400"
                : talking ? "animate-pulse bg-red-500"
                : "bg-emerald-500"
              }`}
            />
            <span aria-live="polite">{status}</span>
          </p>
        </div>
      </div>

      <div
        ref={list}
        onScroll={(e) => {
          const el = e.currentTarget;
          pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
        }}
        className="flex-1 space-y-3 overflow-y-auto overscroll-contain bg-canvas/50 px-4 py-5 [overflow-anchor:none] sm:px-6"
      >
        {state.messages.map((m) => (
          <div key={m.id} className={`animate-fadein flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <p
              className={`max-w-[85%] whitespace-pre-wrap break-words px-4 py-2.5 text-[15px] leading-relaxed sm:max-w-[75%] ${
                m.role === "user"
                  ? "rounded-2xl rounded-br-md bg-navy text-white"
                  : "rounded-2xl rounded-bl-md border border-line bg-white text-ink"
              }`}
            >
              {m.text}
            </p>
          </div>
        ))}
        {showThinking && (
          <div className="flex w-fit gap-1 rounded-2xl rounded-bl-md border border-line bg-white px-4 py-3" aria-label="thinking">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="h-1.5 w-1.5 animate-bounce rounded-full bg-sky"
                style={{ animationDelay: `${i * 150}ms` }}
              />
            ))}
          </div>
        )}
      </div>

      {s === "VIABILITY" && (
        <div className="flex gap-2 border-t border-line bg-white px-4 pt-3 sm:px-6">
          <button
            onClick={() => onDecide("claim")}
            disabled={busy}
            className="flex-1 rounded-xl bg-sky py-2.5 text-sm font-semibold text-white transition hover:bg-sky-dark disabled:opacity-40"
          >
            File claim
          </button>
          <button
            onClick={() => onDecide("dont_claim")}
            disabled={busy}
            className="flex-1 rounded-xl border border-line py-2.5 text-sm font-semibold text-navy transition hover:bg-canvas disabled:opacity-40"
          >
            Don&apos;t claim
          </button>
        </div>
      )}

      <form onSubmit={submit} className="flex items-center gap-2 bg-white px-4 py-3 sm:px-6">
        {s === "EVIDENCE" && (
          <>
            <IconButton onClick={() => fileInput.current?.click()} disabled={busy} title="Upload photo" variant="outline">
              <CameraIcon />
            </IconButton>
            <input ref={fileInput} type="file" accept="image/*" capture="environment" hidden onChange={pickPhoto} />
          </>
        )}
        <div className="flex min-w-0 flex-1 items-center rounded-full border border-line bg-canvas/60 pl-4 pr-1 transition focus-within:border-sky focus-within:bg-white">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={talking ? "Listening… just speak, or type" : "Describe what happened…"}
            className="min-w-0 flex-1 bg-transparent py-2.5 text-sm outline-none placeholder:text-muted"
          />
          <button
            type="submit"
            disabled={!text.trim() || state.status === "connecting" || state.status === "closed"}
            className="grid h-8 w-8 place-items-center rounded-full bg-navy text-white transition disabled:opacity-30"
            title="Send"
          >
            <SendIcon />
          </button>
        </div>
        <button
          type="button"
          onClick={toggleMic}
          disabled={state.status === "connecting" || state.status === "closed"}
          title={talking ? "Stop talking" : "Tap to talk hands-free"}
          aria-label={talking ? "Stop talking" : "Talk"}
          aria-pressed={talking}
          className={`relative grid h-11 w-11 shrink-0 place-items-center rounded-full text-white shadow-sm transition disabled:opacity-40 ${
            talking ? "bg-red-500 ring-4 ring-red-100" : "bg-sky hover:bg-sky-dark"
          }`}
        >
          {talking && state.speaking && <span className="absolute inset-0 animate-ping rounded-full bg-red-400/40" />}
          {talking ? <StopIcon /> : <MicIcon />}
        </button>
      </form>
    </section>
  );
}

function IconButton({
  children,
  variant,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant: "outline" }) {
  return (
    <button
      type="button"
      {...props}
      className={`grid h-11 w-11 shrink-0 place-items-center rounded-full text-navy transition disabled:opacity-40 ${
        variant === "outline" ? "border border-line hover:border-sky hover:bg-sky-soft" : ""
      }`}
    >
      {children}
    </button>
  );
}

const iconProps = {
  width: 18,
  height: 18,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

const MicIcon = () => (
  <svg {...iconProps}>
    <rect x="9" y="2" width="6" height="12" rx="3" />
    <path d="M5 10a7 7 0 0 0 14 0M12 17v5" />
  </svg>
);
const StopIcon = () => (
  <svg {...iconProps}>
    <rect x="7" y="7" width="10" height="10" rx="2" fill="currentColor" />
  </svg>
);
const SendIcon = () => (
  <svg {...iconProps} width={15} height={15}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </svg>
);
const CameraIcon = () => (
  <svg {...iconProps}>
    <path d="M4 8h3l2-3h6l2 3h3v11H4z" />
    <circle cx="12" cy="13" r="3.5" />
  </svg>
);
````

### `web/components/ClaimPanel.tsx`

````tsx
"use client";

import type { Profile } from "@/lib/api";
import { formatDate, label, VERDICT } from "@/lib/format";
import { rupees, type ClaimState } from "@/lib/useClaim";

const FIELD_LABELS: Record<string, string> = {
  vehicle_id: "Vehicle",
  incident_date: "Date",
  incident_location: "Location",
  description_english: "What happened",
  estimated_repair_cost_inr: "Damage estimate",
  garage_name: "Garage",
  third_party_involved: "Third party",
  third_party_property_damaged: "Third-party damage",
  anyone_injured: "Injuries",
  police_report_filed: "FIR filed",
  risk_flags: "Flags",
};

const STEPS = [
  { label: "Details", states: ["INTAKE"] },
  { label: "Policy", states: ["MATCH_POLICY", "NO_COVER"] },
  { label: "Verdict", states: ["VIABILITY", "ADVISED_NO_CLAIM"] },
  { label: "Photos", states: ["EVIDENCE"] },
  { label: "Review", states: ["FORM_REVIEW"] },
  { label: "Filed", states: ["FILED"] },
];

const DOC_LABELS: Record<string, string> = {
  dl: "Driving licence",
  rc: "Registration certificate",
  policy_copy: "Policy copy",
  garage_estimate: "Garage estimate",
  fir: "FIR copy",
};

function Card({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <section className="animate-fadein rounded-2xl border border-line bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function Rows({ rows }: { rows: [string, React.ReactNode][] }) {
  return (
    <dl className="space-y-2 text-sm">
      {rows.map(([k, v]) =>
        typeof v === "string" && v.length > 32 ? (
          <div key={k} className="animate-fadein">
            <dt className="text-muted">{k}</dt>
            <dd className="mt-0.5 font-medium text-ink">{v}</dd>
          </div>
        ) : (
          <div key={k} className="animate-fadein flex justify-between gap-4">
            <dt className="shrink-0 text-muted">{k}</dt>
            <dd className="text-right font-medium text-ink">{v}</dd>
          </div>
        ),
      )}
    </dl>
  );
}

function Stepper({ state }: { state: string }) {
  const current = STEPS.findIndex((s) => s.states.includes(state));
  return (
    <ol className="flex items-center gap-1">
      {STEPS.map((step, i) => (
        <li key={step.label} className="flex flex-1 flex-col items-center gap-1.5">
          <span className={`h-1 w-full rounded-full ${i <= current ? "bg-sky" : "bg-line"}`} />
          <span className={`text-[10px] font-medium ${i === current ? "text-navy" : "text-muted"}`}>{step.label}</span>
        </li>
      ))}
    </ol>
  );
}

export default function ClaimPanel({
  state,
  profile,
  onFile,
}: {
  state: ClaimState;
  profile: Profile;
  onFile: () => void;
}) {
  const { fields, policy, viability, photos, missingDocs, settlement, form, referenceNo } = state;
  const vehicleName = (id: unknown) => {
    const v = profile.vehicles.find((x) => x.id === id);
    return v ? `${v.brand} ${v.model} · ${v.vehicle_number}` : String(id);
  };

  function show(name: string, value: unknown) {
    if (name === "vehicle_id") return vehicleName(value);
    if (name === "estimated_repair_cost_inr") return rupees(value);
    if (name === "incident_date") return formatDate(String(value));
    if (typeof value === "boolean") return value ? "Yes" : "No";
    if (Array.isArray(value)) return value.map(label).join(", ") || "—";
    return String(value);
  }

  const fieldRows = Object.entries(fields)
    .filter(([k, v]) => k in FIELD_LABELS && v !== false && !(Array.isArray(v) && v.length === 0))
    .map(([k, v]) => [FIELD_LABELS[k], show(k, v)] as [string, React.ReactNode]);

  return (
    <aside className="space-y-3 pb-4 md:overflow-y-auto md:pb-0">
      <div className="rounded-2xl border border-line bg-white px-4 py-3 shadow-sm">
        <Stepper state={state.state} />
      </div>

      {viability && (
        <section className={`animate-fadein rounded-2xl border p-4 ${VERDICT[viability.verdict].tone}`}>
          <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider opacity-70">
            <span className={`h-2 w-2 rounded-full ${VERDICT[viability.verdict].dot}`} />
            Recommendation
          </p>
          <p className="mt-1 text-xl font-semibold">{VERDICT[viability.verdict].label}</p>
          {viability.verdict !== "not_covered" && (
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="rounded-xl bg-white/70 p-3">
                <p className="text-xs opacity-70">Insurer pays</p>
                <p className="mt-0.5 text-lg font-bold">
                  {viability.estimate_pending ? "—" : rupees(viability.insurer_payout_inr)}
                </p>
              </div>
              <div className="rounded-xl bg-white/70 p-3">
                <p className="text-xs opacity-70">No-Claim Bonus lost</p>
                <p className="mt-0.5 text-lg font-bold">{rupees(viability.ncb_loss_total_inr)}</p>
                <p className="text-[10px] opacity-60">over 3 years</p>
              </div>
            </div>
          )}
          {viability.estimate_pending && viability.breakeven_estimate_inr && (
            <p className="mt-3 text-xs">
              Worth claiming only if repairs cost more than {rupees(viability.breakeven_estimate_inr)}.
            </p>
          )}
        </section>
      )}


      <Card title="Incident">
        {fieldRows.length === 0 ? (
          <p className="text-sm text-muted">Details will appear here as you describe the accident.</p>
        ) : (
          <Rows rows={fieldRows} />
        )}
      </Card>

      {policy && (
        <Card title="Matched policy">
          <p className="text-sm font-semibold text-ink">{policy.insurer_name}</p>
          <p className="mt-0.5 text-xs text-muted">{policy.policy_number}</p>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {[label(policy.coverage_type), `NCB ${policy.no_claim_bonus_pct}%`, `Deductible ${rupees(policy.deductible_inr)}`, ...policy.add_on_covers.map(label)].map(
              (t) => (
                <span key={t} className="rounded-full bg-canvas px-2.5 py-1 text-xs text-ink">
                  {t}
                </span>
              ),
            )}
          </div>
        </Card>
      )}

      {photos.length > 0 && (
        <Card title="Photos">
          <div className="grid grid-cols-3 gap-2">
            {photos.map((p) => (
              <figure key={p.id} className="relative overflow-hidden rounded-xl border border-line">
                {/* Local data URL preview, so next/image adds nothing here */}
                <img src={p.preview} alt={p.evidence_type ?? "photo"} className="aspect-square w-full object-cover" />
                <figcaption
                  className={`absolute inset-x-0 bottom-0 px-1.5 py-1 text-center text-[10px] font-semibold text-white ${
                    p.status === "accepted" ? "bg-emerald-600/90" : p.status === "retake" ? "bg-red-600/90" : "bg-navy/70"
                  }`}
                >
                  {p.status === "accepted" ? "Accepted" : p.status === "retake" ? "Retake" : "Checking…"}
                </figcaption>
              </figure>
            ))}
          </div>
        </Card>
      )}

      {form && (
        <Card
          title="Claim form"
          action={
            referenceNo && (
              <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">Filed</span>
            )
          }
        >
          <Rows
            rows={Object.entries(form)
              .filter(([, v]) => v !== null && v !== undefined)
              .map(([k, v]) => [
                label(k).replace(/ inr$/i, ""),
                k.endsWith("_inr") ? rupees(v) : k.endsWith("_date") ? formatDate(String(v)) : label(String(v)),
              ])}
          />

          {missingDocs && missingDocs.length > 0 && (
            <div className="mt-4 rounded-xl bg-amber-50 p-3">
              <p className="text-xs font-semibold text-amber-900">Documents needed</p>
              <ul className="mt-1 space-y-0.5 text-sm text-amber-900">
                {missingDocs.map((d) => (
                  <li key={d}>• {DOC_LABELS[d] ?? label(d)}</li>
                ))}
              </ul>
            </div>
          )}
          {settlement && (
            <p className="mt-3 text-sm text-muted">
              Expected settlement in{" "}
              <span className="font-semibold text-ink">
                {settlement.min_days}–{settlement.max_days} days
              </span>{" "}
              ({settlement.route})
            </p>
          )}

          {referenceNo ? (
            <div className="mt-4 rounded-xl bg-navy p-4 text-center text-white">
              <p className="text-xs opacity-70">Reference number</p>
              <p className="mt-1 font-mono text-lg font-semibold tracking-wide">{referenceNo}</p>
              <p className="mt-2 text-xs opacity-80">● Status tracking on. We'll let you know when it changes.</p>
            </div>
          ) : (
            state.state === "FORM_REVIEW" && (
              <button
                onClick={onFile}
                disabled={state.status !== "idle"}
                className="mt-4 w-full rounded-xl bg-sky py-3 text-sm font-semibold text-white transition hover:bg-sky-dark disabled:opacity-40"
              >
                File claim
              </button>
            )
          )}
        </Card>
      )}
    </aside>
  );
}
````

### `web/components/Dashboard.tsx`

````tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import {
  deleteClaim,
  fetchClaim,
  fetchDashboard,
  fileClaim,
  type ClaimDetail,
  type ClaimSummary,
  type DashboardData,
  type DocumentName,
  type Profile,
  type Stage,
  type WalletPolicy,
} from "@/lib/api";
import { formatDate, label, VERDICT } from "@/lib/format";
import { rupees, type Language } from "@/lib/useClaim";

// Where each claim stands, by its conversation stage.
const STAGE: Record<Stage, { label: string; tone: string }> = {
  INTAKE: { label: "Details pending", tone: "bg-amber-50 text-amber-800 ring-amber-200" },
  VIABILITY: { label: "Decision pending", tone: "bg-sky-soft text-navy ring-sky/30" },
  EVIDENCE: { label: "Photos pending", tone: "bg-sky-soft text-navy ring-sky/30" },
  FORM_REVIEW: { label: "Ready to file", tone: "bg-violet-50 text-violet-800 ring-violet-200" },
  FILED: { label: "Filed", tone: "bg-emerald-50 text-emerald-700 ring-emerald-200" },
  NO_COVER: { label: "Not covered", tone: "bg-canvas text-muted ring-line" },
  ADVISED_NO_CLAIM: { label: "Not claimed", tone: "bg-canvas text-muted ring-line" },
  CANCELLED: { label: "Cancelled", tone: "bg-canvas text-muted ring-line" },
};

const PHOTO_LABEL: Record<string, string> = {
  damage_wide: "Vehicle and damage",
  damage_close: "Damage close-up",
  number_plate: "Number plate",
  odometer: "Odometer",
  dl: "Driving licence",
};

const docName = (d: DocumentName, language: Language) => (language === "hi" ? d.name_hindi : d.name_english);

const vehicleOf = (c: ClaimSummary) => (c.brand ? `${c.brand} ${c.model}` : "Vehicle not given yet");

// What the claim is about: the English summary, or else the user's own first words.
const titleOf = (c: ClaimSummary) => c.description_english ?? c.first_user_message ?? "Claim conversation";

function timeAgo(iso: string | null) {
  if (!iso) return "";
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  return formatDate(iso);
}

function StagePill({ stage }: { stage: Stage }) {
  return (
    <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${STAGE[stage].tone}`}>
      {STAGE[stage].label}
    </span>
  );
}

function Section({ title, aside, children }: { title: string; aside?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

function Rows({ rows }: { rows: [string, React.ReactNode][] }) {
  return (
    <dl className="space-y-2 text-sm">
      {rows.map(([k, v]) => (
        <div key={k} className="flex justify-between gap-4">
          <dt className="shrink-0 text-muted">{k}</dt>
          <dd className="min-w-0 text-right font-medium break-words text-ink">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

const TrashIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v6M14 11v6" />
  </svg>
);

// Delete asks once more before it removes the claim and its whole conversation.
function DeleteButton({ onDelete, compact }: { onDelete: () => Promise<void>; compact?: boolean }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  if (!confirming) {
    return (
      <button
        onClick={(e) => {
          e.stopPropagation();
          setConfirming(true);
        }}
        title="Delete this claim"
        aria-label="Delete this claim"
        className={`flex items-center gap-1.5 rounded-xl text-sm font-medium text-muted transition hover:bg-red-50 hover:text-red-700 ${
          compact ? "p-2" : "border border-line px-3 py-2.5"
        }`}
      >
        <TrashIcon />
        {!compact && "Delete"}
      </button>
    );
  }
  return (
    <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
      <span className="text-xs text-red-700">Delete for good?</span>
      <button
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            await onDelete();
          } finally {
            setBusy(false);
            setConfirming(false);
          }
        }}
        className="rounded-lg bg-red-600 px-2.5 py-1.5 text-xs font-semibold text-white transition hover:bg-red-700 disabled:opacity-50"
      >
        {busy ? "Deleting…" : "Delete"}
      </button>
      <button onClick={() => setConfirming(false)} className="rounded-lg px-2 py-1.5 text-xs font-medium text-muted hover:text-ink">
        Keep
      </button>
    </div>
  );
}

// --- claims list -------------------------------------------------------------------------

function ClaimRow({
  claim,
  active,
  onSelect,
  onResume,
  onDelete,
}: {
  claim: ClaimSummary;
  active: boolean;
  onSelect: () => void;
  onResume: () => void;
  onDelete: () => Promise<void>;
}) {
  const payout = claim.viability_assessment?.estimate_pending ? null : claim.expected_payout_inr;
  return (
    <article
      onClick={onSelect}
      aria-current={active}
      className={`cursor-pointer rounded-2xl border bg-white p-4 shadow-sm transition ${
        active ? "border-sky ring-4 ring-sky-soft" : "border-line hover:border-sky"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-ink">{vehicleOf(claim)}</p>
          <p className="truncate text-xs text-muted">{titleOf(claim)}</p>
        </div>
        <StagePill stage={claim.conversation_stage} />
      </div>

      <div className="mt-3 flex flex-wrap items-end justify-between gap-2">
        <div>
          {claim.conversation_stage === "FILED" ? (
            <>
              <p className="text-[11px] text-muted">Reference</p>
              <p className="font-mono text-sm font-semibold text-ink">{claim.claim_reference_number}</p>
              <p className="mt-0.5 text-[11px] font-medium text-emerald-700">● Tracking status</p>
            </>
          ) : (
            <>
              <p className="text-[11px] text-muted">{payout !== null ? "Expected payout" : "Last activity"}</p>
              <p className="text-sm font-semibold text-navy tabular-nums">
                {payout !== null ? rupees(payout) : timeAgo(claim.last_activity_at ?? claim.started_at)}
              </p>
            </>
          )}
        </div>
        <div className="flex items-center gap-1">
          {claim.deletable && <DeleteButton compact onDelete={onDelete} />}
          {claim.resumable && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onResume();
              }}
              className="rounded-xl bg-sky px-3.5 py-2 text-xs font-semibold text-white transition hover:bg-sky-dark"
            >
              Continue →
            </button>
          )}
        </div>
      </div>
    </article>
  );
}

// --- claim detail ------------------------------------------------------------------------

function ClaimDetailPanel({
  userId,
  sessionId,
  language,
  onBack,
  onChanged,
  onResume,
  onDelete,
}: {
  userId: string;
  sessionId: string;
  language: Language;
  onBack: () => void;
  onChanged: () => void;
  onResume: () => void;
  onDelete: () => Promise<void>;
}) {
  const [claim, setClaim] = useState<ClaimDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filing, setFiling] = useState(false);

  useEffect(() => {
    let live = true;
    setClaim(null);
    setError(null);
    fetchClaim(userId, sessionId)
      .then((c) => live && setClaim(c))
      .catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [userId, sessionId]);

  async function file() {
    setFiling(true);
    setError(null);
    try {
      await fileClaim(userId, sessionId);
      setClaim(await fetchClaim(userId, sessionId));
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setFiling(false);
    }
  }

  if (!claim) {
    return (
      <div className="rounded-2xl border border-line bg-white p-6 text-sm text-muted shadow-sm">
        {error ?? "Loading claim…"}
      </div>
    );
  }

  const verdict = claim.claim_recommendation ? VERDICT[claim.claim_recommendation] : null;
  const missing = claim.documents.filter((d) => !d.is_provided);
  const formRows = Object.entries(claim.claim_form_data ?? {})
    .filter(([k, v]) => v !== null && v !== undefined && !["policyholder", "phone_number"].includes(k))
    .map(([k, v]) => [
      label(k).replace(/ inr$/i, ""),
      k.endsWith("_inr") ? rupees(v) : k.endsWith("_date") ? formatDate(String(v)) : label(String(v)),
    ]) as [string, React.ReactNode][];

  return (
    <article className="animate-fadein space-y-3">
      <button onClick={onBack} className="text-sm font-medium text-sky-dark md:hidden">
        ← All claims
      </button>

      <header className="rounded-2xl border border-line bg-white p-4 shadow-sm">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs text-muted">
              {claim.claim_type ? `${label(claim.claim_type)} claim` : `Started ${formatDate(claim.started_at)}`}
            </p>
            <h2 className="mt-0.5 text-lg font-semibold text-ink">{vehicleOf(claim)}</h2>
            <p className="text-xs text-muted">
              {claim.insurer_name ? `${claim.insurer_name} · ${claim.policy_number}` : titleOf(claim)}
            </p>
          </div>
          <StagePill stage={claim.conversation_stage} />
        </div>

        {claim.claim_status === "filed" ? (
          <div className="mt-4 rounded-xl bg-navy p-4 text-white">
            <p className="text-xs opacity-70">Reference number</p>
            <p className="mt-1 font-mono text-lg font-semibold tracking-wide">{claim.claim_reference_number}</p>
            <p className="mt-1 text-xs opacity-70">Filed {claim.filed_at && formatDate(claim.filed_at)}</p>
            <p className="mt-2 text-xs opacity-80">● Status tracking on. We'll let you know when it changes.</p>
          </div>
        ) : (
          <div className="mt-4 space-y-3 rounded-xl bg-canvas p-4">
            <p className="text-xs text-muted">
              {claim.claim_status === "draft"
                ? missing.length > 0
                  ? "Ready to file. You can send the missing documents to the insurer afterwards."
                  : "Ready to file. Everything the insurer needs is in place."
                : claim.resumable
                  ? "Not finished yet. Continue where you left off, or delete it if you don't need it."
                  : "This conversation is closed."}
            </p>
            <div className="flex gap-2">
              {claim.claim_status === "draft" ? (
                <button
                  onClick={file}
                  disabled={filing}
                  className="flex-1 rounded-xl bg-sky py-2.5 text-sm font-semibold text-white transition hover:bg-sky-dark disabled:opacity-40"
                >
                  {filing ? "Filing…" : "File claim"}
                </button>
              ) : (
                claim.resumable && (
                  <button
                    onClick={onResume}
                    className="flex-1 rounded-xl bg-sky py-2.5 text-sm font-semibold text-white transition hover:bg-sky-dark"
                  >
                    Continue claim
                  </button>
                )
              )}
              {claim.deletable && <DeleteButton onDelete={onDelete} />}
            </div>
          </div>
        )}
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      </header>

      {verdict && claim.viability_assessment && (
        <section className={`rounded-2xl border p-4 ${verdict.tone}`}>
          <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider opacity-70">
            <span className={`h-2 w-2 rounded-full ${verdict.dot}`} />
            Recommendation
          </p>
          <p className="mt-1 text-lg font-semibold">{verdict.label}</p>
          {claim.claim_recommendation !== "not_covered" && (
            <div className="mt-3 grid grid-cols-2 gap-3">
              <div className="rounded-xl bg-white/70 p-3">
                <p className="text-xs opacity-70">Insurer pays</p>
                <p className="mt-0.5 font-bold tabular-nums">
                  {claim.viability_assessment.estimate_pending
                    ? "—"
                    : rupees(claim.viability_assessment.insurer_payout_inr)}
                </p>
              </div>
              <div className="rounded-xl bg-white/70 p-3">
                <p className="text-xs opacity-70">No-Claim Bonus lost</p>
                <p className="mt-0.5 font-bold tabular-nums">{rupees(claim.viability_assessment.ncb_loss_total_inr)}</p>
              </div>
            </div>
          )}
        </section>
      )}

      {claim.claim_form_data && (
        <>
          <section className="rounded-2xl border border-line bg-white p-4 shadow-sm">
            <div className="mb-3 flex items-baseline justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">Documents</h3>
              <p className="text-xs text-muted">
                {claim.documents.length - missing.length} of {claim.documents.length} ready
              </p>
            </div>
            <ul className="space-y-2">
              {claim.documents.map((d) => (
                <li key={d.document_code} className="flex items-center gap-3 text-sm">
                  <span
                    aria-hidden
                    className={`grid h-5 w-5 shrink-0 place-items-center rounded-full text-[11px] font-bold ${
                      d.is_provided ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-800"
                    }`}
                  >
                    {d.is_provided ? "✓" : "!"}
                  </span>
                  <span className="min-w-0 flex-1 text-ink">{docName(d, language)}</span>
                  <span className={`text-xs ${d.is_provided ? "text-muted" : "font-medium text-amber-800"}`}>
                    {d.is_provided ? "Have it" : "Needed"}
                  </span>
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded-2xl border border-line bg-white p-4 shadow-sm">
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">Claim form</h3>
            <Rows rows={formRows} />
            {claim.expected_settlement_days_min !== null && (
              <p className="mt-4 border-t border-line pt-3 text-sm text-muted">
                Expected settlement in{" "}
                <span className="font-semibold text-ink">
                  {claim.expected_settlement_days_min}–{claim.expected_settlement_days_max} days
                </span>
              </p>
            )}
          </section>
        </>
      )}

      {claim.evidence.length > 0 && (
        <section className="rounded-2xl border border-line bg-white p-4 shadow-sm">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">Photos checked</h3>
          <ul className="space-y-2 text-sm">
            {claim.evidence.map((e) => (
              <li key={e.id} className="flex items-center justify-between gap-3">
                <span className="text-ink">{PHOTO_LABEL[e.evidence_type] ?? label(e.evidence_type)}</span>
                <span className={`text-xs font-medium ${e.is_accepted ? "text-emerald-700" : "text-red-600"}`}>
                  {e.is_accepted ? "Accepted" : `Retake: ${[...e.detail_mismatches, ...e.quality_issues].map(label).join(", ").toLowerCase()}`}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {claim.messages.length > 0 && (
        <details className="group rounded-2xl border border-line bg-white p-4 shadow-sm">
          <summary className="flex cursor-pointer list-none items-center justify-between text-xs font-semibold uppercase tracking-wider text-muted">
            Conversation ({claim.messages.length})
            <span className="transition group-open:rotate-180">▾</span>
          </summary>
          <ol className="mt-3 space-y-2">
            {claim.messages.map((m, i) => (
              <li key={i} className={`flex ${m.sender_role === "user" ? "justify-end" : "justify-start"}`}>
                <p
                  className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${
                    m.sender_role === "user" ? "bg-navy text-white" : "bg-canvas text-ink"
                  }`}
                >
                  {m.message_text}
                </p>
              </li>
            ))}
          </ol>
        </details>
      )}
    </article>
  );
}

// --- policies ----------------------------------------------------------------------------

function PolicyCard({ policy, language }: { policy: WalletPolicy; language: Language }) {
  const active = new Date(policy.coverage_end_date) >= new Date();
  const comprehensive = policy.coverage_type === "comprehensive";
  return (
    <article className="flex flex-col gap-3 rounded-2xl border border-line bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-ink">
            {policy.vehicle.brand} {policy.vehicle.model}
          </p>
          <p className="text-xs text-muted">
            {policy.vehicle.vehicle_number} · {policy.vehicle.vehicle_type === "2W" ? "Two-wheeler" : "Car"} ·{" "}
            {policy.vehicle.manufacture_year}
          </p>
        </div>
        <span
          className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
            comprehensive ? "bg-sky-soft text-navy" : "bg-canvas text-muted"
          }`}
        >
          {comprehensive ? "Comprehensive" : "Third-party"}
        </span>
      </div>

      <div>
        <p className="text-sm font-medium text-ink">{policy.insurer_name}</p>
        <p className="font-mono text-xs text-muted">{policy.policy_number}</p>
      </div>

      <Rows
        rows={[
          ["Valid till", <span className={active ? "" : "text-red-600"}>{formatDate(policy.coverage_end_date)}</span>],
          ["No-Claim Bonus", `${policy.no_claim_bonus_pct}%`],
          ...(comprehensive
            ? ([
                ["Insured value (IDV)", rupees(policy.insured_declared_value_inr)],
                ["Deductible", rupees(policy.deductible_inr)],
              ] as [string, React.ReactNode][])
            : []),
        ]}
      />

      {policy.add_on_covers.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {policy.add_on_covers.map((a) => (
            <span key={a} className="rounded-full bg-canvas px-2.5 py-1 text-xs text-ink">
              {label(a)}
            </span>
          ))}
        </div>
      )}

      <div className="mt-auto border-t border-line pt-3">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">Documents for a claim</p>
        <p className="mt-1 text-sm text-ink">
          {policy.required_documents.map((d) => docName(d, language)).join(" · ")}
        </p>
      </div>
    </article>
  );
}

// --- page --------------------------------------------------------------------------------

export default function Dashboard({
  profile,
  language,
  onNewClaim,
  onResume,
}: {
  profile: Profile;
  language: Language;
  onNewClaim: () => void;
  onResume: (sessionId: string) => void;
}) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const load = useCallback(() => {
    fetchDashboard(profile.id)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e: Error) => setError(e.message));
  }, [profile.id]);

  useEffect(load, [load]);

  async function remove(sessionId: string) {
    try {
      await deleteClaim(profile.id, sessionId);
      if (selected === sessionId) setSelected(null);
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const claims = data?.claims ?? [];
  const groups = [
    { title: "In progress", items: claims.filter((c) => c.resumable) },
    { title: "Filed", items: claims.filter((c) => c.conversation_stage === "FILED") },
    { title: "Closed", items: claims.filter((c) => !c.resumable && c.conversation_stage !== "FILED") },
  ];
  const uninsured = profile.vehicles.filter((v) => !v.policy);

  return (
    <div className="grid gap-6 py-6 md:grid-cols-[minmax(0,1fr)_400px] md:items-start">
      <div className={`min-w-0 space-y-8 ${selected ? "hidden md:block" : ""}`}>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-navy">Hi {profile.full_name.split(" ")[0]}</h1>
            <p className="mt-1 text-sm text-muted">Pick up a claim where you left off, or start a new one.</p>
          </div>
          <button
            onClick={onNewClaim}
            className="rounded-xl bg-sky px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-dark"
          >
            Start a new claim
          </button>
        </div>

        {error && (
          <p className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}{" "}
            <button onClick={load} className="font-semibold underline">
              Try again
            </button>
          </p>
        )}

        {!data ? (
          <p className="text-sm text-muted">Loading your claims…</p>
        ) : claims.length === 0 ? (
          <Section title="Claims">
            <div className="rounded-2xl border border-dashed border-line bg-white p-6 text-center">
              <p className="text-sm font-medium text-ink">No claims yet</p>
              <p className="mt-1 text-sm text-muted">
                Describe what happened to your vehicle and we&apos;ll tell you if a claim is worth it.
              </p>
            </div>
          </Section>
        ) : (
          groups
            .filter((g) => g.items.length > 0)
            .map((g) => (
              <Section key={g.title} title={g.title} aside={<p className="text-xs text-muted">{g.items.length}</p>}>
                <div className="grid gap-3 lg:grid-cols-2">
                  {g.items.map((c) => (
                    <ClaimRow
                      key={c.session_id}
                      claim={c}
                      active={c.session_id === selected}
                      onSelect={() => setSelected(c.session_id)}
                      onResume={() => onResume(c.session_id)}
                      onDelete={() => remove(c.session_id)}
                    />
                  ))}
                </div>
              </Section>
            ))
        )}

        <Section title="Policies">
          {data && (
            <div className="grid gap-3 lg:grid-cols-2">
              {data.policies.map((p) => (
                <PolicyCard key={p.id} policy={p} language={language} />
              ))}
            </div>
          )}
          {uninsured.length > 0 && (
            <p className="text-sm text-muted">
              No active policy for {uninsured.map((v) => `${v.brand} ${v.model} (${v.vehicle_number})`).join(", ")}.
            </p>
          )}
        </Section>
      </div>

      <aside className={`min-w-0 md:sticky md:top-20 ${selected ? "" : "hidden md:block"}`}>
        {selected ? (
          <ClaimDetailPanel
            key={selected}
            userId={profile.id}
            sessionId={selected}
            language={language}
            onBack={() => setSelected(null)}
            onChanged={load}
            onResume={() => onResume(selected)}
            onDelete={() => remove(selected)}
          />
        ) : (
          <div className="rounded-2xl border border-dashed border-line p-6 text-center text-sm text-muted">
            Select a claim to see its details, documents and conversation.
          </div>
        )}
      </aside>
    </div>
  );
}
````

### `web/components/Login.tsx`

````tsx
"use client";

import { useState } from "react";
import { lookupUser, type Profile } from "@/lib/api";


export default function Login({ onLogin }: { onLogin: (p: Profile) => void }) {
  const [mobile, setMobile] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(number: string) {
    if (number.length !== 10) {
      setError("Enter a 10-digit mobile number");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      onLogin(await lookupUser(number));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[calc(100dvh-4rem)] max-w-md flex-col justify-center pb-16">
      <div className="mb-8 text-center">
        <h1 className="text-2xl font-semibold tracking-tight text-navy">Vehicle damaged?</h1>
        <p className="mt-2 text-sm text-muted">
          Tell us what happened in Hindi or English. We&apos;ll check if a claim is worth it and
          file it for you.
        </p>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(mobile);
        }}
        className="rounded-2xl border border-line bg-white p-6 shadow-sm"
      >
        <label htmlFor="mobile" className="text-sm font-medium text-ink">
          Mobile number
        </label>
        <div
          className={`mt-2 flex items-center rounded-xl border bg-white transition focus-within:ring-4 ${
            error ? "border-red-400 focus-within:ring-red-100" : "border-line focus-within:border-sky focus-within:ring-sky-soft"
          }`}
        >
          <span className="border-r border-line px-3 py-3 text-sm text-muted">+91</span>
          <input
            id="mobile"
            inputMode="numeric"
            autoComplete="tel-national"
            autoFocus
            maxLength={10}
            value={mobile}
            onChange={(e) => {
              setMobile(e.target.value.replace(/\D/g, "").slice(0, 10));
              setError(null);
            }}
            placeholder="10-digit number linked to Paytm"
            className="w-full rounded-r-xl px-3 py-3 text-base tracking-wide outline-none placeholder:text-sm placeholder:tracking-normal"
          />
        </div>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={loading || mobile.length !== 10}
          className="mt-5 w-full rounded-xl bg-sky py-3 text-sm font-semibold text-white transition hover:bg-sky-dark disabled:cursor-not-allowed disabled:opacity-40"
        >
          {loading ? "Fetching your policies…" : "Continue"}
        </button>

      </form>

      <p className="mt-6 text-center text-xs text-muted">
        Prototype with synthetic data. No real insurer or Paytm account is contacted.
      </p>
    </div>
  );
}
````

### `web/lib/api.ts`

````ts
// REST calls to the FastAPI backend (the conversation itself runs in a LiveKit room).
import type { Language } from "./useClaim";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type PolicySummary = {
  id: string;
  insurer_name: string;
  policy_number: string;
  coverage_type: "comprehensive" | "third_party_only";
  no_claim_bonus_pct: number;
  coverage_end_date: string;
  insured_declared_value_inr: number;
  add_on_covers: string[];
};
export type WalletVehicle = {
  id: string;
  vehicle_type: "2W" | "4W";
  vehicle_number: string;
  brand: string;
  model: string;
  manufacture_year: number;
  policy: PolicySummary | null;
};
export type Profile = {
  id: string;
  full_name: string;
  phone_number: string;
  preferred_language: Language;
  vehicles: WalletVehicle[];
};

export type DocumentName = { document_code: string; name_english: string; name_hindi: string };
export type ClaimDocument = DocumentName & { is_provided: boolean };
export type Verdict = "claim" | "dont_claim" | "borderline" | "not_covered";

export type WalletPolicy = {
  id: string;
  insurer_name: string;
  policy_number: string;
  coverage_type: "comprehensive" | "third_party_only";
  coverage_start_date: string;
  coverage_end_date: string;
  insured_declared_value_inr: number;
  no_claim_bonus_pct: number;
  deductible_inr: number;
  add_on_covers: string[];
  vehicle: Omit<WalletVehicle, "policy">;
  required_documents: DocumentName[];
};
export type Stage =
  | "INTAKE"
  | "VIABILITY"
  | "EVIDENCE"
  | "FORM_REVIEW"
  | "FILED"
  | "NO_COVER"
  | "ADVISED_NO_CLAIM"
  | "CANCELLED";

// One claim conversation, listed from its first message. The draft fields (claim_status,
// claim_type, settlement days, ...) stay null until the claim reaches review.
export type ClaimSummary = {
  session_id: string;
  conversation_stage: Stage;
  started_at: string;
  last_activity_at: string | null;
  claim_status: "draft" | "filed" | null;
  claim_reference_number: string | null;
  claim_type: string | null;
  drafted_at: string | null;
  filed_at: string | null;
  expected_settlement_days_min: number | null;
  expected_settlement_days_max: number | null;
  insurer_name: string | null;
  policy_number: string | null;
  brand: string | null;
  model: string | null;
  vehicle_number: string | null;
  incident_date: string | null;
  description_english: string | null;
  first_user_message: string | null; // what the user said first, to name the claim before it has details
  estimated_repair_cost_inr: number | null;
  expected_payout_inr: number | null;
  claim_recommendation: Verdict | null;
  viability_assessment: {
    insurer_payout_inr: number;
    ncb_loss_total_inr: number;
    deductible_inr: number;
    depreciation_inr: number;
    estimate_pending: boolean;
  } | null;
  documents_missing: number;
  resumable: boolean; // still has a step left: can be continued in chat
  deletable: boolean; // not filed yet
};
export type DashboardData = { policies: WalletPolicy[]; claims: ClaimSummary[] };

export type ClaimDetail = ClaimSummary & {
  claim_form_data: Record<string, unknown> | null;
  documents: ClaimDocument[];
  evidence: {
    id: string;
    evidence_type: string;
    is_accepted: boolean;
    quality_issues: string[];
    detail_mismatches: string[]; // e.g. PLATE_MISMATCH, DL_NUMBER_MISMATCH
    uploaded_at: string;
  }[];
  messages: { sender_role: "user" | "bot"; message_text: string; sent_at: string }[];
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new Error("Can't reach the server. Is the backend running?");
  }
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail ?? "Something went wrong");
  return body as T;
}

export const lookupUser = (mobile: string) =>
  request<Profile>(`/users/lookup?phone=${encodeURIComponent(mobile)}`);

export const fetchDashboard = (userId: string) => request<DashboardData>(`/users/${userId}/dashboard`);

export const fetchClaim = (userId: string, sessionId: string) =>
  request<ClaimDetail>(`/users/${userId}/claims/${sessionId}`);

// Joins a new LiveKit room with the claim agent dispatched into it; with resumeId, the agent
// picks that claim up where it was left.
export const fetchLiveKitToken = async (userId: string, language: Language, resumeId: string | null) => {
  const resume = resumeId ? `&session_id=${encodeURIComponent(resumeId)}` : "";
  const body = await request<{ server_url: string; participant_token: string }>(
    `/livekit/token?user_id=${encodeURIComponent(userId)}&language=${language}${resume}`,
    { method: "POST" },
  );
  return { serverUrl: body.server_url, participantToken: body.participant_token };
};

export const deleteClaim = (userId: string, sessionId: string) =>
  request<{ deleted: string }>(`/users/${userId}/claims/${sessionId}`, { method: "DELETE" });

export const fileClaim = (userId: string, sessionId: string) =>
  request<{ claim_reference_number: string }>(`/users/${userId}/claims/${sessionId}/file`, { method: "POST" });
````

### `web/lib/format.ts`

````ts
// Display helpers shared by the live claim panel and the dashboard.

export const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });

export const label = (s: string) => s.replaceAll("_", " ").replace(/^\w/, (c) => c.toUpperCase());

export const VERDICT = {
  claim: { label: "Worth claiming", tone: "border-emerald-200 bg-emerald-50 text-emerald-900", dot: "bg-emerald-500" },
  dont_claim: { label: "Better not to claim", tone: "border-amber-200 bg-amber-50 text-amber-900", dot: "bg-amber-500" },
  borderline: { label: "Borderline", tone: "border-yellow-200 bg-yellow-50 text-yellow-900", dot: "bg-yellow-500" },
  not_covered: { label: "Not covered", tone: "border-red-200 bg-red-50 text-red-900", dot: "bg-red-500" },
};
````

### `web/lib/media.ts`

````ts
// Browser media helpers for the chat.

// Phone photos can be 10MB+; shrink to a 1600px JPEG before sending.
export async function shrinkImage(file: File): Promise<{ blob: Blob; preview: string }> {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, 1600 / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d")!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  const preview = canvas.toDataURL("image/jpeg", 0.85);
  const blob = await new Promise<Blob>((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("could not encode photo"))), "image/jpeg", 0.85),
  );
  return { blob, preview };
}
````

### `web/lib/useClaim.ts`

````ts
"use client";

// The claim conversation over LiveKit. LiveKit carries the audio both ways, the typed chat
// (useSessionMessages) and the agent's state; the agent also sends the whole claim as one
// JSON snapshot on the "claim.state" text stream, which the side panel renders.
import { useAgent, useLocalParticipant, useSessionContext, useSessionMessages, useTextStream } from "@livekit/components-react";
import { useCallback, useMemo, useState } from "react";
import { shrinkImage } from "./media";

export type Language = "hi" | "en";
export type Status = "connecting" | "idle" | "thinking" | "closed";

export type Message = { id: string; role: "bot" | "user"; text: string };
export type Photo = {
  id: string;
  preview: string;
  status: "grading" | "accepted" | "retake";
  evidence_type?: string;
  quality_issues?: string[];
};
export type Policy = {
  policy_id: string;
  insurer_name: string;
  policy_number: string;
  coverage_type: string;
  no_claim_bonus_pct: number;
  deductible_inr: number;
  add_on_covers: string[];
};
export type Viability = {
  verdict: "claim" | "dont_claim" | "borderline" | "not_covered";
  insurer_payout_inr: number;
  ncb_loss_year1_inr: number;
  ncb_loss_total_inr: number;
  deductible_inr: number;
  depreciation_inr: number;
  estimate_pending: boolean;
  breakeven_estimate_inr: number | null;
  reasons: string[];
};
export type Settlement = { min_days: number; max_days: number; route: string };

// What the agent publishes on "claim.state" (agent/claim_agent.py, Claim.publish).
type Snapshot = {
  sessionId: string | null; // a new id when the user cancels and starts a new claim
  state: string;
  fields: Record<string, unknown>;
  policy: Policy | null;
  viability: Viability | null;
  photos: Record<string, Omit<Photo, "id" | "preview">>;
  form: Record<string, unknown> | null;
  missingDocs: string[] | null;
  settlement: Settlement | null;
  referenceNo: string | null;
};

export type ClaimState = Omit<Snapshot, "photos"> & {
  status: Status;
  messages: Message[];
  photos: Photo[];
  speaking: boolean; // the agent is talking
  micOn: boolean;
};

const EMPTY: Snapshot = {
  sessionId: null,
  state: "INTAKE",
  fields: {},
  policy: null,
  viability: null,
  photos: {},
  form: null,
  missingDocs: null,
  settlement: null,
  referenceNo: null,
};

// The buttons answer the agent's questions as if the user had said so.
const DECISION_TEXT: Record<"claim" | "dont_claim" | "file", Record<Language, string>> = {
  claim: { hi: "हाँ, claim फ़ाइल करना है।", en: "Yes, I want to file the claim." },
  dont_claim: { hi: "नहीं, claim नहीं करना।", en: "No, I don't want to claim." },
  file: { hi: "हाँ, claim फ़ाइल कर दीजिए।", en: "Yes, please file the claim." },
};

const MIC_OPTIONS = { echoCancellation: true, noiseSuppression: true, autoGainControl: true, voiceIsolation: true };

// history: the earlier messages of a resumed claim, shown above the live conversation.
export function useClaim(language: Language, history: Message[] = []) {
  const session = useSessionContext();
  const agent = useAgent(session);
  const chat = useSessionMessages(session);
  const { localParticipant, isMicrophoneEnabled } = useLocalParticipant();
  const { textStreams } = useTextStream("claim.state");
  // photo id -> preview, and the claim (session id) it was uploaded to
  const [previews, setPreviews] = useState<Record<string, { preview: string; sessionId: string | null }>>({});

  const snapshot: Snapshot = useMemo(() => {
    const latest = textStreams[textStreams.length - 1];
    return latest ? JSON.parse(latest.text) : EMPTY;
  }, [textStreams]);

  const live: Message[] = chat.messages
    .map((m): Message => {
      const fromUser = m.type === "userTranscript" || (m.type === "chatMessage" && !!m.from?.isLocal);
      return { id: m.id, role: fromUser ? "user" : "bot", text: m.message };
    })
    .filter((m) => m.text.trim());
  const messages = history.length ? [...history, ...live] : live;

  const status: Status = !session.isConnected
    ? live.length > 0
      ? "closed"
      : "connecting"
    : !agent.isConnected
      ? "connecting"
      : agent.state === "thinking" || chat.isSending
        ? "thinking"
        : "idle";

  const state: ClaimState = {
    ...snapshot,
    status,
    messages,
    // only this claim's photos: a cancelled claim's thumbnails disappear with it
    photos: Object.entries(previews)
      .filter(([, p]) => p.sessionId === snapshot.sessionId)
      .map(([id, { preview }]) => ({
        id,
        preview,
        ...(snapshot.photos[id] ?? { status: "grading" as const }),
      })),
    speaking: agent.state === "speaking",
    micOn: isMicrophoneEnabled,
  };

  const sendText = useCallback((text: string) => chat.send(text), [chat]);

  const sendPhoto = useCallback(
    async (file: File) => {
      const id = crypto.randomUUID();
      const { blob, preview } = await shrinkImage(file);
      setPreviews((p) => ({ ...p, [id]: { preview, sessionId: snapshot.sessionId } }));
      // the agent keys the photo's result by the file name (without extension)
      await localParticipant.sendFile(new File([blob], `${id}.jpg`, { type: "image/jpeg" }), {
        topic: "photo",
        mimeType: "image/jpeg",
      });
    },
    [localParticipant, snapshot.sessionId],
  );

  const decide = useCallback(
    (d: "claim" | "dont_claim" | "file") => chat.send(DECISION_TEXT[d][language]),
    [chat, language],
  );

  // the browser's echo cancellation keeps the bot's voice (from the speakers) out of the mic
  const setMic = useCallback(
    (on: boolean) => localParticipant.setMicrophoneEnabled(on, MIC_OPTIONS),
    [localParticipant],
  );

  return { state, sendText, sendPhoto, decide, setMic };
}

export const rupees = (n: unknown) =>
  typeof n === "number" ? `₹${n.toLocaleString("en-IN")}` : "—";
````

### `web/package.json`

````json
{
  "name": "claim-karo-web",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "@livekit/components-react": "2.9.24",
    "livekit-client": "2.23.0",
    "next": "16.4.3",
    "react": "19.3.1",
    "react-dom": "19.3.1"
  },
  "devDependencies": {
    "@tailwindcss/postcss": "4.3.3",
    "@types/node": "^22",
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "tailwindcss": "4.3.3",
    "typescript": "^5"
  }
}
````

### `web/postcss.config.mjs`

````js
export default { plugins: { "@tailwindcss/postcss": {} } };
````

### `web/tsconfig.json`

````json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": [
      "dom",
      "dom.iterable",
      "esnext"
    ],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "react-jsx",
    "incremental": true,
    "plugins": [
      {
        "name": "next"
      }
    ],
    "paths": {
      "@/*": [
        "./*"
      ]
    }
  },
  "include": [
    "next-env.d.ts",
    "**/*.ts",
    "**/*.tsx",
    ".next/types/**/*.ts",
    ".next/dev/types/**/*.ts"
  ],
  "exclude": [
    "node_modules"
  ]
}
````

