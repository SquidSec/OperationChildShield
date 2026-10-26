"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { PoliticianCard } from "@/components/PoliticianCard";
import {
  fetchMembersClient,
  LANDING_PAGE_SIZE,
  type MemberFilters,
} from "@/lib/api";
import type { MemberSummary } from "@/lib/types";

interface PoliticianGridProps {
  members: MemberSummary[];
  total?: number;
  isSearch?: boolean;
  partyFilter?: string;
  stateFilter?: string;
  error?: string | null;
  infiniteScroll?: boolean;
  listFilters?: MemberFilters;
}

function filterSummary(party?: string, state?: string): string | null {
  const parts: string[] = [];
  if (party) parts.push(party);
  if (state) parts.push(state);
  if (!parts.length) return null;
  return parts.join(" · ");
}

export function PoliticianGrid({
  members: initialMembers,
  total: initialTotal = 0,
  isSearch = false,
  partyFilter,
  stateFilter,
  error,
  infiniteScroll = false,
  listFilters,
}: PoliticianGridProps) {
  const activeFilterLabel = filterSummary(partyFilter, stateFilter);
  const [members, setMembers] = useState(initialMembers);
  const [total, setTotal] = useState(initialTotal);
  const [loadingMore, setLoadingMore] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);

  // Reset accumulated results when the server sends a new page of props.
  // Adjusting state during render is the documented alternative to an effect
  // and avoids the extra render pass an effect would add.
  const [syncedMembers, setSyncedMembers] = useState(initialMembers);
  if (initialMembers !== syncedMembers) {
    setSyncedMembers(initialMembers);
    setMembers(initialMembers);
    setTotal(initialTotal);
    setLoadError(null);
  }

  const hasMore = infiniteScroll && members.length < total;

  const loadMore = useCallback(async () => {
    if (!infiniteScroll || !listFilters || loadingMore || members.length >= total) {
      return;
    }

    setLoadingMore(true);
    setLoadError(null);

    try {
      const data = await fetchMembersClient({
        ...listFilters,
        limit: LANDING_PAGE_SIZE,
        offset: members.length,
      });

      setMembers((prev) => {
        const seen = new Set(prev.map((m) => m.bioguideId));
        const next = data.members.filter((m) => !seen.has(m.bioguideId));
        return [...prev, ...next];
      });
      setTotal(data.total);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Failed to load more members");
    } finally {
      setLoadingMore(false);
    }
  }, [infiniteScroll, listFilters, loadingMore, members.length, total]);

  useEffect(() => {
    if (!hasMore) return;

    const sentinel = sentinelRef.current;
    if (!sentinel) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          loadMore();
        }
      },
      { rootMargin: "240px", threshold: 0 }
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, loadMore]);

  if (error) {
    return (
      <div className="rounded-lg border border-red/30 bg-red/5 px-6 py-8 text-center max-w-xl mx-auto">
        <p className="text-red font-semibold">Unable to load congressional data</p>
        <p className="text-sm text-muted mt-2">{error}</p>
      </div>
    );
  }

  if (members.length === 0) {
    return (
      <p className="text-center text-muted py-12">
        {activeFilterLabel
          ? `No members match ${activeFilterLabel}. Try adjusting your filters.`
          : "No members match your search. Try a different name or state."}
      </p>
    );
  }

  return (
    <>
      {!isSearch && activeFilterLabel && (
        <p className="text-center text-muted text-sm mb-6">
          Showing {members.length}
          {total > members.length ? ` of ${total}` : ""} member
          {total === 1 ? "" : "s"} matching{" "}
          <strong className="text-foreground">{activeFilterLabel}</strong>
          {total > members.length ? ". Scroll down to load more." : "."}
        </p>
      )}
      {!isSearch && !activeFilterLabel && total > members.length && (
        <p className="text-center text-muted text-sm mb-6 px-2">
          Showing {members.length} of {total} members. Scroll down to load more.{" "}
          <strong className="text-foreground">Search by name or state</strong> to find
          a specific representative.
        </p>
      )}
      {isSearch && (
        <p className="text-center text-muted text-sm mb-6">
          {members.length === total
            ? `Found ${total} member${total === 1 ? "" : "s"} matching your search${activeFilterLabel ? ` (${activeFilterLabel})` : ""}.`
            : `Showing ${members.length} of ${total} matches${activeFilterLabel ? ` (${activeFilterLabel})` : ""}.`}
        </p>
      )}
      {/* min(100%, 280px) prevents horizontal overflow / card overlap on narrow phones */}
      <div className="grid w-full min-w-0 grid-cols-[repeat(auto-fill,minmax(min(100%,280px),1fr))] items-stretch gap-4 sm:gap-6">
        {members.map((member) => (
          <div key={member.bioguideId} className="flex h-full min-h-0 min-w-0">
            <PoliticianCard member={member} />
          </div>
        ))}
      </div>

      {hasMore && (
        <div ref={sentinelRef} className="py-10 text-center">
          <p className="text-sm text-muted">Scroll for more members</p>
        </div>
      )}

      {loadError && (
        <div className="text-center mt-4">
          <p className="text-sm text-red">{loadError}</p>
          <button
            type="button"
            onClick={loadMore}
            className="mt-2 text-sm font-semibold text-blue hover:underline"
          >
            Try again
          </button>
        </div>
      )}
    </>
  );
}