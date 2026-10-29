"use client";

// Phone-call view over the chat: hands-free, the user can talk over the bot, and a short
// "okay…" plays while it thinks. The chat underneath keeps the full transcript.
import { useCallback, useEffect, useRef, useState } from "react";
import { API_URL } from "@/lib/api";
import { shrinkImage, toBase64 } from "@/lib/media";
import type { ClaimState, Language } from "@/lib/useClaimSocket";
import { useHandsFree } from "@/lib/useHandsFree";

type Props = {
  state: ClaimState;
  onAudio: (data: string, mime: string) => void;
  onPhoto: (data: string, mime: string, preview: string) => void;
  onDecide: (d: "claim" | "dont_claim") => void;
  play: (src: string) => void;
  interrupt: () => void;
  onEnd: () => void;
};

export default function CallScreen({ state, onAudio, onPhoto, onDecide, play, interrupt, onEnd }: Props) {
  const [muted, setMuted] = useState(false);
  const fillers = useRef<Partial<Record<Language, string[]>>>({});
  const fileInput = useRef<HTMLInputElement>(null);
  const busy = state.status !== "idle";

  useEffect(() => {
    for (const lang of ["hi", "en"] as const) {
      fetch(`${API_URL}/voice/fillers?language=${lang}`)
        .then((r) => (r.ok ? r.json() : null))
        .then((body) => {
          if (body) fillers.current[lang] = body.clips.map((c: string) => `data:${body.mime};base64,${c}`);
        })
        .catch(() => {}); // no fillers: the call still works, just with a silent wait
    }
  }, []);

  const sendUtterance = useCallback(
    async (blob: Blob, mime: string) => {
      if (blob.size === 0) return;
      onAudio(await toBase64(blob), mime);
      const clips = fillers.current[state.language];
      if (clips?.length) play(clips[Math.floor(Math.random() * clips.length)]);
    },
    [onAudio, play, state.language],
  );

  const mic = useHandsFree({
    active: true,
    canListen: !muted && !busy && state.turnDone,
    botSpeaking: state.speaking,
    onUtterance: sendUtterance,
    onBargeIn: interrupt,
  });

  async function pickPhoto(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const { data, preview } = await shrinkImage(file);
    onPhoto(data, "image/jpeg", preview);
  }

  const lastBot = [...state.messages].reverse().find((m) => m.role === "bot");
  const lastUser = [...state.messages].reverse().find((m) => m.role === "user");
  const status =
    state.status === "closed" ? "Call dropped"
    : mic.error ? "Mic unavailable"
    : !mic.ready ? "Connecting…"
    : mic.hearing ? "Hearing you…"
    : state.speaking ? "Speaking…"
    : busy || !state.turnDone ? "Thinking…"
    : muted ? "Muted"
    : "Listening…";

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center bg-gradient-to-b from-navy to-[#001a40] px-4 pb-8 pt-12 text-white">
      <p className="text-sm font-medium text-white/60">Claim Karo</p>

      <div className="flex flex-1 flex-col items-center justify-center gap-6">
        <div className="relative grid h-36 w-36 place-items-center">
          {state.speaking && <span className="absolute inset-0 animate-ping rounded-full bg-sky/30" />}
          {mic.hearing && <span className="absolute -inset-3 animate-pulse rounded-full bg-white/15" />}
          <div className="relative grid h-32 w-32 place-items-center rounded-full bg-sky text-3xl font-bold shadow-lg">
            CK
          </div>
        </div>
        <p className="text-base font-medium text-sky" aria-live="polite">{status}</p>

        <div className="max-w-md space-y-3 text-center">
          {lastUser && <p className="text-sm text-white/50">&ldquo;{lastUser.text}&rdquo;</p>}
          {lastBot && <p className="animate-fadein text-lg leading-relaxed" key={lastBot.text}>{lastBot.text}</p>}
          {state.sttFailed && <p className="text-sm text-amber-300">Couldn&apos;t hear that. Please say it again.</p>}
          {(mic.error || state.error) && <p className="text-sm text-red-300">{mic.error ?? state.error}</p>}
        </div>
      </div>

      {state.state === "VIABILITY" && !busy && (
        <div className="mb-6 flex w-full max-w-sm gap-2">
          <button onClick={() => onDecide("claim")} className="flex-1 rounded-xl bg-sky py-2.5 text-sm font-semibold">
            File claim
          </button>
          <button onClick={() => onDecide("dont_claim")} className="flex-1 rounded-xl border border-white/30 py-2.5 text-sm font-semibold">
            Don&apos;t claim
          </button>
        </div>
      )}

      <input ref={fileInput} type="file" accept="image/*" capture="environment" hidden onChange={pickPhoto} />
      <div className="flex items-end gap-6">
        {state.state === "EVIDENCE" && (
          <CallButton label="Photo" onClick={() => fileInput.current?.click()} disabled={busy}>
            <svg {...iconProps}>
              <path d="M4 8h3l2-3h6l2 3h3v11H4z" />
              <circle cx="12" cy="13" r="3.5" />
            </svg>
          </CallButton>
        )}
        <CallButton label={muted ? "Unmute" : "Mute"} onClick={() => setMuted((m) => !m)} active={muted}>
          <svg {...iconProps}>
            <rect x="9" y="2" width="6" height="12" rx="3" />
            <path d="M5 10a7 7 0 0 0 14 0M12 17v5" />
            {muted && <path d="M3 3l18 18" />}
          </svg>
        </CallButton>
        <CallButton label="End" onClick={onEnd} danger>
          <svg {...iconProps}>
            <path d="M18 6 6 18M6 6l12 12" />
          </svg>
        </CallButton>
      </div>
    </div>
  );
}

function CallButton({
  label,
  danger,
  active,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { label: string; danger?: boolean; active?: boolean }) {
  return (
    <div className="flex flex-col items-center gap-1.5">
      <button
        type="button"
        aria-label={label}
        {...props}
        className={`grid h-14 w-14 place-items-center rounded-full transition disabled:opacity-40 ${
          danger ? "bg-red-500 hover:bg-red-600" : active ? "bg-white text-navy" : "bg-white/15 hover:bg-white/25"
        }`}
      >
        {children}
      </button>
      <span className="text-xs text-white/60">{label}</span>
    </div>
  );
}

const iconProps = {
  width: 22,
  height: 22,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};
