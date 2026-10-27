import type {
  AdminFetchResult,
  AdminHealth,
  AdminMe,
  AdminRole,
  AdminSession,
  AdminUser,
  AuditEntry,
  BackupEntry,
  BoardApplication,
  SiteTraffic,
} from "./admin-types";

export function serverApiBase(): string {
  return (
    process.env.API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000"
  );
}

export const ADMIN_SESSION_COOKIE = "ocs_admin_session";

/** True when a raw Cookie header carries the admin session cookie. */
export function hasAdminSessionCookie(cookieHeader: string | null | undefined): boolean {
  if (!cookieHeader) return false;
  return cookieHeader
    .split(";")
    .some((part) => part.trim().startsWith(`${ADMIN_SESSION_COOKIE}=`));
}

function withCookie(cookieHeader: string) {
  return { cache: "no-store" as const, headers: { cookie: cookieHeader } };
}

/** Fetch a JSON endpoint as the signed-in admin, mapping auth failures. */
async function getAsAdmin<T>(
  cookieHeader: string,
  path: string
): Promise<AdminFetchResult<T>> {
  try {
    const res = await fetch(`${serverApiBase()}${path}`, withCookie(cookieHeader));
    if (res.status === 401) return { status: "unauthenticated" };
    if (res.status === 403) return { status: "forbidden" };
    if (!res.ok) return { status: "error" };
    return { status: "ok", data: (await res.json()) as T };
  } catch {
    return { status: "error" };
  }
}

export async function getAdminTraffic(
  cookieHeader: string,
  days: number
): Promise<SiteTraffic | null> {
  const res = await fetch(`${serverApiBase()}/api/admin/traffic?days=${days}`, withCookie(cookieHeader));
  if (res.status === 401) return null;
  if (!res.ok) {
    throw new Error(`Traffic request failed (${res.status})`);
  }
  return res.json();
}

export async function getAdminMe(
  cookieHeader: string
): Promise<AdminMe | null> {
  const res = await fetch(`${serverApiBase()}/api/admin/me`, withCookie(cookieHeader));
  if (res.status === 401) return null;
  if (!res.ok) return null;
  const body = (await res.json()) as {
    user?: {
      id?: number;
      email?: string;
      displayName?: string;
      role?: AdminRole;
      mfaEnabled?: boolean;
    };
  };
  if (!body.user?.email) return null;
  return {
    id: body.user.id ?? 0,
    email: body.user.email,
    displayName: body.user.displayName || body.user.email,
    role: body.user.role ?? "editor",
    mfaEnabled: Boolean(body.user.mfaEnabled),
  };
}

export function getAdminHealth(cookieHeader: string) {
  return getAsAdmin<AdminHealth>(cookieHeader, "/api/admin/health");
}

export function getAdminAudit(cookieHeader: string, limit = 100) {
  return getAsAdmin<{ entries: AuditEntry[] }>(
    cookieHeader,
    `/api/admin/audit?limit=${limit}`
  );
}

export function getAdminUsers(cookieHeader: string) {
  return getAsAdmin<{ users: AdminUser[] }>(cookieHeader, "/api/admin/users");
}

export function getAdminSessions(cookieHeader: string) {
  return getAsAdmin<{ sessions: AdminSession[] }>(
    cookieHeader,
    "/api/admin/sessions"
  );
}

export function getAdminApplications(cookieHeader: string, limit = 200) {
  return getAsAdmin<{ applications: BoardApplication[]; total: number }>(
    cookieHeader,
    `/api/admin/applications?limit=${limit}`
  );
}

export function getAdminBackups(cookieHeader: string) {
  return getAsAdmin<{ backups: BackupEntry[] }>(cookieHeader, "/api/admin/backups");
}

export async function getAdminConfig(): Promise<{
  captchaRequired: boolean;
  captchaSiteKey: string;
  captchaConfigured: boolean;
}> {
  try {
    // Called from a server component, so this needs an absolute URL.
    const res = await fetch(`${serverApiBase()}/api/admin/config`, {
      cache: "no-store",
    });
    if (!res.ok) throw new Error("config unavailable");
    return await res.json();
  } catch {
    return { captchaRequired: true, captchaSiteKey: "", captchaConfigured: false };
  }
}
