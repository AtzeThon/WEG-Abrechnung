"""Abrechnungsperiode (Wirtschaftsjahr) inkl. manuell erfasster Anfangswerte."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import PeriodStatus


class BillingPeriod(Base):
    __tablename__ = "billing_periods"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(80))  # z. B. "Abrechnung 2026"
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[PeriodStatus] = mapped_column(
        Enum(PeriodStatus, native_enum=False, length=10), default=PeriodStatus.DRAFT
    )
    # Rücklagen-Anfangssaldo der Periode als EIN Gesamtbetrag (Gemeinschaftskonto).
    # Die Engine verteilt ihn anteilig nach MEA.
    reserve_opening_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))

    # Flag: in der Einzelabrechnung den künftigen monatlichen Abschlag ausweisen.
    compute_next_advance: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0"
    )
    # Inflationsaufschlag in Prozent auf den berechneten neuen Abschlag (0 = keiner).
    inflation_rate: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), default=Decimal("0"), server_default="0"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    opening_balances: Mapped[list[PeriodOpeningBalance]] = relationship(
        back_populates="period", cascade="all, delete-orphan"
    )
    allocation_overrides: Mapped[list[AllocationOverride]] = relationship(
        back_populates="period", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<BillingPeriod {self.label} {self.start_date}..{self.end_date}>"


class PeriodOpeningBalance(Base):
    """Saldovortrag Hausgeld je Eigentümer (manuell erfasst)."""

    __tablename__ = "period_opening_balances"
    __table_args__ = (UniqueConstraint("period_id", "owner_id", name="uq_opening_period_owner"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    period_id: Mapped[int] = mapped_column(
        ForeignKey("billing_periods.id", ondelete="CASCADE"), index=True
    )
    owner_id: Mapped[int] = mapped_column(ForeignKey("owners.id", ondelete="CASCADE"), index=True)
    hausgeld_carryover: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))

    period: Mapped[BillingPeriod] = relationship(back_populates="opening_balances")
    owner: Mapped[Owner] = relationship()  # noqa: F821


class AllocationOverride(Base):
    """Direkt erfasster Betrag je Eigentümer für eine Kostenart mit Schlüssel 'Zähler'."""

    __tablename__ = "allocation_overrides"
    __table_args__ = (
        UniqueConstraint(
            "period_id", "cost_type_id", "owner_id", name="uq_override_period_ct_owner"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    period_id: Mapped[int] = mapped_column(
        ForeignKey("billing_periods.id", ondelete="CASCADE"), index=True
    )
    cost_type_id: Mapped[int] = mapped_column(
        ForeignKey("cost_types.id", ondelete="CASCADE"), index=True
    )
    owner_id: Mapped[int] = mapped_column(ForeignKey("owners.id", ondelete="CASCADE"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))

    period: Mapped[BillingPeriod] = relationship(back_populates="allocation_overrides")
    cost_type: Mapped[CostType] = relationship()  # noqa: F821
    owner: Mapped[Owner] = relationship()  # noqa: F821
