"""Tests der Buchungserfassung: Anlegen, Filtern, Ledger, Inline-Kostenart."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models import Account, CostType, Owner, Transaction
from app.models.enums import AccountType, CostKind


def _base_data(db):
    giro = Account(name="Giro", type=AccountType.GIRO, opening_balance=Decimal("100"))
    ct = CostType(name="Gehwegreinigung", kind=CostKind.BETRIEBSKOSTEN)
    hg = CostType(name="Hausgeld", kind=CostKind.HAUSGELD)
    e1 = Owner(code="E1", mea=Decimal("500"))
    db.add_all([giro, ct, hg, e1])
    db.commit()
    return giro, ct, hg, e1


def test_create_transaction_deutsche_eingabe(client, db_session):
    giro, ct, _hg, _e1 = _base_data(db_session)
    r = client.post("/buchungen", data={
        "booking_date": "15.03.2026", "payee": "Dienstleister", "account_id": giro.id,
        "cost_type_id": ct.id, "amount": "-83,18", "note": "März",
    }, follow_redirects=True)
    assert r.status_code == 200
    txn = db_session.scalar(select(Transaction))
    assert txn.amount == Decimal("-83.18")
    assert txn.booking_date == date(2026, 3, 15)


def test_filter_nach_kostenart_und_text(client, db_session):
    giro, ct, hg, e1 = _base_data(db_session)
    db_session.add_all([
        Transaction(account_id=giro.id, booking_date=date(2026, 1, 1), payee="A",
                    cost_type_id=ct.id, amount=Decimal("-10")),
        Transaction(account_id=giro.id, booking_date=date(2026, 1, 2), payee="Hausgeld Zahler",
                    cost_type_id=hg.id, owner_id=e1.id, amount=Decimal("200")),
    ])
    db_session.commit()

    r = client.get(f"/buchungen?cost_type_id={hg.id}")
    assert "Hausgeld Zahler" in r.text and ">A<" not in r.text

    r = client.get("/buchungen?q=zahler")
    assert "Hausgeld Zahler" in r.text


def test_account_ledger_running_balance(client, db_session):
    giro, ct, _hg, _e1 = _base_data(db_session)
    db_session.add_all([
        Transaction(account_id=giro.id, booking_date=date(2026, 1, 1), payee="A",
                    cost_type_id=ct.id, amount=Decimal("-30")),
        Transaction(account_id=giro.id, booking_date=date(2026, 1, 2), payee="B",
                    cost_type_id=ct.id, amount=Decimal("-20")),
    ])
    db_session.commit()
    r = client.get(f"/buchungen/kontoauszug/{giro.id}")
    assert r.status_code == 200
    # Anfangssaldo 100 -> 70 -> 50
    assert "50,00" in r.text


def test_inline_kostenart_anlegen(client, db_session):
    r = client.post("/kostenarten/inline-neu", data={
        "name": "Neue Art", "category": "sonstiges", "kind": "betriebskosten",
        "allocation_strategy": "mea",
    })
    assert r.status_code == 200
    assert "<option" in r.text and "Neue Art" in r.text
    assert db_session.scalar(select(CostType).where(CostType.name == "Neue Art")) is not None
