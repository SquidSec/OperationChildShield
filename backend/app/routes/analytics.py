"""Page-view and action ingest. Public read is aggregate impact only."""

from __future__ import annotations

import asyncio
import re

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app.analytics_store import CLIENT_ACTIONS, get_impact_counts, record_action, record_page_view
from app.bot_filter import RateTracker, classify, is_asset_path, is_probe_path
from app.security import client_ip, rate_limit

router = APIRouter()

_PATH_RE = re.compile(r"^/[A-Za-z0-9/_\-.%~]*$")

# One instance-wide counter for the "too fast to be a person" signal.
_RATE = RateTracker(limit=60, window_seconds=60.0)


class PageViewEvent(BaseModel):
    path: str = Field(..., min_length=1, max_length=500)
    referrer: str = Field(default="", max_length=500)
    action: str = Field(default="", max_length=40)

    @field_validator("path", "referrer", "action")
    @classmethod
    def strip_fields(cls, value: str) -> str:
        return (value or "").strip()


def _valid_path(path: str) -> bool:
    return bool(path.startswith("/") and not path.startswith("//") and _PATH_RE.match(path))


@router.post("/analytics/event")
async def track_page_view(body: PageViewEvent, request: Request):
    """Record a page view or allow-listed public action. No raw-event read API."""
    rate_limit(
        client_ip(request),
        bucket="analytics",
        max_hits=120,
        window_seconds=60.0,
        detail="Too many analytics events",
    )

    path = body.path
    if not _valid_path(path):
        raise HTTPException(status_code=400, detail="Invalid path")

    action = body.action.lower()
    if action and action != "page_view":
        if action not in CLIENT_ACTIONS:
            raise HTTPException(status_code=400, detail="Invalid action")
        await asyncio.to_thread(record_action, action, path=path)
        return {"ok": True, "action": action}

    lower = path.lower()
    if (
        lower.startswith("/api/")
        or lower.startswith("/_next/")
        or is_asset_path(lower)
    ):
        return {"ok": True, "skipped": True}

    # Probes never render a page, so they are not visitor traffic at all.
    if is_probe_path(lower):
        return {"ok": True, "skipped": True}

    ip = client_ip(request)
    ua = request.headers.get("user-agent", "")

    # Classify before storing. The row is still written, tagged with a reason,
    # so the filter can be audited and rules can be re-run over history.
    verdict = classify(
        ua,
        headers=dict(request.headers),
        rate_exceeded=_RATE.exceeded(ip, ua),
        datacenter_org=request.headers.get("x-datacenter-org", ""),
    )

    # sqlite3 is blocking; keep it off the event loop.
    await asyncio.to_thread(
        record_page_view,
        path,
        referrer=body.referrer or None,
        user_agent=ua,
        is_bot=verdict.is_bot,
        bot_reason=verdict.reason,
    )
    # Do not tell a bot it was filtered; a plain success keeps probes quiet.
    return {"ok": True}


@router.get("/impact")
async def site_impact(request: Request):
    """Aggregate counts only — no paths, referrers, or other raw events."""
    rate_limit(
        client_ip(request),
        bucket="impact",
        max_hits=60,
        window_seconds=60.0,
        detail="Too many impact requests",
    )
    return await asyncio.to_thread(get_impact_counts)
