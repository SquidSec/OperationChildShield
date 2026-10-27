import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Page not found",
  robots: { index: false, follow: true },
};

/**
 * Catches unmatched URLs that never reach the (public) route group, so the 404
 * keeps the site's styling and navigation instead of Next.js's built-in page.
 */
export default function NotFound() {
  return (
    <div className="page-container py-16 text-center">
      <p className="m-0 text-xs font-bold uppercase tracking-wider text-red">
        404 · Not Found
      </p>
      <h1 className="mt-2 text-3xl font-bold text-blue">This page could not be found</h1>
      <p className="mx-auto mt-3 max-w-xl text-muted leading-relaxed">
        The link may be outdated. Start from the lawmaker directory or see how
        Congress voted on tracked child safety bills.
      </p>
      <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
        <Link
          href="/"
          className="rounded-md bg-red px-4 py-2.5 text-sm font-bold text-white no-underline hover:opacity-90"
        >
          Find your lawmakers
        </Link>
        <Link
          href="/metrics"
          className="rounded-md border border-card-border bg-surface px-4 py-2.5 text-sm font-bold text-blue no-underline hover:bg-surface-muted"
        >
          See the numbers
        </Link>
      </div>
    </div>
  );
}
