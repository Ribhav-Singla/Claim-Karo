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


def required_photo_kinds(policy: Policy, vehicle: Vehicle) -> list[str]:
    # damage_wide is read for the number plate too, so no separate number_plate shot.
    kinds = ["damage_wide"]
    if vehicle.vehicle_type == "4W":
        kinds.append("odometer")
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
