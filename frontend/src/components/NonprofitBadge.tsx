import Image from "next/image";
import Link from "next/link";
import { NONPROFIT } from "@/lib/nonprofit";

/**
 * Trust badge for the 501(c)(3) status.
 *
 * Below 1460px the page container reaches within the badge's footprint, so a
 * fixed badge sits on top of cards, charts, and the footer. There it renders
 * in normal flow after the footer; only on wide screens does it float, where
 * the gutters keep it clear of content.
 */
export function NonprofitBadge() {
  return (
    <Link
      href="/organization#tax-exempt"
      aria-label={`${NONPROFIT.ircSection} nonprofit. View organization details.`}
      className="nonprofit-badge relative mx-auto mt-6 mb-8 flex w-fit max-w-[14rem] items-center gap-2.5 rounded-full border border-card-border bg-surface py-1.5 pr-3.5 pl-1.5 text-left shadow-[0_10px_28px_-8px_rgb(0_0_0_/_0.35)] no-underline transition-transform hover:-translate-y-0.5 hover:border-blue/40 print:hidden min-[1460px]:fixed min-[1460px]:bottom-6 min-[1460px]:right-6 min-[1460px]:mt-0 min-[1460px]:mb-0 min-[1460px]:z-40"
    >
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#0b1220]">
        <Image
          src="/images/ocs-v2-icon-inverted.png"
          alt=""
          width={36}
          height={32}
          className="h-8 w-8 object-contain"
        />
      </span>
      <span className="min-w-0">
        <span className="block text-[0.7rem] font-bold leading-tight tracking-wide text-blue">
          {NONPROFIT.ircSection}
        </span>
        <span className="block text-[0.62rem] font-semibold uppercase leading-tight tracking-wide text-muted">
          Nonprofit
        </span>
      </span>
    </Link>
  );
}
