"""Umbuchung zwischen Rücklagen- und Hausgeldkonto."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.allocation import compute_billing
from app.allocation.types import CostTypeInput, OwnerInput, PeriodInput, TxnInput
from app.models import Account, BillingPeriod, Owner, PeriodOpeningBalance, Transaction
from app.models.enums import AccountType, CostKind
from app.services.billing import compute_period
from app.services.transfers import record_transfer


@pytest.fixture
def konten(db_session):
    giro = Account(name="Girokonto", type=AccountType.GIRO, opening_balance=Decimal("0"))
    ruecklage = Account(name="Rücklagenkonto", type=AccountType.RUECKLAGE, opening_balance=Decimal("0"))
    e1 = Owner(code="E1", mea=Decimal("600"))
    e2 = Owner(code="E2", mea=Decimal("400"))
    p = BillingPeriod(label="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
                      reserve_opening_balance=Decimal("2000"))
    db_session.add_all([giro, ruecklage, e1, e2, p])
    db_session.commit()
    for o in (e1, e2):
        db_session.add(PeriodOpeningBalance(period_id=p.id, owner_id=o.id, hausgeld_carryover=Decimal("0")))
    db_session.commit()
    return dict(giro=giro, ruecklage=ruecklage, e1=e1, e2=e2, p=p)


def test_record_transfer_legt_zwei_buchungen_an(db_session, konten):
    src, dst = record_transfer(
        db_session,
        from_account_id=konten["giro"].id,
        to_account_id=konten["ruecklage"].id,
        amount=Decimal("500"),
        booking_date=date(2026, 6, 1),
        owner_id=None,
        note="Zuführung",
    )
    db_session.commit()
    assert src.amount == Decimal("-500") and src.account_id == konten["giro"].id
    assert dst.amount == Decimal("500") and dst.account_id == konten["ruecklage"].id
    # Rücklagen-Bein hat Typ Rücklage, Giro-Bein ist neutral
    assert dst.cost_type.kind == CostKind.RUECKLAGE
    assert src.cost_type.kind == CostKind.UMBUCHUNG


def test_zufuehrung_neutral_fuer_saldo_gesamt(db_session, konten):
    record_transfer(
        db_session, from_account_id=konten["giro"].id, to_account_id=konten["ruecklage"].id,
        amount=Decimal("500"), booking_date=date(2026, 6, 1), owner_id=None, note="",
    )
    db_session.commit()
    res = compute_period(db_session, konten["p"])
    e1 = res.owner_result("E1")
    # Rücklage +500 (MEA-Anteil E1 = 300), Hausgeld -300 -> Saldo gesamt unverändert
    assert e1.reserve_endsaldo == Decimal("2000") * Decimal("0.6") + Decimal("300")
    assert e1.hausgeld_endsaldo == Decimal("-300")
    assert e1.total_saldo == Decimal("1200")  # = 2000*0.6, wie ohne Umbuchung


def test_neutrale_buchung_wird_von_der_engine_ignoriert():
    owners = [OwnerInput("E1", Decimal("1"))]
    cts = [CostTypeInput("Umbuchung (neutral)", "umbuchung", "mea", "sonstiges")]
    p = PeriodInput(date(2026, 1, 1), date(2026, 12, 31))
    res = compute_billing(
        p, owners, cts, [TxnInput(date(2026, 5, 1), "Umbuchung (neutral)", Decimal("-9999"))], []
    )
    assert res.cost_share_total == Decimal("0")
    assert res.owner_result("E1").total_saldo == Decimal("0")


def test_umbuchung_route(client, db_session, konten):
    r = client.post("/buchungen/umbuchung", data={
        "from_account_id": konten["ruecklage"].id, "to_account_id": konten["giro"].id,
        "amount": "300,00", "booking_date": "01.07.2026",
    }, follow_redirects=False)
    assert r.status_code == 303
    txns = db_session.scalars(select(Transaction)).all()
    assert len(txns) == 2
    assert {t.amount for t in txns} == {Decimal("-300.00"), Decimal("300.00")}
