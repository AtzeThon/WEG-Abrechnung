"""End-to-end: CSV hochladen -> Mapping -> Prüfen -> Buchen; Duplikate; Vorschläge."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import Account, CostType, ImportBatch, Owner, Transaction
from app.models.enums import AccountType, CostKind, TransactionSource

FIXTURES = Path(__file__).parent / "fixtures" / "bank_csv"


@pytest.fixture
def base(db_session):
    giro = Account(name="Giro", type=AccountType.GIRO, opening_balance=Decimal("0"))
    ct_abschlag = CostType(name="Abschlag - Gas, Strom, Wasser", kind=CostKind.BETRIEBSKOSTEN)
    ct_hausgeld = CostType(name="Hausgeld", kind=CostKind.HAUSGELD)
    ct_wartung = CostType(name="Wartung", kind=CostKind.BETRIEBSKOSTEN)
    e1 = Owner(code="E1", mea=Decimal("500"))
    db_session.add_all([giro, ct_abschlag, ct_hausgeld, ct_wartung, e1])
    db_session.commit()
    return dict(giro=giro, abschlag=ct_abschlag, hausgeld=ct_hausgeld, wartung=ct_wartung, e1=e1)


def _upload(client, account_id, name):
    raw = (FIXTURES / name).read_bytes()
    return client.post(
        "/import",
        data={"account_id": str(account_id)},
        files={"file": (name, raw, "text/csv")},
        follow_redirects=False,
    )


def test_voller_ablauf_upload_mapping_buchen(client, db_session, base):
    r = _upload(client, base["giro"].id, "generic_semikolon_utf8.csv")
    assert r.status_code == 303 and "/mapping" in r.headers["location"]
    batch = db_session.scalar(select(ImportBatch))

    # Mapping bestätigen
    r = client.post(f"/import/{batch.id}/mapping", data={
        "amount_mode": "single",
        "map_date": "Buchungstag",
        "map_payee": "Beguenstigter/Zahlungspflichtiger",
        "map_purpose": "Verwendungszweck",
        "map_amount": "Betrag",
        "header_row": "1",
        "profile_name": "Testbank",
    }, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].endswith(f"/import/{batch.id}")

    db_session.expire_all()
    batch = db_session.scalar(select(ImportBatch))
    assert len(batch.rows) == 3

    review = client.get(f"/import/{batch.id}")
    assert "0 Buchung(en) importieren" not in review.text  # Text vorhanden, aber disabled
    assert "disabled" in review.text  # Commit gesperrt (noch keine Kostenart)

    # Jede Zeile zuordnen
    kinds = {"Stadtwerke": base["abschlag"].id, "Eigentuemergemeinschaft": base["hausgeld"].id,
             "Messdienstleister GmbH": base["wartung"].id}
    for row in batch.rows:
        data = {"include": "1", "cost_type_id": str(kinds[row.payee])}
        if kinds[row.payee] == base["hausgeld"].id:
            data["owner_id"] = str(base["e1"].id)
        rr = client.post(f"/import/{batch.id}/zeile/{row.id}", data=data,
                         headers={"HX-Request": "true"})
        assert rr.status_code == 200

    # Buchen
    r = client.post(f"/import/{batch.id}/buchen", follow_redirects=False)
    assert r.status_code == 303 and "/buchungen" in r.headers["location"]

    txns = db_session.scalars(select(Transaction)).all()
    assert len(txns) == 3
    assert all(t.source == TransactionSource.CSV_IMPORT for t in txns)
    assert all(t.import_row_id is not None for t in txns)
    hausgeld_txn = next(t for t in txns if t.cost_type_id == base["hausgeld"].id)
    assert hausgeld_txn.owner_id == base["e1"].id


def test_zweiter_import_erkennt_alle_als_duplikat(client, db_session, base):
    # erster Durchlauf: alles buchen
    _upload(client, base["giro"].id, "generic_semikolon_utf8.csv")
    batch = db_session.scalar(select(ImportBatch))
    client.post(f"/import/{batch.id}/mapping", data={
        "amount_mode": "single", "map_date": "Buchungstag", "map_amount": "Betrag",
        "map_payee": "Beguenstigter/Zahlungspflichtiger", "map_purpose": "Verwendungszweck",
        "header_row": "1", "profile_name": "Testbank",
    })
    db_session.expire_all()
    batch = db_session.scalar(select(ImportBatch))
    for row in batch.rows:
        client.post(f"/import/{batch.id}/zeile/{row.id}",
                    data={"include": "1", "cost_type_id": str(base["wartung"].id)},
                    headers={"HX-Request": "true"})
    client.post(f"/import/{batch.id}/buchen")

    # zweiter Upload derselben Datei -> Profil greift -> alle Zeilen Duplikat
    r = _upload(client, base["giro"].id, "generic_semikolon_utf8.csv")
    assert "/import/" in r.headers["location"] and "/mapping" not in r.headers["location"]
    db_session.expire_all()
    batch2 = db_session.scalars(select(ImportBatch).order_by(ImportBatch.id.desc())).first()
    assert all(row.is_duplicate and not row.include for row in batch2.rows)

    review = client.get(f"/import/{batch2.id}")
    assert "3 Duplikat" in review.text
    assert "disabled" in review.text  # 0 einbezogen -> Commit gesperrt


def test_kategorie_und_eigentuemer_spalte_werden_vorbelegt(client, db_session, base):
    _upload(client, base["giro"].id, "finanztool_kategorie_cp1252.csv")
    batch = db_session.scalar(select(ImportBatch))
    client.post(f"/import/{batch.id}/mapping", data={
        "amount_mode": "single",
        "map_date": "Wertstellung", "map_payee": "Empfänger/Auftraggeber",
        "map_purpose": "Verwendungszweck", "map_amount": "Betrag",
        "map_category": "Kategorie", "map_owner": "Frei 3",
        "header_row": "1", "profile_name": "Finanztool",
    })
    db_session.expire_all()
    batch = db_session.scalar(select(ImportBatch))

    by_purpose = {r.line_no: r for r in batch.rows}
    hausgeld_rows = [r for r in batch.rows if r.raw.get("Kategorie") == "Hausgeld"]
    assert hausgeld_rows and all(r.cost_type_id == base["hausgeld"].id for r in hausgeld_rows)
    assert all(r.owner_id == base["e1"].id for r in hausgeld_rows if r.raw.get("Frei 3") == "E1")

    bank_row = next(r for r in batch.rows if r.raw.get("Kategorie") == "Bankgebühren")
    assert bank_row.cost_type_id is None  # keine passende Kostenart -> kein Vorschlag
    assert "Spalte" in hausgeld_rows[0].suggestion_note
    assert by_purpose  # sanity


def test_historien_vorschlag(client, db_session, base):
    db_session.add(Transaction(
        account_id=base["giro"].id, booking_date=__import__("datetime").date(2025, 1, 1),
        payee="Stadtwerke", cost_type_id=base["abschlag"].id, amount=Decimal("-100"),
    ))
    db_session.commit()

    _upload(client, base["giro"].id, "generic_semikolon_utf8.csv")
    batch = db_session.scalar(select(ImportBatch))
    client.post(f"/import/{batch.id}/mapping", data={
        "amount_mode": "single", "map_date": "Buchungstag", "map_amount": "Betrag",
        "map_payee": "Beguenstigter/Zahlungspflichtiger", "map_purpose": "Verwendungszweck",
        "header_row": "1", "profile_name": "Testbank",
    })
    db_session.expire_all()
    batch = db_session.scalar(select(ImportBatch))
    stadtwerke_row = next(r for r in batch.rows if r.payee == "Stadtwerke")
    assert stadtwerke_row.cost_type_id == base["abschlag"].id
    assert "Historie" in stadtwerke_row.suggestion_note
