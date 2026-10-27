import type { Metadata } from "next";
import Link from "next/link";
import { CompareTable } from "@/components/CompareTable";
import { getReportCards } from "@/lib/api";
import {
  buildCompareRows,
  MAX_COMPARE_IDS,
  MIN_COMPARE_IDS,
  parseCompareIds,
  toCompareMember,
} from "@/lib/compare";
import { friendlyErrorMessage } from "@/lib/errors";
import type { ReportCard } from "@/lib/types";

interface ComparePageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export const metadata: Metadata = {
  title: "Compare voting records",
  description:
    "Compare how up to four members of Congress voted on the same tracked child safety bills.",
  robots: { index: false, follow: true },
};

function InstructionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-8 rounded-[10px] border border-card-border bg-surface p-6 text-center shadow-sm">
      <h2 className="m-0 text-lg font-bold text-blue">{title}</h2>
      <div className="mt-2 text-sm leading-relaxed text-muted">{children}</div>
    </div>
  );
}

export default async function ComparePage({ searchParams }: ComparePageProps) {
  const params = await searchParams;
  const ids = parseCompareIds(params.ids);

  // Compare needs at least two distinct, well-formed bioguide ids.
  if (ids.length < MIN_COMPARE_IDS) {
    return (
      <div className="page-container py-8">
        <Link href="/" className="text-sm text-muted hover:text-blue">
          ← Back to lawmakers
        </Link>
        <h1 className="mt-4 text-3xl font-bold text-blue">Compare voting records</h1>
        <p className="mt-2 max-w-2xl text-muted leading-relaxed">
          Put two to four lawmakers side by side and see how each voted on the
          same tracked child safety bills.
        </p>
        <InstructionCard title="Pick at least two lawmakers">
          <p className="m-0">
            Open any member&apos;s record and choose{" "}
            <strong className="text-foreground">Compare this member</strong>, or add
            ids to the URL directly:{" "}
            <code className="rounded bg-surface-muted px-1.5 py-0.5 text-xs">
              /compare?ids=A000055,B000001
            </code>
          </p>
          <p className="mt-3">
            <Link href="/" className="font-semibold text-red hover:underline">
              Browse the directory →
            </Link>
          </p>
        </InstructionCard>
      </div>
    );
  }

  const results = await getReportCards(ids);
  const loaded = results.filter(
    (result): result is { id: string; card: ReportCard; error: null } =>
      result.card !== null
  );
  const failed = results.filter((r) => r.card === null);

  if (loaded.length === 0) {
    const anyNotFound = failed.some((r) => /API error 400|API error 404/.test(r.error ?? ""));
    return (
      <div className="page-container py-8">
        <Link href="/" className="text-sm text-muted hover:text-blue">
          ← Back to lawmakers
        </Link>
        <h1 className="mt-4 text-3xl font-bold text-blue">Compare voting records</h1>
        <InstructionCard
          title={anyNotFound ? "We couldn't find those members" : "Comparison unavailable"}
        >
          <p className="m-0">
            {anyNotFound
              ? "One or more member ids in this link are not valid. Member ids look like A000055."
              : friendlyErrorMessage(failed[0]?.error, "The voting records could not be loaded right now.")}
          </p>
          <p className="mt-3">
            <Link href="/" className="font-semibold text-red hover:underline">
              Search for a lawmaker →
            </Link>
          </p>
        </InstructionCard>
      </div>
    );
  }

  const members = loaded.map(({ id, card }) => toCompareMember(id, card));
  const rows = buildCompareRows(members);

  return (
    <div className="page-container min-w-0 py-8">
      <Link href="/" className="text-sm text-muted hover:text-blue">
        ← Back to lawmakers
      </Link>

      <h1 className="mt-4 text-3xl font-bold text-blue">Compare voting records</h1>
      <p className="mt-2 max-w-3xl text-muted leading-relaxed">
        Side-by-side votes on the same tracked child safety bills. Empty cells mean
        that member has no record on that bill.
      </p>

      {failed.length > 0 ? (
        <p
          className="mt-4 rounded-md border border-red/30 bg-red/5 px-4 py-3 text-sm text-red"
          role="status"
        >
          {failed.length} requested member{failed.length === 1 ? "" : "s"} could not be
          loaded and {failed.length === 1 ? "was" : "were"} left out of this comparison.
        </p>
      ) : null}

      <p className="mt-4 text-sm text-muted" aria-live="polite">
        Comparing {members.length} lawmaker{members.length === 1 ? "" : "s"} across{" "}
        {rows.length} tracked bill{rows.length === 1 ? "" : "s"}. Compare up to{" "}
        {MAX_COMPARE_IDS} at once.
      </p>

      {rows.length === 0 ? (
        <InstructionCard title="No shared votes yet">
          <p className="m-0">
            These members have no recorded roll-call votes on tracked bills, so
            there is nothing to compare. Senate records and bills decided by voice
            vote do not produce per-member votes.
          </p>
        </InstructionCard>
      ) : (
        <div className="mt-6">
          <CompareTable members={members} rows={rows} />
        </div>
      )}

      <div className="mt-6 flex flex-wrap gap-4">
        {members.map((member) => (
          <Link
            key={member.id}
            href={`/member/${member.id}`}
            className="text-sm font-semibold text-red hover:underline"
          >
            Open full record: {member.name.split(",")[0]} →
          </Link>
        ))}
      </div>
    </div>
  );
}
