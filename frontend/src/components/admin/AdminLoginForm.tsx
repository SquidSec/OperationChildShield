"use client";

import { useCallback, useState } from "react";
import { PowCaptcha } from "@/components/PowCaptcha";

type Step = "credentials" | "otp" | "enrol";

const inputClass =
  "mt-1 w-full rounded-lg border border-card-border bg-surface px-3 py-2 text-sm text-foreground outline-none focus:border-blue focus:ring-2 focus:ring-blue/20";

export function AdminLoginForm() {
  const [captchaToken, setCaptchaToken] = useState("");
  const [status, setStatus] = useState<"idle" | "submitting">("idle");
  const [error, setError] = useState<string | null>(null);

  // OTP is mandatory, so every login proceeds in two steps.
  const [step, setStep] = useState<Step>("credentials");
  const [challenge, setChallenge] = useState("");
  const [otpauthUri, setOtpauthUri] = useState("");
  const [qrSvg, setQrSvg] = useState("");
  const [secret, setSecret] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);

  const onSubmitCredentials = useCallback(
    async (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      setError(null);

      if (!captchaToken) {
        setError("Wait for the bot check to finish, then continue.");
        return;
      }

      setStatus("submitting");
      const form = new FormData(event.currentTarget);
      try {
        const res = await fetch("/api/admin/login", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: String(form.get("email") ?? ""),
            password: String(form.get("password") ?? ""),
            captcha_token: captchaToken,
          }),
        });

        const body = (await res.json().catch(() => null)) as
          | {
              detail?: string;
              ok?: boolean;
              otpRequired?: boolean;
              otpEnrolmentRequired?: boolean;
              challenge?: string;
              otpauthUri?: string;
              secret?: string;
              qrSvg?: string;
            }
          | null;

        if (!res.ok) {
          const detail = body?.detail ?? "";
          if (res.status === 429) {
            setError(
              detail ||
                "Too many failed attempts. Wait a few minutes, or run scripts/seed_admin.py unlock EMAIL."
            );
          } else {
            setError(detail || "Sign in failed. Check your credentials and try again.");
          }
          // Captcha challenges are single-use; solve a fresh one.
          // A rejected attempt burns the challenge server-side; solve a fresh one.
          setCaptchaToken("");
          setStatus("idle");
          return;
        }

        // Password accepted. OTP is always required next.
        if (body?.challenge) {
          setChallenge(body.challenge);
          if (body.otpEnrolmentRequired) {
            setStep("enrol");
            setOtpauthUri(body.otpauthUri ?? "");
            setSecret(body.secret ?? "");
            setQrSvg(body.qrSvg ?? "");
          } else {
            setStep("otp");
          }
          setStatus("idle");
          return;
        }

        setError("Unexpected response from the server. Try again.");
        setStatus("idle");
      } catch {
        setError("Sign in failed. Check your connection and try again.");
        setStatus("idle");
      }
    },
    [captchaToken]
  );

  const onSubmitOtp = useCallback(
    async (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      setError(null);
      setStatus("submitting");
      const form = new FormData(event.currentTarget);

      try {
        const res = await fetch("/api/admin/otp/verify", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            challenge,
            code: String(form.get("otp_code") ?? ""),
          }),
        });

        const body = (await res.json().catch(() => null)) as
          | { detail?: string; recoveryCodes?: string[] | null }
          | null;

        if (!res.ok) {
          setError(body?.detail || "That code was not accepted. Try the next one.");
          setStatus("idle");
          return;
        }

        if (body?.recoveryCodes?.length) {
          // Show once, then continue. The codes are the only way back in if the
          // authenticator device is lost.
          setRecoveryCodes(body.recoveryCodes);
          setStatus("idle");
          setStep("otp");
          return;
        }

        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.assign("/admin");
      } catch {
        setError("Verification failed. Check your connection and try again.");
        setStatus("idle");
      }
    },
    [challenge]
  );

  if (recoveryCodes) {
    return (
      <div className="mt-8 space-y-4">
        <p role="status" className="rounded-lg border border-blue/30 bg-blue/5 p-3 text-sm text-blue">
          OTP is now enabled. Save these recovery codes somewhere safe. Each one
          works once, and they will not be shown again.
        </p>
        <ul className="grid grid-cols-2 gap-2 rounded-lg border border-card-border bg-surface-muted p-4 font-mono text-sm">
          {recoveryCodes.map((code) => (
            <li key={code}>{code}</li>
          ))}
        </ul>
        <a
          href="/admin"
          className="block w-full rounded-full bg-blue px-4 py-2.5 text-center text-sm font-semibold text-white no-underline hover:opacity-90"
        >
          Continue to the dashboard
        </a>
      </div>
    );
  }

  if (step === "otp" || step === "enrol") {
    return (
      <div className="mt-8 space-y-4">
        {step === "enrol" ? (
          <>
            <p className="rounded-lg border border-blue/30 bg-blue/5 p-3 text-sm text-blue">
              OTP is required for every admin account. Add this account to your
              authenticator app, then enter the 6-digit code it shows.
            </p>
            {qrSvg && (
              <div className="flex flex-col items-center gap-2 rounded-lg border border-card-border bg-surface p-4">
                <p className="m-0 text-xs font-semibold uppercase tracking-wide text-muted">
                  Scan with your authenticator app
                </p>
                {/* Geometry-only SVG generated server-side; no untrusted text. */}
                <div
                  className="rounded bg-white p-1"
                  aria-label="Authenticator setup QR code"
                  dangerouslySetInnerHTML={{ __html: qrSvg }}
                />
              </div>
            )}

            {otpauthUri && (
              <div className="rounded-lg border border-card-border bg-surface-muted p-3">
                <p className="m-0 text-xs font-semibold uppercase tracking-wide text-muted">
                  Setup link
                </p>
                <code className="mt-1 block break-all text-[11px] leading-relaxed text-foreground">
                  {otpauthUri}
                </code>
                {secret && (
                  <>
                    <p className="mt-3 mb-0 text-xs font-semibold uppercase tracking-wide text-muted">
                      Or enter this key manually
                    </p>
                    <code className="mt-1 block break-all font-mono text-sm tracking-wider text-foreground">
                      {secret}
                    </code>
                  </>
                )}
              </div>
            )}
          </>
        ) : (
          <p className="rounded-lg border border-card-border bg-surface p-3 text-sm text-muted">
            Enter the 6-digit code from your authenticator app, or a recovery code.
          </p>
        )}

        <form className="space-y-4" onSubmit={onSubmitOtp} noValidate>
          <div>
            <label htmlFor="admin-otp" className="block text-xs font-semibold uppercase tracking-wide text-muted">
              Authenticator code
            </label>
            <input
              id="admin-otp"
              name="otp_code"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={16}
              required
              autoFocus
              className={`${inputClass} font-mono tracking-widest`}
            />
          </div>

          {error && (
            <p role="alert" className="rounded-lg border border-red/40 bg-red/5 p-3 text-sm text-red">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={status === "submitting"}
            className="w-full rounded-full bg-blue px-4 py-2.5 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
          >
            {status === "submitting" ? "Verifying…" : "Verify and sign in"}
          </button>

          <button
            type="button"
            onClick={() => {
              setStep("credentials");
              setChallenge("");
              setError(null);
            }}
            className="w-full text-xs text-muted hover:text-blue"
          >
            ← Start over
          </button>
        </form>
      </div>
    );
  }

  return (
    <form className="mt-8 space-y-4" onSubmit={onSubmitCredentials} noValidate>
      <div>
        <label htmlFor="admin-email" className="block text-xs font-semibold uppercase tracking-wide text-muted">
          Email
        </label>
        <input
          id="admin-email"
          name="email"
          type="email"
          autoComplete="username"
          required
          maxLength={254}
          className={inputClass}
        />
      </div>

      <div>
        <label htmlFor="admin-password" className="block text-xs font-semibold uppercase tracking-wide text-muted">
          Password
        </label>
        <input
          id="admin-password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          maxLength={1024}
          className={inputClass}
        />
      </div>

      <PowCaptcha onToken={setCaptchaToken} />

      {error && (
        <p role="alert" className="rounded-lg border border-red/40 bg-red/5 p-3 text-sm text-red">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={status === "submitting" || !captchaToken}
        className="w-full rounded-full bg-blue px-4 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {status === "submitting" ? "Checking…" : !captchaToken ? "Waiting for bot check…" : "Continue"}
      </button>

      <p className="text-[11px] leading-relaxed text-muted">
        Protected by a proof-of-work bot check and a mandatory authenticator code. No
        registration is available; access is granted by an administrator.
      </p>
    </form>
  );
}
