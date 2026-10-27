"""SQLite backups for the analytics, admin, and users databases.

Each archive is a zip with one member per database, written with the sqlite3
backup API so a live writer cannot produce a torn file. Restore refuses
archives whose members are not one of the known database names.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

DATABASES = ("analytics.db", "admin.db", "users.db")


def _cache_dir() -> Path:
    return Path(settings.cache_dir)


def backup_dir() -> Path:
    configured = (settings.backup_dir or "").strip()
    path = Path(configured) if configured else _cache_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _snapshot(source: Path, target: Path) -> None:
    """Copy a live SQLite file consistently using the backup API."""
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def create_backup() -> str:
    """Snapshot every present database into a zip; prune old archives.

    Returns the archive file name (not the full path) so it is safe to show.
    """
    directory = backup_dir()
    name = f"backup-{_timestamp()}.zip"
    target = directory / name

    with tempfile.TemporaryDirectory(dir=str(directory), prefix=".staging-") as staging:
        members: list[Path] = []
        for db_name in DATABASES:
            source = _cache_dir() / db_name
            if not source.exists():
                continue
            copy = Path(staging) / db_name
            _snapshot(source, copy)
            members.append(copy)

        # Write to a temp name first so a crash cannot leave a half-written zip
        # that a later restore would happily accept.
        partial = directory / f".{name}.partial"
        with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED) as archive:
            for member in members:
                archive.write(member, arcname=member.name)
        os.replace(partial, target)

    try:
        os.chmod(target, 0o600)
    except OSError:
        pass

    prune_backups()
    return name


def list_backups() -> list[dict[str, object]]:
    directory = backup_dir()
    entries: list[dict[str, object]] = []
    for path in sorted(directory.glob("backup-*.zip"), reverse=True):
        try:
            stat = path.stat()
        except OSError:
            continue
        entries.append(
            {
                "name": path.name,
                "bytes": int(stat.st_size),
                "createdAt": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(),
            }
        )
    return entries


def prune_backups(keep: int | None = None) -> list[str]:
    """Delete all but the newest ``keep`` archives; returns removed names."""
    limit = max(1, int(settings.backup_keep if keep is None else keep))
    paths = sorted(backup_dir().glob("backup-*.zip"), reverse=True)
    removed: list[str] = []
    for path in paths[limit:]:
        try:
            path.unlink()
            removed.append(path.name)
        except OSError:
            logger.warning("Could not prune backup %s", path, exc_info=True)
    return removed


def _validate_archive(archive: zipfile.ZipFile) -> None:
    names = archive.namelist()
    if not names:
        raise ValueError("Backup archive is empty")
    for name in names:
        # Reject paths: members must be bare database file names.
        if name not in DATABASES:
            raise ValueError(f"Unexpected archive member: {name}")


def restore_backup(archive_path: str | Path) -> list[str]:
    """Validate and restore an archive. Returns the restored database names."""
    path = Path(archive_path)
    if not path.is_file():
        raise ValueError(f"Backup not found: {path.name}")

    target_dir = _cache_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    restored: list[str] = []

    with zipfile.ZipFile(path) as archive:
        _validate_archive(archive)
        # Stage inside the cache dir so os.replace stays on one filesystem.
        with tempfile.TemporaryDirectory(dir=str(target_dir), prefix=".restore-") as staging:
            archive.extractall(staging)
            for name in archive.namelist():
                source = Path(staging) / name
                conn = sqlite3.connect(str(source))
                try:
                    conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchall()
                except sqlite3.DatabaseError as exc:
                    raise ValueError(f"{name} is not a valid SQLite database") from exc
                finally:
                    conn.close()

                destination = target_dir / name
                conn = sqlite3.connect(str(destination))
                try:
                    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                except sqlite3.DatabaseError:
                    pass
                finally:
                    conn.close()
                # Replace the file outright: a merge would leave stale rows.
                os.replace(source, destination)
                try:
                    os.chmod(destination, 0o600)
                except OSError:
                    pass
                restored.append(name)

    logger.info("Restored admin backup %s (%s)", path.name, ", ".join(restored))
    return restored
