"""Verify tracked bills against Congress.gov and resolve official titles."""

from __future__ import annotations

import logging
from typing import Any

from app.bills import TRACKED_BILLS, TrackedBill
from app.congress_client import CongressClient

logger = logging.getLogger(__name__)

_official_titles: dict[str, str] = {}


async def fetch_official_bill(
    client: CongressClient, bill: TrackedBill
) -> dict[str, Any]:
    return await client.get_bill(bill.congress, bill.bill_type, bill.number)


async def get_official_title(client: CongressClient, bill: TrackedBill) -> str:
    cached = _official_titles.get(bill.bill_id)
    if cached:
        return cached

    official = await fetch_official_bill(client, bill)
    title = (official.get("title") or bill.title).strip()
    _official_titles[bill.bill_id] = title
    return title


async def verify_tracked_bill(
    client: CongressClient, bill: TrackedBill
) -> dict[str, Any]:
    official = await fetch_official_bill(client, bill)
    api_title = (official.get("title") or "").strip()
    api_congress = official.get("congress")
    configured = bill.title.strip()

    congress_ok = api_congress == bill.congress
    title_ok = configured == api_title

    if api_title:
        _official_titles[bill.bill_id] = api_title

    return {
        "bill_id": bill.bill_id,
        "congress": bill.congress,
        "bill_type": bill.bill_type,
        "number": bill.number,
        "configured_title": configured,
        "official_title": api_title,
        "official_congress": api_congress,
        "congress_url": bill.congress_url,
        "title_match": title_ok,
        "congress_match": congress_ok,
        "verified": title_ok and congress_ok and bool(api_title),
    }


async def verify_all_tracked_bills(client: CongressClient) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for bill in TRACKED_BILLS:
        results.append(await verify_tracked_bill(client, bill))
    return results


async def log_bill_verification(client: CongressClient) -> None:
    results = await verify_all_tracked_bills(client)
    failures = [r for r in results if not r["verified"]]

    for result in results:
        if result["verified"]:
            logger.info(
                "Bill verified: %s %s %s - %s",
                result["congress"],
                result["bill_type"],
                result["number"],
                result["official_title"],
            )
        else:
            logger.error(
                "Bill mismatch: %s %s %s configured=%r official=%r congress=%s official_congress=%s",
                result["congress"],
                result["bill_type"],
                result["number"],
                result["configured_title"],
                result["official_title"],
                result["congress"],
                result["official_congress"],
            )

    if failures:
        # Log loudly but keep serving: a Congress.gov outage or upstream title
        # edit must not take the whole site down.
        logger.error(
            "%d tracked bill(s) failed Congress.gov verification: %s",
            len(failures),
            ", ".join(f"{r['congress']} {r['bill_type']} {r['number']}" for r in failures),
        )