"""Perioden-Workflow: Abschließen sperrt Buchungen, Salden aus Vorperiode übernehmen."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Account, BillingPeriod, CostType, Owner, PeriodOpeningBalance, Transaction
from app.models.enums import AccountType, CostKind, PeriodStatus
from app.services.periods import carry_forward_balances


@pytest.fixture
def data(db_session):
    giro = Account(name="Giro", type=AccountType.GIRO, opening_balance=Decimal("0"))
    ct = CostType(name="Gehwegreinigung", kind=CostKind.BETRIEBSKOSTEN)
    e1 = Owner(code="E1", mea=Decimal("500"))
    e2 = Owner(code="E2", mea=Decimal("500"))
    p = BillingPeriod(
        label="2025", start_date=date(2025, 1, 1), end_date=date(2025, 12, 31),
        reserve_opening_balance=Decimal("1000"), status=PeriodStatus.DRAFT,
    )
    db_session.add_all([giro, ct, e1, e2, p])
    db_session.commit()
    db_session.add_all([
        PeriodOpeningBalance(period_id=p.id, owner_id=e1.id, hausgeld_carryover=Decimal("0")),
        PeriodOpeningBalance(period_id=p.id, owner_id=e2.id, hausgeld_carryover=Decimal("0")),
    ])
    db_session.commit()
    return dict(giro=giro, ct=ct, e1=e1, e2=e2, p=p)


def test_abschluss_sperrt_buchungen_im_zeitraum(client, db_session, data):
    p = data["p"]
    # Buchung im Zeitraum anlegen (noch Entwurf -> geht)
    client.post("/buchungen", data={
        "booking_date": "01.06.2025", "account_id": data["giro"].id,
        "cost_type_id": data["ct"].id, "amount": "-50",
    }, follow_redirects=True)
    txn = db_session.scalar(select(Transaction))
    assert txn is not None

    # Periode abschließen
    client.post(f"/abrechnungen/{p.id}/status", data={"target": "final"}, follow_redirects=True)
    db_session.expire_all()
    assert db_session.get(BillingPeriod, p.id).status == PeriodStatus.FINAL

    # Neue Buchung im Zeitraum -> abgelehnt
    r = client.post("/buchungen", data={
        "booking_date": "02.06.2025", "account_id": data["giro"].id,
        "cost_type_id": data["ct"].id, "amount": "-10",
    }, follow_redirects=True)
    assert "abgeschlossen" in r.text
    assert db_session.scalar(select(Transaction).where(Transaction.amount == Decimal("-10"))) is None

    # Bestehende Buchung löschen -> abgelehnt
    client.post(f"/buchungen/{txn.id}/loeschen", follow_redirects=True)
    db_session.expire_all()
    assert db_session.get(Transaction, txn.id) is not None

    # Buchung außerhalb des Zeitraums -> erlaubt
    r = client.post("/buchungen", data={
        "booking_date": "15.01.2026", "account_id": data["giro"].id,
        "cost_type_id": data["ct"].id, "amount": "-99",
    }, follow_redirects=True)
    assert db_session.scalar(select(Transaction).where(Transaction.amount == Decimal("-99"))) is not None

    # Wieder öffnen -> Buchung wieder möglich
    client.post(f"/abrechnungen/{p.id}/status", data={"target": "draft"}, follow_redirects=True)
    client.post("/buchungen", data={
        "booking_date": "02.06.2025", "account_id": data["giro"].id,
        "cost_type_id": data["ct"].id, "amount": "-10",
    }, follow_redirects=True)
    assert db_session.scalar(select(Transaction).where(Transaction.amount == Decimal("-10"))) is not None


def test_salden_aus_vorperiode_uebernehmen(client, db_session, data):
    prev = data["p"]
    # Vorperiode mit Buchungen + abschließen
    db_session.add_all([
        Transaction(account_id=data["giro"].id, booking_date=date(2025, 3, 1),
                    payee="x", cost_type_id=data["ct"].id, amount=Decimal("-200")),
    ])
    hg = CostType(name="Hausgeld", kind=CostKind.HAUSGELD)
    db_session.add(hg)
    db_session.commit()
    db_session.add_all([
        Transaction(account_id=data["giro"].id, booking_date=date(2025, 4, 1), payee="E1",
                    cost_type_id=hg.id, owner_id=data["e1"].id, amount=Decimal("300")),
    ])
    db_session.commit()

    nxt = BillingPeriod(
        label="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        reserve_opening_balance=Decimal("0"), status=PeriodStatus.DRAFT,
    )
    db_session.add(nxt)
    db_session.commit()
    for o in (data["e1"], data["e2"]):
        db_session.add(PeriodOpeningBalance(period_id=nxt.id, owner_id=o.id, hausgeld_carryover=Decimal("0")))
    db_session.commit()

    used = carry_forward_balances(db_session, nxt)
    db_session.commit()
    assert used.id == prev.id

    db_session.expire_all()
    nxt = db_session.get(BillingPeriod, nxt.id)
    # Rücklagen-Anfangssaldo der neuen Periode = Endsaldo Rücklage der Vorperiode (unverändert 1000)
    assert nxt.reserve_opening_balance == Decimal("1000.00")
    obs = {
        ob.owner_id: ob.hausgeld_carryover
        for ob in db_session.scalars(
            select(PeriodOpeningBalance).where(PeriodOpeningBalance.period_id == nxt.id)
        )
    }
    # E1 hat 300 Hausgeld gezahlt, Kostenanteil 100 (halbe 200) -> Guthaben 200 -> Endsaldo 200
    assert obs[data["e1"].id] == Decimal("200.00")
    assert obs[data["e2"].id] == Decimal("-100.00")  # kein Hausgeld, Kostenanteil 100
