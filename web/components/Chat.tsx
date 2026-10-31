"use client";

import { useLayoutEffect, useRef, useState } from "react";
import type { ClaimState } from "@/lib/useClaim";

type Props = {
  state: ClaimState;
  onText: (text: string) => void;
  onPhoto: (file: File) => void;
  onDecide: (d: "claim" | "dont_claim" | "file") => void;
  setMic: (on: boolean) => Promise<unknown>;
};

export default function Chat({ state, onText, onPhoto, onDecide, setMic }: Props) {
  const [text, setText] = useState("");
  const talking = state.micOn; // hands-free: the mic stays open until the user taps it again
  const list = useRef<HTMLDivElement>(null);
  const pinned = useRef(true); // the user is at the bottom of the chat
  const fileInput = useRef<HTMLInputElement>(null);
  const busy = state.status !== "idle";
  const lastMessage = state.messages[state.messages.length - 1];
  // dots until the bot's reply starts streaming in, then the reply bubble takes their place
  const showThinking = state.status === "thinking" && lastMessage?.role !== "bot";

  // Follow the reply as it streams in, without animation and without scrolling the page;
  // smooth-scrolling on every word made the chat shake. Leave it alone if the user scrolled up.
  useLayoutEffect(() => {
    const el = list.current;
    if (el && pinned.current) el.scrollTop = el.scrollHeight;
  }, [state.messages, showThinking]);

  // tap the mic to talk hands-free: LiveKit hears when you've finished; tap again to stop
  function toggleMic() {
    setMic(!state.micOn).catch(() => alert("Microphone not available. Please type instead."));
  }

  function pickPhoto(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (file) onPhoto(file);
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim() || state.status === "connecting" || state.status === "closed") return;
    onText(text.trim());
    setText("");
  }

  const s = state.state;
  const status =
    state.status === "connecting" ? "Connecting…"
    : state.status === "closed" ? "Disconnected"
    : state.speaking ? "Speaking…"
    : state.status === "thinking" ? "Thinking…"
    : talking ? "Listening…"
    : "Online";

  return (
    <section className="flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border border-line bg-white shadow-sm">
      <div className="flex items-center gap-3 border-b border-line px-5 py-3">
        <div className="grid h-9 w-9 place-items-center rounded-full bg-navy text-xs font-bold text-white">CK</div>
        <div className="leading-tight">
          <p className="text-sm font-semibold text-ink">Claim assistant</p>
          <p className="flex items-center gap-1.5 text-xs text-muted">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                state.status === "closed" ? "bg-red-500"
                : state.status === "connecting" ? "bg-amber-400"
                : talking ? "animate-pulse bg-red-500"
                : "bg-emerald-500"
              }`}
            />
            <span aria-live="polite">{status}</span>
          </p>
        </div>
      </div>

      <div
        ref={list}
        onScroll={(e) => {
          const el = e.currentTarget;
          pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
        }}
        className="flex-1 space-y-3 overflow-y-auto overscroll-contain bg-canvas/50 px-4 py-5 [overflow-anchor:none] sm:px-6"
      >
        {state.messages.map((m) => (
          <div key={m.id} className={`animate-fadein flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <p
              className={`max-w-[85%] whitespace-pre-wrap break-words px-4 py-2.5 text-[15px] leading-relaxed sm:max-w-[75%] ${
                m.role === "user"
                  ? "rounded-2xl rounded-br-md bg-navy text-white"
                  : "rounded-2xl rounded-bl-md border border-line bg-white text-ink"
              }`}
            >
              {m.text}
            </p>
          </div>
        ))}
        {showThinking && (
          <div className="flex w-fit gap-1 rounded-2xl rounded-bl-md border border-line bg-white px-4 py-3" aria-label="thinking">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="h-1.5 w-1.5 animate-bounce rounded-full bg-sky"
                style={{ animationDelay: `${i * 150}ms` }}
              />
            ))}
          </div>
        )}
      </div>

      {s === "VIABILITY" && (
        <div className="flex gap-2 border-t border-line bg-white px-4 pt-3 sm:px-6">
          <button
            onClick={() => onDecide("claim")}
            disabled={busy}
            className="flex-1 rounded-xl bg-sky py-2.5 text-sm font-semibold text-white transition hover:bg-sky-dark disabled:opacity-40"
          >
            File claim
          </button>
          <button
            onClick={() => onDecide("dont_claim")}
            disabled={busy}
            className="flex-1 rounded-xl border border-line py-2.5 text-sm font-semibold text-navy transition hover:bg-canvas disabled:opacity-40"
          >
            Don&apos;t claim
          </button>
        </div>
      )}

      <form onSubmit={submit} className="flex items-center gap-2 bg-white px-4 py-3 sm:px-6">
        {s === "EVIDENCE" && (
          <>
            <IconButton onClick={() => fileInput.current?.click()} disabled={busy} title="Upload photo" variant="outline">
              <CameraIcon />
            </IconButton>
            <input ref={fileInput} type="file" accept="image/*" capture="environment" hidden onChange={pickPhoto} />
          </>
        )}
        <div className="flex min-w-0 flex-1 items-center rounded-full border border-line bg-canvas/60 pl-4 pr-1 transition focus-within:border-sky focus-within:bg-white">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={talking ? "Listening… just speak, or type" : "Describe what happened…"}
            className="min-w-0 flex-1 bg-transparent py-2.5 text-sm outline-none placeholder:text-muted"
          />
          <button
            type="submit"
            disabled={!text.trim() || state.status === "connecting" || state.status === "closed"}
            className="grid h-8 w-8 place-items-center rounded-full bg-navy text-white transition disabled:opacity-30"
            title="Send"
          >
            <SendIcon />
          </button>
        </div>
        <button
          type="button"
          onClick={toggleMic}
          disabled={state.status === "connecting" || state.status === "closed"}
          title={talking ? "Stop talking" : "Tap to talk hands-free"}
          aria-label={talking ? "Stop talking" : "Talk"}
          aria-pressed={talking}
          className={`relative grid h-11 w-11 shrink-0 place-items-center rounded-full text-white shadow-sm transition disabled:opacity-40 ${
            talking ? "bg-red-500 ring-4 ring-red-100" : "bg-sky hover:bg-sky-dark"
          }`}
        >
          {talking && state.speaking && <span className="absolute inset-0 animate-ping rounded-full bg-red-400/40" />}
          {talking ? <StopIcon /> : <MicIcon />}
        </button>
      </form>
    </section>
  );
}

function IconButton({
  children,
  variant,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant: "outline" }) {
  return (
    <button
      type="button"
      {...props}
      className={`grid h-11 w-11 shrink-0 place-items-center rounded-full text-navy transition disabled:opacity-40 ${
        variant === "outline" ? "border border-line hover:border-sky hover:bg-sky-soft" : ""
      }`}
    >
      {children}
    </button>
  );
}

const iconProps = {
  width: 18,
  height: 18,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

const MicIcon = () => (
  <svg {...iconProps}>
    <rect x="9" y="2" width="6" height="12" rx="3" />
    <path d="M5 10a7 7 0 0 0 14 0M12 17v5" />
  </svg>
);
const StopIcon = () => (
  <svg {...iconProps}>
    <rect x="7" y="7" width="10" height="10" rx="2" fill="currentColor" />
  </svg>
);
const SendIcon = () => (
  <svg {...iconProps} width={15} height={15}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </svg>
);
const CameraIcon = () => (
  <svg {...iconProps}>
    <path d="M4 8h3l2-3h6l2 3h3v11H4z" />
    <circle cx="12" cy="13" r="3.5" />
  </svg>
);
