import Link from "next/link";
import { AdminLogoutButton } from "@/components/admin/AdminLogoutButton";

/** Page header shared by the admin screens: title, signed-in identity, sign out. */
export function AdminPageHeader({
  title,
  email,
  displayName,
  role,
}: {
  title: string;
  email: string;
  displayName: string;
  role: string;
}) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <p className="m-0 text-xs font-semibold uppercase tracking-[0.2em] text-red">
          Operation Child Shield
        </p>
        <h1 className="mt-1 text-3xl font-bold text-blue">{title}</h1>
        <p className="mt-2 text-sm text-muted">
          Signed in as {displayName} ({email}) · {role}
        </p>
      </div>
      <div className="flex items-center gap-3">
        <Link href="/" className="text-sm text-muted hover:text-blue">
          View site
        </Link>
        <AdminLogoutButton />
      </div>
    </header>
  );
}

/** Shared empty/error note used inside panels. */
export function AdminNotice({
  tone = "muted",
  children,
}: {
  tone?: "muted" | "error";
  children: React.ReactNode;
}) {
  const classes =
    tone === "error"
      ? "rounded-xl border border-red/40 bg-red/5 p-4 text-sm text-red"
      : "rounded-xl border border-card-border bg-surface p-4 text-sm text-muted";
  return <p className={`m-0 ${classes}`}>{children}</p>;
}
