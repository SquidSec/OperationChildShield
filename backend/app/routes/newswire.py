"""Public read API for the Daily Brief newswire, plus an admin-only refresh.

Read endpoints are unauthenticated: the articles are public journalism. The
refresh endpoint costs money (it calls a model), so it requires an admin
session and is rate limited.
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, HTTPException, Query, Request

from app import newswire_collect, newswire_store
from app.admin_auth import current_admin
from app.security import client_ip, rate_limit

logger = logging.getLogger(__name__)
router = APIRouter()

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_LIMIT = 50


def validate_slug(slug: str) -> str:
    value = (slug or "").strip().lower()
    if not _SLUG_RE.match(value) or len(value) > 200:
        raise HTTPException(status_code=400, detail="Invalid article id")
    return value


@router.get("/newswire")
def list_newswire(
    limit: int = Query(default=20, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0, le=10_000),
):
    """Newest-first article index without article bodies."""
    return {
        "articles": newswire_store.list_articles_summary(limit=limit, offset=offset),
        "total": newswire_store.count_articles(),
        "limit": limit,
        "offset": offset,
    }


@router.get("/newswire/status")
def newswire_status():
    return newswire_store.stats()


@router.get("/newswire/{slug}")
def get_newswire_article(slug: str):
    article = newswire_store.get_article(validate_slug(slug))
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.post("/newswire/refresh")
async def refresh_newswire(request: Request, write: bool = Query(default=True)):
    """Collect feeds now, and optionally write new articles.

    Admin-only: writing an article costs a model call. ``write=false`` collects
    only, which is useful for checking a feed without publishing anything.
    """
    current_admin(request)
    rate_limit(
        client_ip(request),
        bucket="newswire_refresh",
        max_hits=6,
        window_seconds=3600,
        detail="Newswire refresh is limited to 6 runs per hour.",
    )

    try:
        from app import newswire_ai

        if write:
            summary = await newswire_ai.run_daily(collect=True)
        else:
            summary = {
                "collected": await newswire_collect.collect(),
                "articlesWritten": 0,
                "slugs": [],
                "errors": [],
            }
    except Exception as exc:  # noqa: BLE001 - report, do not 500 the admin
        logger.exception("Newswire refresh failed")
        raise HTTPException(status_code=502, detail=f"Refresh failed: {exc}") from exc

    return {"ok": True, "summary": summary, "status": newswire_store.stats()}
