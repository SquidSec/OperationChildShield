"use client";

import { useState } from "react";
import { trackAction } from "@/lib/api";
import {
  buildEmailShareUrl,
  buildFacebookShareUrl,
  buildLinkedInShareUrl,
  buildXShareUrl,
} from "@/lib/social";

interface ArticleShareLinksProps {
  title: string;
  url: string;
  dek?: string;
}

/**
 * Share row for a Daily Brief article. Uses plain share-intent links so it
 * works without the Web Share API, and falls back to clipboard copy on desktop.
 */
export function ArticleShareLinks({ title, url, dek = "" }: ArticleShareLinksProps) {
  const [copied, setCopied] = useState(false);

  const text = dek ? `${title}: ${dek}` : title;

  function markShare() {
    void trackAction("share", typeof window !== "undefined" ? window.location.pathname : "/");
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      markShare();
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  async function nativeShare() {
    try {
      await navigator.share({ title, text, url });
      markShare();
    } catch {
      /* user cancelled or unsupported */
    }
  }

  const itemClass =
    "inline-flex items-center justify-center gap-2 rounded-md border border-card-border bg-surface px-4 py-2.5 text-sm font-semibold text-blue no-underline transition-colors hover:bg-surface-muted";

  return (
    <div className="rounded-[10px] border border-card-border bg-surface p-4 shadow-sm">
      <p className="m-0 text-xs font-bold uppercase tracking-wider text-muted">
        Share this article
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => void nativeShare()}
          className="inline-flex items-center justify-center gap-2 rounded-md bg-red px-4 py-2.5 text-sm font-bold text-white transition-opacity hover:opacity-90"
        >
          Share
        </button>
        <a
          href={buildXShareUrl(text, url)}
          target="_blank"
          rel="noopener noreferrer"
          onClick={markShare}
          className={itemClass}
        >
          X
        </a>
        <a
          href={buildFacebookShareUrl(url)}
          target="_blank"
          rel="noopener noreferrer"
          onClick={markShare}
          className={itemClass}
        >
          Facebook
        </a>
        <a
          href={buildLinkedInShareUrl(url)}
          target="_blank"
          rel="noopener noreferrer"
          onClick={markShare}
          className={itemClass}
        >
          LinkedIn
        </a>
        <a
          href={buildEmailShareUrl(title, text, url)}
          onClick={markShare}
          className={itemClass}
        >
          Email
        </a>
        <button type="button" onClick={() => void copyLink()} className={itemClass}>
          {copied ? "Copied" : "Copy link"}
        </button>
      </div>
    </div>
  );
}
