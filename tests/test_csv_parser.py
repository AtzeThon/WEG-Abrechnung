"""Tests des reinen CSV-Parsers gegen synthetische Bank-Fixtures.

(Echte Bank-Exports werden ergänzt, sobald sie vorliegen.)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.imports import (
    AMOUNT_SOLL_HABEN,
    detect_mapping,
    header_signature,
    parse,
    sniff,
)

FIXTURES = Path(__file__).parent / "fixtures" / "bank_csv"


def load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


# --------------------------------------------------------------------------- #
# sniff: Encoding / Trennzeichen / Headerzeile
# --------------------------------------------------------------------------- #
def test_sniff_semikolon_utf8():
    _, dialect = sniff(load("generic_semikolon_utf8.csv"))
    assert dialect.delimiter == ";"
    assert dialect.encoding in ("utf-8-sig", "utf-8")
    assert dialect.header_row == 0


def test_sniff_cp1252_mit_praeambel():
    _, dialect = sniff(load("soll_haben_cp1252.csv"))
    assert dialect.delimiter == ";"
    assert dialect.encoding == "cp1252"
    assert dialect.header_row == 4  # 4 Präambelzeilen davor


def test_sniff_komma_mit_bom():
    _, dialect = sniff(load("sign_column_bom.csv"))
    assert dialect.delimiter == ","
    assert dialect.encoding == "utf-8-sig"


# --------------------------------------------------------------------------- #
# detect_mapping
# --------------------------------------------------------------------------- #
def test_detect_mapping_generic():
    m = detect_mapping(
        ["Buchungstag", "Beguenstigter/Zahlungspflichtiger", "Verwendungszweck", "Betrag", "Waehrung"]
    )
    assert m.date == "Buchungstag"
    assert m.payee == "Beguenstigter/Zahlungspflichtiger"
    assert m.purpose == "Verwendungszweck"
    assert m.amount == "Betrag"


def test_detect_mapping_soll_haben_umlaute():
    m = detect_mapping(
        ["Buchungstag", "Wertstellung", "Erläuterung", "Begünstigter/Auftraggeber",
         "Betrag Soll", "Betrag Haben", "Währung"]
    )
    assert m.date == "Buchungstag"
    assert m.payee == "Begünstigter/Auftraggeber"
    assert m.amount_debit == "Betrag Soll"
    assert m.amount_credit == "Betrag Haben"


# --------------------------------------------------------------------------- #
# parse: Ende-zu-Ende je Betragsmodus
# --------------------------------------------------------------------------- #
def test_parse_single_amount_deutsche_zahlen():
    result = parse(load("generic_semikolon_utf8.csv"))
    assert [r.amount for r in result.rows] == [
        Decimal("-510.00"), Decimal("200.00"), Decimal("-1782.90")
    ]
    assert result.rows[0].booking_date == date(2025, 8, 1)
    assert result.rows[0].payee == "Stadtwerke"
    assert all(r.ok for r in result.rows)
    # Leerzeile wird übersprungen, aber line_no bleibt korrekt
    assert result.rows[2].line_no == 5


def test_parse_soll_haben():
    result = parse(load("soll_haben_cp1252.csv"))
    assert result.dialect.amount_mode == AMOUNT_SOLL_HABEN
    amounts = [r.amount for r in result.rows]
    assert amounts == [Decimal("-83.18"), Decimal("300.00"), Decimal("-295.59")]
    assert result.rows[0].payee == "Hausmeisterdienst"


def test_parse_sign_column():
    result = parse(load("sign_column_bom.csv"))
    assert [r.amount for r in result.rows] == [Decimal("-587.86"), Decimal("999.60")]


def test_parse_messy_datei():
    result = parse(load("messy_utf8_bom.csv"))
    ok = [r for r in result.rows if r.ok]
    bad = [r for r in result.rows if not r.ok]
    assert [r.amount for r in ok] == [Decimal("-9.90"), Decimal("1234.56")]
    assert len(bad) == 2  # 'kein-datum' + 'abc'-Betrag
    assert any("Datum" in e for e in bad[0].errors)
    # Zusatzspalte ohne Header stört nicht
    assert "_extra_4" in result.rows[0].raw


def test_header_signature_stabil_gegen_reihenfolge_und_umlaute():
    a = header_signature(["Buchungstag", "Betrag", "Verwendungszweck"], ";")
    b = header_signature(["betrag", "buchungstag", "verwendungszweck"], ";")
    assert a == b
    assert a != header_signature(["Buchungstag", "Betrag", "Verwendungszweck"], ",")


@pytest.mark.parametrize("name", [
    "generic_semikolon_utf8.csv", "soll_haben_cp1252.csv", "sign_column_bom.csv", "messy_utf8_bom.csv",
    "finanztool_kategorie_cp1252.csv",
])
def test_parse_liefert_immer_ein_ergebnis(name):
    result = parse(load(name))
    assert result.headers
    assert isinstance(result.rows, list)


# --------------------------------------------------------------------------- #
# Echte Beispieldatei (Finanztool-Export mit Kategorie-/Eigentümer-Spalte)
# --------------------------------------------------------------------------- #
def test_finanztool_export_erkennung():
    result = parse(load("finanztool_kategorie_cp1252.csv"))
    assert result.dialect.encoding == "cp1252"
    assert result.dialect.delimiter == ";"
    assert result.dialect.header_row == 0
    m = result.mapping
    assert m.date == "Wertstellung"
    assert m.payee == "Empfänger/Auftraggeber"
    assert m.purpose == "Verwendungszweck"
    assert m.amount == "Betrag"
    assert m.category == "Kategorie"


def test_finanztool_betraege_und_kategorie():
    result = parse(load("finanztool_kategorie_cp1252.csv"))
    assert len(result.rows) == 12  # Leerzeile am Ende übersprungen
    r = result.rows[0]
    assert r.amount == Decimal("1.00")
    assert r.category == "man. Buchungen"
    # Zeile mit Tausenderpunkt
    umbuchung = next(x for x in result.rows if x.category == "04 Umbuchungen")
    assert umbuchung.amount == Decimal("2500.00")
    # Eigentümer-Spalte 'Frei 3' muss manuell gemappt werden -> hier per Mapping
    from app.imports import ColumnMapping, parse_rows
    rows = parse_rows(
        load("finanztool_kategorie_cp1252.csv").decode("cp1252"),
        result.dialect,
        ColumnMapping(**{**result.mapping.__dict__, "owner": "Frei 3"}),
    )
    hausgeld = next(x for x in rows if x.category == "Hausgeld")
    assert hausgeld.owner_hint in {"E1", "E2", "E3", "E4"}
