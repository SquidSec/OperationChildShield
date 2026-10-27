"""Read access to board applications for the admin UI.

Every value is re-sanitized on the way out. The admin frontend renders these as
text (React escapes by default), so the response never carries markup.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.config import settings
from app.sanitize import sanitize_application

logger = logging.getLogger(__name__)

MAX_APPLICATIONS = 500


def _applications_path() -> Path:
    base = Path(settings.cache_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base / "board_applications.jsonl"


def list_applications(limit: int = 200) -> list[dict[str, object]]:
    """Newest first. Malformed lines are skipped rather than failing the page."""
    path = _applications_path()
    if not path.exists():
        return []

    limit = max(1, min(int(limit or 200), MAX_APPLICATIONS))
    rows: list[dict[str, object]] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("Skipping malformed board application line")
                    continue
                if not isinstance(raw, dict):
                    continue
                rows.append(sanitize_application(raw))
                if len(rows) > MAX_APPLICATIONS:
                    rows.pop(0)
    except OSError:
        logger.exception("Could not read board applications")
        return []

    rows.reverse()
    return rows[:limit]


def application_count() -> int:
    return len(list_applications(limit=MAX_APPLICATIONS))


def _record_key(record: dict[str, object]) -> str:
    """Stable identity for a stored application.

    Applications have no database id, so a hash of the immutable fields is used.
    Email alone is not unique (someone may apply twice) and the statement may be
    edited, so the timestamp plus email is the practical identity.
    """
    import hashlib

    raw = f"{record.get('submittedAt', '')}|{record.get('email', '')}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def list_applications_with_ids(limit: int = 200) -> list[dict[str, object]]:
    rows = list_applications(limit=limit)
    for row in rows:
        row["id"] = _record_key(row)
    return rows


def delete_application(application_id: str) -> bool:
    """Remove one application by id. Returns False when it was not found.

    Rewrites the file atomically so a crash mid-delete cannot truncate the list.
    """
    path = _applications_path()
    if not path.exists():
        return False

    kept: list[str] = []
    removed = False
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    raw = json.loads(stripped)
                except json.JSONDecodeError:
                    kept.append(line if line.endswith("\n") else line + "\n")
                    continue
                if isinstance(raw, dict):
                    clean = sanitize_application(raw)
                    if _record_key(clean) == application_id:
                        removed = True
                        continue
                kept.append(stripped + "\n")
    except OSError:
        logger.exception("Could not read applications for deletion")
        return False

    if not removed:
        return False

    tmp = path.with_suffix(".jsonl.tmp")
    try:
        tmp.write_text("".join(kept), encoding="utf-8")
        try:
            tmp.chmod(0o600)
        except OSError:
            pass
        tmp.replace(path)
    except OSError:
        logger.exception("Could not rewrite applications file")
        tmp.unlink(missing_ok=True)
        return False
    return True


def _csv_safe(value: object) -> object:
    """Neutralize spreadsheet formula injection.

    A cell starting with =, +, -, @, tab, or CR is executed as a formula by
    Excel and Sheets. Applicant input is untrusted, so prefix those with a
    single quote: the text stays readable and the formula cannot run.
    """
    if not isinstance(value, str):
        return value
    if value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def export_applications_csv() -> str:
    """CSV of every application, sanitized, for the admin export button."""
    import csv
    import io

    buffer = io.StringIO()
    fields = [
        "id",
        "submittedAt",
        "role",
        "roleLabel",
        "name",
        "email",
        "phone",
        "location",
        "linkedin",
        "statement",
        "source",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in list_applications_with_ids(limit=MAX_APPLICATIONS):
        writer.writerow({k: _csv_safe(v) for k, v in row.items()})
    return buffer.getvalue()
