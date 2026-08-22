import type { Metadata } from "next";
import Link from "next/link";
import { POLICY_DISTILLATIONS } from "@/lib/policy-distillations";

export const metadata: Metadata = {
  title: "Just the Facts",
  description:
    "Facts on tracked child safety legislation, with links to Congress.gov bill text and summaries.",
  openGraph: {
    title: "Just the Facts | Operation Child Shield",
    description:
      "Facts on tracked child safety bills with links to Congress.gov.",
  },
};

export default function TheFactsPage() {
  return (
    <div className="page-container py-8">
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted">
        <Link href="/" className="hover:text-blue">
          ← Back to lawmakers
        </Link>
        <Link href="/about" className="hover:text-blue">
          Our policy
        </Link>
        <Link href="/bills" className="hover:text-blue">
          The bills
        </Link>
      </div>

      <h1 className="text-3xl font-bold text-blue mt-4">Just the Facts</h1>
      <p className="mt-4 text-muted leading-relaxed max-w-3xl">
        Are current laws protecting children from exploitation and trafficking?
        These write-ups show what the bills we track actually do. Compare that
        with{" "}
        <Link href="/" className="text-red font-semibold hover:underline">
          how members voted or abstained
        </Link>{" "}
        and decide from the public record.
      </p>

      <nav aria-label="Fact topics" className="mt-8 flex flex-wrap gap-2">
        {POLICY_DISTILLATIONS.map((policy) => (
          <a
            key={policy.id}
            href={`#${policy.id}`}
            className="inline-flex rounded-full border border-card-border bg-surface px-3 py-1.5 text-xs font-semibold text-blue no-underline hover:border-blue/40"
          >
            {policy.title}
          </a>
        ))}
      </nav>

      <div className="mt-10 space-y-8">
        {POLICY_DISTILLATIONS.map((policy) => (
          <article
            key={policy.id}
            id={policy.id}
            className="scroll-mt-24 overflow-hidden rounded-[12px] border border-card-border bg-surface shadow-[0_8px_24px_-8px_rgb(0_0_0_/_0.12)]"
          >
            <header className="border-b border-card-border bg-surface-muted/80 px-5 py-4 sm:px-6">
              <p className="m-0 text-[0.7rem] font-bold uppercase tracking-[0.14em] text-red">
                {policy.category}
              </p>
              <h2 className="m-0 mt-1 text-xl font-bold text-blue sm:text-2xl">
                {policy.title}
              </h2>
              <p className="mt-1.5 mb-0 text-sm text-muted leading-snug">{policy.scope}</p>
              <a
                href={policy.overviewUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-block text-xs font-semibold text-red hover:underline"
              >
                Open the Bill →
              </a>
            </header>

            <ul className="m-0 list-none space-y-3 p-4 sm:p-5">
              {policy.bullets.map((bullet, index) => (
                <li key={bullet.sourceUrl + bullet.text.slice(0, 24)}>
                  <div className="flex gap-3 rounded-xl border border-blue/15 bg-blue/[0.04] px-4 py-4 sm:gap-4 sm:px-5 sm:py-5 dark:bg-blue/10">
                    <span
                      className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue text-sm font-bold text-white shadow-sm"
                      aria-hidden
                    >
                      {index + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="m-0 text-base font-medium leading-relaxed text-foreground sm:text-[1.05rem] sm:leading-relaxed">
                        {bullet.text}
                      </p>
                      <a
                        href={bullet.sourceUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-3 inline-flex items-center gap-1.5 rounded-md border border-red/25 bg-surface px-3 py-1.5 text-xs font-bold text-red no-underline shadow-sm transition-colors hover:border-red/50 hover:bg-red/5"
                      >
                        See the Source: {bullet.sourceLabel}
                        <span aria-hidden>→</span>
                      </a>
                    </div>
                  </div>
                </li>
              ))}
            </ul>

            {policy.relatedBills.length > 0 && (
              <footer className="border-t border-card-border bg-surface-muted/50 px-5 py-3 sm:px-6">
                <p className="m-0 text-[0.65rem] font-semibold uppercase tracking-wide text-muted">
                  Related bills
                </p>
                <ul className="mt-1.5 mb-0 flex flex-wrap gap-x-3 gap-y-1 list-none pl-0 text-xs">
                  {policy.relatedBills.map((bill) => (
                    <li key={bill.url}>
                      <a
                        href={bill.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-muted hover:text-blue hover:underline"
                      >
                        {bill.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </footer>
            )}
          </article>
        ))}
      </div>

      <p className="mt-12 text-sm text-muted">
        <Link href="/disclaimer" className="text-blue font-medium hover:underline">
          Legal disclaimer
        </Link>
      </p>
    </div>
  );
}
