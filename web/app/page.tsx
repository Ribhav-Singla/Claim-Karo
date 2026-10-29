"use client";

import { RoomAudioRenderer, SessionProvider, useSession } from "@livekit/components-react";
import { TokenSource } from "livekit-client";
import { useEffect, useMemo, useState } from "react";
import Chat from "@/components/Chat";
import ClaimPanel from "@/components/ClaimPanel";
import Dashboard from "@/components/Dashboard";
import Login from "@/components/Login";
import { fetchLiveKitToken, type Profile } from "@/lib/api";
import { useClaim, type Language } from "@/lib/useClaim";

// One claim conversation = one LiveKit room with the claim agent in it.
function Session({ profile, language }: { profile: Profile; language: Language }) {
  const tokenSource = useMemo(
    () => TokenSource.custom(() => fetchLiveKitToken(profile.id, language)),
    [profile.id, language],
  );
  const session = useSession(tokenSource);
  const { start, end } = session;

  useEffect(() => {
    // the mic stays off until the user taps it or starts a call
    start({ tracks: { microphone: { enabled: false } } }).catch(() => {});
    return () => {
      end();
    };
  }, [start, end]);

  return (
    <SessionProvider session={session}>
      <RoomAudioRenderer />
      <Conversation profile={profile} language={language} />
    </SessionProvider>
  );
}

function Conversation({ profile, language }: { profile: Profile; language: Language }) {
  const { state, sendText, sendPhoto, decide, setMic } = useClaim(language);
  return (
    <div className="grid gap-4 py-4 md:h-[calc(100dvh-4rem)] md:grid-cols-[1fr_380px]">
      <Chat state={state} onText={sendText} onPhoto={sendPhoto} onDecide={decide} setMic={setMic} />
      <ClaimPanel state={state} profile={profile} onFile={() => decide("file")} />
    </div>
  );
}

const maskPhone = (phone: string) => {
  const digits = phone.replace(/\D/g, "").slice(-10);
  return `+91 ••••• ${digits.slice(-5)}`;
};

export default function Home() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [language, setLanguage] = useState<Language>("hi");
  const [run, setRun] = useState(0); // bump to start a fresh conversation
  const [view, setView] = useState<"dashboard" | "chat">("dashboard");

  function login(p: Profile) {
    setProfile(p);
    setLanguage(p.preferred_language);
    setView("dashboard");
  }

  function newClaim() {
    setRun((r) => r + 1);
    setView("chat");
  }

  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-10 bg-white/90 shadow-[0_1px_0_var(--color-line)] backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
          <div className="flex items-center gap-2">
            <div className="grid h-8 w-8 place-items-center rounded-lg bg-navy text-sm font-bold text-white">
              CK
            </div>
            <span className="text-lg font-semibold tracking-tight text-navy">
              Claim<span className="text-sky">Karo</span>
            </span>
          </div>

          {profile && (
            <div className="flex items-center gap-2 sm:gap-3">
              <div className="flex rounded-full bg-canvas p-0.5 text-xs font-medium" role="group" aria-label="Language">
                {(["hi", "en"] as const).map((l) => (
                  <button
                    key={l}
                    onClick={() => setLanguage(l)}
                    className={`rounded-full px-3 py-1 transition ${
                      language === l ? "bg-white text-navy shadow-sm" : "text-muted hover:text-ink"
                    }`}
                  >
                    {l === "hi" ? "हिंदी" : "English"}
                  </button>
                ))}
              </div>
              {view === "chat" && (
                <button
                  onClick={() => setView("dashboard")}
                  className="rounded-full border border-line px-3 py-1.5 text-xs font-medium text-ink transition hover:border-sky"
                >
                  My claims
                </button>
              )}
              <button
                onClick={newClaim}
                className="hidden rounded-full border border-line px-3 py-1.5 text-xs font-medium text-ink transition hover:border-sky sm:block"
              >
                New claim
              </button>
              <div className="flex items-center gap-2 border-l border-line pl-3">
                <div className="grid h-8 w-8 place-items-center rounded-full bg-sky-soft text-xs font-semibold text-navy">
                  {profile.full_name.split(" ").map((w) => w[0]).join("")}
                </div>
                <div className="hidden leading-tight sm:block">
                  <p className="text-sm font-medium text-ink">{profile.full_name}</p>
                  <p className="text-xs text-muted">{maskPhone(profile.phone_number)}</p>
                </div>
                <button
                  onClick={() => setProfile(null)}
                  className="ml-1 text-xs text-muted transition hover:text-navy"
                  title="Log out"
                >
                  Log out
                </button>
              </div>
            </div>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4">
        {profile && view === "chat" ? (
          <Session key={`${profile.id}-${language}-${run}`} profile={profile} language={language} />
        ) : profile ? (
          <Dashboard profile={profile} language={language} onNewClaim={newClaim} />
        ) : (
          <Login onLogin={login} />
        )}
      </main>
    </div>
  );
}
