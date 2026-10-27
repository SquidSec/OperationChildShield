"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { BoardApplication } from "@/lib/admin-types";

function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString("en-US", {
    timeZone: "UTC",
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

function Field({ label, value }: { label: string; value: string }) {
  if (!value) return null;
  return (
    <p className="m-0 text-sm text-muted">
      <span className="font-semibold text-foreground">{label}: </span>
      {/* React escapes text nodes, so applicant input is never parsed as HTML. */}
      {value}
    </p>
  );
}

/**
 * Renders applications as plain text. The backend sanitizes on write and again
 * on read; this layer adds no dangerouslySetInnerHTML and no href built from
 * applicant input, so there is no script or attribute-injection path.
 */
export function ApplicationsTable({
  applications,
  canDelete = false,
}: {
  applications: BoardApplication[];
  canDelete?: boolean;
}) {
  const router = useRouter();
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);

  async function remove(id: string) {
    setPending(id);
    setError(null);
    try {
      const res = await fetch(`/api/admin/applications/${id}`, {
        method: "DELETE",
        credentials: "same-origin",
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as { detail?: string } | null;
        setError(body?.detail ?? "Could not delete that application.");
        return;
      }
      setConfirming(null);
      router.refresh();
    } catch {
      setError("Could not delete that application. Check your connection.");
    } finally {
      setPending(null);
    }
  }

  if (applications.length === 0) {
    return (
      <p className="m-0 text-sm text-muted">
        No applications yet. Submissions from the public board page appear here.
      </p>
    );
  }

  return (
    <div>
      {error && (
        <p role="alert" className="m-0 mb-3 rounded-lg border border-red/40 bg-red/5 p-3 text-sm text-red">
          {error}
        </p>
      )}
    <ul className="m-0 list-none space-y-4 p-0">
      {applications.map((app, index) => (
        <li
          key={`${app.submittedAt}-${app.email}-${index}`}
          className="rounded-xl border border-card-border bg-surface-muted p-4"
        >
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className="m-0 font-semibold text-foreground">{app.name}</p>
            <div className="flex items-center gap-3">
              <p className="m-0 text-xs text-muted">{formatDate(app.submittedAt)}</p>
              {canDelete && app.id && (
                confirming === app.id ? (
                  <span className="flex items-center gap-2">
                    <button
                      type="button"
                      disabled={pending !== null}
                      onClick={() => remove(app.id!)}
                      className="rounded-full bg-red px-3 py-1 text-xs font-semibold text-white disabled:opacity-50"
                    >
                      {pending === app.id ? "Deleting…" : "Confirm delete"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirming(null)}
                      className="text-xs text-muted hover:text-blue"
                    >
                      Cancel
                    </button>
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={() => setConfirming(app.id!)}
                    className="rounded-full border border-red/40 px-3 py-1 text-xs font-semibold text-red hover:bg-red/5"
                  >
                    Delete
                  </button>
                )
              )}
            </div>
          </div>
          <p className="m-0 mt-1 text-xs font-semibold uppercase tracking-wide text-red">
            {app.roleLabel}
          </p>

          <div className="mt-3 space-y-1">
            <Field label="Email" value={app.email} />
            <Field label="Phone" value={app.phone} />
            <Field label="Location" value={app.location} />
            <Field label="LinkedIn" value={app.linkedin} />
          </div>

          <div className="mt-3 rounded-lg border border-card-border bg-surface p-3">
            <p className="m-0 text-[11px] font-semibold uppercase tracking-wide text-muted">
              Statement
            </p>
            <p className="m-0 mt-1 whitespace-pre-wrap text-sm leading-relaxed text-foreground">
              {app.statement}
            </p>
          </div>
        </li>
      ))}
    </ul>
    </div>
  );
}
