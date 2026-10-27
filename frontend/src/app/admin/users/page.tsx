import type { Metadata } from "next";
import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { AdminNav } from "@/components/admin/AdminNav";
import { AdminNotice, AdminPageHeader } from "@/components/admin/AdminPageHeader";
import { AdminUsersPanel } from "@/components/admin/AdminUsersPanel";
import { ADMIN_SESSION_COOKIE, getAdminMe, getAdminUsers } from "@/lib/admin-api";

export const metadata: Metadata = {
  title: "Admin users",
  robots: { index: false, follow: false, nocache: true },
};

export const dynamic = "force-dynamic";

export default async function AdminUsersPage() {
  const token = (await cookies()).get(ADMIN_SESSION_COOKIE)?.value;
  if (!token) redirect("/admin/login");

  const cookieHeader = (await headers()).get("cookie") ?? "";
  const user = await getAdminMe(cookieHeader);
  if (!user) redirect("/admin/login");

  const users = await getAdminUsers(cookieHeader);

  return (
    <div className="container mx-auto w-full max-w-6xl px-4 py-8">
      <AdminPageHeader
        title="Admin users"
        displayName={user.displayName}
        email={user.email}
        role={user.role}
      />

      <div className="mt-6">
        <AdminNav current="/admin/users" />
      </div>

      {users.status === "forbidden" ? (
        <div className="mt-6">
          <AdminNotice tone="error">
            Account management is limited to owners. Your role is {user.role}; ask
            an owner if you need access.
          </AdminNotice>
        </div>
      ) : users.status === "unauthenticated" ? (
        redirect("/admin/login")
      ) : users.status === "error" ? (
        <div className="mt-6">
          <AdminNotice tone="error">
            Could not load admin accounts right now. Try again shortly.
          </AdminNotice>
        </div>
      ) : (
        <AdminUsersPanel users={users.data.users} currentUserId={user.id} />
      )}
    </div>
  );
}
