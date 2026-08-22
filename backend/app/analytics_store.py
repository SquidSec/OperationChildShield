"""SQLite-backed page-view and action storage. Public read is aggregates only."""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_initialized = False

# Soft caps to resist unbounded disk growth from open write endpoint.
_MAX_PAGE_VIEWS = 500_000
_PRUNE_TO = 400_000
_MAX_ACTION_EVENTS = 200_000
_ACTION_PRUNE_TO = 160_000

CLIENT_ACTIONS = frozenset({"share", "contact_congress"})
SERVER_ACTIONS = frozenset({"involve_signup"})
ALLOWED_ACTIONS = CLIENT_ACTIONS | SERVER_ACTIONS


def _db_path() -> Path:
    base = Path(settings.cache_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base / "analytics.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _harden_db_file() -> None:
    path = _db_path()
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def init_analytics_db() -> None:
    global _initialized
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS page_views (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL,
                    viewed_at TEXT NOT NULL,
                    referrer TEXT,
                    user_agent TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_page_views_viewed_at ON page_views(viewed_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_page_views_path ON page_views(path)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS action_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    path TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_action_events_name ON action_events(name)"
            )
            conn.commit()
            _initialized = True
        finally:
            conn.close()
        _harden_db_file()


def ensure_initialized() -> None:
    if not _initialized:
        init_analytics_db()


def _maybe_prune(conn: sqlite3.Connection) -> None:
    count = conn.execute("SELECT COUNT(*) FROM page_views").fetchone()[0]
    if count <= _MAX_PAGE_VIEWS:
        return
    # Keep the newest rows; delete oldest overflow.
    to_delete = count - _PRUNE_TO
    logger.warning("Pruning analytics page_views: deleting ~%s oldest rows", to_delete)
    conn.execute(
        """
        DELETE FROM page_views
        WHERE id IN (
            SELECT id FROM page_views ORDER BY viewed_at ASC, id ASC LIMIT ?
        )
        """,
        (to_delete,),
    )
    conn.commit()


def record_page_view(
    path: str,
    *,
    referrer: str | None = None,
    user_agent: str | None = None,
    viewed_at: datetime | None = None,
) -> None:
    ensure_initialized()
    clean_path = (path or "/").strip() or "/"
    if len(clean_path) > 500:
        clean_path = clean_path[:500]
    if not clean_path.startswith("/") or clean_path.startswith("//"):
        clean_path = "/"

    ref = (referrer or "").strip()[:500] or None
    ua = (user_agent or "").strip()[:300] or None
    ts = (viewed_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    iso = ts.isoformat()

    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO page_views (path, viewed_at, referrer, user_agent)
                VALUES (?, ?, ?, ?)
                """,
                (clean_path, iso, ref, ua),
            )
            conn.commit()
            _maybe_prune(conn)
        finally:
            conn.close()
        _harden_db_file()


def _maybe_prune_actions(conn: sqlite3.Connection) -> None:
    count = conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0]
    if count <= _MAX_ACTION_EVENTS:
        return
    to_delete = count - _ACTION_PRUNE_TO
    logger.warning("Pruning analytics action_events: deleting ~%s oldest rows", to_delete)
    conn.execute(
        """
        DELETE FROM action_events
        WHERE id IN (
            SELECT id FROM action_events ORDER BY created_at ASC, id ASC LIMIT ?
        )
        """,
        (to_delete,),
    )
    conn.commit()


def record_action(
    name: str,
    *,
    path: str | None = None,
    created_at: datetime | None = None,
) -> bool:
    action = (name or "").strip().lower()
    if action not in ALLOWED_ACTIONS:
        return False

    ensure_initialized()
    clean_path = (path or "/").strip() or "/"
    if len(clean_path) > 500:
        clean_path = clean_path[:500]
    if not clean_path.startswith("/") or clean_path.startswith("//"):
        clean_path = "/"

    ts = (created_at or datetime.now(timezone.utc)).astimezone(timezone.utc)

    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO action_events (name, path, created_at)
                VALUES (?, ?, ?)
                """,
                (action, clean_path, ts.isoformat()),
            )
            conn.commit()
            _maybe_prune_actions(conn)
        finally:
            conn.close()
        _harden_db_file()
    return True


def get_impact_counts() -> dict[str, int | str]:
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            page_views = conn.execute("SELECT COUNT(*) FROM page_views").fetchone()[0]

            def count_action(action_name: str) -> int:
                return int(
                    conn.execute(
                        "SELECT COUNT(*) FROM action_events WHERE name = ?",
                        (action_name,),
                    ).fetchone()[0]
                )

            return {
                "pageViews": int(page_views),
                "shares": count_action("share"),
                "congressContacts": count_action("contact_congress"),
                "signups": count_action("involve_signup"),
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            }
        finally:
            conn.close()

