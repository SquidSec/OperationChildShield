import type { Metadata } from "next";
import Link from "next/link";
import { NonprofitStatus } from "@/components/NonprofitStatus";

export const metadata: Metadata = {
  title: "How We Read the Votes",
  description:
    "How Operation Child Shield reports voting records and compares floor votes to board-adopted policy positions.",
};

export default function AboutPage() {
  return (
    <div className="page-container py-8">
      <Link href="/" className="text-sm text-muted hover:text-blue">
        ← Back to lawmakers
      </Link>

      <h1 className="text-3xl font-bold text-blue mt-4">
        How We Read the Votes
      </h1>
      <p className="mt-4 text-muted leading-relaxed">
        Operation Child Shield publishes a neutral child safety voting record for
        members of Congress. All vote data is sourced from the public{" "}
        <a
          href="https://api.congress.gov/"
          className="text-red font-semibold hover:underline"
          target="_blank"
          rel="noopener noreferrer"
        >
          Congress.gov API
        </a>
        .
      </p>

      <nav
        aria-label="On this page"
        className="mt-6 rounded-[10px] border border-card-border bg-surface-muted p-4 text-sm"
      >
        <p className="m-0 font-semibold text-foreground">On this page</p>
        <ul className="mt-2 mb-0 flex flex-wrap gap-x-4 gap-y-1 list-none pl-0">
          <li>
            <a href="#what-we-report" className="text-red hover:underline">
              What we report
            </a>
          </li>
          <li>
            <a href="#what-we-do-not-publish" className="text-red hover:underline">
              What we do not publish
            </a>
          </li>
          <li>
            <a href="#bill-selection" className="text-red hover:underline">
              Bill selection
            </a>
          </li>
          <li>
            <a href="#mission" className="text-red hover:underline">
              Mission
            </a>
          </li>
          <li>
            <a href="#tax-exempt" className="text-red hover:underline">
              Tax-exempt status
            </a>
          </li>
        </ul>
      </nav>

      <section
        className="mt-8 rounded-[10px] border border-card-border bg-surface p-6 shadow-sm"
        aria-label="The Facts"
      >
        <h2 className="m-0 text-xl font-bold text-blue">Just the Facts</h2>
        <p className="mt-3 mb-0 text-muted leading-relaxed">
          Short, clear write-ups of the bills we track, with links straight to
          Congress.gov.
        </p>
        <Link
          href="/the-facts"
          className="mt-4 inline-flex items-center justify-center rounded-md bg-blue px-4 py-2.5 text-sm font-bold text-white no-underline hover:opacity-90"
        >
          Get the Facts →
        </Link>
      </section>

      <section id="what-we-report" className="mt-10 scroll-mt-24">
        <h2 className="text-xl font-bold text-blue">What We Report</h2>
        <ul className="mt-4 space-y-3 text-muted leading-relaxed list-disc pl-5">
          <li>
            How each official voted on tracked child safety legislation, including
            bill title, vote cast, and date when available.
          </li>
          <li>
            Whether each recorded floor vote is consistent or not consistent with
            Operation Child Shield&apos;s board-adopted policy positions.
          </li>
          <li>
            Direct links to the official bill page and roll-call record on
            Congress.gov.
          </li>
        </ul>
      </section>

      <section id="what-we-do-not-publish" className="mt-10 scroll-mt-24">
        <h2 className="text-xl font-bold text-blue">What We Do Not Publish</h2>
        <ul className="mt-4 space-y-3 text-muted leading-relaxed list-disc pl-5">
          <li>Letter grades, star ratings, or percentage scores for officials.</li>
          <li>
            Rankings such as &quot;best,&quot; &quot;worst,&quot; or
            &quot;champion/failure&quot; labels.
          </li>
          <li>Editorial endorsements or opposition to any candidate or officeholder.</li>
          <li>Our IRS employer identification number.</li>
        </ul>
      </section>

      <section id="bill-selection" className="mt-10 scroll-mt-24">
        <h2 className="text-xl font-bold text-blue">Bill Selection</h2>
        <p className="mt-4 text-muted leading-relaxed">
          We track legislation on child sexual abuse, exploitation, online safety
          (EARN IT, KOSA), sex offender registration, and victim support. See the{" "}
          <Link href="/bills" className="text-red font-semibold hover:underline">
            tracked bills page
          </Link>{" "}
          for the full list, or{" "}
          <Link href="/the-facts" className="text-red font-semibold hover:underline">
            The Facts
          </Link>
          .
        </p>
      </section>

      <section
        id="mission"
        className="mt-10 scroll-mt-24 bg-surface rounded-[10px] p-6 border border-card-border shadow-sm"
      >
        <h2 className="text-xl font-bold text-blue">Our Mission</h2>
        <p className="mt-3 text-muted leading-relaxed">
          Children depend on adults to protect them. Operation Child Shield
          publishes a public record so anyone can see which child-protection bills
          are moving, how members voted or abstained, whether current law matches
          board-adopted policy, and how to press Congress for stronger
          anti-exploitation protections.
        </p>
      </section>

      <NonprofitStatus className="mt-10" />

      <p className="mt-10 text-sm text-muted">
        See our full{" "}
        <Link href="/disclaimer" className="text-blue font-medium hover:underline">
          legal disclaimer
        </Link>{" "}
        for data sourcing and contact information. For reporting suspected
        exploitation, use the{" "}
        <Link href="/partners" className="text-blue font-medium hover:underline">
          NCMEC CyberTipline resources
        </Link>
        .
      </p>
    </div>
  );
}
