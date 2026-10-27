import type { Metadata } from "next";
import Link from "next/link";
import { CompactMemberCard } from "@/components/CompactMemberCard";
import { getMembers, getTrackedBills } from "@/lib/api";
import { friendlyErrorMessage } from "@/lib/errors";
import type { MemberSummary, TrackedBill } from "@/lib/types";

interface SearchPageProps {
  searchParams: Promise<Record<string, string | undefined>>;
}

export async function generateMetadata({
  searchParams,
}: SearchPageProps): Promise<Metadata> {
  const params = await searchParams;
  const query = params.q?.trim() ?? "";
  return {
    title: query ? `Search results for "${query}"` : "Search bills and lawmakers",
    description:
      "Search every tracked child safety bill and every member of Congress by name, state, bill number or topic.",
    robots: { index: false, follow: true },
  };
}

const SEARCH_MEMBER_LIMIT = 50;

function matchesBill(bill: TrackedBill, query: string): boolean {
  const haystack = [
    bill.number,
    bill.title,
    bill.category,
    bill.description,
    bill.floorStatusLabel,
  ]
    .join(" ")
    .toLowerCase();
  return query
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((term) => haystack.includes(term));
}

function ResultHeading({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <h2 id={id} className="m-0 text-xl font-bold text-blue">
      {children}
    </h2>
  );
}

export default async function SearchPage({ searchParams }: SearchPageProps) {
  const params = await searchParams;
  const query = params.q?.trim() ?? "";

  let members: MemberSummary[] = [];
  let membersError: string | null = null;
  let bills: TrackedBill[] = [];
  let billsError: string | null = null;

  if (query) {
    const [memberResult, billResult] = await Promise.allSettled([
      getMembers({ search: query, limit: SEARCH_MEMBER_LIMIT }),
      getTrackedBills(),
    ]);

    if (memberResult.status === "fulfilled") {
      members = memberResult.value.members;
    } else {
      membersError = friendlyErrorMessage(
        memberResult.reason,
        "We couldn't load lawmakers right now."
      );
    }

    if (billResult.status === "fulfilled") {
      bills = billResult.value.bills;
    } else {
      billsError = friendlyErrorMessage(
        billResult.reason,
        "We couldn't load the bill list right now."
      );
    }
  }

  const matchedBills = query ? bills.filter((bill) => matchesBill(bill, query)) : [];
  const total = members.length + matchedBills.length;

  return (
    <div className="page-container min-w-0 py-8">
      <Link href="/" className="text-sm text-muted hover:text-blue">
        ← Back to lawmakers
      </Link>

      <h1 className="mt-4 text-3xl font-bold text-blue">Search everything</h1>
      <p className="mt-2 max-w-2xl text-muted leading-relaxed">
        Look up lawmakers and tracked bills in one place. Search by name, state,
        bill number, or topic.
      </p>

      <search className="mt-6">
        <form action="/search" method="get" className="max-w-[620px]">
          <label htmlFor="site-search" className="sr-only">
            Search lawmakers and bills
          </label>
          <div className="flex flex-col overflow-hidden rounded-xl border-2 border-blue bg-surface shadow-[0_10px_15px_-3px_rgb(0_0_0_/_0.1)] sm:flex-row">
            <input
              id="site-search"
              type="search"
              name="q"
              defaultValue={query}
              placeholder="Name, state, bill number, or topic"
              className="w-full border-none bg-surface px-4 py-3.5 text-base text-foreground outline-none placeholder:text-muted/80 sm:px-6 sm:py-4"
            />
            <button
              type="submit"
              className="w-full shrink-0 border-none bg-red px-6 py-3.5 font-bold text-white transition-colors hover:bg-[#991b1b] sm:w-auto sm:px-10 sm:py-4"
            >
              Search
            </button>
          </div>
        </form>
      </search>

      <p className="mt-4 text-sm text-muted" aria-live="polite" role="status">
        {query
          ? total === 0
            ? `No results for "${query}".`
            : `${total} result${total === 1 ? "" : "s"} for "${query}": ${members.length} lawmaker${members.length === 1 ? "" : "s"} and ${matchedBills.length} bill${matchedBills.length === 1 ? "" : "s"}.`
          : "Enter a search term to begin."}
      </p>

      {query ? (
        <div className="mt-8 grid gap-10 lg:grid-cols-2">
          <section aria-labelledby="search-lawmakers">
            <div className="flex items-baseline justify-between gap-3">
              <ResultHeading id="search-lawmakers">Lawmakers</ResultHeading>
              <span className="text-sm text-muted">{members.length}</span>
            </div>

            {membersError ? (
              <p className="mt-3 rounded-md border border-red/30 bg-red/5 px-4 py-3 text-sm text-red">
                {membersError}
              </p>
            ) : members.length === 0 ? (
              <p className="mt-3 text-muted">
                No lawmakers match &quot;{query}&quot;. Try a full last name or a
                state like &quot;Ohio&quot;.
              </p>
            ) : (
              <ul className="mt-3 grid gap-3">
                {members.map((member) => (
                  <li key={member.bioguideId}>
                    <CompactMemberCard member={member} />
                  </li>
                ))}
              </ul>
            )}

            {members.length > 0 ? (
              <Link
                href={`/?search=${encodeURIComponent(query)}`}
                className="mt-3 inline-block text-sm font-semibold text-red hover:underline"
              >
                Open the full lawmaker directory →
              </Link>
            ) : null}
          </section>

          <section aria-labelledby="search-bills">
            <div className="flex items-baseline justify-between gap-3">
              <ResultHeading id="search-bills">Bills</ResultHeading>
              <span className="text-sm text-muted">{matchedBills.length}</span>
            </div>

            {billsError ? (
              <p className="mt-3 rounded-md border border-red/30 bg-red/5 px-4 py-3 text-sm text-red">
                {billsError}
              </p>
            ) : matchedBills.length === 0 ? (
              <p className="mt-3 text-muted">
                No tracked bills match &quot;{query}&quot;. Browse{" "}
                <Link href="/bills" className="font-semibold text-red hover:underline">
                  all tracked bills
                </Link>
                .
              </p>
            ) : (
              <ul className="mt-3 space-y-3">
                {matchedBills.map((bill) => (
                  <li
                    key={bill.id}
                    className="rounded-[10px] border border-card-border bg-surface p-4 shadow-sm"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-bold uppercase tracking-wider text-red">
                        {bill.number}
                      </span>
                      <span className="text-xs text-muted">{bill.category}</span>
                      {bill.scorable ? (
                        <span className="rounded-full bg-red/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-red">
                          Roll call
                        </span>
                      ) : null}
                    </div>
                    <h3 className="mt-2 text-base font-bold leading-snug text-foreground">
                      {bill.title}
                    </h3>
                    <p className="mt-1 text-sm leading-relaxed text-muted">
                      {bill.description}
                    </p>
                    <a
                      href={bill.congressUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-2 inline-block text-sm font-bold text-red hover:underline"
                    >
                      Read the bill on Congress.gov →
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      ) : null}

      {query && total === 0 && !membersError && !billsError ? (
        <div className="mt-8 rounded-[10px] border border-card-border bg-surface p-6 text-center shadow-sm">
          <p className="m-0 font-semibold text-foreground">
            Nothing matched &quot;{query}&quot;.
          </p>
          <p className="mt-2 text-sm text-muted">
            Check the spelling, search a state name, or browse the{" "}
            <Link href="/bills" className="font-semibold text-red hover:underline">
              tracked bills
            </Link>
            .
          </p>
        </div>
      ) : null}
    </div>
  );
}
