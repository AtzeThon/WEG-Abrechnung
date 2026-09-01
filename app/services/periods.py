"""Perioden-Workflow: Abschließen (Sperre) und Eröffnen (Salden aus Vorperiode)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BillingPeriod, Owner, PeriodOpeningBalance
from app.models.enums import PeriodStatus
from app.services.billing import compute_period


def locked_period_for_date(db: Session, when: date) -> BillingPeriod | None:
    """Finale Periode, in deren Zeitraum ``when`` fällt (Buchungssperre)."""
    return db.scalar(
        select(BillingPeriod)
        .where(
            BillingPeriod.status == PeriodStatus.FINAL,
            BillingPeriod.start_date <= when,
            BillingPeriod.end_date >= when,
        )
        .order_by(BillingPeriod.start_date.desc())
    )


def previous_period(db: Session, period: BillingPeriod) -> BillingPeriod | None:
    """Zeitlich unmittelbar vorangehende Periode (unabhängig vom Status)."""
    return db.scalar(
        select(BillingPeriod)
        .where(BillingPeriod.end_date <= period.start_date, BillingPeriod.id != period.id)
        .order_by(BillingPeriod.end_date.desc())
    )


def carry_forward_balances(db: Session, period: BillingPeriod) -> BillingPeriod | None:
    """Endsalden der Vorperiode als Anfangswerte dieser Periode übernehmen.

    - Rücklagen-Anfangssaldo  = Endsaldo Rücklage (gesamt) der Vorperiode
    - Saldovortrag Hausgeld je Eigentümer = Endsaldo Hausgeld der Vorperiode
    Gibt die Vorperiode zurück oder ``None``, wenn es keine gibt.
    """
    prev = previous_period(db, period)
    if prev is None:
        return None

    result = compute_period(db, prev)
    period.reserve_opening_balance = result.reserve_endsaldo_total

    existing = {
        ob.owner_id: ob
        for ob in db.scalars(
            select(PeriodOpeningBalance).where(PeriodOpeningBalance.period_id == period.id)
        )
    }
    for owner in db.scalars(select(Owner)):
        if owner.code not in result.owners:
            continue
        value = result.owner_result(owner.code).hausgeld_endsaldo
        ob = existing.get(owner.id)
        if ob is None:
            db.add(
                PeriodOpeningBalance(
                    period_id=period.id, owner_id=owner.id, hausgeld_carryover=value
                )
            )
        else:
            ob.hausgeld_carryover = value
    return prev


def set_status(db: Session, period: BillingPeriod, *, final: bool) -> None:
    period.status = PeriodStatus.FINAL if final else PeriodStatus.DRAFT
    period.finalized_at = datetime.now() if final else None
