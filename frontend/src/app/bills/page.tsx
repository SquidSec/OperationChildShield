import Link from "next/link";
import { getTrackedBills } from "@/lib/api";
import type { TrackedBill } from "@/lib/types";

export const dynamic = "force-dynamic";

/** Keep topic sections stable; matches backend CATEGORY_DISPLAY_ORDER. */
const CATEGORY_ORDER = [
  "Online Safety",
  "Victim Support & Justice",
  "Predator Accountability",
  "Sex Offender Registration",
  "Exploitation & Trafficking",
] as const;

function orderedCategories(categories: string[]): string[] {
  const rank = new Map(CATEGORY_ORDER.map((name, index) => [name, index]));
  return [...categories].sort((a, b) => {
    const aRank = rank.get(a as (typeof CATEGORY_ORDER)[number]) ?? 999;
    const bRank = rank.get(b as (typeof CATEGORY_ORDER)[number]) ?? 999;
    if (aRank !== bRank) return aRank - bRank;
    return a.localeCompare(b);
  });
}

const STATUS_SECTIONS: {
  key: string;
  title: string;
  description: string;
  match: (bill: TrackedBill) => boolean;
  badgeClass: string;
}[] = [
  {
    key: "scored",
    title: "Votes You Can Check",
    description:
      "These bills have recorded House roll-call votes. Open any lawmaker to see how they voted.",
    match: (b) => b.scorable,
    badgeClass: "bg-red/10 text-red",
  },
  {
    key: "floor",
    title: "Passed Without a Public Roll Call",
    description:
      "Advanced by voice vote or unanimous consent. Congress.gov does not list individual member votes for these.",
    match: (b) =>
      !b.scorable &&
      ["passed_house", "passed_senate", "passed_both"].includes(b.floorStatus),
    badgeClass: "bg-blue/10 text-blue",
  },
  {
    key: "introduced",
    title: "Still Moving Through Congress",
    description:
      "Major child-protection bills we are watching. No House roll-call vote yet.",
    match: (b) => b.floorStatus === "introduced",
    badgeClass: "bg-muted/10 text-muted",
  },
];

function BillCard({ bill, badgeClass }: { bill: TrackedBill; badgeClass: string }) {
  return (
    <div className="bg-surface rounded-[10px] p-5 shadow-[0_6px_12px_-2px_rgb(0_0_0_/_0.1)] border border-card-border hover:-translate-y-0.5 transition-transform">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-bold uppercase tracking-wider text-red">
          {bill.number}
        </span>
        <span className="text-xs text-muted">{bill.congress}th Congress</span>
        <span className={`text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full ${badgeClass}`}>
          {bill.scorable ? "Roll call" : bill.floorStatusLabel.split("(")[0].trim()}
        </span>
      </div>
      <h3 className="mt-2 font-bold text-foreground leading-snug">{bill.title}</h3>
      <p className="mt-1 text-xs text-muted">{bill.floorStatusLabel}</p>
      <p className="mt-2 text-sm text-muted leading-relaxed">{bill.description}</p>
      <a
        href={bill.congressUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-3 inline-block text-sm font-bold text-red hover:underline"
      >
        Read the Bill →
      </a>
    </div>
  );
}

export default async function BillsPage() {
  let bills: TrackedBill[] = [];
  let error: string | null = null;

  try {
    const data = await getTrackedBills();
    bills = data.bills;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load bills";
  }

  const scoredCount = bills.filter((b) => b.scorable).length;

  return (
    <div className="page-container py-8">
      <Link href="/" className="text-sm text-muted hover:text-blue">
        ← Back to lawmakers
      </Link>

      <h1 className="text-3xl font-bold text-blue mt-4">The Bills That Matter</h1>
      <p className="mt-2 text-muted max-w-3xl">
        Which bills protecting children from exploitation and trafficking are moving
        through Congress? {bills.length} bills monitored across the 117th-119th
        Congresses.{" "}
        <strong>{scoredCount} bills</strong> have recorded House roll-call votes on
        verified child-protection legislation. Bills passed by voice vote or in the
        Senate are tracked for context but do not produce per-member House vote records.
      </p>

      {error && (
        <div className="mt-6 rounded-lg border border-red/30 bg-red/5 px-6 py-4 text-sm text-red">
          {error}
        </div>
      )}

      {STATUS_SECTIONS.map((section) => {
        const sectionBills = bills.filter(section.match);
        if (sectionBills.length === 0) return null;

        const categories = orderedCategories([
          ...new Set(sectionBills.map((b) => b.category)),
        ]);

        return (
          <section key={section.key} className="mt-10">
            <h2 className="text-xl font-bold text-blue">{section.title}</h2>
            <p className="mt-1 text-sm text-muted max-w-3xl">{section.description}</p>

            {categories.map((category) => (
              <div key={category} className="mt-6">
                <h3 className="text-base font-bold text-foreground border-b border-card-border pb-2">
                  {category}
                </h3>
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  {sectionBills
                    .filter((b) => b.category === category)
                    .map((bill) => (
                      <BillCard
                        key={bill.id}
                        bill={bill}
                        badgeClass={section.badgeClass}
                      />
                    ))}
                </div>
              </div>
            ))}
          </section>
        );
      })}

      <p className="mt-12 text-sm text-muted max-w-3xl">
        Bill tracking is for entertainment purposes. Data is sourced from public
        records. See our{" "}
        <Link href="/disclaimer" className="text-blue font-medium hover:underline">
          legal disclaimer
        </Link>{" "}
        or email{" "}
        <a
          href="mailto:Contact@OperationChildShield.com"
          className="text-blue font-medium hover:underline"
        >
          Contact@OperationChildShield.com
        </a>{" "}
        with concerns.
      </p>
    </div>
  );
}