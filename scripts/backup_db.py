#!/usr/bin/env python3
"""Create, list, or restore SQLite backups of the service databases.

Usage (from the repo root):

    python scripts/backup_db.py backup
    python scripts/backup_db.py list
    python scripts/backup_db.py restore data/backups/backup-20260101T000000Z.zip

The database directory comes from CACHE_DIR (default /app/data in Docker).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import backup  # noqa: E402
from app.config import settings  # noqa: E402


def cmd_backup(_args: argparse.Namespace) -> int:
    name = backup.create_backup()
    print(f"created {backup.backup_dir() / name}")
    return 0


def cmd_list(_args: argparse.Namespace) -> int:
    entries = backup.list_backups()
    if not entries:
        print("no backups")
        return 0
    for entry in entries:
        print(f"{entry['name']}\t{entry['bytes']} bytes\t{entry['createdAt']}")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    try:
        restored = backup.restore_backup(args.file)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"restored {', '.join(restored)} into {settings.cache_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up and restore service databases")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("backup", help="snapshot every database into a timestamped zip").set_defaults(
        func=cmd_backup
    )
    sub.add_parser("list", help="list existing backup archives").set_defaults(func=cmd_list)

    restore = sub.add_parser("restore", help="restore databases from an archive")
    restore.add_argument("file")
    restore.set_defaults(func=cmd_restore)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
