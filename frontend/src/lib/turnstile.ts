export type TurnstileApi = {
  render: (
    container: HTMLElement,
    options: {
      sitekey: string;
      callback: (token: string) => void;
      "expired-callback"?: () => void;
      "error-callback"?: () => void;
      theme?: "light" | "dark" | "auto";
      // "always" forces a widget configured as invisible to draw its checkbox
      // box, so people can see that a check is required instead of a blank gap.
      appearance?: "always" | "execute" | "interaction-only";
      size?: "normal" | "compact" | "flexible";
    }
  ) => string;
  reset: (widgetId?: string) => void;
};

/**
 * Options shared by every captcha render call.
 *
 * `appearance: "always"` is the important one: without it an invisible-type
 * widget (and Cloudflare's "always passes" test key) renders nothing, which
 * looks like the captcha is missing even though a token is issued.
 */
export const TURNSTILE_RENDER_OPTIONS = {
  appearance: "always" as const,
  size: "normal" as const,
};

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

const TURNSTILE_SRC =
  "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

/**
 * Load Cloudflare Turnstile once per document.
 *
 * The script tag carries the request nonce because the CSP uses
 * `script-src 'nonce-…' 'strict-dynamic'`; without it the browser blocks the
 * widget. Every page that renders a captcha must therefore allow
 * challenges.cloudflare.com in script-src and frame-src (see src/proxy.ts).
 */
export function loadTurnstile(nonce?: string): Promise<TurnstileApi> {
  if (typeof window === "undefined") return Promise.reject(new Error("no window"));
  if (window.turnstile) return Promise.resolve(window.turnstile);

  return new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(
      `script[src^="https://challenges.cloudflare.com/turnstile"]`
    );
    const script = existing ?? document.createElement("script");
    script.src = TURNSTILE_SRC;
    script.async = true;
    script.defer = true;
    if (nonce) script.nonce = nonce;
    script.addEventListener("load", () => {
      if (window.turnstile) resolve(window.turnstile);
      else reject(new Error("Turnstile unavailable"));
    });
    script.addEventListener("error", () =>
      reject(new Error("Turnstile failed to load"))
    );
    if (!existing) document.head.appendChild(script);
  });
}
