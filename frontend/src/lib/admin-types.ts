export type TrafficPoint = { date: string; views: number };
export type TrafficPage = { path: string; views: number };
export type TrafficReferrer = { domain: string; views: number };

export interface SiteTraffic {
  days: number;
  since: string;
  generatedAt: string;
  pageViews: number;
  previousPageViews: number;
  /** Automated hits stored but excluded from every visitor metric. */
  botPageViews: number;
  botReasons: { reason: string; count: number }[];
  daily: TrafficPoint[];
  topPages: TrafficPage[];
  topReferrers: TrafficReferrer[];
  actions: {
    share: number;
    contactCongress: number;
    signups: number;
  };
}

export type AdminRole = "viewer" | "editor" | "owner";

export interface AdminUser {
  id: number;
  email: string;
  displayName: string;
  isActive: boolean;
  lastLoginAt: string | null;
  role: AdminRole;
  mfaEnabled: boolean;
}

export interface AdminMe {
  id: number;
  email: string;
  displayName: string;
  role: AdminRole;
  mfaEnabled: boolean;
}

export interface AuditEntry {
  id: number;
  actor: string;
  action: string;
  detail: string;
  ip: string | null;
  createdAt: string;
}

export interface AdminSession {
  id: string;
  createdAt: string;
  expiresAt: string;
  ip: string | null;
  userAgent: string | null;
  isCurrent: boolean;
}

export interface AdminHealth {
  analyticsDbBytes: number;
  adminDbBytes: number;
  pageViewRows: number;
  oldestPageView: string | null;
  cacheFileCount: number;
  congressApiConfigured: boolean;
  schedulerEnabled: boolean;
  schedulerLastRun: { at: string; jobs: string[] } | null;
  uptimeSeconds: number;
  generatedAt: string;
}

/** A board application. All fields are plain text; render as text, never HTML. */
export interface BoardApplication {
  /** Stable hash id used for delete; absent on older stored rows. */
  id?: string;
  submittedAt: string;
  role: string;
  roleLabel: string;
  name: string;
  email: string;
  phone: string;
  location: string;
  linkedin: string;
  statement: string;
  source: string;
}

export interface BackupEntry {
  name: string;
  bytes: number;
  createdAt: string;
}

/** Result of a server-side fetch that can fail by permission or session. */
export type AdminFetchResult<T> =
  | { status: "ok"; data: T }
  | { status: "unauthenticated" }
  | { status: "forbidden" }
  | { status: "error" };
