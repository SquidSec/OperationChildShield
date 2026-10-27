import type { Metadata } from "next";
import Link from "next/link";
import { ResetPasswordClient } from "@/components/account/ResetPasswordClient";

export const metadata: Metadata = {
  title: "Reset your password",
  robots: { index: false, follow: false },
};

export const dynamic = "force-dynamic";

export default async function ResetPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>;
}) {
  const { token } = await searchParams;

  return (
    <div className="page-container py-12">
      <div className="mx-auto max-w-md">
        <h1 className="text-3xl font-bold text-blue">Reset your password</h1>
        {token ? (
          <ResetPasswordClient token={token} />
        ) : (
          <p className="mt-4 text-sm text-muted">
            This link is missing its token.{" "}
            <Link href="/account" className="text-red font-semibold hover:underline">
              Request a new reset link
            </Link>
            .
          </p>
        )}
      </div>
    </div>
  );
}
