import { describe, expect, it } from "vitest";
import type { StateMetric } from "./metrics-types";
import {
  formatConsistencyRate,
  heatColorForRate,
  heatTextClass,
  indexStateMetrics,
  statesWithRecordedVotes,
} from "./state-metrics";

const sample: StateMetric[] = [
  {
    state: "Texas",
    stateCode: "TX",
    membersTracked: 40,
    houseMembersTracked: 38,
    houseMembersWithRecordedVotes: 30,
    recordedVotes: 10,
    policyConsistentVotes: 8,
    policyNotConsistentVotes: 2,
    policyConsistencyRate: 80,
    votesParticipated: 10,
    notVotingCount: 0,
    participationRate: 100,
  },
  {
    state: "Maine",
    stateCode: "ME",
    membersTracked: 4,
    houseMembersTracked: 2,
    houseMembersWithRecordedVotes: 0,
    recordedVotes: 0,
    policyConsistentVotes: 0,
    policyNotConsistentVotes: 0,
    policyConsistencyRate: null,
    votesParticipated: 0,
    notVotingCount: 0,
    participationRate: null,
  },
  {
    state: "Ohio",
    stateCode: "OH",
    membersTracked: 18,
    houseMembersTracked: 15,
    houseMembersWithRecordedVotes: 12,
    recordedVotes: 20,
    policyConsistentVotes: 5,
    policyNotConsistentVotes: 15,
    policyConsistencyRate: 25,
    votesParticipated: 18,
    notVotingCount: 2,
    participationRate: 90,
  },
];

describe("heatColorForRate", () => {
  it("returns empty color for missing rate", () => {
    expect(heatColorForRate(null)).toContain("#94a3b8");
  });

  it("uses darker blue for high consistency", () => {
    expect(heatColorForRate(90)).toBe("#1e3a5f");
  });
});

describe("formatConsistencyRate", () => {
  it("formats rate and missing data", () => {
    expect(formatConsistencyRate(72.5)).toBe("72.5% policy-consistent");
    expect(formatConsistencyRate(null)).toBe("No recorded votes");
  });
});

describe("indexStateMetrics", () => {
  it("indexes by uppercase code", () => {
    const map = indexStateMetrics(sample);
    expect(map.get("TX")?.state).toBe("Texas");
  });
});

describe("statesWithRecordedVotes", () => {
  it("excludes empty states and sorts by rate", () => {
    const ranked = statesWithRecordedVotes(sample);
    expect(ranked.map((r) => r.stateCode)).toEqual(["TX", "OH"]);
  });
});

describe("heatColorForRate", () => {
  it("returns the empty color for null, undefined, and NaN", () => {
    for (const value of [null, undefined, Number.NaN]) {
      expect(heatColorForRate(value)).toContain("heat-empty");
    }
  });

  it("maps each band to a distinct color", () => {
    const bands = [95, 70, 50, 30, 5].map(heatColorForRate);
    expect(new Set(bands).size).toBe(bands.length);
  });

  it("treats band boundaries as inclusive on the lower edge", () => {
    expect(heatColorForRate(80)).toBe(heatColorForRate(100));
    expect(heatColorForRate(60)).toBe(heatColorForRate(79.9));
    expect(heatColorForRate(60)).not.toBe(heatColorForRate(59.9));
    expect(heatColorForRate(40)).not.toBe(heatColorForRate(39.9));
    expect(heatColorForRate(20)).not.toBe(heatColorForRate(19.9));
  });
});

describe("heatTextClass", () => {
  it("uses a dark text color when there is no rate", () => {
    expect(heatTextClass(null)).toBe("text-slate-800");
    expect(heatTextClass(Number.NaN)).toBe("text-slate-800");
  });

  it("uses white text when a rate exists", () => {
    expect(heatTextClass(0)).toBe("text-white");
    expect(heatTextClass(100)).toBe("text-white");
  });
});

describe("formatConsistencyRate", () => {
  it("describes missing data rather than showing zero", () => {
    expect(formatConsistencyRate(null)).toBe("No recorded votes");
    expect(formatConsistencyRate(undefined)).toBe("No recorded votes");
  });

  it("formats to one decimal place", () => {
    expect(formatConsistencyRate(72.44)).toBe("72.4% policy-consistent");
    expect(formatConsistencyRate(0)).toBe("0.0% policy-consistent");
  });
});

describe("indexStateMetrics", () => {
  const row = (stateCode: string, rate: number | null, recordedVotes = 5): StateMetric =>
    ({
      state: `State ${stateCode}`,
      stateCode,
      policyConsistencyRate: rate,
      recordedVotes,
    }) as StateMetric;

  it("keys by uppercased state code", () => {
    const map = indexStateMetrics([row("al", 50), row("AK", 60)]);
    expect(map.get("AL")).toBeDefined();
    expect(map.get("AK")).toBeDefined();
    expect(map.size).toBe(2);
  });

  it("skips rows without a state code", () => {
    const map = indexStateMetrics([row("", 50), row("TX", 40)]);
    expect(map.size).toBe(1);
    expect(map.has("TX")).toBe(true);
  });

  it("keeps the last row when codes collide", () => {
    const map = indexStateMetrics([row("TX", 10), row("tx", 90)]);
    expect(map.size).toBe(1);
    expect(map.get("TX")).toMatchObject({ policyConsistencyRate: 90 });
  });
});

describe("statesWithRecordedVotes", () => {
  const make = (state: string, rate: number | null, recordedVotes: number): StateMetric =>
    ({
      state,
      stateCode: state.slice(0, 2),
      policyConsistencyRate: rate,
      recordedVotes,
    }) as StateMetric;

  it("drops states with no recorded votes or no rate", () => {
    const result = statesWithRecordedVotes([
      make("Alabama", 50, 10),
      make("Alaska", 60, 0),
      make("Arizona", null, 5),
    ]);
    expect(result.map((r) => r.state)).toEqual(["Alabama"]);
  });

  it("sorts by rate desc then name asc", () => {
    const result = statesWithRecordedVotes([
      make("Beta", 50, 1),
      make("Alpha", 50, 1),
      make("Gamma", 90, 1),
    ]);
    expect(result.map((r) => r.state)).toEqual(["Gamma", "Alpha", "Beta"]);
  });

  it("does not mutate the input array", () => {
    const input = [make("A", 10, 1), make("B", 90, 1)];
    const snapshot = input.map((r) => r.state);
    statesWithRecordedVotes(input);
    expect(input.map((r) => r.state)).toEqual(snapshot);
  });

  it("returns an empty array for empty input", () => {
    expect(statesWithRecordedVotes([])).toEqual([]);
  });
});
