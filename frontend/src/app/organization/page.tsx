import type { Metadata } from "next";
import Link from "next/link";
import { NonprofitStatus } from "@/components/NonprofitStatus";
import { ENABLE_BOARD_PAGE } from "@/lib/feature-flags";
import { NONPROFIT } from "@/lib/nonprofit";

export const metadata: Metadata = {
  title: "The Organization",
  description:
    "Who Operation Child Shield is, our mission, and 501(c)(3) public-charity status.",
};

export default function OrganizationPage() {
  return (
    <div className="page-container py-8">
      <Link href="/" className="text-sm text-muted hover:text-blue">
        ← Back to lawmakers
      </Link>

      <h1 className="text-3xl font-bold text-blue mt-4">The Organization</h1>
      <p className="mt-4 text-muted leading-relaxed max-w-3xl">
        {NONPROFIT.legalName} is a public charity that publishes a neutral record of
        how Congress votes on child safety, anti-abuse, and anti-trafficking
        legislation. We do not rank members or endorse candidates.
      </p>

      <section className="mt-10">
        <h2 className="text-xl font-bold text-blue">What we do</h2>
        <ul className="mt-4 space-y-3 text-muted leading-relaxed list-disc pl-5">
          <li>
            Track bills that protect children from exploitation and trafficking.
          </li>
          <li>
            Show how elected officials voted or abstained on those bills.
          </li>
          <li>
            Compare recorded floor votes to board-adopted policy positions.
          </li>
          <li>
            Make it easy to write Congress and share the public record.
          </li>
        </ul>
      </section>

      <section className="mt-10 rounded-[10px] border border-card-border bg-surface p-6 shadow-sm">
        <h2 className="m-0 text-xl font-bold text-blue">Mission</h2>
        <p className="mt-3 mb-0 text-muted leading-relaxed">
          Children depend on adults to protect them. We give the public clear
          information about which child-protection bills are moving, how members
          voted or sat out, and how to press Congress for stronger
          anti-exploitation protections.
        </p>
      </section>

      <NonprofitStatus className="mt-10" />

      <div className="mt-10 grid gap-4 sm:grid-cols-2">
        {ENABLE_BOARD_PAGE ? (
          <Link
            href="/board"
            className="rounded-[10px] border border-card-border bg-surface px-5 py-4 font-bold text-blue no-underline hover:bg-surface-muted"
          >
            Leadership →
          </Link>
        ) : null}
        <Link
          href="/about"
          className="rounded-[10px] border border-card-border bg-surface px-5 py-4 font-bold text-blue no-underline hover:bg-surface-muted"
        >
          How we read the votes →
        </Link>
        <Link
          href="/get-involved"
          className="rounded-[10px] border border-card-border bg-blue px-5 py-4 font-bold text-white no-underline hover:opacity-95"
        >
          Join us →
        </Link>
        <a
          href="mailto:Contact@OperationChildShield.com"
          className="rounded-[10px] border border-card-border bg-surface px-5 py-4 font-bold text-blue no-underline hover:bg-surface-muted"
        >
          Contact@OperationChildShield.com
        </a>
      </div>
    </div>
  );
}
