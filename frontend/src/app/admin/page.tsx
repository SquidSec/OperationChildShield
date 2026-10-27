import type { Metadata } from "next";
import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import Link from "next/link";
import { AdminNav } from "@/components/admin/AdminNav";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";
import { HealthPanel } from "@/components/admin/HealthPanel";
import { ApplicationsTable } from "@/components/admin/ApplicationsTable";
import { TrafficChart } from "@/components/admin/TrafficChart";
import {
  ADMIN_RANGES,
  botReasonLabel,
  botShare,
  busiestDay,
  dailyAverage,
  parseRangeDays,
  percentChange,
  totalActions,
} from "@/lib/admin-format";
import {
  ADMIN_SESSION_COOKIE,
  getAdminApplications,
  getAdminHealth,
  getAdminMe,
  getAdminTraffic,
} from "@/lib/admin-api";
import type { SiteTraffic } from "@/lib/admin-types";
import { formatUtcTimestamp } from "@/lib/format";

export const metadata: Metadata = {
  title: "Traffic",
  robots: { index: false, follow: false, nocache: true },
};

export const dynamic = "force-dynamic";

function StatCard({
  label,
  value,
  sublabel,
}: {
  label: string;
  value: string | number;
  sublabel?: string;
}) {
  return (
    <div className="rounded-xl border border-card-border bg-surface p-5 shadow-sm">
      <p className="m-0 text-xs font-semibold uppercase tracking-wide text-muted">{label}</p>
      <p className="m-0 mt-2 text-3xl font-bold text-blue">{value}</p>
      {sublabel && <p className="m-0 mt-1 text-xs text-muted">{sublabel}</p>}
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

function EmptyRow({ children }: { children: string }) {
  return <p className="m-0 text-sm text-muted">{children}</p>;
}

export default async function AdminDashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ days?: string }>;
}) {
  const params = await searchParams;
  const days = parseRangeDays(params.days);

  const cookieStore = await cookies();
  const token = cookieStore.get(ADMIN_SESSION_COOKIE)?.value;
  if (!token) redirect("/admin/login");

  const cookieHeader = (await headers()).get("cookie") ?? "";
  const [user, traffic, health, applicationsResponse] = await Promise.all([
    getAdminMe(cookieHeader),
    getAdminTraffic(cookieHeader, days).catch(() => "error" as const),
    getAdminHealth(cookieHeader),
    // Applications are surfaced on the dashboard as well as their own tab.
    getAdminApplications(cookieHeader, 5),
  ]);
  const applicationsResult = applicationsResponse;

  if (!user || traffic === null) redirect("/admin/login");
  if (traffic === "error") {
    return (
      <div className="page-container py-10">
        <p className="text-sm text-red">
          Could not load traffic data right now. Try again shortly.
        </p>
      </div>
    );
  }

  const data: SiteTraffic = traffic;
  const busiest = busiestDay(data.daily);
  const actionCount = totalActions(data);
  const applications =
    applicationsResult.status === "ok" ? applicationsResult.data.applications : [];
  const applicationCount =
    applicationsResult.status === "ok" ? applicationsResult.data.total : 0;

  return (
    <div className="container mx-auto w-full max-w-6xl px-4 py-8">
      <AdminPageHeader
        title="Site traffic"
        displayName={user.displayName}
        email={user.email}
        role={user.role}
      />

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <AdminNav current="/admin" />
        {/* Direct link so the browser sends the session cookie and downloads the file. */}
        <a
          href={`/api/admin/traffic/export?days=${days}`}
          download
          className="rounded-full border border-card-border bg-surface px-4 py-2 text-sm font-semibold text-muted no-underline hover:text-blue"
        >
          Export CSV
        </a>
      </div>

      <nav aria-label="Date range" className="mt-4 flex flex-wrap gap-2">
        {ADMIN_RANGES.map((range) => {
          const active = range.days === days;
          return (
            <Link
              key={range.days}
              href={`/admin?days=${range.days}`}
              aria-current={active ? "page" : undefined}
              className={
                active
                  ? "rounded-full bg-blue px-4 py-2 text-sm font-semibold text-white no-underline"
                  : "rounded-full border border-card-border bg-surface px-4 py-2 text-sm font-semibold text-muted no-underline hover:text-blue"
              }
            >
              {range.label}
            </Link>
          );
        })}
      </nav>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Page views"
          value={data.pageViews.toLocaleString("en-US")}
          sublabel={percentChange(data.pageViews, data.previousPageViews)}
        />
        <StatCard
          label="Daily average"
          value={dailyAverage(data).toLocaleString("en-US")}
        />
        <StatCard
          label="Busiest day"
          value={busiest ? busiest.views.toLocaleString("en-US") : "0"}
          sublabel={busiest ? new Date(`${busiest.date}T00:00:00Z`).toLocaleDateString("en-US", {
            timeZone: "UTC",
            month: "short",
            day: "numeric",
            year: "numeric",
          }) : undefined}
        />
        <StatCard
          label="Bots filtered"
          value={(data.botPageViews ?? 0).toLocaleString("en-US")}
          sublabel={`${botShare(data.botPageViews ?? 0, data.pageViews)}% of all requests`}
        />
        <StatCard
          label="Actions"
          value={actionCount.toLocaleString("en-US")}
          sublabel={`${data.actions.share} shares · ${data.actions.contactCongress} contacts · ${data.actions.signups} signups`}
        />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Panel title={`Views per day (${data.days}d)`}>
            <TrafficChart points={data.daily} />
          </Panel>
        </div>
        <Panel title="Top pages">
          {data.topPages.length === 0 ? (
            <EmptyRow>No page views recorded in this range.</EmptyRow>
          ) : (
            <ol className="m-0 list-none space-y-2 p-0">
              {data.topPages.map((page) => (
                <li key={page.path} className="flex items-baseline justify-between gap-3 text-sm">
                  <span className="truncate font-mono text-xs text-foreground" title={page.path}>
                    {page.path}
                  </span>
                  <span className="shrink-0 font-semibold text-muted">
                    {page.views.toLocaleString("en-US")}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </Panel>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Panel title="Top referrers">
          {data.topReferrers.length === 0 ? (
            <EmptyRow>No external referrers recorded in this range.</EmptyRow>
          ) : (
            <ol className="m-0 list-none space-y-2 p-0">
              {data.topReferrers.map((referrer) => (
                <li key={referrer.domain} className="flex items-baseline justify-between gap-3 text-sm">
                  <span className="truncate text-foreground">{referrer.domain}</span>
                  <span className="shrink-0 font-semibold text-muted">
                    {referrer.views.toLocaleString("en-US")}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </Panel>
        <Panel title="Engagement">
          <dl className="m-0 grid grid-cols-3 gap-3 text-center">
            {[
              { label: "Shares", value: data.actions.share },
              { label: "Congress contacts", value: data.actions.contactCongress },
              { label: "Signups", value: data.actions.signups },
            ].map((item) => (
              <div key={item.label}>
                <dd className="m-0 text-2xl font-bold text-blue">
                  {item.value.toLocaleString("en-US")}
                </dd>
                <dt className="mt-1 text-[11px] font-semibold uppercase tracking-wide text-muted">
                  {item.label}
                </dt>
              </div>
            ))}
          </dl>
          <p className="mt-4 text-xs text-muted">
            Aggregates only. Raw paths and user agents are never shown and are
            deleted after the retention window.
          </p>
        </Panel>
      </div>

      <div className="mt-6">
        <Panel title="Filtered traffic by reason">
          {(data.botReasons ?? []).length === 0 ? (
            <EmptyRow>
              No automated traffic recorded in this range. Requests are classified
              on arrival and tagged with a reason.
            </EmptyRow>
          ) : (
            <ul className="m-0 list-none space-y-2 p-0">
              {(data.botReasons ?? []).map((entry) => (
                <li
                  key={entry.reason}
                  className="flex items-baseline justify-between gap-3 text-sm"
                >
                  <span className="text-foreground">{botReasonLabel(entry.reason)}</span>
                  <span className="shrink-0 font-semibold text-muted">
                    {entry.count.toLocaleString("en-US")}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-4 text-xs text-muted">
            Automated hits are stored with a reason code but excluded from every
            visitor metric, so the numbers above count people only.
          </p>
        </Panel>
      </div>

      <div className="mt-6">
        <Panel title={`Board applications (${applicationCount})`}>
          {applications.length === 0 ? (
            <EmptyRow>
              No applications yet. Submissions from the public board page appear
              here and under Applications.
            </EmptyRow>
          ) : (
            <>
              <ApplicationsTable applications={applications} />
              <Link
                href="/admin/applications"
                className="mt-4 inline-block text-sm font-semibold text-red hover:underline"
              >
                View all applications →
              </Link>
            </>
          )}
        </Panel>
      </div>

      <div className="mt-6">
        <HealthPanel result={health} />
      </div>

      <p className="mt-8 text-xs text-muted">
        Generated {formatUtcTimestamp(data.generatedAt)} · window starts{" "}
        {formatUtcTimestamp(data.since)} · admin page views excluded
      </p>
    </div>
  );
}
