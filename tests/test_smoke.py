"""Grundlegende Smoke-Tests der Weboberfläche."""

from __future__ import annotations


def test_health(client):
    assert client.get("/gesundheit").json() == {"status": "ok"}


def test_dashboard_offen_erreichbar(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Kostenarten" in r.text  # Dashboard-Kachel, ohne Umlaut


def test_kein_login_ohne_flag(client):
    # /login leitet auf die Startseite um, solange WEG_REQUIRE_LOGIN nicht gesetzt ist
    r = client.get("/login", follow_redirects=False)
    assert r.status_code == 303


def test_login_erzwungen_wenn_aktiviert(client, login_required):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert "/login" in r.headers["location"]


def test_login_flow_mit_aktiviertem_login(client, db_session, login_required):
    from app.models import User

    user = User(username="admin")
    user.set_password("test1234")
    db_session.add(user)
    db_session.commit()

    assert client.post("/login", data={"username": "admin", "password": "falsch"}).status_code == 401
    r = client.post(
        "/login", data={"username": "admin", "password": "test1234"}, follow_redirects=False
    )
    assert r.status_code == 303
    assert client.get("/").status_code == 200
