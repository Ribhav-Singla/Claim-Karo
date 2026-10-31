"use client";

import { useCallback, useEffect, useState } from "react";
import {
  API_URL,
  deleteClaim,
  fetchClaim,
  fetchDashboard,
  fileClaim,
  type ClaimDetail,
  type ClaimSummary,
  type DashboardData,
  type DocumentName,
  type Profile,
  type Stage,
  type WalletPolicy,
} from "@/lib/api";
import { formatDate, label, VERDICT } from "@/lib/format";
import { rupees, type Language } from "@/lib/useClaim";

// Where each claim stands, by its conversation stage.
const STAGE: Record<Stage, { label: string; tone: string }> = {
  INTAKE: { label: "Details pending", tone: "bg-amber-50 text-amber-800 ring-amber-200" },
  VIABILITY: { label: "Decision pending", tone: "bg-sky-soft text-navy ring-sky/30" },
  EVIDENCE: { label: "Photos pending", tone: "bg-sky-soft text-navy ring-sky/30" },
  FORM_REVIEW: { label: "Ready to file", tone: "bg-violet-50 text-violet-800 ring-violet-200" },
  FILED: { label: "Filed", tone: "bg-emerald-50 text-emerald-700 ring-emerald-200" },
  NO_COVER: { label: "Not covered", tone: "bg-canvas text-muted ring-line" },
  ADVISED_NO_CLAIM: { label: "Not claimed", tone: "bg-canvas text-muted ring-line" },
  CANCELLED: { label: "Cancelled", tone: "bg-canvas text-muted ring-line" },
};

const PHOTO_LABEL: Record<string, string> = {
  damage_wide: "Vehicle and damage",
  damage_close: "Damage close-up",
  number_plate: "Number plate",
  odometer: "Odometer",
  dl: "Driving licence",
};

const docName = (d: DocumentName, language: Language) => (language === "hi" ? d.name_hindi : d.name_english);

const vehicleOf = (c: ClaimSummary) => (c.brand ? `${c.brand} ${c.model}` : "Vehicle not given yet");

// What the claim is about: the English summary, or else the user's own first words.
const titleOf = (c: ClaimSummary) => c.description_english ?? c.first_user_message ?? "Claim conversation";

function timeAgo(iso: string | null) {
  if (!iso) return "";
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  return formatDate(iso);
}

function StagePill({ stage }: { stage: Stage }) {
  return (
    <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${STAGE[stage].tone}`}>
      {STAGE[stage].label}
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

const TrashIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v6M14 11v6" />
  </svg>
);

// Delete asks once more before it removes the claim and its whole conversation.
function DeleteButton({ onDelete, compact }: { onDelete: () => Promise<void>; compact?: boolean }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  if (!confirming) {
    return (
      <button
        onClick={(e) => {
          e.stopPropagation();
          setConfirming(true);
        }}
        title="Delete this claim"
        aria-label="Delete this claim"
        className={`flex items-center gap-1.5 rounded-xl text-sm font-medium text-muted transition hover:bg-red-50 hover:text-red-700 ${
          compact ? "p-2" : "border border-line px-3 py-2.5"
        }`}
      >
        <TrashIcon />
        {!compact && "Delete"}
      </button>
    );
  }
  return (
    <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
      <span className="text-xs text-red-700">Delete for good?</span>
      <button
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            await onDelete();
          } finally {
            setBusy(false);
            setConfirming(false);
          }
        }}
        className="rounded-lg bg-red-600 px-2.5 py-1.5 text-xs font-semibold text-white transition hover:bg-red-700 disabled:opacity-50"
      >
        {busy ? "Deleting…" : "Delete"}
      </button>
      <button onClick={() => setConfirming(false)} className="rounded-lg px-2 py-1.5 text-xs font-medium text-muted hover:text-ink">
        Keep
      </button>
    </div>
  );
}

// --- claims list -------------------------------------------------------------------------

function ClaimRow({
  claim,
  active,
  onSelect,
  onResume,
  onDelete,
}: {
  claim: ClaimSummary;
  active: boolean;
  onSelect: () => void;
  onResume: () => void;
  onDelete: () => Promise<void>;
}) {
  const payout = claim.viability_assessment?.estimate_pending ? null : claim.expected_payout_inr;
  return (
    <article
      onClick={onSelect}
      aria-current={active}
      className={`cursor-pointer rounded-2xl border bg-white p-4 shadow-sm transition ${
        active ? "border-sky ring-4 ring-sky-soft" : "border-line hover:border-sky"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-ink">{vehicleOf(claim)}</p>
          <p className="truncate text-xs text-muted">{titleOf(claim)}</p>
        </div>
        <StagePill stage={claim.conversation_stage} />
      </div>

      <div className="mt-3 flex flex-wrap items-end justify-between gap-2">
        <div>
          {claim.conversation_stage === "FILED" ? (
            <>
              <p className="text-[11px] text-muted">Reference</p>
              <p className="font-mono text-sm font-semibold text-ink">{claim.claim_reference_number}</p>
              <p className="mt-0.5 text-[11px] font-medium text-emerald-700">● Tracking status</p>
            </>
          ) : (
            <>
              <p className="text-[11px] text-muted">{payout !== null ? "Expected payout" : "Last activity"}</p>
              <p className="text-sm font-semibold text-navy tabular-nums">
                {payout !== null ? rupees(payout) : timeAgo(claim.last_activity_at ?? claim.started_at)}
              </p>
            </>
          )}
        </div>
        <div className="flex items-center gap-1">
          {claim.deletable && <DeleteButton compact onDelete={onDelete} />}
          {claim.resumable && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onResume();
              }}
              className="rounded-xl bg-sky px-3.5 py-2 text-xs font-semibold text-white transition hover:bg-sky-dark"
            >
              Continue →
            </button>
          )}
        </div>
      </div>
    </article>
  );
}

// --- claim detail ------------------------------------------------------------------------

function ClaimDetailPanel({
  userId,
  sessionId,
  language,
  onBack,
  onChanged,
  onResume,
  onDelete,
}: {
  userId: string;
  sessionId: string;
  language: Language;
  onBack: () => void;
  onChanged: () => void;
  onResume: () => void;
  onDelete: () => Promise<void>;
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
      onChanged();
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
  const formRows = Object.entries(claim.claim_form_data ?? {})
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
            <p className="text-xs text-muted">
              {claim.claim_type ? `${label(claim.claim_type)} claim` : `Started ${formatDate(claim.started_at)}`}
            </p>
            <h2 className="mt-0.5 text-lg font-semibold text-ink">{vehicleOf(claim)}</h2>
            <p className="text-xs text-muted">
              {claim.insurer_name ? `${claim.insurer_name} · ${claim.policy_number}` : titleOf(claim)}
            </p>
          </div>
          <StagePill stage={claim.conversation_stage} />
        </div>

        {claim.claim_status === "filed" ? (
          <div className="mt-4 rounded-xl bg-navy p-4 text-white">
            <p className="text-xs opacity-70">Reference number</p>
            <p className="mt-1 font-mono text-lg font-semibold tracking-wide">{claim.claim_reference_number}</p>
            <p className="mt-1 text-xs opacity-70">Filed {claim.filed_at && formatDate(claim.filed_at)}</p>
            <p className="mt-2 text-xs opacity-80">● Status tracking on. We'll let you know when it changes.</p>
          </div>
        ) : (
          <div className="mt-4 space-y-3 rounded-xl bg-canvas p-4">
            <p className="text-xs text-muted">
              {claim.claim_status === "draft"
                ? missing.length > 0
                  ? "Ready to file. You can send the missing documents to the insurer afterwards."
                  : "Ready to file. Everything the insurer needs is in place."
                : claim.resumable
                  ? "Not finished yet. Continue where you left off, or delete it if you don't need it."
                  : "This conversation is closed."}
            </p>
            <div className="flex gap-2">
              {claim.claim_status === "draft" ? (
                <button
                  onClick={file}
                  disabled={filing}
                  className="flex-1 rounded-xl bg-sky py-2.5 text-sm font-semibold text-white transition hover:bg-sky-dark disabled:opacity-40"
                >
                  {filing ? "Filing…" : "File claim"}
                </button>
              ) : (
                claim.resumable && (
                  <button
                    onClick={onResume}
                    className="flex-1 rounded-xl bg-sky py-2.5 text-sm font-semibold text-white transition hover:bg-sky-dark"
                  >
                    Continue claim
                  </button>
                )
              )}
              {claim.deletable && <DeleteButton onDelete={onDelete} />}
            </div>
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

      {claim.claim_form_data && (
        <>
          <section className="rounded-2xl border border-line bg-white p-4 shadow-sm">
            <div className="mb-3 flex items-baseline justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">Documents</h3>
              <p className="text-xs text-muted">
                {claim.documents.length - missing.length} of {claim.documents.length} ready
              </p>
            </div>
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
        </>
      )}

      {claim.evidence.length > 0 && (
        <section className="rounded-2xl border border-line bg-white p-4 shadow-sm">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">Photos checked</h3>
          <ul className="space-y-2 text-sm">
            {claim.evidence.map((e) => (
              <li key={e.id} className="flex items-center gap-3">
                {e.url && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={`${API_URL}${e.url}`}
                    alt={e.evidence_type}
                    className="h-12 w-12 shrink-0 rounded-lg border border-line object-cover"
                  />
                )}
                <span className="min-w-0 flex-1 text-ink">{PHOTO_LABEL[e.evidence_type] ?? label(e.evidence_type)}</span>
                <span className={`text-right text-xs font-medium ${e.is_accepted ? "text-emerald-700" : "text-red-600"}`}>
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
  onResume,
}: {
  profile: Profile;
  language: Language;
  onNewClaim: () => void;
  onResume: (sessionId: string) => void;
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

  async function remove(sessionId: string) {
    try {
      await deleteClaim(profile.id, sessionId);
      if (selected === sessionId) setSelected(null);
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const claims = data?.claims ?? [];
  const groups = [
    { title: "In progress", items: claims.filter((c) => c.resumable) },
    { title: "Filed", items: claims.filter((c) => c.conversation_stage === "FILED") },
    { title: "Closed", items: claims.filter((c) => !c.resumable && c.conversation_stage !== "FILED") },
  ];
  const uninsured = profile.vehicles.filter((v) => !v.policy);

  return (
    <div className="grid gap-6 py-6 md:grid-cols-[minmax(0,1fr)_400px] md:items-start">
      <div className={`min-w-0 space-y-8 ${selected ? "hidden md:block" : ""}`}>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-navy">Hi {profile.full_name.split(" ")[0]}</h1>
            <p className="mt-1 text-sm text-muted">Pick up a claim where you left off, or start a new one.</p>
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

        {!data ? (
          <p className="text-sm text-muted">Loading your claims…</p>
        ) : claims.length === 0 ? (
          <Section title="Claims">
            <div className="rounded-2xl border border-dashed border-line bg-white p-6 text-center">
              <p className="text-sm font-medium text-ink">No claims yet</p>
              <p className="mt-1 text-sm text-muted">
                Describe what happened to your vehicle and we&apos;ll tell you if a claim is worth it.
              </p>
            </div>
          </Section>
        ) : (
          groups
            .filter((g) => g.items.length > 0)
            .map((g) => (
              <Section key={g.title} title={g.title} aside={<p className="text-xs text-muted">{g.items.length}</p>}>
                <div className="grid gap-3 lg:grid-cols-2">
                  {g.items.map((c) => (
                    <ClaimRow
                      key={c.session_id}
                      claim={c}
                      active={c.session_id === selected}
                      onSelect={() => setSelected(c.session_id)}
                      onResume={() => onResume(c.session_id)}
                      onDelete={() => remove(c.session_id)}
                    />
                  ))}
                </div>
              </Section>
            ))
        )}

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
            key={selected}
            userId={profile.id}
            sessionId={selected}
            language={language}
            onBack={() => setSelected(null)}
            onChanged={load}
            onResume={() => onResume(selected)}
            onDelete={() => remove(selected)}
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
