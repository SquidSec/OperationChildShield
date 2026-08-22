import type { MetricsOverview } from "./metrics-types";
import type { MemberSummary, ReportCard, TrackedBill } from "./types";

const API_URL =
  process.env.API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

async function fetchApi<T>(path: string, timeoutMs = 20_000): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    // Dev: never serve stale API data (bill categories/descriptions change often).
    // Prod: short revalidate so fixes land without a full rebuild-only dependency.
    const cacheOpts =
      process.env.NODE_ENV === "development"
        ? ({ cache: "no-store" } as const)
        : ({ next: { revalidate: 300 } } as const);

    const res = await fetch(`${API_URL}${path}`, {
      ...cacheOpts,
      signal: controller.signal,
    });

    if (!res.ok) {
      const body = await res.text();
      throw new Error(`API error ${res.status}: ${body}`);
    }

    return res.json();
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error("Request timed out while waiting for congressional data");
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export interface MemberFilters {
  search?: string;
  chamber?: string;
  state?: string;
  party?: string;
  limit?: number;
  offset?: number;
}

export const LANDING_PAGE_SIZE = 15;
export const SEARCH_PAGE_SIZE = 50;

function buildMembersQuery(filters: MemberFilters): string {
  const params = new URLSearchParams();
  if (filters.search) params.set("search", filters.search);
  if (filters.chamber) params.set("chamber", filters.chamber);
  if (filters.state) params.set("state", filters.state);
  if (filters.party) params.set("party", filters.party);
  if (filters.limit != null) params.set("limit", String(filters.limit));
  if (filters.offset != null) params.set("offset", String(filters.offset));
  return params.toString();
}

export type MembersResponse = {
  members: MemberSummary[];
  total: number;
  limit: number | null;
  offset: number;
  congress: number;
};

export async function getMembers(
  filters: MemberFilters = {}
): Promise<MembersResponse> {
  const qs = buildMembersQuery(filters);
  return fetchApi(`/api/members${qs ? `?${qs}` : ""}`);
}

/** Client-side member fetch for infinite scroll (no Next.js cache). */
export async function fetchMembersClient(
  filters: MemberFilters = {}
): Promise<MembersResponse> {
  const qs = buildMembersQuery(filters);
  const res = await fetch(`${API_URL}/api/members${qs ? `?${qs}` : ""}`);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }
  return res.json();
}

export async function getReportCard(bioguideId: string): Promise<ReportCard> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20_000);

  try {
    const res = await fetch(`${API_URL}/api/members/${bioguideId}/report-card`, {
      cache: "no-store",
      signal: controller.signal,
    });

    if (!res.ok) {
      const body = await res.text();
      throw new Error(`API error ${res.status}: ${body}`);
    }

    return res.json();
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error("Request timed out while waiting for voting record");
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export async function getTrackedBills(): Promise<{
  bills: TrackedBill[];
  congress: number;
}> {
  return fetchApi("/api/bills");
}

export async function getHealth(): Promise<{
  status: string;
  api_key_configured: boolean;
}> {
  return fetchApi("/api/health");
}

function metricsApiBase(): string {
  return (
    process.env.API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000"
  );
}

function normalizeMetricsOverview(payload: unknown): MetricsOverview {
  const data = payload as Partial<MetricsOverview>;
  return {
    congress: data.congress ?? 0,
    lastUpdated: data.lastUpdated ?? new Date().toISOString(),
    dataSource: data.dataSource ?? "Congress.gov API",
    methodologyNote: data.methodologyNote ?? "",
    kpis: {
      totalMembersTracked: data.kpis?.totalMembersTracked ?? 0,
      houseMembersWithRecordedVotes: data.kpis?.houseMembersWithRecordedVotes ?? 0,
      totalBillsTracked: data.kpis?.totalBillsTracked ?? 0,
      billsWithRollCalls: data.kpis?.billsWithRollCalls ?? 0,
      totalRecordedFloorVotes: data.kpis?.totalRecordedFloorVotes ?? 0,
      totalNotVotingInstances: data.kpis?.totalNotVotingInstances ?? 0,
    },
    chamberSummary: data.chamberSummary ?? [],
    byState: data.byState ?? [],
    bills: data.bills ?? [],
  };
}

export async function getMetrics(): Promise<MetricsOverview> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120_000);

  try {
    const res = await fetch(`${metricsApiBase()}/api/metrics`, {
      cache: "no-store",
      signal: controller.signal,
    });

    if (!res.ok) {
      const body = await res.text();
      throw new Error(`API error ${res.status}: ${body}`);
    }

    return normalizeMetricsOverview(await res.json());
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error("Request timed out while waiting for legislation overview");
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export function getMetricsExportUrl(): string {
  return `${metricsApiBase()}/api/metrics/export`;
}

export interface InvolveSignupPayload {
  name: string;
  email: string;
  state?: string;
  interest?: string;
  message?: string;
  consent: boolean;
  website?: string;
}

export async function submitInvolveSignup(
  payload: InvolveSignupPayload
): Promise<{ ok: boolean; message: string }> {
  const res = await fetch(`${metricsApiBase()}/api/involve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    let detail = `Signup failed (${res.status})`;
    try {
      const body = (await res.json()) as { detail?: string | { msg?: string }[] };
      if (typeof body.detail === "string") {
        detail = body.detail;
      } else if (Array.isArray(body.detail) && body.detail[0]?.msg) {
        detail = body.detail[0].msg;
      }
    } catch {
      /* use default */
    }
    throw new Error(detail);
  }

  return res.json();
}

export type TrackedAction = "share" | "contact_congress";

export type SiteImpact = {
  pageViews: number;
  shares: number;
  congressContacts: number;
  signups: number;
  updatedAt: string;
};

/** Fire-and-forget page view ingest. */
export async function trackPageView(path: string, referrer = ""): Promise<void> {
  try {
    await fetch(`${metricsApiBase()}/api/analytics/event`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, referrer }),
      keepalive: true,
    });
  } catch {
    /* non-blocking */
  }
}

/** Fire-and-forget allow-listed action (share / contact Congress). */
export async function trackAction(
  action: TrackedAction,
  path = "/"
): Promise<void> {
  try {
    await fetch(`${metricsApiBase()}/api/analytics/event`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, action }),
      keepalive: true,
    });
  } catch {
    /* non-blocking */
  }
}

export async function getImpact(): Promise<SiteImpact | null> {
  try {
    return await fetchApi<SiteImpact>("/api/impact", 8_000);
  } catch {
    return null;
  }
}