import { formatBytes, formatUptime } from "@/lib/admin-format";
import type { AdminFetchResult, AdminHealth } from "@/lib/admin-types";
import { formatUtcTimestamp } from "@/lib/format";

/** Operational snapshot: database sizes, row counts, scheduler, uptime. */
export function HealthPanel({ result }: { result: AdminFetchResult<AdminHealth> }) {
  return (
    <section className="rounded-xl border border-card-border bg-surface p-5 shadow-sm">
      <h2 className="m-0 text-sm font-semibold uppercase tracking-wide text-muted">
        System health
      </h2>
      {result.status !== "ok" ? (
        <p className="m-0 mt-4 text-sm text-muted">
          Health details are unavailable right now.
        </p>
      ) : (
        <HealthGrid health={result.data} />
      )}
    </section>
  );
}

function HealthGrid({ health }: { health: AdminHealth }) {
  const items: { label: string; value: string; hint?: string }[] = [
    { label: "Analytics DB", value: formatBytes(health.analyticsDbBytes) },
    { label: "Admin DB", value: formatBytes(health.adminDbBytes) },
    {
      label: "Page view rows",
      value: health.pageViewRows.toLocaleString("en-US"),
      hint: health.oldestPageView
        ? `oldest ${formatUtcTimestamp(health.oldestPageView)}`
        : "none recorded",
    },
    {
      label: "Cache files",
      value: health.cacheFileCount.toLocaleString("en-US"),
    },
    {
      label: "Congress.gov",
      value: health.congressApiConfigured ? "Configured" : "No API key",
    },
    {
      label: "Scheduler",
      value: health.schedulerEnabled ? "Enabled" : "Disabled",
      hint: health.schedulerLastRun
        ? `last run ${formatUtcTimestamp(health.schedulerLastRun.at)}`
        : "not run yet",
    },
    { label: "Uptime", value: formatUptime(health.uptimeSeconds) },
  ];

  return (
    <dl className="m-0 mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {items.map((item) => (
        <div key={item.label}>
          <dt className="m-0 text-[11px] font-semibold uppercase tracking-wide text-muted">
            {item.label}
          </dt>
          <dd className="m-0 mt-1 text-sm font-semibold text-foreground">{item.value}</dd>
          {item.hint && <p className="m-0 mt-0.5 text-[11px] text-muted">{item.hint}</p>}
        </div>
      ))}
    </dl>
  );
}
