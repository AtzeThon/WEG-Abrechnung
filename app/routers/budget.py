"""Wirtschaftsplan / Prognoserechnung – Web-Ansicht, Speichern und PDF."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import auth
from app.database import get_db
from app.models import BillingPeriod
from app.services import budget as budget_service
from app.templating import templates
from app.web import flash, parse_decimal

router = APIRouter(
    prefix="/wirtschaftsplan", tags=["budget"], dependencies=[Depends(auth.require_login)]
)


def _periods(db: Session) -> list[BillingPeriod]:
    return list(db.scalars(select(BillingPeriod).order_by(BillingPeriod.start_date.desc())))


def _load(db: Session, period_id: int) -> BillingPeriod | None:
    return db.get(BillingPeriod, period_id)


def _grid_context(db: Session, period: BillingPeriod, *, pdf: bool) -> dict:
    grid = budget_service.build_grid(db, period)
    return {"period": period, "grid": grid, "pdf": pdf}


@router.get("", response_class=HTMLResponse, name="budget_index")
def budget_index(request: Request, db: Session = Depends(get_db)):
    periods = _periods(db)
    if len(periods) == 1:
        return RedirectResponse(
            request.url_for("budget_view", period_id=periods[0].id),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return templates.TemplateResponse(request, "budget/index.html", {"periods": periods})


@router.get("/{period_id}", response_class=HTMLResponse, name="budget_view")
def budget_view(request: Request, period_id: int, db: Session = Depends(get_db)):
    period = _load(db, period_id)
    if period is None:
        flash(request, "Periode nicht gefunden.", "error")
        return RedirectResponse(
            request.url_for("budget_index"), status_code=status.HTTP_303_SEE_OTHER
        )
    return templates.TemplateResponse(
        request, "budget/view.html", _grid_context(db, period, pdf=False)
    )


def _parse_form(form) -> dict[tuple[int, int], object]:
    values: dict[tuple[int, int], object] = {}
    for key, raw in form.multi_items():
        if not key.startswith("v_"):
            continue
        try:
            _, mi, ct_id = key.split("_", 2)
            cell_key = (int(mi), int(ct_id))
        except ValueError:
            continue
        values[cell_key] = parse_decimal(raw, default=None)
    return values


@router.post("/{period_id}", name="budget_save")
async def budget_save(request: Request, period_id: int, db: Session = Depends(get_db)):
    period = _load(db, period_id)
    if period is None:
        flash(request, "Periode nicht gefunden.", "error")
        return RedirectResponse(
            request.url_for("budget_index"), status_code=status.HTTP_303_SEE_OTHER
        )
    form = await request.form()
    changed = budget_service.save_overrides(db, period, _parse_form(form))
    db.commit()
    flash(
        request,
        f"Wirtschaftsplan gespeichert ({changed} Zelle{'n' if changed != 1 else ''} angepasst)."
        if changed
        else "Wirtschaftsplan gespeichert (keine Änderung).",
    )
    return RedirectResponse(
        request.url_for("budget_view", period_id=period_id), status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{period_id}/zuruecksetzen", name="budget_reset")
def budget_reset(request: Request, period_id: int, db: Session = Depends(get_db)):
    period = _load(db, period_id)
    if period is not None:
        n = budget_service.reset(db, period)
        db.commit()
        flash(request, f"{n} überschriebene Zelle{'n' if n != 1 else ''} zurückgesetzt.")
    return RedirectResponse(
        request.url_for("budget_view", period_id=period_id), status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/{period_id}/pdf", name="budget_pdf")
def budget_pdf(request: Request, period_id: int, db: Session = Depends(get_db)):
    period = _load(db, period_id)
    if period is None:
        flash(request, "Periode nicht gefunden.", "error")
        return RedirectResponse(
            request.url_for("budget_index"), status_code=status.HTTP_303_SEE_OTHER
        )
    ctx = _grid_context(db, period, pdf=True)
    html = templates.get_template("budget/view.html").render(request=request, **ctx)
    try:
        from app.pdf import render_pdf

        pdf_bytes = render_pdf(html, base_url=str(request.base_url))
    except RuntimeError as exc:
        flash(request, str(exc), "error")
        return RedirectResponse(
            request.url_for("budget_view", period_id=period_id),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return Response(
        pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="Wirtschaftsplan_{period.end_date.year}.pdf"'
        },
    )
