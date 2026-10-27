import { afterEach, describe, expect, it, vi } from "vitest";
import {
  USER_SESSION_COOKIE,
  getAlertSubscriptions,
  getUserProfile,
  hasUserSessionCookie,
  serverApiBase,
} from "./user-api";

function mockFetch(response: Partial<Response> & { json?: () => unknown }) {
  const spy = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({}),
    ...response,
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("hasUserSessionCookie", () => {
  it("detects the cookie among others", () => {
    expect(hasUserSessionCookie(`${USER_SESSION_COOKIE}=abc123`)).toBe(true);
    expect(
      hasUserSessionCookie(`theme=dark; ${USER_SESSION_COOKIE}=abc123; x=1`)
    ).toBe(true);
    expect(hasUserSessionCookie(` ${USER_SESSION_COOKIE}=abc`)).toBe(true);
  });

  it("rejects missing, empty, and prefix-lookalike cookies", () => {
    expect(hasUserSessionCookie(null)).toBe(false);
    expect(hasUserSessionCookie(undefined)).toBe(false);
    expect(hasUserSessionCookie("")).toBe(false);
    expect(hasUserSessionCookie("theme=dark")).toBe(false);
    // A different cookie whose name merely starts with ours must not match.
    expect(hasUserSessionCookie(`${USER_SESSION_COOKIE}_other=abc`)).toBe(false);
  });
});

describe("serverApiBase", () => {
  it("returns an absolute URL with no trailing slash", () => {
    const base = serverApiBase();
    expect(base.startsWith("http")).toBe(true);
    expect(base.endsWith("/")).toBe(false);
  });
});

describe("getUserProfile", () => {
  it("returns the profile on success", async () => {
    const payload = {
      user: { id: 1, email: "a@b.org", displayName: "A", emailVerified: true },
      savedMembers: [],
    };
    const spy = mockFetch({ ok: true, json: async () => payload });
    const result = await getUserProfile("cookie=1");
    expect(result).toEqual(payload);
    // The cookie header is forwarded so the backend can identify the session.
    expect(spy).toHaveBeenCalledWith(
      expect.stringContaining("/api/account/me"),
      expect.objectContaining({ headers: { cookie: "cookie=1" } })
    );
  });

  it("returns null when the session is rejected", async () => {
    mockFetch({ ok: false, json: async () => ({}) });
    expect(await getUserProfile("cookie=1")).toBeNull();
  });
});

describe("getAlertSubscriptions", () => {
  it("returns the alerts array", async () => {
    const alerts = [{ kind: "weekly_digest", bioguideId: "", active: true }];
    mockFetch({ ok: true, json: async () => ({ alerts }) });
    expect(await getAlertSubscriptions("c=1")).toEqual(alerts);
  });

  it("defaults to an empty array when the body has no alerts", async () => {
    mockFetch({ ok: true, json: async () => ({}) });
    expect(await getAlertSubscriptions("c=1")).toEqual([]);
  });

  it("returns an empty array on an error response", async () => {
    mockFetch({ ok: false, json: async () => ({ alerts: [{ kind: "x" }] }) });
    expect(await getAlertSubscriptions("c=1")).toEqual([]);
  });
});
