import type { Metadata } from "next";
import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { AdminNav } from "@/components/admin/AdminNav";
import { AdminNotice, AdminPageHeader } from "@/components/admin/AdminPageHeader";
import { AdminAccountPanels } from "@/components/admin/AdminAccountPanels";
import { ADMIN_SESSION_COOKIE, getAdminMe, getAdminSessions } from "@/lib/admin-api";

export const metadata: Metadata = {
  title: "Account",
  robots: { index: false, follow: false, nocache: true },
};

export const dynamic = "force-dynamic";

export default async function AdminAccountPage() {
  const token = (await cookies()).get(ADMIN_SESSION_COOKIE)?.value;
  if (!token) redirect("/admin/login");

  const cookieHeader = (await headers()).get("cookie") ?? "";
  const user = await getAdminMe(cookieHeader);
  if (!user) redirect("/admin/login");

  const sessions = await getAdminSessions(cookieHeader);

  return (
    <div className="container mx-auto w-full max-w-4xl px-4 py-8">
      <AdminPageHeader
        title="Your account"
        displayName={user.displayName}
        email={user.email}
        role={user.role}
      />

      <div className="mt-6">
        <AdminNav current="/admin/account" />
      </div>

      {sessions.status === "unauthenticated" ? (
        redirect("/admin/login")
      ) : sessions.status === "ok" ? (
        <AdminAccountPanels
          mfaEnabled={user.mfaEnabled}
          sessions={sessions.data.sessions}
        />
      ) : (
        <div className="mt-6">
          <AdminNotice tone="error">
            Could not load your sessions right now. Try again shortly.
          </AdminNotice>
        </div>
      )}
    </div>
  );
}
