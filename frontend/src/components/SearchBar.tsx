"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, useTransition } from "react";

export function SearchBar() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();
  const [search, setSearch] = useState(searchParams.get("search") || "");

  function handleSearch() {
    const params = new URLSearchParams(searchParams.toString());
    const term = search.trim();
    if (term) {
      params.set("search", term);
      // Search is global - drop dropdown filters so results aren't constrained.
      params.delete("party");
      params.delete("state");
    } else {
      params.delete("search");
    }
    params.delete("offset");

    startTransition(() => {
      const qs = params.toString();
      router.push(qs ? `/?${qs}` : "/");
    });
  }

  return (
    <div className="max-w-[620px] mx-auto mb-6">
      <div className="flex flex-col sm:flex-row shadow-[0_10px_15px_-3px_rgb(0_0_0_/_0.1)] border-2 sm:border-[3px] border-blue rounded-xl overflow-hidden bg-surface">
        <label htmlFor="member-search" className="sr-only">
          Search lawmakers by name, state, or city
        </label>
        <input
          id="member-search"
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          placeholder="Name, state, or city..."
          className="w-full px-4 py-3.5 sm:px-6 sm:py-4 border-none text-base sm:text-[1.1rem] outline-none bg-surface text-foreground placeholder:text-muted/80"
        />
        <button
          type="button"
          onClick={handleSearch}
          disabled={isPending}
          className="w-full sm:w-auto shrink-0 px-6 py-3.5 sm:px-10 bg-red text-white border-none border-t sm:border-t-0 sm:border-l border-blue/20 font-bold text-base sm:text-[1.1rem] cursor-pointer hover:bg-[#991b1b] transition-colors disabled:opacity-70"
        >
          {isPending ? "Searching..." : "Find Them"}
        </button>
      </div>
      <p className="mt-2 mb-0 text-center text-sm text-muted">
        <Link
          href={search.trim() ? `/search?q=${encodeURIComponent(search.trim())}` : "/search"}
          className="font-semibold text-red hover:underline"
        >
          Search bills and lawmakers →
        </Link>
      </p>
    </div>
  );
}
