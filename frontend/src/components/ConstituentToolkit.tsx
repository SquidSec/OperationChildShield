"use client";

import { useCallback, useState } from "react";
import {
  buildConstituentMailto,
  buildConstituentMessage,
} from "@/lib/congress-message";
import { trackAction } from "@/lib/api";

export function ConstituentToolkit({
  officialName,
  reportUrl,
  className = "",
}: {
  officialName?: string;
  reportUrl?: string;
  className?: string;
}) {
  const [feedback, setFeedback] = useState<string | null>(null);
  const message = buildConstituentMessage({ officialName, reportUrl });
  const mailto = buildConstituentMailto({ officialName, reportUrl });

  const markContact = useCallback(() => {
    const path =
      typeof window !== "undefined" ? window.location.pathname || "/" : "/";
    void trackAction("contact_congress", path);
  }, []);

  async function copyLetter() {
    try {
      await navigator.clipboard.writeText(message);
      markContact();
      setFeedback("Letter copied");
      window.setTimeout(() => setFeedback(null), 2000);
    } catch {
      setFeedback("Copy failed");
      window.setTimeout(() => setFeedback(null), 2000);
    }
  }

  return (
    <section
      className={`rounded-[10px] border border-card-border bg-surface p-6 shadow-sm ${className}`}
    >
      <h2 className="m-0 text-xl font-bold text-blue">Write Congress</h2>
      <p className="mt-2 mb-0 text-sm text-muted leading-relaxed">
        Copy this letter or open it in your email app. Paste it into your
        representative&apos;s official contact form, or send it from your own
        address.
      </p>
      <pre className="mt-4 mb-0 max-h-56 overflow-auto whitespace-pre-wrap rounded-lg border border-card-border bg-surface-muted p-4 text-sm leading-relaxed text-foreground">
        {message}
      </pre>
      <div className="mt-4 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => void copyLetter()}
          className="inline-flex items-center justify-center rounded-md bg-blue px-4 py-2.5 text-sm font-bold text-white hover:opacity-90"
        >
          {feedback ?? "Copy the letter"}
        </button>
        <a
          href={mailto}
          onClick={markContact}
          className="inline-flex items-center justify-center rounded-md border border-blue px-4 py-2.5 text-sm font-bold text-blue no-underline hover:bg-blue/5"
        >
          Open in email
        </a>
      </div>
    </section>
  );
}
