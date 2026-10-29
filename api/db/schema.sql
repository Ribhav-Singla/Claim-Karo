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
