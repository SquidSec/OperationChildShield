/** Canonical origin and shared site metadata used by metadata routes and JSON-LD. */
export const SITE_URL = (
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://operationchildshield.org"
).replace(/\/+$/, "");

export const SITE_NAME = "Operation Child Shield";

export const SITE_DESCRIPTION =
  "Which child-protection bills are moving, how members voted or abstained, and how to press Congress. A 501(c)(3) public record from Congress.gov.";

export const CONTACT_EMAIL = "Contact@OperationChildShield.org";

export function siteUrl(path = "/"): string {
  if (!path || path === "/") return SITE_URL;
  return `${SITE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

export interface StaticRoute {
  path: string;
  changeFrequency:
    | "always"
    | "hourly"
    | "daily"
    | "weekly"
    | "monthly"
    | "yearly"
    | "never";
  priority: number;
}

/** Public pages that are always indexable (search/compare are excluded). */
export const STATIC_PUBLIC_ROUTES: StaticRoute[] = [
  { path: "/", changeFrequency: "daily", priority: 1 },
  { path: "/metrics", changeFrequency: "daily", priority: 0.9 },
  { path: "/bills", changeFrequency: "weekly", priority: 0.9 },
  { path: "/the-facts", changeFrequency: "monthly", priority: 0.7 },
  { path: "/get-involved", changeFrequency: "monthly", priority: 0.7 },
  { path: "/learn", changeFrequency: "monthly", priority: 0.6 },
  { path: "/about", changeFrequency: "monthly", priority: 0.6 },
  { path: "/organization", changeFrequency: "monthly", priority: 0.5 },
  { path: "/partners", changeFrequency: "monthly", priority: 0.5 },
  { path: "/board", changeFrequency: "monthly", priority: 0.4 },
  { path: "/donate", changeFrequency: "monthly", priority: 0.5 },
  { path: "/disclaimer", changeFrequency: "yearly", priority: 0.3 },
];
