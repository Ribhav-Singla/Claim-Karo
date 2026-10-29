"use client";

// Hands-free listening for the call screen. The mic stays open while `active`; whenever
// `canListen` is true one utterance is recorded and ended by a pause, judged from the input
// level. Speaking over the bot (`botSpeaking`) calls `onBargeIn` and records that instead.
import { useEffect, useRef, useState } from "react";

const SPEECH_LEVEL = 0.02; // RMS above this counts as speech
const MIN_SPEECH_MS = 150; // shorter bursts (clicks, bumps) are ignored
const BARGE_LEVEL = 0.06; // louder bar while the bot talks, so its own echo doesn't count
const BARGE_MS = 300;
const END_PAUSE_MS = 700; // silence after speech that ends the utterance
const MAX_UTTERANCE_MS = 30_000;
const IDLE_RESTART_MS = 10_000; // restart the recorder so a long silence isn't uploaded
const TICK_MS = 50;

type Options = {
  active: boolean;
  canListen: boolean;
  botSpeaking: boolean;
  onUtterance: (blob: Blob, mime: string) => void;
  onBargeIn: () => void;
};

export function useHandsFree({ active, canListen, botSpeaking, onUtterance, onBargeIn }: Options) {
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hearing, setHearing] = useState(false);
  const live = useRef({ botSpeaking, onUtterance, onBargeIn });

  useEffect(() => {
    live.current = { botSpeaking, onUtterance, onBargeIn };
  }, [botSpeaking, onUtterance, onBargeIn]);

  // one mic permission for the whole call
  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    let mic: MediaStream | null = null;
    setError(null);
    navigator.mediaDevices
      .getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } })
      .then((m) => {
        if (cancelled) return m.getTracks().forEach((t) => t.stop());
        mic = m;
        setStream(m);
      })
      .catch(() => !cancelled && setError("Microphone not available. Please allow it or type instead."));
    return () => {
      cancelled = true;
      mic?.getTracks().forEach((t) => t.stop());
      setStream(null);
    };
  }, [active]);

  useEffect(() => {
    if (!stream || !canListen) return;
    const ctx = new AudioContext();
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 1024;
    ctx.createMediaStreamSource(stream).connect(analyser);
    const samples = new Float32Array(analyser.fftSize);

    let rec: MediaRecorder;
    let finish: () => void;
    let startedAt = 0;
    let lastVoice = 0;
    let loudMs = 0;
    let spoke = false;
    let wasSpeaking = live.current.botSpeaking;

    function record() {
      const chunks: Blob[] = [];
      const r = new MediaRecorder(stream!);
      let keep = false;
      r.ondataavailable = (e) => chunks.push(e.data);
      r.onstop = () => keep && live.current.onUtterance(new Blob(chunks, { type: r.mimeType }), r.mimeType);
      r.start();
      rec = r;
      startedAt = performance.now();
      loudMs = 0;
      finish = () => {
        keep = true;
        r.stop();
      };
    }

    function restart() {
      rec.stop(); // discarded: keep is false
      record();
    }

    record();
    const timer = setInterval(() => {
      const { botSpeaking } = live.current;
      const now = performance.now();
      // the bot just finished: drop the recording so its echo isn't sent as the user's words
      if (wasSpeaking && !botSpeaking && !spoke) restart();
      wasSpeaking = botSpeaking;

      analyser.getFloatTimeDomainData(samples);
      const rms = Math.sqrt(samples.reduce((sum, x) => sum + x * x, 0) / samples.length);
      const loud = rms > (botSpeaking ? BARGE_LEVEL : SPEECH_LEVEL);
      loudMs = loud ? loudMs + TICK_MS : 0;
      if (spoke && rms > SPEECH_LEVEL) lastVoice = now;

      if (!spoke && loudMs >= (botSpeaking ? BARGE_MS : MIN_SPEECH_MS)) {
        spoke = true;
        lastVoice = now;
        setHearing(true);
        if (botSpeaking) live.current.onBargeIn();
      }
      if (spoke && (now - lastVoice > END_PAUSE_MS || now - startedAt > MAX_UTTERANCE_MS)) {
        clearInterval(timer);
        finish();
      } else if (!spoke && !botSpeaking && now - startedAt > IDLE_RESTART_MS) {
        restart();
      }
    }, TICK_MS);

    return () => {
      clearInterval(timer);
      if (rec.state !== "inactive") rec.stop(); // turn moved on or call ended: discard
      ctx.close();
      setHearing(false);
    };
  }, [stream, canListen]);

  return { ready: stream !== null, listening: stream !== null && canListen, hearing, error };
}
