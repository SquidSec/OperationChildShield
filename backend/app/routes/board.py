"""Board / officer applications (e.g. the open Vice President seat).

Applications are stored as JSONL under CACHE_DIR and emailed to the ops inbox.
Every submission must pass a Cloudflare Turnstile check, so this open form
cannot be used to spam the inbox or fill the disk.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app.captcha import verify_turnstile
from app.config import settings
from app.sanitize import clean_text, sanitize_application
from app.email_smtp import send_plain_email
from app.security import client_ip, rate_limit

logger = logging.getLogger(__name__)
router = APIRouter()

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Same cap as the involve form so a public form cannot fill the volume.
_MAX_APPLICATION_FILE_BYTES = 5 * 1024 * 1024

ROLE_LABELS = {
    "vice-president": "Vice President",
}


class ApplicationRequest(BaseModel):
    role: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=1, max_length=120)
    email: str = Field(..., min_length=3, max_length=254)
    phone: str = Field(default="", max_length=40)
    location: str = Field(default="", max_length=120)
    linkedin: str = Field(default="", max_length=200)
    statement: str = Field(..., min_length=1, max_length=4000)
    consent: bool = False
    captcha_token: str = Field(default="", max_length=4096)
    # Honeypot: real applicants leave this blank.
    website: str = Field(default="", max_length=200)

    @field_validator(
        "role", "name", "email", "phone", "location", "linkedin",
        "statement", "captcha_token", "website",
    )
    @classmethod
    def strip_strings(cls, value: str) -> str:
        return (value or "").strip()

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if not _EMAIL_RE.match(value):
            raise ValueError("Invalid email address")
        return value.lower()


def _application_path() -> Path:
    base = Path(settings.cache_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base / "board_applications.jsonl"


def _ensure_private_file(path: Path) -> None:
    if not path.exists():
        path.touch(mode=0o600)
    else:
        try:
            os.chmod(path, 0o600)
        except OSError:
            logger.warning("Could not chmod application file to 0600")


def _notify_application(record: dict[str, object]) -> None:
    to = (settings.involve_notify_to or settings.smtp_user or "").strip()
    if not to or not settings.smtp_configured:
        logger.info("Board application stored (SMTP not configured; no email sent)")
        return
    body = (
        "New board application\n\n"
        f"Role: {record['roleLabel']}\n"
        f"Name: {record['name']}\n"
        f"Email: {record['email']}\n"
        f"Phone: {record['phone'] or '(not provided)'}\n"
        f"Location: {record['location'] or '(not provided)'}\n"
        f"LinkedIn: {record['linkedin'] or '(not provided)'}\n\n"
        f"Statement:\n{record['statement']}\n\n"
        f"Submitted: {record['submittedAt']}\n"
    )
    try:
        send_plain_email(to, f"Board application: {record['roleLabel']}", body)
    except Exception:
        logger.exception("Failed to email board application")


@router.post("/board/apply")
async def apply_for_board_role(
    body: ApplicationRequest,
    request: Request,
    background_tasks: BackgroundTasks,
):
    # Silent success for honeypot hits so bots learn nothing.
    if body.website:
        logger.info("Board application honeypot triggered from %s", client_ip(request))
        return {"ok": True, "message": "Thank you. Your application was received."}

    ip = client_ip(request)
    rate_limit(
        ip,
        bucket="board_apply",
        max_hits=5,
        window_seconds=3600.0,
        detail="Too many applications from this address. Please try again later.",
    )

    if not body.consent:
        raise HTTPException(
            status_code=400,
            detail="Please confirm you agree to be contacted about your application.",
        )

    role = body.role.strip().lower()
    if role not in ROLE_LABELS:
        raise HTTPException(status_code=400, detail="That role is not open.")

    captcha_ok = await verify_turnstile(body.captcha_token, remote_ip=ip)
    if not captcha_ok:
        raise HTTPException(
            status_code=400,
            detail="Captcha verification failed. Please try again.",
        )

    # Store plain text only: strip control/invisible characters and cap length so
    # nothing downstream ever has to trust applicant input.
    record = sanitize_application(
        {
            "submittedAt": datetime.now(timezone.utc).isoformat(),
            "role": role,
            "roleLabel": ROLE_LABELS[role],
            "name": body.name,
            "email": body.email,
            "phone": body.phone,
            "location": body.location,
            "linkedin": body.linkedin,
            "statement": clean_text(body.statement),
            "source": "board-page",
        }
    )

    path = _application_path()
    try:
        if path.exists() and path.stat().st_size >= _MAX_APPLICATION_FILE_BYTES:
            logger.error("Board application file at size cap")
            raise HTTPException(
                status_code=503,
                detail="Applications are temporarily closed. Please email Contact@OperationChildShield.org.",
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
        logger.exception("Failed to persist board application")
        raise HTTPException(
            status_code=503,
            detail="Unable to save your application right now. Please email Contact@OperationChildShield.org.",
        )

    logger.info("Board application saved role=%s", role)
    background_tasks.add_task(_notify_application, record)
    return {
        "ok": True,
        "message": "Thank you. Your application was received and we will follow up.",
    }
