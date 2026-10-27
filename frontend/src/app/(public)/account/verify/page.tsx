import type { Metadata } from "next";
import Link from "next/link";
import { VerifyClient } from "@/components/account/VerifyClient";

export const metadata: Metadata = {
  title: "Confirm your account",
  robots: { index: false, follow: false },
};

export const dynamic = "force-dynamic";

export default async function VerifyPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>;
}) {
  const { token } = await searchParams;

  return (
    <div className="page-container py-12">
      <div className="mx-auto max-w-md">
        <h1 className="text-3xl font-bold text-blue">Confirm your account</h1>
        {token ? (
          <VerifyClient token={token} />
        ) : (
          <p className="mt-4 text-sm text-muted">
            This link is missing its token.{" "}
            <Link href="/account" className="text-red font-semibold hover:underline">
              Sign in
            </Link>{" "}
            to request a new email.
          </p>
        )}
      </div>
    </div>
  );
}
