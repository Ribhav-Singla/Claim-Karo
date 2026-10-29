"use client";

// The claim conversation over LiveKit. LiveKit carries the audio both ways, the typed chat
// (useSessionMessages) and the agent's state; the agent also sends the whole claim as one
// JSON snapshot on the "claim.state" text stream, which the side panel renders.
import { useAgent, useLocalParticipant, useSessionContext, useSessionMessages, useTextStream } from "@livekit/components-react";
import { useCallback, useMemo, useState } from "react";
import { shrinkImage } from "./media";

export type Language = "hi" | "en";
export type Status = "connecting" | "idle" | "thinking" | "closed";

export type Message = { id: string; role: "bot" | "user"; text: string };
export type Photo = {
  id: string;
  preview: string;
  status: "grading" | "accepted" | "retake";
  evidence_type?: string;
  quality_issues?: string[];
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
  speaking: boolean; // the agent is talking
  micOn: boolean;
};

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

  const state: ClaimState = {
    ...snapshot,
    status,
    messages,
    // only this claim's photos: a cancelled claim's thumbnails disappear with it
    photos: Object.entries(previews)
      .filter(([, p]) => p.sessionId === snapshot.sessionId)
      .map(([id, { preview }]) => ({
        id,
        preview,
        ...(snapshot.photos[id] ?? { status: "grading" as const }),
      })),
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
