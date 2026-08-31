"""End-to-end: DB (Seed) -> services.billing.compute_period -> Excel-Sollwerte."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

import pytest
from sqlalchemy import select

from app.models import BillingPeriod
from app.services.billing import compute_period
from scripts.seed_2026 import seed


def cent(v) -> Decimal:
    return Decimal(v).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@pytest.fixture
def seeded(db_session):
    seed(db_session, force=True)
    period = db_session.scalar(select(BillingPeriod))
    return db_session, period


def test_compute_period_reproduziert_fixture(seeded):
    db, period = seeded
    result = compute_period(db, period)

    assert cent(result.cost_share_total) == Decimal("12486.58")
    assert cent(result.owner_result("E1").cost_share_total) == Decimal("2671.45")
    assert cent(result.owner_result("E2").cost_share_total) == Decimal("6040.75")
    assert cent(result.owner_result("E1").hausgeld_paid) == Decimal("2820.00")
    assert cent(result.owner_result("E2").guthaben) == Decimal("-1720.75")
    assert cent(result.owner_result("E1").reserve_opening) == Decimal("930.96")
    assert cent(result.investition_total) == Decimal("15836.58")
    assert cent(result.cost_types["Heizkosten/Wasser/Betriebskosten"].weg_total) == Decimal("6517.78")


def test_period_overview_seite(client, db_session):
    seed(db_session, force=True)
    period = db_session.scalar(select(BillingPeriod))
    r = client.get(f"/abrechnungen/{period.id}")
    assert r.status_code == 200
    assert "12.486,58" in r.text          # Gesamtkostenanteil
    assert "Hausgeldübersicht" in r.text
