import type { Metadata } from "next";
import { headers } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";
import { AdminLoginForm } from "@/components/admin/AdminLoginForm";
import { getAdminConfig, getAdminMe, hasAdminSessionCookie } from "@/lib/admin-api";

export const metadata: Metadata = {
  title: "Admin sign in",
  robots: { index: false, follow: false, nocache: true },
};

export const dynamic = "force-dynamic";

export default async function AdminLoginPage() {
  const requestHeaders = await headers();
  const nonce = requestHeaders.get("x-nonce") ?? undefined;

  // Already signed in? Skip the form. Invalid cookies still render the form.
  const cookieHeader = requestHeaders.get("cookie") ?? "";
  if (hasAdminSessionCookie(cookieHeader)) {
    const user = await getAdminMe(cookieHeader);
    if (user) redirect("/admin");
  }

  const config = await getAdminConfig();

  return (
    <div className="min-h-screen w-full bg-surface-muted">
      <div className="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center px-4 py-12">
        <p className="m-0 text-xs font-semibold uppercase tracking-[0.2em] text-red">
          Operation Child Shield
        </p>
        <h1 className="mt-2 text-3xl font-bold text-blue">Admin sign in</h1>
        <p className="mt-3 text-sm leading-relaxed text-muted">
          This area is restricted to seeded staff accounts. Access and login
          attempts are rate-limited and logged.
        </p>

        <AdminLoginForm
          nonce={nonce}
          captchaRequired={config.captchaRequired}
          captchaSiteKey={config.captchaSiteKey}
        />

        <p className="mt-8 text-xs text-muted">
          Not staff? Return to the{" "}
          <Link href="/" className="text-red font-semibold hover:underline">
            public site
          </Link>
          .
        </p>
      </div>
    </div>
  );
}
