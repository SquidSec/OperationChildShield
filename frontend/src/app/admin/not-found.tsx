import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Not found",
  robots: { index: false, follow: false, nocache: true },
};

export default function AdminNotFound() {
  return (
    <div className="mx-auto flex min-h-[60vh] w-full max-w-md flex-col justify-center px-4 py-12">
      <p className="m-0 text-xs font-semibold uppercase tracking-[0.2em] text-red">
        Operation Child Shield
      </p>
      <h1 className="mt-2 text-3xl font-bold text-blue">Page not found</h1>
      <p className="mt-3 text-sm leading-relaxed text-muted">
        That admin page does not exist. It may have moved, or the link may be
        mistyped.
      </p>
      <div className="mt-8 flex gap-3">
        <Link
          href="/admin"
          className="rounded-full bg-blue px-4 py-2 text-sm font-semibold text-white no-underline hover:opacity-90"
        >
          Back to dashboard
        </Link>
        <Link
          href="/"
          className="rounded-full border border-card-border bg-surface px-4 py-2 text-sm font-semibold text-muted no-underline hover:text-blue"
        >
          Public site
        </Link>
      </div>
    </div>
  );
}
