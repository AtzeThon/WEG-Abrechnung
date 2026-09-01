"""Validierung der Berechnungs-Engine gegen die reale Beispiel-Abrechnung 2026."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

import pytest

from app.allocation import compute_billing
from tests.fixtures import abrechnung_2026 as fx

CENT = Decimal("0.01")


def cent(value) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


@pytest.fixture(scope="module")
def result():
    return compute_billing(
        period=fx.period_input(),
        owners=fx.OWNERS,
        cost_types=fx.COST_TYPES,
        transactions=fx.TRANSACTIONS,
        overrides=fx.OVERRIDES,
    )


# --------------------------------------------------------------------------- #
# Kostenanteil je Eigentümer  (Excel 'Abrechnung 2026' Spalte X, Zeilen 12-15)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "code, expected",
    [("E1", "2671.45"), ("E2", "6040.75"), ("E3", "2142.59"), ("E4", "1631.79")],
)
def test_kostenanteil_je_eigentuemer(result, code, expected):
    assert cent(result.owner_result(code).cost_share_total) == Decimal(expected)


def test_gesamtkostenanteil(result):
    # Excel X17
    assert cent(result.cost_share_total) == Decimal("12486.58")


# --------------------------------------------------------------------------- #
# Geleistetes Hausgeld  (Excel K24-K27)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "code, expected",
    [("E1", "2820.00"), ("E2", "4320.00"), ("E3", "1905.00"), ("E4", "1943.00")],
)
def test_geleistetes_hausgeld(result, code, expected):
    assert cent(result.owner_result(code).hausgeld_paid) == Decimal(expected)


# --------------------------------------------------------------------------- #
# Guthaben / Nachzahlung  (Excel M24-M27)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "code, expected",
    [("E1", "148.55"), ("E2", "-1720.75"), ("E3", "-237.59"), ("E4", "311.21")],
)
def test_guthaben_nachzahlung(result, code, expected):
    assert cent(result.owner_result(code).guthaben) == Decimal(expected)


# --------------------------------------------------------------------------- #
# Umlageschlüssel-Ergebnisse einzelner Kostenarten
# --------------------------------------------------------------------------- #
def test_zaehler_kostenart_gesamtbetrag(result):
    # Summe der Direkteingaben (Excel G10 / G17)
    ct = result.cost_types["Heizkosten/Wasser/Betriebskosten"]
    assert cent(ct.weg_total) == Decimal("6517.78")
    assert cent(ct.share("E1")) == Decimal("1083.69")


def test_vorauszahlung_wird_nicht_umgelegt(result):
    ct = result.cost_types["Abschlag - Gas, Strom, Wasser"]
    assert cent(ct.actual_cash) == Decimal("3526.46")   # tatsächlich geflossen
    assert cent(ct.weg_total) == Decimal("0.00")        # nicht auf Eigentümer umgelegt


def test_mea_kostenart_summe(result):
    ct = result.cost_types["Gehwegreinigung"]
    assert cent(ct.weg_total) == Decimal("1022.59")


# --------------------------------------------------------------------------- #
# Sonderumlage / Investition / Rücklage
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "code, expected",
    [("E1", "1729.07"), ("E2", "2483.00"), ("E3", "999.60"), ("E4", "1296.69")],
)
def test_sonderumlage_eigentuemerbezogen(result, code, expected):
    assert cent(result.owner_result(code).sonderumlage_paid) == Decimal(expected)


def test_investition_gesamt_und_anteil(result):
    assert cent(result.investition_total) == Decimal("15836.58")   # Excel J29
    # Anteil nach MEA (Excel J24)
    assert cent(result.owner_result("E1").investition_share) == Decimal("4212.69")


def test_ruecklage_anfangssaldo_nach_mea(result):
    assert cent(result.reserve_opening_total) == Decimal("3499.72")
    assert cent(result.owner_result("E1").reserve_opening) == Decimal("930.96")   # Excel P24
    assert cent(result.owner_result("E2").reserve_opening) == Decimal("1336.89")  # Excel P25
    summe = sum(
        (result.owner_result(c).reserve_opening for c in result.owner_order), Decimal("0")
    )
    assert cent(summe) == Decimal("3499.72")


# --------------------------------------------------------------------------- #
# Endsaldo Hausgeld  (Excel N24 – ABZÜGLICH der dort per MEA verteilten
# Erstattung/Nachzahlung, die in der neuen App noch nicht verrechnet wird)
# --------------------------------------------------------------------------- #
def test_endsaldo_hausgeld_e1(result):
    r = result.owner_result("E1")
    assert cent(r.hausgeld_endsaldo) == Decimal("367.10")
    # Gegenprobe Excel N24 = 1040,32 = 367,10 + 673,22 (Erstattungssumme × MEA-Anteil E1)
    assert cent(r.hausgeld_endsaldo + Decimal("673.2207681")) == Decimal("1040.32")


def test_saldo_gesamt_ist_hausgeld_plus_ruecklage(result):
    for code in result.owner_order:
        r = result.owner_result(code)
        assert r.total_saldo == r.hausgeld_endsaldo + r.reserve_endsaldo


# --------------------------------------------------------------------------- #
# Eigenschaften / Invarianten
# --------------------------------------------------------------------------- #
def test_summe_anteile_gleich_weg_gesamt_pro_kostenart(result):
    for name in result.cost_type_order:
        ct = result.cost_types[name]
        summe = sum((ct.share(c) for c in result.owner_order), Decimal("0"))
        assert cent(summe) == cent(ct.weg_total)


def test_datumsfilter_grenzen_inklusive():
    # Eine Buchung exakt am Start- und am Endtag zählt dazu, eine außerhalb nicht.
    from datetime import timedelta

    from app.allocation.types import CostTypeInput, OwnerInput, PeriodInput, TxnInput

    owners = [OwnerInput("E1", Decimal("1"))]
    cts = [CostTypeInput("X", "betriebskosten", "mea")]
    p = fx.PERIOD_START
    q = fx.PERIOD_END
    txns = [
        TxnInput(p, "X", Decimal("-10")),
        TxnInput(q, "X", Decimal("-10")),
        TxnInput(p - timedelta(days=1), "X", Decimal("-999")),
        TxnInput(q + timedelta(days=1), "X", Decimal("-999")),
    ]
    res = compute_billing(PeriodInput(p, q), owners, cts, txns, [])
    assert res.cost_types["X"].weg_total == Decimal("20")


def test_ruecklagenbewegung_verschiebt_nur_zwischen_konten():
    """Eine Rücklagen-Zuführung/-Entnahme lässt 'Saldo gesamt' unverändert."""
    from datetime import date

    from app.allocation.types import CostTypeInput, OwnerInput, PeriodInput, TxnInput

    owners = [OwnerInput("E1", Decimal("600")), OwnerInput("E2", Decimal("400"))]
    cts = [CostTypeInput("Rücklage", "ruecklage", "mea", "sonstiges")]
    p = PeriodInput(date(2026, 1, 1), date(2026, 12, 31), reserve_opening_balance=Decimal("1000"))

    base = compute_billing(p, owners, cts, [], [])
    # Zuführung 300 durch E1 (eigentümerbezogen)
    moved = compute_billing(
        p, owners, cts,
        [TxnInput(date(2026, 6, 1), "Rücklage", Decimal("300"), owner="E1")],
        [],
    )
    e1_base, e1_moved = base.owner_result("E1"), moved.owner_result("E1")
    assert e1_moved.reserve_endsaldo == e1_base.reserve_endsaldo + Decimal("300")
    assert e1_moved.hausgeld_endsaldo == e1_base.hausgeld_endsaldo - Decimal("300")
    assert e1_moved.total_saldo == e1_base.total_saldo  # Summe unverändert
    # E2 unberührt
    assert moved.owner_result("E2").total_saldo == base.owner_result("E2").total_saldo
