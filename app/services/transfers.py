"""Umbuchung zwischen Konten (typisch Rücklagen- ↔ Hausgeldkonto).

Erzeugt zwei Buchungen: die auf dem Rücklagenkonto trägt den fachlichen Typ
*Rücklage* (wirkt auf den Endsaldo Rücklage und gegengleich auf den Endsaldo
Hausgeld), die Gegenbuchung auf dem anderen Konto den Typ *Umbuchung (neutral)*
(nur für den Kontoauszug, ohne Wirkung auf die Abrechnung).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, CostType, Transaction
from app.models.enums import AccountType, AllocationStrategy, CostCategory, CostKind

RUECKLAGE_CT_NAME = "Rücklage – Zuführung / Entnahme"
NEUTRAL_CT_NAME = "Umbuchung (neutral)"


def _get_or_create_ct(db: Session, name: str, kind: CostKind) -> CostType:
    ct = db.scalar(select(CostType).where(CostType.name == name))
    if ct is None:
        ct = CostType(
            name=name,
            kind=kind,
            category=CostCategory.SONSTIGES,
            allocation_strategy=AllocationStrategy.MEA,
        )
        db.add(ct)
        db.flush()
    return ct


def record_transfer(
    db: Session,
    *,
    from_account_id: int,
    to_account_id: int,
    amount: Decimal,
    booking_date: date,
    owner_id: int | None,
    note: str,
) -> tuple[Transaction, Transaction]:
    if amount is None or amount <= 0:
        raise ValueError("Der Betrag muss größer als 0 sein.")
    if from_account_id == to_account_id:
        raise ValueError("Quell- und Zielkonto müssen verschieden sein.")

    src = db.get(Account, from_account_id)
    dst = db.get(Account, to_account_id)
    if src is None or dst is None:
        raise ValueError("Konto nicht gefunden.")

    ruecklage_ct = _get_or_create_ct(db, RUECKLAGE_CT_NAME, CostKind.RUECKLAGE)
    neutral_ct = _get_or_create_ct(db, NEUTRAL_CT_NAME, CostKind.UMBUCHUNG)

    def ct_for(account: Account) -> CostType:
        return ruecklage_ct if account.type == AccountType.RUECKLAGE else neutral_ct

    note = (note or "").strip() or "Umbuchung"
    src_txn = Transaction(
        account_id=src.id, booking_date=booking_date, payee="Umbuchung",
        cost_type_id=ct_for(src).id, owner_id=owner_id, amount=-amount, note=note,
    )
    dst_txn = Transaction(
        account_id=dst.id, booking_date=booking_date, payee="Umbuchung",
        cost_type_id=ct_for(dst).id, owner_id=owner_id, amount=amount, note=note,
    )
    db.add_all([src_txn, dst_txn])
    return src_txn, dst_txn
