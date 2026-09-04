"""Einzelabrechnung: Web-Ansicht + PDF-Route (inkl. Fallback ohne WeasyPrint)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from app.models import BillingPeriod
from scripts.seed_2026 import seed


def _period(db):
    seed(db, force=True)
    return db.scalar(select(BillingPeriod))


def test_statement_web_zeigt_kernwerte(client, db_session):
    period = _period(db_session)
    r = client.get(f"/abrechnungen/{period.id}/eigentuemer/E1")
    assert r.status_code == 200
    assert "Summe Kosten" in r.text
    assert "2.671,45" in r.text          # Kostenanteil E1
    assert "2.820,00" in r.text          # geleistetes Hausgeld
    assert "148,55" in r.text            # Guthaben
    assert "Hausgeldkonto" in r.text and "Rücklage" in r.text


def test_kuenftiger_abschlag_nur_bei_gesetztem_flag(client, db_session):
    period = _period(db_session)

    # Flag aus (Default) -> kein Abschnitt
    r = client.get(f"/abrechnungen/{period.id}/eigentuemer/E1")
    assert "Künftiger monatlicher Abschlag" not in r.text

    # Flag an, 3 % Inflation
    period.compute_next_advance = True
    period.inflation_rate = Decimal("3.00")
    db_session.commit()

    r = client.get(f"/abrechnungen/{period.id}/eigentuemer/E1")
    assert r.status_code == 200
    assert "Künftiger monatlicher Abschlag" in r.text
    assert "3 % Inflationsanpassung" in r.text
    # E1: Hausgeld 2.820, Guthaben +148,55 -> Grundlage 2.671,45 -> /12 = 222,62
    # -> * 1,03 = 229,30 -> gerundet 229
    assert "Neuer monatlicher Abschlag" in r.text
    assert "229,00" in r.text


def test_statement_unbekannter_eigentuemer_leitet_um(client, db_session):
    period = _period(db_session)
    r = client.get(f"/abrechnungen/{period.id}/eigentuemer/E9", follow_redirects=False)
    assert r.status_code == 303


def test_statement_pdf_route(client, db_session):
    period = _period(db_session)
    r = client.get(f"/abrechnungen/{period.id}/eigentuemer/E1/pdf", follow_redirects=False)
    if r.status_code == 200:
        assert r.headers["content-type"] == "application/pdf"
        assert r.content[:4] == b"%PDF"
        assert "Abrechnung_2026_E1.pdf" in r.headers["content-disposition"]
    else:
        # WeasyPrint/GTK nicht installiert -> saubere Weiterleitung mit Hinweis
        assert r.status_code == 303
        assert "/eigentuemer/E1" in r.headers["location"]


def test_alle_einzelabrechnungen_pdf(client, db_session):
    period = _period(db_session)
    r = client.get(f"/abrechnungen/{period.id}/einzelabrechnungen.pdf", follow_redirects=False)
    if r.status_code == 200:
        assert r.headers["content-type"] == "application/pdf"
        assert "Einzelabrechnungen_2026.pdf" in r.headers["content-disposition"]
    else:
        assert r.status_code == 303


def test_uebersicht_verlinkt_alle_als_pdf(client, db_session):
    period = _period(db_session)
    r = client.get(f"/abrechnungen/{period.id}")
    assert "Alle als PDF" in r.text
    assert f"/abrechnungen/{period.id}/einzelabrechnungen.pdf" in r.text
