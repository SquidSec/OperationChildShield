import { NONPROFIT, nonprofitStatusSummary } from "@/lib/nonprofit";

export function NonprofitStatus({
  compact = false,
  className = "",
}: {
  compact?: boolean;
  className?: string;
}) {
  if (compact) {
    return (
      <p className={className}>
        {nonprofitStatusSummary()} Mailing address: {NONPROFIT.mailingAddress}.
      </p>
    );
  }

  return (
    <section
      id="tax-exempt"
      className={`scroll-mt-24 rounded-[10px] border border-card-border bg-surface p-6 shadow-sm ${className}`}
    >
      <h2 className="m-0 text-xl font-bold text-blue">Tax-Exempt Status</h2>
      <p className="mt-3 mb-0 text-muted leading-relaxed">
        {NONPROFIT.legalName} is recognized by the IRS as a {NONPROFIT.ircSection}{" "}
        public charity under IRC Section {NONPROFIT.publicCharityStatus}. The
        exemption is effective {NONPROFIT.effectiveDateLabel}. Donors can deduct
        contributions under IRC Section 170 to the extent allowed by law.
      </p>
      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <dt className="font-semibold text-foreground">Legal name</dt>
          <dd className="mt-0.5 mb-0 text-muted">{NONPROFIT.legalName}</dd>
        </div>
        <div>
          <dt className="font-semibold text-foreground">Public charity</dt>
          <dd className="mt-0.5 mb-0 text-muted">
            IRC {NONPROFIT.publicCharityStatus}
          </dd>
        </div>
        <div>
          <dt className="font-semibold text-foreground">Effective</dt>
          <dd className="mt-0.5 mb-0 text-muted">{NONPROFIT.effectiveDateLabel}</dd>
        </div>
        <div>
          <dt className="font-semibold text-foreground">Mailing address</dt>
          <dd className="mt-0.5 mb-0 text-muted">
            {NONPROFIT.mailingAddressLines.map((line) => (
              <span key={line} className="block">
                {line}
              </span>
            ))}
          </dd>
        </div>
      </dl>
    </section>
  );
}
