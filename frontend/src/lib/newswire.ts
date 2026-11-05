/** Types and fetchers for the Daily Brief newswire. */

const API_URL =
  process.env.API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

export type NewsCategory = "enforcement" | "laws" | "policy" | "community" | "news";

export interface NewsSource {
  title: string;
  publisher: string;
  url: string;
  publishedAt?: string;
}

export interface NewsArticleSummary {
  id: number;
  slug: string;
  title: string;
  dek: string;
  category: NewsCategory;
  tags: string[];
  sources: NewsSource[];
  createdAt: string;
}

export interface NewsArticle extends NewsArticleSummary {
  body: string;
  model: string;
  updatedAt: string;
}

export interface NewsFeedResponse {
  articles: NewsArticleSummary[];
  total: number;
  limit: number;
  offset: number;
}

export const NEWS_PAGE_SIZE = 12;

export const CATEGORY_LABELS: Record<NewsCategory, string> = {
  enforcement: "Law enforcement",
  laws: "Laws & legislation",
  policy: "Policy & oversight",
  community: "Community response",
  news: "News",
};

export function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category as NewsCategory] ?? "News";
}

async function fetchApi<T>(path: string, timeoutMs = 20_000): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${API_URL}${path}`, {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!res.ok) {
      throw new Error(`API error ${res.status}`);
    }
    return (await res.json()) as T;
  } finally {
    clearTimeout(timeout);
  }
}

export async function getNewsFeed(
  limit = NEWS_PAGE_SIZE,
  offset = 0
): Promise<NewsFeedResponse> {
  return fetchApi<NewsFeedResponse>(`/api/newswire?limit=${limit}&offset=${offset}`);
}

export async function getNewsArticle(slug: string): Promise<NewsArticle> {
  return fetchApi<NewsArticle>(`/api/newswire/${encodeURIComponent(slug)}`);
}

export function formatNewsDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

/** Reading time is estimated from the full body, which only the detail page has. */
export function readingMinutes(body: string): number {
  const words = (body.match(/\S+/g) ?? []).length;
  return Math.max(1, Math.round(words / 220));
}
