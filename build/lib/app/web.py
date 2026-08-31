"""Gemeinsame Helfer für die Weboberfläche: Flash-Nachrichten, Formularparsing."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from fastapi import Request

from app.templating import templates

_FLASH_KEY = "_flash"


def flash(request: Request, message: str, category: str = "success") -> None:
    request.session.setdefault(_FLASH_KEY, []).append({"message": message, "category": category})


def get_flashed(request: Request) -> list[dict]:
    return request.session.pop(_FLASH_KEY, [])


templates.env.globals["get_flashed"] = get_flashed


def parse_decimal(value: str | None, *, default: Decimal | None = Decimal("0")) -> Decimal | None:
    """Akzeptiert deutsche ('1.234,56') und englische ('1234.56') Schreibweise."""
    if value is None:
        return default
    raw = value.strip()
    if raw == "":
        return default
    raw = raw.replace(" ", "").replace(" ", "")
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        return Decimal(raw)
    except InvalidOperation as exc:  # noqa: TRY003
        raise ValueError(f"Ungültiger Betrag: {value!r}") from exc


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Ungültiges Datum: {value!r}")
