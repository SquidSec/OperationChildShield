import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { JsonLd } from "@/components/JsonLd";
import { ArticleBody } from "@/components/news/ArticleBody";
import { ArticleShareLinks } from "@/components/news/ArticleShareLinks";
import {
  categoryLabel,
  formatNewsDate,
  getNewsArticle,
  readingMinutes,
  type NewsArticle,
} from "@/lib/newswire";
import { siteUrl } from "@/lib/site";

interface NewsArticlePageProps {
  params: Promise<{ slug: string }>;
}

const SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

async function loadArticle(slug: string): Promise<NewsArticle | null> {
  if (!SLUG_PATTERN.test(slug) || slug.length > 200) return null;
  try {
    return await getNewsArticle(slug);
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: NewsArticlePageProps): Promise<Metadata> {
  const { slug } = await params;
  const article = await loadArticle(slug);
  if (!article) {
    return { title: "Brief not found" };
  }
  const description = article.dek || article.title;
  return {
    title: article.title,
    description,
    openGraph: {
      type: "article",
      title: `${article.title} | Operation Child Shield`,
      description,
      url: `/news/${article.slug}`,
      publishedTime: article.createdAt,
    },
    twitter: {
      card: "summary_large_image",
      title: `${article.title} | Operation Child Shield`,
      description,
    },
  };
}

export default async function NewsArticlePage({ params }: NewsArticlePageProps) {
  const { slug } = await params;
  const article = await loadArticle(slug);
  if (!article) notFound();

  const url = siteUrl(`/news/${article.slug}`);

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    headline: article.title,
    description: article.dek,
    datePublished: article.createdAt,
    dateModified: article.updatedAt,
    mainEntityOfPage: url,
    publisher: {
      "@type": "Organization",
      name: "Operation Child Shield",
      url: siteUrl("/"),
    },
    ...(article.sources.length
      ? {
          citation: article.sources.map((source) => ({
            "@type": "CreativeWork",
            name: source.title,
            url: source.url,
            ...(source.publisher ? { publisher: source.publisher } : {}),
          })),
        }
      : {}),
  };

  return (
    <div className="page-container py-8">
      <JsonLd data={jsonLd} />

      <Link href="/news" className="text-sm text-muted hover:text-blue">
        ← The Daily Brief
      </Link>

      <article className="mt-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-blue/10 px-3 py-1 text-[0.7rem] font-bold uppercase tracking-wide text-blue">
            {categoryLabel(article.category)}
          </span>
          <time
            dateTime={article.createdAt}
            className="text-sm font-semibold text-muted"
          >
            {formatNewsDate(article.createdAt)}
          </time>
          <span className="text-sm text-muted" aria-hidden>
            ·
          </span>
          <span className="text-sm text-muted">
            {readingMinutes(article.body)} min read
          </span>
        </div>

        <h1 className="mt-4 mb-0 max-w-3xl text-3xl font-bold leading-tight text-blue sm:text-4xl">
          {article.title}
        </h1>

        {article.dek ? (
          <p className="mt-4 mb-0 max-w-3xl text-lg leading-relaxed text-muted">
            {article.dek}
          </p>
        ) : null}

        <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1fr)_300px]">
          <div className="min-w-0">
            <ArticleBody body={article.body} />

            {article.tags.length > 0 ? (
              <ul className="mt-8 flex list-none flex-wrap gap-2 p-0">
                {article.tags.map((tag) => (
                  <li
                    key={tag}
                    className="rounded-full border border-card-border bg-surface-muted px-3 py-1 text-xs font-semibold text-muted"
                  >
                    {tag}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>

          <aside className="min-w-0 space-y-4 lg:sticky lg:top-4 lg:self-start">
            <ArticleShareLinks title={article.title} dek={article.dek} url={url} />

            {article.sources.length > 0 ? (
              <div className="rounded-[10px] border border-card-border bg-surface p-4 shadow-sm">
                <h2 className="m-0 text-xs font-bold uppercase tracking-wider text-muted">
                  Sources
                </h2>
                <ul className="mt-3 list-none space-y-3 p-0">
                  {article.sources.map((source, index) => (
                    <li key={`${source.url}-${index}`} className="text-sm">
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer nofollow"
                        className="font-semibold text-blue hover:underline"
                      >
                        {source.title}
                      </a>
                      <p className="m-0 mt-1 text-xs text-muted">
                        {source.publisher}
                        {source.publishedAt
                          ? ` · ${formatNewsDate(source.publishedAt)}`
                          : ""}
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            <div className="rounded-[10px] border border-red/30 bg-red/5 p-4">
              <h2 className="m-0 text-sm font-bold text-red">
                See something to report?
              </h2>
              <p className="mt-2 mb-0 text-sm leading-relaxed text-muted">
                Report suspected child exploitation to the National Center for
                Missing &amp; Exploited Children.
              </p>
              <a
                href="https://report.cybertip.org/"
                target="_blank"
                rel="noopener noreferrer"
                className="mt-3 inline-flex items-center justify-center rounded-md bg-red px-4 py-2 text-sm font-bold text-white no-underline hover:opacity-90"
              >
                Open CyberTipline →
              </a>
            </div>

            <Link
              href="/take-action"
              className="block rounded-[10px] border border-blue/30 bg-blue/5 p-4 text-sm font-semibold text-blue no-underline hover:bg-blue/10"
            >
              Find what you can do, based on who you are →
            </Link>
          </aside>
        </div>
      </article>

      <p className="mt-10 max-w-3xl text-xs leading-relaxed text-muted">
        This brief was written for Operation Child Shield from the public sources
        listed above. Details may change as a case moves through the courts. Nothing
        here is legal advice, and anyone charged with a crime is presumed innocent
        unless convicted.
      </p>
    </div>
  );
}
