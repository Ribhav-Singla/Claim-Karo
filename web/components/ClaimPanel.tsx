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
