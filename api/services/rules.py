"""Deterministic claim rules. Pure functions, no I/O. All amounts are integer INR.

Rules decide, Claude explains: nothing in here calls a model, and nothing outside here
computes money. See README §6 for the spec these functions implement.
"""

from __future__ import annotations

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


def _has_own_damage(incident: Incident) -> bool:
    # An unknown estimate still means the user's own vehicle was damaged.
    return incident.estimated_damage_inr != 0 or "theft" in incident.flags


def _has_third_party_liability(incident: Incident) -> bool:
    return incident.third_party_damage or incident.injuries


def claim_type(incident: Incident, policy: Policy) -> ClaimType | None:
    own = _has_own_damage(incident) and policy.cover_type == "comprehensive"
    tp = _has_third_party_liability(incident)
    if own and tp:
        return "both"
    if own:
        return "own_damage"
    if tp:
        return "third_party"
    return None


def match_policy(incident: Incident, policies: list[Policy]) -> Policy | None:
    if incident.vehicle_id is None or incident.incident_date is None:
        return None
    for policy in policies:
        if policy.vehicle_id != incident.vehicle_id:
            continue
        if not policy.period_start <= incident.incident_date <= policy.period_end:
            continue
        if claim_type(incident, policy) is None:
            continue
        return policy
    return None


def fir_required(incident: Incident) -> bool:
    return _has_third_party_liability(incident) or bool(FIR_FLAGS & set(incident.flags))


def is_cashless(incident: Incident, policy: Policy) -> bool:
    if not incident.garage_name:
        return False
    wanted = incident.garage_name.strip().casefold()
    return any(g.strip().casefold() == wanted for g in policy.cashless_garages)


def vehicle_age_months(vehicle: Vehicle, as_of: date) -> int:
    # Only the model year is known, so age is measured from 1 Jan of that year.
    return max(0, (as_of.year - vehicle.year) * 12 + as_of.month - 1)


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
    if "ncb_protect" in policy.addons:
        return 0, 0
    premium = policy.od_premium_inr
    year1 = premium * policy.ncb_pct // 100
    total = year1
    no_claim = policy.ncb_pct
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
    deductible = policy.compulsory_deductible_inr + policy.voluntary_deductible_inr
    ncb_protected = "ncb_protect" in policy.addons
    reasons: list[str] = []

    def result(verdict, payout=0, depreciation=0, y1=0, total=0, **extra) -> Viability:
        return Viability(
            insurer_payout_inr=payout,
            deductible_inr=deductible,
            depreciation_inr=depreciation,
            ncb_loss_year1_inr=y1,
            ncb_loss_total_inr=total,
            verdict=verdict,
            reasons=reasons,
            ncb_protected=ncb_protected,
            **extra,
        )

    excluded = [f for f in incident.flags if f in policy.exclusions]
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
    zero_dep = "zero_dep" in policy.addons
    dep_pct = 0 if zero_dep else depreciation_pct(vehicle_age_months(vehicle, as_of))
    breakeven = _breakeven_estimate(deductible, dep_pct, total)

    if incident.estimated_damage_inr is None:
        reasons.append("ESTIMATE_PENDING")
        return result(
            "borderline",
            y1=y1,
            total=total,
            estimate_pending=True,
            breakeven_estimate_inr=breakeven,
        )

    assessed = incident.estimated_damage_inr
    if assessed > policy.idv_inr:
        assessed = policy.idv_inr
        reasons.append("ESTIMATE_CAPPED_AT_IDV")
    depreciation = assessed * dep_pct // 100
    if zero_dep:
        reasons.append("ZERO_DEP_APPLIED")
    elif depreciation:
        reasons.append("DEPRECIATION_APPLIED")
    payout = max(0, assessed - depreciation - deductible)

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


def required_documents(incident: Incident, policy: Policy) -> list[str]:
    """Every document this claim needs: the policy's list, plus an FIR if the incident needs one."""
    required = list(policy.required_documents)
    if fir_required(incident) and "fir" not in required:
        required.append("fir")
    return list(dict.fromkeys(required))


def missing_documents(incident: Incident, policy: Policy, evidence: list[Evidence]) -> list[str]:
    have = {e.kind for e in evidence if e.accepted} | WALLET_DOCS
    if incident.garage_estimate_uploaded or is_cashless(incident, policy):
        have.add("garage_estimate")
    if incident.police_report_filed:
        have.add("fir")

    return [doc for doc in required_documents(incident, policy) if doc not in have]


def required_photo_kinds(incident: Incident, vehicle: Vehicle) -> list[str]:
    # damage_wide is graded for plate visibility too, so no separate number_plate shot.
    kinds = ["damage_wide"]
    if vehicle.type == "4W":
        kinds.append("odometer")
    return kinds
