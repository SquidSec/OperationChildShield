import Link from "next/link";
import { SocialLinks } from "@/components/SocialLinks";
import { ENABLE_BOARD_PAGE, ENABLE_DONATE_PAGE } from "@/lib/feature-flags";

export function Footer() {
  return (
    <footer className="site-footer bg-blue text-white text-center py-10 px-4 text-[0.95rem]">
      <p className="m-0">
        <strong>One Nation Under God • United in Defense of Our Children</strong>
      </p>
      <p className="mt-3 mb-0 opacity-85">
        Data from Congress.gov Public API • Transparency for We the People
      </p>
      <p className="mt-3 mb-0 text-sm opacity-85 flex flex-wrap justify-center gap-x-4 gap-y-1">
        <Link href="/" className="underline hover:opacity-100">
          Find Lawmakers
        </Link>
        <a href="/metrics" className="underline hover:opacity-100">
          See the Numbers
        </a>
        <a href="/the-facts" className="underline hover:opacity-100">
          The Facts
        </a>
        <a href="/bills" className="underline hover:opacity-100">
          The Bills
        </a>
        <a href="/get-involved" className="underline hover:opacity-100">
          Join Us
        </a>
        {ENABLE_DONATE_PAGE && (
          <a href="/donate" className="underline hover:opacity-100">
            Donate
          </a>
        )}
        <a href="/learn" className="underline hover:opacity-100">
          How It Works
        </a>
        <a href="/organization" className="underline hover:opacity-100">
          The Organization
        </a>
        <a href="/partners" className="underline hover:opacity-100">
          Our Allies
        </a>
        <a
          href="https://report.cybertip.org/"
          className="underline hover:opacity-100"
          target="_blank"
          rel="noopener noreferrer"
        >
          Report Abuse Now
        </a>
        {ENABLE_BOARD_PAGE && (
          <a href="/board" className="underline hover:opacity-100">
            Leadership
          </a>
        )}
        <a href="/disclaimer" className="underline hover:opacity-100">
          Disclaimer
        </a>
        {/* Staff-only entry point. The route itself redirects anonymous
            visitors to the sign-in form and is noindex. */}
        <a href="/admin/login" className="underline hover:opacity-100">
          Admin
        </a>
      </p>
      <SocialLinks variant="footer" className="mt-4 text-sm opacity-85" />
      <p className="mt-3 mb-0 text-xs opacity-70 max-w-xl mx-auto">
        501(c)(3) public charity.{" "}
        <a href="/organization" className="underline hover:opacity-100">
          About the organization
        </a>
        .
      </p>
      <p className="mt-3 mb-0 text-xs opacity-70 max-w-xl mx-auto">
        For entertainment purposes only. Data sourced from public records. Questions
        or disputes:{" "}
        <a
          href="mailto:Contact@OperationChildShield.org"
          className="underline hover:opacity-100"
        >
          Contact@OperationChildShield.org
        </a>
        .
      </p>
      <p className="mt-3 mb-0 text-xs opacity-70">
        Not affiliated with the U.S. Government. Always verify at{" "}
        <a
          href="https://www.congress.gov"
          className="underline hover:opacity-100"
          target="_blank"
          rel="noopener noreferrer"
        >
          Congress.gov
        </a>
        .
      </p>
    </footer>
  );
}
