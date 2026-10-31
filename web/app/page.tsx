"use client";

import { RoomAudioRenderer, SessionProvider, useSession } from "@livekit/components-react";
import { TokenSource } from "livekit-client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Chat from "@/components/Chat";
import ClaimPanel, { ProgressBar } from "@/components/ClaimPanel";
import Dashboard from "@/components/Dashboard";
import Login from "@/components/Login";
import PaytmHome from "@/components/PaytmHome";
import { fetchClaim, fetchLiveKitToken, type Profile } from "@/lib/api";
import { useClaim, type ClaimState, type Language, type Message } from "@/lib/useClaim";

type SessionProps = {
  profile: Profile;
  language: Language;
  resumeId: string | null; // continue this claim instead of starting a new one
  onSessionId: (id: string) => void;
};

// One claim conversation = one LiveKit room with the claim agent in it.
function Session({ profile, language, resumeId, onSessionId }: SessionProps) {
  const tokenSource = useMemo(
    () => TokenSource.custom(() => fetchLiveKitToken(profile.id, language, resumeId)),
    [profile.id, language, resumeId],
  );
  const session = useSession(tokenSource);
  const { start, end } = session;

  useEffect(() => {
    // the mic stays off until the user taps it
    start({ tracks: { microphone: { enabled: false } } }).catch(() => {});
    return () => {
      end();
    };
  }, [start, end]);

  return (
    <SessionProvider session={session}>
      <RoomAudioRenderer />
      <Conversation profile={profile} language={language} resumeId={resumeId} onSessionId={onSessionId} />
    </SessionProvider>
  );
}

// On a phone the claim details sit in an accordion above the chat: the header always shows
// the progress bar; open it to see the details, close it to get back to chat and voice.
function MobileClaimAccordion({
  state,
  profile,
  onFile,
  open,
  onToggle,
}: {
  state: ClaimState;
  profile: Profile;
  onFile: () => void;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="md:hidden">
      <button
        onClick={onToggle}
        aria-expanded={open}
        aria-controls="claim-details"
        className="flex w-full items-center gap-3 rounded-2xl border border-line bg-white px-4 py-3 text-left shadow-sm"
      >
        <div className="min-w-0 flex-1">
          <ProgressBar state={state.state} percent={state.progress} compact />
        </div>
        <span className="flex shrink-0 items-center gap-1 text-xs font-medium text-sky-dark">
          {open ? "Hide" : "Details"}
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            className={`transition ${open ? "rotate-180" : ""}`}
          >
            <path d="m6 9 6 6 6-6" />
          </svg>
        </span>
      </button>
      {open && (
        <div id="claim-details" className="mt-3 animate-fadein">
          <ClaimPanel state={state} profile={profile} onFile={onFile} hideProgress />
        </div>
      )}
    </div>
  );
}

function Conversation({ profile, language, resumeId, onSessionId }: SessionProps) {
  // a resumed claim shows what was said before, above the live conversation
  const [history, setHistory] = useState<Message[]>([]);
  const [detailsOpen, setDetailsOpen] = useState(false);
  useEffect(() => {
    if (!resumeId) return;
    let live = true;
    fetchClaim(profile.id, resumeId)
      .then((c) => {
        if (!live) return;
        setHistory(
          c.messages.map((m, i) => ({ id: `history-${i}`, role: m.sender_role, text: m.message_text })),
        );
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [profile.id, resumeId]);

  const { state, sendText, sendPhoto, decide, setMic } = useClaim(language, history);
  useEffect(() => {
    if (state.sessionId) onSessionId(state.sessionId);
  }, [state.sessionId, onSessionId]);

  const file = () => decide("file");

  return (
    <div className="flex flex-col gap-3 py-3 md:grid md:h-[calc(100dvh-4rem)] md:grid-cols-[1fr_380px] md:gap-4 md:py-4">
      <MobileClaimAccordion
        state={state}
        profile={profile}
        onFile={file}
        open={detailsOpen}
        onToggle={() => setDetailsOpen((o) => !o)}
      />
      {/* on a phone the chat steps aside while the details are open */}
      <div className={`min-h-0 ${detailsOpen ? "hidden md:flex" : "flex"} flex-col`}>
        <Chat state={state} onText={sendText} onPhoto={sendPhoto} onDecide={decide} setMic={setMic} />
      </div>
      <div className="hidden min-h-0 md:block">
        <ClaimPanel state={state} profile={profile} onFile={file} />
      </div>
    </div>
  );
}

const maskPhone = (phone: string) => {
  const digits = phone.replace(/\D/g, "").slice(-10);
  return `+91 ••••• ${digits.slice(-5)}`;
};

const initials = (name: string) =>
  name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

// Name and phone behind the avatar, with log out; opens on hover, or on tap / keyboard focus.
function ProfileMenu({ profile, onLogout }: { profile: Profile; onLogout: () => void }) {
  return (
    <div className="group relative">
      <button
        className="flex items-center gap-2 rounded-full p-0.5 pr-2 transition hover:bg-canvas focus:bg-canvas focus:outline-none"
        aria-haspopup="menu"
        aria-label={`Account: ${profile.full_name}`}
      >
        <span className="grid h-8 w-8 place-items-center rounded-full bg-navy text-xs font-semibold text-white">
          {initials(profile.full_name)}
        </span>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-muted transition group-hover:rotate-180 group-focus-within:rotate-180">
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>
      {/* pt-2 bridges the gap so the menu stays open while the pointer moves onto it */}
      <div className="invisible absolute right-0 top-full z-20 pt-2 opacity-0 transition group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100">
        <div role="menu" className="w-60 overflow-hidden rounded-2xl border border-line bg-white shadow-lg">
          <div className="flex items-center gap-3 px-4 py-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-sky-soft text-sm font-semibold text-navy">
              {initials(profile.full_name)}
            </span>
            <div className="min-w-0 leading-tight">
              <p className="truncate text-sm font-semibold text-ink">{profile.full_name}</p>
              <p className="text-xs text-muted">{maskPhone(profile.phone_number)}</p>
            </div>
          </div>
          <div className="border-t border-line p-1.5">
            <button
              role="menuitem"
              onClick={onLogout}
              className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-sm text-ink transition hover:bg-red-50 hover:text-red-700"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
              </svg>
              Log out
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

type OpenChat = { run: number; resumeId: string | null };
// login (number) -> Paytm home -> Claims dashboard -> claim conversation
type View = "home" | "claims";

export default function Home() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [language, setLanguage] = useState<Language>("hi");
  const [view, setView] = useState<View>("home");
  const [chat, setChat] = useState<OpenChat | null>(null); // null: the dashboard is showing
  const currentSession = useRef<string | null>(null); // the claim the open chat is on

  function login(p: Profile) {
    setProfile(p);
    setLanguage(p.preferred_language);
    setView("home");
    setChat(null);
  }

  function logout() {
    setProfile(null);
    setChat(null);
    setView("home");
  }

  function openChat(resumeId: string | null) {
    currentSession.current = resumeId;
    setChat((c) => ({ run: (c?.run ?? 0) + 1, resumeId }));
  }

  function goHome() {
    setChat(null);
    setView("home");
  }

  function switchLanguage(l: Language) {
    setLanguage(l);
    // reconnecting in the new language carries on with the same claim
    if (chat) setChat({ run: chat.run + 1, resumeId: currentSession.current });
  }

  const onSessionId = useCallback((id: string) => {
    currentSession.current = id;
  }, []);

  if (profile && view === "home" && !chat) {
    return (
      <div className="min-h-dvh bg-canvas">
        <PaytmHome
          profile={profile}
          onOpenClaims={() => setView("claims")}
          onLogout={logout}
        />
      </div>
    );
  }

  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-10 border-b border-line bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-4 px-4">
          {profile && (
            <button
              onClick={goHome}
              className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-ink transition hover:bg-canvas"
              aria-label="Back to Paytm home"
              title="Paytm home"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M15 18l-6-6 6-6" />
              </svg>
            </button>
          )}
          <button onClick={() => profile && setChat(null)} className="flex items-center gap-2" aria-label="Claim Karo home">
            <div className="grid h-8 w-8 place-items-center rounded-lg bg-navy text-sm font-bold text-white">CK</div>
            <span className="text-lg font-semibold tracking-tight text-navy">
              Claim<span className="text-sky">Karo</span>
            </span>
          </button>

          {profile && (
            <>
              <nav className="ml-2 hidden items-center gap-1 sm:flex" aria-label="Main">
                {[
                  { label: "My claims", active: !chat, onClick: () => setChat(null) },
                  ...(chat ? [{ label: chat.resumeId ? "Continuing claim" : "New claim", active: true, onClick: () => {} }] : []),
                ].map((item) => (
                  <button
                    key={item.label}
                    onClick={item.onClick}
                    aria-current={item.active ? "page" : undefined}
                    className={`relative rounded-lg px-3 py-2 text-sm font-medium transition ${
                      item.active ? "text-navy" : "text-muted hover:bg-canvas hover:text-ink"
                    }`}
                  >
                    {item.label}
                    {item.active && <span className="absolute inset-x-3 -bottom-[13px] h-0.5 rounded-full bg-sky" />}
                  </button>
                ))}
              </nav>

              <div className="ml-auto flex items-center gap-2 sm:gap-3">
                {chat && (
                  <button
                    onClick={() => setChat(null)}
                    className="rounded-full border border-line px-3 py-1.5 text-xs font-medium text-ink transition hover:border-sky sm:hidden"
                  >
                    My claims
                  </button>
                )}
                <div className="flex rounded-full bg-canvas p-0.5 text-xs font-medium" role="group" aria-label="Language">
                  {(["hi", "en"] as const).map((l) => (
                    <button
                      key={l}
                      onClick={() => switchLanguage(l)}
                      aria-pressed={language === l}
                      className={`rounded-full px-3 py-1 transition ${
                        language === l ? "bg-white text-navy shadow-sm" : "text-muted hover:text-ink"
                      }`}
                    >
                      {l === "hi" ? "हिंदी" : "EN"}
                    </button>
                  ))}
                </div>
                {!chat && (
                  <button
                    onClick={() => openChat(null)}
                    className="hidden items-center gap-1.5 rounded-full bg-sky px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-sky-dark sm:flex"
                  >
                    <span className="text-base leading-none">+</span> New claim
                  </button>
                )}
                <ProfileMenu profile={profile} onLogout={logout} />
              </div>
            </>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4">
        {profile && chat ? (
          <Session
            key={`${profile.id}-${chat.run}`}
            profile={profile}
            language={language}
            resumeId={chat.resumeId}
            onSessionId={onSessionId}
          />
        ) : profile ? (
          <Dashboard
            profile={profile}
            language={language}
            onNewClaim={() => openChat(null)}
            onResume={(id) => openChat(id)}
          />
        ) : (
          <Login onLogin={login} />
        )}
      </main>
    </div>
  );
}
