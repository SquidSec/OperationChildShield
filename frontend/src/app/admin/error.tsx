"use client";

import Link from "next/link";

/**
 * Admin segment error boundary. Client component per the App Router contract;
 * `reset` re-renders the failed segment.
 */
export default function AdminError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  void error;

  return (
    <div className="mx-auto flex min-h-[60vh] w-full max-w-md flex-col justify-center px-4 py-12">
      <p className="m-0 text-xs font-semibold uppercase tracking-[0.2em] text-red">
        Operation Child Shield
      </p>
      <h1 className="mt-2 text-3xl font-bold text-blue">Something went wrong</h1>
      <p className="mt-3 text-sm leading-relaxed text-muted">
        This admin screen could not be loaded. Try again; if it keeps failing, the
        backend may be unavailable.
      </p>
      <div className="mt-8 flex gap-3">
        <button
          type="button"
          onClick={reset}
          className="rounded-full bg-blue px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
        >
          Try again
        </button>
        <Link
          href="/admin"
          className="rounded-full border border-card-border bg-surface px-4 py-2 text-sm font-semibold text-muted no-underline hover:text-blue"
        >
          Back to dashboard
        </Link>
      </div>
    </div>
  );
}
