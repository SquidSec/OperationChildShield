import type { Metadata } from "next";
import { Suspense } from "react";
import { Inter, Roboto_Mono } from "next/font/google";
import { headers } from "next/headers";
import { Footer } from "@/components/Footer";
import { Header } from "@/components/Header";
import { NcmecReportBanner } from "@/components/NcmecReportBanner";
import { NonprofitBadge } from "@/components/NonprofitBadge";
import { VisitTracker } from "@/components/VisitTracker";
import { THEME_INIT_SCRIPT } from "@/lib/theme";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-inter",
});

const robotoMono = Roboto_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-roboto-mono",
});

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://operationchildshield.org";

const SITE_TITLE = "Operation Child Shield";
const SITE_DESCRIPTION =
  "Which child-protection bills are moving, how members voted or abstained, and how to press Congress. A 501(c)(3) public record from Congress.gov.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: `${SITE_TITLE} • Child Safety Voting Records`,
    template: `%s • ${SITE_TITLE}`,
  },
  description: SITE_DESCRIPTION,
  icons: {
    icon: "/images/ocs-v2-icon-inverted.png",
    apple: "/images/ocs-v2-icon-inverted.png",
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    siteName: SITE_TITLE,
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    images: [
      {
        url: "/images/ocs-v2.jpg",
        width: 1254,
        height: 1254,
        alt: "Operation Child Shield: protecting America's children through congressional accountability",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    images: ["/images/ocs-v2.jpg"],
  },
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Nonce from proxy.ts CSP; also forces dynamic rendering for per-request nonces
  const nonce = (await headers()).get("x-nonce") ?? undefined;

  return (
    <html
      lang="en"
      className={`${inter.variable} ${robotoMono.variable} h-full`}
      suppressHydrationWarning
    >
      <head>
        <script
          nonce={nonce}
          suppressHydrationWarning
          dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }}
        />
      </head>
      <body className="min-h-full flex flex-col antialiased bg-background text-foreground transition-colors duration-200">
        <NcmecReportBanner variant="banner" />
        <Header />
        <main className="flex-1">{children}</main>
        <Footer />
        <NonprofitBadge />
        <Suspense fallback={null}>
          <VisitTracker />
        </Suspense>
      </body>
    </html>
  );
}
