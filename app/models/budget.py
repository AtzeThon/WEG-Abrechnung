"""Wirtschaftsplan / Prognoserechnung – gespeicherte Nutzer-Overrides je Zelle.

Eine Zelle des Wirtschaftsplans (Monat × Kostenart) zeigt normalerweise den
Ist-Wert (falls schon gebucht) oder den Vorschlag aus der Vorperiode. Trägt der
Verwalter einen abweichenden Wert ein, wird dieser hier als ``BudgetEntry``
festgehalten; unbearbeitete Zellen werden **nicht** gespeichert.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BudgetEntry(Base):
    __tablename__ = "budget_entries"
    __table_args__ = (
        UniqueConstraint("period_id", "month_index", "cost_type_id", name="uq_budget_cell"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    period_id: Mapped[int] = mapped_column(
        ForeignKey("billing_periods.id", ondelete="CASCADE"), index=True
    )
    month_index: Mapped[int] = mapped_column(Integer)  # 0 = erster Kalendermonat der Periode
    cost_type_id: Mapped[int] = mapped_column(
        ForeignKey("cost_types.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    period: Mapped[BillingPeriod] = relationship()  # noqa: F821
    cost_type: Mapped[CostType] = relationship()  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<BudgetEntry p={self.period_id} m={self.month_index} ct={self.cost_type_id} {self.amount}>"
