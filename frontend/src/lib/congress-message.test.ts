import { describe, expect, it } from "vitest";
import {
  buildConstituentMailto,
  buildConstituentMessage,
} from "./congress-message";

describe("buildConstituentMessage", () => {
  it("builds a ready-to-send constituent letter", () => {
    const text = buildConstituentMessage({
      officialName: "Rep. Jane Doe",
      reportUrl: "https://operationchildshield.org/member/D000001",
    });
    expect(text).toContain("Dear Rep. Jane Doe,");
    expect(text).toContain("child safety");
    expect(text).toContain("anti-trafficking");
    expect(text).toContain("voted or abstained");
    expect(text).toContain("https://operationchildshield.org/member/D000001");
    expect(text).not.toMatch(/\b\d{2}-\d{7}\b/);
  });

  it("falls back to a generic greeting", () => {
    const text = buildConstituentMessage();
    expect(text).toContain("Dear Representative or Senator,");
    expect(buildConstituentMailto()).toMatch(/^mailto:\?/);
  });
});
