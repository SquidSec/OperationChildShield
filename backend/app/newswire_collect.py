"""Collect child-trafficking news from public RSS feeds.

Design notes:

* **No new dependencies.** Feeds are parsed with ``xml.etree`` from the stdlib.
  ``feedparser`` would be more forgiving, but the two feed shapes we use are
  well-formed RSS 2.0.
* **Sources are explicit, not scraped.** Every request is a documented RSS/Atom
  endpoint belonging to the publisher. We never fetch an article page, so we do
  not republish anyone's text beyond the headline used to identify a story.
* **Failures are per-source.** One blocked feed must not stop the other sources
  or the daily job.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus

import httpx

from app import newswire_store

logger = logging.getLogger(__name__)

USER_AGENT = (
    "OperationChildShieldNewsBot/1.0 (+https://operationchildshield.org; "
    "news aggregation for a public 501(c)(3) record)"
)
REQUEST_TIMEOUT = 20.0

# Story categories, in the order the feed page displays them.
CATEGORIES = ("enforcement", "laws", "policy", "community", "news")

# Feed endpoints. Google News RSS is queried per topic so the mix covers
# legislation, law enforcement action, and community response rather than one
# narrow phrase.
GOOGLE_NEWS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

FEEDS: tuple[dict[str, str], ...] = (
    {
        "name": "Google News",
        "url": GOOGLE_NEWS.format(
            query=quote_plus(
                '"child trafficking" OR "child sex trafficking" when:2d'
            )
        ),
        "category": "news",
    },
    {
        "name": "Google News",
        "url": GOOGLE_NEWS.format(
            query=quote_plus(
                '(trafficking OR "human trafficking") (arrest OR sentenced OR indicted '
                "OR rescued) children when:2d"
            )
        ),
        "category": "enforcement",
    },
    {
        "name": "Google News",
        "url": GOOGLE_NEWS.format(
            query=quote_plus(
                '(bill OR law OR legislature OR congress) child trafficking when:3d'
            )
        ),
        "category": "laws",
    },
    {
        "name": "Google News",
        "url": GOOGLE_NEWS.format(
            query=quote_plus(
                '"missing children" OR "child exploitation" OR "child sexual abuse material" when:2d'
            )
        ),
        "category": "news",
    },
    {
        "name": "U.S. Department of Justice",
        "url": "https://www.justice.gov/news/rss?type=press_release",
        "category": "enforcement",
        "filter": "traffick",
        # A federal agency feed is US by definition; skip the geography gate so
        # local datelines ("Nanticoke") are not mistaken for foreign coverage.
        "trusted_us": "1",
    },
)

# A headline is kept only if it mentions the subject. This is a relevance gate,
# not sentiment: traffic-related "trafficking" hits are dropped by requiring a
# child term or a trafficking term paired with a child term.
_CHILD_TERMS = re.compile(
    r"\b(child|children|minor|minors|juvenile|youth|teen|teenager|infant|"
    r"student|students|kid|kids|girl|girls|boy|boys)\b",
    re.IGNORECASE,
)
_TRAFFICKING_TERMS = re.compile(
    r"\b(traffick\w*|exploit\w*|abduct\w*|predator\w*|"
    r"sexual abuse material|csam|grooming|sextort\w*)\b",
    re.IGNORECASE,
)

# The brief covers the United States, so a story needs a US marker. Google News
# uses the US edition, but still surfaces foreign coverage of the same subject.
_US_MARKERS = re.compile(
    r"\b(U\.?S\.?|United States|America|American|federal|FBI|ICE|HSI|DHS|"
    r"Justice Department|DOJ|Homeland Security|Congress|Senate|House|"
    r"state|states|county|sheriff|police|governor|attorney general|"
    r"Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|"
    r"Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|"
    r"Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|"
    r"Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|"
    r"New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|"
    r"Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|"
    r"Virginia|Washington|West Virginia|Wisconsin|Wyoming|"
    r"District of Columbia|Puerto Rico|Guam)\b",
    re.IGNORECASE,
)

# A dateline naming another country means this is not a US story, even if it
# mentions "federal" in translation.
_FOREIGN_MARKERS = re.compile(
    r"\b(Australia|Australian|Canada|Canadian|United Kingdom|Britain|British|"
    r"England|Scotland|Wales|Ireland|India|Indian|Pakistan|Nigeria|Nigerian|"
    r"Ghana|Kenya|Philippines|Filipino|Indonesia|Malaysia|Thailand|Vietnam|"
    r"China|Chinese|Japan|Japanese|Korea|Brazil|Mexican|Mexico|Colombia|"
    r"Romania|Romanian|Ukraine|Russia|Moldova|Nepal|Bangladesh|Uganda|"
    r"South Africa|New Zealand)\b",
    re.IGNORECASE,
)

# Keyword routing for the per-story category badge.
_CATEGORY_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "laws",
        re.compile(
            r"\b(bill|law|laws|legislat\w*|senate|house|congress|governor|"
            r"ballot|measure|statute|ordinance|court rules|appeals court|supreme court)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "enforcement",
        re.compile(
            r"\b(arrest\w*|charge\w*|convict\w*|sentenc\w*|indict\w*|plea\w*|"
            r"rescued|rescue|raid|sting|sheriff|police|fbi|prosecutor|"
            r"task force|homeland security|ice|marshal|jail|prison|guilty)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "policy",
        re.compile(
            r"\b(agency|department|federal|administration|report|audit|funding|"
            r"grant|task force|policy|hearing|committee| Oversight)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "community",
        re.compile(
            r"\b(nonprofit|community|church|school|teacher|parent|vigil|"
            r"awareness|volunteer|survivor|donat\w*|fundrais\w*)\b",
            re.IGNORECASE,
        ),
    ),
)


def is_relevant(title: str, summary: str = "", *, require_us: bool = True) -> bool:
    """True when a headline is about child exploitation or trafficking in the US.

    Requires a trafficking/exploitation term. A child term in the same text
    narrows it to minors, but a headline that names a minor-specific crime
    (e.g. "CSAM") qualifies on its own. A US marker is required so foreign
    coverage does not fill a United States brief; feeds published by a US agency
    pass ``require_us=False`` because their whole output is domestic.
    """
    text = f"{title} {summary}"
    if not _TRAFFICKING_TERMS.search(text):
        return False
    if require_us:
        if not _US_MARKERS.search(text):
            return False
        # A foreign dateline in the headline itself is decisive.
        if _FOREIGN_MARKERS.search(title) and not _US_MARKERS.search(title):
            return False
    if _CHILD_TERMS.search(text):
        return True
    return bool(re.search(r"\bcsam\b|sexual abuse material", text, re.IGNORECASE))


def classify(title: str, fallback: str = "news") -> str:
    for name, pattern in _CATEGORY_RULES:
        if pattern.search(title):
            return name
    return fallback if fallback in CATEGORIES else "news"


def _text(node: ET.Element | None, *tags: str) -> str:
    if node is None:
        return ""
    for tag in tags:
        found = node.find(tag)
        if found is not None and found.text:
            return found.text.strip()
    return ""


def _parse_date(raw: str) -> str | None:
    if not raw:
        return None
    # RSS 2.0: "Wed, 04 Nov 2026 07:33:11 GMT"
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            parsed = datetime.strptime(raw, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(
            timezone.utc
        ).isoformat()
    except ValueError:
        return None


def _clean_source_title(title: str, source: str) -> str:
    """Google News appends " - Publisher" to every headline; strip it."""
    if source:
        suffix = f" - {source}"
        if title.endswith(suffix):
            return title[: -len(suffix)].strip()
    return title


def parse_feed(xml_text: str, feed: dict[str, str]) -> list[dict[str, Any]]:
    """Turn one RSS document into candidate items. Never raises on bad markup."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("Skipping malformed feed: %s", feed.get("url", "")[:80])
        return []

    channel = root.find("channel")
    nodes = channel.findall("item") if channel is not None else root.findall(".//item")

    items: list[dict[str, Any]] = []
    for node in nodes:
        source = _text(node, "source") or feed.get("name", "")
        title = _clean_source_title(_text(node, "title"), _text(node, "source"))
        link = _text(node, "link")
        summary = re.sub(r"<[^>]+>", " ", _text(node, "description"))
        summary = re.sub(r"\s+", " ", summary).strip()
        published = _parse_date(_text(node, "pubDate", "published", "updated"))

        if not title or not link:
            continue
        require_us = not feed.get("trusted_us")
        if not is_relevant(title, summary, require_us=require_us):
            continue
        if not link.startswith(("http://", "https://")):
            continue

        items.append(
            {
                "source": source[:120],
                "title": title[:500],
                "url": link[:1000],
                "summary": summary[:2000],
                "publishedAt": published,
                "collectedAt": datetime.now(timezone.utc).isoformat(),
                "category": classify(title, feed.get("category", "news")),
            }
        )
    return items


async def collect(client: httpx.AsyncClient | None = None) -> dict[str, int]:
    """Fetch every feed once and store new headlines.

    Returns counts for the caller (the admin panel and the daily job both want
    a human-readable summary).
    """
    newswire_store.init_newswire_db()
    own_client = client is None
    client = client or httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml"},
        follow_redirects=True,
    )

    fetched = 0
    added = 0
    failed = 0
    try:
        for feed in FEEDS:
            try:
                res = await client.get(feed["url"])
                if res.status_code != 200:
                    logger.info(
                        "Feed returned %s: %s", res.status_code, feed["url"][:100]
                    )
                    failed += 1
                    continue
                entries = parse_feed(res.text, feed)
                fetched += len(entries)
                for entry in entries:
                    if newswire_store.save_item(entry):
                        added += 1
            except Exception:  # noqa: BLE001 - one feed must not stop the rest
                failed += 1
                logger.warning("Feed fetch failed: %s", feed["url"][:100], exc_info=True)
    finally:
        if own_client:
            await client.aclose()

    newswire_store.prune_items()
    logger.info("Newswire collection: %s fetched, %s new, %s feeds failed", fetched, added, failed)
    return {"fetched": fetched, "added": added, "failedFeeds": failed}
