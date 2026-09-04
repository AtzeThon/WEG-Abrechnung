"""Künftiger monatlicher Abschlag – reine Rechnung (app/allocation/advance.py)."""

from __future__ import annotations

from decimal import Decimal

from app.allocation import compute_next_advance


def test_beispiel_aus_anforderung_ohne_inflation():
    # geleistete Hausgeldzahlungen 4.320, Nachzahlung 1.720,75 -> Grundlage 6.040,75
    na = compute_next_advance(Decimal("4320.00"), Decimal("-1720.75"))
    assert na.settlement == Decimal("1720.75")
    assert na.base == Decimal("6040.75")
    assert na.monthly == Decimal("503.40")  # 6040,75 / 12
    assert na.amount == Decimal("503")       # kaufmännisch auf volle Euro


def test_beispiel_mit_inflation():
    na = compute_next_advance(Decimal("4320.00"), Decimal("-1720.75"), Decimal("3.00"))
    assert na.monthly == Decimal("503.40")
    assert na.monthly_inflated == Decimal("518.50")  # 503,3958 * 1,03
    assert na.amount == Decimal("518")


def test_guthaben_senkt_den_abschlag():
    # Eigentümer hatte 600 Guthaben -> Grundlage 4320 - 600 = 3720
    na = compute_next_advance(Decimal("4320.00"), Decimal("600.00"))
    assert na.settlement == Decimal("-600.00")
    assert na.base == Decimal("3720.00")
    assert na.amount == Decimal("310")


def test_kaufmaennische_rundung_auf_euro():
    # base 6006 -> 500,50 /Monat -> rundet auf 501
    assert compute_next_advance(Decimal("6006.00"), Decimal("0")).amount == Decimal("501")
    # base 5994 -> 499,50 -> rundet auf 500
    assert compute_next_advance(Decimal("5994.00"), Decimal("0")).amount == Decimal("500")
    # base 5993 -> 499,41666 -> 499
    assert compute_next_advance(Decimal("5993.00"), Decimal("0")).amount == Decimal("499")
