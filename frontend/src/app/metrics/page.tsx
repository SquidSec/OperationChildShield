import type { Metadata } from "next";
import Link from "next/link";
import { MetricsCharts } from "@/components/metrics/MetricsCharts";
import { StatePerformanceTable } from "@/components/metrics/StatePerformanceTable";
import { getMetrics, getMetricsExportUrl } from "@/lib/api";
import { formatUtcTimestamp } from "@/lib/format";
import type { BillMetricsRow } from "@/lib/metrics-types";

export const metadata: Metadata = {
  title: "See How Congress Voted",
  description:
    "Roll-call totals and state metrics for tracked child safety legislation.",
};

export const dynamic = "force-dynamic";

function KpiCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-[10px] border border-card-border bg-surface p-5 shadow-sm text-center">
      <p className="m-0 text-3xl font-bold text-blue">{value}</p>
      <p className="m-0 mt-2 text-xs font-semibold uppercase tracking-wide text-muted">
        {label}
      </p>
    </div>
  );
}

function BillRow({ bill }: { bill: BillMetricsRow }) {
  const hasRollCall = bill.eligibleMembers > 0;

  return (
    <tr className="border-b border-card-border last:border-b-0">
      <td className="py-4 pr-4 align-top">
        <a
          href={bill.congressUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="font-semibold text-red hover:underline"
        >
          {bill.billNumber}
        </a>
        <p className="m-0 mt-1 text-sm text-muted leading-snug">{bill.billTitle}</p>
      </td>
      <td className="py-4 px-3 align-top text-center text-sm">
        {hasRollCall ? bill.eligibleMembers : "-"}
      </td>
      <td className="py-4 px-3 align-top text-center text-sm">
        {hasRollCall ? bill.voteCounts.yes : "-"}
      </td>
      <td className="py-4 px-3 align-top text-center text-sm">
        {hasRollCall ? bill.voteCounts.no : "-"}
      </td>
      <td className="py-4 px-3 align-top text-center text-sm">
        {hasRollCall ? bill.voteCounts.notVoting : "-"}
      </td>
      <td className="py-4 px-3 align-top text-center text-sm">
        {hasRollCall ? bill.policyConsistentVotes : "-"}
      </td>
      <td className="py-4 pl-3 align-top text-center text-sm">
        {hasRollCall ? bill.policyNotConsistentVotes : "-"}
      </td>
    </tr>
  );
}

export default async function MetricsPage() {
  let error: string | null = null;
  let data: Awaited<ReturnType<typeof getMetrics>> | null = null;

  try {
    data = await getMetrics();
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load legislation overview";
  }

  return (
    <div className="page-container min-w-0 py-8">
      <Link href="/" className="text-sm text-muted hover:text-blue">
        ← Back to lawmakers
      </Link>

      <h1 className="text-3xl font-bold text-blue mt-4">See the Numbers</h1>
      <p className="mt-4 text-muted leading-relaxed max-w-3xl">
        Roll-call totals and state-level metrics on tracked child safety bills.
        Use the state table below to open members by state.
      </p>

      {error ? (
        <p className="mt-6 text-red">{error}</p>
      ) : data ? (
        <>
          <p className="mt-3 text-xs text-muted">
            {data.dataSource} · Congress {data.congress} · Updated{" "}
            {formatUtcTimestamp(data.lastUpdated)}
          </p>

          <div className="mt-10 grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
            <KpiCard label="Members Tracked" value={data.kpis.totalMembersTracked} />
            <KpiCard
              label="House w/ Recorded Votes"
              value={data.kpis.houseMembersWithRecordedVotes}
            />
            <KpiCard label="Bills Tracked" value={data.kpis.totalBillsTracked} />
            <KpiCard label="Bills w/ Roll Calls" value={data.kpis.billsWithRollCalls} />
            <KpiCard
              label="Recorded Floor Votes"
              value={data.kpis.totalRecordedFloorVotes}
            />
            <KpiCard
              label="Not Voting Instances"
              value={data.kpis.totalNotVotingInstances}
            />
          </div>

          <section className="mt-10 grid gap-4 md:grid-cols-2">
            {(data.chamberSummary ?? []).map((chamber) => (
              <div
                key={chamber.chamber}
                className="rounded-[10px] border border-card-border bg-surface p-5 shadow-sm"
              >
                <h2 className="m-0 text-lg font-bold text-blue">{chamber.chamber}</h2>
                <ul className="mt-3 space-y-2 text-sm text-muted">
                  <li>
                    <strong className="text-foreground">{chamber.memberCount}</strong>{" "}
                    members in directory
                  </li>
                  <li>
                    <strong className="text-foreground">
                      {chamber.membersWithRecordedVotes}
                    </strong>{" "}
                    with at least one recorded floor vote on tracked bills
                  </li>
                  <li>
                    <strong className="text-foreground">
                      {chamber.totalRecordedVotes}
                    </strong>{" "}
                    total recorded floor votes
                  </li>
                  <li>
                    <strong className="text-foreground">
                      {chamber.totalNotVotingInstances}
                    </strong>{" "}
                    not-voting instances on tracked roll calls
                  </li>
                </ul>
              </div>
            ))}
          </section>

          <MetricsCharts bills={data.bills ?? []} />

          <section className="mt-10">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <h2 className="m-0 text-xl font-bold text-blue">Every Bill, Vote by Vote</h2>
              <a
                href={getMetricsExportUrl()}
                className="text-sm font-semibold text-red hover:underline"
              >
                Download the Data →
              </a>
            </div>
            <p className="mt-2 text-sm text-muted">
              Per-bill vote totals across the House. Policy columns count how many
              recorded votes aligned with Operation Child Shield board-adopted
              positions.
            </p>

            <div className="mt-4 overflow-x-auto rounded-[10px] border border-card-border bg-surface shadow-sm">
              <table className="w-full min-w-[760px] border-collapse text-left">
                <thead>
                  <tr className="border-b border-card-border bg-surface-muted text-xs font-bold uppercase tracking-wide text-muted">
                    <th className="py-3 pl-4 pr-4">Bill</th>
                    <th className="py-3 px-3 text-center">Eligible</th>
                    <th className="py-3 px-3 text-center">Yes</th>
                    <th className="py-3 px-3 text-center">No</th>
                    <th className="py-3 px-3 text-center">Not Voting</th>
                    <th className="py-3 px-3 text-center">Policy Consistent</th>
                    <th className="py-3 pl-3 pr-4 text-center">Policy Not Consistent</th>
                  </tr>
                </thead>
                <tbody>
                  {(data.bills ?? []).map((bill) => (
                    <BillRow key={bill.billId} bill={bill} />
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <StatePerformanceTable byState={data.byState ?? []} />

        </>
      ) : null}
    </div>
  );
}