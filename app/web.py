"""Gemeinsame Helfer für die Weboberfläche: Flash-Nachrichten, Formularparsing."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import Request

from app.formats import parse_german_date, parse_german_decimal
from app.templating import templates

_FLASH_KEY = "_flash"


def flash(request: Request, message: str, category: str = "success") -> None:
    request.session.setdefault(_FLASH_KEY, []).append({"message": message, "category": category})


def get_flashed(request: Request) -> list[dict]:
    return request.session.pop(_FLASH_KEY, [])


templates.env.globals["get_flashed"] = get_flashed


def parse_decimal(value: str | None, *, default: Decimal | None = Decimal("0")) -> Decimal | None:
    """Deutsche ('1.234,56') und englische ('1234.56') Schreibweise -> Decimal."""
    return parse_german_decimal(value, default=default)


def parse_date(value: str | None) -> date | None:
    return parse_german_date(value)
