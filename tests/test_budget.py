"""Wirtschaftsplan-Service: Monatsfenster, Grid-Aufbau, Overrides speichern."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Account, BillingPeriod, BudgetEntry, CostType, Owner, Transaction
from app.models.enums import AccountType, CostKind, PeriodStatus
from app.services import budget

# „Heute" für die Grid-Tests: Periodenbeginn, damit noch kein Monat abgeschlossen
# ist (abgeschlossene Monate zeigen Ist statt Plan – eigene Tests dafür).
PLAN_TODAY = date(2025, 8, 1)


@pytest.fixture
def data(db_session):
    giro = Account(name="Giro", type=AccountType.GIRO, opening_balance=Decimal("4000"))
    ruecklage = Account(name="Rücklage", type=AccountType.RUECKLAGE, opening_balance=Decimal("9999"))
    hausgeld = CostType(name="Hausgeld", kind=CostKind.HAUSGELD, sort_order=1)
    gas = CostType(name="Abschlag Gas/Strom/Wasser", kind=CostKind.BETRIEBSKOSTEN, sort_order=2)
    garten = CostType(name="Gartenpflege", kind=CostKind.BETRIEBSKOSTEN, sort_order=3)
    ungenutzt = CostType(name="Ungenutzte Kostenart", kind=CostKind.BETRIEBSKOSTEN, sort_order=4)
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
    db_session.add_all([giro, ruecklage, hausgeld, gas, garten, ungenutzt, e1, e2, prev, cur])
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
               garten=garten, ungenutzt=ungenutzt, prev=prev, cur=cur)


def test_betrag_filter_zwei_nachkommastellen():
    from app.locale import betrag, geld

    assert betrag(Decimal("782.9")) == "782,90"
    assert betrag(Decimal("1234.5")) == "1234,50"  # kein Tausendertrenner im Eingabefeld
    assert betrag(None) == "0,00"
    assert geld(Decimal("1234.5")) == "1.234,50"  # Anzeige mit Tausendertrenner
    assert geld(Decimal("-11769.86")) == "-11.769,86"


def test_month_windows_labels(data):
    windows = budget.month_windows(data["cur"])
    assert len(windows) == 12
    assert windows[0].label.startswith("August")
    assert windows[0].start == date(2025, 8, 1)
    assert windows[0].end == date(2025, 8, 31)
    assert windows[11].label.startswith("Juli")
    assert windows[11].end == date(2026, 7, 31)


def test_anfangssaldo_nur_girokonto(db_session, data):
    grid = budget.build_grid(db_session, data["cur"], today=PLAN_TODAY)
    # Girokonto: 4000 Anfangsbestand + alle Buchungen vor dem 01.08.2025
    #   -745 -745 (Gas) -86,67 (Garten) +529 +300 (Hausgeld) = 3252,33
    # Das Rücklagenkonto (9999) zählt NICHT mit.
    assert grid.anfangssaldo == Decimal("3252.33")


def test_ist_vor_vorschlag_pro_zelle(db_session, data):
    grid = budget.build_grid(db_session, data["cur"], today=PLAN_TODAY)
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
    grid = budget.build_grid(db_session, data["cur"], today=PLAN_TODAY)
    running = grid.anfangssaldo
    for m in grid.months:
        running += m.differenz
        assert m.saldo == running
    assert grid.endsaldo == grid.months[-1].saldo
    # Gesamtausgaben = Summe aller Monatsausgaben
    assert grid.total_ausgaben == sum(m.ausgaben for m in grid.months)


def test_erstattung_zaehlt_zu_den_einnahmen(db_session, data):
    cur = data["cur"]
    erst = CostType(name="Erstattung/Nachzahlung", kind=CostKind.ERSTATTUNG, sort_order=9)
    db_session.add(erst)
    db_session.commit()
    # Nachzahlung des Eigentümers (Geldzufluss, positiv gebucht) im 1. Monat
    db_session.add(
        Transaction(account_id=data["giro"].id, booking_date=date(2025, 8, 25), payee="E1",
                    cost_type_id=erst.id, amount=Decimal("183.98"))
    )
    db_session.commit()

    grid = budget.build_grid(db_session, cur, today=PLAN_TODAY)
    assert erst in grid.income_types
    assert erst not in grid.expense_types
    cell = grid.months[0].cells[erst.id]
    assert cell.source == "ist"
    assert cell.effective == Decimal("183.98")  # positiv, nicht -183,98
    assert grid.months[0].einnahmen >= Decimal("183.98")


def test_abgeschlossener_monat_zeigt_ist_statt_plan(db_session, data):
    cur, gas = data["cur"], data["gas"]
    # Vorab (vor Jahresbeginn) einen Planwert für August und September erfassen.
    budget.save_overrides(
        db_session, cur, {(0, gas.id): Decimal("999.00"), (1, gas.id): Decimal("999.00")},
        today=PLAN_TODAY,
    )
    db_session.commit()

    # Wir sind im September: August (Index 0) ist abgeschlossen, September (1) läuft.
    sept = date(2025, 9, 15)
    grid = budget.build_grid(db_session, cur, today=sept)

    aug = grid.months[0].cells[gas.id]
    assert grid.months[0].is_past is True
    assert aug.is_past is True
    assert aug.source == "ist"
    assert aug.effective == Decimal("800.00")  # Ist verdrängt den Planwert 999

    sep = grid.months[1].cells[gas.id]
    assert grid.months[1].is_past is False
    assert sep.source == "manuell"
    assert sep.effective == Decimal("999.00")  # laufender Monat -> Plan gilt weiter

    # Am Jahresanfang gilt für August noch der Plan.
    grid0 = budget.build_grid(db_session, cur, today=PLAN_TODAY)
    assert grid0.months[0].cells[gas.id].effective == Decimal("999.00")


def test_abgeschlossener_monat_nur_ist_kein_plan(db_session, data):
    cur, garten, gas = data["cur"], data["garten"], data["gas"]
    # Planwert für Oktober-Gartenpflege erfasst; es wird nie gebucht.
    budget.save_overrides(db_session, cur, {(2, garten.id): Decimal("120.00")}, today=PLAN_TODAY)
    db_session.commit()
    grid = budget.build_grid(db_session, cur, today=date(2025, 12, 1))

    # Abgeschlossener Monat ohne Buchung -> 0, weder Plan- noch Vorjahreswert.
    garten_cell = grid.months[2].cells[garten.id]
    assert garten_cell.is_past is True
    assert garten_cell.source == "leer"
    assert garten_cell.effective == Decimal("0.00")

    # gas Monat 2 hätte einen Vorjahres-Vorschlag – im abgeschlossenen Monat trotzdem 0.
    gas_cell = grid.months[2].cells[gas.id]
    assert gas_cell.effective == Decimal("0.00")
    assert gas_cell.source == "leer"


def test_abgeschlossener_monat_zaehlt_nachtraegliche_buchung(db_session, data):
    cur, gas = data["cur"], data["gas"]
    # Buchung mit Buchungsdatum im (bereits abgeschlossenen) August, erst im
    # September erfasst -> muss im August-Feld des Wirtschaftsplans auftauchen.
    db_session.add(
        Transaction(account_id=data["giro"].id, booking_date=date(2025, 8, 30), payee="Rechnung spät",
                    cost_type_id=gas.id, amount=Decimal("-50.00"))
    )
    db_session.commit()
    grid = budget.build_grid(db_session, cur, today=date(2025, 9, 20))
    aug = grid.months[0].cells[gas.id]
    assert aug.is_past is True
    # August-Ist = 800 (20.08.) + 50 (30.08.) = 850
    assert aug.effective == Decimal("850.00")
    assert aug.source == "ist"


def test_save_overrides_upsert_und_delete(db_session, data):
    cur, gas = data["cur"], data["gas"]
    # Monat 1 (September, Index 1): manueller Gas-Wert 750 (weicht vom Vorschlag 745 ab)
    budget.save_overrides(db_session, cur, {(1, gas.id): Decimal("750.00")}, today=PLAN_TODAY)
    db_session.commit()
    entry = db_session.scalar(select(BudgetEntry).where(BudgetEntry.period_id == cur.id))
    assert entry is not None and entry.amount == Decimal("750.00")

    grid = budget.build_grid(db_session, cur, today=PLAN_TODAY)
    assert grid.months[1].cells[gas.id].source == "manuell"
    assert grid.months[1].cells[gas.id].effective == Decimal("750.00")

    # Zurück auf den Default (Vorschlag 745) -> Entry wird gelöscht
    budget.save_overrides(db_session, cur, {(1, gas.id): Decimal("745.00")}, today=PLAN_TODAY)
    db_session.commit()
    assert db_session.scalar(select(BudgetEntry).where(BudgetEntry.period_id == cur.id)) is None


def test_save_overrides_ist_zelle_ueberschreiben(db_session, data):
    cur, gas = data["cur"], data["gas"]
    # Monat 0 hat Ist 800; manuell auf 800 -> kein Entry (== Default)
    budget.save_overrides(db_session, cur, {(0, gas.id): Decimal("800.00")}, today=PLAN_TODAY)
    db_session.commit()
    assert db_session.scalar(select(BudgetEntry).where(BudgetEntry.period_id == cur.id)) is None
    # manuell auf 900 -> Entry
    budget.save_overrides(db_session, cur, {(0, gas.id): Decimal("900.00")}, today=PLAN_TODAY)
    db_session.commit()
    grid = budget.build_grid(db_session, cur, today=PLAN_TODAY)
    assert grid.months[0].cells[gas.id].source == "manuell"
    assert grid.months[0].cells[gas.id].effective == Decimal("900.00")


def test_reset_loescht_alle_entries(db_session, data):
    cur, gas, garten = data["cur"], data["gas"], data["garten"]
    budget.save_overrides(db_session, cur, {
        (1, gas.id): Decimal("750.00"),
        (4, garten.id): Decimal("90.00"),
    }, today=PLAN_TODAY)
    db_session.commit()
    assert db_session.scalars(select(BudgetEntry)).all()
    budget.reset(db_session, cur)
    db_session.commit()
    assert not db_session.scalars(select(BudgetEntry)).all()


def test_ohne_vorperiode_kein_vorschlag(db_session, data):
    grid = budget.build_grid(db_session, data["prev"], today=PLAN_TODAY)  # prev hat keine Vorperiode
    assert grid.previous_period_label is None
    for m in grid.months:
        for cell in m.cells.values():
            assert cell.vorschlag is None


# --------------------------------------------------------------------------- #
# Web-Routen
# --------------------------------------------------------------------------- #
def test_budget_view_rendert_grid(client, data):
    r = client.get(f"/wirtschaftsplan/{data['cur'].id}")
    assert r.status_code == 200
    assert "Wirtschaftsplan" in r.text
    assert "August" in r.text and "Juli" in r.text
    assert data["gas"].name in r.text


def test_budget_save_und_reset_ueber_route(client, db_session, data):
    cur, gas = data["cur"], data["gas"]
    r = client.post(
        f"/wirtschaftsplan/{cur.id}",
        # Monat 1: 750 weicht vom Vorschlag 745 ab -> Entry.
        # Monat 0: 800 entspricht dem Ist -> kein Entry.
        data={f"v_1_{gas.id}": "750,00", f"v_0_{gas.id}": "800,00"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    entries = db_session.scalars(select(BudgetEntry).where(BudgetEntry.period_id == cur.id)).all()
    assert len(entries) == 1
    assert entries[0].month_index == 1 and entries[0].amount == Decimal("750.00")

    client.post(f"/wirtschaftsplan/{cur.id}/zuruecksetzen", follow_redirects=True)
    db_session.expire_all()
    assert not db_session.scalars(select(BudgetEntry).where(BudgetEntry.period_id == cur.id)).all()


def test_budget_pdf_ohne_leere_spalten_und_ohne_fehler(client, db_session, data):
    # „garten" hat keine Ist-/Vorschlags-/Manuellwerte -> Spalte fällt im PDF weg.
    from app.routers.budget import _grid_context

    ctx = _grid_context(db_session, data["cur"], pdf=True)
    names = [c.name for c in ctx["grid"].expense_types]
    assert data["gas"].name in names
    assert data["ungenutzt"].name not in names

    # Route rendert das Template (pdf=1); ohne WeasyPrint -> 303-Fallback, kein 500.
    r = client.get(f"/wirtschaftsplan/{data['cur'].id}/pdf", follow_redirects=False)
    assert r.status_code in (200, 303)


def test_budget_index_leitet_bei_einer_periode_weiter(client, db_session):
    p = BillingPeriod(
        label="Nur eine", start_date=date(2025, 1, 1), end_date=date(2025, 12, 31),
        status=PeriodStatus.DRAFT,
    )
    db_session.add(p)
    db_session.commit()
    r = client.get("/wirtschaftsplan", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].endswith(f"/wirtschaftsplan/{p.id}")


# --------------------------------------------------------------------------- #
# Jahresvergleich
# --------------------------------------------------------------------------- #
def test_build_comparison_differenzen(db_session, data):
    cur, prev, gas, garten = data["cur"], data["prev"], data["gas"], data["garten"]

    grid = budget.build_comparison(db_session, cur, prev, today=PLAN_TODAY)
    m0 = grid.months[0]
    # Gas Monat 0: cur = Ist 800, prev = Ist 745 -> Differenz 55
    assert m0.cells[gas.id].a == Decimal("800.00")
    assert m0.cells[gas.id].b == Decimal("745.00")
    assert m0.cells[gas.id].diff == Decimal("55.00")
    # Gas Monat 1: cur = Vorschlag 745 (aus prev), prev = Ist 745 -> Differenz 0
    assert grid.months[1].cells[gas.id].diff == Decimal("0.00")

    # Manuelle Überschreibung in cur schlägt in der Differenz durch
    budget.save_overrides(db_session, cur, {(3, garten.id): Decimal("120.00")}, today=PLAN_TODAY)
    db_session.commit()
    grid = budget.build_comparison(db_session, cur, prev, today=PLAN_TODAY)
    m3 = grid.months[3]
    assert m3.cells[garten.id].a == Decimal("120.00")
    assert m3.cells[garten.id].b == Decimal("0.00")
    assert m3.cells[garten.id].diff == Decimal("120.00")

    # Summen-Differenz konsistent
    assert grid.total_ausgaben.diff == grid.total_ausgaben.a - grid.total_ausgaben.b


def test_compare_index_und_pdf_routen(client, data):
    cur, prev = data["cur"], data["prev"]

    r = client.get("/jahresvergleich")
    assert r.status_code == 200
    assert "Jahresvergleich" in r.text
    assert cur.label in r.text and prev.label in r.text

    r = client.get(f"/jahresvergleich?jahr={prev.id}&vergleich={cur.id}")
    assert r.status_code == 200

    r = client.get("/jahresvergleich/pdf", follow_redirects=False)
    assert r.status_code in (200, 303)


def test_compare_index_ohne_zweite_periode(client, db_session):
    db_session.add(
        BillingPeriod(
            label="Einzige", start_date=date(2025, 1, 1), end_date=date(2025, 12, 31),
            status=PeriodStatus.DRAFT,
        )
    )
    db_session.commit()
    r = client.get("/jahresvergleich")
    assert r.status_code == 200
    assert "zwei Abrechnungsperioden" in r.text
