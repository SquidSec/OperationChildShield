import Link from "next/link";
import type { StateMetric } from "@/lib/metrics-types";
import { statesWithRecordedVotes } from "@/lib/state-metrics";

interface StatePerformanceTableProps {
  byState: StateMetric[];
}

export function StatePerformanceTable({ byState }: StatePerformanceTableProps) {
  const rows = statesWithRecordedVotes(byState);
  const noDataCount = byState.filter((s) => s.recordedVotes === 0).length;

  return (
    <section className="mt-8">
      <h2 className="m-0 text-xl font-bold text-blue">Every State at a Glance</h2>
      <p className="mt-2 text-sm text-muted max-w-3xl leading-relaxed">
        House votes on tracked bills, grouped by state and sorted by policy
        consistency.
        {noDataCount > 0
          ? ` ${noDataCount} state${noDataCount === 1 ? "" : "s"} have no recorded House votes yet.`
          : null}
      </p>

      {rows.length === 0 ? (
        <p className="mt-4 text-muted">No state-level recorded votes available yet.</p>
      ) : (
        <div className="mt-4 overflow-x-auto rounded-[10px] border border-card-border bg-surface shadow-sm">
          <table className="w-full min-w-[720px] border-collapse text-left">
            <caption className="sr-only">
              House roll-call totals by state, sorted by policy consistency rate.
            </caption>
            <thead>
              <tr className="border-b border-card-border bg-surface-muted text-xs font-bold uppercase tracking-wide text-muted">
                <th scope="col" className="py-3 pl-4 pr-3">State</th>
                <th scope="col" className="py-3 px-3 text-center">Consistency rate</th>
                <th scope="col" className="py-3 px-3 text-center">Consistent</th>
                <th scope="col" className="py-3 px-3 text-center">Not consistent</th>
                <th scope="col" className="py-3 px-3 text-center">Recorded votes</th>
                <th scope="col" className="py-3 px-3 text-center">House w/ votes</th>
                <th scope="col" className="py-3 pl-3 pr-4 text-center">Participation</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.stateCode}
                  className="border-b border-card-border last:border-b-0"
                >
                  <td className="py-3 pl-4 pr-3 align-middle">
                    <Link
                      href={`/states/${row.stateCode.toLowerCase()}`}
                      className="font-semibold text-red hover:underline"
                    >
                      {row.state}
                    </Link>
                    <span className="ml-2 text-xs text-muted">{row.stateCode}</span>
                  </td>
                  <td className="py-3 px-3 text-center text-sm font-semibold text-blue">
                    {row.policyConsistencyRate != null
                      ? `${row.policyConsistencyRate.toFixed(1)}%`
                      : "-"}
                  </td>
                  <td className="py-3 px-3 text-center text-sm">
                    {row.policyConsistentVotes}
                  </td>
                  <td className="py-3 px-3 text-center text-sm">
                    {row.policyNotConsistentVotes}
                  </td>
                  <td className="py-3 px-3 text-center text-sm">{row.recordedVotes}</td>
                  <td className="py-3 px-3 text-center text-sm">
                    {row.houseMembersWithRecordedVotes}
                  </td>
                  <td className="py-3 pl-3 pr-4 text-center text-sm">
                    {row.participationRate != null
                      ? `${row.participationRate.toFixed(1)}%`
                      : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

    </section>
  );
}
