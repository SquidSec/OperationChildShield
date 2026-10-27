"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";
import { US_STATE_OPTIONS } from "@/lib/states";

const PARTY_OPTIONS = [
  { value: "", label: "All parties" },
  { value: "Democrat", label: "Democrat" },
  { value: "Republican", label: "Republican" },
  { value: "Independent", label: "Independent" },
] as const;

const CHAMBER_OPTIONS = [
  { value: "", label: "Both chambers" },
  { value: "House", label: "House" },
  { value: "Senate", label: "Senate" },
] as const;

type FilterKey = "party" | "state" | "chamber";

const SELECT_CLASS =
  "w-full max-w-full min-w-0 rounded-xl border-2 border-card-border bg-surface px-3 py-2.5 text-sm font-medium text-foreground outline-none focus:border-blue disabled:opacity-60 cursor-pointer";

export function MemberFiltersBar() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();

  // The query string is the single source of truth, so every control is
  // reload-safe and shareable.
  const activeParty = searchParams.get("party") || "";
  const activeState = searchParams.get("state") || "";
  const activeChamber = searchParams.get("chamber") || "";
  const hasFilters = Boolean(activeParty || activeState || activeChamber);

  function apply(next: URLSearchParams) {
    next.delete("offset");
    startTransition(() => {
      const qs = next.toString();
      router.replace(qs ? `/?${qs}` : "/", { scroll: false });
    });
  }

  function updateFilter(key: FilterKey, value: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (value) params.set(key, value);
    else params.delete(key);
    apply(params);
  }

  function clearFilters() {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("party");
    params.delete("state");
    params.delete("chamber");
    apply(params);
  }

  return (
    <div className="mb-8 w-full min-w-0">
      <p className="text-center text-sm font-semibold text-muted uppercase tracking-wider mb-3">
        Filter by Party, State &amp; Chamber
      </p>
      <div className="flex flex-col sm:flex-row flex-wrap justify-center gap-3 max-w-[860px] mx-auto w-full min-w-0">
        <label className="flex flex-col gap-1 w-full min-w-0 sm:min-w-[10rem] sm:flex-1 sm:max-w-[14rem]">
          <span className="text-xs font-semibold text-muted px-1">Party</span>
          <select
            aria-label="Filter by party"
            value={activeParty}
            disabled={isPending}
            onChange={(e) => updateFilter("party", e.target.value)}
            className={SELECT_CLASS}
          >
            {PARTY_OPTIONS.map(({ value, label }) => (
              <option key={value || "all"} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 w-full min-w-0 sm:min-w-[10rem] sm:flex-1 sm:max-w-[16rem]">
          <span className="text-xs font-semibold text-muted px-1">State</span>
          <select
            aria-label="Filter by state"
            value={activeState}
            disabled={isPending}
            onChange={(e) => updateFilter("state", e.target.value)}
            className={SELECT_CLASS}
          >
            <option value="">All states</option>
            {US_STATE_OPTIONS.map(({ name, code }) => (
              <option key={code} value={name}>
                {name} ({code})
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 w-full min-w-0 sm:min-w-[9rem] sm:flex-1 sm:max-w-[12rem]">
          <span className="text-xs font-semibold text-muted px-1">Chamber</span>
          <select
            aria-label="Filter by chamber"
            value={activeChamber}
            disabled={isPending}
            onChange={(e) => updateFilter("chamber", e.target.value)}
            className={SELECT_CLASS}
          >
            {CHAMBER_OPTIONS.map(({ value, label }) => (
              <option key={value || "all"} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <div className="flex w-full sm:w-auto items-end">
          <button
            type="button"
            onClick={clearFilters}
            disabled={isPending || !hasFilters}
            className="w-full sm:w-auto px-4 py-2.5 rounded-xl text-sm font-semibold text-blue border-2 border-blue/30 bg-blue/5 hover:bg-blue/10 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Clear filters
          </button>
        </div>
      </div>
      <p
        className="text-center text-sm text-muted mt-3 min-h-[1.25rem]"
        role="status"
        aria-live="polite"
      >
        {isPending ? "Updating results..." : ""}
      </p>
    </div>
  );
}
