"""Reines Parsen deutscher Zahl- und Datumsformate – ohne DB-/Web-Abhängigkeit.

Wird sowohl von der Weboberfläche (`app/web.py`) als auch vom CSV-Parser
(`app/imports/`) genutzt. Geldbeträge immer als ``decimal.Decimal``.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

# Reihenfolge = Priorität beim Ausprobieren
GERMAN_DATE_FORMATS: tuple[str, ...] = ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d")

_STRIP_CHARS = ("\xa0", " ", " ", "€", "EUR", "\t")


def parse_german_decimal(value: object, *, default: Decimal | None = None) -> Decimal | None:
    """'1.234,56' / '-1.234,56' / '1234.56' / '1234' -> Decimal.

    Deutsches Format: Punkt = Tausender-, Komma = Dezimaltrennzeichen. Kommt nur
    ein Punkt vor, wird er als Dezimaltrennzeichen interpretiert (englische
    Schreibweise). Leerer Wert -> ``default``. Unlesbarer Wert -> ``ValueError``.
    """
    if value is None:
        return default
    raw = str(value).strip()
    for ch in _STRIP_CHARS:
        raw = raw.replace(ch, "")
    if raw == "":
        return default

    negative = False
    if raw.endswith("-"):  # Betrag mit nachgestelltem Vorzeichen (manche Banken)
        negative, raw = True, raw[:-1]
    raw = raw.lstrip("+")

    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")

    try:
        result = Decimal(raw)
    except InvalidOperation as exc:  # noqa: TRY003
        raise ValueError(f"Ungültiger Betrag: {value!r}") from exc
    return -result if negative else result


def parse_german_date(value: object, fmt: str | None = None) -> date | None:
    """'TT.MM.JJJJ' (o. ä.) -> date. Leerer Wert -> ``None``, sonst ``ValueError``."""
    if value is None:
        return None
    raw = str(value).strip()
    if raw == "":
        return None
    for f in ((fmt,) if fmt else GERMAN_DATE_FORMATS):
        try:
            return datetime.strptime(raw, f).date()
        except ValueError:
            continue
    raise ValueError(f"Ungültiges Datum: {value!r}")
