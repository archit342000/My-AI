"""Manage users: python -m backend.auth.cli add <email> [--role user|admin] | deactivate <email> | list"""
import argparse
import sqlite3
import sys
from typing import Optional

from backend import config
from backend.logging import log_event
from backend.database import db
from backend.database.init_db import init_db


def _valid_email(email: str) -> bool:
    return "@" in email and not any(ch.isspace() for ch in email) and not email.startswith("@") and not email.endswith("@")


def main(argv: Optional[list] = None) -> int:
    """Run the user CLI with `argv` (default: sys.argv) and return the exit code."""
    parser = argparse.ArgumentParser(prog="python -m backend.auth.cli", description="Manage My-AI users.")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="add an active user")
    add.add_argument("email")
    add.add_argument("--role", choices=("user", "admin"), default="user")
    deactivate = sub.add_parser("deactivate", help="deactivate a user")
    deactivate.add_argument("email")
    sub.add_parser("list", help="list users")
    args = parser.parse_args(argv)

    init_db()
    if args.command == "add":
        if not _valid_email(args.email):
            print(f"Invalid email: {args.email!r}", file=sys.stderr)
            return 1
        try:
            user = db.create_user(args.email, args.role)
        except sqlite3.IntegrityError:
            print(f"User already exists: {args.email}", file=sys.stderr)
            return 1
        log_event("user_added", {"email": user["email"], "role": user["role"]})
        print(f"Added {user['email']} ({user['role']})")
    elif args.command == "deactivate":
        if config.ADMIN_EMAIL and args.email.strip().lower() == config.ADMIN_EMAIL:
            print("Refusing to deactivate ADMIN_EMAIL: the seed re-activates it on every start. Change ADMIN_EMAIL first.", file=sys.stderr)
            return 1
        if not db.set_user_active(args.email, False):
            print(f"No such user: {args.email}", file=sys.stderr)
            return 1
        log_event("user_deactivated", {"email": args.email.strip().lower()})
        print(f"Deactivated {args.email}")
    else:
        for user in db.list_users():
            print(f"{user['email']}\t{user['role']}\t{'active' if user['is_active'] else 'inactive'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
