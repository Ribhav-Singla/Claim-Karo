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
