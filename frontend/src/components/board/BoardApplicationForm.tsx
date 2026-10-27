"use client";

import { useState, type FormEvent } from "react";
import { PowCaptcha } from "@/components/PowCaptcha";

const inputClass =
  "mt-1 w-full rounded-lg border border-card-border bg-surface px-3 py-2 text-sm text-foreground outline-none focus:border-blue focus:ring-2 focus:ring-blue/20";

export function BoardApplicationForm() {
  const [captchaToken, setCaptchaToken] = useState("");
  const [status, setStatus] = useState<"idle" | "submitting" | "done">("idle");
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!captchaToken) {
      setError("Wait for the bot check to finish, then submit again.");
      return;
    }

    setStatus("submitting");
    const data = new FormData(event.currentTarget);

    try {
      const res = await fetch("/api/board/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          role: "vice-president",
          name: String(data.get("name") ?? ""),
          email: String(data.get("email") ?? ""),
          phone: String(data.get("phone") ?? ""),
          location: String(data.get("location") ?? ""),
          linkedin: String(data.get("linkedin") ?? ""),
          statement: String(data.get("statement") ?? ""),
          consent: data.get("consent") === "on",
          captcha_token: captchaToken,
          website: String(data.get("website") ?? ""),
        }),
      });

      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as { detail?: string } | null;
        setError(body?.detail ?? "We could not submit your application. Please try again.");
        // A failed submit burns the challenge server-side; solve a new one.
        setCaptchaToken("");
        setStatus("idle");
        return;
      }

      setStatus("done");
    } catch {
      setError("Network error. Please try again.");
      setStatus("idle");
    }
  }

  if (status === "done") {
    return (
      <p
        role="status"
        className="mt-6 rounded-lg border border-blue/30 bg-blue/5 p-4 text-sm text-blue"
      >
        Thank you. Your application was received. We will follow up by email.
      </p>
    );
  }

  return (
    <form className="mt-6 space-y-4" onSubmit={onSubmit} noValidate>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="apply-name" className="block text-xs font-semibold uppercase tracking-wide text-muted">
            Full name *
          </label>
          <input id="apply-name" name="name" type="text" required maxLength={120} autoComplete="name" className={inputClass} />
        </div>
        <div>
          <label htmlFor="apply-email" className="block text-xs font-semibold uppercase tracking-wide text-muted">
            Email *
          </label>
          <input id="apply-email" name="email" type="email" required maxLength={254} autoComplete="email" className={inputClass} />
        </div>
        <div>
          <label htmlFor="apply-phone" className="block text-xs font-semibold uppercase tracking-wide text-muted">
            Phone
          </label>
          <input id="apply-phone" name="phone" type="tel" maxLength={40} autoComplete="tel" className={inputClass} />
        </div>
        <div>
          <label htmlFor="apply-location" className="block text-xs font-semibold uppercase tracking-wide text-muted">
            City and state
          </label>
          <input id="apply-location" name="location" type="text" maxLength={120} autoComplete="address-level2" className={inputClass} />
        </div>
      </div>

      <div>
        <label htmlFor="apply-linkedin" className="block text-xs font-semibold uppercase tracking-wide text-muted">
          LinkedIn or website
        </label>
        <input id="apply-linkedin" name="linkedin" type="text" maxLength={200} className={inputClass} />
      </div>

      <div>
        <label htmlFor="apply-statement" className="block text-xs font-semibold uppercase tracking-wide text-muted">
          Why you want this seat *
        </label>
        <textarea
          id="apply-statement"
          name="statement"
          required
          maxLength={4000}
          rows={6}
          className={inputClass}
          placeholder="Your relevant experience, why child-safety transparency matters to you, and what you would bring to the board."
        />
      </div>

      {/* Honeypot: hidden from people, tempting to bots. */}
      <div className="hidden" aria-hidden>
        <label htmlFor="apply-website">Website</label>
        <input id="apply-website" name="website" type="text" tabIndex={-1} autoComplete="off" />
      </div>

      <label className="flex items-start gap-2 text-xs text-muted">
        <input type="checkbox" name="consent" className="mt-0.5" required />
        <span>I agree to be contacted about this application. *</span>
      </label>

      <PowCaptcha onToken={setCaptchaToken} />

      {error && (
        <p role="alert" className="rounded-lg border border-red/40 bg-red/5 p-3 text-sm text-red">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={status === "submitting" || !captchaToken}
        className="w-full rounded-full bg-blue px-4 py-2.5 text-sm font-semibold text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto sm:px-8"
      >
        {status === "submitting"
          ? "Submitting…"
          : !captchaToken
            ? "Waiting for bot check…"
            : "Submit application"}
      </button>

      <p className="text-[11px] leading-relaxed text-muted">
        Protected by a self-hosted proof-of-work check. We use your details only to review this
        application.
      </p>
    </form>
  );
}
