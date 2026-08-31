"""Kostenart (Bezeichnung einer Buchung) inkl. fachlichem Typ und Umlageschlüssel."""

from __future__ import annotations

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import AllocationStrategy, CostCategory, CostKind


class CostType(Base):
    __tablename__ = "cost_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    category: Mapped[CostCategory] = mapped_column(
        Enum(CostCategory, native_enum=False, length=32),
        default=CostCategory.SONSTIGES,
    )
    default_supplier: Mapped[str] = mapped_column(String(120), default="")
    kind: Mapped[CostKind] = mapped_column(
        Enum(CostKind, native_enum=False, length=20),
        default=CostKind.BETRIEBSKOSTEN,
    )
    allocation_strategy: Mapped[AllocationStrategy] = mapped_column(
        Enum(AllocationStrategy, native_enum=False, length=20),
        default=AllocationStrategy.MEA,
    )
    # Nur für allocation_strategy == PROPORTIONAL relevant (spätere Erweiterung):
    # Kostenart, in deren Verhältnis verteilt wird.
    proportional_to_id: Mapped[int | None] = mapped_column(
        ForeignKey("cost_types.id", ondelete="SET NULL"), nullable=True
    )
    proportional_to: Mapped[CostType | None] = relationship(
        remote_side="CostType.id", foreign_keys=[proportional_to_id]
    )

    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(default=0)

    transactions: Mapped[list[Transaction]] = relationship(  # noqa: F821
        back_populates="cost_type"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CostType {self.name} kind={self.kind.value} strat={self.allocation_strategy.value}>"
