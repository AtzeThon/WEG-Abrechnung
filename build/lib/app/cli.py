"""Kommandozeilenwerkzeuge: DB anlegen, Verwalter-Account verwalten."""

from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import User


def _create_all() -> None:
    import app.models  # noqa: F401  (Modelle registrieren)

    Base.metadata.create_all(engine)
    print("Tabellen angelegt (falls nicht vorhanden).")


def _create_admin(username: str, password: str | None) -> None:
    if password is None:
        password = getpass.getpass("Passwort: ")
        if password != getpass.getpass("Passwort wiederholen: "):
            sys.exit("Passwörter stimmen nicht überein.")
    if len(password) < 8:
        sys.exit("Passwort muss mindestens 8 Zeichen haben.")

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        if user is None:
            user = User(username=username)
            db.add(user)
            action = "angelegt"
        else:
            action = "aktualisiert"
        user.set_password(password)
        db.commit()
    print(f"Verwalter {username!r} {action}.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="weg-admin")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("initdb", help="Tabellen anlegen (ohne Alembic)")

    p_admin = sub.add_parser("create-admin", help="Verwalter-Account anlegen/ändern")
    p_admin.add_argument("username")
    p_admin.add_argument("--password", help="Passwort (sonst interaktive Abfrage)")

    args = parser.parse_args(argv)
    if args.cmd == "initdb":
        _create_all()
    elif args.cmd == "create-admin":
        _create_admin(args.username, args.password)


if __name__ == "__main__":
    main()
