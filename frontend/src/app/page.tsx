import { Suspense } from "react";
import { PolicyLegend } from "@/components/PolicyLegend";
import { MemberFiltersBar } from "@/components/MemberFiltersBar";
import { PoliticianGrid } from "@/components/PoliticianGrid";
import { SearchBar } from "@/components/SearchBar";
import {
  getMembers,
  LANDING_PAGE_SIZE,
  SEARCH_PAGE_SIZE,
  type MemberFilters,
} from "@/lib/api";

interface HomePageProps {
  searchParams: Promise<Record<string, string | undefined>>;
}

async function GridSection({
  filters,
  isSearch,
  partyFilter,
  stateFilter,
}: {
  filters: MemberFilters;
  isSearch: boolean;
  partyFilter?: string;
  stateFilter?: string;
}) {
  let members: Awaited<ReturnType<typeof getMembers>>["members"] = [];
  let total = 0;
  let error: string | null = null;

  try {
    const data = await getMembers(filters);
    members = data.members;
    total = data.total;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load members";
  }

  const enableInfiniteScroll = !isSearch;

  return (
    <PoliticianGrid
      members={members}
      total={total}
      isSearch={isSearch}
      partyFilter={partyFilter}
      stateFilter={stateFilter}
      error={error}
      infiniteScroll={enableInfiniteScroll}
      listFilters={
        enableInfiniteScroll
          ? {
              limit: LANDING_PAGE_SIZE,
              offset: 0,
              party: filters.party,
              state: filters.state,
              chamber: filters.chamber,
            }
          : undefined
      }
    />
  );
}

export default async function HomePage({ searchParams }: HomePageProps) {
  const params = await searchParams;
  const hasSearch = Boolean(params.search?.trim());
  const partyFilter = params.party?.trim() || undefined;
  const stateFilter = params.state?.trim() || undefined;

  const limit = hasSearch ? SEARCH_PAGE_SIZE : LANDING_PAGE_SIZE;

  const filters: MemberFilters = {
    search: params.search,
    chamber: params.chamber,
    state: params.state,
    party: params.party,
    limit,
    offset: 0,
  };

  return (
    <div className="page-container py-8 min-w-0">
      <Suspense
        fallback={
          <div className="h-[72px] max-w-[620px] mx-auto mb-10 bg-surface/50 rounded-xl animate-pulse" />
        }
      >
        <SearchBar />
      </Suspense>

      <p className="text-center text-muted text-sm mb-4 max-w-2xl mx-auto leading-relaxed px-1">
        Search the full <strong className="text-foreground">House and Senate</strong>{" "}
        directory. House records use roll-call votes on bills we track. Senate members
        are listed for reference when per-member floor votes are not available.
        Eligible members who sat out a vote appear as &quot;Not Voting.&quot;
      </p>

      <PolicyLegend className="mb-8" />

      <Suspense fallback={<div className="h-20 mb-8 bg-surface/50 rounded-xl animate-pulse" />}>
        <MemberFiltersBar />
      </Suspense>

      <Suspense
        fallback={
          <div className="grid w-full min-w-0 grid-cols-[repeat(auto-fill,minmax(min(100%,280px),1fr))] gap-4 sm:gap-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-[340px] bg-surface rounded-[10px] animate-pulse" />
            ))}
          </div>
        }
      >
        <GridSection
          filters={filters}
          isSearch={hasSearch}
          partyFilter={partyFilter}
          stateFilter={stateFilter}
        />
      </Suspense>
    </div>
  );
}