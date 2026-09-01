"""Abrechnungsperioden: CRUD, manuelle Anfangswerte, Perioden-Übersicht."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import auth
from app.database import get_db
from app.models import (
    AllocationOverride,
    BillingPeriod,
    CostType,
    Owner,
    PeriodOpeningBalance,
)
from app.models.enums import AllocationStrategy, CostCategory, PeriodStatus
from app.services.billing import compute_period
from app.services.periods import carry_forward_balances, previous_period, set_status
from app.templating import templates
from app.web import flash, parse_date, parse_decimal

router = APIRouter(prefix="/abrechnungen", tags=["periods"], dependencies=[Depends(auth.require_login)])


def _active_owners(db: Session) -> list[Owner]:
    return list(db.scalars(select(Owner).where(Owner.active).order_by(Owner.sort_order, Owner.code)))


def _zaehler_cost_types(db: Session) -> list[CostType]:
    return list(
        db.scalars(
            select(CostType)
            .where(CostType.allocation_strategy == AllocationStrategy.ZAEHLER)
            .order_by(CostType.name)
        )
    )


@router.get("", response_class=HTMLResponse, name="periods_list")
def periods_list(request: Request, db: Session = Depends(get_db)):
    periods = list(db.scalars(select(BillingPeriod).order_by(BillingPeriod.start_date.desc())))
    return templates.TemplateResponse(request, "periods/list.html", {"periods": periods})


@router.get("/neu", response_class=HTMLResponse, name="periods_new")
def periods_new(request: Request):
    today = date.today()
    return templates.TemplateResponse(request, "periods/form.html", {"period": None, "today": today})


@router.post("", name="periods_create")
def periods_create(
    request: Request,
    label: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    reserve_opening_balance: str = Form("0"),
    db: Session = Depends(get_db),
):
    period = BillingPeriod(
        label=label.strip(),
        start_date=parse_date(start_date),
        end_date=parse_date(end_date),
        reserve_opening_balance=parse_decimal(reserve_opening_balance),
        status=PeriodStatus.DRAFT,
    )
    db.add(period)
    db.flush()
    for owner in _active_owners(db):
        db.add(PeriodOpeningBalance(period_id=period.id, owner_id=owner.id))
    db.commit()
    flash(request, f"Periode „{period.label}“ angelegt. Bitte Anfangswerte erfassen.")
    return RedirectResponse(
        request.url_for("periods_edit", period_id=period.id), status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/{period_id}/bearbeiten", response_class=HTMLResponse, name="periods_edit")
def periods_edit(request: Request, period_id: int, db: Session = Depends(get_db)):
    period = db.get(BillingPeriod, period_id)
    if period is None:
        flash(request, "Periode nicht gefunden.", "error")
        return RedirectResponse(request.url_for("periods_list"), status_code=status.HTTP_303_SEE_OTHER)

    owners = _active_owners(db)
    carryover = {
        ob.owner_id: ob.hausgeld_carryover
        for ob in db.scalars(
            select(PeriodOpeningBalance).where(PeriodOpeningBalance.period_id == period_id)
        )
    }
    overrides = {
        (o.cost_type_id, o.owner_id): o.amount
        for o in db.scalars(
            select(AllocationOverride).where(AllocationOverride.period_id == period_id)
        )
    }
    return templates.TemplateResponse(
        request,
        "periods/form.html",
        {
            "period": period,
            "owners": owners,
            "carryover": carryover,
            "zaehler_cost_types": _zaehler_cost_types(db),
            "overrides": overrides,
            "has_previous": previous_period(db, period) is not None,
        },
    )


@router.post("/{period_id}/vorperiode-uebernehmen", name="periods_carry_forward")
def periods_carry_forward(request: Request, period_id: int, db: Session = Depends(get_db)):
    period = db.get(BillingPeriod, period_id)
    if period is None:
        flash(request, "Periode nicht gefunden.", "error")
        return RedirectResponse(request.url_for("periods_list"), status_code=status.HTTP_303_SEE_OTHER)
    if period.status == PeriodStatus.FINAL:
        flash(request, "Abgeschlossene Periode – zuerst auf Entwurf zurücksetzen.", "error")
    else:
        prev = carry_forward_balances(db, period)
        if prev is None:
            flash(request, "Keine Vorperiode gefunden.", "error")
        else:
            db.commit()
            flash(
                request,
                f"Anfangswerte aus „{prev.label}“ übernommen "
                "(Rücklagen-Anfangssaldo und Saldovortrag je Eigentümer). Bitte prüfen.",
            )
    return RedirectResponse(
        request.url_for("periods_edit", period_id=period_id), status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{period_id}", name="periods_update")
async def periods_update(request: Request, period_id: int, db: Session = Depends(get_db)):
    period = db.get(BillingPeriod, period_id)
    if period is None:
        flash(request, "Periode nicht gefunden.", "error")
        return RedirectResponse(request.url_for("periods_list"), status_code=status.HTTP_303_SEE_OTHER)
    if period.status == PeriodStatus.FINAL:
        flash(
            request,
            "Die Periode ist abgeschlossen. Zum Ändern zuerst auf „Entwurf“ zurücksetzen.",
            "error",
        )
        return RedirectResponse(
            request.url_for("period_overview", period_id=period_id),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    form = await request.form()
    period.label = str(form.get("label", period.label)).strip()
    period.start_date = parse_date(form.get("start_date")) or period.start_date
    period.end_date = parse_date(form.get("end_date")) or period.end_date
    period.reserve_opening_balance = parse_decimal(form.get("reserve_opening_balance"))

    owners = _active_owners(db)
    owner_by_id = {o.id: o for o in owners}

    # Saldovortrag Hausgeld je Eigentümer
    existing_ob = {
        ob.owner_id: ob
        for ob in db.scalars(
            select(PeriodOpeningBalance).where(PeriodOpeningBalance.period_id == period_id)
        )
    }
    for owner in owners:
        value = parse_decimal(form.get(f"carryover_{owner.id}"))
        ob = existing_ob.get(owner.id)
        if ob is None:
            db.add(PeriodOpeningBalance(period_id=period_id, owner_id=owner.id, hausgeld_carryover=value))
        else:
            ob.hausgeld_carryover = value

    # Zähler-Direkteingaben je Kostenart × Eigentümer
    existing_ov = {
        (o.cost_type_id, o.owner_id): o
        for o in db.scalars(
            select(AllocationOverride).where(AllocationOverride.period_id == period_id)
        )
    }
    for ct in _zaehler_cost_types(db):
        for owner in owners:
            raw = form.get(f"override_{ct.id}_{owner.id}")
            key = (ct.id, owner.id)
            if raw is None or str(raw).strip() == "":
                if key in existing_ov:
                    db.delete(existing_ov[key])
                continue
            value = parse_decimal(raw)
            if key in existing_ov:
                existing_ov[key].amount = value
            elif owner.id in owner_by_id:
                db.add(
                    AllocationOverride(
                        period_id=period_id, cost_type_id=ct.id, owner_id=owner.id, amount=value
                    )
                )

    db.commit()
    flash(request, "Periode gespeichert.")
    return RedirectResponse(
        request.url_for("period_overview", period_id=period_id), status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{period_id}/status", name="periods_set_status")
def periods_set_status(
    request: Request, period_id: int, target: str = Form(...), db: Session = Depends(get_db)
):
    period = db.get(BillingPeriod, period_id)
    if period is not None:
        final = target == "final"
        set_status(db, period, final=final)
        db.commit()
        if final:
            flash(
                request,
                f"Periode „{period.label}“ abgeschlossen. Buchungen im Zeitraum "
                f"{period.start_date:%d.%m.%Y}–{period.end_date:%d.%m.%Y} sind jetzt gesperrt.",
            )
        else:
            flash(request, f"Periode „{period.label}“ ist wieder ein Entwurf (Buchungen entsperrt).")
    return RedirectResponse(
        request.url_for("period_overview", period_id=period_id), status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{period_id}/loeschen", name="periods_delete")
def periods_delete(request: Request, period_id: int, db: Session = Depends(get_db)):
    period = db.get(BillingPeriod, period_id)
    if period is not None:
        db.delete(period)
        db.commit()
        flash(request, "Periode gelöscht.")
    return RedirectResponse(request.url_for("periods_list"), status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{period_id}", response_class=HTMLResponse, name="period_overview")
def period_overview(request: Request, period_id: int, db: Session = Depends(get_db)):
    period = db.get(BillingPeriod, period_id)
    if period is None:
        flash(request, "Periode nicht gefunden.", "error")
        return RedirectResponse(request.url_for("periods_list"), status_code=status.HTTP_303_SEE_OTHER)
    result = compute_period(db, period)

    # Kostenarten nach Kategorie gruppieren (nur solche mit Betrag)
    labels = {c.value: c.label for c in CostCategory}
    groups: dict[str, list] = {}
    for name in result.cost_type_order:
        ct = result.cost_types[name]
        if ct.weg_total == 0 and all(v == 0 for v in ct.shares.values()):
            continue
        groups.setdefault(labels.get(ct.category, ct.category), []).append(ct)

    return templates.TemplateResponse(
        request,
        "periods/overview.html",
        {"period": period, "result": result, "cost_groups": groups},
    )
