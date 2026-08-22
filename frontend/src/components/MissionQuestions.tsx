import Link from "next/link";

const QUESTIONS = [
  {
    href: "/bills",
    question:
      "Which bills protecting children from exploitation and trafficking are moving through Congress?",
    answer: "See tracked bills and what has a public roll-call vote.",
    cta: "The Bills",
  },
  {
    href: "/",
    question:
      "How have elected representatives voted, or abstained from voting, on child safety, anti-abuse, and anti-trafficking legislation?",
    answer: "Search the directory. Not voting is recorded as Not Voting.",
    cta: "Find Lawmakers",
  },
  {
    href: "/the-facts",
    question:
      "Are current laws protecting children from exploitation and trafficking?",
    answer: "Read the bills we track, then judge the public record yourself.",
    cta: "The Facts",
  },
  {
    href: "/get-involved",
    question:
      "What can I do to push policy toward stronger child safety and anti-exploitation protections?",
    answer: "Write Congress, share the record, and sign up to help.",
    cta: "Take Action",
  },
] as const;

export function MissionQuestions({ className = "" }: { className?: string }) {
  return (
    <section className={className} aria-label="What this site answers">
      <h2 className="m-0 text-center text-lg font-bold text-blue sm:text-xl">
        What this site answers
      </h2>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {QUESTIONS.map((item) => (
          <Link
            key={item.href + item.cta}
            href={item.href}
            className="rounded-[10px] border border-card-border bg-surface p-4 no-underline shadow-sm transition-colors hover:border-blue/40 hover:bg-surface-muted"
          >
            <p className="m-0 text-sm font-semibold leading-snug text-foreground">
              {item.question}
            </p>
            <p className="mt-2 mb-0 text-xs leading-relaxed text-muted">
              {item.answer}
            </p>
            <p className="mt-3 mb-0 text-xs font-bold text-red">{item.cta} →</p>
          </Link>
        ))}
      </div>
    </section>
  );
}
