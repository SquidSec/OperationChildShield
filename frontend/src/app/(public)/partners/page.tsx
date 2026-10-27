import Image from "next/image";
import Link from "next/link";
import { NcmecReportBanner } from "@/components/NcmecReportBanner";

const partners = [
  {
    name: "Countervail Intelligence",
    description:
      "Strategic intelligence and analysis supporting organizations that protect children and strengthen national security.",
    href: "https://countervailintelligence.com/",
    logo: "/partners/countervail.png",
    logoWidth: 320,
    logoHeight: 213,
  },
  {
    name: "SquidSec",
    description:
      "Cybersecurity and digital offense expertise helping organizations identify threats and defend against online exploitation.",
    href: "https://squidoffense.com/",
    logo: "/partners/squidoffense.png",
    logoWidth: 232,
    logoHeight: 280,
  },
];

export default function PartnersPage() {
  return (
    <div className="page-container py-10">
      <Link href="/" className="text-sm text-muted hover:text-blue">
        ← Back to lawmakers
      </Link>

      <h1 className="text-3xl font-bold text-blue mt-4">Who Stands With Us</h1>
      <p className="mt-3 text-muted leading-relaxed max-w-2xl">
        Operation Child Shield is proud to collaborate with organizations dedicated
        to protecting children and advancing transparency in public policy. We also
        surface public reporting resources such as NCMEC.
      </p>

      <div className="mt-8">
        <NcmecReportBanner variant="card" />
      </div>

      <div className="mt-10 grid gap-6">
        {partners.map((partner) => (
          <a
            key={partner.name}
            href={partner.href}
            target="_blank"
            rel="noopener noreferrer"
            className="group flex flex-col sm:flex-row items-center gap-6 bg-surface rounded-[10px] p-8 border border-card-border shadow-[0_6px_12px_-2px_rgb(0_0_0_/_0.1)] hover:-translate-y-1 hover:shadow-[0_20px_25px_-5px_rgb(0_0_0_/_0.15)] transition-all no-underline"
          >
            <div className="w-full sm:w-72 shrink-0 flex items-center justify-center bg-surface-muted rounded-lg p-6 border border-card-border">
              <Image
                src={partner.logo}
                alt={`${partner.name} logo`}
                width={partner.logoWidth}
                height={partner.logoHeight}
                className="object-contain max-h-32 w-auto"
                priority
              />
            </div>
            <div className="flex-1 text-center sm:text-left">
              <h2 className="text-xl font-bold text-blue m-0 group-hover:text-red transition-colors">
                {partner.name}
              </h2>
              <p className="mt-2 text-muted text-sm leading-relaxed m-0">
                {partner.description}
              </p>
              <span className="inline-block mt-4 text-sm font-bold text-red group-hover:underline">
                Visit Their Site →
              </span>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}