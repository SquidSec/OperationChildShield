import Link from "next/link";
import type { CompareMember, CompareRow } from "@/lib/compare";
import { formatDisplayName, resolvePolicyConsistent, voteToLabel } from "@/lib/format";
import { PartyBadge } from "@/components/PartyBadge";

interface CompareTableProps {
  members: CompareMember[];
  rows: CompareRow[];
}

function VoteCell({
  vote,
}: {
  vote: CompareRow["votes"][number];
}) {
  if (!vote) {
    return <span className="text-xs text-muted">No record</span>;
  }

  const label = voteToLabel(vote.vote_cast);
  const consistent = resolvePolicyConsistent(vote.policy_consistent, vote.score_impact);

  return (
    <span className="inline-flex flex-wrap items-center justify-center gap-1.5">
      <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${label.className}`}>
        {label.label}
      </span>
      <span className="text-[10px] font-semibold uppercase tracking-wide text-muted">
        {consistent === null ? "" : consistent ? "Consistent" : "Not consistent"}
      </span>
    </span>
  );
}

export function CompareTable({ members, rows }: CompareTableProps) {
  return (
    <div className="overflow-x-auto rounded-[10px] border border-card-border bg-surface shadow-sm">
      <table className="w-full min-w-[720px] border-collapse text-left">
        <caption className="sr-only">
          Roll-call votes on tracked child safety bills for{" "}
          {members.map((m) => formatDisplayName(m.name)).join(", ")}.
        </caption>
        <thead>
          <tr className="border-b border-card-border bg-surface-muted">
            <th scope="col" className="py-3 pl-4 pr-3 text-xs font-bold uppercase tracking-wide text-muted">
              Bill
            </th>
            {members.map((member) => (
              <th
                key={member.id}
                scope="col"
                className="px-3 py-3 text-center align-bottom"
              >
                <Link
                  href={`/member/${member.id}`}
                  className="block text-sm font-bold text-blue hover:underline"
                >
                  {formatDisplayName(member.name)}
                </Link>
                <span className="mt-1 block text-[11px] font-medium text-muted">
                  {member.chamber === "Senate" ? "Sen." : "Rep."} {member.state}
                </span>
                <span className="mt-1 flex justify-center">
                  <PartyBadge party={member.party} variant="light" size="sm" />
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.billId} className="border-b border-card-border last:border-b-0">
              <th scope="row" className="py-3 pl-4 pr-3 align-top text-left font-normal">
                <span className="block text-xs font-bold uppercase tracking-wide text-red">
                  {row.billNumber}
                </span>
                <span className="mt-0.5 block text-sm leading-snug text-foreground">
                  {row.billTitle}
                </span>
              </th>
              {row.votes.map((vote, index) => (
                <td
                  key={`${row.billId}-${members[index].id}`}
                  className="px-3 py-3 text-center align-middle"
                >
                  <VoteCell vote={vote} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
