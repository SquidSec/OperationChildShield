"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { AdminSession } from "@/lib/admin-types";
import { formatUtcTimestamp } from "@/lib/format";

const MIN_PASSWORD_LENGTH = 12;

export function AdminAccountPanels({
  mfaEnabled,
  sessions,
}: {
  mfaEnabled: boolean;
  sessions: AdminSession[];
}) {
  return (
    <div className="mt-6 space-y-6">
      <PasswordForm />
      <MfaPanel mfaEnabled={mfaEnabled} />
      <SessionsPanel sessions={sessions} />
    </div>
  );
}

function Panel({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-card-border bg-surface p-5 shadow-sm">
      <h2 className="m-0 text-sm font-semibold uppercase tracking-wide text-muted">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function Feedback({ error, notice }: { error: string | null; notice: string | null }) {
  if (error) {
    return (
      <p role="alert" className="m-0 text-sm text-red">
        {error}
      </p>
    );
  }
  if (notice) {
    return <p className="m-0 text-sm text-muted">{notice}</p>;
  }
  return null;
}

const inputClass =
  "mt-1 block w-full rounded-lg border border-card-border bg-surface px-3 py-2 text-sm font-normal normal-case tracking-normal text-foreground outline-none focus:border-blue focus:ring-2 focus:ring-blue/20";

function PasswordForm() {
  const router = useRouter();
  const [status, setStatus] = useState<"idle" | "submitting">("idle");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    const form = event.currentTarget;
    const data = new FormData(form);
    const newPassword = String(data.get("new_password") ?? "");
    if (newPassword.length < MIN_PASSWORD_LENGTH) {
      setError(`New password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }
    if (newPassword !== String(data.get("confirm_password") ?? "")) {
      setError("New password and confirmation do not match.");
      return;
    }

    setStatus("submitting");
    try {
      const res = await fetch("/api/admin/password", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_password: String(data.get("current_password") ?? ""),
          new_password: newPassword,
        }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as
          | { detail?: string | { msg?: string }[] }
          | null;
        const detail = body?.detail;
        setError(
          typeof detail === "string"
            ? detail
            : Array.isArray(detail)
              ? (detail[0]?.msg ?? "Could not change the password.")
              : "Could not change the password."
        );
        return;
      }
      const body = (await res.json().catch(() => null)) as
        | { revokedSessions?: number }
        | null;
      const revoked = body?.revokedSessions ?? 0;
      setNotice(
        revoked > 0
          ? `Password changed. ${revoked} other session${revoked === 1 ? "" : "s"} signed out.`
          : "Password changed."
      );
      form.reset();
      router.refresh();
    } catch {
      setError("Could not change the password. Check your connection and try again.");
    } finally {
      setStatus("idle");
    }
  }

  return (
    <Panel title="Password">
      <form className="grid gap-4 sm:grid-cols-3" onSubmit={onSubmit} noValidate>
        <label className="text-xs font-semibold uppercase tracking-wide text-muted">
          Current password
          <input
            name="current_password"
            type="password"
            required
            autoComplete="current-password"
            maxLength={1024}
            className={inputClass}
          />
        </label>
        <label className="text-xs font-semibold uppercase tracking-wide text-muted">
          New password
          <input
            name="new_password"
            type="password"
            required
            minLength={MIN_PASSWORD_LENGTH}
            autoComplete="new-password"
            maxLength={1024}
            className={inputClass}
          />
        </label>
        <label className="text-xs font-semibold uppercase tracking-wide text-muted">
          Confirm
          <input
            name="confirm_password"
            type="password"
            required
            minLength={MIN_PASSWORD_LENGTH}
            autoComplete="new-password"
            maxLength={1024}
            className={inputClass}
          />
        </label>
        <div className="sm:col-span-3 space-y-3">
          <Feedback error={error} notice={notice} />
          <button
            type="submit"
            disabled={status === "submitting"}
            className="rounded-full bg-blue px-4 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {status === "submitting" ? "Changing…" : "Change password"}
          </button>
        </div>
      </form>
      <p className="mt-3 text-xs text-muted">
        At least {MIN_PASSWORD_LENGTH} characters. Changing it signs out your other
        sessions.
      </p>
    </Panel>
  );
}

function MfaPanel({ mfaEnabled: initialEnabled }: { mfaEnabled: boolean }) {
  const router = useRouter();
  const [enabled, setEnabled] = useState(initialEnabled);
  const [setup, setSetup] = useState<{ secret: string; otpauthUri: string } | null>(null);
  const [code, setCode] = useState("");
  const [status, setStatus] = useState<"idle" | "submitting">("idle");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function startSetup() {
    setStatus("submitting");
    setError(null);
    setNotice(null);
    try {
      const res = await fetch("/api/admin/mfa/setup", {
        method: "POST",
        credentials: "same-origin",
      });
      if (!res.ok) {
        setError("Could not start MFA setup. Try again.");
        return;
      }
      setSetup((await res.json()) as { secret: string; otpauthUri: string });
    } catch {
      setError("Could not start MFA setup. Check your connection and try again.");
    } finally {
      setStatus("idle");
    }
  }

  async function verifyCode(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("submitting");
    setError(null);
    setNotice(null);
    try {
      const res = await fetch("/api/admin/mfa/enable", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
      });
      if (!res.ok) {
        setError("That code is not valid. Check your authenticator and try again.");
        return;
      }
      setEnabled(true);
      setSetup(null);
      setCode("");
      setNotice("Two-factor authentication is on.");
      router.refresh();
    } catch {
      setError("Could not verify the code. Check your connection and try again.");
    } finally {
      setStatus("idle");
    }
  }

  return (
    <Panel title="Two-factor authentication">
      <p className="m-0 text-sm text-muted">
        Status:{" "}
        <span className={enabled ? "font-semibold text-foreground" : "font-semibold text-red"}>
          {enabled ? "On" : "Off"}
        </span>
      </p>

      <p className="mt-2 text-xs text-muted">
        Two-factor authentication is required for every admin account and cannot
        be turned off, here or anywhere else.
      </p>

      {enabled ? (
        <p className="mt-3 rounded-lg border border-card-border bg-surface-muted p-3 text-xs text-muted">
          To replace a lost device, ask an owner to reset your OTP. You will set up
          a new authenticator at your next sign-in.
        </p>
      ) : setup ? (
        <div className="mt-4 space-y-4">
          <p className="m-0 text-sm text-muted">
            Add this secret to your authenticator app, then enter the current
            6-digit code to confirm.
          </p>
          <div className="rounded-lg border border-card-border bg-surface-muted p-3">
            <p className="m-0 text-[11px] font-semibold uppercase tracking-wide text-muted">
              Secret
            </p>
            <p className="m-0 mt-1 break-all font-mono text-sm text-foreground">{setup.secret}</p>
            <p className="m-0 mt-3 text-[11px] font-semibold uppercase tracking-wide text-muted">
              Setup URI
            </p>
            <p className="m-0 mt-1 break-all font-mono text-[11px] text-muted">
              {setup.otpauthUri}
            </p>
          </div>
          <form className="flex flex-wrap items-end gap-3" onSubmit={verifyCode}>
            <label className="text-xs font-semibold uppercase tracking-wide text-muted">
              Code
              <input
                value={code}
                onChange={(event) => setCode(event.target.value)}
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={8}
                required
                className={`${inputClass} w-32 font-mono tracking-widest`}
              />
            </label>
            <button
              type="submit"
              disabled={status === "submitting"}
              className="rounded-full bg-blue px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              {status === "submitting" ? "Verifying…" : "Enable MFA"}
            </button>
            <button
              type="button"
              onClick={() => setSetup(null)}
              className="rounded-full border border-card-border px-4 py-2 text-sm font-semibold text-muted"
            >
              Cancel
            </button>
          </form>
        </div>
      ) : (
        <button
          type="button"
          onClick={startSetup}
          disabled={status === "submitting"}
          className="mt-4 rounded-full border border-card-border px-4 py-2 text-sm font-semibold text-muted hover:text-blue disabled:opacity-50"
        >
          Set up MFA
        </button>
      )}

      <div className="mt-3">
        <Feedback error={error} notice={notice} />
      </div>
    </Panel>
  );
}

function SessionsPanel({ sessions }: { sessions: AdminSession[] }) {
  const router = useRouter();
  const [status, setStatus] = useState<"idle" | "submitting">("idle");
  const [error, setError] = useState<string | null>(null);

  async function revokeAll() {
    setStatus("submitting");
    setError(null);
    try {
      const res = await fetch("/api/admin/sessions/revoke-all", {
        method: "POST",
        credentials: "same-origin",
      });
      if (!res.ok) {
        setError("Could not revoke sessions. Try again.");
        return;
      }
      router.replace("/admin/login");
      router.refresh();
    } catch {
      setError("Could not revoke sessions. Check your connection and try again.");
    } finally {
      setStatus("idle");
    }
  }

  return (
    <Panel title="Sessions">
      <ul className="m-0 list-none space-y-3 p-0">
        {sessions.map((session) => (
          <li
            key={session.id}
            className="rounded-lg border border-card-border bg-surface-muted p-3 text-sm"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="font-mono text-xs text-muted">{session.id}…</span>
              {session.isCurrent && (
                <span className="text-[11px] font-semibold uppercase tracking-wide text-blue">
                  this session
                </span>
              )}
            </div>
            <p className="m-0 mt-1 truncate text-xs text-muted" title={session.userAgent ?? ""}>
              {session.userAgent || "Unknown client"} · {session.ip || "unknown IP"}
            </p>
            <p className="m-0 mt-1 text-[11px] text-muted">
              Started {formatUtcTimestamp(session.createdAt)} · expires{" "}
              {formatUtcTimestamp(session.expiresAt)}
            </p>
          </li>
        ))}
      </ul>

      <div className="mt-4 space-y-3">
        <Feedback error={error} notice={null} />
        <button
          type="button"
          onClick={revokeAll}
          disabled={status === "submitting"}
          className="rounded-full border border-red/40 px-4 py-2 text-sm font-semibold text-red hover:bg-red/5 disabled:opacity-50"
        >
          {status === "submitting" ? "Revoking…" : "Revoke all sessions"}
        </button>
        <p className="m-0 text-xs text-muted">
          Revoking all sessions signs this browser out too.
        </p>
      </div>
    </Panel>
  );
}
