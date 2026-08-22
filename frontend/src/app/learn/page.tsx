import type { Metadata } from "next";
import Link from "next/link";
import { MissionQuestions } from "@/components/MissionQuestions";
import { NcmecReportBanner } from "@/components/NcmecReportBanner";

export const metadata: Metadata = {
  title: "How It Works",
  description:
    "How to read child safety voting records, find help resources, and take action with Operation Child Shield.",
  openGraph: {
    title: "How It Works | Operation Child Shield",
    description:
      "Find records, understand the bills, and take action with Operation Child Shield.",
  },
};

export default function LearnPage() {
  return (
    <div className="page-container py-8">
      <Link href="/" className="text-sm text-muted hover:text-blue">
        ← Back to lawmakers
      </Link>

      <h1 className="text-3xl font-bold text-blue mt-4">How It Works</h1>
      <p className="mt-4 text-muted leading-relaxed">
        Operation Child Shield exists to{" "}
        <strong className="text-foreground">protect, educate, and mobilize</strong>
        {" "}
        with voting records from Congress.gov compared to board-adopted policy
        positions. Use this page if you need clarity or want to act.
      </p>

      <MissionQuestions className="mt-8" />

      <div className="mt-8">
        <NcmecReportBanner variant="card" />
      </div>

      <section className="mt-10">
        <h2 className="text-xl font-bold text-blue">If you need help or information</h2>
        <ul className="mt-4 space-y-3 text-muted leading-relaxed list-disc pl-5">
          <li>
            <strong className="text-foreground">Report exploitation or a missing child:</strong>{" "}
            use the{" "}
            <a
              href="https://report.cybertip.org/"
              className="text-red font-semibold hover:underline"
              target="_blank"
              rel="noopener noreferrer"
            >
              NCMEC CyberTipline
            </a>{" "}
            or call 1-800-THE-LOST. OCS is not a crisis service.
          </li>
          <li>
            <strong className="text-foreground">Read a member&apos;s record:</strong>{" "}
            search the{" "}
            <Link href="/" className="text-red font-semibold hover:underline">
              directory
            </Link>{" "}
            or open any official&apos;s page for recorded floor votes on tracked child
            safety bills. Each vote shows Yes/No (or not voting) and whether it is
            consistent with OCS policy.
          </li>
          <li>
            <strong className="text-foreground">See the bills we track:</strong> the{" "}
            <Link href="/bills" className="text-red font-semibold hover:underline">
              tracked bills
            </Link>{" "}
            page lists legislation on exploitation, online safety, offender
            registration, and related topics.
          </li>
          <li>
            <strong className="text-foreground">Compare across Congress:</strong>{" "}
            <Link href="/metrics" className="text-red font-semibold hover:underline">
              metrics &amp; numbers
            </Link>{" "}
            show bill-level roll-call totals and state policy-consistency rates.
          </li>
          <li>
            <strong className="text-foreground">Partner resources:</strong> visit{" "}
            <Link href="/partners" className="text-red font-semibold hover:underline">
              our partners
            </Link>{" "}
            for organizations working on prevention, recovery, and advocacy.
          </li>
          <li>
            <strong className="text-foreground">Questions or corrections:</strong>{" "}
            email{" "}
            <a
              href="mailto:Contact@OperationChildShield.com"
              className="text-red font-semibold hover:underline"
            >
              Contact@OperationChildShield.com
            </a>
            .
          </li>
        </ul>
        <p className="mt-4 text-sm text-muted leading-relaxed rounded-[10px] border border-card-border bg-surface-muted p-4">
          If you or someone you know is in immediate danger, contact local emergency
          services. This site publishes legislative transparency data and is not a
          crisis hotline or legal service.
        </p>
      </section>

      <section className="mt-10">
        <h2 className="text-xl font-bold text-blue">How voting records work</h2>
        <ol className="mt-4 space-y-3 text-muted leading-relaxed list-decimal pl-5">
          <li>
            We track a curated list of child safety bills (see{" "}
            <Link href="/about" className="text-red font-semibold hover:underline">
              policy positions
            </Link>
            ).
          </li>
          <li>
            For House roll-call votes, we record how each member voted and whether
            that vote aligns with the board-adopted stance on that bill.
          </li>
          <li>
            Senate members appear in the directory; per-member Senate floor votes
            are limited by what Congress.gov provides today.
          </li>
        </ol>
      </section>

      <section className="mt-10">
        <h2 className="text-xl font-bold text-blue">If you want to get involved</h2>
        <ul className="mt-4 space-y-3 text-muted leading-relaxed list-disc pl-5">
          <li>
            <strong className="text-foreground">Know your state:</strong> open the{" "}
            <Link href="/metrics" className="text-red font-semibold hover:underline">
              state metrics
            </Link>{" "}
            and drill into your state&apos;s members.
          </li>
          <li>
            <strong className="text-foreground">Contact representatives:</strong> use
            member pages for Congress.gov profiles and, when available, office
            contact details. Share factual vote records rather than personal attacks.
          </li>
          <li>
            <strong className="text-foreground">Share the data:</strong> every member
            page has share options (X, Facebook, LinkedIn, email, copy link) so
            others can verify the same public record.
          </li>
          <li>
            <strong className="text-foreground">Volunteer or partner:</strong>{" "}
            <Link
              href="/get-involved"
              className="text-red font-semibold hover:underline"
            >
              sign up to get involved
            </Link>{" "}
            and tell us how you can help.
          </li>
        </ul>
      </section>

      <div className="mt-10 grid gap-4 sm:grid-cols-2">
        <Link
          href="/get-involved"
          className="rounded-[10px] border border-card-border bg-blue px-5 py-4 text-center font-bold text-white no-underline hover:opacity-95"
        >
          Join Us →
        </Link>
        <Link
          href="/metrics"
          className="rounded-[10px] border border-card-border bg-surface px-5 py-4 text-center font-bold text-blue no-underline hover:bg-surface-muted"
        >
          See the Numbers →
        </Link>
      </div>
    </div>
  );
}
