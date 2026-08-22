import { getImpact } from "@/lib/api";

function formatCount(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

export async function ImpactStrip({ className = "" }: { className?: string }) {
  const impact = await getImpact();
  if (!impact) return null;

  const items = [
    { label: "Page views", value: impact.pageViews },
    { label: "Records shared", value: impact.shares },
    { label: "Congress contacts started", value: impact.congressContacts },
    { label: "People who signed up", value: impact.signups },
  ];

  return (
    <section
      className={`rounded-[10px] border border-card-border bg-surface p-5 shadow-sm ${className}`}
      aria-label="Is this site working"
    >
      <h2 className="m-0 text-lg font-bold text-blue">Is this working?</h2>
      <p className="mt-2 mb-0 text-sm text-muted leading-relaxed">
        We count when people read the record, share it, start a letter to Congress,
        or sign up. That is how we tell whether the site is turning information
        into action.
      </p>
      <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {items.map((item) => (
          <div
            key={item.label}
            className="rounded-lg border border-card-border bg-surface-muted px-3 py-3 text-center"
          >
            <dd className="m-0 text-2xl font-bold text-blue">
              {formatCount(item.value)}
            </dd>
            <dt className="mt-1 text-[0.7rem] font-semibold uppercase tracking-wide text-muted">
              {item.label}
            </dt>
          </div>
        ))}
      </dl>
    </section>
  );
}
