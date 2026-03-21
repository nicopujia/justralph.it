import { useState, useCallback, useRef } from "react";

const LS_KEY = "ralph_sound_enabled";

function getInitial(): boolean {
  try {
    return localStorage.getItem(LS_KEY) === "true";
  } catch {
    return false;
  }
}

/** Play a short two-tone chime via Web Audio API. Uses a shared AudioContext. */
function playChime(ctx: AudioContext, freq1: number, freq2: number, duration = 0.12) {
  const now = ctx.currentTime;

  const osc1 = ctx.createOscillator();
  const gain1 = ctx.createGain();
  osc1.type = "sine";
  osc1.frequency.value = freq1;
  gain1.gain.setValueAtTime(0.18, now);
  gain1.gain.exponentialRampToValueAtTime(0.001, now + duration);
  osc1.connect(gain1);
  gain1.connect(ctx.destination);
  osc1.start(now);
  osc1.stop(now + duration);

  // Second tone slightly after
  const osc2 = ctx.createOscillator();
  const gain2 = ctx.createGain();
  osc2.type = "sine";
  osc2.frequency.value = freq2;
  gain2.gain.setValueAtTime(0.14, now + duration * 0.6);
  gain2.gain.exponentialRampToValueAtTime(0.001, now + duration * 1.6);
  osc2.connect(gain2);
  gain2.connect(ctx.destination);
  osc2.start(now + duration * 0.6);
  osc2.stop(now + duration * 1.6);
}

export function useSoundNotification() {
  const [enabled, setEnabled] = useState<boolean>(getInitial);
  // Lazily created; browsers require user gesture before AudioContext can produce sound.
  const ctxRef = useRef<AudioContext | null>(null);

  function getCtx(): AudioContext | null {
    try {
      if (!ctxRef.current) {
        ctxRef.current = new AudioContext();
      }
      // Resume if suspended (autoplay policy)
      if (ctxRef.current.state === "suspended") {
        ctxRef.current.resume();
      }
      return ctxRef.current;
    } catch {
      return null;
    }
  }

  const toggle = useCallback(() => {
    setEnabled((prev) => {
      const next = !prev;
      try { localStorage.setItem(LS_KEY, String(next)); } catch { /* noop */ }
      // Ensure context is created on first user interaction
      getCtx();
      return next;
    });
  }, []);

  /** Played when Ralphy finishes responding (assistant message received). */
  const playResponseDone = useCallback(() => {
    if (!enabled) return;
    const ctx = getCtx();
    if (!ctx) return;
    // Soft descending chime: 880 -> 660 Hz
    playChime(ctx, 880, 660);
  }, [enabled]);

  /** Played when "Just Ralph It" becomes available (readiness threshold). */
  const playReadyToRalph = useCallback(() => {
    if (!enabled) return;
    const ctx = getCtx();
    if (!ctx) return;
    // Ascending chime: 660 -> 990 Hz -- signals something is ready
    playChime(ctx, 660, 990, 0.15);
  }, [enabled]);

  return { enabled, toggle, playResponseDone, playReadyToRalph };
}
