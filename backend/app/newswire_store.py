"""SQLite storage for the Daily Brief newswire.

Two tables:

* ``news_items`` — one row per collected source headline. Kept as raw material so
  an article can be regenerated and so a source is never fetched/written twice.
* ``news_articles`` — the original article the model wrote, one per story group.

Only the backend reads and writes these tables; the public API serves a curated
projection (see ``app/routes/newswire.py``). Article bodies are stored as
Markdown with a strict allow-list of block types, so the frontend can render
them without an HTML sanitizer.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_initialized = False

# Hard caps: the scheduler writes daily, but a manual refresh must not grow the
# file without bound.
_MAX_ARTICLES = 500
_ARTICLE_PRUNE_TO = 400
_MAX_ITEMS = 5000
_ITEM_PRUNE_TO = 4000


def _db_path() -> Path:
    base = Path(settings.cache_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base / "newswire.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_newswire_db() -> None:
    global _initialized
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS news_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    published_at TEXT,
                    collected_at TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'news',
                    used_in_article TEXT,
                    UNIQUE(url)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS news_articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slug TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    dek TEXT NOT NULL DEFAULT '',
                    body TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'news',
                    tags TEXT NOT NULL DEFAULT '[]',
                    sources TEXT NOT NULL DEFAULT '[]',
                    model TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'published',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_articles_created"
                " ON news_articles (created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_items_collected"
                " ON news_items (collected_at DESC)"
            )
            conn.commit()
            try:
                os.chmod(_db_path(), 0o600)
            except OSError:
                pass
        finally:
            conn.close()
        _initialized = True


def _ensure_initialized() -> None:
    if not _initialized:
        init_newswire_db()


def _row_article(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "slug": row["slug"],
        "title": row["title"],
        "dek": row["dek"],
        "body": row["body"],
        "category": row["category"],
        "tags": _safe_json(row["tags"], []),
        "sources": _safe_json(row["sources"], []),
        "model": row["model"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _safe_json(raw: str, fallback: Any) -> Any:
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return fallback


def _row_item(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "source": row["source"],
        "title": row["title"],
        "url": row["url"],
        "summary": row["summary"],
        "publishedAt": row["published_at"],
        "collectedAt": row["collected_at"],
        "category": row["category"],
    }


# --- items ------------------------------------------------------------------


def save_item(item: dict[str, Any]) -> bool:
    """Insert a collected headline. Returns False when the URL is already known."""
    _ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO news_items
                    (source, title, url, summary, published_at, collected_at, category)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.get("source", "")[:120],
                    item.get("title", "")[:500],
                    item.get("url", "")[:1000],
                    item.get("summary", "")[:2000],
                    item.get("publishedAt"),
                    item.get("collectedAt") or _now(),
                    item.get("category", "news")[:40],
                ),
            )
            inserted = conn.total_changes > 0
            conn.commit()
            return inserted
        finally:
            conn.close()


def recent_items(limit: int = 200) -> list[dict[str, Any]]:
    _ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT * FROM news_items ORDER BY collected_at DESC, id DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()
            return [_row_item(r) for r in rows]
        finally:
            conn.close()


def unused_items(since_hours: int = 48, limit: int = 120) -> list[dict[str, Any]]:
    """Collected headlines not yet woven into an article."""
    _ensure_initialized()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).isoformat()
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                """
                SELECT * FROM news_items
                WHERE used_in_article IS NULL AND collected_at >= ?
                ORDER BY collected_at DESC, id DESC
                LIMIT ?
                """,
                (cutoff, max(1, int(limit))),
            ).fetchall()
            return [_row_item(r) for r in rows]
        finally:
            conn.close()


def mark_items_used(item_ids: list[int], slug: str) -> None:
    if not item_ids:
        return
    _ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            conn.executemany(
                "UPDATE news_items SET used_in_article = ? WHERE id = ?",
                [(slug[:200], int(i)) for i in item_ids],
            )
            conn.commit()
        finally:
            conn.close()


def item_url_exists(url: str) -> bool:
    _ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT 1 FROM news_items WHERE url = ? LIMIT 1", (url[:1000],)
            ).fetchone()
            return row is not None
        finally:
            conn.close()


# --- articles ---------------------------------------------------------------


def save_article(article: dict[str, Any]) -> dict[str, Any] | None:
    """Insert an article. Returns the stored row, or None if the slug exists."""
    _ensure_initialized()
    now = _now()
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO news_articles
                    (slug, title, dek, body, category, tags, sources, model,
                     status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article["slug"][:200],
                    article["title"][:300],
                    article.get("dek", "")[:600],
                    article["body"],
                    article.get("category", "news")[:40],
                    json.dumps(article.get("tags", [])[:12]),
                    json.dumps(article.get("sources", [])[:20]),
                    article.get("model", "")[:120],
                    article.get("status", "published")[:20],
                    article.get("createdAt") or now,
                    now,
                ),
            )
            inserted = cur.rowcount > 0
            conn.commit()
            if not inserted:
                return None
            row = conn.execute(
                "SELECT * FROM news_articles WHERE slug = ?", (article["slug"][:200],)
            ).fetchone()
            _prune_articles(conn)
            return _row_article(row) if row else None
        finally:
            conn.close()


def update_article_body(slug: str, **fields: Any) -> None:
    allowed = {
        "title",
        "dek",
        "body",
        "category",
        "tags",
        "sources",
        "status",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    _ensure_initialized()
    sets = ", ".join(f"{key} = ?" for key in updates)
    values: list[Any] = []
    for key, value in updates.items():
        if key in ("tags", "sources"):
            values.append(json.dumps(value))
        else:
            values.append(value)
    values.extend([_now(), slug])
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                f"UPDATE news_articles SET {sets}, updated_at = ? WHERE slug = ?",
                values,
            )
            conn.commit()
        finally:
            conn.close()


def _prune_articles(conn: sqlite3.Connection) -> None:
    count = conn.execute("SELECT COUNT(*) AS n FROM news_articles").fetchone()["n"]
    if count <= _MAX_ARTICLES:
        return
    keep = conn.execute(
        "SELECT id FROM news_articles ORDER BY created_at DESC LIMIT ?",
        (_ARTICLE_PRUNE_TO,),
    ).fetchall()
    keep_ids = [r["id"] for r in keep]
    if not keep_ids:
        return
    placeholders = ",".join("?" for _ in keep_ids)
    conn.execute(
        f"DELETE FROM news_articles WHERE id NOT IN ({placeholders})", keep_ids
    )
    conn.commit()


def prune_items() -> int:
    """Keep the raw item table bounded. Returns rows removed."""
    _ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            count = conn.execute("SELECT COUNT(*) AS n FROM news_items").fetchone()["n"]
            if count <= _MAX_ITEMS:
                return 0
            keep = conn.execute(
                "SELECT id FROM news_items ORDER BY collected_at DESC LIMIT ?",
                (_ITEM_PRUNE_TO,),
            ).fetchall()
            keep_ids = [r["id"] for r in keep]
            if not keep_ids:
                return 0
            placeholders = ",".join("?" for _ in keep_ids)
            before = conn.execute("SELECT COUNT(*) AS n FROM news_items").fetchone()["n"]
            conn.execute(
                f"DELETE FROM news_items WHERE id NOT IN ({placeholders})", keep_ids
            )
            conn.commit()
            after = conn.execute("SELECT COUNT(*) AS n FROM news_items").fetchone()["n"]
            return int(before - after)
        finally:
            conn.close()


def list_articles(limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
    _ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                """
                SELECT * FROM news_articles WHERE status = 'published'
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (max(1, int(limit)), max(0, int(offset))),
            ).fetchall()
            return [_row_article(r) for r in rows]
        finally:
            conn.close()


def list_articles_summary(limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
    """Feed rows without the full body, for list pages and the API index."""
    _ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                """
                SELECT id, slug, title, dek, category, tags, sources, created_at
                FROM news_articles WHERE status = 'published'
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (max(1, int(limit)), max(0, int(offset))),
            ).fetchall()
            return [
                {
                    "id": r["id"],
                    "slug": r["slug"],
                    "title": r["title"],
                    "dek": r["dek"],
                    "category": r["category"],
                    "tags": _safe_json(r["tags"], []),
                    "sources": _safe_json(r["sources"], []),
                    "createdAt": r["created_at"],
                }
                for r in rows
            ]
        finally:
            conn.close()


def get_article(slug: str) -> dict[str, Any] | None:
    _ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT * FROM news_articles WHERE slug = ? AND status = 'published'",
                (slug[:200],),
            ).fetchone()
            return _row_article(row) if row else None
        finally:
            conn.close()


def count_articles() -> int:
    _ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            return int(
                conn.execute("SELECT COUNT(*) AS n FROM news_articles").fetchone()["n"]
            )
        finally:
            conn.close()


def stats() -> dict[str, Any]:
    _ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            articles = conn.execute(
                "SELECT COUNT(*) AS n FROM news_articles"
            ).fetchone()["n"]
            items = conn.execute("SELECT COUNT(*) AS n FROM news_items").fetchone()["n"]
            unused = conn.execute(
                "SELECT COUNT(*) AS n FROM news_items WHERE used_in_article IS NULL"
            ).fetchone()["n"]
            latest = conn.execute(
                "SELECT created_at FROM news_articles ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            last_item = conn.execute(
                "SELECT collected_at FROM news_items ORDER BY collected_at DESC LIMIT 1"
            ).fetchone()
            return {
                "articles": int(articles),
                "items": int(items),
                "unusedItems": int(unused),
                "latestArticleAt": latest["created_at"] if latest else None,
                "lastCollectedAt": last_item["collected_at"] if last_item else None,
            }
        finally:
            conn.close()


def reset_for_tests() -> None:
    """Drop the memoized init flag so a new CACHE_DIR takes effect."""
    global _initialized
    with _lock:
        _initialized = False
