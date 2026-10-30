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
                "choice. Then explain the verdict. " + note
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
