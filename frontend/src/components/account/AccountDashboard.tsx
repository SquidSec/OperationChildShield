"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ALERT_LABELS, type AlertSubscription, type SavedMember } from "@/lib/user-types";

async function api(path: string, method: string, body?: unknown): Promise<Response> {
  return fetch(path, {
    method,
    credentials: "same-origin",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
}

export function AccountDashboard({
  initialSaved,
  initialAlerts,
}: {
  initialSaved: SavedMember[];
  initialAlerts: AlertSubscription[];
}) {
  const router = useRouter();
  const [saved, setSaved] = useState(initialSaved);
  const [alerts, setAlerts] = useState(initialAlerts);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function removeMember(id: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await api(`/api/account/saved-members/${encodeURIComponent(id)}`, "DELETE");
      if (!res.ok) {
        setError("Could not remove that lawmaker.");
        return;
      }
      const body = (await res.json()) as { members: SavedMember[] };
      setSaved(body.members);
    } finally {
      setBusy(false);
    }
  }

  async function refreshAlerts() {
    const res = await fetch("/api/account/alerts", { credentials: "same-origin" });
    if (res.ok) {
      const body = (await res.json()) as { alerts: AlertSubscription[] };
      setAlerts(body.alerts);
    }
  }

  async function toggleAlert(kind: AlertSubscription["kind"]) {
    const active = alerts.some((a) => a.kind === kind && a.active);

    if (!active && kind === "member_vote" && saved.length === 0) {
      setError(
        "Save a lawmaker first. Member vote alerts follow the people in your saved list."
      );
      return;
    }

    setBusy(true);
    setError(null);
    try {
      if (active) {
        // member_vote subscriptions are per lawmaker, so clear them all.
        const targets =
          kind === "member_vote"
            ? saved.map((m) => m.bioguideId)
            : [""];
        for (const id of targets) {
          const qs = id ? `?bioguideId=${encodeURIComponent(id)}` : "";
          await api(`/api/account/alerts/${kind}${qs}`, "DELETE");
        }
        await refreshAlerts();
        return;
      }

      // member_vote follows every saved lawmaker, so the toggle matches the list.
      const targets =
        kind === "member_vote" ? saved.map((m) => m.bioguideId) : [""];
      for (const id of targets) {
        const res = await api("/api/account/alerts", "POST", {
          kind,
          bioguideId: id,
        });
        if (!res.ok) {
          const body = (await res.json().catch(() => ({}))) as { detail?: string };
          setError(body.detail ?? "Could not update alerts.");
          return;
        }
      }
      await refreshAlerts();
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    await api("/api/account/logout", "POST");
    router.replace("/account");
    router.refresh();
  }

  return (
    <div className="mt-8 space-y-6">
      <section className="rounded-xl border border-card-border bg-surface p-5">
        <h2 className="m-0 text-sm font-semibold uppercase tracking-wide text-muted">
          Lawmakers you follow
        </h2>
        {saved.length === 0 ? (
          <p className="mt-3 text-sm text-muted">
            Nothing saved yet.{" "}
            <Link href="/" className="text-red font-semibold hover:underline">
              Find your lawmakers
            </Link>{" "}
            and use “Save to my account” on their page.
          </p>
        ) : (
          <ul className="mt-3 space-y-2">
            {saved.map((member) => (
              <li key={member.bioguideId} className="flex items-center justify-between gap-3 text-sm">
                <Link href={`/member/${member.bioguideId}`} className="text-red font-semibold hover:underline">
                  {member.name || member.bioguideId}
                </Link>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => removeMember(member.bioguideId)}
                  className="text-xs text-muted hover:text-red disabled:opacity-50"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-xl border border-card-border bg-surface p-5">
        <h2 className="m-0 text-sm font-semibold uppercase tracking-wide text-muted">
          Email alerts
        </h2>
        <ul className="mt-3 space-y-3">
          {(Object.keys(ALERT_LABELS) as AlertSubscription["kind"][]).map((kind) => {
            const active = alerts.find((a) => a.kind === kind && a.active);
            return (
              <li key={kind} className="flex items-center justify-between gap-3 text-sm">
                <span>{ALERT_LABELS[kind]}</span>
                <button
                  type="button"
                  disabled={busy}
                  aria-pressed={Boolean(active)}
                  onClick={() => toggleAlert(kind)}
                  className={
                    active
                      ? "rounded-full bg-blue px-3 py-1 text-xs font-semibold text-white disabled:opacity-50"
                      : "rounded-full border border-card-border px-3 py-1 text-xs font-semibold text-muted hover:text-blue disabled:opacity-50"
                  }
                >
                  {active ? "On" : "Off"}
                </button>
              </li>
            );
          })}
        </ul>
        <p className="mt-3 text-xs text-muted">
          Every alert email includes a one-click unsubscribe link. We never sell
          your address.
        </p>
      </section>

      {error && (
        <p role="alert" className="rounded-lg border border-red/40 bg-red/5 p-3 text-sm text-red">
          {error}
        </p>
      )}

      <button
        type="button"
        onClick={signOut}
        className="rounded-full border border-card-border bg-surface px-4 py-2 text-sm font-semibold text-muted hover:text-blue"
      >
        Sign out
      </button>
    </div>
  );
}
