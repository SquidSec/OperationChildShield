import type { MemberSummary, MemberVote } from "./types";

const STATE_CODES: Record<string, string> = {
  Alabama: "AL", Alaska: "AK", Arizona: "AZ", Arkansas: "AR", California: "CA",
  Colorado: "CO", Connecticut: "CT", Delaware: "DE", Florida: "FL", Georgia: "GA",
  Hawaii: "HI", Idaho: "ID", Illinois: "IL", Indiana: "IN", Iowa: "IA",
  Kansas: "KS", Kentucky: "KY", Louisiana: "LA", Maine: "ME", Maryland: "MD",
  Massachusetts: "MA", Michigan: "MI", Minnesota: "MN", Mississippi: "MS",
  Missouri: "MO", Montana: "MT", Nebraska: "NE", Nevada: "NV",
  "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
  "North Carolina": "NC", "North Dakota": "ND", Ohio: "OH", Oklahoma: "OK",
  Oregon: "OR", Pennsylvania: "PA", "Rhode Island": "RI", "South Carolina": "SC",
  "South Dakota": "SD", Tennessee: "TN", Texas: "TX", Utah: "UT", Vermont: "VT",
  Virginia: "VA", Washington: "WA", "West Virginia": "WV", Wisconsin: "WI",
  Wyoming: "WY", "District of Columbia": "DC", "Puerto Rico": "PR",
};

export function formatMemberSubtitle(member: MemberSummary): string {
  const prefix = member.chamber === "Senate" ? "Sen." : "Rep.";
  const stateCode =
    member.stateCode ||
    STATE_CODES[member.state] ||
    member.state.slice(0, 2).toUpperCase();

  const location =
    member.chamber === "House" && member.district != null
      ? `${stateCode}-${member.district}`
      : stateCode;

  return `${prefix} ${location}`;
}

/** @deprecated Use formatMemberSubtitle - party shown separately on cards */
export function formatMemberTitle(member: MemberSummary): string {
  return `${formatMemberSubtitle(member)} • ${formatPartyLabel(member.party)}`;
}

export function formatPartyLabel(party: string): string {
  const p = party.trim();
  if (!p || p === "Unknown") return "Unknown";
  if (p.toLowerCase().includes("democrat")) return "Democrat";
  if (p.toLowerCase().includes("republican")) return "Republican";
  if (p.toLowerCase().includes("independent")) return "Independent";
  return p;
}

export function partyBadgeClass(
  party: string,
  variant: "header" | "light" = "light"
): string {
  const label = formatPartyLabel(party).toLowerCase();
  if (variant === "header") {
    if (label === "democrat") return "bg-white text-blue-800 border-white shadow-sm";
    if (label === "republican") return "bg-red-600 text-white border-red-700";
    if (label === "independent") return "bg-purple-100 text-purple-900 border-purple-200";
    return "bg-white/90 text-slate-700 border-white/80";
  }
  if (label === "democrat") return "bg-blue-100 text-blue-800 border-blue-300";
  if (label === "republican") return "bg-red-100 text-red-800 border-red-300";
  if (label === "independent") return "bg-purple-100 text-purple-800 border-purple-300";
  return "bg-slate-100 text-slate-700 border-slate-300";
}

export function formatDisplayName(invertedName: string): string {
  const parts = invertedName.split(",").map((p) => p.trim());
  if (parts.length >= 2) return `${parts[1]} ${parts[0]}`;
  return invertedName;
}

export function gradeCircleClass(grade: string): string {
  const letter = grade.charAt(0).toUpperCase();
  if (letter === "A") return "grade-circle-a";
  if (letter === "B") return "grade-circle-b";
  if (letter === "C") return "grade-circle-c";
  if (letter === "D") return "grade-circle-d";
  if (letter === "F") return "grade-circle-f";
  return "grade-circle-na";
}

export function resolvePolicyConsistent(
  policyConsistent: boolean | null | undefined,
  scoreImpact?: string | null
): boolean | null {
  if (policyConsistent === true || policyConsistent === false) {
    return policyConsistent;
  }
  const impact = scoreImpact?.toLowerCase() ?? "";
  if (impact.includes("consistent with ocs")) {
    return !impact.includes("not consistent");
  }
  return null;
}

export interface MemberVoteSummary {
  recorded: number;
  consistent: number;
  notConsistent: number;
  notVoting: number;
}

export function summarizeMemberVotes(votes: MemberVote[]): MemberVoteSummary {
  let recorded = 0;
  let consistent = 0;
  let notConsistent = 0;
  let notVoting = 0;

  for (const vote of votes) {
    const policy = resolvePolicyConsistent(
      vote.policy_consistent,
      vote.score_impact
    );
    if (policy !== null) {
      recorded += 1;
      if (policy) consistent += 1;
      else notConsistent += 1;
    }
    if (vote.vote_cast.toLowerCase() === "not voting") {
      notVoting += 1;
    }
  }

  return { recorded, consistent, notConsistent, notVoting };
}

export function voteToLabel(vote: string): { label: string; className: string } {
  const v = vote.toLowerCase();
  if (v === "aye" || v === "yea" || v === "yes") return { label: "Yes", className: "vote-yes" };
  if (v === "nay" || v === "no") return { label: "No", className: "vote-no" };
  if (v === "not voting") return { label: "Not Voting", className: "vote-no" };
  if (v === "present") return { label: "Present", className: "vote-no" };
  if (v === "unknown") return { label: "No vote held yet", className: "vote-neutral" };
  return { label: vote, className: "vote-neutral" };
}

/** Report card order: no/absent votes → yes votes → bills awaiting a floor vote. */
export function voteSortOrder(vote: string): number {
  const v = vote.toLowerCase();
  if (v === "unknown") return 2;
  if (v === "aye" || v === "yea" || v === "yes") return 1;
  return 0;
}

/**
 * Format an ISO-8601 UTC timestamp with an explicit UTC time zone label.
 *
 * Built by hand instead of via `toLocaleString`: the `timeZoneName` option
 * needs full ICU data, and its first call took ~6s on the CI runner, which
 * timed the unit test out at 5s. The values here are always UTC, so the
 * numeric fields can be read straight off the Date.
 */
export function formatUtcTimestamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;

  const hours = date.getUTCHours();
  const hour12 = hours % 12 === 0 ? 12 : hours % 12;
  const meridiem = hours < 12 ? "AM" : "PM";
  const pad = (n: number) => String(n).padStart(2, "0");

  return (
    `${date.getUTCMonth() + 1}/${date.getUTCDate()}/${date.getUTCFullYear()}, ` +
    `${hour12}:${pad(date.getUTCMinutes())}:${pad(date.getUTCSeconds())} ` +
    `${meridiem} UTC`
  );
}
