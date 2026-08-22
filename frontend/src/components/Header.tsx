import Image from "next/image";
import Link from "next/link";
import { ThemeToggle } from "@/components/ThemeToggle";
import { ENABLE_BOARD_PAGE } from "@/lib/feature-flags";

/** Ordered for engagement: explore data first, then act, then org/legal. */
const NAV_LINKS = [
  { href: "/", label: "Find Lawmakers" },
  { href: "/metrics", label: "See the Numbers" },
  { href: "/the-facts", label: "The Facts" },
  { href: "/bills", label: "The Bills" },
  { href: "/get-involved", label: "Join Us" },
  { href: "/learn", label: "How It Works" },
  { href: "/about", label: "Our Policy" },
  { href: "/organization", label: "The Organization" },
  { href: "/partners", label: "Our Allies" },
  ...(ENABLE_BOARD_PAGE ? [{ href: "/board", label: "Leadership" }] : []),
  { href: "/disclaimer", label: "Disclaimer" },
] as const;

export function Header() {
  return (
    <header className="hero-header relative">
      <div className="absolute top-4 right-4 z-[3]">
        <ThemeToggle />
      </div>
      <div className="relative z-[2] w-full max-w-[900px] px-4 py-6 sm:py-0">
        <Link href="/" className="block text-white no-underline hover:opacity-95 transition-opacity">
          <Image
            src="/images/ocs-v2-icon-inverted.png"
            alt=""
            width={775}
            height={690}
            priority
            aria-hidden
            className="mx-auto h-20 w-auto sm:h-28 object-contain drop-shadow-[0_4px_12px_rgba(0,0,0,0.5)]"
          />
          <h1 className="m-0 mt-2 sm:mt-3 [text-shadow:0_4px_12px_rgba(0,0,0,0.7)]">
            <span className="flex items-center justify-center gap-3 sm:gap-4">
              <span className="h-px w-10 sm:w-16 bg-white/50" aria-hidden />
              <span className="text-[#d02829] text-xs sm:text-base font-bold tracking-[0.25em] uppercase">
                Operation
              </span>
              <span className="h-px w-10 sm:w-16 bg-white/50" aria-hidden />
            </span>
            <span className="block mt-1 text-[2.25rem] leading-none sm:text-[3.75rem] font-bold tracking-tight uppercase">
              Child Shield
            </span>
          </h1>
          <div className="mt-3 sm:mt-4 flex flex-col items-center gap-2 max-w-md mx-auto [text-shadow:0_2px_8px_rgba(0,0,0,0.8)]">
            <span className="h-px w-full bg-white/40" aria-hidden />
            <p className="text-xs sm:text-sm font-semibold tracking-[0.12em] uppercase text-white/90 m-0">
              Protect | Educate | Mobilize
            </p>
          </div>
        </Link>
        <nav
          aria-label="Main navigation"
          className="mt-5 sm:mt-6 flex flex-wrap justify-center items-center gap-2 sm:gap-3"
        >
          {NAV_LINKS.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className="inline-flex h-10 w-[10.5rem] shrink-0 items-center justify-center rounded-full border border-white/25 bg-white/10 px-2 text-center text-sm font-semibold leading-tight text-white no-underline backdrop-blur-sm transition-colors hover:border-white/40 hover:bg-white/20"
            >
              {label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}