"""Demo-Datensatz laden: anonymisierte Beispiel-Abrechnung 2026.

    python -m scripts.seed_2026 [--force]

Legt Konten, Eigentümer, Kostenarten, ~95 Buchungen, die Abrechnungsperiode
2025/26 samt Saldovortrag und Zähler-Direkteingaben an. Dient dem visuellen
Abgleich der Web-/PDF-Ansicht mit der ursprünglichen Excel.
"""

from __future__ import annotations

import sys
from datetime import date

from sqlalchemy import select

from app.database import SessionLocal
from app.models import (
    Account,
    AllocationOverride,
    BillingPeriod,
    CostType,
    Owner,
    PeriodOpeningBalance,
    Transaction,
)
from app.models.enums import (
    AccountType,
    AllocationStrategy,
    CostCategory,
    CostKind,
    PeriodStatus,
)
from tests.fixtures import abrechnung_2026 as fx

_CATEGORY = {c.value: c for c in CostCategory}
_KIND = {k.value: k for k in CostKind}
_STRATEGY = {s.value: s for s in AllocationStrategy}


def run(force: bool = False) -> None:
    with SessionLocal() as db:
        if db.scalar(select(Owner).limit(1)) is not None and not force:
            sys.exit("Es sind bereits Daten vorhanden. Mit --force überschreiben.")

        if force:
            for model in (Transaction, AllocationOverride, PeriodOpeningBalance,
                          BillingPeriod, CostType, Owner, Account):
                db.query(model).delete()
            db.flush()

        giro = Account(
            name="Girokonto", type=AccountType.GIRO,
            opening_balance=fx.GIRO_OPENING, opening_balance_date=date(2025, 8, 1), sort_order=0,
        )
        ruecklage = Account(
            name="Rücklagenkonto", type=AccountType.RUECKLAGE,
            opening_balance=fx.RESERVE_OPENING_TOTAL, opening_balance_date=date(2025, 8, 1), sort_order=1,
        )
        db.add_all([giro, ruecklage])

        owners: dict[str, Owner] = {}
        for i, o in enumerate(fx.OWNERS):
            owner = Owner(code=o.code, name=o.name, email="", mea=o.mea, sort_order=i)
            owners[o.code] = owner
            db.add(owner)

        cost_types: dict[str, CostType] = {}
        for i, ct in enumerate(fx.COST_TYPES):
            row = CostType(
                name=ct.name,
                category=_CATEGORY[ct.category],
                default_supplier=ct.supplier,
                kind=_KIND[ct.kind],
                allocation_strategy=_STRATEGY[ct.strategy],
                sort_order=i,
            )
            cost_types[ct.name] = row
            db.add(row)
        db.flush()

        for t in fx.TRANSACTIONS:
            db.add(
                Transaction(
                    account_id=giro.id,
                    booking_date=t.booking_date,
                    payee=t.payee,
                    cost_type_id=cost_types[t.cost_type].id,
                    owner_id=owners[t.owner].id if t.owner else None,
                    amount=t.amount,
                    note="",
                )
            )

        period = BillingPeriod(
            label="Abrechnung 2026",
            start_date=fx.PERIOD_START,
            end_date=fx.PERIOD_END,
            status=PeriodStatus.DRAFT,
            reserve_opening_balance=fx.RESERVE_OPENING_TOTAL,
        )
        db.add(period)
        db.flush()

        for code, amount in fx.hausgeld_carryover().items():
            db.add(
                PeriodOpeningBalance(
                    period_id=period.id, owner_id=owners[code].id, hausgeld_carryover=amount
                )
            )
        for ov in fx.OVERRIDES:
            db.add(
                AllocationOverride(
                    period_id=period.id,
                    cost_type_id=cost_types[ov.cost_type].id,
                    owner_id=owners[ov.owner].id,
                    amount=ov.amount,
                )
            )

        db.commit()
        print(
            f"Seed OK: {len(fx.OWNERS)} Eigentümer, {len(fx.COST_TYPES)} Kostenarten, "
            f"{len(fx.TRANSACTIONS)} Buchungen, Periode „{period.label}“."
        )


if __name__ == "__main__":
    run(force="--force" in sys.argv)
