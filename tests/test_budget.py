"""Wirtschaftsplan-Service: Monatsfenster, Grid-Aufbau, Overrides speichern."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Account, BillingPeriod, BudgetEntry, CostType, Owner, Transaction
from app.models.enums import AccountType, CostKind, PeriodStatus
from app.services import budget


@pytest.fixture
def data(db_session):
    giro = Account(name="Giro", type=AccountType.GIRO, opening_balance=Decimal("4000"))
    ruecklage = Account(name="Rücklage", type=AccountType.RUECKLAGE, opening_balance=Decimal("9999"))
    hausgeld = CostType(name="Hausgeld", kind=CostKind.HAUSGELD, sort_order=1)
    gas = CostType(name="Abschlag Gas/Strom/Wasser", kind=CostKind.BETRIEBSKOSTEN, sort_order=2)
    garten = CostType(name="Gartenpflege", kind=CostKind.BETRIEBSKOSTEN, sort_order=3)
    e1 = Owner(code="E1", mea=Decimal("500"))
    e2 = Owner(code="E2", mea=Decimal("500"))

    prev = BillingPeriod(
        label="Abrechnung 2025", start_date=date(2024, 8, 1), end_date=date(2025, 7, 31),
        status=PeriodStatus.FINAL,
    )
    cur = BillingPeriod(
        label="Abrechnung 2026", start_date=date(2025, 8, 1), end_date=date(2026, 7, 31),
        status=PeriodStatus.DRAFT,
    )
    db_session.add_all([giro, ruecklage, hausgeld, gas, garten, e1, e2, prev, cur])
    db_session.commit()

    # Vorperiode: Gas im 1. + 2. Monat (Aug/Sep 2024), Garten im 3. Monat (Oktober 2024)
    db_session.add_all([
        Transaction(account_id=giro.id, booking_date=date(2024, 8, 15), payee="EVU",
                    cost_type_id=gas.id, amount=Decimal("-745")),
        Transaction(account_id=giro.id, booking_date=date(2024, 9, 15), payee="EVU",
                    cost_type_id=gas.id, amount=Decimal("-745")),
        Transaction(account_id=giro.id, booking_date=date(2024, 10, 5), payee="Gärtner",
                    cost_type_id=garten.id, amount=Decimal("-86.67")),
        Transaction(account_id=giro.id, booking_date=date(2024, 8, 3), payee="E1",
                    cost_type_id=hausgeld.id, owner_id=e1.id, amount=Decimal("529")),
    ])
    # Girokonto-Bewegung VOR Periodenbeginn der laufenden Periode -> Anfangssaldo
    db_session.add(
        Transaction(account_id=giro.id, booking_date=date(2025, 6, 1), payee="E2",
                    cost_type_id=hausgeld.id, owner_id=e2.id, amount=Decimal("300"))
    )
    # Laufende Periode: Ist-Buchung Gas im 1. Monat (August 2025)
    db_session.add(
        Transaction(account_id=giro.id, booking_date=date(2025, 8, 20), payee="EVU",
                    cost_type_id=gas.id, amount=Decimal("-800"))
    )
    db_session.commit()
    return dict(giro=giro, ruecklage=ruecklage, hausgeld=hausgeld, gas=gas,
               garten=garten, prev=prev, cur=cur)


def test_month_windows_labels(data):
    windows = budget.month_windows(data["cur"])
    assert len(windows) == 12
    assert windows[0].label.startswith("August")
    assert windows[0].start == date(2025, 8, 1)
    assert windows[0].end == date(2025, 8, 31)
    assert windows[11].label.startswith("Juli")
    assert windows[11].end == date(2026, 7, 31)


def test_anfangssaldo_nur_girokonto(db_session, data):
    grid = budget.build_grid(db_session, data["cur"])
    # Girokonto: 4000 Anfangsbestand + alle Buchungen vor dem 01.08.2025
    #   -745 -745 (Gas) -86,67 (Garten) +529 +300 (Hausgeld) = 3252,33
    # Das Rücklagenkonto (9999) zählt NICHT mit.
    assert grid.anfangssaldo == Decimal("3252.33")


def test_ist_vor_vorschlag_pro_zelle(db_session, data):
    grid = budget.build_grid(db_session, data["cur"])
    m0 = grid.months[0]
    gas_cell = m0.cells[data["gas"].id]
    assert gas_cell.source == "ist"
    assert gas_cell.effective == Decimal("800.00")

    # Oktober (Index 2): kein Ist, aber Vorperiode hatte Gartenpflege -> Vorschlag
    m2 = grid.months[2]
    garten_cell = m2.cells[data["garten"].id]
    assert garten_cell.source == "prognose"
    assert garten_cell.effective == Decimal("86.67")

    # August: Gas-Vorschlag (745) wird vom Ist (800) verdeckt
    assert gas_cell.vorschlag == Decimal("745.00")


def test_laufender_saldo_und_summen(db_session, data):
    grid = budget.build_grid(db_session, data["cur"])
    running = grid.anfangssaldo
    for m in grid.months:
        running += m.differenz
        assert m.saldo == running
    assert grid.endsaldo == grid.months[-1].saldo
    # Gesamtausgaben = Summe aller Monatsausgaben
    assert grid.total_ausgaben == sum(m.ausgaben for m in grid.months)


def test_save_overrides_upsert_und_delete(db_session, data):
    cur, gas = data["cur"], data["gas"]
    # Monat 1 (September, Index 1): manueller Gas-Wert 750 (weicht vom Vorschlag 745 ab)
    budget.save_overrides(db_session, cur, {(1, gas.id): Decimal("750.00")})
    db_session.commit()
    entry = db_session.scalar(select(BudgetEntry).where(BudgetEntry.period_id == cur.id))
    assert entry is not None and entry.amount == Decimal("750.00")

    grid = budget.build_grid(db_session, cur)
    assert grid.months[1].cells[gas.id].source == "manuell"
    assert grid.months[1].cells[gas.id].effective == Decimal("750.00")

    # Zurück auf den Default (Vorschlag 745) -> Entry wird gelöscht
    budget.save_overrides(db_session, cur, {(1, gas.id): Decimal("745.00")})
    db_session.commit()
    assert db_session.scalar(select(BudgetEntry).where(BudgetEntry.period_id == cur.id)) is None


def test_save_overrides_ist_zelle_ueberschreiben(db_session, data):
    cur, gas = data["cur"], data["gas"]
    # Monat 0 hat Ist 800; manuell auf 800 -> kein Entry (== Default)
    budget.save_overrides(db_session, cur, {(0, gas.id): Decimal("800.00")})
    db_session.commit()
    assert db_session.scalar(select(BudgetEntry).where(BudgetEntry.period_id == cur.id)) is None
    # manuell auf 900 -> Entry
    budget.save_overrides(db_session, cur, {(0, gas.id): Decimal("900.00")})
    db_session.commit()
    grid = budget.build_grid(db_session, cur)
    assert grid.months[0].cells[gas.id].source == "manuell"
    assert grid.months[0].cells[gas.id].effective == Decimal("900.00")


def test_reset_loescht_alle_entries(db_session, data):
    cur, gas, garten = data["cur"], data["gas"], data["garten"]
    budget.save_overrides(db_session, cur, {
        (1, gas.id): Decimal("750.00"),
        (4, garten.id): Decimal("90.00"),
    })
    db_session.commit()
    assert db_session.scalars(select(BudgetEntry)).all()
    budget.reset(db_session, cur)
    db_session.commit()
    assert not db_session.scalars(select(BudgetEntry)).all()


def test_ohne_vorperiode_kein_vorschlag(db_session, data):
    grid = budget.build_grid(db_session, data["prev"])  # prev hat keine Vorperiode
    assert grid.previous_period_label is None
    for m in grid.months:
        for cell in m.cells.values():
            assert cell.vorschlag is None
