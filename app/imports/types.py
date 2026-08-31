"""Datenstrukturen des CSV-Parsers – rein, ohne DB-/Web-Abhängigkeit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

# Betragslogik einer Bank-CSV
AMOUNT_SINGLE = "single"                 # eine Betragsspalte, Vorzeichen im Wert
AMOUNT_SOLL_HABEN = "soll_haben"         # getrennte Soll-/Haben-Spalten
AMOUNT_SIGN_COLUMN = "betrag_vorzeichen"  # Betragsspalte + separate S/H-Kennzeichen-Spalte
AMOUNT_MODES = (AMOUNT_SINGLE, AMOUNT_SOLL_HABEN, AMOUNT_SIGN_COLUMN)

# Zielfelder des Mappings (Reihenfolge = Anzeige im Assistenten)
TARGET_FIELDS = (
    "date", "payee", "purpose", "amount", "amount_debit", "amount_credit",
    "sign_column", "category", "owner",
)
TARGET_LABELS = {
    "date": "Buchungsdatum",
    "payee": "Zahlungspartner",
    "purpose": "Verwendungszweck / Buchungstext",
    "amount": "Betrag",
    "amount_debit": "Betrag Soll / Belastung",
    "amount_credit": "Betrag Haben / Gutschrift",
    "sign_column": "Soll/Haben-Kennzeichen",
    "category": "Kategorie → Kostenart (Vorschlag)",
    "owner": "Spalte mit Eigentümer-Kürzel (Vorschlag)",
}


@dataclass(frozen=True)
class CsvDialect:
    delimiter: str = ";"
    encoding: str = "utf-8-sig"
    header_row: int = 0            # 0-basiert; Zeilen davor sind Präambel
    decimal_comma: bool = True
    date_format: str | None = None
    amount_mode: str = AMOUNT_SINGLE


@dataclass(frozen=True)
class ColumnMapping:
    date: str | None = None
    payee: str | None = None
    purpose: str | None = None
    amount: str | None = None
    amount_debit: str | None = None
    amount_credit: str | None = None
    sign_column: str | None = None
    # optional: Spalten mit fertiger fachlicher Zuordnung (nur Vorschlag)
    category: str | None = None      # -> Kostenart per Namensabgleich
    owner: str | None = None         # -> Eigentümer per Kürzel

    def amount_ready(self, mode: str) -> bool:
        if mode == AMOUNT_SOLL_HABEN:
            return bool(self.amount_debit and self.amount_credit)
        if mode == AMOUNT_SIGN_COLUMN:
            return bool(self.amount and self.sign_column)
        return bool(self.amount)

    def is_complete(self, mode: str) -> bool:
        return bool(self.date) and self.amount_ready(mode)

    def as_dict(self) -> dict[str, str]:
        return {k: v for k, v in self.__dict__.items() if v}


@dataclass(frozen=True)
class ParsedRow:
    line_no: int
    booking_date: date | None
    payee: str
    purpose: str
    amount: Decimal | None
    raw: dict[str, str]
    errors: tuple[str, ...] = ()
    category: str = ""      # Rohwert der Kategorie-Spalte (falls gemappt)
    owner_hint: str = ""    # Rohwert der Eigentümer-Spalte (falls gemappt)

    @property
    def ok(self) -> bool:
        return not self.errors and self.booking_date is not None and self.amount is not None


@dataclass(frozen=True)
class ParseResult:
    dialect: CsvDialect
    headers: list[str]
    mapping: ColumnMapping
    rows: list[ParsedRow]

    @property
    def ok_rows(self) -> list[ParsedRow]:
        return [r for r in self.rows if r.ok]
