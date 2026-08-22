import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { NONPROFIT, nonprofitStatusSummary } from "./nonprofit";

const SOURCE_DIR = dirname(fileURLToPath(import.meta.url));

describe("nonprofit public status", () => {
  it("publishes 501(c)(3) facts without an EIN", () => {
    expect(NONPROFIT.legalName).toBe("Operation Child Shield");
    expect(NONPROFIT.ircSection).toBe("501(c)(3)");
    expect(NONPROFIT.publicCharityStatus).toBe("170(b)(1)(A)(vi)");
    expect(NONPROFIT.effectiveDateLabel).toBe("July 1, 2026");
    expect(NONPROFIT.contributionDeductible).toBe(true);
    expect(NONPROFIT.mailingAddress).toContain("Manson, WA");
    expect(nonprofitStatusSummary()).toContain("501(c)(3)");
    expect(nonprofitStatusSummary()).toContain("tax-deductible");

    const published = JSON.stringify(NONPROFIT);
    expect(published).not.toMatch(/\b\d{2}-\d{7}\b/);
    expect(published.toLowerCase()).not.toContain("ein");
    expect(Object.keys(NONPROFIT)).not.toContain("ein");
  });

  it("keeps employer-id language out of the public nonprofit module", () => {
    const source = readFileSync(join(SOURCE_DIR, "nonprofit.ts"), "utf8");
    expect(source.toLowerCase()).not.toContain("ein");
    expect(source).not.toMatch(/\b\d{2}-\d{7}\b/);
    expect(source).not.toMatch(/\b\d{9}\b/);
  });
});
