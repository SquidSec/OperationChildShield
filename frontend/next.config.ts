import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // CSP nonces are applied in src/proxy.ts. Caddy sets HSTS/COOP/CORP/COEP.
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
    ];
  },
  async redirects() {
    return [
      { source: "/stats", destination: "/metrics", permanent: true },
      { source: "/ai-policy", destination: "/the-facts", permanent: true },
      { source: "/about/ai-policy", destination: "/the-facts", permanent: true },
      // Analytics UI removed; visits stay in server-side SQLite only
      { source: "/analytics", destination: "/", permanent: true },
    ];
  },
  async rewrites() {
    const apiBase =
      process.env.API_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      "http://localhost:8000";
    return [
      {
        // Session-bearing routes are proxied so their cookies stay first-party
        // in local dev (production Caddy routes /api/* to the backend already).
        source: "/api/admin/:path*",
        destination: `${apiBase}/api/admin/:path*`,
      },
      {
        source: "/api/account/:path*",
        destination: `${apiBase}/api/account/:path*`,
      },
      {
        source: "/api/alerts/:path*",
        destination: `${apiBase}/api/alerts/:path*`,
      },
      {
        source: "/api/board/:path*",
        destination: `${apiBase}/api/board/:path*`,
      },
      {
        // Proof-of-work challenges are issued from the login and application
        // pages, which are same-origin in the browser.
        source: "/api/captcha/:path*",
        destination: `${apiBase}/api/captcha/:path*`,
      },
    ];
  },
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "www.congress.gov",
        pathname: "/img/member/**",
      },
      {
        protocol: "https",
        hostname: "cdn.jsdelivr.net",
        pathname: "/gh/djaiss/mapsicon/**",
      },
    ],
  },
};

export default nextConfig;
