"""Referenzdatensatz aus der realen Beispiel-Abrechnung.

Quelle: ``XX Final Abrechnung 2026.xlsx`` – Blätter *Abrechnung 2026*, *Kontoauszug*,
*E1..E4*. Wirtschaftsjahr 01.08.2025 – 31.07.2026.

Der Datensatz wird sowohl vom Engine-Test (``tests/test_engine.py``) als auch vom
Seed-Skript (``scripts/seed_2026.py``) verwendet.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.allocation.types import (
    CostTypeInput,
    OverrideInput,
    OwnerInput,
    PeriodInput,
    TxnInput,
)

_XL_EPOCH = date(1899, 12, 30)


def xl(serial: int) -> date:
    """Excel-Datumsserie -> date."""
    return _XL_EPOCH + timedelta(days=serial)


def D(value) -> Decimal:
    return Decimal(str(value))


PERIOD_START = xl(45870)   # 2025-08-01
PERIOD_END = xl(46234)     # 2026-07-31

# Girokonto-Anfangssaldo (Postbank H4). In der Excel wird daraus der Saldovortrag
# Hausgeld je Eigentümer anteilig nach MEA gebildet; in der neuen App wird der
# Saldovortrag manuell je Eigentümer erfasst – hier reproduzieren wir die Excel.
GIRO_OPENING = D("10158.16")
RESERVE_OPENING_TOTAL = D("3499.72")


OWNERS: list[OwnerInput] = [
    OwnerInput(code="E1", mea=D("266.01"), name="Eigentümer 1"),
    OwnerInput(code="E2", mea=D("382"), name="Eigentümer 2"),
    OwnerInput(code="E3", mea=D("152.5"), name="Eigentümer 3"),
    OwnerInput(code="E4", mea=D("199.49"), name="Eigentümer 4"),
]

_HWB = "heizen_wasser_betrieb"
_VERS = "versicherungen"
_GEB = "gebuehren_abgaben"
_WART = "wartung_dienstleistung"

COST_TYPES: list[CostTypeInput] = [
    CostTypeInput("Heizkosten/Wasser/Betriebskosten", "betriebskosten", "zaehler", _HWB, "Stadtwerke"),
    CostTypeInput("Techem Miete und Dienstleistung", "betriebskosten", "mea", _HWB, "Techem"),
    CostTypeInput("Abschlag - Gas, Strom, Wasser", "betriebskosten", "vorauszahlung", _HWB, "Stadtwerke"),
    CostTypeInput("Haftpflicht", "betriebskosten", "mea", _VERS, "VGH"),
    CostTypeInput("Gebäudeversicherung", "betriebskosten", "mea", _VERS, "VGH"),
    CostTypeInput("Vermögenschadenhaftpflicht", "betriebskosten", "mea", _VERS, "VGH"),
    CostTypeInput("Grundbesitzabgaben", "betriebskosten", "mea", _GEB, "Stadt Osnabrück"),
    CostTypeInput("Bankgebühren", "betriebskosten", "mea", _GEB, "Postbank"),
    CostTypeInput("Schornsteinfeger", "betriebskosten", "mea", _WART, "Uwe Kemper"),
    CostTypeInput("Heizungswartung", "betriebskosten", "mea", _WART, "Sanitec"),
    CostTypeInput("Gehwegreinigung", "betriebskosten", "mea", _WART, "BS Gebäude-DL"),
    CostTypeInput("Gartenpflege", "betriebskosten", "mea", _WART, "T. Kluczek"),
    CostTypeInput("Sonstige Wartungs und Reparaturkosten", "betriebskosten", "mea", _WART, ""),
    CostTypeInput("Hausgeld", "hausgeld", "mea", "sonstiges", ""),
    CostTypeInput("Erstattung/Nachzahlung", "erstattung", "mea", "sonstiges", ""),
    CostTypeInput("Sonderzahlung Heizung", "sonderumlage", "mea", "sonstiges", ""),
    CostTypeInput("Heizungseinbau", "investition", "mea", "sonstiges", "Fa. Mihalev"),
]

OVERRIDES: list[OverrideInput] = [
    OverrideInput("Heizkosten/Wasser/Betriebskosten", "E1", D("1083.69")),
    OverrideInput("Heizkosten/Wasser/Betriebskosten", "E2", D("3760.67")),
    OverrideInput("Heizkosten/Wasser/Betriebskosten", "E3", D("1232.35")),
    OverrideInput("Heizkosten/Wasser/Betriebskosten", "E4", D("441.07")),
]

# (serial, payee, owner|None, cost_type, amount)  -- 1:1 aus dem Kontoauszug
_RAW_TX: list[tuple] = [
    (45870, "Eigentümergemeinschaft", "E2", "Hausgeld", 300),
    (45870, "Eigentümergemeinschaft", "E1", "Hausgeld", 200),
    (45881, "Techem Service GmbH", None, "Techem Miete und Dienstleistung", -782.9),
    (45883, "BS Dienstleistung", None, "Gehwegreinigung", -83.18),
    (45883, "Stadtkasse Osnabrück", None, "Grundbesitzabgaben", -241.95),
    (45884, "Stadtwerke Osnabrück", None, "Abschlag - Gas, Strom, Wasser", -510),
    (45900, "Postbank", None, "Bankgebühren", -19.1),
    (45901, "Eigentümergemeinschaft", "E4", "Erstattung/Nachzahlung", -309.03),
    (45901, "Eigentümergemeinschaft", "E2", "Hausgeld", 300),
    (45901, "Eigentümergemeinschaft", "E1", "Erstattung/Nachzahlung", 183.98),
    (45901, "Eigentümergemeinschaft", "E1", "Hausgeld", 200),
    (45901, "Eigentümergemeinschaft", "E3", "Erstattung/Nachzahlung", 286.78),
    (45903, "Eigentümergemeinschaft", "E3", "Hausgeld", 145),
    (45912, "Eigentümergemeinschaft", "E4", "Hausgeld", 145),
    (45915, "BS Dienstleistung", None, "Gehwegreinigung", -83.18),
    (45915, "Stadtwerke Osnabrück", None, "Abschlag - Gas, Strom, Wasser", -510),
    (45930, "Eigentümergemeinschaft", "E3", "Hausgeld", 160),
    (45930, "Postbank", None, "Bankgebühren", -20.22),
    (45931, "VGH Versicherung", None, "Haftpflicht", -159.58),
    (45931, "VGH-Versicherung", None, "Gebäudeversicherung", -1626.6),
    (45931, "Eigentümergemeinschaft", "E2", "Hausgeld", 300),
    (45931, "Eigentümergemeinschaft", "E1", "Hausgeld", 200),
    (45937, "Eigentümergemeinschaft", "E4", "Hausgeld", 145),
    (45944, "BS Dienstleistung", None, "Gehwegreinigung", -83.18),
    (45945, "Stadtwerke Osnabrück", None, "Abschlag - Gas, Strom, Wasser", -510),
    (45960, "Eigentümergemeinschaft", "E3", "Hausgeld", 160),
    (45960, "Postbank", None, "Bankgebühren", -2.5),
    (45961, "Postbank", None, "Bankgebühren", -16.94),
    (45964, "Eigentümergemeinschaft", "E2", "Hausgeld", 300),
    (45964, "Eigentümergemeinschaft", "E1", "Hausgeld", 200),
    (45965, "Eigentümergemeinschaft", "E4", "Hausgeld", 145),
    (45973, "Fa. Sanitec", None, "Heizungswartung", -343.01),
    (45978, "BS Dienstleistung", None, "Gehwegreinigung", -83.18),
    (45978, "Stadtkasse Osnabrück", None, "Grundbesitzabgaben", -242.01),
    (45978, "Stadtwerke Osnabrück", None, "Abschlag - Gas, Strom, Wasser", -510),
    (45991, "Postbank", None, "Bankgebühren", -19.38),
    (45992, "Eigentümergemeinschaft", "E2", "Hausgeld", 390),
    (45992, "Eigentümergemeinschaft", "E1", "Hausgeld", 200),
    (45992, "Eigentümergemeinschaft", "E3", "Hausgeld", 180),
    (45993, "Eigentümergemeinschaft", "E4", "Hausgeld", 188.5),
    (46006, "BS Dienstleistung", None, "Gehwegreinigung", -83.18),
    (46006, "Stadtwerke Osnabrück", None, "Abschlag - Gas, Strom, Wasser", -510),
    (46008, "Eigentümergemeinschaft", "E2", "Erstattung/Nachzahlung", 2369.08),
    (46009, "Fa. Kluczek", None, "Gartenpflege", -587.86),
    (46021, "Eigentümergemeinschaft", "E3", "Hausgeld", 180),
    (46022, "Postbank", None, "Bankgebühren", -18.14),
    (46024, "Eigentümergemeinschaft", "E2", "Hausgeld", 390),
    (46024, "Eigentümergemeinschaft", "E1", "Hausgeld", 260),
    (46028, "Eigentümergemeinschaft", "E4", "Hausgeld", 188.5),
    (46044, "Eigentümergemeinschaft", "E2", "Sonderzahlung Heizung", 2483),
    (46044, "Eigentümergemeinschaft", "E1", "Sonderzahlung Heizung", 1729.07),
    (46045, "BS Dienstleistung", None, "Gehwegreinigung", -86.67),
    (46045, "Eigentümergemeinschaft", "E4", "Sonderzahlung Heizung", 1296.69),
    (46049, "Eigentümergemeinschaft", "E3", "Sonderzahlung Heizung", 999.6),
    (46052, "Eigentümergemeinschaft", "E3", "Hausgeld", 180),
    (46052, "Postbank", None, "Bankgebühren", -19.02),
    (46055, "Eigentümergemeinschaft", "E2", "Hausgeld", 390),
    (46055, "Eigentümergemeinschaft", "E1", "Hausgeld", 260),
    (46062, "Stadtkasse Osnabrück", None, "Grundbesitzabgaben", -295.59),
    (46062, "Eigentümergemeinschaft", "E4", "Hausgeld", 188.5),
    (46070, "BS Dienstleistung", None, "Gehwegreinigung", -86.67),
    (46080, "Postbank", None, "Bankgebühren", -16.1),
    (46083, "Eigentümergemeinschaft", "E2", "Hausgeld", 390),
    (46083, "Eigentümergemeinschaft", "E1", "Hausgeld", 260),
    (46083, "Eigentümergemeinschaft", "E3", "Hausgeld", 180),
    (46093, "Fa. Mihalev", None, "Heizungseinbau", -13050.81),
    (46098, "BS Dienstleistung", None, "Gehwegreinigung", -86.67),
    (46108, "Eigentümergemeinschaft", "E4", "Hausgeld", 377),
    (46111, "Eigentümergemeinschaft", "E3", "Hausgeld", 180),
    (46111, "Postbank", None, "Bankgebühren", -19.38),
    (46113, "Eigentümergemeinschaft", "E2", "Hausgeld", 390),
    (46113, "Eigentümergemeinschaft", "E1", "Hausgeld", 260),
    (46129, "BS Dienstleistung", None, "Gehwegreinigung", -86.67),
    (46142, "Eigentümergemeinschaft", "E3", "Hausgeld", 180),
    (46142, "Postbank", None, "Bankgebühren", -15.82),
    (46143, "Eigentümergemeinschaft", "E1", "Hausgeld", 260),
    (46146, "Fa. Mihalev", None, "Heizungseinbau", -2785.77),
    (46146, "Eigentümergemeinschaft", "E2", "Hausgeld", 390),
    (46156, "BS Dienstleistung", None, "Gehwegreinigung", -86.67),
    (46157, "Stadtkasse Osnabrück", None, "Grundbesitzabgaben", -295.59),
    (46161, "Eigentümergemeinschaft", "E4", "Hausgeld", 188.5),
    (46171, "Postbank", None, "Bankgebühren", -19.1),
    (46174, "Eigentümergemeinschaft", "E2", "Hausgeld", 390),
    (46174, "Eigentümergemeinschaft", "E1", "Hausgeld", 260),
    (46174, "Eigentümergemeinschaft", "E3", "Hausgeld", 180),
    (46175, "Eigentümergemeinschaft", "E4", "Hausgeld", 188.5),
    (46188, "BS Dienstleistung", None, "Gehwegreinigung", -86.67),
    (46188, "VGH", None, "Vermögenschadenhaftpflicht", -149.94),
    (46203, "Stadtwerke Osnabrück", None, "Abschlag - Gas, Strom, Wasser", -231.46),
    (46203, "Eigentümergemeinschaft", "E3", "Hausgeld", 180),
    (46203, "Postbank", None, "Bankgebühren", -19.66),
    (46204, "Eigentümergemeinschaft", "E2", "Hausgeld", 390),
    (46204, "Eigentümergemeinschaft", "E1", "Hausgeld", 260),
    (46218, "Stadtwerke Osnabrück", None, "Abschlag - Gas, Strom, Wasser", -745),
    (46220, "BS Dienstleistung", None, "Gehwegreinigung", -86.67),
    (46234, "Postbank", None, "Bankgebühren", -15.82),
    # Sparkasse-Konto (zweiter Kontoblock im Excel-Kontoauszug):
    (46206, "Eigentümergemeinschaft", "E4", "Hausgeld", 188.5),
]

TRANSACTIONS: list[TxnInput] = [
    TxnInput(
        booking_date=xl(serial),
        payee=payee,
        owner=owner,
        cost_type=cost_type,
        amount=D(amount),
    )
    for serial, payee, owner, cost_type, amount in _RAW_TX
]


def hausgeld_carryover() -> dict[str, Decimal]:
    """Saldovortrag Hausgeld je Eigentümer wie in der Excel (Giro-Anfangssaldo × MEA)."""
    total_mea = sum((o.mea for o in OWNERS), Decimal("0"))
    return {o.code: GIRO_OPENING * o.mea / total_mea for o in OWNERS}


def period_input() -> PeriodInput:
    return PeriodInput(
        start_date=PERIOD_START,
        end_date=PERIOD_END,
        reserve_opening_balance=RESERVE_OPENING_TOTAL,
        hausgeld_carryover=hausgeld_carryover(),
    )
