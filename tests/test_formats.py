"""Tests für app/formats.py – deutsches Zahl-/Datumsparsing."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.formats import parse_german_date, parse_german_decimal


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1.234,56", Decimal("1234.56")),
        ("-1.234,56", Decimal("-1234.56")),
        ("1.234,56-", Decimal("-1234.56")),
        ("+12,00", Decimal("12.00")),
        ("1234.56", Decimal("1234.56")),
        ("0,00", Decimal("0.00")),
        ("1.000.000,00", Decimal("1000000.00")),
        ("  -42,10 €", Decimal("-42.10")),
        ("1.234,56 EUR", Decimal("1234.56")),
    ],
)
def test_parse_german_decimal(raw, expected):
    assert parse_german_decimal(raw) == expected


def test_parse_german_decimal_leer_und_none():
    assert parse_german_decimal("") is None
    assert parse_german_decimal(None) is None
    assert parse_german_decimal("", default=Decimal("0")) == Decimal("0")


def test_parse_german_decimal_ungueltig():
    with pytest.raises(ValueError):
        parse_german_decimal("abc")


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("15.03.2026", date(2026, 3, 15)),
        ("01.08.25", date(2025, 8, 1)),
        ("2026-07-31", date(2026, 7, 31)),
        ("", None),
    ],
)
def test_parse_german_date(raw, expected):
    assert parse_german_date(raw) == expected


def test_parse_german_date_mit_explizitem_format():
    assert parse_german_date("31/07/2026", fmt="%d/%m/%Y") == date(2026, 7, 31)


def test_parse_german_date_ungueltig():
    with pytest.raises(ValueError):
        parse_german_date("kein datum")


def test_web_wrapper_kompatibel():
    from app.web import parse_date, parse_decimal

    assert parse_decimal("") == Decimal("0")  # Default bleibt 0
    assert parse_decimal("1.234,56") == Decimal("1234.56")
    assert parse_date("15.03.2026") == date(2026, 3, 15)
