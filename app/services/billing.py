"""Adapter: ORM-Objekte einer Abrechnungsperiode -> reine Engine-Eingaben -> Ergebnis."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.allocation import (
    BillingResult,
    CostTypeInput,
    OverrideInput,
    OwnerInput,
    PeriodInput,
    TxnInput,
    compute_billing,
)
from app.models import (
    AllocationOverride,
    BillingPeriod,
    CostType,
    Owner,
    PeriodOpeningBalance,
    Transaction,
)


def build_period_input(db: Session, period: BillingPeriod) -> PeriodInput:
    carryover = {
        ob.owner.code: ob.hausgeld_carryover
        for ob in db.scalars(
            select(PeriodOpeningBalance)
            .options(selectinload(PeriodOpeningBalance.owner))
            .where(PeriodOpeningBalance.period_id == period.id)
        )
    }
    return PeriodInput(
        start_date=period.start_date,
        end_date=period.end_date,
        reserve_opening_balance=period.reserve_opening_balance,
        hausgeld_carryover=carryover,
    )


def _owner_inputs(db: Session) -> list[OwnerInput]:
    owners = db.scalars(
        select(Owner).where(Owner.active).order_by(Owner.sort_order, Owner.code)
    )
    return [OwnerInput(code=o.code, mea=o.mea, name=o.name, email=o.email) for o in owners]


def _cost_type_inputs(db: Session) -> list[CostTypeInput]:
    out = []
    for ct in db.scalars(select(CostType).options(selectinload(CostType.proportional_to))):
        out.append(
            CostTypeInput(
                name=ct.name,
                kind=ct.kind.value,
                strategy=ct.allocation_strategy.value,
                category=ct.category.value,
                supplier=ct.default_supplier,
                proportional_to=ct.proportional_to.name if ct.proportional_to else None,
            )
        )
    return out


def _txn_inputs(db: Session, period: BillingPeriod) -> list[TxnInput]:
    rows = db.scalars(
        select(Transaction)
        .options(selectinload(Transaction.cost_type), selectinload(Transaction.owner))
        .where(
            Transaction.booking_date >= period.start_date,
            Transaction.booking_date <= period.end_date,
        )
    )
    return [
        TxnInput(
            booking_date=t.booking_date,
            cost_type=t.cost_type.name,
            amount=t.amount,
            owner=t.owner.code if t.owner else None,
            payee=t.payee,
        )
        for t in rows
    ]


def _override_inputs(db: Session, period: BillingPeriod) -> list[OverrideInput]:
    rows = db.scalars(
        select(AllocationOverride)
        .options(selectinload(AllocationOverride.cost_type), selectinload(AllocationOverride.owner))
        .where(AllocationOverride.period_id == period.id)
    )
    return [OverrideInput(cost_type=o.cost_type.name, owner=o.owner.code, amount=o.amount) for o in rows]


def compute_period(db: Session, period: BillingPeriod) -> BillingResult:
    """Vollständige Abrechnung einer Periode berechnen."""
    return compute_billing(
        period=build_period_input(db, period),
        owners=_owner_inputs(db),
        cost_types=_cost_type_inputs(db),
        transactions=_txn_inputs(db, period),
        overrides=_override_inputs(db, period),
    )
