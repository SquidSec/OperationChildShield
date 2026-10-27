"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

export function VerifyClient({ token }: { token: string }) {
  const [state, setState] = useState<"working" | "done" | "error">("working");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function run() {
      try {
        const res = await fetch("/api/account/verify", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token }),
        });
        if (cancelled) return;
        if (!res.ok) {
          const body = (await res.json().catch(() => ({}))) as { detail?: string };
          setMessage(body.detail ?? "This link is invalid or has expired.");
          setState("error");
          return;
        }
        setState("done");
      } catch {
        if (!cancelled) {
          setMessage("Network error. Please try again.");
          setState("error");
        }
      }
    }
    void run();
    return () => {
      cancelled = true;
    };
  }, [token]);

  if (state === "working") {
    return <p className="mt-4 text-sm text-muted" role="status">Confirming your email…</p>;
  }
  if (state === "error") {
    return (
      <div className="mt-4">
        <p role="alert" className="rounded-lg border border-red/40 bg-red/5 p-3 text-sm text-red">
          {message}
        </p>
        <Link href="/account" className="mt-4 inline-block text-sm text-red font-semibold hover:underline">
          Back to sign in
        </Link>
      </div>
    );
  }
  return (
    <div className="mt-4">
      <p role="status" className="rounded-lg border border-blue/30 bg-blue/5 p-3 text-sm text-blue">
        Your email is confirmed and you are signed in.
      </p>
      <Link
        href="/account/dashboard"
        className="mt-4 inline-block rounded-full bg-blue px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
      >
        Go to your account
      </Link>
    </div>
  );
}
