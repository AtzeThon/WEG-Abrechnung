"""Kontobewegung (Buchung)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    booking_date: Mapped[date] = mapped_column(Date, index=True)
    payee: Mapped[str] = mapped_column(String(200), default="")  # Zahlungspartner / Lieferant
    cost_type_id: Mapped[int] = mapped_column(
        ForeignKey("cost_types.id", ondelete="RESTRICT"), index=True
    )
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("owners.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    # Betrag: positiv = Einzahlung, negativ = Ausgabe.
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    note: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    account: Mapped[Account] = relationship(back_populates="transactions")  # noqa: F821
    cost_type: Mapped[CostType] = relationship(back_populates="transactions")  # noqa: F821
    owner: Mapped[Owner | None] = relationship(back_populates="transactions")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Transaction {self.booking_date} {self.amount} {self.payee!r}>"
