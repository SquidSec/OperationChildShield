import type { SiteTraffic } from "./admin-types";

export const ADMIN_RANGES = [
  { days: 1, label: "24 hours" },
  { days: 7, label: "7 days" },
  { days: 30, label: "30 days" },
  { days: 90, label: "90 days" },
] as const;

/** Clamp an untrusted ?days= value to one of the offered ranges. */
export function parseRangeDays(raw: string | undefined, fallback = 30): number {
  // Only accept a bare integer; parseInt would silently accept "7abc".
  if (!raw || !/^\d{1,3}$/.test(raw)) return fallback;
  const parsed = Number.parseInt(raw, 10);
  return ADMIN_RANGES.some((range) => range.days === parsed) ? parsed : fallback;
}

export function percentChange(current: number, previous: number): string {
  if (previous <= 0) return current > 0 ? "new activity" : "no change";
  const change = ((current - previous) / previous) * 100;
  const sign = change > 0 ? "+" : "";
  return `${sign}${change.toFixed(0)}% vs. prior period`;
}

export function dailyAverage(traffic: Pick<SiteTraffic, "pageViews" | "days">): number {
  if (traffic.days <= 0) return 0;
  return Math.round(traffic.pageViews / traffic.days);
}

export function busiestDay(
  daily: SiteTraffic["daily"]
): { date: string; views: number } | null {
  if (daily.length === 0) return null;
  return daily.reduce((best, point) => (point.views > best.views ? point : best));
}

export function totalActions(traffic: Pick<SiteTraffic, "actions">): number {
  const { share, contactCongress, signups } = traffic.actions;
  return share + contactCongress + signups;
}

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const exponent = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1
  );
  const value = bytes / 1024 ** exponent;
  return `${exponent === 0 ? value : value.toFixed(1)} ${units[exponent]}`;
}

/** Human-readable duration from a second count, e.g. "3d 4h". */
export function formatUptime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "—";
  const total = Math.floor(seconds);
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m`;
  return `${total}s`;
}

const ROLE_LABELS: Record<string, string> = {
  viewer: "Viewer",
  editor: "Editor",
  owner: "Owner",
};

export function roleLabel(role: string | null | undefined): string {
  return ROLE_LABELS[(role ?? "").toLowerCase()] ?? "Editor";
}

/** Stable class for a role badge, using the existing token palette. */
export function roleBadgeClass(role: string | null | undefined): string {
  switch ((role ?? "").toLowerCase()) {
    case "owner":
      return "border-red/40 bg-red/5 text-red";
    case "viewer":
      return "border-card-border bg-surface-muted text-muted";
    default:
      return "border-blue/30 bg-blue/5 text-blue";
  }
}

/** Friendly label for an audit action id (snake_case from the backend). */
export function auditActionLabel(action: string): string {
  const words = (action || "").split("_").filter(Boolean);
  if (words.length === 0) return "Event";
  return words
    .map((word, index) =>
      index === 0 ? word.charAt(0).toUpperCase() + word.slice(1) : word
    )
    .join(" ");
}

/** Human labels for the backend's bot reason codes. */
export const BOT_REASON_LABELS: Record<string, string> = {
  "no-ua": "No user agent",
  "declared-search": "Search engine bot",
  "declared-social": "Social / link preview",
  "declared-ai": "AI crawler",
  "declared-feed": "Feed reader",
  "declared-other": "Other declared bot",
  "client-lib": "HTTP client library",
  scanner: "Security scanner",
  monitor: "Uptime / speed monitor",
  prefetch: "Browser prefetch",
  "malformed-ua": "Malformed user agent",
  "non-browser": "Non-browser user agent",
  "implausible-headers": "Browser UA without browser headers",
  "rate-limit": "Request rate exceeded",
  datacenter: "Datacenter / hosting network",
  internal: "Admin / staff navigation",
};

export function botReasonLabel(reason: string): string {
  if (!reason) return "Unclassified";
  return BOT_REASON_LABELS[reason] ?? reason;
}

/** Share of requests that were automation, 0-100. */
export function botShare(bot: number, human: number): number {
  const total = bot + human;
  if (total <= 0) return 0;
  return Math.round((bot / total) * 100);
}
