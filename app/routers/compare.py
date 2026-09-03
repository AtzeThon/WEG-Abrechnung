"""Jahresvergleich – zwei Wirtschaftsjahre auf Basis des Wirtschaftsplans."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import auth
from app.database import get_db
from app.models import BillingPeriod
from app.services import budget as budget_service
from app.services.periods import previous_period
from app.templating import templates
from app.web import flash

router = APIRouter(
    prefix="/jahresvergleich", tags=["compare"], dependencies=[Depends(auth.require_login)]
)


def _periods(db: Session) -> list[BillingPeriod]:
    return list(db.scalars(select(BillingPeriod).order_by(BillingPeriod.start_date.desc())))


def _pick(db: Session, raw: str | None) -> BillingPeriod | None:
    try:
        pid = int(raw) if raw not in (None, "") else None
    except (TypeError, ValueError):
        return None
    return db.get(BillingPeriod, pid) if pid else None


def _defaults(
    db: Session, periods: list[BillingPeriod], jahr: str | None, vergleich: str | None
) -> tuple[BillingPeriod, BillingPeriod]:
    period = _pick(db, jahr) or periods[0]
    base = _pick(db, vergleich) or previous_period(db, period)
    if base is None or base.id == period.id:
        base = next((p for p in periods if p.id != period.id), period)
    return period, base


def _context(db: Session, period: BillingPeriod, base: BillingPeriod, *, pdf: bool) -> dict:
    grid = budget_service.build_comparison(db, period, base)
    if pdf:
        grid.income_types = [c for c in grid.income_types if grid.totals[c.id].a or grid.totals[c.id].b]
        grid.expense_types = [c for c in grid.expense_types if grid.totals[c.id].a or grid.totals[c.id].b]
    return {
        "grid": grid,
        "period": period,
        "base": base,
        "periods": _periods(db),
        "pdf": pdf,
    }


@router.get("", response_class=HTMLResponse, name="compare_index")
def compare_index(
    request: Request,
    db: Session = Depends(get_db),
    jahr: str | None = None,
    vergleich: str | None = None,
):
    periods = _periods(db)
    if len(periods) < 2:
        return templates.TemplateResponse(
            request, "budget/compare.html", {"periods": periods, "grid": None}
        )
    period, base = _defaults(db, periods, jahr, vergleich)
    return templates.TemplateResponse(
        request, "budget/compare.html", _context(db, period, base, pdf=False)
    )


@router.get("/pdf", name="compare_pdf")
def compare_pdf(
    request: Request,
    db: Session = Depends(get_db),
    jahr: str | None = None,
    vergleich: str | None = None,
):
    periods = _periods(db)
    if len(periods) < 2:
        flash(request, "Für einen Jahresvergleich werden zwei Abrechnungsperioden benötigt.", "error")
        return RedirectResponse(
            request.url_for("compare_index"), status_code=status.HTTP_303_SEE_OTHER
        )
    period, base = _defaults(db, periods, jahr, vergleich)
    ctx = _context(db, period, base, pdf=True)
    html = templates.get_template("budget/compare.html").render(request=request, **ctx)
    try:
        from app.pdf import BUDGET_PRINT_CSS, render_pdf

        pdf_bytes = render_pdf(html, base_url=str(request.base_url), extra_css=BUDGET_PRINT_CSS)
    except RuntimeError as exc:
        flash(request, str(exc), "error")
        return RedirectResponse(
            request.url_for("compare_index").include_query_params(
                jahr=period.id, vergleich=base.id
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    name = f"Jahresvergleich_{period.end_date.year}_{base.end_date.year}.pdf"
    return Response(
        pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
