"use client";

import { useEffect, useRef, useState } from "react";
import type { ClaimState } from "@/lib/useClaimSocket";

type Props = {
  state: ClaimState;
  onText: (text: string) => void;
  onAudio: (data: string, mime: string) => void;
  onPhoto: (data: string, mime: string, preview: string) => void;
  onDecide: (d: "claim" | "dont_claim" | "file") => void;
};

const toBase64 = (blob: Blob) =>
  new Promise<string>((resolve) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve((reader.result as string).split(",")[1]);
    reader.readAsDataURL(blob);
  });

// Phone photos can be 10MB+; shrink to a 1600px JPEG before sending.
async function shrinkImage(file: File): Promise<{ data: string; preview: string }> {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, 1600 / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d")!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  const preview = canvas.toDataURL("image/jpeg", 0.85);
  return { data: preview.split(",")[1], preview };
}

export default function Chat({ state, onText, onAudio, onPhoto, onDecide }: Props) {
  const [text, setText] = useState("");
  const [recording, setRecording] = useState(false);
  const recorder = useRef<MediaRecorder | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const busy = state.status !== "idle";

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [state.messages, busy]);

  async function startRecording() {
    if (busy || recording) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks: Blob[] = [];
      const rec = new MediaRecorder(stream);
      rec.ondataavailable = (e) => chunks.push(e.data);
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks, { type: rec.mimeType });
        if (blob.size > 0) onAudio(await toBase64(blob), rec.mimeType);
      };
      rec.start();
      recorder.current = rec;
      setRecording(true);
    } catch {
      alert("Microphone not available. Please type instead.");
    }
  }

  function stopRecording() {
    recorder.current?.stop();
    recorder.current = null;
    setRecording(false);
  }

  async function pickPhoto(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const { data, preview } = await shrinkImage(file);
    onPhoto(data, "image/jpeg", preview);
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim() || busy) return;
    onText(text.trim());
    setText("");
  }

  const s = state.state;
  const status =
    state.status === "connecting" ? "Connecting…"
    : state.status === "closed" ? "Disconnected"
    : recording ? "Listening…"
    : state.status === "thinking" ? "Thinking…"
    : "Online";

  return (
    <section className="flex min-h-[70dvh] flex-col overflow-hidden rounded-2xl border border-line bg-white shadow-sm md:h-full md:min-h-0">
      <div className="flex items-center gap-3 border-b border-line px-5 py-3">
        <div className="grid h-9 w-9 place-items-center rounded-full bg-navy text-xs font-bold text-white">CK</div>
        <div className="leading-tight">
          <p className="text-sm font-semibold text-ink">Claim assistant</p>
          <p className="flex items-center gap-1.5 text-xs text-muted">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                state.status === "closed" ? "bg-red-500" : state.status === "connecting" ? "bg-amber-400" : "bg-emerald-500"
              }`}
            />
            {status}
          </p>
        </div>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto bg-canvas/50 px-4 py-5 sm:px-6">
        {state.messages.map((m, i) => (
          <div key={i} className={`animate-fadein flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <p
              className={`max-w-[85%] whitespace-pre-wrap px-4 py-2.5 text-[15px] leading-relaxed sm:max-w-[75%] ${
                m.role === "user"
                  ? "rounded-2xl rounded-br-md bg-navy text-white"
                  : "rounded-2xl rounded-bl-md border border-line bg-white text-ink"
              }`}
            >
              {m.text}
            </p>
          </div>
        ))}
        {state.status === "thinking" && (
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
        {state.sttFailed && (
          <p className="text-center text-xs text-amber-700">Couldn&apos;t hear that. Please try again or type.</p>
        )}
        {state.error && <p className="text-center text-xs text-red-600">{state.error}</p>}
        <div ref={bottom} />
      </div>

      {s === "VIABILITY" && !busy && (
        <div className="flex gap-2 border-t border-line bg-white px-4 pt-3 sm:px-6">
          <button
            onClick={() => onDecide("claim")}
            className="flex-1 rounded-xl bg-sky py-2.5 text-sm font-semibold text-white transition hover:bg-sky-dark"
          >
            File claim
          </button>
          <button
            onClick={() => onDecide("dont_claim")}
            className="flex-1 rounded-xl border border-line py-2.5 text-sm font-semibold text-navy transition hover:bg-canvas"
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
            placeholder={recording ? "Listening… release to send" : "Describe what happened…"}
            className="min-w-0 flex-1 bg-transparent py-2.5 text-sm outline-none placeholder:text-muted"
          />
          <button
            type="submit"
            disabled={busy || !text.trim()}
            className="grid h-8 w-8 place-items-center rounded-full bg-navy text-white transition disabled:opacity-30"
            title="Send"
          >
            <SendIcon />
          </button>
        </div>
        <button
          type="button"
          onPointerDown={startRecording}
          onPointerUp={stopRecording}
          onPointerLeave={() => recording && stopRecording()}
          disabled={busy}
          title="Hold to talk"
          className={`grid h-11 w-11 shrink-0 place-items-center rounded-full text-white shadow-sm transition disabled:opacity-40 ${
            recording ? "scale-110 bg-red-500 ring-4 ring-red-100" : "bg-sky hover:bg-sky-dark"
          }`}
        >
          <MicIcon />
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
