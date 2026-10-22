"""Perioden-Flag „Erstattung/Nachzahlung im Endsaldo berücksichtigen"."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.allocation import compute_billing
from app.allocation.types import CostTypeInput, OwnerInput, PeriodInput, TxnInput
from app.models import BillingPeriod, Owner
from scripts.seed_2026 import seed
from tests.fixtures import abrechnung_2026 as fx

D = Decimal


def _mini(include_refunds: bool):
    """Zwei Eigentümer, nur Erstattungsbuchungen: Nachzahlung +446,54 / Guthaben −292,30."""
    owners = [OwnerInput("E1", D("500")), OwnerInput("E2", D("500"))]
    cts = [CostTypeInput("Erstattung/Nachzahlung", kind="erstattung")]
    txns = [
        TxnInput(date(2026, 9, 1), "Erstattung/Nachzahlung", D("446.54"), owner="E1"),
        TxnInput(date(2026, 9, 2), "Erstattung/Nachzahlung", D("-292.30"), owner="E2"),
    ]
    period = PeriodInput(
        date(2026, 8, 1), date(2027, 7, 31),
        hausgeld_carryover={"E1": D("834.07"), "E2": D("1184.07")},
        include_refunds=include_refunds,
    )
    return compute_billing(period, owners, cts, txns, [])


def test_flag_aus_ignoriert_erstattung():
    res = _mini(False)
    assert res.owner_result("E1").erstattung == 0
    assert res.owner_result("E1").hausgeld_endsaldo == D("834.07")
    assert res.owner_result("E2").hausgeld_endsaldo == D("1184.07")


def test_flag_an_verrechnet_eigentuemerbezogen_mit_vorzeichen():
    res = _mini(True)
    # eingegangene Nachzahlung erhöht, ausgezahltes Guthaben senkt den Endsaldo
    assert res.owner_result("E1").erstattung == D("446.54")
    assert res.owner_result("E1").hausgeld_endsaldo == D("1280.61")
    assert res.owner_result("E2").erstattung == D("-292.30")
    assert res.owner_result("E2").hausgeld_endsaldo == D("891.77")
    # Saldo gesamt folgt dem Endsaldo Hausgeld
    assert res.owner_result("E1").total_saldo == D("1280.61")


def test_erstattung_ohne_eigentuemer_wird_nie_verteilt():
    owners = [OwnerInput("E1", D("500")), OwnerInput("E2", D("500"))]
    cts = [CostTypeInput("Erstattung/Nachzahlung", kind="erstattung")]
    txns = [TxnInput(date(2026, 9, 1), "Erstattung/Nachzahlung", D("100"))]  # kein Eigentümer
    period = PeriodInput(date(2026, 8, 1), date(2027, 7, 31), include_refunds=True)
    res = compute_billing(period, owners, cts, txns, [])
    assert all(res.owner_result(c).erstattung == 0 for c in ("E1", "E2"))


def test_fixture_flag_aendert_nur_den_endsaldo():
    kwargs = dict(
        owners=fx.OWNERS, cost_types=fx.COST_TYPES, transactions=fx.TRANSACTIONS,
        overrides=fx.OVERRIDES,
    )
    ohne = compute_billing(fx.period_input(), **kwargs)
    mit = compute_billing(replace(fx.period_input(), include_refunds=True), **kwargs)

    # Kostenanteil, Hausgeld, Guthaben unverändert
    assert mit.cost_share_total == ohne.cost_share_total
    for code in ohne.owner_order:
        assert mit.owner_result(code).guthaben == ohne.owner_result(code).guthaben
    # Endsaldo wächst genau um die gebuchte Erstattung je Eigentümer (Excel-Buchungen)
    expected = {"E1": D("183.98"), "E2": D("2369.08"), "E3": D("286.78"), "E4": D("-309.03")}
    for code, amount in expected.items():
        diff = mit.owner_result(code).hausgeld_endsaldo - ohne.owner_result(code).hausgeld_endsaldo
        assert diff == amount


def test_flag_default_false_und_formular_speichert_es(client, db_session):
    seed(db_session, force=True)
    period = db_session.scalar(select(BillingPeriod))
    assert period.include_refunds is False

    # Übersicht ohne Flag: keine Spalte
    r = client.get(f"/abrechnungen/{period.id}")
    assert "Erstattung / Nachzahlung" not in r.text

    owner_fields = {
        f"carryover_{o.id}": "0,00"
        for o in db_session.scalars(select(Owner))
    }
    resp = client.post(
        f"/abrechnungen/{period.id}",
        data={"label": period.label, "start_date": "01.08.2025", "end_date": "31.07.2026",
              "reserve_opening_balance": "0", "include_refunds": "1", **owner_fields},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    db_session.expire_all()
    assert db_session.get(BillingPeriod, period.id).include_refunds is True

    r = client.get(f"/abrechnungen/{period.id}")
    assert "Erstattung / Nachzahlung" in r.text          # Spalte in der Hausgeldübersicht
    assert "Erstattung/Nachzahlung wird verrechnet" in r.text

    r = client.get(f"/abrechnungen/{period.id}/eigentuemer/E2")
    assert "Nachzahlung eingegangen" in r.text            # E2 hat +2.369,08 gebucht


def test_abgeschlossene_periode_laesst_flag_nicht_aendern(client, db_session):
    from app.models.enums import PeriodStatus

    seed(db_session, force=True)
    period = db_session.scalar(select(BillingPeriod))
    period.status = PeriodStatus.FINAL
    db_session.commit()

    client.post(
        f"/abrechnungen/{period.id}",
        data={"label": period.label, "include_refunds": "1"},
        follow_redirects=False,
    )
    db_session.expire_all()
    assert db_session.get(BillingPeriod, period.id).include_refunds is False
