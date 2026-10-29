-- Applied on every backend start; every statement is idempotent.

-- Synthetic wallet, copied from data/*.json on startup (the JSON stays the source of truth).
CREATE TABLE IF NOT EXISTS users (
    id          text PRIMARY KEY,
    name        text NOT NULL,
    language    text NOT NULL,
    phone       text NOT NULL
);

CREATE TABLE IF NOT EXISTS vehicles (
    id          text PRIMARY KEY,
    user_id     text NOT NULL REFERENCES users(id),
    type        text NOT NULL,
    reg_no      text NOT NULL,
    make_model  text NOT NULL,
    year        int  NOT NULL
);

CREATE TABLE IF NOT EXISTS policies (
    id                         text PRIMARY KEY,
    user_id                    text NOT NULL REFERENCES users(id),
    vehicle_id                 text NOT NULL REFERENCES vehicles(id),
    insurer                    text NOT NULL,
    policy_no                  text NOT NULL,
    cover_type                 text NOT NULL,
    period_start               date NOT NULL,
    period_end                 date NOT NULL,
    idv_inr                    int  NOT NULL,
    od_premium_inr             int  NOT NULL,
    ncb_pct                    int  NOT NULL,
    compulsory_deductible_inr  int  NOT NULL,
    voluntary_deductible_inr   int  NOT NULL,
    addons                     jsonb NOT NULL DEFAULT '[]',
    exclusions                 jsonb NOT NULL DEFAULT '[]',
    cashless_garages           jsonb NOT NULL DEFAULT '[]'
);

-- Every document an insurer can ask for (copied from data/documents.json on startup).
-- Codes match services/rules.py and evidence kinds.
CREATE TABLE IF NOT EXISTS documents (
    code     text PRIMARY KEY,
    name_en  text NOT NULL,
    name_hi  text NOT NULL
);

-- Documents each policy asks for on every claim (copied from data/policies.json on startup).
CREATE TABLE IF NOT EXISTS policy_required_documents (
    policy_id      text NOT NULL REFERENCES policies(id) ON DELETE CASCADE,
    document_code  text NOT NULL REFERENCES documents(code),
    PRIMARY KEY (policy_id, document_code)
);

-- One row per WebSocket conversation.
CREATE TABLE IF NOT EXISTS sessions (
    id          text PRIMARY KEY,
    user_id     text NOT NULL REFERENCES users(id),
    state       text NOT NULL,
    language    text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
    id          bigserial PRIMARY KEY,
    session_id  text NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role        text NOT NULL,              -- 'user' | 'bot'
    text        text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS incidents (
    session_id            text PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    user_id               text NOT NULL REFERENCES users(id),
    vehicle_id            text REFERENCES vehicles(id),
    policy_id             text REFERENCES policies(id),
    incident_date         date,
    location              text,
    description_en        text,
    description_original  text,
    third_party_involved  boolean NOT NULL DEFAULT false,
    third_party_damage    boolean NOT NULL DEFAULT false,
    injuries              boolean NOT NULL DEFAULT false,
    estimated_damage_inr  int,
    garage_name           text,
    police_report_filed   boolean,
    flags                 jsonb NOT NULL DEFAULT '[]',
    verdict               text,
    viability             jsonb,
    updated_at            timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS evidence (
    id          text PRIMARY KEY,
    session_id  text NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    kind        text NOT NULL,
    accepted    boolean NOT NULL,
    issues      jsonb NOT NULL DEFAULT '[]',
    confidence  real NOT NULL DEFAULT 0,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS claims (
    session_id           text PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    policy_id            text NOT NULL REFERENCES policies(id),
    claim_type           text NOT NULL,
    status               text NOT NULL DEFAULT 'draft',   -- 'draft' | 'filed'
    form                 jsonb NOT NULL,
    settlement_days_min  int,
    settlement_days_max  int,
    reference_no         text UNIQUE,
    created_at           timestamptz NOT NULL DEFAULT now(),
    filed_at             timestamptz
);

-- One claim's document checklist: every document it needs, and whether we already have it.
CREATE TABLE IF NOT EXISTS claim_documents (
    session_id     text NOT NULL REFERENCES claims(session_id) ON DELETE CASCADE,
    document_code  text NOT NULL REFERENCES documents(code),
    provided       boolean NOT NULL DEFAULT false,
    PRIMARY KEY (session_id, document_code)
);
