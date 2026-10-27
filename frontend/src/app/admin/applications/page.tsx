import type { Metadata } from "next";
import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { AdminNav } from "@/components/admin/AdminNav";
import { AdminNotice, AdminPageHeader } from "@/components/admin/AdminPageHeader";
import { ApplicationsTable } from "@/components/admin/ApplicationsTable";
import {
  ADMIN_SESSION_COOKIE,
  getAdminApplications,
  getAdminMe,
} from "@/lib/admin-api";

export const metadata: Metadata = {
  title: "Board applications",
  robots: { index: false, follow: false, nocache: true },
};

export const dynamic = "force-dynamic";

export default async function AdminApplicationsPage() {
  const token = (await cookies()).get(ADMIN_SESSION_COOKIE)?.value;
  if (!token) redirect("/admin/login");

  const cookieHeader = (await headers()).get("cookie") ?? "";
  const user = await getAdminMe(cookieHeader);
  if (!user) redirect("/admin/login");

  const applications = await getAdminApplications(cookieHeader, 200);

  return (
    <div className="container mx-auto w-full max-w-6xl px-4 py-8">
      <AdminPageHeader
        title="Board applications"
        displayName={user.displayName}
        email={user.email}
        role={user.role}
      />

      <div className="mt-6">
        <AdminNav current="/admin/applications" />
      </div>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <h2 className="m-0 text-sm font-semibold uppercase tracking-wide text-muted">
          Latest applications
        </h2>
        {/* Direct link so the browser sends the cookie and downloads the file. */}
        <a
          href="/api/admin/applications/export"
          download
          className="rounded-full border border-card-border bg-surface px-4 py-2 text-sm font-semibold text-muted no-underline hover:text-blue"
        >
          Export CSV
        </a>
      </div>

      <section className="mt-4 rounded-xl border border-card-border bg-surface p-5 shadow-sm">
        <div className="mt-4">
          {applications.status === "forbidden" ? (
            <AdminNotice tone="error">
              Viewers cannot read applications. Ask an editor or owner for access.
            </AdminNotice>
          ) : applications.status === "unauthenticated" ? (
            <AdminNotice tone="error">Your session has expired. Sign in again.</AdminNotice>
          ) : applications.status === "error" ? (
            <AdminNotice tone="error">
              Could not load applications right now. Try again shortly.
            </AdminNotice>
          ) : (
            <ApplicationsTable
              applications={applications.data.applications}
              canDelete={user.role === "owner"}
            />
          )}
        </div>
      </section>

      <p className="mt-6 text-xs text-muted">
        Applicant text is stored and displayed as plain text. Control,
        zero-width, and bidi-override characters are stripped on write and again
        on read.
      </p>
    </div>
  );
}
