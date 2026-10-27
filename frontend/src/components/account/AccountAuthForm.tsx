"use client";

import { useCallback, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

type Mode = "login" | "register" | "forgot";

const inputClass =
  "mt-1 w-full rounded-lg border border-card-border bg-surface px-3 py-2 text-sm text-foreground outline-none focus:border-blue focus:ring-2 focus:ring-blue/20";

function post(path: string, body: unknown): Promise<Response> {
  return fetch(path, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function readDetail(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: string; message?: string };
    return body.detail ?? body.message ?? "Something went wrong. Please try again.";
  } catch {
    return "Something went wrong. Please try again.";
  }
}

export function AccountAuthForm({ initialMode = "login" }: { initialMode?: Mode }) {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>(initialMode);
  const [status, setStatus] = useState<"idle" | "submitting">("idle");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [devLink, setDevLink] = useState<string | null>(null);

  const switchMode = useCallback((next: Mode) => {
    setMode(next);
    setError(null);
    setNotice(null);
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    setStatus("submitting");
    const data = new FormData(event.currentTarget);

    try {
      if (mode === "register") {
        const res = await post("/api/account/register", {
          email: String(data.get("email") ?? ""),
          password: String(data.get("password") ?? ""),
          displayName: String(data.get("displayName") ?? ""),
          consent: data.get("consent") === "on",
        });
        if (!res.ok) {
          setError(await readDetail(res));
          return;
        }
        const body = (await res.json()) as { message?: string; devVerificationUrl?: string | null };
        setNotice(body.message ?? "Check your email to finish signing up.");
        // Local development only: the backend returns the link when no mail
        // server is wired up, so the flow can be tested end to end.
        if (body.devVerificationUrl) {
          setDevLink(body.devVerificationUrl);
        }
        return;
      }

      if (mode === "forgot") {
        const res = await post("/api/account/password/request", {
          email: String(data.get("email") ?? ""),
        });
        const body = await res.json().catch(() => ({}));
        if (!res.ok) {
          setError(await readDetail(res));
          return;
        }
        setNotice(body.message ?? "If that email has an account, a reset link is on its way.");
        return;
      }

      const res = await post("/api/account/login", {
        email: String(data.get("email") ?? ""),
        password: String(data.get("password") ?? ""),
      });
      if (!res.ok) {
        setError(await readDetail(res));
        return;
      }
      router.replace("/account");
      router.refresh();
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setStatus("idle");
    }
  }

  return (
    <div className="mt-6">
      <div role="tablist" aria-label="Account action" className="flex gap-2">
        {(
          [
            ["login", "Sign in"],
            ["register", "Create account"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={mode === value}
            onClick={() => switchMode(value)}
            className={
              mode === value
                ? "rounded-full bg-blue px-4 py-1.5 text-sm font-semibold text-white"
                : "rounded-full border border-card-border bg-surface px-4 py-1.5 text-sm font-semibold text-muted hover:text-blue"
            }
          >
            {label}
          </button>
        ))}
      </div>

      <form className="mt-5 space-y-4" onSubmit={onSubmit} noValidate>
        {mode === "register" && (
          <div>
            <label htmlFor="displayName" className="block text-xs font-semibold uppercase tracking-wide text-muted">
              Name (optional)
            </label>
            <input id="displayName" name="displayName" type="text" maxLength={120} className={inputClass} />
          </div>
        )}

        <div>
          <label htmlFor="account-email" className="block text-xs font-semibold uppercase tracking-wide text-muted">
            Email
          </label>
          <input
            id="account-email"
            name="email"
            type="email"
            autoComplete="email"
            required
            maxLength={254}
            className={inputClass}
          />
        </div>

        {mode !== "forgot" && (
          <div>
            <label htmlFor="account-password" className="block text-xs font-semibold uppercase tracking-wide text-muted">
              Password
            </label>
            <input
              id="account-password"
              name="password"
              type="password"
              autoComplete={mode === "register" ? "new-password" : "current-password"}
              required
              minLength={mode === "register" ? 15 : undefined}
              maxLength={1024}
              className={inputClass}
            />
            {mode === "register" && (
              <p className="mt-1 text-[11px] text-muted">At least 15 characters. A short phrase works well.</p>
            )}
          </div>
        )}

        {mode === "register" && (
          <label className="flex items-start gap-2 text-xs text-muted">
            <input type="checkbox" name="consent" className="mt-0.5" />
            <span>
              I agree to receive account emails. I can turn off alerts at any time.
            </span>
          </label>
        )}

        {error && (
          <p role="alert" className="rounded-lg border border-red/40 bg-red/5 p-3 text-sm text-red">
            {error}
          </p>
        )}
        {notice && (
          <p role="status" className="rounded-lg border border-blue/30 bg-blue/5 p-3 text-sm text-blue">
            {notice}
          </p>
        )}
        {devLink && (
          <p className="rounded-lg border border-card-border bg-surface-muted p-3 text-xs text-muted">
            Local development: no mail server is configured.{" "}
            <a href={devLink} className="font-semibold text-red hover:underline">
              Open the verification link
            </a>
            .
          </p>
        )}

        <button
          type="submit"
          disabled={status === "submitting"}
          className="w-full rounded-full bg-blue px-4 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {status === "submitting"
            ? "Working…"
            : mode === "register"
              ? "Create account"
              : mode === "forgot"
                ? "Send reset link"
                : "Sign in"}
        </button>
      </form>

      <div className="mt-4 flex flex-wrap gap-4 text-xs">
        {mode !== "forgot" && (
          <button type="button" onClick={() => switchMode("forgot")} className="text-muted hover:text-blue">
            Forgot your password?
          </button>
        )}
        {mode === "forgot" && (
          <button type="button" onClick={() => switchMode("login")} className="text-muted hover:text-blue">
            ← Back to sign in
          </button>
        )}
      </div>
    </div>
  );
}
