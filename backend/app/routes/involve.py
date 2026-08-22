"""Volunteer / get-involved signup capture (local file storage)."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app.analytics_store import record_action
from app.config import settings
from app.email_smtp import auto_reply_involve_signup, notify_involve_signup
from app.security import client_ip, rate_limit

logger = logging.getLogger(__name__)
router = APIRouter()

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Cap signup file growth (bytes) to resist disk-fill abuse.
_MAX_SIGNUP_FILE_BYTES = 5 * 1024 * 1024  # 5 MiB


class InvolveSignupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: str = Field(..., min_length=3, max_length=254)
    state: str = Field(default="", max_length=64)
    interest: str = Field(default="", max_length=64)
    message: str = Field(default="", max_length=2000)
    consent: bool = False
    # Honeypot - real users leave blank; bots often fill it.
    website: str = Field(default="", max_length=200)

    @field_validator("name", "email", "state", "interest", "message", "website")
    @classmethod
    def strip_strings(cls, value: str) -> str:
        return (value or "").strip()

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if not _EMAIL_RE.match(value):
            raise ValueError("Invalid email address")
        return value.lower()


def _signup_path() -> Path:
    base = Path(settings.cache_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base / "involve_signups.jsonl"


def _ensure_private_file(path: Path) -> None:
    """Create or tighten permissions so signup PII is not world-readable."""
    if not path.exists():
        path.touch(mode=0o600)
    else:
        try:
            os.chmod(path, 0o600)
        except OSError:
            logger.warning("Could not chmod signup file to 0600")


@router.post("/involve")
async def submit_involve_signup(body: InvolveSignupRequest, request: Request):
    # Silent success for honeypot traps so bots don't learn the field.
    if body.website:
        logger.info("Involve honeypot triggered from %s", client_ip(request))
        return {"ok": True, "message": "Thank you for signing up."}

    if not body.consent:
        raise HTTPException(
            status_code=400,
            detail="Consent is required to submit this form.",
        )

    rate_limit(
        client_ip(request),
        bucket="involve",
        max_hits=8,
        window_seconds=3600.0,
        detail="Too many signup attempts. Please try again later.",
    )

    allowed_interests = {
        "",
        "volunteer",
        "advocacy",
        "media",
        "partner",
        "other",
    }
    interest = body.interest.lower()
    if interest not in allowed_interests:
        interest = "other"

    record = {
        "submittedAt": datetime.now(timezone.utc).isoformat(),
        "name": body.name,
        "email": body.email,
        "state": body.state,
        "interest": interest,
        "message": body.message,
        "source": "get-involved",
    }

    path = _signup_path()
    try:
        if path.exists() and path.stat().st_size >= _MAX_SIGNUP_FILE_BYTES:
            logger.error("Involve signup file at size cap (%s bytes)", _MAX_SIGNUP_FILE_BYTES)
            raise HTTPException(
                status_code=503,
                detail="Unable to save signup right now. Please email Contact@OperationChildShield.com.",
            )
        _ensure_private_file(path)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    except HTTPException:
        raise
    except OSError:
        logger.exception("Failed to persist involve signup")
        raise HTTPException(
            status_code=503,
            detail="Unable to save signup right now. Please email Contact@OperationChildShield.com.",
        )

    logger.info(
        "Involve signup saved interest=%s state=%s",
        interest or "none",
        body.state or "none",
    )

    try:
        record_action("involve_signup", path="/get-involved")
    except Exception:
        logger.exception("Failed to record involve signup action")

    # Email ops (+ optional auto-reply). Persistence already succeeded; do not fail
    # the HTTP response if SMTP is down — signups stay in involve_signups.jsonl.
    try:
        if notify_involve_signup(record):
            logger.info("Involve signup emailed to notify inbox")
    except Exception:
        logger.exception("Failed to email involve notify")

    try:
        if auto_reply_involve_signup(record):
            logger.info("Involve auto-reply sent to submitter")
    except Exception:
        logger.exception("Failed to send involve auto-reply")

    return {
        "ok": True,
        "message": "Thank you. We received your signup and will follow up.",
    }
