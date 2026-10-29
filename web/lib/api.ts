// REST calls to the FastAPI backend (the conversation itself runs over the WebSocket).
import type { Language } from "./useClaimSocket";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type PolicySummary = {
  id: string;
  insurer_name: string;
  policy_number: string;
  coverage_type: "comprehensive" | "third_party_only";
  no_claim_bonus_pct: number;
  coverage_end_date: string;
  insured_declared_value_inr: number;
  add_on_covers: string[];
};
export type WalletVehicle = {
  id: string;
  vehicle_type: "2W" | "4W";
  vehicle_number: string;
  brand: string;
  model: string;
  manufacture_year: number;
  policy: PolicySummary | null;
};
export type Profile = {
  id: string;
  full_name: string;
  phone_number: string;
  preferred_language: Language;
  vehicles: WalletVehicle[];
};

export type DocumentName = { document_code: string; name_english: string; name_hindi: string };
export type ClaimDocument = DocumentName & { is_provided: boolean };
export type Verdict = "claim" | "dont_claim" | "borderline" | "not_covered";

export type WalletPolicy = {
  id: string;
  insurer_name: string;
  policy_number: string;
  coverage_type: "comprehensive" | "third_party_only";
  coverage_start_date: string;
  coverage_end_date: string;
  insured_declared_value_inr: number;
  no_claim_bonus_pct: number;
  deductible_inr: number;
  add_on_covers: string[];
  vehicle: Omit<WalletVehicle, "policy">;
  required_documents: DocumentName[];
};
export type ClaimSummary = {
  session_id: string;
  claim_status: "draft" | "filed";
  claim_reference_number: string | null;
  claim_type: string;
  drafted_at: string;
  filed_at: string | null;
  expected_settlement_days_min: number | null;
  expected_settlement_days_max: number | null;
  insurer_name: string;
  policy_number: string;
  brand: string;
  model: string;
  vehicle_number: string;
  incident_date: string | null;
  estimated_repair_cost_inr: number | null;
  expected_payout_inr: number | null;
  claim_recommendation: Verdict | null;
  documents_missing: number;
};
export type DashboardData = { policies: WalletPolicy[]; claims: ClaimSummary[] };

export type ClaimDetail = {
  session_id: string;
  claim_status: "draft" | "filed";
  claim_reference_number: string | null;
  claim_type: string;
  claim_form_data: Record<string, unknown>;
  expected_settlement_days_min: number | null;
  expected_settlement_days_max: number | null;
  drafted_at: string;
  filed_at: string | null;
  claim_recommendation: Verdict | null;
  viability_assessment: {
    insurer_payout_inr: number;
    ncb_loss_total_inr: number;
    deductible_inr: number;
    depreciation_inr: number;
    estimate_pending: boolean;
  } | null;
  documents: ClaimDocument[];
  evidence: {
    id: string;
    evidence_type: string;
    is_accepted: boolean;
    quality_issues: string[];
    detail_mismatches: string[]; // e.g. PLATE_MISMATCH, DL_NUMBER_MISMATCH
    uploaded_at: string;
  }[];
  messages: { sender_role: "user" | "bot"; message_text: string; sent_at: string }[];
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
  request<{ claim_reference_number: string }>(`/users/${userId}/claims/${sessionId}/file`, { method: "POST" });
