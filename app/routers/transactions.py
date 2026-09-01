"""Buchungserfassung: Formular, filterbare Liste, Konto-Ledger."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app import auth
from app.database import get_db
from app.models import Account, CostType, Owner, Transaction
from app.services.periods import locked_period_for_date
from app.services.transfers import record_transfer
from app.templating import templates
from app.web import flash, parse_date, parse_decimal

router = APIRouter(prefix="/buchungen", tags=["transactions"], dependencies=[Depends(auth.require_login)])

_SORT_COLUMNS = {
    "datum": Transaction.booking_date,
    "betrag": Transaction.amount,
    "partner": Transaction.payee,
}


def _int_or_none(value: str | None) -> int | None:
    """Leere Filter-Query-Parameter ('') als 'nicht gesetzt' behandeln."""
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _lookups(db: Session) -> dict:
    return {
        "accounts": list(db.scalars(select(Account).order_by(Account.sort_order, Account.name))),
        "owners": list(db.scalars(select(Owner).order_by(Owner.sort_order, Owner.code))),
        "cost_types": list(
            db.scalars(select(CostType).where(CostType.active).order_by(CostType.name))
        ),
    }


@router.get("", response_class=HTMLResponse, name="transactions_list")
def transactions_list(
    request: Request,
    db: Session = Depends(get_db),
    account_id: str | None = None,
    owner_id: str | None = None,
    cost_type_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    q: str | None = None,
    sort: str = "datum",
    dir: str = "desc",
):
    account_id = _int_or_none(account_id)
    owner_id = _int_or_none(owner_id)
    cost_type_id = _int_or_none(cost_type_id)

    stmt = select(Transaction).options(
        selectinload(Transaction.account),
        selectinload(Transaction.cost_type),
        selectinload(Transaction.owner),
    )
    if account_id:
        stmt = stmt.where(Transaction.account_id == account_id)
    if owner_id:
        stmt = stmt.where(Transaction.owner_id == owner_id)
    if cost_type_id:
        stmt = stmt.where(Transaction.cost_type_id == cost_type_id)
    d_from, d_to = parse_date(date_from), parse_date(date_to)
    if d_from:
        stmt = stmt.where(Transaction.booking_date >= d_from)
    if d_to:
        stmt = stmt.where(Transaction.booking_date <= d_to)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Transaction.payee.ilike(like), Transaction.note.ilike(like)))

    col = _SORT_COLUMNS.get(sort, Transaction.booking_date)
    stmt = stmt.order_by(col.desc() if dir == "desc" else col.asc(), Transaction.id.desc())

    rows = list(db.scalars(stmt))
    total = sum((t.amount for t in rows), Decimal("0"))
    context = {
        "rows": rows,
        "total": total,
        "filters": {
            "account_id": account_id, "owner_id": owner_id, "cost_type_id": cost_type_id,
            "date_from": date_from or "", "date_to": date_to or "", "q": q or "",
            "sort": sort, "dir": dir,
        },
        **_lookups(db),
    }
    template = "transactions/_table.html" if request.headers.get("HX-Request") else "transactions/list.html"
    return templates.TemplateResponse(request, template, context)


@router.get("/neu", response_class=HTMLResponse, name="transactions_new")
def transactions_new(request: Request, db: Session = Depends(get_db), account_id: str | None = None):
    return templates.TemplateResponse(
        request,
        "transactions/form.html",
        {"txn": None, "preset_account_id": _int_or_none(account_id), **_lookups(db)},
    )


def _locked_message(db: Session, *dates) -> str | None:
    """Fällt eines der Daten in eine abgeschlossene (finale) Periode?"""
    for d in dates:
        if d is None:
            continue
        period = locked_period_for_date(db, d)
        if period is not None:
            return (
                f"Der {d:%d.%m.%Y} liegt im abgeschlossenen Zeitraum „{period.label}“. "
                "Setze die Periode zuerst auf „Entwurf“ zurück, um Buchungen zu ändern."
            )
    return None


def _form_values(
    booking_date: str, payee: str, account_id: int, cost_type_id: int,
    owner_id: str | None, amount: str, note: str,
) -> dict:
    d = parse_date(booking_date)
    if d is None:
        raise ValueError("Datum ist erforderlich.")
    return {
        "booking_date": d,
        "payee": payee.strip(),
        "account_id": account_id,
        "cost_type_id": cost_type_id,
        "owner_id": int(owner_id) if owner_id else None,
        "amount": parse_decimal(amount, default=None),
        "note": note.strip(),
    }


@router.post("", name="transactions_create")
def transactions_create(
    request: Request,
    booking_date: str = Form(...),
    payee: str = Form(""),
    account_id: int = Form(...),
    cost_type_id: int = Form(...),
    owner_id: str = Form(None),
    amount: str = Form(...),
    note: str = Form(""),
    again: str = Form(None),
    db: Session = Depends(get_db),
):
    try:
        values = _form_values(booking_date, payee, account_id, cost_type_id, owner_id, amount, note)
    except ValueError as exc:
        flash(request, str(exc), "error")
        return RedirectResponse(request.url_for("transactions_new"), status_code=status.HTTP_303_SEE_OTHER)
    if values["amount"] is None:
        flash(request, "Betrag ist erforderlich.", "error")
        return RedirectResponse(request.url_for("transactions_new"), status_code=status.HTTP_303_SEE_OTHER)

    locked = _locked_message(db, values["booking_date"])
    if locked:
        flash(request, locked, "error")
        return RedirectResponse(request.url_for("transactions_new"), status_code=status.HTTP_303_SEE_OTHER)

    db.add(Transaction(**values))
    db.commit()
    flash(request, "Buchung gespeichert.")
    target = "transactions_new" if again is not None else "transactions_list"
    return RedirectResponse(request.url_for(target), status_code=status.HTTP_303_SEE_OTHER)


@router.get("/umbuchung", response_class=HTMLResponse, name="transfer_new")
def transfer_new(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "transactions/transfer.html", _lookups(db))


@router.post("/umbuchung", name="transfer_create")
def transfer_create(
    request: Request,
    from_account_id: int = Form(...),
    to_account_id: int = Form(...),
    amount: str = Form(...),
    booking_date: str = Form(...),
    owner_id: str = Form(None),
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    d = parse_date(booking_date)
    back = RedirectResponse(request.url_for("transfer_new"), status_code=status.HTTP_303_SEE_OTHER)
    if d is None:
        flash(request, "Datum ist erforderlich.", "error")
        return back
    locked = _locked_message(db, d)
    if locked:
        flash(request, locked, "error")
        return back
    try:
        record_transfer(
            db,
            from_account_id=from_account_id,
            to_account_id=to_account_id,
            amount=parse_decimal(amount, default=None),
            booking_date=d,
            owner_id=_int_or_none(owner_id),
            note=note,
        )
    except ValueError as exc:
        flash(request, str(exc), "error")
        return back
    db.commit()
    flash(request, "Umbuchung erfasst (zwei Buchungen angelegt).")
    return RedirectResponse(request.url_for("transactions_list"), status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{txn_id}/bearbeiten", response_class=HTMLResponse, name="transactions_edit")
def transactions_edit(request: Request, txn_id: int, db: Session = Depends(get_db)):
    txn = db.get(Transaction, txn_id)
    if txn is None:
        flash(request, "Buchung nicht gefunden.", "error")
        return RedirectResponse(request.url_for("transactions_list"), status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request, "transactions/form.html", {"txn": txn, "preset_account_id": None, **_lookups(db)}
    )


@router.post("/{txn_id}", name="transactions_update")
def transactions_update(
    request: Request,
    txn_id: int,
    booking_date: str = Form(...),
    payee: str = Form(""),
    account_id: int = Form(...),
    cost_type_id: int = Form(...),
    owner_id: str = Form(None),
    amount: str = Form(...),
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    txn = db.get(Transaction, txn_id)
    if txn is None:
        flash(request, "Buchung nicht gefunden.", "error")
        return RedirectResponse(request.url_for("transactions_list"), status_code=status.HTTP_303_SEE_OTHER)
    try:
        values = _form_values(booking_date, payee, account_id, cost_type_id, owner_id, amount, note)
    except ValueError as exc:
        flash(request, str(exc), "error")
        return RedirectResponse(
            request.url_for("transactions_edit", txn_id=txn_id), status_code=status.HTTP_303_SEE_OTHER
        )
    if values["amount"] is None:
        flash(request, "Betrag ist erforderlich.", "error")
        return RedirectResponse(
            request.url_for("transactions_edit", txn_id=txn_id), status_code=status.HTTP_303_SEE_OTHER
        )
    locked = _locked_message(db, txn.booking_date, values["booking_date"])
    if locked:
        flash(request, locked, "error")
        return RedirectResponse(
            request.url_for("transactions_edit", txn_id=txn_id), status_code=status.HTTP_303_SEE_OTHER
        )
    for key, value in values.items():
        setattr(txn, key, value)
    db.commit()
    flash(request, "Buchung aktualisiert.")
    return RedirectResponse(request.url_for("transactions_list"), status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{txn_id}/loeschen", name="transactions_delete")
def transactions_delete(request: Request, txn_id: int, db: Session = Depends(get_db)):
    txn = db.get(Transaction, txn_id)
    if txn is not None:
        locked = _locked_message(db, txn.booking_date)
        if locked:
            flash(request, locked, "error")
            return RedirectResponse(
                request.url_for("transactions_list"), status_code=status.HTTP_303_SEE_OTHER
            )
        db.delete(txn)
        db.commit()
        flash(request, "Buchung gelöscht.")
    return RedirectResponse(request.url_for("transactions_list"), status_code=status.HTTP_303_SEE_OTHER)


@router.get("/kontoauszug/{account_id}", response_class=HTMLResponse, name="account_ledger")
def account_ledger(request: Request, account_id: int, db: Session = Depends(get_db)):
    account = db.get(Account, account_id)
    if account is None:
        flash(request, "Konto nicht gefunden.", "error")
        return RedirectResponse(request.url_for("accounts_list"), status_code=status.HTTP_303_SEE_OTHER)
    rows = list(
        db.scalars(
            select(Transaction)
            .options(selectinload(Transaction.cost_type), selectinload(Transaction.owner))
            .where(Transaction.account_id == account_id)
            .order_by(Transaction.booking_date, Transaction.id)
        )
    )
    running = account.opening_balance
    ledger = []
    for t in rows:
        running += t.amount
        ledger.append((t, running))
    return templates.TemplateResponse(
        request,
        "transactions/ledger.html",
        {"account": account, "ledger": ledger, "closing": running},
    )


@router.get("/konto-saldo/{account_id}", name="account_balance_json")
def account_balance(account_id: int, db: Session = Depends(get_db)) -> dict:
    account = db.get(Account, account_id)
    if account is None:
        return {"balance": None}
    total = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.account_id == account_id
        )
    )
    return {"balance": str(account.opening_balance + Decimal(total or 0))}
