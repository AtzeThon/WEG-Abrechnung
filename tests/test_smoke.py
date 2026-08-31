"""Grundlegende Smoke-Tests der Weboberfläche."""

from __future__ import annotations


def test_health(client):
    assert client.get("/gesundheit").json() == {"status": "ok"}


def test_dashboard_erreichbar_nach_login(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Kostenarten" in r.text  # Dashboard-Kachel, ohne Umlaut


def test_geschuetzt_ohne_login_leitet_um():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        r = c.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert "/login" in r.headers["location"]
