import type { Metadata } from "next";
import Link from "next/link";
import { headers, cookies } from "next/headers";
import { redirect } from "next/navigation";
import { AccountAuthForm } from "@/components/account/AccountAuthForm";
import { hasUserSessionCookie, getUserProfile, USER_SESSION_COOKIE } from "@/lib/user-api";

export const metadata: Metadata = {
  title: "Your account",
  description: "Save lawmakers and manage voting alerts from Operation Child Shield.",
  robots: { index: false, follow: false },
};

export const dynamic = "force-dynamic";

export default async function AccountPage() {
  const cookieStore = await cookies();
  if (cookieStore.get(USER_SESSION_COOKIE)?.value) {
    const cookieHeader = (await headers()).get("cookie") ?? "";
    if (hasUserSessionCookie(cookieHeader)) {
      const profile = await getUserProfile(cookieHeader);
      if (profile) redirect("/account/dashboard");
    }
  }

  return (
    <div className="page-container py-10">
      <div className="mx-auto max-w-md">
        <Link href="/" className="text-sm text-muted hover:text-blue">
          ← Back to lawmakers
        </Link>
        <h1 className="mt-4 text-3xl font-bold text-blue">Your account</h1>
        <p className="mt-3 text-sm leading-relaxed text-muted">
          Save the lawmakers you follow and get an email when they vote on
          tracked child-safety bills. No grading, no rankings — just the record.
        </p>
        <AccountAuthForm />
      </div>
    </div>
  );
}
