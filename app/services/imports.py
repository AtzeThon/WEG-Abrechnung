"""CSV-Import: Bindeglied zwischen reinem Parser (`app/imports/`) und ORM.

- Batch aus hochgeladener Datei / gespeichertem Profil parsen
- Duplikate gegen vorhandene Buchungen markieren
- Kostenart-/Eigentümer-Vorschlag aus der Buchungshistorie
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.imports import (
    ColumnMapping,
    CsvDialect,
    guess_amount_mode,
    header_signature,
    normalize,
    parse,
    sniff,
)
from app.models import (
    OWNER_REQUIRED_KINDS,
    CostType,
    ImportBatch,
    ImportProfile,
    ImportRow,
    Owner,
    Transaction,
    TransactionSource,
)

_WS = re.compile(r"\s+")


def _norm(text: str | None) -> str:
    return _WS.sub(" ", (text or "").strip()).lower()


# --------------------------------------------------------------------------- #
# Parsen / Zeilen erzeugen
# --------------------------------------------------------------------------- #
def dialect_from_profile(profile: ImportProfile) -> CsvDialect:
    return CsvDialect(
        delimiter=profile.delimiter,
        encoding=profile.encoding,
        header_row=profile.header_row,
        decimal_comma=profile.decimal_comma,
        date_format=profile.date_format or None,
        amount_mode=profile.amount_mode,
    )


def parse_batch(db: Session, batch: ImportBatch, profile: ImportProfile | None) -> None:
    """Rohdaten des Batches parsen und `batch.rows` (neu) befüllen.

    Enthält die CSV eine Kategorie-/Eigentümer-Spalte (Mapping ``category`` /
    ``owner``), wird daraus direkt ein Kostenart-/Eigentümer-Vorschlag abgeleitet.
    """
    raw = bytes(batch.raw_content)
    if profile is not None:
        result = parse(
            raw,
            dialect=dialect_from_profile(profile),
            mapping=ColumnMapping(**profile.mapping),
            amount_mode=profile.amount_mode,
        )
    else:
        result = parse(raw)

    cost_types = {
        normalize(c.name): c for c in db.scalars(select(CostType).where(CostType.active))
    }
    owners_by_code = {o.code.strip().upper(): o.id for o in db.scalars(select(Owner))}
    cat_column = (profile.mapping.get("category") if profile else result.mapping.category) or ""

    batch.rows.clear()
    for pr in result.rows:
        row = ImportRow(
            line_no=pr.line_no,
            booking_date=pr.booking_date,
            payee=pr.payee[:255],
            purpose=pr.purpose[:1000],
            amount=pr.amount,
            raw={k: str(v) for k, v in pr.raw.items()},
            parse_error="; ".join(pr.errors)[:500],
            is_duplicate=False,
            include=not pr.errors,
        )
        if pr.category:
            match = cost_types.get(normalize(pr.category))
            if match is not None:
                row.cost_type_id = match.id
                row.suggestion_note = f"aus Spalte „{cat_column or 'Kategorie'}“"[:200]
                if match.kind in OWNER_REQUIRED_KINDS and pr.owner_hint:
                    row.owner_id = owners_by_code.get(pr.owner_hint.strip().upper())
        batch.rows.append(row)


def sniff_batch(batch: ImportBatch) -> tuple[list[str], CsvDialect, ColumnMapping, list[dict]]:
    """Für den Mapping-Assistenten: Kopfzeilen, Dialekt, Auto-Mapping, Beispielzeilen."""
    result = parse(bytes(batch.raw_content))
    sample = [
        {"line_no": r.line_no, **r.raw}
        for r in result.rows[:6]
    ]
    return result.headers, result.dialect, result.mapping, sample


def signature_for(batch: ImportBatch) -> str:
    _, dialect = sniff(bytes(batch.raw_content))
    result = parse(bytes(batch.raw_content), dialect=dialect)
    return header_signature(result.headers, dialect.delimiter)


def upsert_profile(
    db: Session,
    *,
    signature: str,
    name: str,
    dialect: CsvDialect,
    mapping: ColumnMapping,
) -> ImportProfile:
    profile = db.scalar(select(ImportProfile).where(ImportProfile.signature == signature))
    if profile is None:
        profile = ImportProfile(signature=signature)
        db.add(profile)
    profile.name = name
    profile.delimiter = dialect.delimiter
    profile.encoding = dialect.encoding
    profile.header_row = dialect.header_row
    profile.decimal_comma = dialect.decimal_comma
    profile.date_format = dialect.date_format or ""
    profile.amount_mode = dialect.amount_mode or guess_amount_mode(mapping)
    profile.mapping = mapping.as_dict()
    profile.last_used_at = datetime.now()
    return profile


# --------------------------------------------------------------------------- #
# Duplikate
# --------------------------------------------------------------------------- #
def mark_duplicates(db: Session, batch: ImportBatch) -> int:
    existing = db.scalars(
        select(Transaction).where(Transaction.account_id == batch.account_id)
    ).all()
    seen = {(t.booking_date, t.amount, _norm(t.note)) for t in existing}
    within_batch: set[tuple] = set()
    count = 0
    for row in batch.rows:
        if row.booking_date is None or row.amount is None:
            continue
        key = (row.booking_date, Decimal(row.amount), _norm(row.purpose))
        if key in seen or key in within_batch:
            row.is_duplicate = True
            row.include = False
            count += 1
        within_batch.add(key)
    return count


# --------------------------------------------------------------------------- #
# Historien-Vorschlag
# --------------------------------------------------------------------------- #
def _dominant(counter: Counter, total: int) -> int | None:
    if not counter:
        return None
    value, n = counter.most_common(1)[0]
    if len(counter) == 1 or (total and n / total > 0.8):
        return value
    return None


_MIN_SUBSTRING_LEN = 4  # kürzere Zahlungspartner nur exakt matchen


def suggest(db: Session, account_id: int, payee: str, purpose: str) -> tuple[int | None, int | None, str]:
    payee = (payee or "").strip()
    if len(payee) < 2:
        return None, None, ""

    txns = db.scalars(select(Transaction).where(Transaction.payee.ilike(payee))).all()
    basis = "exakt"
    if not txns and len(payee) >= _MIN_SUBSTRING_LEN:
        like = payee.replace("%", r"\%").replace("_", r"\_")
        txns = db.scalars(
            select(Transaction).where(Transaction.payee.ilike(f"%{like}%"))
        ).all()
        basis = "enthält"
    if not txns:
        return None, None, ""

    ct_id = _dominant(Counter(t.cost_type_id for t in txns), len(txns))
    if ct_id is None:
        return None, None, ""

    owner_id = None
    cost_type = db.get(CostType, ct_id)
    if cost_type is not None and cost_type.kind in OWNER_REQUIRED_KINDS:
        with_owner = [t.owner_id for t in txns if t.owner_id]
        owner_id = _dominant(Counter(with_owner), len(with_owner))

    note = f"aus Historie ({basis}: {payee[:40]})"
    return ct_id, owner_id, note


def apply_suggestions(db: Session, batch: ImportBatch) -> None:
    for row in batch.rows:
        if row.parse_error or row.cost_type_id:
            continue
        ct_id, owner_id, note = suggest(db, batch.account_id, row.payee, row.purpose)
        if ct_id:
            row.cost_type_id = ct_id
            row.owner_id = owner_id
            row.suggestion_note = note[:200]


# --------------------------------------------------------------------------- #
# Buchen
# --------------------------------------------------------------------------- #
def row_is_ready(row: ImportRow, cost_type: CostType | None) -> bool:
    if row.parse_error or row.booking_date is None or row.amount is None:
        return False
    if cost_type is None:
        return False
    if cost_type.kind in OWNER_REQUIRED_KINDS and row.owner_id is None:
        return False
    return True


def commit_batch(db: Session, batch: ImportBatch) -> int:
    cost_types = {c.id: c for c in db.scalars(select(CostType))}
    created = 0
    for row in batch.rows:
        if not row.include:
            continue
        cost_type = cost_types.get(row.cost_type_id) if row.cost_type_id else None
        if not row_is_ready(row, cost_type):
            raise ValueError(f"Zeile {row.line_no} ist nicht vollständig zugeordnet.")
        txn = Transaction(
            account_id=batch.account_id,
            booking_date=row.booking_date,
            payee=row.payee,
            cost_type_id=row.cost_type_id,
            owner_id=row.owner_id,
            amount=row.amount,
            note=row.purpose,
            source=TransactionSource.CSV_IMPORT,
        )
        db.add(txn)
        db.flush()
        txn.import_row_id = row.id
        created += 1

    from app.models.enums import ImportBatchStatus

    batch.status = ImportBatchStatus.IMPORTIERT
    batch.committed_at = datetime.now()
    return created
