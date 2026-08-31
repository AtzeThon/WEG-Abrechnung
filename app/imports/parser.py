"""Robuster CSV-Parser für deutsche Bank-Kontoauszüge (nur `csv` aus der stdlib).

Ablauf:
    raw: bytes
      -> sniff(raw)            -> (text, CsvDialect)   Encoding/Trennzeichen/Header
      -> detect_mapping(...)   -> ColumnMapping         Spalten raten
      -> parse_rows(...)       -> list[ParsedRow]       Zeilen -> Decimal/date
oder in einem Schritt: parse(raw, dialect=?, mapping=?, amount_mode=?)
"""

from __future__ import annotations

import csv
import hashlib
import io

from app.formats import parse_german_date, parse_german_decimal
from app.imports.types import (
    AMOUNT_SIGN_COLUMN,
    AMOUNT_SINGLE,
    AMOUNT_SOLL_HABEN,
    ColumnMapping,
    CsvDialect,
    ParsedRow,
    ParseResult,
)

_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
_DELIMITERS = (";", ",", "\t", "|")

# Schlüsselwörter je Zielfeld (normalisiert: klein, ohne Umlaute/Sonderzeichen).
# Reihenfolge = Priorität (spezifische Felder zuerst).
_KEYWORDS: dict[str, tuple[str, ...]] = {
    "sign_column": ("sollhabenkennzeichen", "shkennzeichen", "kennzeichen", "sollhaben"),
    "amount_debit": ("betragsoll", "soll", "belastung", "auszahlung", "abgang", "sollbetrag"),
    "amount_credit": ("betraghaben", "haben", "gutschrift", "einzahlung", "zugang", "habenbetrag"),
    "date": ("buchungstag", "buchungsdatum", "buchung", "datum", "valuta", "wertstellung"),
    "payee": (
        "beguenstigterzahlungspflichtiger", "beguenstigterauftraggeber", "beguenstigter",
        "zahlungspflichtiger", "zahlungsempfaenger", "zahlungsbeteiligter", "empfaenger",
        "auftraggeber", "kontoinhaber", "name",
    ),
    "purpose": ("verwendungszweck", "buchungstext", "vwz", "umsatztext", "verwendung"),
    "amount": ("betrag", "umsatz", "betrageur", "umsatzeur"),
    "category": ("kategorie", "umsatzart", "buchungsart"),
}
# Bei Feld -> normalisierte Header-Fragmente, die die Zuordnung ausschließen.
_EXCLUDE: dict[str, tuple[str, ...]] = {
    "amount": ("soll", "haben", "kennzeichen"),
    "amount_debit": ("kennzeichen",),
    "amount_credit": ("kennzeichen",),
}

_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "ae", "Ö": "oe", "Ü": "ue"})


def normalize(text: str) -> str:
    text = (text or "").strip().lower().translate(_UMLAUTS)
    return "".join(ch for ch in text if ch.isalnum())


def header_signature(headers: list[str], delimiter: str) -> str:
    """Stabiler Fingerabdruck einer CSV-Struktur (für ImportProfile)."""
    norm = sorted(normalize(h) for h in headers if h and h.strip())
    payload = repr(delimiter) + "|" + "|".join(norm)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


# --------------------------------------------------------------------------- #
# Encoding / Trennzeichen / Headerzeile
# --------------------------------------------------------------------------- #
def decode(raw: bytes) -> tuple[str, str]:
    for enc in _ENCODINGS:
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace"), "latin-1"


def sniff_delimiter(text: str) -> str:
    sample = "\n".join(line for line in text.splitlines()[:20] if line.strip())
    try:
        return csv.Sniffer().sniff(sample, delimiters="".join(_DELIMITERS)).delimiter
    except csv.Error:
        counts = {d: sample.count(d) for d in _DELIMITERS}
        best = max(counts, key=counts.get)
        return best if counts[best] else ";"


def _score_header(cells: list[str]) -> int:
    norms = [normalize(c) for c in cells]
    hits = 0
    for keys in _KEYWORDS.values():
        if any(any(k in n for k in keys) for n in norms if n):
            hits += 1
    return hits


def find_header_row(rows: list[list[str]]) -> int:
    best_idx, best_score = 0, -1
    for idx, cells in enumerate(rows[:30]):
        score = _score_header(cells)
        non_empty = sum(1 for c in cells if c and c.strip())
        score = score * 10 + (non_empty if score else 0)
        if score > best_score and non_empty >= 2:
            best_idx, best_score = idx, score
    return best_idx


def sniff(raw: bytes) -> tuple[str, CsvDialect]:
    text, encoding = decode(raw)
    delimiter = sniff_delimiter(text)
    all_rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    header_row = find_header_row(all_rows) if all_rows else 0
    return text, CsvDialect(delimiter=delimiter, encoding=encoding, header_row=header_row)


# --------------------------------------------------------------------------- #
# Spalten-Mapping
# --------------------------------------------------------------------------- #
def detect_mapping(headers: list[str]) -> ColumnMapping:
    norm_headers = [(h, normalize(h)) for h in headers if h and h.strip()]
    picked: dict[str, str] = {}
    used: set[str] = set()

    for field, keys in _KEYWORDS.items():
        excludes = _EXCLUDE.get(field, ())
        # 1. exakte Übereinstimmung, 2. Teilstring
        for want_exact in (True, False):
            for original, norm in norm_headers:
                if original in used or not norm:
                    continue
                if any(x in norm for x in excludes):
                    continue
                match = norm in keys if want_exact else any(k in norm for k in keys)
                if match:
                    picked[field] = original
                    used.add(original)
                    break
            if field in picked:
                break

    return ColumnMapping(**picked)


def guess_amount_mode(mapping: ColumnMapping) -> str:
    if mapping.amount_debit and mapping.amount_credit:
        return AMOUNT_SOLL_HABEN
    if mapping.amount and mapping.sign_column:
        return AMOUNT_SIGN_COLUMN
    return AMOUNT_SINGLE


# --------------------------------------------------------------------------- #
# Zeilen parsen
# --------------------------------------------------------------------------- #
_DEBIT_SIGNS = {"s", "soll", "-", "d", "debit"}


def _amount_for_row(row: dict[str, str], mapping: ColumnMapping, mode: str) -> tuple[object, str | None]:
    from decimal import Decimal

    try:
        if mode == AMOUNT_SOLL_HABEN:
            debit = parse_german_decimal(row.get(mapping.amount_debit or ""), default=Decimal("0"))
            credit = parse_german_decimal(row.get(mapping.amount_credit or ""), default=Decimal("0"))
            return abs(credit) - abs(debit), None
        value = parse_german_decimal(row.get(mapping.amount or ""))
        if value is None:
            return None, "Betrag fehlt"
        if mode == AMOUNT_SIGN_COLUMN:
            sign = normalize(row.get(mapping.sign_column or ""))
            return (-abs(value) if sign in _DEBIT_SIGNS else abs(value)), None
        return value, None
    except ValueError as exc:
        return None, str(exc)


def parse_rows(
    text: str,
    dialect: CsvDialect,
    mapping: ColumnMapping,
    *,
    amount_mode: str | None = None,
) -> list[ParsedRow]:
    mode = amount_mode or dialect.amount_mode
    all_rows = list(csv.reader(io.StringIO(text), delimiter=dialect.delimiter))
    if dialect.header_row >= len(all_rows):
        return []
    headers = [h.strip() for h in all_rows[dialect.header_row]]
    out: list[ParsedRow] = []

    for offset, cells in enumerate(all_rows[dialect.header_row + 1 :], start=1):
        line_no = dialect.header_row + 1 + offset  # 1-basiert im Original
        if not any(c and c.strip() for c in cells):
            continue  # Leerzeile
        row = {headers[i]: (cells[i].strip() if i < len(cells) else "") for i in range(len(headers))}
        # Zusatzspalten ohne Header trotzdem festhalten
        for i in range(len(headers), len(cells)):
            row[f"_extra_{i}"] = cells[i].strip()

        errors: list[str] = []
        booking_date = None
        try:
            booking_date = parse_german_date(row.get(mapping.date or ""), dialect.date_format)
        except ValueError as exc:
            errors.append(str(exc))
        if booking_date is None and not errors:
            errors.append("Datum fehlt")

        amount, amount_err = _amount_for_row(row, mapping, mode)
        if amount_err:
            errors.append(amount_err)

        out.append(
            ParsedRow(
                line_no=line_no,
                booking_date=booking_date,
                payee=(row.get(mapping.payee or "") or "").strip(),
                purpose=(row.get(mapping.purpose or "") or "").strip(),
                amount=amount,
                raw=row,
                errors=tuple(errors),
                category=(row.get(mapping.category or "") or "").strip(),
                owner_hint=(row.get(mapping.owner or "") or "").strip(),
            )
        )
    return out


def parse(
    raw: bytes,
    *,
    dialect: CsvDialect | None = None,
    mapping: ColumnMapping | None = None,
    amount_mode: str | None = None,
) -> ParseResult:
    if dialect is None:
        text, dialect = sniff(raw)
    else:
        text, _ = decode(raw)
    all_rows = list(csv.reader(io.StringIO(text), delimiter=dialect.delimiter))
    headers = [h.strip() for h in all_rows[dialect.header_row]] if dialect.header_row < len(all_rows) else []
    if mapping is None:
        mapping = detect_mapping(headers)
    mode = amount_mode or guess_amount_mode(mapping)
    dialect = CsvDialect(
        delimiter=dialect.delimiter,
        encoding=dialect.encoding,
        header_row=dialect.header_row,
        decimal_comma=dialect.decimal_comma,
        date_format=dialect.date_format,
        amount_mode=mode,
    )
    rows = parse_rows(text, dialect, mapping, amount_mode=mode)
    return ParseResult(dialect=dialect, headers=headers, mapping=mapping, rows=rows)
