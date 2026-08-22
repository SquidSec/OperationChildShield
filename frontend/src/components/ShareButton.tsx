"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { trackAction } from "@/lib/api";
import { buildSharePayload, type ShareReportInput } from "@/lib/share";
import {
  buildEmailShareUrl,
  buildFacebookShareUrl,
  buildLinkedInShareUrl,
  buildXShareUrl,
} from "@/lib/social";

interface ShareButtonProps extends ShareReportInput {
  className?: string;
  variant?: "card" | "report";
}

function ShareIcon() {
  return (
    <svg
      aria-hidden
      className="h-4 w-4 shrink-0"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7" />
      <path d="M12 3v12" />
      <path d="m7 8 5-5 5 5" />
    </svg>
  );
}

export function ShareButton({
  className = "",
  variant = "card",
  ...input
}: ShareButtonProps) {
  const [open, setOpen] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const payload = buildSharePayload(input);

  const markShare = useCallback(() => {
    const path =
      typeof window !== "undefined" ? window.location.pathname || "/" : "/";
    void trackAction("share", path);
  }, []);

  const showFeedback = useCallback((message: string) => {
    setFeedback(message);
    window.setTimeout(() => setFeedback(null), 2000);
  }, []);

  useEffect(() => {
    if (!open) return;

    function handlePointerDown(event: MouseEvent) {
      if (!menuRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [open]);

  async function copyToClipboard(value: string, successMessage: string) {
    try {
      await navigator.clipboard.writeText(value);
      markShare();
      showFeedback(successMessage);
      setOpen(false);
    } catch {
      showFeedback("Copy failed");
    }
  }

  async function nativeShare() {
    if (typeof navigator !== "undefined" && typeof navigator.share === "function") {
      try {
        await navigator.share(payload);
        markShare();
        setOpen(false);
        return;
      } catch {
        /* cancelled */
      }
    }
    await copyToClipboard(payload.text, "Message copied!");
  }

  const baseButtonClass =
    variant === "report"
      ? "inline-flex items-center justify-center gap-2 rounded-md border border-blue bg-surface px-4 py-2.5 text-sm font-bold text-blue transition-colors hover:bg-blue/5"
      : "inline-flex w-full items-center justify-center gap-2 rounded-md border border-card-border bg-surface px-4 py-3 text-sm font-bold text-blue transition-colors hover:bg-surface-muted";

  const itemClass =
    "block w-full px-4 py-2.5 text-left text-sm font-semibold text-foreground hover:bg-surface-muted border-t border-card-border first:border-t-0";

  return (
    <div ref={menuRef} className={`relative ${open ? "z-50" : "z-0"} ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className={baseButtonClass}
        aria-expanded={open}
        aria-haspopup="menu"
      >
        <ShareIcon />
        {feedback ?? "Share This Record"}
      </button>

      {open && (
        <div
          role="menu"
          className="absolute bottom-full left-0 right-0 z-50 mb-2 max-h-[min(24rem,70vh)] overflow-y-auto rounded-md border border-card-border bg-surface shadow-[0_10px_25px_-5px_rgb(0_0_0_/_0.15)]"
        >
          <button
            type="button"
            role="menuitem"
            onClick={() => void nativeShare()}
            className={itemClass}
          >
            Share from this device...
          </button>
          <a
            role="menuitem"
            href={buildXShareUrl(payload.text, payload.url)}
            target="_blank"
            rel="noopener noreferrer"
            className={`${itemClass} no-underline`}
            onClick={() => {
              markShare();
              setOpen(false);
            }}
          >
            Post on X
          </a>
          <a
            role="menuitem"
            href={buildFacebookShareUrl(payload.url)}
            target="_blank"
            rel="noopener noreferrer"
            className={`${itemClass} no-underline`}
            onClick={() => {
              markShare();
              setOpen(false);
            }}
          >
            Post on Facebook
          </a>
          <a
            role="menuitem"
            href={buildLinkedInShareUrl(payload.url)}
            target="_blank"
            rel="noopener noreferrer"
            className={`${itemClass} no-underline`}
            onClick={() => {
              markShare();
              setOpen(false);
            }}
          >
            Share on LinkedIn
          </a>
          <a
            role="menuitem"
            href={buildEmailShareUrl(payload.title, payload.text, payload.url)}
            className={`${itemClass} no-underline`}
            onClick={() => {
              markShare();
              setOpen(false);
            }}
          >
            Email this record
          </a>
          <button
            type="button"
            role="menuitem"
            onClick={() => copyToClipboard(payload.url, "Link copied!")}
            className={itemClass}
          >
            Copy the link
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => copyToClipboard(payload.text, "Message copied!")}
            className={itemClass}
          >
            Copy a ready-to-send message
          </button>
        </div>
      )}
    </div>
  );
}
