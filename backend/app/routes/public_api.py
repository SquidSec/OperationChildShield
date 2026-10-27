"""Read-only public API for third parties.

Requires a per-consumer API key (``X-API-Key``) and is disabled entirely until
keys are configured via ``PUBLIC_API_KEYS``. Reuses the same service layer and
serialization as the internal routes so the payloads cannot drift apart.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Header, HTTPException, Query, Request

from app.config import settings
from app.security import (
    rate_limit,
    safe_service_error,
    safe_upstream_error,
    validate_congress,
)
from app.services import build_directory, get_bills_summary

router = APIRouter(prefix="/public/v1", tags=["public"])

_UNAUTHORIZED_MESSAGE = (
    "A valid API key is required. Send it in the X-API-Key header. "
    "Request access at Contact@OperationChildShield.org."
)


def require_api_key(x_api_key: str | None = Header(default=None)) -> str:
    """Validate the API key, returning the canonical key for quota buckets."""
    configured = settings.public_api_key_list
    if not configured:
        raise HTTPException(
            status_code=503,
            detail="Public API is not enabled",
        )
    presented = (x_api_key or "").strip()
    if not presented:
        raise HTTPException(status_code=401, detail=_UNAUTHORIZED_MESSAGE)
    for key in configured:
        if secrets.compare_digest(presented, key):
            return key
    raise HTTPException(status_code=401, detail=_UNAUTHORIZED_MESSAGE)


def _enforce_quota(key: str) -> None:
    rate_limit(
        key,
        bucket=f"public_api:{key}",
        max_hits=settings.public_api_rate_limit_per_hour,
        window_seconds=3600.0,
        detail="Hourly API quota exceeded for this key. Please retry later.",
    )


@router.get("/members")
async def public_list_members(
    request: Request,
    x_api_key: str | None = Header(default=None),
    search: str | None = Query(None, max_length=120, description="Search by name or state"),
    chamber: str | None = Query(None, max_length=32, description="House or Senate"),
    state: str | None = Query(None, max_length=64, description="State name or abbreviation"),
    party: str | None = Query(None, max_length=64, description="Party name filter"),
    congress: int | None = Query(None),
    limit: int | None = Query(None, ge=1, le=250, description="Max members to return"),
    offset: int = Query(0, ge=0, le=10_000, description="Pagination offset"),
):
    key = require_api_key(x_api_key)
    _enforce_quota(key)

    client = request.app.state.congress_client
    congress_num = validate_congress(congress, settings.congress_number)

    try:
        members, total = await build_directory(
            client,
            congress_num,
            search=search,
            chamber=chamber,
            state=state,
            party=party,
            limit=limit,
            offset=offset,
        )
    except ValueError as e:
        raise safe_service_error(e)
    except Exception as e:
        raise safe_upstream_error(e, public_message="Unable to load members")

    return {
        "members": members,
        "total": total,
        "limit": limit,
        "offset": offset,
        "congress": congress_num,
    }


@router.get("/bills")
async def public_list_bills(
    request: Request,
    x_api_key: str | None = Header(default=None),
):
    key = require_api_key(x_api_key)
    _enforce_quota(key)

    client = request.app.state.congress_client
    try:
        bills = await get_bills_summary(client)
    except ValueError as e:
        raise safe_service_error(e)
    except Exception as e:
        raise safe_upstream_error(e, public_message="Unable to load tracked bills")

    return {"bills": bills, "congress": settings.congress_number}
