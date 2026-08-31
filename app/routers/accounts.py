"""Stammdaten-CRUD: Bankkonten."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import auth
from app.database import get_db
from app.models import Account, Transaction
from app.models.enums import AccountType
from app.templating import templates
from app.web import flash, parse_date, parse_decimal

router = APIRouter(prefix="/konten", tags=["accounts"], dependencies=[Depends(auth.require_login)])

_TYPE_OPTIONS = [(t.value, {"giro": "Girokonto", "ruecklage": "Rücklagenkonto"}[t.value]) for t in AccountType]


def _balance(db: Session, account: Account) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.account_id == account.id
        )
    )
    return account.opening_balance + Decimal(total or 0)


@router.get("", response_class=HTMLResponse, name="accounts_list")
def accounts_list(request: Request, db: Session = Depends(get_db)):
    accounts = list(db.scalars(select(Account).order_by(Account.sort_order, Account.name)))
    balances = {a.id: _balance(db, a) for a in accounts}
    return templates.TemplateResponse(
        request, "accounts/list.html", {"accounts": accounts, "balances": balances}
    )


@router.get("/neu", response_class=HTMLResponse, name="accounts_new")
def accounts_new(request: Request):
    return templates.TemplateResponse(
        request, "accounts/form.html", {"account": None, "type_options": _TYPE_OPTIONS}
    )


@router.post("", name="accounts_create")
def accounts_create(
    request: Request,
    name: str = Form(...),
    type: str = Form("giro"),
    opening_balance: str = Form("0"),
    opening_balance_date: str = Form(""),
    active: str = Form(None),
    db: Session = Depends(get_db),
):
    account = Account(
        name=name.strip(),
        type=AccountType(type),
        opening_balance=parse_decimal(opening_balance),
        opening_balance_date=parse_date(opening_balance_date),
        active=active is not None,
        sort_order=db.scalar(select(func.count(Account.id))) or 0,
    )
    db.add(account)
    db.commit()
    flash(request, f"Konto „{account.name}“ angelegt.")
    return RedirectResponse(request.url_for("accounts_list"), status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{account_id}/bearbeiten", response_class=HTMLResponse, name="accounts_edit")
def accounts_edit(request: Request, account_id: int, db: Session = Depends(get_db)):
    account = db.get(Account, account_id)
    if account is None:
        flash(request, "Konto nicht gefunden.", "error")
        return RedirectResponse(request.url_for("accounts_list"), status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request, "accounts/form.html", {"account": account, "type_options": _TYPE_OPTIONS}
    )


@router.post("/{account_id}", name="accounts_update")
def accounts_update(
    request: Request,
    account_id: int,
    name: str = Form(...),
    type: str = Form("giro"),
    opening_balance: str = Form("0"),
    opening_balance_date: str = Form(""),
    active: str = Form(None),
    db: Session = Depends(get_db),
):
    account = db.get(Account, account_id)
    if account is None:
        flash(request, "Konto nicht gefunden.", "error")
        return RedirectResponse(request.url_for("accounts_list"), status_code=status.HTTP_303_SEE_OTHER)
    account.name = name.strip()
    account.type = AccountType(type)
    account.opening_balance = parse_decimal(opening_balance)
    account.opening_balance_date = parse_date(opening_balance_date)
    account.active = active is not None
    db.commit()
    flash(request, f"Konto „{account.name}“ gespeichert.")
    return RedirectResponse(request.url_for("accounts_list"), status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{account_id}/loeschen", name="accounts_delete")
def accounts_delete(request: Request, account_id: int, db: Session = Depends(get_db)):
    account = db.get(Account, account_id)
    if account is None:
        flash(request, "Konto nicht gefunden.", "error")
    elif db.scalar(select(func.count(Transaction.id)).where(Transaction.account_id == account_id)):
        flash(request, f"Konto „{account.name}“ hat Buchungen und kann nicht gelöscht werden.", "error")
    else:
        db.delete(account)
        db.commit()
        flash(request, f"Konto „{account.name}“ gelöscht.")
    return RedirectResponse(request.url_for("accounts_list"), status_code=status.HTTP_303_SEE_OTHER)
