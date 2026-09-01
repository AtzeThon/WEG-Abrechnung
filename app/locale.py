"""Deutsche Zahl-, Währungs- und Datumsformatierung als Jinja-Filter (via Babel)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from babel.dates import format_date as _babel_format_date
from babel.numbers import format_currency, format_decimal

from app.config import settings

LOCALE = settings.locale
_CENT = Decimal("0.01")


def _to_decimal(value) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def euro(value, *, cents: bool = True) -> str:
    d = _to_decimal(value).quantize(_CENT, rounding=ROUND_HALF_UP)
    pattern = None if cents else "#,##0 ¤"
    return format_currency(d, "EUR", locale=LOCALE, format=pattern)


def dezimal(value, digits: int = 2) -> str:
    d = _to_decimal(value)
    q = Decimal(1).scaleb(-digits)
    return format_decimal(d.quantize(q, rounding=ROUND_HALF_UP), locale=LOCALE)


def betrag(value) -> str:
    """Betrag mit genau zwei Nachkommastellen, ohne Tausendertrenner ('782,90')."""
    d = _to_decimal(value).quantize(_CENT, rounding=ROUND_HALF_UP)
    return format_decimal(d, format="0.00", locale=LOCALE)


def geld(value) -> str:
    """Kompakter Geldbetrag: Tausendertrenner, zwei Nachkommastellen, kein Symbol."""
    d = _to_decimal(value).quantize(_CENT, rounding=ROUND_HALF_UP)
    return format_decimal(d, format="#,##0.00", locale=LOCALE)


def prozent(value, digits: int = 2) -> str:
    """Erwartet einen Bruch (0.26601 -> '26,60 %')."""
    pattern = "0." + ("0" * digits) if digits else "0"
    hundred = _to_decimal(value) * 100
    return format_decimal(hundred, format=pattern, locale=LOCALE) + " %"


def datum(value) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        value = value.date()
    if not isinstance(value, date):
        return str(value)
    return _babel_format_date(value, format="dd.MM.yyyy", locale=LOCALE)


def quantize_cent(value) -> Decimal:
    return _to_decimal(value).quantize(_CENT, rounding=ROUND_HALF_UP)


def register_filters(env) -> None:
    env.filters["euro"] = euro
    env.filters["dezimal"] = dezimal
    env.filters["betrag"] = betrag
    env.filters["geld"] = geld
    env.filters["prozent"] = prozent
    env.filters["datum"] = datum
