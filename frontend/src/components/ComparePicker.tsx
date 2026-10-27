"use client";

import Link from "next/link";
import { useState } from "react";
import { MAX_COMPARE_IDS } from "@/lib/compare";

const ID_PATTERN = /^[A-Za-z][0-9]{5,7}$/;

interface ComparePickerProps {
  bioguideId: string;
  displayName: string;
}

/**
 * Lightweight "add another member" control for /compare. State lives here only
 * until the user leaves for the comparison URL; the URL is the source of truth.
 */
export function ComparePicker({ bioguideId, displayName }: ComparePickerProps) {
  const [ids, setIds] = useState<string[]>([bioguideId.toUpperCase()]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);

  const full = ids.length >= MAX_COMPARE_IDS;

  function addId() {
    const id = draft.trim().toUpperCase();
    if (!id) return;
    if (!ID_PATTERN.test(id)) {
      setError("Member ids look like A000055 (one letter and six digits).");
      return;
    }
    if (ids.includes(id)) {
      setError("That member is already in the comparison.");
      return;
    }
    if (full) {
      setError(`You can compare up to ${MAX_COMPARE_IDS} members at once.`);
      return;
    }
    setIds([...ids, id]);
    setDraft("");
    setError(null);
  }

  function removeId(id: string) {
    if (id === bioguideId.toUpperCase()) return;
    setIds(ids.filter((existing) => existing !== id));
    setError(null);
  }

  const compareHref = `/compare?ids=${ids.join(",")}`;

  return (
    <div className="rounded-[10px] border border-card-border bg-surface-muted p-4">
      <h2 className="m-0 text-base font-bold text-blue">Compare voting records</h2>
      <p className="mt-1 mb-0 text-sm leading-relaxed text-muted">
        Add up to {MAX_COMPARE_IDS - 1} more lawmakers to see how they voted on the
        same bills. Paste a member id from another record&apos;s Compare link.
      </p>

      <ul className="mt-3 flex flex-wrap gap-2 p-0" aria-label="Members in this comparison">
        {ids.map((id) => (
          <li
            key={id}
            className="flex items-center gap-1.5 rounded-full border border-card-border bg-surface py-1 pl-3 pr-1 text-xs font-semibold text-foreground"
          >
            {id === bioguideId.toUpperCase() ? displayName : id}
            {id !== bioguideId.toUpperCase() ? (
              <button
                type="button"
                onClick={() => removeId(id)}
                aria-label={`Remove ${id} from the comparison`}
                className="flex h-5 w-5 items-center justify-center rounded-full text-muted hover:bg-surface-muted hover:text-red"
              >
                ×
              </button>
            ) : null}
          </li>
        ))}
      </ul>

      <form
        className="mt-3 flex flex-col gap-2 sm:flex-row"
        onSubmit={(event) => {
          event.preventDefault();
          addId();
        }}
      >
        <label htmlFor="compare-member-id" className="sr-only">
          Add a member id to compare
        </label>
        <input
          id="compare-member-id"
          type="text"
          value={draft}
          onChange={(event) => {
            setDraft(event.target.value);
            if (error) setError(null);
          }}
          placeholder="Member id, e.g. B000001"
          disabled={full}
          className="w-full min-w-0 flex-1 rounded-md border border-card-border bg-surface px-3 py-2 text-sm text-foreground outline-none focus:border-blue disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={full || !draft.trim()}
          className="shrink-0 rounded-md border border-blue/30 bg-blue/5 px-3 py-2 text-sm font-semibold text-blue hover:bg-blue/10 disabled:opacity-60"
        >
          Add
        </button>
      </form>

      {error ? (
        <p className="mt-2 text-sm text-red" role="status">
          {error}
        </p>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <Link
          href={compareHref}
          className={`inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-bold no-underline transition-colors ${
            ids.length >= 2
              ? "bg-red text-white hover:bg-[#991b1b]"
              : "pointer-events-none bg-surface text-muted border border-card-border"
          }`}
          aria-disabled={ids.length < 2}
          tabIndex={ids.length < 2 ? -1 : undefined}
        >
          Compare {ids.length} member{ids.length === 1 ? "" : "s"}
        </Link>
        <Link href="/compare" className="text-sm font-semibold text-blue hover:underline">
          How comparing works →
        </Link>
      </div>
    </div>
  );
}
