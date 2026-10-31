"use client";

// The claim conversation over LiveKit. LiveKit carries the audio both ways, the typed chat
// (useSessionMessages) and the agent's state; the agent also sends the whole claim as one
// JSON snapshot on the "claim.state" text stream, which the side panel renders.
import { useAgent, useLocalParticipant, useSessionContext, useSessionMessages, useTextStream } from "@livekit/components-react";
import { useCallback, useMemo, useState } from "react";
import { API_URL } from "./api";
import { shrinkImage } from "./media";

export type Language = "hi" | "en";
export type Status = "connecting" | "idle" | "thinking" | "closed";

export type Message = { id: string; role: "bot" | "user"; text: string };
export type Photo = {
  id: string;
  preview: string; // a local data URL just after upload, or the API's copy on a resumed claim
  status: "grading" | "accepted" | "retake";
  evidence_type?: string;
  quality_issues?: string[];
  url?: string | null;
};
export type Policy = {
  policy_id: string;
  insurer_name: string;
  policy_number: string;
  coverage_type: string;
  no_claim_bonus_pct: number;
  deductible_inr: number;
  add_on_covers: string[];
};
export type Viability = {
  verdict: "claim" | "dont_claim" | "borderline" | "not_covered";
  insurer_payout_inr: number;
  ncb_loss_year1_inr: number;
  ncb_loss_total_inr: number;
  deductible_inr: number;
  depreciation_inr: number;
  estimate_pending: boolean;
  breakeven_estimate_inr: number | null;
  reasons: string[];
};
export type Settlement = { min_days: number; max_days: number; route: string };

// What the agent publishes on "claim.state" (agent/claim_agent.py, Claim.publish).
type Snapshot = {
  sessionId: string | null; // a new id when the user cancels and starts a new claim
  state: string;
  fields: Record<string, unknown>;
  policy: Policy | null;
  viability: Viability | null;
  photos: Record<string, Omit<Photo, "id" | "preview">>;
  form: Record<string, unknown> | null;
  missingDocs: string[] | null;
  settlement: Settlement | null;
  referenceNo: string | null;
};

export type ClaimState = Omit<Snapshot, "photos"> & {
  status: Status;
  messages: Message[];
  photos: Photo[];
  progress: number; // 0-100, how far the claim has come
  speaking: boolean; // the agent is talking
  micOn: boolean;
};

// How far along the claim is: 0 until the incident is captured, 60 once the verdict is in,
// 90 when the photos are done and the form is ready, 100 when filed.
export function claimProgress(state: string, photos: Record<string, { status: string }>): number {
  switch (state) {
    case "INTAKE":
      return 0;
    case "VIABILITY":
    case "NO_COVER":
    case "ADVISED_NO_CLAIM":
    case "CANCELLED":
      return 60;
    case "EVIDENCE":
      return Object.values(photos).some((p) => p.status === "accepted") ? 75 : 60;
    case "FORM_REVIEW":
      return 90;
    case "FILED":
      return 100;
    default:
      return 0;
  }
}

const EMPTY: Snapshot = {
  sessionId: null,
  state: "INTAKE",
  fields: {},
  policy: null,
  viability: null,
  photos: {},
  form: null,
  missingDocs: null,
  settlement: null,
  referenceNo: null,
};

// The buttons answer the agent's questions as if the user had said so.
const DECISION_TEXT: Record<"claim" | "dont_claim" | "file", Record<Language, string>> = {
  claim: { hi: "हाँ, claim फ़ाइल करना है।", en: "Yes, I want to file the claim." },
  dont_claim: { hi: "नहीं, claim नहीं करना।", en: "No, I don't want to claim." },
  file: { hi: "हाँ, claim फ़ाइल कर दीजिए।", en: "Yes, please file the claim." },
};

const MIC_OPTIONS = { echoCancellation: true, noiseSuppression: true, autoGainControl: true, voiceIsolation: true };

// history: the earlier messages of a resumed claim, shown above the live conversation.
export function useClaim(language: Language, history: Message[] = []) {
  const session = useSessionContext();
  const agent = useAgent(session);
  const chat = useSessionMessages(session);
  const { localParticipant, isMicrophoneEnabled } = useLocalParticipant();
  const { textStreams } = useTextStream("claim.state");
  // photo id -> preview, and the claim (session id) it was uploaded to
  const [previews, setPreviews] = useState<Record<string, { preview: string; sessionId: string | null }>>({});

  const snapshot: Snapshot = useMemo(() => {
    const latest = textStreams[textStreams.length - 1];
    return latest ? JSON.parse(latest.text) : EMPTY;
  }, [textStreams]);

  const live: Message[] = chat.messages
    .map((m): Message => {
      const fromUser = m.type === "userTranscript" || (m.type === "chatMessage" && !!m.from?.isLocal);
      return { id: m.id, role: fromUser ? "user" : "bot", text: m.message };
    })
    .filter((m) => m.text.trim());
  const messages = history.length ? [...history, ...live] : live;

  const status: Status = !session.isConnected
    ? live.length > 0
      ? "closed"
      : "connecting"
    : !agent.isConnected
      ? "connecting"
      : agent.state === "thinking" || chat.isSending
        ? "thinking"
        : "idle";

  // Photos uploaded in this tab show their local preview straight away; on a resumed claim
  // the agent's snapshot carries each earlier photo's url instead. Only this claim's photos:
  // a cancelled claim's thumbnails disappear with it.
  const uploadedHere: Photo[] = Object.entries(previews)
    .filter(([, p]) => p.sessionId === snapshot.sessionId)
    .map(([id, { preview }]) => ({ id, preview, ...(snapshot.photos[id] ?? { status: "grading" as const }) }));
  const fromServer: Photo[] = Object.entries(snapshot.photos)
    .filter(([id, p]) => !(id in previews) && p.url)
    .map(([id, p]) => ({ id, preview: `${API_URL}${p.url}`, ...p }));
  const photos = [...fromServer, ...uploadedHere];

  const state: ClaimState = {
    ...snapshot,
    status,
    messages,
    photos,
    progress: claimProgress(snapshot.state, snapshot.photos),
    speaking: agent.state === "speaking",
    micOn: isMicrophoneEnabled,
  };

  const sendText = useCallback((text: string) => chat.send(text), [chat]);

  const sendPhoto = useCallback(
    async (file: File) => {
      const id = crypto.randomUUID();
      const { blob, preview } = await shrinkImage(file);
      setPreviews((p) => ({ ...p, [id]: { preview, sessionId: snapshot.sessionId } }));
      // the agent keys the photo's result by the file name (without extension)
      await localParticipant.sendFile(new File([blob], `${id}.jpg`, { type: "image/jpeg" }), {
        topic: "photo",
        mimeType: "image/jpeg",
      });
    },
    [localParticipant, snapshot.sessionId],
  );

  const decide = useCallback(
    (d: "claim" | "dont_claim" | "file") => chat.send(DECISION_TEXT[d][language]),
    [chat, language],
  );

  // the browser's echo cancellation keeps the bot's voice (from the speakers) out of the mic
  const setMic = useCallback(
    (on: boolean) => localParticipant.setMicrophoneEnabled(on, MIC_OPTIONS),
    [localParticipant],
  );

  return { state, sendText, sendPhoto, decide, setMic };
}

export const rupees = (n: unknown) =>
  typeof n === "number" ? `₹${n.toLocaleString("en-IN")}` : "—";
