from datetime import date

import pytest

from models import Evidence, Incident
from seed import load_wallet
from services import rules, settlement

W = load_wallet()
RAVI_BIKE = W.vehicles["v_ravi_bike"]
RAVI_SCOOTY = W.vehicles["v_ravi_scooty"]
CRETA = W.vehicles["v_priya_creta"]
SWIFT = W.vehicles["v_priya_swift"]
P_RAVI = W.policies["POL-RAVI-2W"]
P_PRIYA = W.policies["POL-PRIYA-4W"]
P_PRIYA_PROTECT = W.policies["POL-PRIYA-4W-2"]
P_RAVI_TP = W.policies["POL-RAVI-SCOOTY-TP"]

DEMO_DAY = date(2026, 10, 24)


def incident(vehicle_id: str, **kw) -> Incident:
    kw.setdefault("incident_date", DEMO_DAY)
    return Incident(vehicle_id=vehicle_id, **kw)


def ev(kind: str, accepted: bool = True) -> Evidence:
    return Evidence(id=f"e_{kind}", kind=kind, file_path=f"/tmp/{kind}.jpg", accepted=accepted)


# --- Demo scenarios (README §12) -------------------------------------------------------


def test_scenario1_ravi_scrape_dont_claim():
    inc = incident("v_ravi_bike", estimated_damage_inr=4200, third_party_involved=True)
    assert rules.match_policy(inc, W.policies_for("u_ravi")) == P_RAVI

    v = rules.viability(inc, P_RAVI, RAVI_BIKE)
    assert v.depreciation_inr == 1470  # 4y9m old -> 35%
    assert v.deductible_inr == 600
    assert v.insurer_payout_inr == 2130
    assert v.ncb_loss_year1_inr == 1050  # 35% of 3,000
    assert v.ncb_loss_total_inr == 2550  # + (45-20)% + (50-25)%
    assert v.verdict == "dont_claim"
    assert "NCB_LOSS_EXCEEDS_PAYOUT" in v.reasons
    assert "DEPRECIATION_APPLIED" in v.reasons
    assert not rules.fir_required(inc)


def test_scenario2_priya_divider_claim():
    inc = incident("v_priya_creta", estimated_damage_inr=38000, garage_name="Sharma Motors Noida")
    assert rules.match_policy(inc, W.policies_for("u_priya")) == P_PRIYA

    v = rules.viability(inc, P_PRIYA, CRETA)
    assert v.insurer_payout_inr == 37000
    assert v.depreciation_inr == 0
    assert v.ncb_loss_year1_inr == 6300
    assert v.ncb_loss_total_inr == 14000
    assert v.verdict == "claim"
    assert "ZERO_DEP_APPLIED" in v.reasons
    assert rules.claim_type(inc, P_PRIYA) == "own_damage"

    assert rules.required_photo_kinds(inc, CRETA) == ["damage_wide", "odometer"]
    evidence = [ev("damage_wide", accepted=False), ev("damage_wide"), ev("odometer")]
    missing = rules.missing_documents(inc, P_PRIYA, evidence)
    assert missing == ["dl"]

    assert rules.is_cashless(inc, P_PRIYA)
    s_now = settlement.estimate("own_damage", cashless=True, docs_complete=True)
    s_later = settlement.estimate("own_damage", cashless=True, docs_complete=False)
    assert (s_now.min_days, s_now.max_days) == (7, 9)
    assert (s_later.min_days, s_later.max_days) == (12, 14)


def test_ncb_protect_flips_small_claim_to_claim():
    inc = incident("v_priya_swift", estimated_damage_inr=6000)
    v = rules.viability(inc, P_PRIYA_PROTECT, SWIFT)
    assert v.ncb_protected
    assert v.ncb_loss_year1_inr == v.ncb_loss_total_inr == 0
    assert v.verdict == "claim"
    assert "NCB_PROTECTED" in v.reasons


def test_same_small_claim_without_protect_is_dont_claim():
    no_protect = P_PRIYA_PROTECT.model_copy(update={"addons": []})
    v = rules.viability(incident("v_priya_swift", estimated_damage_inr=6000), no_protect, SWIFT)
    assert v.verdict == "dont_claim"


def test_tp_only_policy_gives_no_cover_for_own_damage():
    inc = incident("v_ravi_scooty", estimated_damage_inr=3000)
    assert rules.claim_type(inc, P_RAVI_TP) is None
    assert rules.match_policy(inc, W.policies_for("u_ravi")) is None
    v = rules.viability(inc, P_RAVI_TP, RAVI_SCOOTY)
    assert v.verdict == "not_covered"
    assert v.reasons == ["NO_APPLICABLE_COVER"]


# --- match_policy ----------------------------------------------------------------------


def test_match_policy_rejects_date_outside_period():
    inc = incident("v_priya_creta", estimated_damage_inr=38000, incident_date=date(2027, 2, 1))
    assert rules.match_policy(inc, W.policies_for("u_priya")) is None


def test_match_policy_needs_vehicle_and_date():
    assert (
        rules.match_policy(Incident(estimated_damage_inr=1000), list(W.policies.values())) is None
    )
    inc = Incident(vehicle_id="v_priya_creta", estimated_damage_inr=1000)
    assert rules.match_policy(inc, list(W.policies.values())) is None


def test_tp_only_policy_matches_third_party_incident():
    inc = incident("v_ravi_scooty", estimated_damage_inr=3000, third_party_damage=True)
    assert rules.match_policy(inc, W.policies_for("u_ravi")) == P_RAVI_TP
    v = rules.viability(inc, P_RAVI_TP, RAVI_SCOOTY)
    assert v.verdict == "claim"
    assert {"THIRD_PARTY_LIABILITY", "OWN_DAMAGE_NOT_COVERED", "FIR_REQUIRED"} <= set(v.reasons)


# --- claim_type / FIR ------------------------------------------------------------------


@pytest.mark.parametrize(
    "kw, expected",
    [
        ({"estimated_damage_inr": 5000}, "own_damage"),
        ({"estimated_damage_inr": None}, "own_damage"),
        ({"estimated_damage_inr": 5000, "third_party_damage": True}, "both"),
        ({"estimated_damage_inr": 5000, "injuries": True}, "both"),
        ({"estimated_damage_inr": 0, "third_party_damage": True}, "third_party"),
        ({"estimated_damage_inr": 0}, None),
    ],
)
def test_claim_type(kw, expected):
    assert rules.claim_type(incident("v_priya_creta", **kw), P_PRIYA) == expected


@pytest.mark.parametrize(
    "kw, expected",
    [
        ({}, False),
        ({"third_party_involved": True}, False),
        ({"third_party_damage": True}, True),
        ({"injuries": True}, True),
        ({"flags": ["theft"]}, True),
        ({"flags": ["hit_and_run"]}, True),
    ],
)
def test_fir_required(kw, expected):
    assert rules.fir_required(incident("v_priya_creta", **kw)) is expected


# --- viability edge cases --------------------------------------------------------------


def test_exclusion_makes_not_covered():
    inc = incident("v_priya_creta", estimated_damage_inr=38000, flags=["drunk_driving"])
    v = rules.viability(inc, P_PRIYA, CRETA)
    assert v.verdict == "not_covered"
    assert v.reasons == ["EXCLUSION_DRUNK_DRIVING"]
    assert v.insurer_payout_inr == 0


def test_flag_not_in_policy_exclusions_is_ignored():
    inc = incident("v_ravi_scooty", third_party_damage=True, flags=["commercial_use"])
    assert rules.viability(inc, P_RAVI_TP, RAVI_SCOOTY).verdict == "claim"


def test_payout_below_deductible():
    v = rules.viability(incident("v_priya_creta", estimated_damage_inr=800), P_PRIYA, CRETA)
    assert v.insurer_payout_inr == 0
    assert v.verdict == "dont_claim"
    assert "PAYOUT_BELOW_DEDUCTIBLE" in v.reasons


def test_estimate_capped_at_idv():
    inc = incident("v_priya_creta", estimated_damage_inr=2_000_000)
    v = rules.viability(inc, P_PRIYA, CRETA)
    assert v.insurer_payout_inr == P_PRIYA.idv_inr - 1000
    assert "ESTIMATE_CAPPED_AT_IDV" in v.reasons


def test_borderline_band():
    # Priya: loss total 14,000; borderline if 14,000 < payout <= 17,500.
    v = rules.viability(incident("v_priya_creta", estimated_damage_inr=17000), P_PRIYA, CRETA)
    assert v.insurer_payout_inr == 16000
    assert v.verdict == "borderline"
    v = rules.viability(incident("v_priya_creta", estimated_damage_inr=15000), P_PRIYA, CRETA)
    assert v.verdict == "dont_claim"  # payout 14,000 == loss
    v = rules.viability(incident("v_priya_creta", estimated_damage_inr=18501), P_PRIYA, CRETA)
    assert v.verdict == "claim"


def test_estimate_pending_mode():
    inc = incident("v_ravi_bike", estimated_damage_inr=None)
    v = rules.viability(inc, P_RAVI, RAVI_BIKE)
    assert v.estimate_pending
    assert v.verdict == "borderline"
    assert "ESTIMATE_PENDING" in v.reasons
    assert v.ncb_loss_total_inr == 2550
    assert v.insurer_payout_inr == 0


def test_breakeven_estimate_is_the_tipping_point():
    v = rules.viability(incident("v_ravi_bike", estimated_damage_inr=4200), P_RAVI, RAVI_BIKE)
    be = v.breakeven_estimate_inr
    below = rules.viability(incident("v_ravi_bike", estimated_damage_inr=be - 1), P_RAVI, RAVI_BIKE)
    at = rules.viability(incident("v_ravi_bike", estimated_damage_inr=be), P_RAVI, RAVI_BIKE)
    assert below.insurer_payout_inr <= v.ncb_loss_total_inr
    assert at.insurer_payout_inr > v.ncb_loss_total_inr


def test_both_claim_type_adds_reason():
    inc = incident("v_priya_creta", estimated_damage_inr=38000, third_party_damage=True)
    v = rules.viability(inc, P_PRIYA, CRETA)
    assert v.verdict == "claim"
    assert {"THIRD_PARTY_ALSO_INVOLVED", "FIR_REQUIRED"} <= set(v.reasons)


# --- NCB math --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ncb, y1, total",
    [
        (0, 0, 0),
        (20, 2000, 2000 + 500 + 1000),  # 25-20, 35-25
        (25, 2500, 2500 + 1500 + 2000),  # 35-20, 45-25
        (35, 3500, 3500 + 2500 + 2500),  # 45-20, 50-25
        (45, 4500, 4500 + 3000 + 2500),  # 50-20, 50-25
        (50, 5000, 5000 + 3000 + 2500),
    ],
)
def test_ncb_loss_ladder(ncb, y1, total):
    policy = P_PRIYA.model_copy(update={"ncb_pct": ncb, "od_premium_inr": 10000, "addons": []})
    assert rules.ncb_loss(policy) == (y1, total)


def test_readme_headline_example():
    # §1: ₹4,000 scrape, ₹1,000 deductible, 35% NCB on ₹10,000 OD premium.
    policy = P_PRIYA.model_copy(update={"ncb_pct": 35, "od_premium_inr": 10000})
    v = rules.viability(incident("v_priya_creta", estimated_damage_inr=4000), policy, CRETA)
    assert v.insurer_payout_inr == 3000
    assert v.ncb_loss_year1_inr == 3500
    assert v.verdict == "dont_claim"


@pytest.mark.parametrize(
    "months, pct",
    [
        (0, 0),
        (5, 0),
        (6, 5),
        (11, 5),
        (12, 10),
        (24, 15),
        (36, 25),
        (48, 35),
        (59, 35),
        (60, 45),
        (200, 45),
    ],
)
def test_depreciation_pct(months, pct):
    assert rules.depreciation_pct(months) == pct


def test_vehicle_age_months():
    assert rules.vehicle_age_months(RAVI_BIKE, date(2026, 10, 24)) == 57
    assert rules.vehicle_age_months(RAVI_BIKE, date(2022, 1, 5)) == 0
    assert rules.vehicle_age_months(RAVI_BIKE, date(2021, 6, 1)) == 0


# --- documents / photos ----------------------------------------------------------------


def test_missing_docs_reimbursement_needs_garage_estimate():
    inc = incident("v_priya_creta", estimated_damage_inr=38000, garage_name="Some Local Garage")
    assert not rules.is_cashless(inc, P_PRIYA)
    assert rules.missing_documents(inc, P_PRIYA, []) == ["dl", "garage_estimate"]
    inc.garage_estimate_uploaded = True
    assert rules.missing_documents(inc, P_PRIYA, [ev("dl")]) == []


def test_missing_docs_adds_fir_when_required():
    inc = incident("v_priya_creta", estimated_damage_inr=38000, third_party_damage=True)
    assert "fir" in rules.missing_documents(inc, P_PRIYA, [])
    inc.police_report_filed = True
    assert "fir" not in rules.missing_documents(inc, P_PRIYA, [])


def test_missing_docs_ignores_rejected_evidence():
    inc = incident("v_priya_creta", estimated_damage_inr=38000, garage_name="Sharma Motors Noida")
    assert rules.missing_documents(inc, P_PRIYA, [ev("dl", accepted=False)]) == ["dl"]


def test_cashless_garage_match_is_case_insensitive():
    inc = incident("v_priya_creta", garage_name="  sharma motors noida ")
    assert rules.is_cashless(inc, P_PRIYA)
    assert not rules.is_cashless(incident("v_priya_creta"), P_PRIYA)


def test_required_photo_kinds_2w():
    assert rules.required_photo_kinds(incident("v_ravi_bike"), RAVI_BIKE) == ["damage_wide"]


# --- settlement table ------------------------------------------------------------------


@pytest.mark.parametrize("ctype", ["own_damage", "third_party", "both"])
@pytest.mark.parametrize("cashless", [True, False])
@pytest.mark.parametrize("complete", [True, False])
def test_settlement_table_is_complete(ctype, cashless, complete):
    s = settlement.estimate(ctype, cashless, complete)
    assert 0 < s.min_days <= s.max_days
