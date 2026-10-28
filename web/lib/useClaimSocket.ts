"use client";

// Owns the WebSocket to the FastAPI backend and reduces server events into UI state.
import { useCallback, useEffect, useReducer, useRef } from "react";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws";

export type Language = "hi" | "en";
export type Status = "connecting" | "idle" | "thinking" | "closed";

export type Message = { role: "bot" | "user"; text: string };
export type Photo = {
  id: string;
  preview: string;
  status: "grading" | "accepted" | "retake";
  kind?: string;
  issues?: string[];
};
export type Policy = {
  policy_id: string;
  insurer: string;
  policy_no: string;
  cover_type: string;
  ncb_pct: number;
  deductible_inr: number;
  addons: string[];
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

export type ClaimState = {
  status: Status;
  state: string;
  messages: Message[];
  fields: Record<string, unknown>;
  policy: Policy | null;
  viability: Viability | null;
  photos: Photo[];
  form: Record<string, unknown> | null;
  missingDocs: string[] | null;
  settlement: Settlement | null;
  referenceNo: string | null;
  error: string | null;
  sttFailed: boolean;
};

const initial: ClaimState = {
  status: "connecting",
  state: "INTAKE",
  messages: [],
  fields: {},
  policy: null,
  viability: null,
  photos: [],
  form: null,
  missingDocs: null,
  settlement: null,
  referenceNo: null,
  error: null,
  sttFailed: false,
};

type ServerEvent = { type: string } & Record<string, any>;
type Action =
  | ServerEvent
  | { type: "_open" }
  | { type: "_closed" }
  | { type: "_user"; text: string }
  | { type: "_sending" }
  | { type: "_photo"; photo: Photo };

function reducer(s: ClaimState, e: Action): ClaimState {
  switch (e.type) {
    case "_open":
      return { ...s, status: "idle", error: null };
    case "_closed":
      return { ...s, status: "closed" };
    case "_user":
      return { ...s, messages: [...s.messages, { role: "user", text: e.text }], sttFailed: false };
    case "_sending":
    case "bot_thinking":
      return { ...s, status: "thinking", sttFailed: false };
    case "_photo":
      return { ...s, photos: [...s.photos, e.photo], status: "thinking" };
    case "transcript":
      return { ...s, messages: [...s.messages, { role: "user", text: e.text }] };
    case "bot_message":
      return { ...s, status: "idle", messages: [...s.messages, { role: "bot", text: e.text }] };
    case "state":
      return { ...s, state: e.state };
    case "field":
      return { ...s, fields: { ...s.fields, [e.name]: e.value } };
    case "policy_matched":
      return { ...s, policy: e as unknown as Policy };
    case "viability":
      return { ...s, viability: e as unknown as Viability };
    case "photo_graded":
      return {
        ...s,
        photos: s.photos.map((p) =>
          p.id === e.photo_id
            ? { ...p, kind: e.kind, issues: e.issues, status: e.accepted ? "accepted" : "retake" }
            : p,
        ),
      };
    case "form_ready":
      return { ...s, form: e.form };
    case "missing_docs":
      return { ...s, missingDocs: e.docs };
    case "settlement":
      return { ...s, settlement: e as unknown as Settlement };
    case "filed":
      return { ...s, referenceNo: e.reference_no };
    case "stt_failed":
      return { ...s, status: "idle", sttFailed: true };
    case "error":
      return { ...s, status: "idle", error: e.message };
    default:
      return s;
  }
}

export function useClaimSocket(userId: string, language: Language) {
  const [state, dispatch] = useReducer(reducer, initial);
  const ws = useRef<WebSocket | null>(null);
  const audioQueue = useRef<string[]>([]);
  const playing = useRef(false);

  const playNext = useCallback(() => {
    const src = audioQueue.current.shift();
    if (!src) {
      playing.current = false;
      return;
    }
    playing.current = true;
    const audio = new Audio(src);
    audio.onended = audio.onerror = () => playNext();
    audio.play().catch(() => playNext()); // autoplay blocked: text is already on screen
  }, []);

  useEffect(() => {
    const socket = new WebSocket(`${WS_URL}?user_id=${userId}&language=${language}`);
    ws.current = socket;
    socket.onopen = () => dispatch({ type: "_open" });
    socket.onclose = () => dispatch({ type: "_closed" });
    socket.onmessage = (msg) => {
      const event: ServerEvent = JSON.parse(msg.data);
      if (event.type === "audio") {
        audioQueue.current.push(`data:${event.mime};base64,${event.data}`);
        if (!playing.current) playNext();
        return;
      }
      dispatch(event);
    };
    return () => socket.close();
  }, [userId, language, playNext]);

  const send = useCallback((payload: object) => {
    if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(JSON.stringify(payload));
  }, []);

  return {
    state,
    sendText: (text: string) => {
      dispatch({ type: "_user", text });
      dispatch({ type: "_sending" });
      send({ type: "text", text });
    },
    sendAudio: (data: string, mime: string) => {
      dispatch({ type: "_sending" });
      send({ type: "audio", data, mime });
    },
    sendPhoto: (data: string, mime: string, preview: string) => {
      const id = crypto.randomUUID();
      dispatch({ type: "_photo", photo: { id, preview, status: "grading" } });
      send({ type: "photo", data, mime, photo_id: id });
    },
    decide: (decision: "claim" | "dont_claim" | "file") => {
      dispatch({ type: "_sending" });
      send({ type: "decision", decision });
    },
  };
}

export const rupees = (n: unknown) =>
  typeof n === "number" ? `₹${n.toLocaleString("en-IN")}` : "—";
