"""Einzelabrechnung: Web-Ansicht + PDF-Route (inkl. Fallback ohne WeasyPrint)."""

from __future__ import annotations

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
    assert "Instandhaltungsrücklage" in r.text


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
