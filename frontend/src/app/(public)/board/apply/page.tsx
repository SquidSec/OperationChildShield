import type { Metadata } from "next";
import Link from "next/link";
import { headers } from "next/headers";
import { BoardApplicationForm } from "@/components/board/BoardApplicationForm";
import { getAdminConfig } from "@/lib/admin-api";

export const metadata: Metadata = {
  title: "Vice President application",
  description:
    "Apply for the open Vice President seat on the Operation Child Shield board of directors.",
};

export const dynamic = "force-dynamic";

export default async function BoardApplyPage() {
  const nonce = (await headers()).get("x-nonce") ?? undefined;
  // Same Turnstile widget keys as the admin login; captcha is required.
  const config = await getAdminConfig();

  return (
    <div className="page-container py-10">
      <div className="mx-auto max-w-2xl">
        <Link href="/board" className="text-sm text-muted hover:text-blue">
          ← Back to leadership
        </Link>

        <p className="mt-4 text-xs font-bold uppercase tracking-wider text-red">
          Open seat
        </p>
        <h1 className="mt-1 text-3xl font-bold text-blue">
          Vice President, Board of Directors
        </h1>
        <p className="mt-3 text-muted leading-relaxed">
          Operation Child Shield is a 501(c)(3) public charity that publishes
          neutral congressional voting records on child-safety legislation. The
          Vice President serves as a founding voting member of the board and
          works alongside the President, Secretary, and Treasurer on governance,
          oversight, and organizational strategy.
        </p>

        <h2 className="mt-8 text-lg font-bold text-blue">What the role involves</h2>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-relaxed text-muted">
          <li>Voting member of the board, with fiduciary duties to the organization.</li>
          <li>Support the President in setting board agendas and priorities.</li>
          <li>Review and approve board-adopted policy positions on tracked bills.</li>
          <li>Help represent the organization to partners and the public.</li>
          <li>Roughly a few hours a month, with quarterly board meetings.</li>
        </ul>

        <h2 className="mt-8 text-lg font-bold text-blue">Apply</h2>
        <p className="mt-2 text-sm text-muted leading-relaxed">
          Tell us why you want the seat and what you would bring. We read every
          application. Fields marked with an asterisk are required.
        </p>

        <BoardApplicationForm
          nonce={nonce}
          captchaRequired={config.captchaRequired}
          captchaSiteKey={config.captchaSiteKey}
        />
      </div>
    </div>
  );
}
