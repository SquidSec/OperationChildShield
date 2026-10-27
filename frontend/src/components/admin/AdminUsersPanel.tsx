"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { roleBadgeClass, roleLabel } from "@/lib/admin-format";
import type { AdminRole, AdminUser } from "@/lib/admin-types";
import { formatUtcTimestamp } from "@/lib/format";

const ROLE_OPTIONS: AdminRole[] = ["viewer", "editor", "owner"];

type Pending = { action: string; userId: number } | null;

export function AdminUsersPanel({
  users,
  currentUserId,
}: {
  users: AdminUser[];
  currentUserId: number;
}) {
  const router = useRouter();
  const [pending, setPending] = useState<Pending>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // Password reset panel, keyed by user id.
  const [resetFor, setResetFor] = useState<AdminUser | null>(null);
  const [newPassword, setNewPassword] = useState("");
  // Delete confirmation, keyed by user id.
  const [deleteFor, setDeleteFor] = useState<AdminUser | null>(null);

  async function post(
    path: string,
    action: string,
    userId: number,
    body?: Record<string, string>,
    method: "POST" | "DELETE" = "POST"
  ): Promise<boolean> {
    setPending({ action, userId });
    setError(null);
    setNotice(null);
    try {
      const res = await fetch(path, {
        method,
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as { detail?: string } | null;
        setError(body?.detail ?? "That action failed. Try again.");
        return false;
      }
      // Return true so callers close their panel only on success.
      setNotice("Saved.");
      router.refresh();
      return true;
    } catch {
      setError("That action failed. Check your connection and try again.");
      return false;
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="mt-6 space-y-6">
      {error && (
        <p role="alert" className="m-0 rounded-xl border border-red/40 bg-red/5 p-4 text-sm text-red">
          {error}
        </p>
      )}
      {notice && (
        <p className="m-0 rounded-xl border border-card-border bg-surface p-4 text-sm text-muted">
          {notice}
        </p>
      )}

      <section className="rounded-xl border border-card-border bg-surface p-5 shadow-sm">
        <h2 className="m-0 text-sm font-semibold uppercase tracking-wide text-muted">
          Accounts
        </h2>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[720px] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-card-border">
                {["Email", "Name", "Role", "Status", "MFA", "Last sign-in", "Actions"].map(
                  (heading) => (
                    <th
                      key={heading}
                      scope="col"
                      className="pb-2 pr-4 text-[11px] font-semibold uppercase tracking-wide text-muted"
                    >
                      {heading}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody>
              {users.map((user) => {
                const isSelf = user.id === currentUserId;
                return (
                  <tr key={user.id} className="border-b border-card-border/60 last:border-0">
                    <td className="py-3 pr-4 text-foreground">
                      {user.email}
                      {isSelf && (
                        <span className="ml-2 text-[11px] font-semibold uppercase text-muted">
                          you
                        </span>
                      )}
                    </td>
                    <td className="py-3 pr-4 text-muted">{user.displayName}</td>
                    <td className="py-3 pr-4">
                      <span
                        className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${roleBadgeClass(user.role)}`}
                      >
                        {roleLabel(user.role)}
                      </span>
                    </td>
                    <td className="py-3 pr-4">
                      <span className={user.isActive ? "text-foreground" : "text-red"}>
                        {user.isActive ? "Active" : "Disabled"}
                      </span>
                    </td>
                    <td className="py-3 pr-4 text-muted">{user.mfaEnabled ? "On" : "Off"}</td>
                    <td className="whitespace-nowrap py-3 pr-4 text-xs text-muted">
                      {user.lastLoginAt ? formatUtcTimestamp(user.lastLoginAt) : "never"}
                    </td>
                    <td className="py-3 pr-4">
                      <div className="flex flex-wrap gap-2">
                        {isSelf ? (
                          <span className="text-xs text-muted">Manage in Account</span>
                        ) : (
                          <>
                            <button
                              type="button"
                              disabled={pending !== null}
                              onClick={() =>
                                post(
                                  `/api/admin/users/${user.id}/${user.isActive ? "disable" : "enable"}`,
                                  user.isActive ? "disable" : "enable",
                                  user.id
                                )
                              }
                              className="rounded-full border border-card-border px-3 py-1 text-xs font-semibold text-muted hover:text-blue disabled:opacity-50"
                            >
                              {pending?.userId === user.id &&
                              pending.action === (user.isActive ? "disable" : "enable")
                                ? "Saving…"
                                : user.isActive
                                  ? "Disable"
                                  : "Enable"}
                            </button>
                            <select
                              aria-label={`Role for ${user.email}`}
                              value={user.role}
                              disabled={pending !== null}
                              onChange={(event) =>
                                post(`/api/admin/users/${user.id}/role`, "role", user.id, {
                                  role: event.target.value,
                                })
                              }
                              className="rounded-full border border-card-border bg-surface px-2 py-1 text-xs text-muted"
                            >
                              {ROLE_OPTIONS.map((role) => (
                                <option key={role} value={role}>
                                  {roleLabel(role)}
                                </option>
                              ))}
                            </select>
                            <button
                              type="button"
                              disabled={pending !== null}
                              onClick={() => {
                                setResetFor(user);
                                setNewPassword("");
                                setError(null);
                              }}
                              className="rounded-full border border-card-border px-3 py-1 text-xs font-semibold text-muted hover:text-blue disabled:opacity-50"
                            >
                              Reset password
                            </button>
                            <button
                              type="button"
                              disabled={pending !== null}
                              onClick={() =>
                                post(`/api/admin/users/${user.id}/revoke`, "revoke", user.id)
                              }
                              className="rounded-full border border-card-border px-3 py-1 text-xs font-semibold text-muted hover:text-blue disabled:opacity-50"
                            >
                              Revoke sessions
                            </button>
                            <button
                              type="button"
                              disabled={pending !== null}
                              onClick={() => {
                                setDeleteFor(user);
                                setError(null);
                              }}
                              className="rounded-full border border-red/40 px-3 py-1 text-xs font-semibold text-red hover:bg-red/5 disabled:opacity-50"
                            >
                              Delete
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {resetFor && (
        <section className="rounded-xl border border-card-border bg-surface p-5 shadow-sm">
          <h2 className="m-0 text-sm font-semibold uppercase tracking-wide text-muted">
            Reset password
          </h2>
          <p className="mt-2 text-sm text-muted">
            Set a new password for <strong className="text-foreground">{resetFor.email}</strong>.
            Their sessions will be signed out. OTP settings are unchanged.
          </p>
          <form
            aria-label="Reset password"
            className="mt-4 flex flex-wrap items-end gap-3"
            onSubmit={async (event) => {
              event.preventDefault();
              const ok = await post(
                `/api/admin/users/${resetFor.id}/reset-password`,
                "reset-password",
                resetFor.id,
                { new_password: newPassword }
              );
              if (ok) {
                setResetFor(null);
                setNewPassword("");
              }
            }}
          >
            <label className="flex-1 text-xs font-semibold uppercase tracking-wide text-muted">
              New password
              <input
                id="reset-new-password"
                type="password"
                required
                minLength={15}
                maxLength={128}
                autoComplete="new-password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                className="mt-1 w-full rounded-lg border border-card-border bg-surface px-3 py-2 text-sm text-foreground outline-none focus:border-blue focus:ring-2 focus:ring-blue/20"
              />
            </label>
            <button
              type="submit"
              disabled={pending !== null || newPassword.length < 15}
              className="rounded-full bg-blue px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
            >
              {pending?.action === "reset-password" ? "Saving…" : "Set password"}
            </button>
            <button
              type="button"
              onClick={() => setResetFor(null)}
              className="rounded-full border border-card-border px-4 py-2 text-sm font-semibold text-muted hover:text-blue"
            >
              Cancel
            </button>
          </form>
          <p className="mt-3 text-xs text-muted">
            At least 15 characters. Breached passwords and the organization name
            are rejected. The password is never shown again, so share it out of band.
          </p>
        </section>
      )}

      {deleteFor && (
        <section className="rounded-xl border border-red/40 bg-red/5 p-5">
          <h2 className="m-0 text-sm font-semibold uppercase tracking-wide text-red">
            Delete account
          </h2>
          <p className="mt-2 text-sm text-foreground">
            Permanently delete <strong>{deleteFor.email}</strong>? Their sessions
            are revoked and the account cannot be recovered. Audit log entries are
            kept.
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              disabled={pending !== null}
              onClick={async () => {
                const ok = await post(
                  `/api/admin/users/${deleteFor.id}`,
                  "delete",
                  deleteFor.id,
                  undefined,
                  "DELETE"
                );
                if (ok) setDeleteFor(null);
              }}
              className="rounded-full bg-red px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
            >
              {pending?.action === "delete" ? "Deleting…" : "Delete permanently"}
            </button>
            <button
              type="button"
              onClick={() => setDeleteFor(null)}
              className="rounded-full border border-card-border bg-surface px-4 py-2 text-sm font-semibold text-muted hover:text-blue"
            >
              Cancel
            </button>
          </div>
        </section>
      )}

      <CreateUserForm onCreated={() => router.refresh()} />
    </div>
  );
}

function CreateUserForm({ onCreated }: { onCreated: () => void }) {
  const [status, setStatus] = useState<"idle" | "submitting">("idle");
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<string | null>(null);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setCreated(null);
    const form = event.currentTarget;
    const data = new FormData(form);
    setStatus("submitting");
    try {
      const res = await fetch("/api/admin/users", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: String(data.get("email") ?? ""),
          display_name: String(data.get("display_name") ?? ""),
          password: String(data.get("password") ?? ""),
          role: String(data.get("role") ?? "editor"),
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
              ? (detail[0]?.msg ?? "Could not create the account.")
              : "Could not create the account."
        );
        return;
      }
      setCreated(String(data.get("email") ?? ""));
      form.reset();
      onCreated();
    } catch {
      setError("Could not create the account. Check your connection and try again.");
    } finally {
      setStatus("idle");
    }
  }

  return (
    <section className="rounded-xl border border-card-border bg-surface p-5 shadow-sm">
      <h2 className="m-0 text-sm font-semibold uppercase tracking-wide text-muted">
        Create account
      </h2>
      <p className="mt-2 text-xs text-muted">
        The new account must change its temporary password after signing in.
        Passwords need at least 15 characters and must not be a known breached password.
      </p>

      <form className="mt-4 grid gap-4 sm:grid-cols-2" onSubmit={onSubmit} noValidate>
        <label className="text-xs font-semibold uppercase tracking-wide text-muted">
          Email
          <input
            name="email"
            type="email"
            required
            maxLength={254}
            autoComplete="off"
            className="mt-1 block w-full rounded-lg border border-card-border bg-surface px-3 py-2 text-sm font-normal normal-case tracking-normal text-foreground outline-none focus:border-blue focus:ring-2 focus:ring-blue/20"
          />
        </label>
        <label className="text-xs font-semibold uppercase tracking-wide text-muted">
          Display name
          <input
            name="display_name"
            type="text"
            maxLength={120}
            autoComplete="off"
            className="mt-1 block w-full rounded-lg border border-card-border bg-surface px-3 py-2 text-sm font-normal normal-case tracking-normal text-foreground outline-none focus:border-blue focus:ring-2 focus:ring-blue/20"
          />
        </label>
        <label className="text-xs font-semibold uppercase tracking-wide text-muted">
          Temporary password
          <input
            name="password"
            type="password"
            required
            minLength={15}
            maxLength={1024}
            autoComplete="new-password"
            className="mt-1 block w-full rounded-lg border border-card-border bg-surface px-3 py-2 text-sm font-normal normal-case tracking-normal text-foreground outline-none focus:border-blue focus:ring-2 focus:ring-blue/20"
          />
        </label>
        <label className="text-xs font-semibold uppercase tracking-wide text-muted">
          Role
          <select
            name="role"
            defaultValue="editor"
            className="mt-1 block w-full rounded-lg border border-card-border bg-surface px-3 py-2 text-sm font-normal normal-case tracking-normal text-foreground outline-none focus:border-blue focus:ring-2 focus:ring-blue/20"
          >
            {ROLE_OPTIONS.map((role) => (
              <option key={role} value={role}>
                {roleLabel(role)}
              </option>
            ))}
          </select>
        </label>

        {error && (
          <p role="alert" className="m-0 text-sm text-red sm:col-span-2">
            {error}
          </p>
        )}
        {created && (
          <p className="m-0 text-sm text-muted sm:col-span-2">
            Created {created}. Share the temporary password out of band.
          </p>
        )}

        <div className="sm:col-span-2">
          <button
            type="submit"
            disabled={status === "submitting"}
            className="rounded-full bg-blue px-4 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {status === "submitting" ? "Creating…" : "Create account"}
          </button>
        </div>
      </form>
    </section>
  );
}
