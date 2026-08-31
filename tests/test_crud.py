"""CRUD-Tests für die Stammdaten (Eigentümer, Konten, Kostenarten)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from app.models import Account, CostType, Owner


def test_owner_crud(client, db_session):
    r = client.post(
        "/eigentuemer",
        data={"code": "E1", "name": "Max Muster", "email": "m@example.de", "mea": "266,01", "active": "1"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    owner = db_session.scalar(select(Owner).where(Owner.code == "E1"))
    assert owner is not None and owner.mea == Decimal("266.01")

    client.post(f"/eigentuemer/{owner.id}", data={"code": "E1", "name": "Neu", "mea": "266,01"},
                follow_redirects=True)
    db_session.expire_all()
    assert db_session.get(Owner, owner.id).name == "Neu"

    client.post(f"/eigentuemer/{owner.id}/loeschen", follow_redirects=True)
    assert db_session.scalar(select(Owner).where(Owner.code == "E1")) is None


def test_owner_list_zeigt_mea_warnung(client):
    client.post("/eigentuemer", data={"code": "E1", "mea": "500", "active": "1"})
    r = client.get("/eigentuemer")
    assert "≠ 1000" in r.text


def test_account_crud_und_saldo(client, db_session):
    client.post("/konten", data={"name": "Giro", "type": "giro", "opening_balance": "1.000,00", "active": "1"},
                follow_redirects=True)
    acc = db_session.scalar(select(Account).where(Account.name == "Giro"))
    assert acc is not None and acc.opening_balance == Decimal("1000")
    r = client.get("/konten")
    assert "Giro" in r.text


def test_cost_type_crud_proportional(client, db_session):
    client.post("/kostenarten", data={
        "name": "Heizkosten", "category": "heizen_wasser_betrieb", "kind": "betriebskosten",
        "allocation_strategy": "zaehler", "active": "1",
    }, follow_redirects=True)
    base = db_session.scalar(select(CostType).where(CostType.name == "Heizkosten"))
    assert base is not None

    client.post("/kostenarten", data={
        "name": "Abschlag", "category": "heizen_wasser_betrieb", "kind": "betriebskosten",
        "allocation_strategy": "proportional", "proportional_to_id": str(base.id), "active": "1",
    }, follow_redirects=True)
    ab = db_session.scalar(select(CostType).where(CostType.name == "Abschlag"))
    assert ab.proportional_to_id == base.id

    # Strategiewechsel weg von 'proportional' entfernt die Referenz
    client.post(f"/kostenarten/{ab.id}", data={
        "name": "Abschlag", "category": "heizen_wasser_betrieb", "kind": "betriebskosten",
        "allocation_strategy": "mea", "proportional_to_id": str(base.id), "active": "1",
    }, follow_redirects=True)
    db_session.expire_all()
    assert db_session.get(CostType, ab.id).proportional_to_id is None
