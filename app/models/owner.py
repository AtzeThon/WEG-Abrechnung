"""Eigentümer (Wohnungseigentümer der WEG)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Owner(Base):
    __tablename__ = "owners"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)  # z. B. "E1"
    name: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(200), default="")
    # Miteigentumsanteil in Anteilspunkten (Summe aller Eigentümer typischerweise 1000).
    mea: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(default=0)

    transactions: Mapped[list[Transaction]] = relationship(  # noqa: F821
        back_populates="owner"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Owner {self.code} mea={self.mea}>"
