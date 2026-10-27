import type { Metadata } from "next";

/**
 * Admin chrome: minimal, no public nav/footer, no visit tracking, and excluded
 * from indexing. Separate from the public layout so client navigation between
 * /admin and the public site swaps chrome correctly.
 */
export const metadata: Metadata = {
  robots: { index: false, follow: false, nocache: true },
};

export default function AdminLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return <main className="flex-1">{children}</main>;
}
