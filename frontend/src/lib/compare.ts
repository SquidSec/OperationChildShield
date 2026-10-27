import type { MemberVote, ReportCard } from "./types";

/** Compare URL accepts 2–4 bioguide ids. */
export const MIN_COMPARE_IDS = 2;
export const MAX_COMPARE_IDS = 4;

/** Normalize the `ids` query value into an ordered, de-duplicated id list. */
export function parseCompareIds(raw: string | string[] | undefined): string[] {
  const joined = Array.isArray(raw) ? raw.join(",") : (raw ?? "");
  const seen = new Set<string>();
  const ids: string[] = [];

  for (const part of joined.split(",")) {
    const id = part.trim().toUpperCase();
    if (!/^[A-Z][0-9]{5,7}$/.test(id) || seen.has(id)) continue;
    seen.add(id);
    ids.push(id);
    if (ids.length === MAX_COMPARE_IDS) break;
  }

  return ids;
}

export interface CompareMember {
  id: string;
  name: string;
  party: string;
  state: string;
  chamber: string;
  votes: Map<string, MemberVote>;
}

export interface CompareRow {
  billId: string;
  billNumber: string;
  billTitle: string;
  votes: (MemberVote | null)[];
}

export function toCompareMember(id: string, card: ReportCard): CompareMember {
  return {
    id,
    name: card.name,
    party: card.party,
    state: card.state,
    chamber: card.chamber,
    votes: new Map(card.key_votes.map((vote) => [vote.bill_id, vote])),
  };
}

/**
 * One row per bill any compared member has a record for, so gaps in a member's
 * record stay visible instead of silently dropping the bill.
 */
export function buildCompareRows(members: CompareMember[]): CompareRow[] {
  const bills = new Map<string, { number: string; title: string }>();

  members.forEach((member) => {
    member.votes.forEach((vote, billId) => {
      if (!bills.has(billId)) {
        bills.set(billId, {
          number: vote.bill_number,
          title: vote.bill_title,
        });
      }
    });
  });

  return [...bills.entries()]
    .sort(([, a], [, b]) => a.number.localeCompare(b.number))
    .map(([billId, bill]) => ({
      billId,
      billNumber: bill.number,
      billTitle: bill.title,
      votes: members.map((member) => member.votes.get(billId) ?? null),
    }));
}
