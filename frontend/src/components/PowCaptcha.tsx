"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { leadingZeroBits, sha256Ascii } from "@/lib/sha256";

type Phase = "idle" | "working" | "ready" | "error";

interface Challenge {
  challenge: string;
  difficulty: number;
  expiresIn: number;
}

/**
 * Solve the challenge on the main thread in slices.
 *
 * A Worker would avoid blocking the UI, but it needs a separately bundled
 * script and a CSP worker-src allowance. Yielding every few thousand hashes
 * keeps the page responsive for under a second of work, which is all this
 * difficulty costs, so the simpler approach wins.
 */
function solveWithYield(
  challenge: string,
  difficulty: number,
  onProgress: (attempts: number) => void,
  shouldStop: () => boolean
): Promise<{ nonce: string; hash: string; attempts: number }> {
  return new Promise((resolve, reject) => {
    const prefix = `${challenge}:`;
    let nonce = 0;
    let attempts = 0;
    const startedAt = performance.now();

    function slice() {
      if (shouldStop()) {
        reject(new Error("cancelled"));
        return;
      }
      const batchEnd = nonce + 3000;
      while (nonce < batchEnd) {
        const digest = sha256Ascii(prefix + nonce);
        attempts++;
        if (leadingZeroBits(digest) >= difficulty) {
          resolve({ nonce: String(nonce), hash: toHex(digest), attempts });
          return;
        }
        nonce++;
      }
      onProgress(attempts);
      // Give the event loop a turn so the page can paint.
      if (performance.now() - startedAt > 60_000) {
        reject(new Error("This is taking unusually long. Reload and try again."));
        return;
      }
      setTimeout(slice, 0);
    }

    setTimeout(slice, 0);
  });
}

function toHex(bytes: Uint8Array): string {
  let out = "";
  for (const byte of bytes) out += byte.toString(16).padStart(2, "0");
  return out;
}

export function PowCaptcha({
  onToken,
  label = "Bot check",
}: {
  /** Called with "<challenge>.<nonce>" when solved, or "" when it expires. */
  onToken: (token: string) => void;
  label?: string;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [attempts, setAttempts] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [difficulty, setDifficulty] = useState<number | null>(null);
  const cancelled = useRef(false);
  const started = useRef(false);

  const run = useCallback(async () => {
    cancelled.current = false;
    setPhase("working");
    setError(null);
    setAttempts(0);
    setDifficulty(null);

    try {
      const res = await fetch("/api/captcha/challenge", { cache: "no-store" });
      if (!res.ok) {
        setError("Could not start the bot check. Reload the page.");
        setPhase("error");
        return;
      }
      const data = (await res.json()) as Challenge;
      setDifficulty(data.difficulty);

      const result = await solveWithYield(
        data.challenge,
        data.difficulty,
        setAttempts,
        () => cancelled.current
      );
      if (cancelled.current) return;
      setAttempts(result.attempts);
      onToken(`${data.challenge}.${result.nonce}`);
      setPhase("ready");
    } catch (err) {
      if (cancelled.current) return;
      setError(err instanceof Error ? err.message : "The bot check failed.");
      setPhase("error");
    }
  }, [onToken]);

  // Solve once on mount. Strict Mode double-invokes effects in development,
  // which would burn two challenges, so guard with a ref.
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void run();
    return () => {
      cancelled.current = true;
    };
  }, [run]);

  return (
    <div className="rounded-lg border border-card-border bg-surface-muted p-3">
      <div className="flex items-center justify-between gap-3">
        <p className="m-0 text-xs font-semibold uppercase tracking-wide text-muted">
          {label} <span className="text-red">*</span>
        </p>
        {phase === "ready" && (
          <span className="text-xs font-semibold text-blue">Verified</span>
        )}
      </div>

      <div className="mt-2 flex items-center gap-3" role="status" aria-live="polite">
        {phase === "working" && (
          <span
            className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-card-border border-t-blue"
            aria-hidden
          />
        )}
        {phase === "ready" && (
          <span
            className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-blue text-xs font-bold text-white"
            aria-hidden
          >
            ✓
          </span>
        )}
        <p className="m-0 text-xs text-muted">
          {phase === "working" &&
            `Checking your browser… ${attempts.toLocaleString("en-US")} hashes`}
          {phase === "ready" && "Bot check passed. You can submit."}
          {phase === "error" && <span className="text-red">{error}</span>}
          {phase === "idle" && "Preparing…"}
        </p>
      </div>

      {phase === "error" && (
        <button
          type="button"
          onClick={() => void run()}
          className="mt-2 rounded-full border border-card-border bg-surface px-3 py-1 text-xs font-semibold text-muted hover:text-blue"
        >
          Retry bot check
        </button>
      )}

      {difficulty !== null && phase === "working" && (
        <p className="m-0 mt-1 text-[11px] text-muted">
          This is a self-hosted proof-of-work check. It costs a bot real CPU time
          and costs us nothing.
        </p>
      )}
    </div>
  );
}
