"""Adapter: ORM-Objekte einer Abrechnungsperiode -> reine Engine-Eingaben -> Ergebnis."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
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
    Account,
    AllocationOverride,
    BillingPeriod,
    CostType,
    Owner,
    PeriodOpeningBalance,
    Transaction,
)
from app.models.enums import AccountType


def reserve_account(db: Session) -> Account | None:
    return db.scalar(
        select(Account)
        .where(Account.type == AccountType.RUECKLAGE)
        .order_by(Account.sort_order, Account.id)
    )


def account_balance_before(db: Session, account: Account, before) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.account_id == account.id, Transaction.booking_date < before
        )
    )
    return account.opening_balance + Decimal(total or 0)


def effective_reserve_opening(db: Session, period: BillingPeriod) -> tuple[Decimal, str]:
    """Rücklagen-Anfangssaldo der Periode + Herkunft.

    Vorrang hat der manuell erfasste Wert der Periode. Ist er 0, wird der Stand
    des Rücklagenkontos zu Periodenbeginn (Anfangssaldo + Buchungen davor)
    verwendet.
    """
    if period.reserve_opening_balance and period.reserve_opening_balance != 0:
        return period.reserve_opening_balance, "manuell erfasst"
    acc = reserve_account(db)
    if acc is None:
        return Decimal("0"), "kein Rücklagenkonto"
    return account_balance_before(db, acc, period.start_date), f"Rücklagenkonto „{acc.name}“"


def build_period_input(db: Session, period: BillingPeriod) -> PeriodInput:
    carryover = {
        ob.owner.code: ob.hausgeld_carryover
        for ob in db.scalars(
            select(PeriodOpeningBalance)
            .options(selectinload(PeriodOpeningBalance.owner))
            .where(PeriodOpeningBalance.period_id == period.id)
        )
    }
    reserve_opening, _ = effective_reserve_opening(db, period)
    return PeriodInput(
        start_date=period.start_date,
        end_date=period.end_date,
        reserve_opening_balance=reserve_opening,
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
