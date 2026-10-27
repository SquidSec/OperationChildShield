import { describe, expect, it } from "vitest";
import { ApiError, apiErrorStatus, friendlyErrorMessage } from "./errors";

describe("friendlyErrorMessage", () => {
  it("never surfaces raw API error text", () => {
    const message = friendlyErrorMessage(new ApiError(502, "API error 502: upstream boom"));
    expect(message).not.toContain("upstream boom");
    expect(message).toMatch(/temporarily unavailable/);
  });

  it("explains timeouts", () => {
    expect(
      friendlyErrorMessage(new Error("Request timed out while waiting for congressional data"))
    ).toMatch(/took too long/);
  });

  it("falls back to the supplied copy for unknown errors", () => {
    expect(friendlyErrorMessage(new Error("kaboom"), "Custom copy.")).toBe("Custom copy.");
    expect(friendlyErrorMessage(undefined)).toMatch(/Something went wrong/);
  });
});

describe("apiErrorStatus", () => {
  it("exposes the upstream status only for ApiError", () => {
    expect(apiErrorStatus(new ApiError(400, "API error 400: bad"))).toBe(400);
    expect(apiErrorStatus(new Error("API error 400: bad"))).toBeNull();
  });
});
