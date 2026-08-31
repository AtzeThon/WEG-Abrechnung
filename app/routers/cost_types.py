"""Stammdaten-CRUD: Kostenarten (inkl. Kategorie, fachlicher Typ, Umlageschlüssel)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import auth
from app.database import get_db
from app.models import CostType, Transaction
from app.models.enums import AllocationStrategy, CostCategory, CostKind
from app.templating import templates
from app.web import flash

router = APIRouter(prefix="/kostenarten", tags=["cost_types"], dependencies=[Depends(auth.require_login)])

CATEGORY_OPTIONS = [(c.value, c.label) for c in CostCategory]
KIND_OPTIONS = [(k.value, k.label) for k in CostKind]
STRATEGY_OPTIONS = [(s.value, s.label) for s in AllocationStrategy]


def _form_context(db: Session, cost_type: CostType | None) -> dict:
    others = db.scalars(
        select(CostType).where(CostType.id != (cost_type.id if cost_type else -1)).order_by(CostType.name)
    )
    return {
        "cost_type": cost_type,
        "category_options": CATEGORY_OPTIONS,
        "kind_options": KIND_OPTIONS,
        "strategy_options": STRATEGY_OPTIONS,
        "proportional_options": [(ct.id, ct.name) for ct in others],
    }


def _apply_form(
    ct: CostType,
    *,
    name: str,
    category: str,
    default_supplier: str,
    kind: str,
    allocation_strategy: str,
    proportional_to_id: str | None,
    active: str | None,
) -> None:
    ct.name = name.strip()
    ct.category = CostCategory(category)
    ct.default_supplier = default_supplier.strip()
    ct.kind = CostKind(kind)
    ct.allocation_strategy = AllocationStrategy(allocation_strategy)
    ct.proportional_to_id = (
        int(proportional_to_id)
        if proportional_to_id and ct.allocation_strategy == AllocationStrategy.PROPORTIONAL
        else None
    )
    ct.active = active is not None


@router.get("", response_class=HTMLResponse, name="cost_types_list")
def cost_types_list(request: Request, db: Session = Depends(get_db)):
    cost_types = list(
        db.scalars(select(CostType).order_by(CostType.category, CostType.sort_order, CostType.name))
    )
    return templates.TemplateResponse(request, "cost_types/list.html", {"cost_types": cost_types})


@router.get("/neu", response_class=HTMLResponse, name="cost_types_new")
def cost_types_new(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "cost_types/form.html", _form_context(db, None))


@router.post("", name="cost_types_create")
def cost_types_create(
    request: Request,
    name: str = Form(...),
    category: str = Form("sonstiges"),
    default_supplier: str = Form(""),
    kind: str = Form("betriebskosten"),
    allocation_strategy: str = Form("mea"),
    proportional_to_id: str = Form(None),
    active: str = Form(None),
    db: Session = Depends(get_db),
):
    ct = CostType(sort_order=db.scalar(select(func.count(CostType.id))) or 0)
    _apply_form(
        ct,
        name=name,
        category=category,
        default_supplier=default_supplier,
        kind=kind,
        allocation_strategy=allocation_strategy,
        proportional_to_id=proportional_to_id,
        active=active,
    )
    db.add(ct)
    db.commit()
    flash(request, f"Kostenart „{ct.name}“ angelegt.")
    return RedirectResponse(request.url_for("cost_types_list"), status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{cost_type_id}/bearbeiten", response_class=HTMLResponse, name="cost_types_edit")
def cost_types_edit(request: Request, cost_type_id: int, db: Session = Depends(get_db)):
    ct = db.get(CostType, cost_type_id)
    if ct is None:
        flash(request, "Kostenart nicht gefunden.", "error")
        return RedirectResponse(request.url_for("cost_types_list"), status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request, "cost_types/form.html", _form_context(db, ct))


@router.post("/{cost_type_id}", name="cost_types_update")
def cost_types_update(
    request: Request,
    cost_type_id: int,
    name: str = Form(...),
    category: str = Form("sonstiges"),
    default_supplier: str = Form(""),
    kind: str = Form("betriebskosten"),
    allocation_strategy: str = Form("mea"),
    proportional_to_id: str = Form(None),
    active: str = Form(None),
    db: Session = Depends(get_db),
):
    ct = db.get(CostType, cost_type_id)
    if ct is None:
        flash(request, "Kostenart nicht gefunden.", "error")
        return RedirectResponse(request.url_for("cost_types_list"), status_code=status.HTTP_303_SEE_OTHER)
    _apply_form(
        ct,
        name=name,
        category=category,
        default_supplier=default_supplier,
        kind=kind,
        allocation_strategy=allocation_strategy,
        proportional_to_id=proportional_to_id,
        active=active,
    )
    db.commit()
    flash(request, f"Kostenart „{ct.name}“ gespeichert.")
    return RedirectResponse(request.url_for("cost_types_list"), status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{cost_type_id}/loeschen", name="cost_types_delete")
def cost_types_delete(request: Request, cost_type_id: int, db: Session = Depends(get_db)):
    ct = db.get(CostType, cost_type_id)
    if ct is None:
        flash(request, "Kostenart nicht gefunden.", "error")
    elif db.scalar(select(func.count(Transaction.id)).where(Transaction.cost_type_id == cost_type_id)):
        flash(request, f"Kostenart „{ct.name}“ hat Buchungen und kann nicht gelöscht werden.", "error")
    else:
        db.delete(ct)
        db.commit()
        flash(request, f"Kostenart „{ct.name}“ gelöscht.")
    return RedirectResponse(request.url_for("cost_types_list"), status_code=status.HTTP_303_SEE_OTHER)
