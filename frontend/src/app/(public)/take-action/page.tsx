import type { Metadata } from "next";
import Link from "next/link";
import { NcmecReportBanner } from "@/components/NcmecReportBanner";
import { TakeActionPicker } from "@/components/TakeActionPicker";
import { JsonLd } from "@/components/JsonLd";
import { siteUrl } from "@/lib/site";

export const metadata: Metadata = {
  title: "Take Action",
  description:
    "What you can do about child trafficking in the United States, based on who you are: a parent, teacher, law enforcement officer, clinician, young person, faith leader, employer, or volunteer.",
  openGraph: {
    title: "Take Action | Operation Child Shield",
    description:
      "Concrete, lawful steps you can take against child trafficking, matched to your role.",
    url: "/take-action",
  },
};

export default function TakeActionPage() {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "HowTo",
    name: "Take action against child trafficking",
    description:
      "Role-based guidance for parents, teachers, law enforcement, clinicians, young people, faith leaders, employers, and volunteers.",
    url: siteUrl("/take-action"),
  };

  return (
    <div className="page-container py-8">
      <JsonLd data={jsonLd} />

      <Link href="/" className="text-sm text-muted hover:text-blue">
        ← Back to lawmakers
      </Link>

      <h1 className="mt-4 mb-0 text-3xl font-bold text-blue sm:text-4xl">
        What can I actually do?
      </h1>
      <p className="mt-3 max-w-3xl leading-relaxed text-muted">
        Advice that ignores your situation is advice nobody follows. Pick the
        description closest to your life and get a short list of concrete, lawful
        steps — plus the limit of what your role should not attempt.
      </p>

      <div className="mt-8">
        <TakeActionPicker />
      </div>

      <div className="mt-10 grid gap-4 sm:grid-cols-2">
        <NcmecReportBanner variant="card" />
        <aside className="rounded-[10px] border border-card-border bg-surface p-6 shadow-sm">
          <p className="m-0 text-xs font-bold uppercase tracking-wider text-blue">
            Also worth your time
          </p>
          <h2 className="m-0 mt-2 text-xl font-bold text-blue">
            Read the record before you act
          </h2>
          <p className="mt-3 mb-0 text-sm leading-relaxed text-muted">
            Sharing is not action unless it is accurate. Every Daily Brief lists
            its sources, and every voting record links to Congress.gov.
          </p>
          <div className="mt-5 flex flex-col gap-2">
            <Link
              href="/news"
              className="inline-flex items-center justify-center rounded-md border border-blue bg-surface px-4 py-2.5 text-sm font-bold text-blue no-underline hover:bg-blue/5"
            >
              Read the Daily Brief →
            </Link>
            <Link
              href="/bills"
              className="inline-flex items-center justify-center rounded-md border border-card-border bg-surface px-4 py-2.5 text-sm font-bold text-blue no-underline hover:bg-surface-muted"
            >
              See the tracked bills →
            </Link>
            <Link
              href="/get-involved"
              className="inline-flex items-center justify-center rounded-md bg-red px-4 py-2.5 text-sm font-bold text-white no-underline hover:opacity-90"
            >
              Sign up to volunteer →
            </Link>
          </div>
        </aside>
      </div>
    </div>
  );
}
