import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Disclaimer",
  description:
    "Legal disclaimer for Operation Child Shield: entertainment purposes, public data sources, and contact information.",
};

const CONTACT_EMAIL = "Contact@OperationChildShield.com";

export default function DisclaimerPage() {
  return (
    <div className="page-container py-8">
      <Link href="/" className="text-sm text-muted hover:text-blue">
        ← Back to lawmakers
      </Link>

      <h1 className="text-3xl font-bold text-blue mt-4">Disclaimer</h1>

      <section className="mt-8 space-y-6 text-muted leading-relaxed">
        <p>
          <strong className="text-foreground">Entertainment purposes.</strong>{" "}
          Operation Child Shield is provided for informational purposes only.
          Nothing on this site constitutes legal, political, or professional
          advice. Voting records and policy-consistency indicators are factual
          presentations of publicly available legislative data and should not be
          treated as official government records or endorsements of any candidate.
        </p>

        <p>
          <strong className="text-foreground">Public data sources.</strong> Member
          profiles, votes, and bill metadata are drawn from public data locations,
          including the{" "}
          <a
            href="https://api.congress.gov/"
            className="text-red font-semibold hover:underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            Congress.gov API
          </a>{" "}
          and related open government datasets. We organize that data and compare
          recorded votes to board-adopted policy positions. Always verify official
          records directly at{" "}
          <a
            href="https://www.congress.gov"
            className="text-red font-semibold hover:underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            Congress.gov
          </a>
          .
        </p>

        <p>
          <strong className="text-foreground">No government affiliation.</strong>{" "}
          Operation Child Shield is not affiliated with, endorsed by, or operated
          on behalf of the United States Government or any federal agency.
        </p>

        <p>
          <strong className="text-foreground">Accuracy.</strong> While we work to
          keep information current, congressional data can change, APIs may lag
          official publications, and errors may occur in processing or display. Use
          this site at your own discretion.
        </p>

        <p>
          <strong className="text-foreground">Site analytics.</strong> This site
          records first-party page-view events (path, referrer, and browser user
          agent) on our servers for operational metrics only. There is no public
          analytics dashboard and no third-party ad trackers. Data is rate-limited,
          stored with restricted file permissions, and is not sold. By using the
          site you acknowledge this limited technical logging.
        </p>
      </section>

      <p className="mt-10 text-sm text-muted">
        For legal name, mailing address, and 501(c)(3) status, see{" "}
        <Link href="/organization" className="text-blue font-medium hover:underline">
          The Organization
        </Link>
        .
      </p>

      <section className="mt-10 bg-surface rounded-[10px] p-6 border border-card-border shadow-sm">
        <h2 className="text-xl font-bold text-blue">Disputes &amp; Concerns</h2>
        <p className="mt-3 text-muted leading-relaxed">
          If you believe information on this site is incorrect, misleading, or
          raises a concern, please contact us. We review good-faith reports and
          will respond as promptly as practicable.
        </p>
        <p className="mt-4">
          <a
            href={`mailto:${CONTACT_EMAIL}`}
            className="inline-flex items-center gap-2 text-red font-semibold hover:underline"
          >
            {CONTACT_EMAIL}
          </a>
        </p>
      </section>
    </div>
  );
}