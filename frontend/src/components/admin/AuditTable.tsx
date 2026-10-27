import { auditActionLabel } from "@/lib/admin-format";
import type { AuditEntry } from "@/lib/admin-types";
import { formatUtcTimestamp } from "@/lib/format";

export function AuditTable({ entries }: { entries: AuditEntry[] }) {
  if (entries.length === 0) {
    return <p className="m-0 text-sm text-muted">No audit events recorded yet.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-card-border">
            {["When", "Actor", "Action", "Detail", "IP"].map((heading) => (
              <th
                key={heading}
                scope="col"
                className="pb-2 pr-4 text-[11px] font-semibold uppercase tracking-wide text-muted"
              >
                {heading}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr key={entry.id} className="border-b border-card-border/60 last:border-0">
              <td className="whitespace-nowrap py-2 pr-4 text-xs text-muted">
                {formatUtcTimestamp(entry.createdAt)}
              </td>
              <td className="py-2 pr-4 text-foreground">{entry.actor}</td>
              <td className="whitespace-nowrap py-2 pr-4 font-semibold text-blue">
                {auditActionLabel(entry.action)}
              </td>
              <td className="py-2 pr-4 text-muted">{entry.detail || "—"}</td>
              <td className="whitespace-nowrap py-2 pr-4 font-mono text-xs text-muted">
                {entry.ip || "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
