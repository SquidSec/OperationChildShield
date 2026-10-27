"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

export function ResetPasswordClient({ token }: { token: string }) {
  const [state, setState] = useState<"idle" | "submitting" | "done" | "error">("idle");
  const [message, setMessage] = useState("");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setState("submitting");
    const data = new FormData(event.currentTarget);
    const password = String(data.get("password") ?? "");
    const confirm = String(data.get("confirm") ?? "");
    if (password !== confirm) {
      setMessage("Passwords do not match.");
      setState("error");
      return;
    }
    try {
      const res = await fetch("/api/account/password/reset", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, password }),
      });
      const body = (await res.json().catch(() => ({}))) as { detail?: string; message?: string };
      if (!res.ok) {
        setMessage(body.detail ?? "This link is invalid or has expired.");
        setState("error");
        return;
      }
      setMessage(body.message ?? "Password updated.");
      setState("done");
    } catch {
      setMessage("Network error. Please try again.");
      setState("error");
    }
  }

  if (state === "done") {
    return (
      <div className="mt-4">
        <p role="status" className="rounded-lg border border-blue/30 bg-blue/5 p-3 text-sm text-blue">
          {message}
        </p>
        <Link href="/account" className="mt-4 inline-block text-sm text-red font-semibold hover:underline">
          Sign in
        </Link>
      </div>
    );
  }

  return (
    <form className="mt-4 space-y-4" onSubmit={onSubmit} noValidate>
      <div>
        <label htmlFor="new-password" className="block text-xs font-semibold uppercase tracking-wide text-muted">
          New password
        </label>
        <input
          id="new-password"
          name="password"
          type="password"
          autoComplete="new-password"
          required
          minLength={15}
          maxLength={1024}
          className="mt-1 w-full rounded-lg border border-card-border bg-surface px-3 py-2 text-sm text-foreground outline-none focus:border-blue focus:ring-2 focus:ring-blue/20"
        />
        <p className="mt-1 text-[11px] text-muted">At least 15 characters. A short phrase works well.</p>
      </div>
      <div>
        <label htmlFor="confirm-password" className="block text-xs font-semibold uppercase tracking-wide text-muted">
          Confirm password
        </label>
        <input
          id="confirm-password"
          name="confirm"
          type="password"
          autoComplete="new-password"
          required
          maxLength={1024}
          className="mt-1 w-full rounded-lg border border-card-border bg-surface px-3 py-2 text-sm text-foreground outline-none focus:border-blue focus:ring-2 focus:ring-blue/20"
        />
      </div>

      {state === "error" && (
        <p role="alert" className="rounded-lg border border-red/40 bg-red/5 p-3 text-sm text-red">
          {message}
        </p>
      )}

      <button
        type="submit"
        disabled={state === "submitting"}
        className="w-full rounded-full bg-blue px-4 py-2.5 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
      >
        {state === "submitting" ? "Updating…" : "Update password"}
      </button>
    </form>
  );
}
