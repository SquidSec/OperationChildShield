import { describe, expect, it } from "vitest";
import {
  CONTACT_EMAIL,
  SITE_NAME,
  SITE_URL,
  STATIC_PUBLIC_ROUTES,
  siteUrl,
} from "./site";
import {
  memberJsonLd,
  metricsJsonLd,
  siteJsonLd,
} from "./structured-data";

describe("siteUrl", () => {
  it("returns the bare origin for root", () => {
    expect(siteUrl()).toBe(SITE_URL);
    expect(siteUrl("/")).toBe(SITE_URL);
    expect(siteUrl("")).toBe(SITE_URL);
  });

  it("joins paths with exactly one slash", () => {
    expect(siteUrl("/metrics")).toBe(`${SITE_URL}/metrics`);
    expect(siteUrl("metrics")).toBe(`${SITE_URL}/metrics`);
  });

  it("never emits a double slash", () => {
    expect(siteUrl("/a/b").includes("//a")).toBe(false);
  });
});

describe("static route table", () => {
  it("includes the home page with the highest priority", () => {
    const home = STATIC_PUBLIC_ROUTES.find((route) => route.path === "/");
    expect(home).toBeDefined();
    expect(home?.priority).toBe(1);
  });

  it("excludes private routes from the sitemap", () => {
    const paths = STATIC_PUBLIC_ROUTES.map((route) => route.path);
    for (const privatePath of ["/admin", "/account", "/search", "/compare"]) {
      expect(paths.some((path) => path.startsWith(privatePath))).toBe(false);
    }
  });

  it("keeps priorities within the sitemap protocol range", () => {
    for (const route of STATIC_PUBLIC_ROUTES) {
      expect(route.priority).toBeGreaterThan(0);
      expect(route.priority).toBeLessThanOrEqual(1);
      expect(route.path.startsWith("/")).toBe(true);
    }
  });
});

describe("structured data", () => {
  it("declares Organization and WebSite nodes", () => {
    const graph = siteJsonLd()["@graph"] as Array<Record<string, unknown>>;
    const types = graph.map((node) => node["@type"]);
    expect(types).toContain("Organization");
    expect(types).toContain("WebSite");

    const org = graph.find((node) => node["@type"] === "Organization");
    expect(org?.name).toBe(SITE_NAME);
    expect(org?.email).toBe(CONTACT_EMAIL);
    expect(org?.nonprofitStatus).toBe("Nonprofit501c3");
  });

  it("produces JSON-serializable output with no undefined values", () => {
    const json = JSON.stringify(siteJsonLd());
    expect(json).not.toContain("undefined");
    expect(() => JSON.parse(json)).not.toThrow();
  });

  it("describes a member without inventing a rating", () => {
    const node = memberJsonLd({
      bioguideId: "A000055",
      name: "Robert B. Aderholt",
      party: "Republican",
      state: "Alabama",
      chamber: "House",
    });
    expect(node["@type"]).toBe("Person");
    expect(node.name).toBe("Robert B. Aderholt");
    expect(node.url).toBe(siteUrl("/member/A000055"));
    // A voting record is not a rating; the graph must not claim one.
    expect(JSON.stringify(node).toLowerCase()).not.toContain("rating");
    expect(JSON.stringify(node).toLowerCase()).not.toContain("score");
  });

  it("escapes nothing that would break a JSON script tag", () => {
    const json = JSON.stringify(
      memberJsonLd({
        bioguideId: "X1",
        name: 'Rep. "Quote" <script>',
        party: "Independent",
        state: "Alaska",
        chamber: "Senate",
      })
    );
    // The raw sequence must not appear unescaped inside the serialized string.
    expect(json.includes("</script>")).toBe(false);
  });

  it("emits a Dataset for the metrics page", () => {
    const node = metricsJsonLd({
      name: "House voting record",
      description: "Recorded floor votes on tracked child-protection bills.",
      congress: 119,
      lastUpdated: "2026-10-27",
      recordCount: 42,
    });
    expect(node["@type"]).toBe("Dataset");
    expect(node.isAccessibleForFree).toBe(true);
    expect(String(node.citation)).toContain("Congress.gov");
    expect(String(node.citation)).toContain("119th");
    expect(node.size).toContain("42");
  });

  it("links the Dataset to the organization node", () => {
    const node = metricsJsonLd({
      name: "n",
      description: "d",
      congress: 119,
      lastUpdated: "2026-10-27",
      recordCount: 1,
    });
    expect(JSON.stringify(node.creator)).toContain("#organization");
    expect(JSON.stringify(node.publisher)).toContain("#organization");
  });
});
