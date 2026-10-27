"use client";

import { useState } from "react";

/**
 * Saves a lawmaker to the signed-in constituent's account. Renders a sign-in
 * link when the visitor is anonymous so the control is never a dead end.
 */
export function SaveMemberButton({
  bioguideId,
  name,
  state,
  initiallySaved = false,
  signedIn = false,
}: {
  bioguideId: string;
  name: string;
  state: string;
  initiallySaved?: boolean;
  signedIn?: boolean;
}) {
  const [saved, setSaved] = useState(initiallySaved);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!signedIn) {
    return (
      <a
        href={`/account?next=/member/${bioguideId}`}
        className="inline-flex items-center gap-2 rounded-full border border-card-border bg-surface px-4 py-2 text-sm font-semibold text-muted no-underline hover:text-blue"
      >
        Save to my account
      </a>
    );
  }

  async function toggle() {
    setBusy(true);
    setError(null);
    try {
      const res = saved
        ? await fetch(`/api/account/saved-members/${encodeURIComponent(bioguideId)}`, {
            method: "DELETE",
            credentials: "same-origin",
          })
        : await fetch("/api/account/saved-members", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ bioguideId, name, state }),
          });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { detail?: string };
        setError(body.detail ?? "Could not update saved lawmakers.");
        return;
      }
      setSaved(!saved);
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="inline-flex flex-col items-start gap-1">
      <button
        type="button"
        onClick={toggle}
        disabled={busy}
        aria-pressed={saved}
        className={
          saved
            ? "rounded-full bg-blue px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            : "rounded-full border border-card-border bg-surface px-4 py-2 text-sm font-semibold text-muted hover:text-blue disabled:opacity-50"
        }
      >
        {saved ? "Saved ✓" : "Save to my account"}
      </button>
      {error && <span className="text-xs text-red">{error}</span>}
    </span>
  );
}
