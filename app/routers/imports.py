"""CSV-Import von Kontoauszügen – Assistent (Upload, Mapping, Prüfen, Buchen)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import auth
from app.database import get_db
from app.imports import TARGET_LABELS, ColumnMapping, CsvDialect, guess_amount_mode
from app.imports.types import AMOUNT_MODES
from app.models import (
    OWNER_REQUIRED_KINDS,
    Account,
    CostType,
    ImportBatch,
    ImportProfile,
    Owner,
)
from app.models.enums import ImportBatchStatus
from app.services import imports as svc
from app.templating import templates
from app.web import flash

router = APIRouter(prefix="/import", tags=["imports"], dependencies=[Depends(auth.require_login)])

_OWNER_REQUIRED_VALUES = {k.value for k in OWNER_REQUIRED_KINDS}


def _get_batch(db: Session, batch_id: int) -> ImportBatch | None:
    return db.scalar(
        select(ImportBatch).options(selectinload(ImportBatch.rows)).where(ImportBatch.id == batch_id)
    )


def _lookups(db: Session) -> dict:
    cost_types = list(
        db.scalars(select(CostType).where(CostType.active).order_by(CostType.name))
    )
    return {
        "cost_types": cost_types,
        "cost_types_by_id": {c.id: c for c in cost_types},
        "owners": list(db.scalars(select(Owner).where(Owner.active).order_by(Owner.code))),
        "owner_required_kinds": _OWNER_REQUIRED_VALUES,
    }


def _review_context(db: Session, batch: ImportBatch) -> dict:
    cost_types = {c.id: c for c in db.scalars(select(CostType))}
    total = incl = ready = dupes = 0
    for row in batch.rows:
        if row.is_duplicate:
            dupes += 1
        if row.parse_error:
            continue
        total += 1
        if row.include:
            incl += 1
            if svc.row_is_ready(row, cost_types.get(row.cost_type_id)):
                ready += 1
    return {
        "batch": batch,
        "account": db.get(Account, batch.account_id),
        "counts": {"total": total, "included": incl, "ready": ready, "duplicates": dupes},
        "can_commit": incl > 0 and ready == incl and batch.status == ImportBatchStatus.ENTWURF,
        **_lookups(db),
    }


# --------------------------------------------------------------------------- #
# Übersicht + Upload
# --------------------------------------------------------------------------- #
@router.get("", response_class=HTMLResponse, name="imports_index")
def imports_index(request: Request, db: Session = Depends(get_db)):
    batches = list(
        db.scalars(
            select(ImportBatch).options(selectinload(ImportBatch.rows)).order_by(ImportBatch.id.desc())
        )
    )
    accounts = list(db.scalars(select(Account).where(Account.active).order_by(Account.name)))
    return templates.TemplateResponse(
        request, "imports/index.html", {"batches": batches, "accounts": accounts}
    )


@router.post("", name="imports_upload")
async def imports_upload(
    request: Request,
    account_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    raw = await file.read()
    if not raw:
        flash(request, "Die Datei ist leer.", "error")
        return RedirectResponse(request.url_for("imports_index"), status_code=status.HTTP_303_SEE_OTHER)

    batch = ImportBatch(account_id=account_id, filename=file.filename or "kontoauszug.csv", raw_content=raw)
    db.add(batch)
    db.flush()

    signature = svc.signature_for(batch)
    profile = db.scalar(select(ImportProfile).where(ImportProfile.signature == signature))
    if profile is not None:
        batch.profile_id = profile.id
        svc.parse_batch(db, batch, profile)
        svc.mark_duplicates(db, batch)
        svc.apply_suggestions(db, batch)
        db.commit()
        flash(request, f"{len(batch.rows)} Zeilen erkannt (Profil „{profile.name}“).")
        return RedirectResponse(
            request.url_for("imports_review", batch_id=batch.id), status_code=status.HTTP_303_SEE_OTHER
        )

    db.commit()
    return RedirectResponse(
        request.url_for("imports_mapping", batch_id=batch.id), status_code=status.HTTP_303_SEE_OTHER
    )


# --------------------------------------------------------------------------- #
# Spalten-Mapping
# --------------------------------------------------------------------------- #
@router.get("/{batch_id}/mapping", response_class=HTMLResponse, name="imports_mapping")
def imports_mapping(request: Request, batch_id: int, db: Session = Depends(get_db)):
    batch = _get_batch(db, batch_id)
    if batch is None:
        flash(request, "Import nicht gefunden.", "error")
        return RedirectResponse(request.url_for("imports_index"), status_code=status.HTTP_303_SEE_OTHER)

    headers, dialect, mapping, sample = svc.sniff_batch(batch)
    default_name = f"{db.get(Account, batch.account_id).name} ({', '.join(headers[:3])})"
    return templates.TemplateResponse(
        request,
        "imports/mapping.html",
        {
            "batch": batch,
            "headers": headers,
            "dialect": dialect,
            "mapping": mapping,
            "sample": sample,
            "target_labels": TARGET_LABELS,
            "amount_modes": AMOUNT_MODES,
            "detected_mode": guess_amount_mode(mapping),
            "default_name": default_name,
        },
    )


@router.post("/{batch_id}/mapping", name="imports_mapping_save")
async def imports_mapping_save(request: Request, batch_id: int, db: Session = Depends(get_db)):
    batch = _get_batch(db, batch_id)
    if batch is None:
        flash(request, "Import nicht gefunden.", "error")
        return RedirectResponse(request.url_for("imports_index"), status_code=status.HTTP_303_SEE_OTHER)

    form = await request.form()
    _, sniffed, _, _ = svc.sniff_batch(batch)
    amount_mode = form.get("amount_mode") or "single"
    header_row_1based = form.get("header_row")
    header_row = int(header_row_1based) - 1 if header_row_1based else sniffed.header_row
    dialect = CsvDialect(
        delimiter=sniffed.delimiter,
        encoding=sniffed.encoding,
        header_row=max(header_row, 0),
        decimal_comma=True,
        date_format=(form.get("date_format") or "").strip() or None,
        amount_mode=amount_mode,
    )
    mapping = ColumnMapping(
        date=form.get("map_date") or None,
        payee=form.get("map_payee") or None,
        purpose=form.get("map_purpose") or None,
        amount=form.get("map_amount") or None,
        amount_debit=form.get("map_amount_debit") or None,
        amount_credit=form.get("map_amount_credit") or None,
        sign_column=form.get("map_sign_column") or None,
        category=form.get("map_category") or None,
        owner=form.get("map_owner") or None,
    )
    if not mapping.is_complete(amount_mode):
        flash(request, "Bitte mindestens Datum und Betrag zuordnen.", "error")
        return RedirectResponse(
            request.url_for("imports_mapping", batch_id=batch.id), status_code=status.HTTP_303_SEE_OTHER
        )

    signature = svc.signature_for(batch)
    profile = svc.upsert_profile(
        db,
        signature=signature,
        name=(form.get("profile_name") or "Import-Profil").strip(),
        dialect=dialect,
        mapping=mapping,
    )
    db.flush()
    batch.profile_id = profile.id
    svc.parse_batch(db, batch, profile)
    svc.mark_duplicates(db, batch)
    svc.apply_suggestions(db, batch)
    db.commit()
    flash(request, f"Mapping gespeichert, {len(batch.rows)} Zeilen erkannt.")
    return RedirectResponse(
        request.url_for("imports_review", batch_id=batch.id), status_code=status.HTTP_303_SEE_OTHER
    )


# --------------------------------------------------------------------------- #
# Prüfen + Zuordnen
# --------------------------------------------------------------------------- #
@router.get("/{batch_id}", response_class=HTMLResponse, name="imports_review")
def imports_review(request: Request, batch_id: int, db: Session = Depends(get_db)):
    batch = _get_batch(db, batch_id)
    if batch is None:
        flash(request, "Import nicht gefunden.", "error")
        return RedirectResponse(request.url_for("imports_index"), status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request, "imports/review.html", _review_context(db, batch))


@router.post("/{batch_id}/zeile/{row_id}", response_class=HTMLResponse, name="imports_row_update")
async def imports_row_update(request: Request, batch_id: int, row_id: int, db: Session = Depends(get_db)):
    batch = _get_batch(db, batch_id)
    row = next((r for r in batch.rows if r.id == row_id), None) if batch else None
    if row is None:
        return HTMLResponse("", status_code=404)

    form = await request.form()
    row.include = form.get("include") is not None and not row.parse_error
    ct_raw = form.get("cost_type_id")
    row.cost_type_id = int(ct_raw) if ct_raw else None
    owner_raw = form.get("owner_id")
    row.owner_id = int(owner_raw) if owner_raw else None
    row.suggestion_note = ""

    cost_type = db.get(CostType, row.cost_type_id) if row.cost_type_id else None
    if cost_type is None or cost_type.kind not in OWNER_REQUIRED_KINDS:
        row.owner_id = None
    db.commit()

    ctx = _review_context(db, batch)
    ctx["row"] = row
    return templates.TemplateResponse(request, "imports/_row.html", ctx)


# --------------------------------------------------------------------------- #
# Buchen / Verwerfen
# --------------------------------------------------------------------------- #
@router.post("/{batch_id}/buchen", name="imports_commit")
def imports_commit(request: Request, batch_id: int, db: Session = Depends(get_db)):
    batch = _get_batch(db, batch_id)
    if batch is None or batch.status != ImportBatchStatus.ENTWURF:
        flash(request, "Import kann nicht gebucht werden.", "error")
        return RedirectResponse(request.url_for("imports_index"), status_code=status.HTTP_303_SEE_OTHER)

    from app.services.periods import locked_period_for_date

    for row in batch.rows:
        if row.include and row.booking_date and locked_period_for_date(db, row.booking_date):
            flash(
                request,
                f"Zeile {row.line_no}: {row.booking_date:%d.%m.%Y} liegt in einem "
                "abgeschlossenen Zeitraum. Import nicht möglich.",
                "error",
            )
            return RedirectResponse(
                request.url_for("imports_review", batch_id=batch.id),
                status_code=status.HTTP_303_SEE_OTHER,
            )
    try:
        created = svc.commit_batch(db, batch)
    except ValueError as exc:
        db.rollback()
        flash(request, str(exc), "error")
        return RedirectResponse(
            request.url_for("imports_review", batch_id=batch.id), status_code=status.HTTP_303_SEE_OTHER
        )
    account_id = batch.account_id
    db.commit()
    flash(request, f"{created} Buchung(en) importiert.")
    return RedirectResponse(
        request.url_for("transactions_list").include_query_params(account_id=account_id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{batch_id}/verwerfen", name="imports_discard")
def imports_discard(request: Request, batch_id: int, db: Session = Depends(get_db)):
    batch = db.get(ImportBatch, batch_id)
    if batch is not None:
        batch.status = ImportBatchStatus.VERWORFEN
        db.commit()
        flash(request, "Import verworfen.")
    return RedirectResponse(request.url_for("imports_index"), status_code=status.HTTP_303_SEE_OTHER)
