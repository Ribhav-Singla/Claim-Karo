"""Pydantic v2 models shared by the API, agent graph and services. See README §5."""

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
]


class Document(BaseModel):
    code: str
    name_en: str
    name_hi: str


class User(BaseModel):
    id: str
    name: str
    language: Language
    phone: str


class Vehicle(BaseModel):
    id: str
    user_id: str
    type: VehicleType
    reg_no: str
    make_model: str
    year: int


class Policy(BaseModel):
    id: str
    user_id: str
    vehicle_id: str
    insurer: str
    policy_no: str
    cover_type: CoverType
    period_start: date
    period_end: date
    idv_inr: int
    od_premium_inr: int
    ncb_pct: NcbPct
    compulsory_deductible_inr: int
    voluntary_deductible_inr: int = 0
    addons: list[Addon] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    required_documents: list[str] = Field(default_factory=list)
    cashless_garages: list[str] = Field(default_factory=list)


class Incident(BaseModel):
    id: str | None = None
    session_id: str | None = None
    user_id: str | None = None
    vehicle_id: str | None = None
    incident_date: date | None = None
    location: str | None = None
    description_en: str | None = None
    description_original: str | None = None
    third_party_involved: bool = False
    third_party_damage: bool = False
    injuries: bool = False
    estimated_damage_inr: int | None = None
    garage_estimate_uploaded: bool = False
    police_report_filed: bool | None = None
    garage_name: str | None = None
    # Exclusion / FIR triggers: drunk_driving, no_valid_dl, commercial_use, theft, hit_and_run
    flags: list[str] = Field(default_factory=list)


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
    kind: EvidenceKind
    file_path: str
    accepted: bool
    issues: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class Claim(BaseModel):
    id: str
    incident_id: str
    policy_id: str
    claim_type: ClaimType
    status: Literal["draft", "filed"] = "draft"
    form: dict = Field(default_factory=dict)
    missing_docs: list[str] = Field(default_factory=list)
    settlement_days_min: int | None = None
    settlement_days_max: int | None = None
    reference_no: str | None = None


class Session(BaseModel):
    id: str
    user_id: str
    state: SessionState = "INTAKE"
    language: Language
    history: list[dict] = Field(default_factory=list)
    created_at: datetime
