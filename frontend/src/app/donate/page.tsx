import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { DonationForm } from "@/components/DonationForm";
import { ENABLE_DONATE_PAGE } from "@/lib/feature-flags";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Fuel the Mission",
  description:
    "Support Operation Child Shield and keep child safety voting records public.",
};

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
        for tax-exempt status. Choose a suggested donation below to preview the
        experience. Payment processing is not yet connected.
      </p>

      <div className="mt-10">
        <DonationForm />
      </div>
    </div>
  );
}