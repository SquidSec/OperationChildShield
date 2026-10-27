"""SQLite-backed page-view and action storage. Public read is aggregates only."""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
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
                    user_agent TEXT,
                    -- Automated traffic is stored, not discarded, so filtering can
                    -- be audited and rules can be re-run over history.
                    is_bot INTEGER NOT NULL DEFAULT 0,
                    bot_reason TEXT NOT NULL DEFAULT ''
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
            _migrate_page_view_columns(conn)
            conn.commit()
            _initialized = True
        finally:
            conn.close()
        _harden_db_file()


def _migrate_page_view_columns(conn: sqlite3.Connection) -> None:
    """Add bot columns to databases created before filtering existed."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(page_views)")}
    if "is_bot" not in existing:
        conn.execute("ALTER TABLE page_views ADD COLUMN is_bot INTEGER NOT NULL DEFAULT 0")
    if "bot_reason" not in existing:
        conn.execute("ALTER TABLE page_views ADD COLUMN bot_reason TEXT NOT NULL DEFAULT ''")


def ensure_initialized() -> None:
    if not _initialized:
        init_analytics_db()


def _retention_cutoff() -> str | None:
    days = settings.analytics_retention_days
    if days <= 0:
        return None
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _prune_expired(conn: sqlite3.Connection) -> None:
    """Drop rows older than the retention window (raw UA/referrer are personal data)."""
    cutoff = _retention_cutoff()
    if cutoff is None:
        return
    deleted = conn.execute("DELETE FROM page_views WHERE viewed_at < ?", (cutoff,)).rowcount
    deleted_actions = conn.execute(
        "DELETE FROM action_events WHERE created_at < ?", (cutoff,)
    ).rowcount
    if deleted or deleted_actions:
        logger.info(
            "Pruned analytics rows past retention: page_views=%s action_events=%s",
            deleted,
            deleted_actions,
        )
    conn.commit()


def _maybe_prune(conn: sqlite3.Connection) -> None:
    _prune_expired(conn)
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
    is_bot: bool = False,
    bot_reason: str = "",
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
                INSERT INTO page_views
                    (path, viewed_at, referrer, user_agent, is_bot, bot_reason)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (clean_path, iso, ref, ua, 1 if is_bot else 0, (bot_reason or "")[:40]),
            )
            conn.commit()
            _maybe_prune(conn)
        finally:
            conn.close()
        _harden_db_file()


def _maybe_prune_actions(conn: sqlite3.Connection) -> None:
    _prune_expired(conn)
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


def _traffic_since(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 365)))


def _referrer_domain(referrer: str | None) -> str | None:
    if not referrer:
        return None
    from urllib.parse import urlsplit

    try:
        host = urlsplit(referrer).hostname or ""
    except ValueError:
        return None
    host = host.lower().lstrip(".")
    if not host or host.startswith("localhost"):
        return None
    # Collapse our own pages into one bucket so internal navigation is obvious.
    if host.endswith("operationchildshield.org"):
        return "operationchildshield.org"
    return host[:120]


# Admin pages are excluded from visitor metrics. These are complete literal
# queries (no interpolation) so query text can never include request input.
_COUNT_VIEWS_SQL = (
    "SELECT COUNT(*) FROM page_views "
    "WHERE viewed_at >= ? AND path NOT LIKE '/admin%' AND is_bot = 0"
)
_COUNT_PREVIOUS_VIEWS_SQL = (
    "SELECT COUNT(*) FROM page_views "
    "WHERE viewed_at >= ? AND viewed_at < ? AND path NOT LIKE '/admin%' AND is_bot = 0"
)
_DAILY_VIEWS_SQL = (
    "SELECT substr(viewed_at, 1, 10) AS day, COUNT(*) AS views "
    "FROM page_views WHERE viewed_at >= ? AND path NOT LIKE '/admin%' AND is_bot = 0 "
    "GROUP BY day ORDER BY day ASC"
)
_TOP_PAGES_SQL = (
    "SELECT path, COUNT(*) AS views FROM page_views "
    "WHERE viewed_at >= ? AND path NOT LIKE '/admin%' AND is_bot = 0 "
    "GROUP BY path ORDER BY views DESC, path ASC LIMIT 10"
)
_REFERRERS_SQL = (
    "SELECT referrer, COUNT(*) AS views FROM page_views "
    "WHERE viewed_at >= ? AND path NOT LIKE '/admin%' AND is_bot = 0 "
    "AND referrer IS NOT NULL AND referrer != '' GROUP BY referrer"
)
_COUNT_BOTS_SQL = (
    "SELECT COUNT(*) FROM page_views "
    "WHERE viewed_at >= ? AND path NOT LIKE '/admin%' AND is_bot = 1"
)
_BOT_REASON_SQL = (
    "SELECT bot_reason, COUNT(*) AS count FROM page_views "
    "WHERE viewed_at >= ? AND path NOT LIKE '/admin%' AND is_bot = 1 "
    "GROUP BY bot_reason ORDER BY count DESC"
)
_ACTION_COUNTS_SQL = (
    "SELECT name, COUNT(*) AS count FROM action_events "
    "WHERE created_at >= ? GROUP BY name"
)


def get_traffic_overview(days: int = 30) -> dict[str, object]:
    """Aggregate traffic for the admin dashboard. Never returns raw rows."""
    days = max(1, min(int(days or 30), 365))
    since = _traffic_since(days).isoformat()
    ensure_initialized()

    with _lock:
        conn = _connect()
        try:
            total_views = int(conn.execute(_COUNT_VIEWS_SQL, (since,)).fetchone()[0])
            previous_since = (datetime.now(timezone.utc) - timedelta(days=days * 2)).isoformat()
            previous_views = int(
                conn.execute(
                    _COUNT_PREVIOUS_VIEWS_SQL, (previous_since, since)
                ).fetchone()[0]
            )

            daily = {
                row["day"]: int(row["views"])
                for row in conn.execute(_DAILY_VIEWS_SQL, (since,)).fetchall()
            }

            top_pages = [
                {"path": row["path"], "views": int(row["views"])}
                for row in conn.execute(_TOP_PAGES_SQL, (since,)).fetchall()
            ]

            referrers: dict[str, int] = {}
            for row in conn.execute(_REFERRERS_SQL, (since,)).fetchall():
                domain = _referrer_domain(row["referrer"])
                if domain:
                    referrers[domain] = referrers.get(domain, 0) + int(row["views"])
            top_referrers = [
                {"domain": domain, "views": views}
                for domain, views in sorted(
                    referrers.items(), key=lambda item: (-item[1], item[0])
                )[:10]
            ]

            actions = {
                row["name"]: int(row["count"])
                for row in conn.execute(_ACTION_COUNTS_SQL, (since,)).fetchall()
            }

            # Filtered traffic is reported, not hidden, so the filter is auditable.
            bot_total = int(
                conn.execute(_COUNT_BOTS_SQL, (since,)).fetchone()[0]
            )
            bot_reasons = [
                {"reason": row["bot_reason"] or "unknown", "count": int(row["count"])}
                for row in conn.execute(_BOT_REASON_SQL, (since,)).fetchall()
            ]

            return {
                "days": days,
                "since": since,
                "generatedAt": datetime.now(timezone.utc).isoformat(),
                "pageViews": total_views,
                "botPageViews": bot_total,
                "botReasons": bot_reasons,
                "previousPageViews": previous_views,
                "daily": [
                    {"date": day, "views": daily.get(day, 0)}
                    for day in _date_range(days)
                ],
                "topPages": top_pages,
                "topReferrers": top_referrers,
                "actions": {
                    "share": int(actions.get("share", 0)),
                    "contactCongress": int(actions.get("contact_congress", 0)),
                    "signups": int(actions.get("involve_signup", 0)),
                },
            }
        finally:
            conn.close()


def _date_range(days: int) -> list[str]:
    today = datetime.now(timezone.utc).date()
    return [
        (today - timedelta(days=offset)).isoformat()
        for offset in range(days - 1, -1, -1)
    ]


def reclassify_page_views(batch: int = 5000) -> dict[str, int]:
    """Re-run the bot classifier over stored human rows.

    Widening the rules should apply to history, otherwise old bot traffic keeps
    inflating the numbers until it ages out. Only rows currently counted as human
    are considered; an existing bot row keeps its original classification.
    """
    from app.bot_filter import classify

    ensure_initialized()
    promoted = 0
    checked = 0
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT id, user_agent FROM page_views WHERE is_bot = 0 LIMIT ?",
                (max(1, batch),),
            ).fetchall()
            updates: list[tuple[str, int]] = []
            for row in rows:
                checked += 1
                verdict = classify(row["user_agent"], headers=None)
                if verdict.is_bot:
                    updates.append((verdict.reason, int(row["id"])))
            if updates:
                conn.executemany(
                    "UPDATE page_views SET is_bot = 1, bot_reason = ? WHERE id = ?",
                    updates,
                )
                promoted = len(updates)
            conn.commit()
        finally:
            conn.close()
    if promoted:
        logger.info("Reclassified page views as bots: %s of %s", promoted, checked)
    return {"checked": checked, "promoted": promoted}


def prune_expired_now() -> dict[str, int]:
    """Run retention pruning on demand (used by the background scheduler)."""
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            cutoff = _retention_cutoff()
            if cutoff is None:
                return {"page_views": 0, "action_events": 0}
            views = conn.execute("DELETE FROM page_views WHERE viewed_at < ?", (cutoff,)).rowcount
            actions = conn.execute(
                "DELETE FROM action_events WHERE created_at < ?", (cutoff,)
            ).rowcount
            conn.commit()
            if views or actions:
                logger.info("Scheduled prune: page_views=%s action_events=%s", views, actions)
            return {"page_views": int(views), "action_events": int(actions)}
        finally:
            conn.close()


def storage_stats() -> dict[str, object]:
    """Row counts and the oldest retained timestamp, for the admin health panel."""
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            views = int(conn.execute("SELECT COUNT(*) FROM page_views").fetchone()[0])
            actions = int(conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0])
            oldest = conn.execute("SELECT MIN(viewed_at) FROM page_views").fetchone()[0]
            return {
                "pageViewRows": views,
                "actionEventRows": actions,
                "oldestPageView": oldest,
            }
        finally:
            conn.close()


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
