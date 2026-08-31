"""Bankkonten der WEG (Girokonto, Rücklagenkonto)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, Enum, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import AccountType


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    type: Mapped[AccountType] = mapped_column(
        Enum(AccountType, native_enum=False, length=16), default=AccountType.GIRO
    )
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    opening_balance_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(default=0)

    transactions: Mapped[list[Transaction]] = relationship(  # noqa: F821
        back_populates="account", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Account {self.name} ({self.type.value})>"
