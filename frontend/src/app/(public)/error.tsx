"use client";

import { useEffect } from "react";
import Link from "next/link";

export default function PublicError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="page-container py-16 text-center" role="alert">
      <p className="m-0 text-xs font-bold uppercase tracking-wider text-red">
        Something went wrong
      </p>
      <h1 className="mt-2 text-3xl font-bold text-blue">
        We couldn&apos;t load this page
      </h1>
      <p className="mx-auto mt-3 max-w-xl text-muted leading-relaxed">
        This is usually a temporary problem reaching the congressional data
        service. Try again, or head back to the directory.
      </p>
      <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
        <button
          type="button"
          onClick={reset}
          className="rounded-md bg-red px-4 py-2.5 text-sm font-bold text-white hover:opacity-90"
        >
          Try again
        </button>
        <Link
          href="/"
          className="rounded-md border border-card-border bg-surface px-4 py-2.5 text-sm font-bold text-blue no-underline hover:bg-surface-muted"
        >
          Back to lawmakers
        </Link>
      </div>
    </div>
  );
}
