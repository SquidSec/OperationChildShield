"use client";

import { useState, type FormEvent } from "react";
import { submitInvolveSignup } from "@/lib/api";
import { US_STATE_OPTIONS } from "@/lib/states";

const INTEREST_OPTIONS = [
  { value: "", label: "Select an interest (optional)" },
  { value: "volunteer", label: "Volunteer" },
  { value: "advocacy", label: "Advocacy / contacting lawmakers" },
  { value: "media", label: "Media / press" },
  { value: "partner", label: "Partnership" },
  { value: "other", label: "Other" },
] as const;

export function InvolveForm() {
  const [status, setStatus] = useState<"idle" | "submitting" | "success" | "error">(
    "idle"
  );
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setStatus("submitting");

    const form = event.currentTarget;
    const data = new FormData(form);

    try {
      await submitInvolveSignup({
        name: String(data.get("name") ?? ""),
        email: String(data.get("email") ?? ""),
        state: String(data.get("state") ?? ""),
        interest: String(data.get("interest") ?? ""),
        message: String(data.get("message") ?? ""),
        consent: data.get("consent") === "on",
        website: String(data.get("website") ?? ""),
      });
      setStatus("success");
      form.reset();
    } catch (e) {
      setStatus("error");
      setError(e instanceof Error ? e.message : "Signup failed");
    }
  }

  if (status === "success") {
    return (
      <div
        className="rounded-[10px] border border-card-border bg-surface p-6 shadow-sm"
        role="status"
      >
        <h2 className="m-0 text-xl font-bold text-blue">Thank you</h2>
        <p className="mt-3 text-muted leading-relaxed">
          We received your signup. Someone from Operation Child Shield will follow
          up when there is a good fit for your interest. You can also reach us at{" "}
          <a
            href="mailto:Contact@OperationChildShield.org"
            className="text-red font-semibold hover:underline"
          >
            Contact@OperationChildShield.org
          </a>
          .
        </p>
        <button
          type="button"
          className="mt-4 text-sm font-semibold text-blue hover:underline"
          onClick={() => setStatus("idle")}
        >
          Submit another response
        </button>
      </div>
    );
  }

  const fieldClass =
    "w-full rounded-lg border border-card-border bg-surface px-3 py-2.5 text-sm text-foreground outline-none focus:border-blue";

  return (
    <form
      onSubmit={onSubmit}
      className="rounded-[10px] border border-card-border bg-surface p-6 shadow-sm space-y-4"
      noValidate
    >
      <div>
        <label htmlFor="involve-name" className="block text-sm font-semibold text-foreground">
          Name <span className="text-red">*</span>
        </label>
        <input
          id="involve-name"
          name="name"
          type="text"
          required
          maxLength={120}
          autoComplete="name"
          className={`mt-1 ${fieldClass}`}
        />
      </div>

      <div>
        <label htmlFor="involve-email" className="block text-sm font-semibold text-foreground">
          Email <span className="text-red">*</span>
        </label>
        <input
          id="involve-email"
          name="email"
          type="email"
          required
          maxLength={254}
          autoComplete="email"
          className={`mt-1 ${fieldClass}`}
        />
      </div>

      <div>
        <label htmlFor="involve-state" className="block text-sm font-semibold text-foreground">
          State
        </label>
        <select id="involve-state" name="state" className={`mt-1 ${fieldClass}`} defaultValue="">
          <option value="">Select state (optional)</option>
          {US_STATE_OPTIONS.map((s) => (
            <option key={s.code} value={s.name}>
              {s.name}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label
          htmlFor="involve-interest"
          className="block text-sm font-semibold text-foreground"
        >
          How do you want to get involved?
        </label>
        <select
          id="involve-interest"
          name="interest"
          className={`mt-1 ${fieldClass}`}
          defaultValue=""
        >
          {INTEREST_OPTIONS.map((opt) => (
            <option key={opt.value || "none"} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label
          htmlFor="involve-message"
          className="block text-sm font-semibold text-foreground"
        >
          Message
        </label>
        <textarea
          id="involve-message"
          name="message"
          rows={4}
          maxLength={2000}
          className={`mt-1 ${fieldClass}`}
          placeholder="Tell us a little about yourself or how you'd like to help."
        />
      </div>

      {/* Honeypot - hidden from users */}
      <div className="absolute -left-[9999px] h-0 w-0 overflow-hidden" aria-hidden>
        <label htmlFor="involve-website">Website</label>
        <input id="involve-website" name="website" type="text" tabIndex={-1} autoComplete="off" />
      </div>

      <label className="flex items-start gap-2 text-sm text-muted">
        <input
          type="checkbox"
          name="consent"
          required
          className="mt-1"
        />
        <span>
          I agree to be contacted by Operation Child Shield about volunteering or
          advocacy opportunities. See our{" "}
          <a href="/disclaimer" className="text-blue hover:underline">
            disclaimer
          </a>
          . <span className="text-red">*</span>
        </span>
      </label>

      {error && (
        <p className="m-0 text-sm text-red" role="alert">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={status === "submitting"}
        className="inline-flex items-center justify-center rounded-md bg-blue px-5 py-2.5 text-sm font-bold text-white transition-opacity hover:opacity-90 disabled:opacity-60"
      >
        {status === "submitting" ? "Sending..." : "Count Me In"}
      </button>
    </form>
  );
}
