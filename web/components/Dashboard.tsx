"use client";

import { useCallback, useEffect, useState } from "react";
import {
  fetchClaim,
  fetchDashboard,
  fileClaim,
  type ClaimDetail,
  type ClaimSummary,
  type DashboardData,
  type DocumentName,
  type Profile,
  type WalletPolicy,
} from "@/lib/api";
import { formatDate, label, VERDICT } from "@/lib/format";
import { rupees, type Language } from "@/lib/useClaimSocket";

const STATUS = {
  draft: { label: "Draft", tone: "bg-amber-50 text-amber-800 ring-amber-200" },
  filed: { label: "Filed", tone: "bg-emerald-50 text-emerald-700 ring-emerald-200" },
};

const PHOTO_LABEL: Record<string, string> = {
  damage_wide: "Vehicle and damage",
  damage_close: "Damage close-up",
  number_plate: "Number plate",
  odometer: "Odometer",
  dl: "Driving licence",
};

const docName = (d: DocumentName, language: Language) => (language === "hi" ? d.name_hindi : d.name_english);

function StatusPill({ status }: { status: ClaimSummary["claim_status"] }) {
  return (
    <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${STATUS[status].tone}`}>
      {STATUS[status].label}
    </span>
  );
}

function Section({ title, aside, children }: { title: string; aside?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

function Rows({ rows }: { rows: [string, React.ReactNode][] }) {
  return (
    <dl className="space-y-2 text-sm">
      {rows.map(([k, v]) => (
        <div key={k} className="flex justify-between gap-4">
          <dt className="shrink-0 text-muted">{k}</dt>
          <dd className="min-w-0 text-right font-medium break-words text-ink">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

// --- claims list -------------------------------------------------------------------------

function ClaimRow({ claim, active, onSelect }: { claim: ClaimSummary; active: boolean; onSelect: () => void }) {
  return (
    <button
      onClick={onSelect}
      aria-current={active}
      className={`w-full rounded-2xl border bg-white p-4 text-left shadow-sm transition ${
        active ? "border-sky ring-4 ring-sky-soft" : "border-line hover:border-sky"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-ink">
            {claim.brand} {claim.model}
          </p>
          <p className="text-xs text-muted">
            {claim.vehicle_number} · {claim.incident_date ? `Incident ${formatDate(claim.incident_date)}` : "Date not given"}
          </p>
        </div>
        <StatusPill status={claim.claim_status} />
      </div>
      <div className="mt-3 flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="text-[11px] text-muted">Expected payout</p>
          <p className="text-base font-semibold text-navy tabular-nums">{rupees(claim.expected_payout_inr)}</p>
        </div>
        <p className="text-xs text-muted">
          {claim.claim_status === "filed" ? (
            <span className="font-mono text-ink">{claim.claim_reference_number}</span>
          ) : claim.documents_missing > 0 ? (
            <span className="text-amber-700">
              {claim.documents_missing} document{claim.documents_missing > 1 ? "s" : ""} needed
            </span>
          ) : (
            "Ready to file"
          )}
        </p>
      </div>
    </button>
  );
}

// --- claim detail ------------------------------------------------------------------------

function ClaimDetailPanel({
  userId,
  sessionId,
  language,
  onBack,
  onFiled,
}: {
  userId: string;
  sessionId: string;
  language: Language;
  onBack: () => void;
  onFiled: () => void;
}) {
  const [claim, setClaim] = useState<ClaimDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filing, setFiling] = useState(false);

  useEffect(() => {
    let live = true;
    setClaim(null);
    setError(null);
    fetchClaim(userId, sessionId)
      .then((c) => live && setClaim(c))
      .catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [userId, sessionId]);

  async function file() {
    setFiling(true);
    setError(null);
    try {
      await fileClaim(userId, sessionId);
      setClaim(await fetchClaim(userId, sessionId));
      onFiled();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setFiling(false);
    }
  }

  if (!claim) {
    return (
      <div className="rounded-2xl border border-line bg-white p-6 text-sm text-muted shadow-sm">
        {error ?? "Loading claim…"}
      </div>
    );
  }

  const verdict = claim.claim_recommendation ? VERDICT[claim.claim_recommendation] : null;
  const missing = claim.documents.filter((d) => !d.is_provided);
  const formRows = Object.entries(claim.claim_form_data)
    .filter(([k, v]) => v !== null && v !== undefined && !["policyholder", "phone_number"].includes(k))
    .map(([k, v]) => [
      label(k).replace(/ inr$/i, ""),
      k.endsWith("_inr") ? rupees(v) : k.endsWith("_date") ? formatDate(String(v)) : label(String(v)),
    ]) as [string, React.ReactNode][];

  return (
    <article className="animate-fadein space-y-3">
      <button onClick={onBack} className="text-sm font-medium text-sky-dark md:hidden">
        ← All claims
      </button>

      <header className="rounded-2xl border border-line bg-white p-4 shadow-sm">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs text-muted">{label(claim.claim_type)} claim</p>
            <h2 className="mt-0.5 text-lg font-semibold text-ink">{String(claim.claim_form_data.vehicle ?? "")}</h2>
            <p className="text-xs text-muted">
              {String(claim.claim_form_data.insurer_name ?? "")} ·{" "}
              {String(claim.claim_form_data.policy_number ?? "")}
            </p>
          </div>
          <StatusPill status={claim.claim_status} />
        </div>

        {claim.claim_status === "filed" ? (
          <div className="mt-4 rounded-xl bg-navy p-4 text-white">
            <p className="text-xs opacity-70">Reference number</p>
            <p className="mt-1 font-mono text-lg font-semibold tracking-wide">{claim.claim_reference_number}</p>
            <p className="mt-1 text-xs opacity-70">Filed {claim.filed_at && formatDate(claim.filed_at)}</p>
          </div>
        ) : (
          <div className="mt-4 rounded-xl bg-amber-50 p-4">
            <p className="text-sm font-semibold text-amber-900">Not filed yet</p>
            <p className="mt-0.5 text-xs text-amber-900/80">
              Started {formatDate(claim.drafted_at)}.{" "}
              {missing.length > 0
                ? "You can file now and send the missing documents to the insurer afterwards."
                : "Everything the insurer needs is in place."}
            </p>
            <button
              onClick={file}
              disabled={filing}
              className="mt-3 w-full rounded-xl bg-sky py-2.5 text-sm font-semibold text-white transition hover:bg-sky-dark disabled:opacity-40"
            >
              {filing ? "Filing…" : "File claim"}
            </button>
          </div>
        )}
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      </header>

      {verdict && claim.viability_assessment && (
        <section className={`rounded-2xl border p-4 ${verdict.tone}`}>
          <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider opacity-70">
            <span className={`h-2 w-2 rounded-full ${verdict.dot}`} />
            Recommendation
          </p>
          <p className="mt-1 text-lg font-semibold">{verdict.label}</p>
          {claim.claim_recommendation !== "not_covered" && (
            <div className="mt-3 grid grid-cols-2 gap-3">
              <div className="rounded-xl bg-white/70 p-3">
                <p className="text-xs opacity-70">Insurer pays</p>
                <p className="mt-0.5 font-bold tabular-nums">
                  {claim.viability_assessment.estimate_pending
                    ? "—"
                    : rupees(claim.viability_assessment.insurer_payout_inr)}
                </p>
              </div>
              <div className="rounded-xl bg-white/70 p-3">
                <p className="text-xs opacity-70">No-Claim Bonus lost</p>
                <p className="mt-0.5 font-bold tabular-nums">{rupees(claim.viability_assessment.ncb_loss_total_inr)}</p>
              </div>
            </div>
          )}
        </section>
      )}

      <section className="rounded-2xl border border-line bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-baseline justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">Documents</h3>
          <p className="text-xs text-muted">
            {claim.documents.length - missing.length} of {claim.documents.length} ready
          </p>
        </div>
        {claim.documents.length === 0 ? (
          <p className="text-sm text-muted">No document checklist was saved for this claim.</p>
        ) : (
          <ul className="space-y-2">
            {claim.documents.map((d) => (
              <li key={d.document_code} className="flex items-center gap-3 text-sm">
                <span
                  aria-hidden
                  className={`grid h-5 w-5 shrink-0 place-items-center rounded-full text-[11px] font-bold ${
                    d.is_provided ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-800"
                  }`}
                >
                  {d.is_provided ? "✓" : "!"}
                </span>
                <span className="min-w-0 flex-1 text-ink">{docName(d, language)}</span>
                <span className={`text-xs ${d.is_provided ? "text-muted" : "font-medium text-amber-800"}`}>
                  {d.is_provided ? "Have it" : "Needed"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-2xl border border-line bg-white p-4 shadow-sm">
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">Claim form</h3>
        <Rows rows={formRows} />
        {claim.expected_settlement_days_min !== null && (
          <p className="mt-4 border-t border-line pt-3 text-sm text-muted">
            Expected settlement in{" "}
            <span className="font-semibold text-ink">
              {claim.expected_settlement_days_min}–{claim.expected_settlement_days_max} days
            </span>
          </p>
        )}
      </section>

      {claim.evidence.length > 0 && (
        <section className="rounded-2xl border border-line bg-white p-4 shadow-sm">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">Photos checked</h3>
          <ul className="space-y-2 text-sm">
            {claim.evidence.map((e) => (
              <li key={e.id} className="flex items-center justify-between gap-3">
                <span className="text-ink">{PHOTO_LABEL[e.evidence_type] ?? label(e.evidence_type)}</span>
                <span className={`text-xs font-medium ${e.is_accepted ? "text-emerald-700" : "text-red-600"}`}>
                  {e.is_accepted ? "Accepted" : `Retake: ${[...e.detail_mismatches, ...e.quality_issues].map(label).join(", ").toLowerCase()}`}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {claim.messages.length > 0 && (
        <details className="group rounded-2xl border border-line bg-white p-4 shadow-sm">
          <summary className="flex cursor-pointer list-none items-center justify-between text-xs font-semibold uppercase tracking-wider text-muted">
            Conversation ({claim.messages.length})
            <span className="transition group-open:rotate-180">▾</span>
          </summary>
          <ol className="mt-3 space-y-2">
            {claim.messages.map((m, i) => (
              <li key={i} className={`flex ${m.sender_role === "user" ? "justify-end" : "justify-start"}`}>
                <p
                  className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${
                    m.sender_role === "user" ? "bg-navy text-white" : "bg-canvas text-ink"
                  }`}
                >
                  {m.message_text}
                </p>
              </li>
            ))}
          </ol>
        </details>
      )}
    </article>
  );
}

// --- policies ----------------------------------------------------------------------------

function PolicyCard({ policy, language }: { policy: WalletPolicy; language: Language }) {
  const active = new Date(policy.coverage_end_date) >= new Date();
  const comprehensive = policy.coverage_type === "comprehensive";
  return (
    <article className="flex flex-col gap-3 rounded-2xl border border-line bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-ink">
            {policy.vehicle.brand} {policy.vehicle.model}
          </p>
          <p className="text-xs text-muted">
            {policy.vehicle.vehicle_number} · {policy.vehicle.vehicle_type === "2W" ? "Two-wheeler" : "Car"} ·{" "}
            {policy.vehicle.manufacture_year}
          </p>
        </div>
        <span
          className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
            comprehensive ? "bg-sky-soft text-navy" : "bg-canvas text-muted"
          }`}
        >
          {comprehensive ? "Comprehensive" : "Third-party"}
        </span>
      </div>

      <div>
        <p className="text-sm font-medium text-ink">{policy.insurer_name}</p>
        <p className="font-mono text-xs text-muted">{policy.policy_number}</p>
      </div>

      <Rows
        rows={[
          ["Valid till", <span className={active ? "" : "text-red-600"}>{formatDate(policy.coverage_end_date)}</span>],
          ["No-Claim Bonus", `${policy.no_claim_bonus_pct}%`],
          ...(comprehensive
            ? ([
                ["Insured value (IDV)", rupees(policy.insured_declared_value_inr)],
                ["Deductible", rupees(policy.deductible_inr)],
              ] as [string, React.ReactNode][])
            : []),
        ]}
      />

      {policy.add_on_covers.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {policy.add_on_covers.map((a) => (
            <span key={a} className="rounded-full bg-canvas px-2.5 py-1 text-xs text-ink">
              {label(a)}
            </span>
          ))}
        </div>
      )}

      <div className="mt-auto border-t border-line pt-3">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">Documents for a claim</p>
        <p className="mt-1 text-sm text-ink">
          {policy.required_documents.map((d) => docName(d, language)).join(" · ")}
        </p>
      </div>
    </article>
  );
}

// --- page --------------------------------------------------------------------------------

export default function Dashboard({
  profile,
  language,
  onNewClaim,
}: {
  profile: Profile;
  language: Language;
  onNewClaim: () => void;
}) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const load = useCallback(() => {
    fetchDashboard(profile.id)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e: Error) => setError(e.message));
  }, [profile.id]);

  useEffect(load, [load]);

  const drafts = data?.claims.filter((c) => c.claim_status === "draft").length ?? 0;
  const filed = (data?.claims.length ?? 0) - drafts;
  const uninsured = profile.vehicles.filter((v) => !v.policy);

  return (
    <div className="grid gap-6 py-6 md:grid-cols-[minmax(0,1fr)_400px] md:items-start">
      <div className={`min-w-0 space-y-8 ${selected ? "hidden md:block" : ""}`}>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-navy">Hi {profile.full_name.split(" ")[0]}</h1>
            <p className="mt-1 text-sm text-muted">Your policies and claims in one place.</p>
          </div>
          <button
            onClick={onNewClaim}
            className="rounded-xl bg-sky px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-dark"
          >
            Start a new claim
          </button>
        </div>

        {error && (
          <p className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}{" "}
            <button onClick={load} className="font-semibold underline">
              Try again
            </button>
          </p>
        )}

        <Section
          title="Claims"
          aside={data && data.claims.length > 0 && <p className="text-xs text-muted">{drafts} draft · {filed} filed</p>}
        >
          {!data ? (
            <p className="text-sm text-muted">Loading your claims…</p>
          ) : data.claims.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-line bg-white p-6 text-center">
              <p className="text-sm font-medium text-ink">No claims yet</p>
              <p className="mt-1 text-sm text-muted">
                Describe what happened to your vehicle and we&apos;ll tell you if a claim is worth it.
              </p>
            </div>
          ) : (
            <div className="grid gap-3 lg:grid-cols-2">
              {data.claims.map((c) => (
                <ClaimRow
                  key={c.session_id}
                  claim={c}
                  active={c.session_id === selected}
                  onSelect={() => setSelected(c.session_id)}
                />
              ))}
            </div>
          )}
        </Section>

        <Section title="Policies">
          {data && (
            <div className="grid gap-3 lg:grid-cols-2">
              {data.policies.map((p) => (
                <PolicyCard key={p.id} policy={p} language={language} />
              ))}
            </div>
          )}
          {uninsured.length > 0 && (
            <p className="text-sm text-muted">
              No active policy for {uninsured.map((v) => `${v.brand} ${v.model} (${v.vehicle_number})`).join(", ")}.
            </p>
          )}
        </Section>
      </div>

      <aside className={`min-w-0 md:sticky md:top-20 ${selected ? "" : "hidden md:block"}`}>
        {selected ? (
          <ClaimDetailPanel
            userId={profile.id}
            sessionId={selected}
            language={language}
            onBack={() => setSelected(null)}
            onFiled={load}
          />
        ) : (
          <div className="rounded-2xl border border-dashed border-line p-6 text-center text-sm text-muted">
            Select a claim to see its details, documents and conversation.
          </div>
        )}
      </aside>
    </div>
  );
}
