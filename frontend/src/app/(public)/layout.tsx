import type { Metadata } from "next";
import { Suspense } from "react";
import { Footer } from "@/components/Footer";
import { Header } from "@/components/Header";
import { JsonLd } from "@/components/JsonLd";
import { NcmecReportBanner } from "@/components/NcmecReportBanner";
import { NonprofitBadge } from "@/components/NonprofitBadge";
import { VisitTracker } from "@/components/VisitTracker";
import { siteJsonLd } from "@/lib/structured-data";

export const metadata: Metadata = {
  robots: { index: true, follow: true },
};

/**
 * Public site chrome. Lives in a route group layout (not the root layout) so it
 * renders and unmounts correctly when the client navigates between /admin and
 * the public pages; a shared layout is preserved across such navigations.
 */
export default function PublicLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <>
      <JsonLd data={siteJsonLd()} />
      <NcmecReportBanner variant="banner" />
      <Header />
      <main id="main-content" className="flex-1">
        {children}
      </main>
      <Footer />
      <NonprofitBadge />
      <Suspense fallback={null}>
        <VisitTracker />
      </Suspense>
    </>
  );
}
