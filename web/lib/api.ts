// REST calls to the FastAPI backend (the conversation itself runs over the WebSocket).
import type { Language } from "./useClaimSocket";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type PolicySummary = {
  id: string;
  insurer: string;
  policy_no: string;
  cover_type: "comprehensive" | "third_party_only";
  ncb_pct: number;
  period_end: string;
  idv_inr: number;
  addons: string[];
};
export type WalletVehicle = {
  id: string;
  type: "2W" | "4W";
  reg_no: string;
  make_model: string;
  year: number;
  policy: PolicySummary | null;
};
export type Profile = {
  id: string;
  name: string;
  phone: string;
  language: Language;
  vehicles: WalletVehicle[];
};

export type DocumentName = { code: string; name_en: string; name_hi: string };
export type ClaimDocument = DocumentName & { provided: boolean };
export type Verdict = "claim" | "dont_claim" | "borderline" | "not_covered";

export type WalletPolicy = {
  id: string;
  insurer: string;
  policy_no: string;
  cover_type: "comprehensive" | "third_party_only";
  period_start: string;
  period_end: string;
  idv_inr: number;
  ncb_pct: number;
  deductible_inr: number;
  addons: string[];
  vehicle: Omit<WalletVehicle, "policy">;
  required_documents: DocumentName[];
};
export type ClaimSummary = {
  session_id: string;
  status: "draft" | "filed";
  reference_no: string | null;
  claim_type: string;
  created_at: string;
  filed_at: string | null;
  settlement_days_min: number | null;
  settlement_days_max: number | null;
  insurer: string;
  policy_no: string;
  make_model: string;
  reg_no: string;
  incident_date: string | null;
  estimated_damage_inr: number | null;
  expected_payout_inr: number | null;
  verdict: Verdict | null;
  documents_missing: number;
};
export type DashboardData = { policies: WalletPolicy[]; claims: ClaimSummary[] };

export type ClaimDetail = {
  session_id: string;
  status: "draft" | "filed";
  reference_no: string | null;
  claim_type: string;
  form: Record<string, unknown>;
  settlement_days_min: number | null;
  settlement_days_max: number | null;
  created_at: string;
  filed_at: string | null;
  verdict: Verdict | null;
  viability: {
    insurer_payout_inr: number;
    ncb_loss_total_inr: number;
    deductible_inr: number;
    depreciation_inr: number;
    estimate_pending: boolean;
  } | null;
  documents: ClaimDocument[];
  evidence: { id: string; kind: string; accepted: boolean; issues: string[]; created_at: string }[];
  messages: { role: "user" | "bot"; text: string; created_at: string }[];
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new Error("Can't reach the server. Is the backend running?");
  }
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail ?? "Something went wrong");
  return body as T;
}

export const lookupUser = (mobile: string) =>
  request<Profile>(`/users/lookup?phone=${encodeURIComponent(mobile)}`);

export const fetchDashboard = (userId: string) => request<DashboardData>(`/users/${userId}/dashboard`);

export const fetchClaim = (userId: string, sessionId: string) =>
  request<ClaimDetail>(`/users/${userId}/claims/${sessionId}`);

export const fileClaim = (userId: string, sessionId: string) =>
  request<{ reference_no: string }>(`/users/${userId}/claims/${sessionId}/file`, { method: "POST" });
