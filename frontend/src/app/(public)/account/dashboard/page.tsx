import type { Metadata } from "next";
import Link from "next/link";
import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { AccountDashboard } from "@/components/account/AccountDashboard";
import { getAlertSubscriptions, getUserProfile, USER_SESSION_COOKIE } from "@/lib/user-api";

export const metadata: Metadata = {
  title: "Your account",
  robots: { index: false, follow: false },
};

export const dynamic = "force-dynamic";

export default async function AccountDashboardPage() {
  const cookieStore = await cookies();
  if (!cookieStore.get(USER_SESSION_COOKIE)?.value) redirect("/account");

  const cookieHeader = (await headers()).get("cookie") ?? "";
  const [profile, alerts] = await Promise.all([
    getUserProfile(cookieHeader),
    getAlertSubscriptions(cookieHeader),
  ]);
  if (!profile) redirect("/account");

  return (
    <div className="page-container py-10">
      <div className="mx-auto max-w-3xl">
        <Link href="/" className="text-sm text-muted hover:text-blue">
          ← Back to lawmakers
        </Link>
        <h1 className="mt-4 text-3xl font-bold text-blue">
          {profile.user.displayName || "Your account"}
        </h1>
        <p className="mt-1 text-sm text-muted">{profile.user.email}</p>
        <AccountDashboard
          initialSaved={profile.savedMembers}
          initialAlerts={alerts}
        />
      </div>
    </div>
  );
}
