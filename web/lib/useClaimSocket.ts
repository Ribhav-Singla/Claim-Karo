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
  turnDone: boolean; // server finished the last turn; nothing more comes until we send
  speaking: boolean; // bot audio is playing
  language: Language; // of the last bot message (follows the language the user speaks)
};

const initial: Omit<ClaimState, "language"> = {
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
  turnDone: false,
  speaking: false,
};

type ServerEvent = { type: string } & Record<string, any>;
type Action =
  | ServerEvent
  | { type: "_open" }
  | { type: "_closed" }
  | { type: "_user"; text: string }
  | { type: "_sending" }
  | { type: "_photo"; photo: Photo }
  | { type: "_speaking"; speaking: boolean };

function reducer(s: ClaimState, e: Action): ClaimState {
  switch (e.type) {
    case "_open":
      return { ...s, status: "idle", error: null };
    case "_closed":
      return { ...s, status: "closed" };
    case "_user":
      return { ...s, messages: [...s.messages, { role: "user", text: e.text }], sttFailed: false };
    case "_sending":
      return { ...s, status: "thinking", sttFailed: false, turnDone: false };
    case "bot_thinking":
      return { ...s, status: "thinking", sttFailed: false };
    case "_photo":
      return { ...s, photos: [...s.photos, e.photo], status: "thinking", turnDone: false };
    case "_speaking":
      return { ...s, speaking: e.speaking };
    case "turn_done":
      return { ...s, status: "idle", turnDone: true };
    case "transcript":
      return { ...s, messages: [...s.messages, { role: "user", text: e.text }] };
    case "bot_message":
      return {
        ...s,
        status: "idle",
        language: e.language ?? s.language,
        messages: [...s.messages, { role: "bot", text: e.text }],
      };
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
            ? {
                ...p,
                evidence_type: e.evidence_type,
                quality_issues: e.quality_issues,
                status: e.is_accepted ? "accepted" : "retake",
              }
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
      return { ...s, referenceNo: e.claim_reference_number };
    case "stt_failed":
      return { ...s, status: "idle", sttFailed: true };
    case "error":
      return { ...s, status: "idle", error: e.message };
    default:
      return s;
  }
}

export function useClaimSocket(userId: string, language: Language) {
  const [state, dispatch] = useReducer(reducer, { ...initial, language });
  const ws = useRef<WebSocket | null>(null);
  const audioQueue = useRef<string[]>([]);
  const current = useRef<HTMLAudioElement | null>(null);

  const playNext = useCallback(() => {
    const src = audioQueue.current.shift();
    if (!src) {
      current.current = null;
      dispatch({ type: "_speaking", speaking: false });
      return;
    }
    const audio = new Audio(src);
    current.current = audio;
    dispatch({ type: "_speaking", speaking: true });
    audio.onended = audio.onerror = () => playNext();
    audio.play().catch(() => playNext()); // autoplay blocked: text is already on screen
  }, []);

  const play = useCallback(
    (src: string) => {
      audioQueue.current.push(src);
      if (!current.current) playNext();
    },
    [playNext],
  );

  // the user started talking over the bot: drop what it was saying
  const interrupt = useCallback(() => {
    audioQueue.current = [];
    current.current?.pause();
    current.current = null;
    dispatch({ type: "_speaking", speaking: false });
  }, []);

  useEffect(() => {
    const socket = new WebSocket(`${WS_URL}?user_id=${userId}&language=${language}`);
    ws.current = socket;
    socket.onopen = () => dispatch({ type: "_open" });
    socket.onclose = () => dispatch({ type: "_closed" });
    socket.onmessage = (msg) => {
      const event: ServerEvent = JSON.parse(msg.data);
      if (event.type === "audio") {
        play(`data:${event.mime};base64,${event.data}`);
        return;
      }
      dispatch(event);
    };
    return () => {
      socket.close();
      interrupt();
    };
  }, [userId, language, play, interrupt]);

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
    play,
    interrupt,
  };
}

export const rupees = (n: unknown) =>
  typeof n === "number" ? `₹${n.toLocaleString("en-IN")}` : "—";
