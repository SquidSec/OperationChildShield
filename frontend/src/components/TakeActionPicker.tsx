"use client";

import Link from "next/link";
import { useCallback, useSyncExternalStore } from "react";
import { ROLES, getRole, roleDefaultId, type RoleId } from "@/lib/take-action";

const STORAGE_KEY = "ocs_action_role";

// The saved role is external state (localStorage), so it is read through
// useSyncExternalStore: the server and first client paint both use the default,
// then a stored choice is adopted without a hydration mismatch.
const _listeners = new Set<() => void>();

function subscribe(listener: () => void): () => void {
  _listeners.add(listener);
  return () => {
    _listeners.delete(listener);
  };
}

function readStoredRole(): RoleId {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved && getRole(saved)) return saved as RoleId;
  } catch {
    /* storage unavailable */
  }
  return roleDefaultId();
}

function writeStoredRole(id: RoleId): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, id);
  } catch {
    /* storage unavailable */
  }
  for (const listener of _listeners) listener();
}

function RoleGlyph({ kind }: { kind: string }) {
  const common = {
    "aria-hidden": true,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    className: "h-6 w-6",
  };
  switch (kind) {
    case "book":
      return (
        <svg {...common}>
          <path d="M4 5a2 2 0 0 1 2-2h5v18H6a2 2 0 0 1-2-2Z" />
          <path d="M20 5a2 2 0 0 0-2-2h-5v18h5a2 2 0 0 0 2-2Z" />
        </svg>
      );
    case "badge":
      return (
        <svg {...common}>
          <path d="M12 3 5 6v6c0 4 3 7 7 9 4-2 7-5 7-9V6Z" />
          <path d="m9 12 2 2 4-4" />
        </svg>
      );
    case "heart":
      return (
        <svg {...common}>
          <path d="M12 20s-7-4.5-7-9.5A4 4 0 0 1 12 7a4 4 0 0 1 7 3.5C19 15.5 12 20 12 20Z" />
        </svg>
      );
    case "child":
      return (
        <svg {...common}>
          <circle cx="12" cy="7" r="3" />
          <path d="M6 20v-2a6 6 0 0 1 12 0v2" />
        </svg>
      );
    case "spark":
      return (
        <svg {...common}>
          <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18" />
        </svg>
      );
    case "cross":
      return (
        <svg {...common}>
          <path d="M12 4v16M6 9h12" />
        </svg>
      );
    case "briefcase":
      return (
        <svg {...common}>
          <rect x="3" y="7" width="18" height="13" rx="2" />
          <path d="M9 7V5h6v2M3 12h18" />
        </svg>
      );
    case "hands":
      return (
        <svg {...common}>
          <path d="M7 12V6a2 2 0 1 1 4 0v6" />
          <path d="M11 12V5a2 2 0 1 1 4 0v7" />
          <path d="M15 12V7a2 2 0 1 1 4 0v8a6 6 0 0 1-6 6H9a6 6 0 0 1-6-6v-2" />
        </svg>
      );
    default:
      return (
        <svg {...common}>
          <path d="M12 3 4 6v6c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V6Z" />
        </svg>
      );
  }
}

export function TakeActionPicker() {
  const roleId = useSyncExternalStore(
    subscribe,
    readStoredRole,
    roleDefaultId
  );

  const choose = useCallback((id: RoleId) => {
    writeStoredRole(id);
  }, []);

  const role = getRole(roleId) ?? ROLES[0];

  return (
    <div>
      <p className="m-0 text-sm font-bold uppercase tracking-wider text-muted">
        Step 1 · Who are you?
      </p>
      <div
        className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3"
        role="group"
        aria-label="Choose your role"
      >
        {ROLES.map((option) => {
          const selected = option.id === role.id;
          return (
            <button
              key={option.id}
              type="button"
              aria-pressed={selected}
              onClick={() => choose(option.id)}
              className={`flex min-h-[5.5rem] flex-col items-start gap-2 rounded-[10px] border-2 p-3 text-left transition-colors ${
                selected
                  ? "border-red bg-red/5"
                  : "border-card-border bg-surface hover:border-blue/40 hover:bg-surface-muted"
              }`}
            >
              <span className={selected ? "text-red" : "text-blue"}>
                <RoleGlyph kind={option.icon} />
              </span>
              <span className="block text-sm font-bold leading-tight text-foreground">
                {option.label}
              </span>
              <span className="block text-[0.72rem] leading-tight text-muted">
                {option.tagline}
              </span>
            </button>
          );
        })}
      </div>

      <section
        className="mt-8"
        aria-live="polite"
        aria-labelledby="action-role-heading"
      >
        <p className="m-0 text-sm font-bold uppercase tracking-wider text-muted">
          Step 2 · What you can do
        </p>
        <h2
          id="action-role-heading"
          className="mt-2 mb-0 text-2xl font-bold text-blue sm:text-3xl"
        >
          {role.label}
        </h2>
        <p className="mt-3 max-w-3xl leading-relaxed text-muted">{role.intro}</p>

        <ol className="mt-6 list-none space-y-3 p-0">
          {role.steps.map((step, index) => (
            <li
              key={step.title}
              className="rounded-[10px] border border-card-border bg-surface p-4 shadow-sm sm:p-5"
            >
              <div className="flex items-start gap-3">
                <span
                  className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue text-sm font-bold text-white"
                  aria-hidden
                >
                  {index + 1}
                </span>
                <div className="min-w-0">
                  <h3 className="m-0 text-base font-bold text-foreground sm:text-lg">
                    {step.title}
                  </h3>
                  <p className="mt-1.5 mb-0 text-sm leading-relaxed text-muted sm:text-[0.95rem]">
                    {step.body}
                  </p>
                  {step.href ? (
                    step.external ? (
                      <a
                        href={step.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-2 inline-block text-sm font-bold text-red hover:underline"
                      >
                        {step.linkLabel} →
                      </a>
                    ) : (
                      <Link
                        href={step.href}
                        className="mt-2 inline-block text-sm font-bold text-red hover:underline"
                      >
                        {step.linkLabel} →
                      </Link>
                    )
                  ) : null}
                </div>
              </div>
            </li>
          ))}
        </ol>

        <div className="mt-4 rounded-[10px] border-l-4 border-red bg-red/5 px-4 py-3">
          <p className="m-0 text-sm leading-relaxed text-foreground">
            <strong className="font-bold">Stay in your lane. </strong>
            {role.guardrail}
          </p>
        </div>
      </section>
    </div>
  );
}
