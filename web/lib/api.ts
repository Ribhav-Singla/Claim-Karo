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

export async function lookupUser(mobile: string): Promise<Profile> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/users/lookup?phone=${encodeURIComponent(mobile)}`);
  } catch {
    throw new Error("Can't reach the server. Is the backend running?");
  }
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail ?? "Something went wrong");
  return body as Profile;
}
