import type { Metadata } from "next";
import Link from "next/link";
import { ConstituentToolkit } from "@/components/ConstituentToolkit";
import { InvolveForm } from "@/components/InvolveForm";

export const metadata: Metadata = {
  title: "Join Us",
  description:
    "Volunteer, advocate, or partner with Operation Child Shield.",
  openGraph: {
    title: "Join Us | Operation Child Shield",
    description:
      "Write Congress, share voting records, and volunteer with Operation Child Shield.",
  },
};

export default function GetInvolvedPage() {
  return (
    <div className="page-container py-8">
      <Link href="/learn" className="text-sm text-muted hover:text-blue">
        ← How it works
      </Link>

      <h1 className="text-3xl font-bold text-blue mt-4">Your Move</h1>
      <p className="mt-4 text-muted leading-relaxed">
        Push policy toward stronger child safety and anti-exploitation protections:
        write Congress, share the public record, then tell us how you want to help.
        We store signups for follow-up and never sell your information.
      </p>
      <p className="mt-2 text-sm text-muted">
        Prefer email?{" "}
        <a
          href="mailto:Contact@OperationChildShield.com"
          className="text-red font-semibold hover:underline"
        >
          Contact@OperationChildShield.com
        </a>
      </p>

      <ol className="mt-6 space-y-2 text-sm text-muted leading-relaxed list-decimal pl-5">
        <li>
          <Link href="/" className="text-red font-semibold hover:underline">
            Find your lawmakers
          </Link>{" "}
          and read how they voted or abstained.
        </li>
        <li>Copy the letter below and send it through their official office.</li>
        <li>Share the voting record so neighbors can do the same.</li>
        <li>Sign up if you want to volunteer, advocate, or partner.</li>
      </ol>

      <ConstituentToolkit className="mt-8" />

      <div className="mt-8 relative">
        <InvolveForm />
      </div>
    </div>
  );
}
