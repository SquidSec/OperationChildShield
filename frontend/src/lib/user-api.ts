import type { AlertSubscription, SavedMember, UserProfile } from "./user-types";

export const USER_SESSION_COOKIE = "ocs_user_session";

export function serverApiBase(): string {
  return (
    process.env.API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000"
  );
}

export function hasUserSessionCookie(cookieHeader: string | null | undefined): boolean {
  if (!cookieHeader) return false;
  return cookieHeader
    .split(";")
    .some((part) => part.trim().startsWith(`${USER_SESSION_COOKIE}=`));
}

export async function getUserProfile(
  cookieHeader: string
): Promise<{ user: UserProfile; savedMembers: SavedMember[] } | null> {
  const res = await fetch(`${serverApiBase()}/api/account/me`, {
    cache: "no-store",
    headers: { cookie: cookieHeader },
  });
  if (!res.ok) return null;
  return res.json();
}

export async function getAlertSubscriptions(
  cookieHeader: string
): Promise<AlertSubscription[]> {
  const res = await fetch(`${serverApiBase()}/api/account/alerts`, {
    cache: "no-store",
    headers: { cookie: cookieHeader },
  });
  if (!res.ok) return [];
  const body = (await res.json()) as { alerts?: AlertSubscription[] };
  return body.alerts ?? [];
}
