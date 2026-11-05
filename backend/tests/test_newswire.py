import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import newswire_ai, newswire_collect, newswire_store
from app.config import settings
from app.routes import newswire


RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Test Feed</title>
  <item>
    <title>Man charged with child trafficking in Ohio - Test Wire</title>
    <link>https://example.test/a</link>
    <description>A 41-year-old was charged after investigators said he
      transported a 15-year-old across state lines.</description>
    <pubDate>Wed, 04 Nov 2026 07:33:11 GMT</pubDate>
    <source>Test Wire</source>
  </item>
  <item>
    <title>Highway traffic delays reported near Dayton - Test Wire</title>
    <link>https://example.test/traffic</link>
    <description>Construction closed two lanes.</description>
    <pubDate>Wed, 04 Nov 2026 06:00:00 GMT</pubDate>
    <source>Test Wire</source>
  </item>
  <item>
    <title>Senate committee advances child exploitation bill - Test Wire</title>
    <link>https://example.test/b</link>
    <description>The bill would fund task forces.</description>
    <pubDate>Wed, 04 Nov 2026 05:00:00 GMT</pubDate>
    <source>Test Wire</source>
  </item>
</channel></rss>
"""


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "cache_dir", str(tmp_path))
    newswire_store.reset_for_tests()
    newswire_store.init_newswire_db()
    yield
    newswire_store.reset_for_tests()


def _client(monkeypatch) -> TestClient:
    app = FastAPI()
    app.include_router(newswire.router, prefix="/api")
    return TestClient(app)


# --- collection -------------------------------------------------------------


def test_parse_feed_keeps_only_child_trafficking_items():
    feed = {"name": "Test Wire", "url": "https://example.test/rss", "category": "news"}
    items = newswire_collect.parse_feed(RSS, feed)
    titles = [item["title"] for item in items]
    assert "Man charged with child trafficking in Ohio" in titles
    assert "Senate committee advances child exploitation bill" in titles
    # A traffic story that happens to be near the word "traffic" is dropped.
    assert not any("Highway" in title for title in titles)


def test_parse_feed_strips_google_news_publisher_suffix():
    feed = {"name": "Google News", "url": "x", "category": "news"}
    xml = RSS.replace("<title>Man charged with child trafficking in Ohio - Test Wire</title>",
                      "<title>Man charged with child trafficking in Ohio - The Daily Bugle</title>")
    xml = xml.replace("<source>Test Wire</source>", "<source>The Daily Bugle</source>", 1)
    titles = [i["title"] for i in newswire_collect.parse_feed(xml, feed)]
    assert "Man charged with child trafficking in Ohio" in titles


def test_parse_feed_tolerates_broken_xml():
    assert newswire_collect.parse_feed("<rss><channel>", {"name": "x"}) == []


def test_parse_feed_rejects_dtd_and_entity_expansion():
    # "Billion laughs": entity expansion is the attack ElementTree does not
    # protect against, so any document declaring a DTD is refused outright.
    bomb = """<?xml version="1.0"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
]>
<rss version="2.0"><channel><item>
  <title>&lol2; child trafficking United States</title>
  <link>https://example.test/x</link>
</item></channel></rss>"""
    assert newswire_collect.parse_feed(bomb, {"name": "Test"}) == []


def test_collect_skips_oversized_feed(monkeypatch):
    import asyncio

    monkeypatch.setattr(newswire_collect, "MAX_FEED_BYTES", 100)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=RSS)

    feeds = ({"name": "Test Wire", "url": "https://example.test/rss", "category": "news"},)
    monkeypatch.setattr(newswire_collect, "FEEDS", feeds)

    async def run():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            return await newswire_collect.collect(client=client)

    result = asyncio.run(run())
    assert result["added"] == 0
    assert result["failedFeeds"] == 1


def test_classify_routes_story_categories():
    assert newswire_collect.classify("Man sentenced to 12 years for trafficking") == "enforcement"
    assert newswire_collect.classify("Senate passes trafficking bill") == "laws"
    assert newswire_collect.classify("Church hosts vigil for survivors") == "community"


def test_relevance_gate_rejects_foreign_coverage():
    """Only markers that imply US jurisdiction count as US markers.

    "police", "state", and "county" appear in every country. They used to count,
    which let Delhi Police coverage of an Indian case into a US brief.
    """
    foreign = [
        "Delhi Police Files FIR Against Meta Over Child Sexual Abuse Material",
        "Delhi police register FIR over child sexual abuse material on Meta platforms",
        "Australian author sentenced over child exploitation material",
        "NHRC directs Delhi Police in child abuse material case",
    ]
    for title in foreign:
        assert not newswire_collect.is_relevant(title), title

    domestic = [
        "Florida man sentenced for child trafficking",
        "FBI arrests two in Broken Arrow child exploitation probe",
        "U.S. Attorney announces child exploitation conviction",
        "Man charged with trafficking a minor in Ohio",
    ]
    for title in domestic:
        assert newswire_collect.is_relevant(title), title


def test_trusted_us_feed_skips_geography_gate():
    """A DOJ release with a local dateline is still a US story.

    The subject gate still applies; only the geography check is skipped.
    """
    title = "Nanticoke Man Arraigned on 600 Counts of Child Exploitation"
    assert not newswire_collect.is_relevant(title)
    assert newswire_collect.is_relevant(title, require_us=False)
    # The subject gate is not bypassed for a trusted feed: "exploitation" with
    # no child term stays out even from DOJ.
    assert not newswire_collect.is_relevant(
        "Nanticoke Man Arraigned on 600 Felony Exploitation Counts",
        require_us=False,
    )


def test_collect_stores_items_and_dedupes(tmp_path, monkeypatch):
    calls = {"n": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, text=RSS)

    feeds = ({"name": "Test Wire", "url": "https://example.test/rss", "category": "news"},)
    monkeypatch.setattr(newswire_collect, "FEEDS", feeds)

    async def run():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            return await newswire_collect.collect(client=client)

    import asyncio

    first = asyncio.run(run())
    assert first["added"] == 2
    assert first["failedFeeds"] == 0

    second = asyncio.run(run())
    # URLs are unique, so a second crawl inserts nothing.
    assert second["added"] == 0
    assert newswire_store.stats()["items"] == 2


# --- article generation -----------------------------------------------------


def _fake_llm(article: dict):
    async def handler(request: httpx.Request) -> httpx.Response:
        import json

        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": "```json\n" + json.dumps(article) + "\n```"}}
                ]
            },
        )

    return handler


GOOD_ARTICLE = {
    "title": "Ohio Man Charged After Trafficking Investigation",
    "dek": "Federal prosecutors say the case involved a minor moved across state lines.",
    "category": "enforcement",
    "tags": ["ohio", "federal charges"],
    "body": "## What happened\n\n" + ("A man was charged in the case. " * 60) + "\n\n## Why it matters\n\n" + ("The record matters. " * 40),
    "sources": [0],
}


def test_write_article_persists_and_links_sources(monkeypatch):
    import asyncio

    feed = {"name": "Test Wire", "url": "https://example.test/rss", "category": "news"}
    items = newswire_collect.parse_feed(RSS, feed)
    for item in items:
        newswire_store.save_item(item)

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "newswire_enabled", True)

    async def run():
        transport = httpx.MockTransport(_fake_llm(GOOD_ARTICLE))
        async with httpx.AsyncClient(transport=transport) as client:
            return await newswire_ai.write_article_from_items(items, client=client)

    stored = asyncio.run(run())
    assert stored is not None
    assert stored["category"] == "enforcement"
    assert stored["sources"][0]["url"] == "https://example.test/a"
    assert newswire_store.get_article(stored["slug"]) is not None


def test_write_article_rejects_short_body(monkeypatch):
    import asyncio

    feed = {"name": "Test Wire", "url": "x", "category": "news"}
    items = newswire_collect.parse_feed(RSS, feed)
    bad = dict(GOOD_ARTICLE, body="Too short.")
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "newswire_enabled", True)

    async def run():
        transport = httpx.MockTransport(_fake_llm(bad))
        async with httpx.AsyncClient(transport=transport) as client:
            return await newswire_ai.write_article_from_items(items, client=client)

    assert asyncio.run(run()) is None


def test_body_length_floor_matches_the_prompt_word_target():
    # The prompt asks for 350-650 words; a 200-word draft is a failed generation,
    # not a brief, so it must be rejected rather than published.
    items = newswire_collect.parse_feed(RSS, {"name": "x", "url": "x"})
    with pytest.raises(newswire_ai.ArticleError):
        newswire_ai._validate(
            dict(GOOD_ARTICLE, body="A short paragraph. " * 20), len(items)
        )
    # A draft at the floor passes.
    passing = newswire_ai._validate(
        dict(GOOD_ARTICLE, body="word " * newswire_ai.MIN_BODY_WORDS), len(items)
    )
    assert passing["body"]


def test_inferred_sources_capture_prose_the_model_forgot_to_cite():
    items = [
        {"title": "Nanticoke Man Arraigned On 600 Felony Counts", "url": "https://x/1"},
        {"title": "Holliston Teacher Charged With Exploitation", "url": "https://x/2"},
        {"title": "Senate Panel Advances Funding Measure", "url": "https://x/3"},
    ]
    body = (
        "A Nanticoke arraignment drew attention this week. "
        "Separately, a Holliston teacher was charged."
    )
    indices = newswire_ai.inferred_source_indices(body, items)
    # Both named towns appear in the prose, so both items are attributed even
    # though the model left them out of its own citation list.
    assert indices == [0, 1]


def test_inferred_sources_skips_items_with_no_prose_presence():
    items = [{"title": "Senate Panel Advances Funding Measure", "url": "https://x/3"}]
    assert newswire_ai.inferred_source_indices("Unrelated text.", items) == []


def test_distinctive_tokens_ignore_generic_words():
    tokens = newswire_ai._distinctive_tokens(
        "Man Charged With Child Trafficking In Federal Court"
    )
    assert tokens == set()


def test_cluster_items_groups_stories_by_shared_rare_names():
    items = [
        {"title": "Nanticoke man arraigned on felony counts", "url": "https://x/1"},
        {"title": "Nanticoke police announce additional charges", "url": "https://x/2"},
        {"title": "Holliston teacher faces exploitation charge", "url": "https://x/3"},
    ]
    clusters = newswire_ai.cluster_items(items, max_clusters=2)
    assert len(clusters) == 2
    largest = max(clusters, key=len)
    assert len(largest) == 2
    assert all("Nanticoke" in item["title"] for item in largest)


def test_pick_cluster_separates_focus_from_rest():
    items = [
        {"title": "Nanticoke man arraigned on felony counts", "url": "https://x/1"},
        {"title": "Nanticoke police announce additional charges", "url": "https://x/2"},
        {"title": "Holliston teacher faces exploitation charge", "url": "https://x/3"},
        {"title": "Portland man sentenced for trafficking", "url": "https://x/4"},
    ]
    focus, rest = newswire_ai.pick_cluster(items)
    assert len(focus) == 2
    assert focus[0]["url"] == "https://x/1"
    assert rest and all(item not in focus for item in rest)


def test_choose_cluster_prefers_an_uncovered_category():
    enforcement = [
        {"title": "Nanticoke man arraigned on felony counts", "url": "https://x/1", "category": "enforcement"},
        {"title": "Nanticoke police announce more charges", "url": "https://x/2", "category": "enforcement"},
        {"title": "Nanticoke court sets hearing date", "url": "https://x/3", "category": "enforcement"},
    ]
    laws = [
        {"title": "Colorado ballot measure on trafficking penalties", "url": "https://x/4", "category": "laws"},
        {"title": "Colorado voters weigh trafficking sentencing", "url": "https://x/5", "category": "laws"},
    ]
    # First pick, nothing written yet: the larger story wins.
    first = newswire_ai.choose_cluster([enforcement, laws], written_categories=set())
    assert first is enforcement

    # Once enforcement is covered, the smaller policy story is picked so the
    # feed is not all arrest reports.
    second = newswire_ai.choose_cluster(
        [enforcement, laws], written_categories={"enforcement"}
    )
    assert second is laws


def test_write_article_needs_two_items_for_one_story(monkeypatch):
    import asyncio

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "newswire_enabled", True)
    single = [{"title": "Nanticoke man arraigned on felony counts", "url": "https://x/1"}]
    assert asyncio.run(newswire_ai.write_article_from_items(single)) is None


def test_write_article_skips_without_key(monkeypatch):
    import asyncio

    monkeypatch.setattr(settings, "llm_api_key", "")
    items = newswire_collect.parse_feed(RSS, {"name": "x", "url": "x"})
    assert asyncio.run(newswire_ai.write_article_from_items(items)) is None


def test_validate_clamps_unknown_category_and_bad_indices():
    parsed = newswire_ai._validate(
        {
            "title": "A valid headline here",
            "dek": "dek",
            "category": "not-a-real-category",
            "tags": ["ok", "<script>"],
            "body": "word " * newswire_ai.MIN_BODY_WORDS,
            "sources": [0, 99, "junk", 1],
        },
        2,
    )
    assert parsed["category"] == "news"
    assert parsed["sourceIndices"] == [0, 1]
    assert "<script>" not in parsed["tags"]


def test_slugify_produces_url_safe_slug():
    assert newswire_ai._slugify("Man, 41, Charged — Child Trafficking!") == (
        "man-41-charged-child-trafficking"
    )
    assert newswire_ai._slugify("***") == "daily-brief"


def test_duplicate_story_detection():
    newswire_store.save_article(
        {
            "slug": "fbi-arrests-two-in-broken-arrow",
            "title": "FBI Arrests Two in Broken Arrow After Years-Long Probe",
            "dek": "d",
            "body": "word " * 200,
            "category": "enforcement",
            "tags": [],
            "sources": [],
        }
    )
    # Rewording of the same event is caught.
    assert newswire_ai.is_duplicate_story(
        "FBI Arrests Two in Broken Arrow Following Years-Long Probe"
    )
    # A different event is not.
    assert not newswire_ai.is_duplicate_story(
        "Colorado Voters Approve Ballot Measure on Trafficking Sentences"
    )
    # Too short to judge is not treated as a duplicate.
    assert not newswire_ai.is_duplicate_story("Probe")


# --- routes -----------------------------------------------------------------


def _seed_article():
    newswire_store.save_article(
        {
            "slug": "test-article",
            "title": "Test article headline",
            "dek": "Dek",
            "body": "Body " * 100,
            "category": "enforcement",
            "tags": ["t"],
            "sources": [{"title": "S", "publisher": "P", "url": "https://example.test/a"}],
            "model": "test",
            "createdAt": "2026-11-04T12:00:00+00:00",
        }
    )


def test_list_returns_summaries_without_body(monkeypatch):
    _seed_article()
    client = _client(monkeypatch)
    res = client.get("/api/newswire")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert "body" not in body["articles"][0]


def test_get_article_by_slug(monkeypatch):
    _seed_article()
    client = _client(monkeypatch)
    res = client.get("/api/newswire/test-article")
    assert res.status_code == 200
    assert res.json()["title"] == "Test article headline"


def test_unknown_or_malformed_slug_is_rejected(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/api/newswire/does-not-exist").status_code == 404
    assert client.get("/api/newswire/Bad_Slug!").status_code == 400


def test_refresh_requires_admin(monkeypatch):
    client = _client(monkeypatch)
    res = client.post("/api/newswire/refresh")
    assert res.status_code == 401
