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
| P0 | Push-to-talk voice intake (Sarvam STT) + text fallback | B |
| P0 | Incident extraction to structured JSON (Claude, structured output) | A |
| P0 | Policy matching from synthetic wallet | A |
| P0 | Viability rules engine + Claude explanation in user's language | A |
| P0 | Photo upload + vision grading with retake guidance | A/B |
| P0 | Live claim-form panel that fills as fields arrive (WebSocket) | B |
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
│  - push-to-talk mic button            │  - photo thumbnails with ✓ / retake     │
│  - photo upload                       │  - viability verdict card               │
│  - audio player for TTS               │  - missing docs, settlement estimate    │
└───────────────┬───────────────────────┴──────────────────────┬──────────────────┘
                │ WebSocket /ws (audio / text / photo / decision ⇄ events, JSON)          
                ▼                                               ▲
┌──────────────────────────────── FastAPI backend ─────────────────────────────────┐
│  main.py            WebSocket /ws — one Agent per connection                     │
│  agent/             state_machine.py  ← one handler per state                    │
│  services/          claude.py  sarvam.py  rules.py  settlement.py                │
│  db/                asyncpg pool, schema.sql (applied on startup)                │
│  data/              policies.json  users.json  settlement_table.json             │
│  static/audio/      pre-generated TTS for fixed bot lines                        │
└──────────────────────────────────────────────────────────────────────────────────┘
        │ Claude API (Sonnet: text + vision)   │ Sarvam API (STT + TTS)   │ Postgres (Docker)
                                                                        ▲ CloudBeaver :8978
```

### Design decisions (do not relitigate)

1. **Plain Python state machine, not LangGraph/agents.** Each state has exactly one job and
   one Claude call with a forced JSON schema. Predictable on stage.
2. **Rules decide, Claude explains.** All money math lives in `services/rules.py` and is
   unit-tested. Claude receives the computed numbers and writes the explanation. Claude
   never computes deductibles, NCB or payouts.
3. **Policies are hand-written structured JSON**, not PDFs in a vector store.
4. **One model**: latest Sonnet (`claude-sonnet-5-5`, set via `CLAUDE_MODEL`) for
   extraction, explanation and vision. Every call uses structured outputs
   (`client.messages.parse` with a Pydantic `output_format`); retry once on validation
   failure. Sonnet 5.5 rejects forced `tool_choice` and custom `temperature`, so no tool use.
5. **Language flow**: STT text (Hindi/English) → Claude works internally in English →
   Claude writes the user-facing reply in `session.language` → Sarvam TTS.
6. **Transport**: **one WebSocket per conversation** (`/ws?user_id=&language=`). Browser
   sends text, audio (base64), photos (base64) and decisions as JSON; server pushes every
   event back on the same socket. The agent keeps working state in memory and writes
   through to Postgres (sessions, messages, incidents, evidence, claims).
7. **Push-to-talk only.** No VAD, no always-on mic, no barge-in.
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

| State | Input | Does | Claude call | Emits (WS) | Next |
|---|---|---|---|---|---|
| `INTAKE` | user utterance | Extract/merge `Incident`. If required fields missing, ask one targeted question. | `extract_incident` (tool) | `transcript`, `field` ×N, `bot_message`, `audio` | self (ask) or `MATCH_POLICY` |
| `MATCH_POLICY` | Incident | Filter user's policies by vehicle reg + date in period + cover type. | none (rules) | `policy_matched` | `VIABILITY` or `NO_COVER` |
| `VIABILITY` | Incident + Policy | `rules.viability()` → numbers + verdict. Claude explains in user language. Ask "claim karna hai?" | `explain_verdict` | `viability`, `bot_message`, `audio` | `EVIDENCE` (yes) / `ADVISED_NO_CLAIM` (no) |
| `EVIDENCE` | photo | `vision.grade_photo()` against checklist. Retake or accept. Loop until required shots present. | `grade_damage_photo` (vision tool) | `photo_graded`, `bot_message`, `audio` | self or `FORM_REVIEW` |
| `FORM_REVIEW` | — | Assemble `ClaimForm`, compute missing docs, settlement estimate. Read summary aloud. | `summarise_claim` | `form_ready`, `missing_docs`, `settlement`, `bot_message`, `audio` | `FILED` on user tap |
| `FILED` | user tap | Persist, show reference number. | none | `filed` | end |

Required `Incident` fields to leave `INTAKE`: `vehicle_ref` (or vehicle type if only one
in wallet), `incident_date`, `description`, `estimated_damage_inr` (can be "unknown" →
agent asks for garage estimate or lets user say "pata nahi" and proceeds with
`VIABILITY` in "estimate pending" mode).

---

## 5. Data model

Stored in Postgres (`api/db/schema.sql`, tables listed in §11); Pydantic models in `models.py`. Synthetic seed data in `data/`.

```python
class User:           id, name, language ("hi"|"en"), phone
class Vehicle:        id, user_id, type ("2W"|"4W"), reg_no, make_model, year
class Policy:
    id, user_id, vehicle_id, insurer, policy_no
    cover_type: "comprehensive" | "third_party_only"
    period_start, period_end
    idv_inr: int                         # insured declared value
    od_premium_inr: int                  # own-damage premium (base for NCB math)
    ncb_pct: 0|20|25|35|45|50
    compulsory_deductible_inr: int       # 100 (2W) / 1000–2000 (4W) typical
    voluntary_deductible_inr: int
    addons: list["zero_dep"|"ncb_protect"|"engine_protect"|"rsa"|"consumables"]
    exclusions: list[str]                # e.g. "drunk_driving","no_valid_dl","commercial_use"
    required_documents: list[str]        # e.g. "rc","dl","policy_copy","garage_estimate","fir"
    cashless_garages: list[str]
class Incident:
    id, session_id, user_id, vehicle_id
    incident_date, location, description_en, description_original
    third_party_involved: bool, third_party_damage: bool, injuries: bool
    estimated_damage_inr: int | None, garage_estimate_uploaded: bool
    police_report_filed: bool | None
    garage_name: str | None              # in policy.cashless_garages → cashless route
    flags: list[str]                     # "drunk_driving","no_valid_dl","commercial_use",
                                         # "theft","hit_and_run" — matched against exclusions / FIR rules
class Viability:
    insurer_payout_inr, deductible_inr, depreciation_inr,
    ncb_loss_year1_inr, ncb_loss_total_inr
    verdict: "claim" | "dont_claim" | "borderline" | "not_covered"
    reasons: list[str]                   # machine codes, e.g. "NCB_LOSS_EXCEEDS_PAYOUT"
    ncb_protected: bool
    estimate_pending: bool               # no damage estimate yet; numbers are zero
class Evidence:
    id, claim_id, kind ("damage_wide"|"damage_close"|"number_plate"|"odometer"|"garage_estimate"|"dl"|"rc")
    file_path, accepted: bool, issues: list[str], confidence: float
class Claim:
    id, incident_id, policy_id, claim_type ("own_damage"|"third_party"|"both")
    status: "draft"|"filed", form: dict, missing_docs: list[str]
    settlement_days_min, settlement_days_max, reference_no
class Session:
    id, user_id, state, language, history: list[dict], created_at
```

### Synthetic seed data

`api/data/users.json` (users + vehicles) and `api/data/policies.json`:

| # | Policy | Vehicle | Key terms | Purpose |
|---|---|---|---|---|
| 1 | `POL-RAVI-2W` | Ravi's Royal Enfield Classic 350 (2022), `UP16AB4521` | comprehensive, NCB 35%, OD premium ₹3,000, deductibles ₹100 + ₹500 voluntary, no addons | Scenario 1 → `dont_claim` |
| 2 | `POL-PRIYA-4W` | Priya's Hyundai Creta (2023), `DL3CAF7788` | comprehensive, NCB 45%, OD premium ₹14,000, deductible ₹1,000, `zero_dep`, cashless at "Sharma Motors Noida" | Scenario 2 → `claim` |
| 3 | `POL-PRIYA-4W-2` | Priya's Maruti Swift (2021), `DL8CX1234` | comprehensive, NCB 50%, `ncb_protect` | Verdict flip on a small claim |
| 4 | `POL-RAVI-SCOOTY-TP` | Ravi's Honda Activa (2016), `UP16Z9001` | `third_party_only` | `NO_COVER` for own damage |

Ravi's OD premium was raised from ₹1,800 to ₹3,000, and a ₹500 voluntary deductible
added, so that Scenario 1 clearly lands on `dont_claim` (see §12).

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

Required photos: `damage_wide` (must show the number plate) for every vehicle, plus
`odometer` for 4W.

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

## 8. Sarvam integration (`services/sarvam.py`)

Checked against docs.sarvam.ai on 2026-10-28.

- **STT**: `POST https://api.sarvam.ai/speech-to-text`, header `api-subscription-key`,
  multipart `file` + `model=saaras:v4` + `language_code=unknown` (auto-detect). Returns
  `transcript` + `language_code`; the detected language becomes the session language.
  Timeout 8 s; on failure emit `stt_failed` and the user types instead.
- **TTS**: `POST https://api.sarvam.ai/text-to-speech`, JSON `{text, language_code
  (hi-IN|en-IN), model: "bulbul:v3", speaker, output_audio_codec: "mp3"}`. Returns
  base64 in `audios[0]`, sent straight to the browser in the `audio` event. Speaker from
  `SARVAM_TTS_SPEAKER` (default `shubh`; v3 voices: shubh, aditya, ritu, priya, neha, …).
- **Later**: cache TTS by `(text, lang)` hash, pre-generate fixed lines
  (`scripts/pregen_audio.py`), sentence-level TTS for long replies.

---

## 9. API contract

```
GET /users/lookup?phone=9000011111       login stand-in: wallet user + vehicles + policies
                                         (matches the last 10 digits; 404 if unknown)
WS  /ws?user_id=u_ravi&language=hi       one socket = one conversation
```

Client → server (JSON):

```
{"type": "text",     "text": "..."}
{"type": "audio",    "data": "<base64>", "mime": "audio/webm"}
{"type": "photo",    "data": "<base64>", "mime": "image/jpeg", "photo_id": "<uuid>"}
{"type": "decision", "decision": "claim" | "dont_claim" | "file"}
```

Server → client, `{"type": <name>, ...fields}`, in the order a turn typically produces them:

```
transcript       {text, language}
bot_thinking     {}                           # UI shows pulsing indicator
field            {name, value}                # one per extracted/updated incident field
policy_matched   {policy_id, insurer, policy_no, cover_type, ncb_pct, deductible_inr, addons}
viability        {...Viability}
photo_graded     {photo_id, kind, accepted, issues, retake_instruction}
form_ready       {form}
missing_docs     {docs: [..]}
settlement       {min_days, max_days, route, docs_complete}
bot_message      {text, language}             # always, before audio
audio            {data (base64 mp3), mime}
state            {state}
filed            {reference_no}
error            {code, message}
stt_failed       {}
```

Messages on one socket are handled one at a time, in arrival order.

---

## 10. Frontend (`web/`)

Next.js (App Router) + Tailwind v4. Single page, two columns on desktop, stacked on mobile.

Paytm-inspired theme (navy `#002E6E`, cyan `#00BAF2`), tokens in `app/globals.css`.

- `components/Login.tsx` — mobile-number entry (+91), calls `/users/lookup`; demo numbers
  9000011111 (Ravi, Hindi) and 9000022222 (Priya, English) as one-tap chips.
- `app/page.tsx` — header (language toggle, new claim, user, log out), then the session.
- `components/Chat.tsx` — messages, hold-to-talk mic (MediaRecorder), text input,
  photo upload in `EVIDENCE` (resized to 1600px JPEG), claim / don't-claim buttons.
- `components/ClaimPanel.tsx` — progress stepper, verdict card, the user's vehicles and
  policies (until one is matched), incident fields, policy, verdict card, photo grid with
  ✓ / retake, claim form, missing docs, settlement, File claim button.
- `lib/useClaimSocket.ts` — owns the WebSocket, reduces events into state, queues audio.

Never block the UI on audio; text appears first.

---

## 11. Repo structure

```
claim-karo/
├── README.md                   ← this file
├── docker-compose.yml          # Postgres 17 + CloudBeaver
├── docker/cloudbeaver/         # preset CloudBeaver connection (copied in on first run)
├── start.ps1 / stop.ps1        # start / stop everything
├── api/
│   ├── main.py                 # FastAPI app + WebSocket /ws
│   ├── db/                     # __init__.py (asyncpg queries), schema.sql
│   ├── agent/state_machine.py  # Agent: one per connection
│   ├── services/               # claude.py sarvam.py rules.py settlement.py
│   ├── models.py               # Pydantic
│   ├── seed.py                 # loads data/*.json into models
│   ├── data/                   # users.json policies.json settlement_table.json
│   ├── static/audio/           # pre-generated TTS
│   ├── scripts/pregen_audio.py
│   └── tests/test_rules.py
├── web/                        # Next.js app
│   ├── app/                    # layout.tsx page.tsx globals.css
│   ├── components/             # Chat.tsx ClaimPanel.tsx
│   └── lib/useClaimSocket.ts
└── docs/
    ├── DEMO_SCENARIOS.md
    └── pitch/Claim_Karo_Pitch.pptx
```

Env vars (`api/.env`): `ANTHROPIC_API_KEY`, `SARVAM_API_KEY`, `CLAUDE_MODEL`,
`SARVAM_TTS_SPEAKER`, `DATABASE_URL`, `CORS_ORIGINS` (optional). Web (`web/.env.local`, optional):
`NEXT_PUBLIC_WS_URL` (default `ws://localhost:8000/ws`), `NEXT_PUBLIC_API_URL`
(default `http://localhost:8000`).

### Running locally

Needs Docker Desktop, Python 3.13 (`py` launcher) and Node 22.

```
.\start.ps1            # Docker, frontend production build, then API and web (next start) in their own windows
.\stop.ps1             # stop everything, keep the data
.\stop.ps1 -Reset      # stop everything and delete the database + CloudBeaver volumes
```

The first run creates `api/.venv`, `api/.env` and `web/node_modules`.

| Service | URL | Login |
|---|---|---|
| App | http://localhost:3000 | — |
| API | http://localhost:8000 (WebSocket `/ws`) | — |
| CloudBeaver | http://localhost:8978 | opens anonymously with the `Claim Karo (Postgres)` connection; admin `cbadmin` / `ClaimKaro123` |
| Postgres | `localhost:5433`, db `claim_karo` | `claimkaro` / `claimkaro` |

Tables: `users`, `vehicles`, `policies` (copied from `data/*.json` on every start),
`sessions`, `messages`, `incidents` (with verdict + viability JSON), `evidence`, `claims`.
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
User (Ravi): "Signal pe bike ko taxi ne maar diya, ₹4,200 ka kharcha bata raha hai mechanic."
→ policy 1 matched → ₹4,200 − 35% depreciation (₹1,470) − ₹600 deductibles = payout
**₹2,130**; NCB loss ₹1,050 next year, **₹2,550** over three years → `dont_claim`
→ agent explains in Hindi and recommends paying out of pocket; offers to file anyway.

**Scenario 2 — Car hits divider, English, claim worth filing**
User (Priya): "Hit a divider on the expressway last night, garage says ₹38,000."
→ policy 2 (zero_dep) → payout ₹37,000 vs NCB loss ₹14,000 over three years → `claim`
→ EVIDENCE: first photo `PLATE_NOT_VISIBLE` → retake accepted
→ odometer shot → form pre-filled, missing: `dl` → settlement "7–9 days cashless if DL
uploaded today, 12–14 otherwise" → File → reference number.

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
- No business logic in `main.py`; it calls the state machine; the state machine calls services.
- Every Claude tool has a fixture test with a canned response.
- Commit small and often; `main` must always run Scenario 1.
- Log every Claude/Sarvam call with latency to `logs/` — we will tune from this.
