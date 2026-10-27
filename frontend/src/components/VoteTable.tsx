import { PolicyBadge } from "@/components/PolicyBadge";
import type { MemberVote } from "@/lib/types";
import { resolvePolicyConsistent, voteSortOrder, voteToLabel } from "@/lib/format";

interface VoteTableProps {
  votes: MemberVote[];
}

export function VoteTable({ votes }: VoteTableProps) {
  if (votes.length === 0) {
    return (
      <p className="text-muted text-sm py-6 text-center">
        No tracked votes on record for this member.
      </p>
    );
  }

  const sortedVotes = [...votes].sort((a, b) => {
    const orderDiff = voteSortOrder(a.vote_cast) - voteSortOrder(b.vote_cast);
    if (orderDiff !== 0) return orderDiff;
    const dateA = a.vote_date ? new Date(a.vote_date).getTime() : 0;
    const dateB = b.vote_date ? new Date(b.vote_date).getTime() : 0;
    return dateB - dateA;
  });

  return (
    <div className="space-y-2">
      {sortedVotes.map((vote) => {
        const voteDisplay = voteToLabel(vote.vote_cast);
        const policyConsistent = resolvePolicyConsistent(
          vote.policy_consistent,
          vote.score_impact
        );
        return (
          <div
            key={vote.bill_id}
            className="vote-row py-3 px-4 bg-surface-muted rounded-md border-l-4 border-red"
          >
            <div className="flex justify-between items-center gap-3">
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-foreground text-sm m-0">
                  {vote.bill_number}: {vote.bill_title}
                </p>
                {policyConsistent === null && vote.score_impact && (
                  <p className="text-xs text-muted mt-1 m-0">{vote.score_impact}</p>
                )}
                {vote.vote_date && (
                  <p className="text-xs text-muted mt-0.5 m-0">
                    {new Date(vote.vote_date).toLocaleDateString()}
                  </p>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span
                  className={`font-bold px-2.5 py-0.5 rounded-full text-[0.8rem] whitespace-nowrap ${voteDisplay.className}`}
                >
                  {voteDisplay.label}
                </span>
                <PolicyBadge consistent={policyConsistent} />
              </div>
            </div>
            <div className="mt-2 flex gap-3 text-xs">
              <a
                href={vote.congress_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-red font-semibold hover:underline"
              >
                View Bill →
              </a>
              {vote.roll_call_url && (
                <a
                  href={vote.roll_call_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue font-semibold hover:underline"
                >
                  Roll Call →
                </a>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
