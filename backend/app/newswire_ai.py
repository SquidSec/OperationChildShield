"""Write original newsroom-style articles from collected headlines.

The model is given the day's collected headlines (title, publisher, category,
short summary) and asked for a JSON object describing one article. We never ask
it to copy source text, and the prompt states that explicitly. The returned
body is Markdown with a fixed block vocabulary so the frontend can render it
without injecting HTML.

Everything here is defensive: a bad response, a timeout, or a missing key
returns ``None`` instead of raising, because the daily job must not crash the
scheduler thread.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

import httpx

from app import newswire_store
from app.config import settings
from app.newswire_collect import CATEGORIES

logger = logging.getLogger(__name__)

MAX_ITEMS_IN_PROMPT = 20
MAX_BODY_CHARS = 14_000
# The prompt targets 300-500 words. The floor sits well below that so a tight
# 250-word brief from a single source is accepted, while a model that answered
# with two paragraphs and stopped is rejected.
MIN_BODY_WORDS = 180

SYSTEM_PROMPT = """\
You are a staff writer for Operation Child Shield, a nonpartisan 501(c)(3) \
public charity that tracks child-protection legislation and publishes voting \
records from Congress.gov. You write the Daily Brief: short, factual newsroom \
articles about child trafficking and child exploitation in the United States.

Hard rules:
1. Write ORIGINAL prose. Never copy sentences or phrasing from the source \
headlines or summaries. Attribute facts in your own words.
2. Use ONLY facts present in the supplied headlines and summaries. Never invent \
names, numbers, charges, sentences, dates, quotes, or locations. If a detail is \
not supplied, describe the development without it.
3. Do not accuse anyone of a crime beyond what the source states. Use \
"charged with", "accused of", "convicted of" exactly as the source does, and \
include the presumption of innocence when describing pending charges.
4. No calls to violence, no identifying information about victims, no graphic \
description of abuse. Refer to material as "child sexual abuse material", never \
with abbreviations that read as graphic.
5. Be nonpartisan. Describe legislation and its sponsors by name and party if \
given; do not editorialize for or against a party.
6. If the supplied items describe unrelated stories, write about the one with \
the most concrete public-safety or policy development and mention the rest in a \
short "Also this week" list.

Output: a single JSON object, no Markdown fence, matching exactly this shape:

{
  "title": "string, <= 110 characters, plain text, no clickbait",
  "dek": "string, <= 240 characters, one sentence summary",
  "category": "one of: enforcement, laws, policy, community, news",
  "tags": ["3 to 6 short lowercase topical tags"],
  "body": "string, Markdown, 300-500 words",
  "sources": [0-based indices of the supplied items you relied on]
}

Length: aim for 300-500 words. Reach it with specific supplied facts first \
(who, what agency, what charge, what court, what sentence, where), then what \
that legal or procedural step means for this case, then what a reader should \
watch next. Keep general background to at most one short paragraph. Do not \
repeat the same idea in new words, and never invent facts or quotes to reach \
the length.

Body format rules:
- Start with one 2-4 sentence paragraph that states what happened.
- Use "## " subheadings for 2-3 sections (for example "What the filing says", \
"Why it matters", "What to watch").
- Use "- " bullet lists only where a list genuinely helps.
- Use **bold** sparingly for key terms.
- Close with a one-paragraph "What you can do" section giving a concrete, \
lawful, nonpartisan action (contacting a representative, checking a local \
school policy, reporting suspected exploitation to the CyberTipline).
- No links. No images. No tables. No code blocks.
"""


class ArticleError(RuntimeError):
    """Raised for a response we cannot use. Callers log and move on."""


def _strip_fence(text: str) -> str:
    """Models sometimes wrap JSON in a ```json fence despite instructions."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _slugify(text: str, max_length: int = 80) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower()
    if not slug:
        slug = "daily-brief"
    return slug[:max_length].strip("-")


def build_item_context(items: list[dict[str, Any]]) -> str:
    """Render the collected items for the prompt, numbered for citation."""
    lines: list[str] = []
    for index, item in enumerate(items[:MAX_ITEMS_IN_PROMPT]):
        summary = (item.get("summary") or "").strip()
        if len(summary) > 400:
            summary = f"{summary[:400]}..."
        lines.append(
            "\n".join(
                [
                    f"[{index}] {item.get('title', '')}",
                    f"Publisher: {item.get('source', 'unknown')}",
                    f"Category hint: {item.get('category', 'news')}",
                    f"Published: {item.get('publishedAt') or 'unknown'}",
                    f"Summary: {summary or '(no summary provided)'}",
                ]
            )
        )
    return "\n\n".join(lines)


_GENERIC_TITLE_WORDS = {
    "man", "woman", "child", "children", "sexual", "abuse", "material",
    "trafficking", "case", "court", "federal", "charged", "charge", "charges",
    "counts", "felony", "investigation", "years", "prison", "sentence",
    "sentenced", "guilty", "plea", "state", "police", "arrest", "arrested",
    "arraigned", "arraignment", "indicted", "indictment", "county",
    "department", "justice", "attorney", "office", "officials", "authorities",
    "teacher", "coach", "pastor", "doctor", "nurse", "father", "mother",
    "parents", "family", "school", "students", "senate", "house", "congress",
    "committee", "panel", "measure", "funding", "advances", "passes", "bill",
    "law", "laws", "local", "national", "report", "reports", "officer",
    "officers", "deputies", "sheriff", "guard", "worker", "employee",
    "company", "business", "group", "center", "program", "service",
    "services", "statewide", "trial", "judge", "jury", "pleaded", "pleads",
    "convicted", "conviction", "authority", "agents", "agent", "official",
    "news", "update", "updates", "police", "us", "u.s.", "america",
    "american", "united", "states", "new", "former", "two", "three", "four",
    "five", "six", "seven", "eight", "nine", "ten", "over", "more", "after",
    "before", "with", "from", "into", "that", "this", "these", "those",
}


def _distinctive_tokens(title: str) -> set[str]:
    """Place names and surnames that identify a story.

    A capitalized word of at least five letters is treated as a proper noun
    unless it is a common headline word, so "Nanticoke" counts and "Charged"
    does not. Two matching tokens are required downstream to avoid tying an
    article to a story it merely mentions in passing.
    """
    tokens: set[str] = set()
    for word in re.findall(r"\b[A-Z][A-Za-z'’-]{4,}\b", title or ""):
        token = word.lower().strip("'’-")
        if token in _GENERIC_TITLE_WORDS:
            continue
        # Apostrophe-free letters only, so possessives still match their root.
        if token.replace("-", "").isalpha():
            tokens.add(token)
    return tokens


def inferred_source_indices(body: str, items: list[dict[str, Any]]) -> list[int]:
    """Find supplied items whose distinctive names appear in the finished body.

    The model is asked to cite what it used, but a writer that names a town or a
    defendant in prose sometimes forgets to list the item, and attribution must
    be complete.

    Only *rare* tokens count: a name that appears in a single supplied headline
    identifies that story, while a word shared across many headlines ("Florida",
    "Ohio") does not. That keeps a passing mention of a state from attaching
    every story in the batch to the article.
    """
    body_tokens = {
        t.lower().strip("'’-") for t in re.findall(r"[A-Za-z'’-]{4,}", body)
    }
    per_item = [_distinctive_tokens(str(item.get("title") or "")) for item in items]
    frequency = _frequency(per_item)

    found: list[int] = []
    for index, tokens in enumerate(per_item):
        rare_hits = {
            token
            for token in tokens
            if frequency[token] <= 3 and token in body_tokens
        }
        if rare_hits:
            found.append(index)
    return found


def _frequency(per_item: list[set[str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for tokens in per_item:
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
    return counts


def cluster_items(
    items: list[dict[str, Any]], *, max_clusters: int = 3
) -> list[list[dict[str, Any]]]:
    """Group supplied items that describe the same story.

    Items are joined when they share a rare proper-noun token (a place or a
    surname) or an identical URL host plus a distinctive name. The model is then
    asked to write about one cluster, which keeps each brief focused instead of
    turning into a roundup of unrelated cases.
    """
    tokens_per_item = [_distinctive_tokens(str(item.get("title") or "")) for item in items]
    frequency = _frequency(tokens_per_item)

    # Union-find over item indices.
    parent = list(range(len(items)))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    token_owner: dict[str, int] = {}
    for index, tokens in enumerate(tokens_per_item):
        for token in tokens:
            # A name shared by a handful of headlines in one batch identifies a
            # story; a name shared by most of the batch is a recurring state or
            # agency and would merge unrelated cases.
            if frequency[token] > 3:
                continue
            if token in token_owner:
                union(token_owner[token], index)
            else:
                token_owner[token] = index

    groups: dict[int, list[dict[str, Any]]] = {}
    for index, item in enumerate(items):
        groups.setdefault(find(index), []).append(item)

    clusters = list(groups.values())
    # Largest cluster first: the best-supported story leads the feed.
    clusters.sort(key=len, reverse=True)
    return clusters[:max_clusters]


def _cluster_category(cluster: list[dict[str, Any]]) -> str:
    """The most common category among a cluster's items."""
    counts: dict[str, int] = {}
    for item in cluster:
        category = str(item.get("category") or "news")
        counts[category] = counts.get(category, 0) + 1
    return max(counts, key=counts.get) if counts else "news"


def choose_cluster(
    clusters: list[list[dict[str, Any]]], *, written_categories: set[str]
) -> list[dict[str, Any]]:
    """Pick the next story, preferring a category the run has not covered yet.

    A newsroom that publishes only arrest reports is not covering the subject.
    Stories are ranked by how many sources corroborate them, with a penalty for
    a category already written in this run so the day's output mixes
    enforcement with legislation or policy when both are available.
    """
    if not clusters:
        return []

    def score(cluster: list[dict[str, Any]]) -> tuple[int, int, int]:
        category = _cluster_category(cluster)
        # More sources is better; a repeated category is much worse; a
        # legislation/policy story edges out another arrest report at equal size.
        repeat_penalty = -10 if category in written_categories else 0
        policy_bonus = 1 if category in {"laws", "policy", "community"} else 0
        return (len(cluster) + repeat_penalty, policy_bonus, len(cluster))

    return max(clusters, key=score)


def pick_cluster(
    items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split items into (focus cluster, remaining items).

    ``remaining`` is passed to the model only as a "briefly mention these"
    list, never as material for the main body.
    """
    clusters = cluster_items(items, max_clusters=2)
    if not clusters:
        return [], []
    focus = clusters[0]
    if len(clusters) > 1:
        # Keep a few other headlines for a one-line "also this week" note.
        rest = [item for cluster in clusters[1:] for item in cluster][:4]
    else:
        rest = []
    return focus, rest


def _validate(article: dict[str, Any], item_count: int) -> dict[str, Any]:
    title = str(article.get("title") or "").strip()
    body = str(article.get("body") or "").strip()
    if len(title) < 10:
        raise ArticleError("Title too short")
    # The prompt asks for 350-650 words. Enforce a floor slightly below the
    # target so a nearly-complete draft is not thrown away, while still catching
    # a model that answered with a two-paragraph summary.
    word_count = len(body.split())
    if word_count < MIN_BODY_WORDS:
        raise ArticleError(f"Body too short ({word_count} words)")

    category = str(article.get("category") or "news").strip().lower()
    if category not in CATEGORIES:
        category = "news"

    raw_tags = article.get("tags") or []
    tags = []
    if isinstance(raw_tags, list):
        for tag in raw_tags[:8]:
            cleaned = re.sub(r"[^a-z0-9 ]", "", str(tag).lower()).strip()
            if cleaned:
                tags.append(cleaned[:40])

    raw_sources = article.get("sources") or []
    sources: list[int] = []
    if isinstance(raw_sources, list):
        for value in raw_sources:
            try:
                index = int(value)
            except (TypeError, ValueError):
                continue
            if 0 <= index < item_count:
                sources.append(index)
    sources = sorted(set(sources))

    return {
        "title": title[:300],
        "dek": str(article.get("dek") or "").strip()[:600],
        "category": category,
        "tags": tags,
        "body": body[:MAX_BODY_CHARS],
        "sourceIndices": sources,
    }


async def request_article(
    items: list[dict[str, Any]],
    *,
    client: httpx.AsyncClient | None = None,
    also_week: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Ask the model for one article. Returns None on any failure."""
    if not items:
        return None
    if not settings.llm_api_key:
        logger.info("Newswire article skipped: LLM_API_KEY is not set")
        return None

    prompt = (
        "Write ONE focused Daily Brief article about the single story described "
        "by the items below. Do not turn it into a roundup of unrelated cases.\n\n"
        f"{build_item_context(items)}\n"
    )
    if also_week:
        prompt += (
            "\nOptional: these separate headlines may be mentioned in at most one "
            "short 'Also this week' sentence at the end. Do not build the article "
            "around them and do not cite them in the sources list.\n\n"
            + "\n".join(f"- {item.get('title', '')}" for item in also_week[:4])
            + "\n"
        )
    prompt += "\nReturn only the JSON object."

    own_client = client is None
    client = client or httpx.AsyncClient(timeout=settings.llm_timeout_seconds)

    try:
        response = await client.post(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.llm_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.4,
                # Reasoning models (DeepSeek v4.x) spend 1-2k tokens on hidden
                # reasoning before the answer. A 4000 budget truncated the JSON
                # mid-string and every draft was rejected; 8000 leaves room for
                # both the reasoning and a 500-word body.
                "max_tokens": 8000,
                "response_format": {"type": "json_object"},
            },
        )
    except Exception:  # noqa: BLE001 - network failure must not break the job
        logger.warning("Newswire LLM request failed", exc_info=True)
        return None
    finally:
        if own_client:
            await client.aclose()

    if response.status_code != 200:
        logger.warning(
            "Newswire LLM returned %s: %s",
            response.status_code,
            response.text[:300],
        )
        return None

    try:
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError):
        logger.warning("Newswire LLM response had an unexpected shape")
        return None

    try:
        parsed = json.loads(_strip_fence(str(content)))
        if not isinstance(parsed, dict):
            raise ArticleError("Response was not a JSON object")
        return _validate(parsed, len(items))
    except (ValueError, ArticleError) as exc:
        logger.warning("Newswire article rejected: %s", exc)
        return None


def _title_tokens(title: str) -> set[str]:
    """Content words of a headline, for near-duplicate detection."""
    stop = {
        "the", "a", "an", "of", "on", "in", "for", "and", "to", "after", "with",
        "man", "woman", "men", "arrested", "charged", "faces", "over", "new",
        "child", "children", "sexual", "abuse", "material", "exploitation",
        "trafficking", "case", "cases", "investigation", "federal", "court",
    }
    return {
        word.lower().strip(".,'")
        for word in re.findall(r"[A-Za-z']{3,}", title or "")
        if word.lower().strip(".,'") not in stop
    }


def is_duplicate_story(title: str, *, threshold: float = 0.6) -> bool:
    """True when a stored article already covers this headline.

    The same story reaches us from several publishers, and a later run can pick
    it up again when new coverage arrives. Slugs differ, so a slug check is not
    enough; compare the content words of the headline instead.
    """
    incoming = _title_tokens(title)
    if len(incoming) < 2:
        return False
    for existing in newswire_store.list_articles_summary(limit=100):
        stored = _title_tokens(str(existing.get("title") or ""))
        if not stored:
            continue
        shared = len(incoming & stored)
        overlap = shared / min(len(incoming), len(stored))
        if overlap >= threshold:
            return True
    return False


def _unique_slug(base: str) -> str:
    """Return a slug that does not collide with an existing article."""
    if not _slug_exists(base):
        return base
    for suffix in range(2, 50):
        candidate = f"{base}-{suffix}"
        if not _slug_exists(candidate):
            return candidate
    return f"{base}-{int(datetime.now(timezone.utc).timestamp())}"


def _slug_exists(slug: str) -> bool:
    return newswire_store.get_article(slug) is not None


def _source_records(items: list[dict[str, Any]], indices: list[int]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for index in indices:
        if index >= len(items):
            continue
        item = items[index]
        records.append(
            {
                "title": str(item.get("title") or "")[:300],
                "publisher": str(item.get("source") or "")[:120],
                "url": str(item.get("url") or "")[:1000],
                "publishedAt": str(item.get("publishedAt") or ""),
            }
        )
    # De-duplicate by URL in case the same story appears in two feeds.
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for record in records:
        if record["url"] in seen:
            continue
        seen.add(record["url"])
        unique.append(record)
    return unique


async def write_article_from_items(
    items: list[dict[str, Any]],
    *,
    client: httpx.AsyncClient | None = None,
    also_week: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Generate, validate, and persist one article. Returns the stored row."""
    # A single headline cannot support even a short brief without the model
    # padding with generic background, so it is not used on its own.
    if len(items) < 2:
        logger.info("Newswire article skipped: only %s item(s) for one story", len(items))
        return None

    draft = await request_article(items, client=client, also_week=also_week)
    if draft is None:
        return None

    # A later run can pick up fresh coverage of a story already published.
    # Refuse it rather than publishing the same event twice.
    if is_duplicate_story(draft["title"]):
        logger.info("Newswire duplicate story skipped: %s", draft["title"][:80])
        return None

    slug_base = _slugify(draft["title"])
    slug = _unique_slug(slug_base)
    # Union: what the model cited, plus anything it clearly used in prose.
    cited = set(draft["sourceIndices"])
    cited.update(inferred_source_indices(draft["body"], items))
    sources = _source_records(items, sorted(cited))

    record = {
        "slug": slug,
        "title": draft["title"],
        "dek": draft["dek"],
        "body": draft["body"],
        "category": draft["category"],
        "tags": draft["tags"],
        "sources": sources,
        "model": settings.llm_model,
        "status": "published",
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }

    stored = newswire_store.save_article(record)
    if stored is None:
        logger.info("Newswire article slug already existed: %s", slug)
        return None
    return stored


async def run_daily(
    *,
    collect: bool = True,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """The daily job: collect, then write up to N articles.

    Returns a summary dict so the scheduler/admin panel can show what happened.
    """
    from app import newswire_collect

    summary: dict[str, Any] = {
        "collected": None,
        "articlesWritten": 0,
        "slugs": [],
        "errors": [],
    }

    if collect:
        try:
            summary["collected"] = await newswire_collect.collect(client=client)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Newswire collection failed")
            summary["errors"].append(f"collect: {exc}")

    if not settings.newswire_configured:
        summary["errors"].append("article writing disabled or unconfigured")
        return summary

    per_run = max(1, min(int(settings.newswire_max_articles_per_run or 1), 10))
    min_items = max(1, int(settings.newswire_min_items or 1))
    # Track clusters that produced nothing usable so one thin story does not
    # stall the run. Keyed by the cluster's item URLs.
    skipped: set[str] = set()
    written_categories: set[str] = set()
    attempts = 0
    max_attempts = per_run * 3

    while summary["articlesWritten"] < per_run and attempts < max_attempts:
        attempts += 1
        # Look at a wider pool than one prompt so a legislation story published
        # a day or two ago can still be picked over today's newest arrest report.
        # The prompt itself is capped at MAX_ITEMS_IN_PROMPT below.
        items = newswire_store.unused_items(since_hours=72, limit=120)
        items = [i for i in items if i.get("url") not in skipped]
        if len(items) < min_items:
            break

        clusters = cluster_items(items, max_clusters=6)
        if not clusters:
            break

        focus = choose_cluster(clusters, written_categories=written_categories)
        rest = [i for c in clusters if c is not focus for i in c][:4]

        article = await write_article_from_items(focus, client=client, also_week=rest)
        if article is None:
            skipped.update(str(i.get("url")) for i in focus)
            summary["errors"].append(
                f"skipped story: {focus[0].get('title', '')[:80]}"
            )
            continue

        # Only the focus cluster's items are consumed, so the remaining stories
        # stay available for the next article in this run.
        used_ids = [item["id"] for item in focus if item.get("id") is not None]
        newswire_store.mark_items_used(used_ids, article["slug"])
        written_categories.add(article["category"])
        summary["articlesWritten"] += 1
        summary["slugs"].append(article["slug"])

    return summary
