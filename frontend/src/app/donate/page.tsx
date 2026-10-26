import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { DonorboxEmbed } from "@/components/DonorboxEmbed";
import { ENABLE_DONATE_PAGE } from "@/lib/feature-flags";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Fuel the Mission",
  description:
    "Support Operation Child Shield and keep child safety voting records public.",
};

const IMPACT_ITEMS = [
  "Maintaining Congress.gov data pipelines and verification",
  "Expanding tracked child-protection legislation",
  "Building transparency tools for voters, journalists, and advocates",
  "Keeping the platform unbiased and publicly accessible",
] as const;

export default function DonatePage() {
  if (!ENABLE_DONATE_PAGE) notFound();

  return (
    <div className="page-container py-10">
      <Link href="/" className="text-sm text-muted hover:text-blue">
        ← Back to lawmakers
      </Link>

      <h1 className="text-3xl font-bold text-blue mt-4">Fuel the Mission</h1>
      <p className="mt-3 text-muted leading-relaxed max-w-2xl">
        Operation Child Shield is building a lasting public record of how Congress
        votes on child protection. See{" "}
        <Link href="/organization" className="text-red font-semibold hover:underline">
          the organization
        </Link>{" "}
        for tax-exempt status. Donations are processed securely by Donorbox.
      </p>

      <div className="mt-10 grid lg:grid-cols-[1.1fr_0.9fr] gap-8 items-start">
        <DonorboxEmbed />

        <div className="space-y-6">
          <section className="bg-surface rounded-[10px] p-6 border border-card-border shadow-sm">
            <h2 className="text-lg font-bold text-blue m-0">Why donate?</h2>
            <p className="mt-3 text-sm text-muted leading-relaxed m-0">
              Operation Child Shield turns public congressional voting data into
              actionable accountability tools. Your support helps us keep the platform
              independent, accurate, and free for the public.
            </p>
          </section>

          <section className="bg-surface rounded-[10px] p-6 border border-card-border shadow-sm">
            <h2 className="text-lg font-bold text-blue m-0">Where your gift goes</h2>
            <ul className="mt-4 space-y-3 text-sm text-muted leading-relaxed list-disc pl-5 m-0">
              {IMPACT_ITEMS.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>

          <section className="rounded-[10px] p-6 border border-blue/20 bg-blue/5">
            <p className="text-sm text-foreground leading-relaxed m-0">
              <strong className="text-blue">Tax &amp; receipt note:</strong> Operation
              Child Shield is a 501(c)(3) public charity. Donorbox emails the official
              receipt for each gift.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
