"""CSV-Import von Kontoauszügen: Profil (Spalten-Mapping), Stapel, Zeilen."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ImportBatchStatus


class ImportProfile(Base):
    """Gemerkte CSV-Struktur einer Bank, erkannt an der Spalten-Signatur."""

    __tablename__ = "import_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    # Hash aus normalisierten Spaltenüberschriften + Trennzeichen (eindeutig).
    signature: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    delimiter: Mapped[str] = mapped_column(String(4), default=";")
    encoding: Mapped[str] = mapped_column(String(20), default="utf-8-sig")
    decimal_comma: Mapped[bool] = mapped_column(Boolean, default=True)
    date_format: Mapped[str] = mapped_column(String(20), default="%d.%m.%Y")
    header_row: Mapped[int] = mapped_column(Integer, default=0)
    # 'single' | 'soll_haben' | 'betrag_vorzeichen'
    amount_mode: Mapped[str] = mapped_column(String(20), default="single")
    # Zielfeld -> CSV-Spaltenname, z. B. {"date": "Buchungstag", "amount": "Betrag", ...}
    mapping: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ImportProfile {self.name!r} sig={self.signature[:8]}>"


class ImportBatch(Base):
    """Ein hochgeladener Kontoauszug im Import-Assistenten."""

    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255), default="")
    raw_content: Mapped[bytes] = mapped_column(LargeBinary)  # Original für Re-Parse
    profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("import_profiles.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[ImportBatchStatus] = mapped_column(
        Enum(ImportBatchStatus, native_enum=False, length=12),
        default=ImportBatchStatus.ENTWURF,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    committed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    account: Mapped[Account] = relationship()  # noqa: F821
    profile: Mapped[ImportProfile | None] = relationship()
    rows: Mapped[list[ImportRow]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", order_by="ImportRow.line_no"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ImportBatch {self.filename!r} {self.status.value}>"


class ImportRow(Base):
    """Eine geparste CSV-Zeile mit fachlicher Zuordnung durch den Verwalter."""

    __tablename__ = "import_rows"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("import_batches.id", ondelete="CASCADE"), index=True
    )
    line_no: Mapped[int] = mapped_column(Integer)

    booking_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    payee: Mapped[str] = mapped_column(String(255), default="")
    purpose: Mapped[str] = mapped_column(String(1000), default="")
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)
    parse_error: Mapped[str] = mapped_column(String(500), default="")

    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    include: Mapped[bool] = mapped_column(Boolean, default=True)

    cost_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("cost_types.id", ondelete="SET NULL"), nullable=True
    )
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("owners.id", ondelete="SET NULL"), nullable=True
    )
    suggestion_note: Mapped[str] = mapped_column(String(200), default="")

    batch: Mapped[ImportBatch] = relationship(back_populates="rows")
    cost_type: Mapped[CostType | None] = relationship()  # noqa: F821
    owner: Mapped[Owner | None] = relationship()  # noqa: F821
    # Aus der Buchung erzeugt? (Quelle der Wahrheit: Transaction.import_row_id)
    transaction: Mapped[Transaction | None] = relationship(  # noqa: F821
        primaryjoin="ImportRow.id == foreign(Transaction.import_row_id)",
        viewonly=True,
        uselist=False,
    )

    @property
    def has_error(self) -> bool:
        return bool(self.parse_error)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ImportRow {self.line_no} {self.booking_date} {self.amount}>"
