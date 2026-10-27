import { describe, expect, it } from "vitest";
import {
  auditActionLabel,
  busiestDay,
  dailyAverage,
  formatBytes,
  formatUptime,
  parseRangeDays,
  percentChange,
  roleBadgeClass,
  roleLabel,
  totalActions,
} from "./admin-format";

describe("parseRangeDays", () => {
  it("accepts offered ranges", () => {
    expect(parseRangeDays("1")).toBe(1);
    expect(parseRangeDays("7")).toBe(7);
    expect(parseRangeDays("30")).toBe(30);
    expect(parseRangeDays("90")).toBe(90);
  });

  it("falls back for junk and out-of-range values", () => {
    expect(parseRangeDays(undefined)).toBe(30);
    expect(parseRangeDays("")).toBe(30);
    expect(parseRangeDays("365")).toBe(30);
    expect(parseRangeDays("-5")).toBe(30);
    expect(parseRangeDays("abc")).toBe(30);
    expect(parseRangeDays("7; DROP TABLE page_views")).toBe(30);
  });
});

describe("percentChange", () => {
  it("reports growth and decline", () => {
    expect(percentChange(150, 100)).toBe("+50% vs. prior period");
    expect(percentChange(50, 100)).toBe("-50% vs. prior period");
  });

  it("handles a period with no prior traffic", () => {
    expect(percentChange(10, 0)).toBe("new activity");
    expect(percentChange(0, 0)).toBe("no change");
  });
});

describe("dailyAverage", () => {
  it("rounds views per day", () => {
    expect(dailyAverage({ pageViews: 100, days: 7 })).toBe(14);
    expect(dailyAverage({ pageViews: 0, days: 30 })).toBe(0);
  });

  it("avoids division by zero", () => {
    expect(dailyAverage({ pageViews: 10, days: 0 })).toBe(0);
  });
});

describe("busiestDay", () => {
  it("picks the highest day", () => {
    expect(
      busiestDay([
        { date: "2026-10-01", views: 4 },
        { date: "2026-10-02", views: 12 },
        { date: "2026-10-03", views: 9 },
      ])
    ).toEqual({ date: "2026-10-02", views: 12 });
  });

  it("returns null for an empty series", () => {
    expect(busiestDay([])).toBeNull();
  });
});

describe("totalActions", () => {
  it("sums engagement actions", () => {
    expect(
      totalActions({ actions: { share: 3, contactCongress: 2, signups: 1 } })
    ).toBe(6);
  });
});

describe("formatBytes", () => {
  it("scales to readable units", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 MB");
  });

  it("handles junk input", () => {
    expect(formatBytes(Number.NaN)).toBe("0 B");
    expect(formatBytes(-10)).toBe("0 B");
  });
});

describe("formatUptime", () => {
  it("picks the largest useful unit", () => {
    expect(formatUptime(45)).toBe("45s");
    expect(formatUptime(90)).toBe("1m");
    expect(formatUptime(3700)).toBe("1h 1m");
    expect(formatUptime(90000)).toBe("1d 1h");
  });

  it("marks invalid input", () => {
    expect(formatUptime(-1)).toBe("—");
  });
});

describe("roleLabel", () => {
  it("title-cases known roles and defaults to Editor", () => {
    expect(roleLabel("owner")).toBe("Owner");
    expect(roleLabel("viewer")).toBe("Viewer");
    expect(roleLabel(undefined)).toBe("Editor");
    expect(roleLabel("something-else")).toBe("Editor");
  });
});

describe("roleBadgeClass", () => {
  it("uses a distinct class per role", () => {
    expect(roleBadgeClass("owner")).toContain("text-red");
    expect(roleBadgeClass("editor")).toContain("text-blue");
    expect(roleBadgeClass("viewer")).toContain("text-muted");
  });
});

describe("auditActionLabel", () => {
  it("reads like a sentence fragment", () => {
    expect(auditActionLabel("login_success")).toBe("Login success");
    expect(auditActionLabel("role_change")).toBe("Role change");
    expect(auditActionLabel("")).toBe("Event");
  });
});
