#!/usr/bin/env python3
"""Seed or update admin accounts. There is no public registration.

Usage (run from the repo root, with the backend venv):

    backend/.venv/bin/python scripts/seed_admin.py add \
        admin@example.org --name "Site Admin"

The password is read from ADMIN_PASSWORD when set, otherwise prompted twice.
Other commands:

    scripts/seed_admin.py list
    scripts/seed_admin.py disable admin@example.org
    scripts/seed_admin.py enable admin@example.org

The database lives at $CACHE_DIR/admin.db (default /app/data in Docker,
set CACHE_DIR=./data for local runs).
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import admin_store  # noqa: E402
from app.config import settings  # noqa: E402


def _read_password() -> str:
    env_password = os.environ.get("ADMIN_PASSWORD", "")
    if env_password:
        return env_password
    first = getpass.getpass("Password: ")
    second = getpass.getpass("Confirm password: ")
    if first != second:
        raise SystemExit("Passwords do not match")
    return first


def cmd_add(args: argparse.Namespace) -> int:
    password = _read_password()
    try:
        user = admin_store.upsert_admin(
            args.email,
            password,
            display_name=args.name or "",
            is_active=not args.inactive,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"saved admin {user['email']} (id={user['id']}, active={user['isActive']})")
    print(
        "OTP is mandatory: this account will show a one-time authenticator setup\n"
        "link when it first signs in, then require a 6-digit code every time."
    )
    return 0


def cmd_list(_args: argparse.Namespace) -> int:
    users = admin_store.list_admins()
    if not users:
        print("no admin users")
        return 0
    for user in users:
        status = "active" if user["isActive"] else "disabled"
        print(f"{user['email']}\t{user['displayName']}\t{status}\tlast_login={user['lastLoginAt']}")
    return 0


def cmd_set_active(args: argparse.Namespace, active: bool) -> int:
    if not admin_store.set_admin_active(args.email, active):
        print(f"error: no admin found for {args.email}", file=sys.stderr)
        return 1
    print(f"{'enabled' if active else 'disabled'} {args.email}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    user = admin_store.get_admin_by_email(args.email)
    if user is None:
        print(f"error: no admin found for {args.email}", file=sys.stderr)
        return 1
    user_id = int(user["id"])
    remaining = admin_store.lockout_remaining_seconds(args.email)
    otp = admin_store.otp_status(user_id)
    print(f"{user['email']}")
    print(f"  active:        {user['isActive']}")
    print(f"  role:          {user.get('role')}")
    print(f"  locked:        {'yes, ' + str((remaining + 59) // 60) + ' min left' if remaining else 'no'}")
    print(f"  otp enrolled:  {otp['enrolled']}")
    print(f"  recovery codes remaining: {otp.get('recoveryCodesRemaining', 0)}")
    return 0


def cmd_reset_otp(args: argparse.Namespace) -> int:
    user = admin_store.get_admin_by_email(args.email)
    if user is None:
        print(f"error: no admin found for {args.email}", file=sys.stderr)
        return 1
    admin_store.force_otp_reset(int(user["id"]))
    print(
        f"forced OTP re-enrolment for {user['email']} and revoked its sessions.\n"
        "OTP stays required; the account will show a new authenticator setup\n"
        "link at next sign-in."
    )
    return 0


def cmd_unlock(args: argparse.Namespace) -> int:
    """Clear a lockout created by repeated failed sign-ins."""
    user = admin_store.get_admin_by_email(args.email)
    if user is None:
        print(f"error: no admin found for {args.email}", file=sys.stderr)
        return 1
    admin_store.clear_lockout(args.email)
    print(f"unlocked {user['email']}; it can sign in again now.")
    return 0


def main() -> int:
    admin_store.init_admin_db()
    print(f"database: {settings.cache_dir}/admin.db")

    parser = argparse.ArgumentParser(description="Manage admin accounts")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="create an admin or reset its password")
    add.add_argument("email")
    add.add_argument("--name", default="", help="display name")
    add.add_argument("--inactive", action="store_true", help="create disabled")
    add.set_defaults(func=cmd_add)

    listing = sub.add_parser("list", help="list admin accounts")
    listing.set_defaults(func=cmd_list)

    disable = sub.add_parser("disable", help="disable an admin and kill its sessions")
    disable.add_argument("email")
    disable.set_defaults(func=lambda a: cmd_set_active(a, False))

    reset_otp = sub.add_parser(
        "reset-otp",
        help="force re-enrolment (OTP is never disabled) at next sign-in",
    )
    reset_otp.add_argument("email")
    reset_otp.set_defaults(func=cmd_reset_otp)

    unlock = sub.add_parser(
        "unlock", help="clear a temporary lockout after failed sign-ins"
    )
    unlock.add_argument("email")
    unlock.set_defaults(func=cmd_unlock)

    status = sub.add_parser(
        "status", help="show lockout and OTP state for one account"
    )
    status.add_argument("email")
    status.set_defaults(func=cmd_status)

    enable = sub.add_parser("enable", help="re-enable a disabled admin")
    enable.add_argument("email")
    enable.set_defaults(func=lambda a: cmd_set_active(a, True))

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
