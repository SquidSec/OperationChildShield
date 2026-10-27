import { NextRequest, NextResponse } from "next/server";

/**
 * Strict CSP with per-request nonces (Next.js 16 proxy convention).
 * Avoids script-src 'unsafe-inline' / 'unsafe-eval' in production.
 * React style={{...}} props use style-src-attr (CSP3); style tags use nonces.
 */
function connectSrcDirective(isDev: boolean): string {
  // Browser fetches to a different port (e.g. :3010 page -> :8010 API) are
  // cross-origin. 'self' alone blocks them and the UI looks empty of vote data.
  const origins = new Set<string>(["'self'"]);
  for (const raw of [
    process.env.NEXT_PUBLIC_API_URL,
    process.env.API_URL,
    isDev ? "http://127.0.0.1:8010" : "",
    isDev ? "http://localhost:8010" : "",
    isDev ? "http://127.0.0.1:8000" : "",
    isDev ? "http://localhost:8000" : "",
  ]) {
    if (!raw) continue;
    try {
      origins.add(new URL(raw).origin);
    } catch {
      /* ignore invalid */
    }
  }
  return `connect-src ${[...origins].join(" ")}`;
}

export function proxy(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const isDev = process.env.NODE_ENV === "development";
  const pathname = request.nextUrl.pathname;

  // Admin pages are not public. Check for the session cookie here to avoid
  // rendering the dashboard shell; the page still validates it with the API.
  if (pathname.startsWith("/admin") && !pathname.startsWith("/admin/login")) {
    if (!request.cookies.get("ocs_admin_session")?.value) {
      const loginUrl = new URL("/admin/login", request.url);
      const response = NextResponse.redirect(loginUrl);
      response.headers.set("Cache-Control", "no-store");
      return response;
    }
  }

  // Donorbox's custom element injects its own <style> tags into shadow DOM and a
  // stylesheet from rsms.me. Injected styles cannot carry our nonce, so that route
  // drops the style nonce in favor of 'unsafe-inline'; every other route keeps it.
  const isDonate = request.nextUrl.pathname.startsWith("/donate");
  // The captcha is self-hosted proof of work: no third-party script, iframe, or
  // style origin is needed, so captcha routes keep the same strict policy.
  const styleSrc = isDonate
    ? "style-src 'self' 'unsafe-inline' https://rsms.me https://donorbox.org"
    : `style-src 'self' 'nonce-${nonce}'`;

  const csp = [
    "default-src 'self'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "object-src 'none'",
    // Local assets + congress.gov member photos; Donorbox renders its own images
    `img-src 'self' data: blob: https://www.congress.gov${isDonate ? " https://donorbox.org" : ""}`,
    `font-src 'self' data:${isDonate ? " https://rsms.me" : ""}`,
    styleSrc,
    "style-src-attr 'unsafe-inline'",
    // Nonce + strict-dynamic: no 'unsafe-inline'. Dev-only eval for React refresh.
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${isDev ? " 'unsafe-eval'" : ""}`,
    isDonate
      ? `${connectSrcDirective(isDev).replace("connect-src ", "connect-src https://donorbox.org ")}`
      : connectSrcDirective(isDev),
    // Donorbox opens Stripe / PayPal frames during checkout
    ...(isDonate
      ? ["frame-src https://donorbox.org https://js.stripe.com https://www.paypal.com"]
      : []),
    "upgrade-insecure-requests",
  ]
    .join("; ")
    .replace(/\s{2,}/g, " ")
    .trim();

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  // Next.js reads CSP from the request to auto-apply nonces to framework scripts
  requestHeaders.set("Content-Security-Policy", csp);

  const response = NextResponse.next({
    request: { headers: requestHeaders },
  });
  response.headers.set("Content-Security-Policy", csp);
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  if (pathname.startsWith("/admin")) {
    // Defense in depth alongside robots.ts and per-page metadata.
    response.headers.set("X-Robots-Tag", "noindex, nofollow, noarchive");
    response.headers.set("Cache-Control", "no-store");
  }
  response.headers.set(
    "Permissions-Policy",
    "camera=(), microphone=(), geolocation=()",
  );

  return response;
}

export const config = {
  matcher: [
    {
      source:
        "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|jfif|ico)$).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
