"""SMTP helpers for Join Us notifications (stdlib only)."""

from __future__ import annotations

import logging
import re
import smtplib
import ssl
import threading
import time
from email.message import EmailMessage
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

# CR/LF and other C0 controls (except TAB) must never enter headers or untrusted body lines.
_UNSAFE_EMAIL_CHARS = re.compile(r"[\r\n\x00-\x08\x0b\x0c\x0e-\x1f\x7f]+")

# Keep SMTP failures short: these run in a background thread, and a long stall
# only delays other queued mail.
SMTP_TIMEOUT_SECONDS = 10


def sanitize_email_header(value: str, *, max_length: int = 200) -> str:
    """Strip header-injection sequences and control characters for Subject/Reply-To/etc."""
    cleaned = _UNSAFE_EMAIL_CHARS.sub(" ", str(value or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip()
    return cleaned


def sanitize_email_body(value: str, *, max_length: int = 8000) -> str:
    """Normalize newlines and strip dangerous controls for message bodies."""
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    if len(text) > max_length:
        text = text[:max_length]
    return text


def _from_address() -> str:
    return (settings.smtp_from or settings.smtp_user or "").strip()


def _notify_to() -> str:
    return (settings.involve_notify_to or settings.smtp_user or "").strip()


def send_email(
    *,
    to: str,
    subject: str,
    body: str,
    reply_to: str | None = None,
) -> None:
    if not settings.smtp_configured:
        raise RuntimeError("SMTP is not configured")

    safe_to = sanitize_email_header(to, max_length=320)
    safe_subject = sanitize_email_header(subject, max_length=200)
    safe_from = sanitize_email_header(_from_address(), max_length=320)
    safe_body = sanitize_email_body(body)
    if not safe_to or not safe_from:
        raise RuntimeError("Invalid email addresses for send")

    msg = EmailMessage()
    msg["Subject"] = safe_subject
    msg["From"] = safe_from
    msg["To"] = safe_to
    if reply_to:
        safe_reply = sanitize_email_header(reply_to, max_length=320)
        if safe_reply and "@" in safe_reply and "\n" not in safe_reply:
            msg["Reply-To"] = safe_reply
    msg.set_content(safe_body)

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    except Exception:
        logger.exception("SMTP send_email failed (to domain redacted)")
        raise


def notify_involve_signup(record: dict[str, Any]) -> bool:
    """Email the ops inbox about a new Join Us submission. Returns True if sent."""
    if not settings.smtp_configured:
        logger.warning("SMTP not configured; involve signup not emailed")
        return False

    to = _notify_to()
    if not to:
        logger.warning("No involve notify recipient configured")
        return False

    name = sanitize_email_header(str(record.get("name") or "(no name)"), max_length=120)
    email = sanitize_email_header(str(record.get("email") or "(no email)"), max_length=320)
    interest = sanitize_email_header(str(record.get("interest") or "(none)"), max_length=80)
    state = sanitize_email_header(str(record.get("state") or "(none)"), max_length=80)
    message = sanitize_email_body(str(record.get("message") or ""), max_length=4000)
    submitted = sanitize_email_header(str(record.get("submittedAt") or ""), max_length=80)

    body = (
        "New Operation Child Shield Join Us signup\n"
        "=========================================\n\n"
        f"Submitted: {submitted}\n"
        f"Name: {name}\n"
        f"Email: {email}\n"
        f"State: {state}\n"
        f"Interest: {interest}\n\n"
        f"Message:\n{message}\n"
    )

    try:
        send_email(
            to=to,
            subject=f"[OCS Join Us] {interest} — {name}",
            body=body,
            reply_to=email if "@" in email else None,
        )
    except Exception:
        logger.exception("notify_involve_signup failed")
        return False
    return True


_auto_reply_lock = threading.Lock()
# address -> last time we auto-replied
_auto_reply_by_address: dict[str, float] = {}
# send timestamps inside the global rolling window
_auto_reply_global: list[float] = []
_AUTO_REPLY_WINDOW_SECONDS = 3600.0


def _reserve_auto_reply(email: str) -> bool:
    """Claim an auto-reply slot, or return False when throttled.

    Signup is unauthenticated, so without this the endpoint can be pointed at
    any address to generate mail from our domain.
    """
    now = time.time()
    window = max(settings.auto_reply_per_address_hours, 0.0) * 3600.0
    with _auto_reply_lock:
        last = _auto_reply_by_address.get(email)
        if window > 0 and last is not None and now - last < window:
            return False

        _auto_reply_global[:] = [
            t for t in _auto_reply_global if now - t < _AUTO_REPLY_WINDOW_SECONDS
        ]
        if len(_auto_reply_global) >= max(settings.auto_reply_max_per_hour, 0):
            return False

        _auto_reply_by_address[email] = now
        _auto_reply_global.append(now)

        # Bound memory: drop entries whose window has expired.
        if len(_auto_reply_by_address) > 10_000:
            stale = [
                addr
                for addr, sent in _auto_reply_by_address.items()
                if window <= 0 or now - sent >= window
            ]
            for addr in stale:
                _auto_reply_by_address.pop(addr, None)
        return True


def reset_auto_reply_throttle_for_tests() -> None:
    with _auto_reply_lock:
        _auto_reply_by_address.clear()
        _auto_reply_global.clear()


def auto_reply_involve_signup(record: dict[str, Any]) -> bool:
    """Optional confirmation email to the person who signed up."""
    if not settings.smtp_configured or not settings.involve_send_auto_reply:
        return False

    email = sanitize_email_header(str(record.get("email") or ""), max_length=320)
    if not email or "@" not in email:
        return False

    if not _reserve_auto_reply(email):
        logger.info("Auto-reply throttled for repeat recipient (%s)", email.split("@")[-1])
        return False

    name = sanitize_email_header(str(record.get("name") or "").strip() or "friend", max_length=120)
    body = (
        f"Hi {name},\n\n"
        "Thank you for signing up with Operation Child Shield. We received your "
        "message and will follow up when there is a good fit for your interest.\n\n"
        "If you need to reach us sooner, email Contact@OperationChildShield.org.\n\n"
        "— Operation Child Shield\n"
        "Protect | Educate | Mobilize\n"
        "https://operationchildshield.org\n"
    )

    try:
        send_email(
            to=email,
            subject="We received your Operation Child Shield signup",
            body=body,
        )
    except Exception:
        logger.exception("auto_reply_involve_signup failed")
        return False
    return True
