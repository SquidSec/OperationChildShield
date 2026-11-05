import type { Metadata } from "next";
import Link from "next/link";
import { JsonLd } from "@/components/JsonLd";
import {
  NEWS_PAGE_SIZE,
  categoryLabel,
  formatNewsDate,
  getNewsFeed,
  type NewsArticleSummary,
} from "@/lib/newswire";
import { siteUrl } from "@/lib/site";

export const metadata: Metadata = {
  title: "The Daily Brief",
  description:
    "Original daily reporting on child trafficking and child exploitation in the United States: law enforcement action, legislation, policy, and community response.",
  openGraph: {
    title: "The Daily Brief | Operation Child Shield",
    description:
      "Original daily reporting on child trafficking and exploitation in the United States.",
    url: "/news",
  },
};

export const dynamic = "force-dynamic";

function ArticleCard({ article }: { article: NewsArticleSummary }) {
  return (
    <article className="flex h-full flex-col rounded-[10px] border border-card-border bg-surface p-5 shadow-sm transition-shadow hover:shadow-md">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-blue/10 px-2.5 py-1 text-[0.68rem] font-bold uppercase tracking-wide text-blue">
          {categoryLabel(article.category)}
        </span>
        <time
          dateTime={article.createdAt}
          className="text-xs font-semibold text-muted"
        >
          {formatNewsDate(article.createdAt)}
        </time>
      </div>

      <h2 className="m-0 mt-3 text-lg font-bold leading-snug text-blue">
        <Link href={`/news/${article.slug}`} className="no-underline hover:underline">
          {article.title}
        </Link>
      </h2>

      {article.dek ? (
        <p className="mt-2 mb-0 flex-1 text-sm leading-relaxed text-muted">
          {article.dek}
        </p>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs text-muted">
          {article.sources.length} source{article.sources.length === 1 ? "" : "s"}
        </span>
        <Link
          href={`/news/${article.slug}`}
          className="text-sm font-bold text-red no-underline hover:underline"
        >
          Read the brief →
        </Link>
      </div>
    </article>
  );
}

export default async function NewsPage() {
  let articles: NewsArticleSummary[] = [];
  let total = 0;
  let error: string | null = null;

  try {
    const feed = await getNewsFeed(NEWS_PAGE_SIZE, 0);
    articles = feed.articles;
    total = feed.total;
  } catch {
    error = "The newsroom is unavailable right now. Please try again shortly.";
  }

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: "The Daily Brief",
    description:
      "Original daily reporting on child trafficking and child exploitation in the United States.",
    url: siteUrl("/news"),
  };

  return (
    <div className="page-container py-8">
      <JsonLd data={jsonLd} />

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="m-0 text-3xl font-bold text-blue sm:text-4xl">
            The Daily Brief
          </h1>
          <p className="mt-3 mb-0 max-w-2xl leading-relaxed text-muted">
            Original reporting on child trafficking and child exploitation in the
            United States, published daily. Each brief is built from public news
            releases and press coverage, then written for this site. Sources are
            listed with every story.
          </p>
        </div>
        <Link
          href="/take-action"
          className="inline-flex items-center justify-center rounded-md bg-red px-5 py-3 text-sm font-bold text-white no-underline hover:opacity-90"
        >
          What can I do? →
        </Link>
      </div>

      {error ? (
        <div
          className="mt-8 rounded-lg border border-red/30 bg-red/5 px-6 py-5 text-sm text-red"
          role="alert"
        >
          <p className="m-0 font-semibold">Newsroom unavailable</p>
          <p className="m-0 mt-1">{error}</p>
        </div>
      ) : articles.length === 0 ? (
        <div className="mt-8 rounded-lg border border-card-border bg-surface px-6 py-10 text-center">
          <p className="m-0 font-semibold text-foreground">
            No briefs published yet.
          </p>
          <p className="mt-2 text-sm text-muted">
            The Daily Brief collects sources and publishes its first article each
            morning. Check back soon.
          </p>
        </div>
      ) : (
        <>
          <p
            className="mt-6 text-sm text-muted"
            role="status"
            aria-live="polite"
          >
            {articles.length === total
              ? `${total} brief${total === 1 ? "" : "s"} published.`
              : `Showing ${articles.length} of ${total} briefs.`}
          </p>
          <div className="mt-4 grid w-full min-w-0 grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-6 lg:grid-cols-3">
            {articles.map((article) => (
              <ArticleCard key={article.slug} article={article} />
            ))}
          </div>
        </>
      )}

      <section className="mt-10 rounded-[10px] border border-card-border bg-surface-muted p-5">
        <h2 className="m-0 text-lg font-bold text-blue">How this is reported</h2>
        <p className="mt-2 mb-0 text-sm leading-relaxed text-muted">
          Each morning we collect publicly published headlines and press releases
          about child trafficking and exploitation in the United States. Those
          items are passed to a language model that writes an original brief using
          only the facts supplied. Every article lists the source material it drew
          on, so you can check the record yourself. Operational details that could
          identify a victim are deliberately left out.
        </p>
      </section>
    </div>
  );
}
