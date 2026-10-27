import type { Metadata } from "next";
import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { AdminNav } from "@/components/admin/AdminNav";
import { AdminNotice, AdminPageHeader } from "@/components/admin/AdminPageHeader";
import { AuditTable } from "@/components/admin/AuditTable";
import { ADMIN_SESSION_COOKIE, getAdminAudit, getAdminMe } from "@/lib/admin-api";

export const metadata: Metadata = {
  title: "Audit log",
  robots: { index: false, follow: false, nocache: true },
};

export const dynamic = "force-dynamic";

export default async function AdminAuditPage() {
  const token = (await cookies()).get(ADMIN_SESSION_COOKIE)?.value;
  if (!token) redirect("/admin/login");

  const cookieHeader = (await headers()).get("cookie") ?? "";
  const user = await getAdminMe(cookieHeader);
  if (!user) redirect("/admin/login");

  const audit = await getAdminAudit(cookieHeader, 100);

  return (
    <div className="container mx-auto w-full max-w-6xl px-4 py-8">
      <AdminPageHeader
        title="Audit log"
        displayName={user.displayName}
        email={user.email}
        role={user.role}
      />

      <div className="mt-6">
        <AdminNav current="/admin/audit" />
      </div>

      <section className="mt-6 rounded-xl border border-card-border bg-surface p-5 shadow-sm">
        <h2 className="m-0 text-sm font-semibold uppercase tracking-wide text-muted">
          Latest 100 events
        </h2>
        <div className="mt-4">
          {audit.status === "forbidden" ? (
            <AdminNotice tone="error">
              Only owners can read the audit log. Ask an owner for access.
            </AdminNotice>
          ) : audit.status === "unauthenticated" ? (
            <AdminNotice tone="error">Your session has expired. Sign in again.</AdminNotice>
          ) : audit.status === "error" ? (
            <AdminNotice tone="error">
              Could not load the audit log right now. Try again shortly.
            </AdminNotice>
          ) : (
            <AuditTable entries={audit.data.entries} />
          )}
        </div>
      </section>

      <p className="mt-6 text-xs text-muted">
        Sign-ins, account and role changes, MFA changes, password resets, session
        revocations, and CSV exports are recorded. Times are shown in UTC.
      </p>
    </div>
  );
}
