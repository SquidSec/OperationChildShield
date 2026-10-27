import { describe, expect, it } from "vitest";
import {
  buildCompareRows,
  parseCompareIds,
  toCompareMember,
  type CompareMember,
} from "./compare";
import type { MemberVote, ReportCard } from "./types";

function vote(billId: string, number: string, cast = "Aye"): MemberVote {
  return {
    bill_id: billId,
    bill_title: `Bill ${number}`,
    bill_number: number,
    category: "Online Safety",
    vote_cast: cast,
    vote_date: null,
    vote_question: null,
    vote_result: null,
    congress_url: "https://example.com",
    roll_call_url: null,
    score_impact: "",
    policy_consistent: cast === "Aye",
  };
}

function card(id: string, votes: MemberVote[]): ReportCard {
  return {
    bioguide_id: id,
    name: "Doe, Jane",
    chamber: "House",
    state: "Ohio",
    party: "Democrat",
    district: "1",
    image_url: null,
    votes_tracked: votes.length,
    key_votes: votes,
    congress_profile_url: `https://www.congress.gov/member/${id}`,
    contact: null,
  };
}

describe("parseCompareIds", () => {
  it("accepts two to four valid ids", () => {
    expect(parseCompareIds("A000055,B000001")).toEqual(["A000055", "B000001"]);
  });

  it("normalizes case, trims, and de-duplicates", () => {
    expect(parseCompareIds(" a000055 , A000055,b000001 ")).toEqual([
      "A000055",
      "B000001",
    ]);
  });

  it("truncates at four ids", () => {
    expect(parseCompareIds("A000001,A000002,A000003,A000004,A000005")).toHaveLength(4);
  });

  it("drops malformed ids so the page can show its picker", () => {
    expect(parseCompareIds("nope,<script>,B000001")).toEqual(["B000001"]);
    expect(parseCompareIds(undefined)).toEqual([]);
  });

  it("accepts repeated query params", () => {
    expect(parseCompareIds(["A000055", "B000001"])).toEqual(["A000055", "B000001"]);
  });
});

describe("buildCompareRows", () => {
  const alice: CompareMember = toCompareMember(
    "A000055",
    card("A000055", [vote("b1", "HR 6484"), vote("b2", "HR 134", "Nay")])
  );
  const bob: CompareMember = toCompareMember("B000001", card("B000001", [vote("b1", "HR 6484")]));

  it("keeps a column per member and a row per bill", () => {
    const rows = buildCompareRows([alice, bob]);
    expect(rows.map((row) => row.billId)).toEqual(["b2", "b1"]);
    expect(rows[1].votes[0]?.vote_cast).toBe("Aye");
    expect(rows[1].votes[1]?.vote_cast).toBe("Aye");
  });

  it("uses null for members with no record on a bill", () => {
    const rows = buildCompareRows([alice, bob]);
    expect(rows[0].votes[0]?.bill_number).toBe("HR 134");
    expect(rows[0].votes[1]).toBeNull();
  });

  it("returns no rows when nobody has votes", () => {
    const empty = toCompareMember("C000001", card("C000001", []));
    expect(buildCompareRows([empty])).toEqual([]);
  });
});
