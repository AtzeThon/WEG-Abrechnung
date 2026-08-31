"""Stammdaten-CRUD: Eigentümer."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import auth
from app.database import get_db
from app.models import Owner, Transaction
from app.templating import templates
from app.web import flash, parse_decimal

router = APIRouter(prefix="/eigentuemer", tags=["owners"], dependencies=[Depends(auth.require_login)])


def _all_owners(db: Session) -> list[Owner]:
    return list(db.scalars(select(Owner).order_by(Owner.sort_order, Owner.code)))


@router.get("", response_class=HTMLResponse, name="owners_list")
def owners_list(request: Request, db: Session = Depends(get_db)):
    owners = _all_owners(db)
    total_mea = sum((o.mea for o in owners), Decimal("0"))
    return templates.TemplateResponse(
        request,
        "owners/list.html",
        {"owners": owners, "total_mea": total_mea},
    )


@router.get("/neu", response_class=HTMLResponse, name="owners_new")
def owners_new(request: Request):
    return templates.TemplateResponse(request, "owners/form.html", {"owner": None})


@router.post("", name="owners_create")
def owners_create(
    request: Request,
    code: str = Form(...),
    name: str = Form(""),
    email: str = Form(""),
    mea: str = Form("0"),
    active: str = Form(None),
    db: Session = Depends(get_db),
):
    owner = Owner(
        code=code.strip(),
        name=name.strip(),
        email=email.strip(),
        mea=parse_decimal(mea),
        active=active is not None,
        sort_order=db.scalar(select(func.count(Owner.id))) or 0,
    )
    db.add(owner)
    db.commit()
    flash(request, f"Eigentümer {owner.code} angelegt.")
    return RedirectResponse(request.url_for("owners_list"), status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{owner_id}/bearbeiten", response_class=HTMLResponse, name="owners_edit")
def owners_edit(request: Request, owner_id: int, db: Session = Depends(get_db)):
    owner = db.get(Owner, owner_id)
    if owner is None:
        flash(request, "Eigentümer nicht gefunden.", "error")
        return RedirectResponse(request.url_for("owners_list"), status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request, "owners/form.html", {"owner": owner})


@router.post("/{owner_id}", name="owners_update")
def owners_update(
    request: Request,
    owner_id: int,
    code: str = Form(...),
    name: str = Form(""),
    email: str = Form(""),
    mea: str = Form("0"),
    active: str = Form(None),
    db: Session = Depends(get_db),
):
    owner = db.get(Owner, owner_id)
    if owner is None:
        flash(request, "Eigentümer nicht gefunden.", "error")
        return RedirectResponse(request.url_for("owners_list"), status_code=status.HTTP_303_SEE_OTHER)
    owner.code = code.strip()
    owner.name = name.strip()
    owner.email = email.strip()
    owner.mea = parse_decimal(mea)
    owner.active = active is not None
    db.commit()
    flash(request, f"Eigentümer {owner.code} gespeichert.")
    return RedirectResponse(request.url_for("owners_list"), status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{owner_id}/loeschen", name="owners_delete")
def owners_delete(request: Request, owner_id: int, db: Session = Depends(get_db)):
    owner = db.get(Owner, owner_id)
    if owner is None:
        flash(request, "Eigentümer nicht gefunden.", "error")
    elif db.scalar(select(func.count(Transaction.id)).where(Transaction.owner_id == owner_id)):
        flash(
            request,
            f"Eigentümer {owner.code} kann nicht gelöscht werden – es existieren Buchungen.",
            "error",
        )
    else:
        db.delete(owner)
        db.commit()
        flash(request, f"Eigentümer {owner.code} gelöscht.")
    return RedirectResponse(request.url_for("owners_list"), status_code=status.HTTP_303_SEE_OTHER)
