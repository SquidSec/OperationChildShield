"""Email alert delivery for constituent subscriptions.

Design goals:
- Never let a mail failure break a request or a scheduler tick.
- Never send the same alert twice to the same address (dedupe on
  email + kind + subject, enforced by a unique index).
- Every message carries a signed one-click unsubscribe link.

Callers either use :func:`queue_alert` directly or push work with
:func:`enqueue_pending` and let the scheduler drain it in
:func:`dispatch_pending_alerts`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import smtplib
import ssl
import threading
from email.message import EmailMessage
from typing import Any, Iterable
from urllib.parse import quote

from app import users_store
from app.config import settings
from app.email_smtp import sanitize_email_body, sanitize_email_header

logger = logging.getLogger(__name__)

UNSUBSCRIBE_PATH = "/api/alerts/unsubscribe"
SMTP_TIMEOUT_SECONDS = 10

# Alerts queued in this process, drained on the next scheduler tick.
_pending_lock = threading.Lock()
_pending: list[dict[str, Any]] = []


def _signing_key() -> bytes:
    """Stable signing key; rotates only if the SMTP password changes."""
    secret = (settings.smtp_password or "").strip()
    if not secret:
        secret = (getattr(settings, "turnstile_secret_key", "") or "").strip()
    if not secret:
        secret = "ocs-unsubscribe-dev-secret"
    return hashlib.sha256(f"ocs-unsub:{secret}".encode("utf-8")).digest()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def unsubscribe_token(email: str, kind: str, bioguide_id: str = "") -> str:
    """Sign an unsubscribe claim: base64(payload).base64(hmac)."""
    payload = json.dumps(
        {
            "email": (email or "").strip().lower(),
            "kind": (kind or "").strip().lower(),
            "bioguideId": (bioguide_id or "").strip().upper(),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    signature = hmac.new(_signing_key(), payload, hashlib.sha256).digest()[:16]
    return f"{_b64(payload)}.{_b64(signature)}"


def verify_unsubscribe_token(token: str) -> dict[str, str] | None:
    """Validate an unsubscribe token; returns its claims or None."""
    if not token or "." not in token or len(token) > 1024:
        return None
    encoded, signature_text = token.rsplit(".", 1)
    try:
        payload = _unb64(encoded)
        signature = _unb64(signature_text)
    except (ValueError, TypeError):
        return None
    expected = hmac.new(_signing_key(), payload, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        claims = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(claims, dict):
        return None
    email = str(claims.get("email") or "")
    if "@" not in email:
        return None
    return {
        "email": email,
        "kind": str(claims.get("kind") or ""),
        "bioguideId": str(claims.get("bioguideId") or ""),
    }


def render_unsubscribe_url(email: str, kind: str, bioguide_id: str = "") -> str:
    """Build a signed unsubscribe URL for one address."""
    base = (settings.public_site_url or "").rstrip("/")
    token = unsubscribe_token(email, kind, bioguide_id)
    return f"{base}{UNSUBSCRIBE_PATH}?token={quote(token)}"


def _send(
    to: str,
    subject: str,
    text: str,
    html: str | None = None,
    *,
    list_unsubscribe: str | None = None,
) -> bool:
    """Send one message over SMTP/TLS. Returns False instead of raising."""
    if not settings.smtp_configured:
        return False

    safe_to = sanitize_email_header(to, max_length=320)
    safe_from = sanitize_email_header(settings.smtp_from or settings.smtp_user, max_length=320)
    safe_subject = sanitize_email_header(subject, max_length=200)
    if not safe_to or not safe_from or not safe_subject:
        logger.warning("Refusing to send alert with an invalid from/to/subject")
        return False

    msg = EmailMessage()
    msg["Subject"] = safe_subject
    msg["From"] = safe_from
    msg["To"] = safe_to
    msg.set_content(sanitize_email_body(text, max_length=20000))
    if html:
        msg.add_alternative(sanitize_email_body(html, max_length=40000), subtype="html")
    if list_unsubscribe:
        msg["List-Unsubscribe"] = f"<{list_unsubscribe}>"

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    except Exception:  # noqa: BLE001 - SMTP errors vary by server
        # Recipient address is intentionally not logged (personal data).
        logger.warning("SMTP send failed for alert to %s", safe_to.split("@")[-1])
        return False
    return True


def _body_with_unsubscribe(text: str, email: str, kind: str, bioguide_id: str) -> str:
    link = render_unsubscribe_url(email, kind, bioguide_id)
    return (
        f"{text.rstrip()}\n\n"
        "--\n"
        "You receive this because you subscribed to Operation Child Shield alerts.\n"
        f"Unsubscribe: {link}\n"
    )


def _deliver_one(
    *,
    email: str,
    kind: str,
    subject: str,
    body_text: str,
    bioguide_id: str,
) -> str:
    """Try one recipient with retries. Returns ``"sent"`` or ``"failed"``."""
    unsubscribe_url = render_unsubscribe_url(email, kind, bioguide_id)
    body = _body_with_unsubscribe(body_text, email, kind, bioguide_id)
    attempts = max(1, int(settings.alert_max_attempts))

    for attempt in range(attempts):
        try:
            ok = _send(email, subject, body, list_unsubscribe=unsubscribe_url)
        except Exception:  # noqa: BLE001 - a broken send must not break the tick
            logger.exception("Unexpected alert send error for kind=%s", kind)
            ok = False
        if ok:
            users_store.record_delivery(email, kind, subject, "sent")
            return "sent"
        logger.warning(
            "Alert send attempt %s/%s failed for kind=%s",
            attempt + 1,
            attempts,
            kind,
        )

    # Recording the failure stops an endless retry loop on later ticks; the
    # (email, kind, subject) row is what blocks duplicate work.
    users_store.record_delivery(email, kind, subject, "failed", "send failed")
    return "failed"


def queue_alert(
    kind: str,
    subject: str,
    body_text: str,
    *,
    bioguide_id: str | None = None,
    recipients: Iterable[dict[str, str]] | None = None,
) -> dict[str, int]:
    """Send one alert to every active subscriber of ``kind``.

    Returns ``{"sent": n, "failed": n, "skipped": n}``. Never raises for a
    single delivery failure; failures are recorded so they are not retried
    forever on every tick.
    """
    summary = {"sent": 0, "failed": 0, "skipped": 0}
    if not settings.alerts_enabled:
        logger.info("Alerts disabled; queue_alert is a no-op")
        return summary
    if not settings.smtp_configured:
        logger.info("Alerts skipped: SMTP is not configured")
        return summary

    safe_subject = sanitize_email_header(subject, max_length=200)
    if not safe_subject:
        logger.warning("Refusing to queue alert with an empty subject")
        return summary

    subs = list(recipients if recipients is not None else users_store.active_subscribers(kind))
    wanted = (bioguide_id or "").strip().upper()
    if wanted:
        subs = [s for s in subs if (s.get("bioguideId") or "").strip().upper() == wanted]

    for sub in subs:
        email = sub.get("email") or ""
        member = sub.get("bioguideId") or ""
        if not email:
            summary["skipped"] += 1
            continue
        if users_store.was_delivered(email, kind, safe_subject):
            summary["skipped"] += 1
            continue

        status = _deliver_one(
            email=email,
            kind=kind,
            subject=safe_subject,
            body_text=body_text,
            bioguide_id=member,
        )
        summary[status] += 1

    logger.info(
        "Alert dispatch kind=%s sent=%s failed=%s skipped=%s",
        kind,
        summary["sent"],
        summary["failed"],
        summary["skipped"],
    )
    return summary


def enqueue_pending(
    kind: str,
    subject: str,
    body_text: str,
    *,
    bioguide_id: str | None = None,
) -> None:
    """Queue an alert for the scheduler to drain on its next tick."""
    with _pending_lock:
        _pending.append(
            {
                "kind": kind,
                "subject": subject,
                "body_text": body_text,
                "bioguide_id": bioguide_id,
            }
        )


def pending_count() -> int:
    with _pending_lock:
        return len(_pending)


def dispatch_pending_alerts() -> dict[str, int]:
    """Scheduler entry point: send everything queued in this process.

    Reports zeros when alerts are off or SMTP is unconfigured.
    """
    summary = {"sent": 0, "failed": 0, "skipped": 0}
    if not settings.alerts_enabled or not settings.smtp_configured:
        return summary

    with _pending_lock:
        batch = list(_pending)
        _pending.clear()

    for item in batch:
        result = queue_alert(
            item["kind"],
            item["subject"],
            item["body_text"],
            bioguide_id=item["bioguide_id"],
        )
        for key in summary:
            summary[key] += result.get(key, 0)

    if batch:
        logger.info(
            "Dispatched %s queued alert(s): sent=%s failed=%s skipped=%s",
            len(batch),
            summary["sent"],
            summary["failed"],
            summary["skipped"],
        )
    return summary


def notify_member_vote(
    *,
    bioguide_id: str,
    member_name: str,
    bill_number: str,
    bill_title: str,
    vote_cast: str,
) -> dict[str, int]:
    """Send a vote alert for one lawmaker to their followers."""
    subject = f"Vote alert: {member_name} on {bill_number}"
    body = (
        f"{member_name} voted {vote_cast} on {bill_number}.\n\n"
        f"{bill_title}\n\n"
        "Read the full record on Operation Child Shield."
    )
    return queue_alert("member_vote", subject, body, bioguide_id=bioguide_id)


def notify_bill_floor_vote(
    *, bill_number: str, bill_title: str, congress_url: str
) -> dict[str, int]:
    """Send a floor-vote alert for a tracked bill to all subscribers."""
    subject = f"Floor vote: {bill_number}"
    body = (
        f"A floor vote was recorded on {bill_number}.\n\n"
        f"{bill_title}\n\n"
        f"Official record: {congress_url}"
    )
    return queue_alert("bill_floor_vote", subject, body)


def reset_for_tests() -> None:
    """Clear the in-process queue."""
    with _pending_lock:
        _pending.clear()
