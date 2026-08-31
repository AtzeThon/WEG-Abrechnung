"""Einzelabrechnung je Eigentümer – Web-Ansicht und PDF (gleiche Vorlage)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app import auth
from app.database import get_db
from app.models import BillingPeriod
from app.models.enums import CostCategory
from app.services.billing import compute_period
from app.templating import templates
from app.web import flash

router = APIRouter(prefix="/abrechnungen", tags=["statements"], dependencies=[Depends(auth.require_login)])

_CATEGORY_LABELS = {c.value: c.label for c in CostCategory}


def _statement_context(db: Session, period: BillingPeriod, code: str, *, pdf: bool) -> dict | None:
    result = compute_period(db, period)
    if code not in result.owners:
        return None
    return {
        "period": period,
        "result": result,
        "owner": result.owner_result(code),
        "cost_groups": _cost_groups(result, code),
        "pdf": pdf,
        "year": period.end_date.year,
    }


def _load_period(db: Session, period_id: int) -> BillingPeriod | None:
    return db.get(BillingPeriod, period_id)


def _cost_groups(result, code: str) -> dict[str, list]:
    groups: dict[str, list] = {}
    for ct in result.cost_lines_for(code):
        groups.setdefault(_CATEGORY_LABELS.get(ct.category, ct.category), []).append(ct)
    return groups


@router.get("/{period_id}/eigentuemer/{code}", response_class=HTMLResponse, name="owner_statement")
def owner_statement(request: Request, period_id: int, code: str, db: Session = Depends(get_db)):
    period = _load_period(db, period_id)
    if period is None:
        flash(request, "Periode nicht gefunden.", "error")
        return RedirectResponse(request.url_for("periods_list"), status_code=status.HTTP_303_SEE_OTHER)
    ctx = _statement_context(db, period, code, pdf=False)
    if ctx is None:
        flash(request, f"Kein Eigentümer „{code}“ in dieser Periode.", "error")
        return RedirectResponse(
            request.url_for("period_overview", period_id=period_id), status_code=status.HTTP_303_SEE_OTHER
        )
    return templates.TemplateResponse(request, "statement.html", ctx)


@router.get("/{period_id}/eigentuemer/{code}/pdf", name="owner_statement_pdf")
def owner_statement_pdf(request: Request, period_id: int, code: str, db: Session = Depends(get_db)):
    period = _load_period(db, period_id)
    if period is None:
        flash(request, "Periode nicht gefunden.", "error")
        return RedirectResponse(request.url_for("periods_list"), status_code=status.HTTP_303_SEE_OTHER)
    ctx = _statement_context(db, period, code, pdf=True)
    if ctx is None:
        flash(request, f"Kein Eigentümer „{code}“ in dieser Periode.", "error")
        return RedirectResponse(
            request.url_for("period_overview", period_id=period_id), status_code=status.HTTP_303_SEE_OTHER
        )

    html = templates.get_template("statement.html").render(request=request, **ctx)
    try:
        pdf_bytes = _render(html, request)
    except RuntimeError as exc:
        flash(request, str(exc), "error")
        return RedirectResponse(
            request.url_for("owner_statement", period_id=period_id, code=code),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return _pdf_response(pdf_bytes, f"Abrechnung_{ctx['year']}_{code}.pdf")


@router.get("/{period_id}/einzelabrechnungen.pdf", name="all_statements_pdf")
def all_statements_pdf(request: Request, period_id: int, db: Session = Depends(get_db)):
    period = _load_period(db, period_id)
    if period is None:
        flash(request, "Periode nicht gefunden.", "error")
        return RedirectResponse(request.url_for("periods_list"), status_code=status.HTTP_303_SEE_OTHER)

    result = compute_period(db, period)
    statements = [
        {"owner": result.owner_result(code), "cost_groups": _cost_groups(result, code)}
        for code in result.owner_order
    ]
    html = templates.get_template("statements_all.html").render(
        request=request,
        period=period,
        result=result,
        year=period.end_date.year,
        statements=statements,
    )
    try:
        pdf_bytes = _render(html, request)
    except RuntimeError as exc:
        flash(request, str(exc), "error")
        return RedirectResponse(
            request.url_for("period_overview", period_id=period_id),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return _pdf_response(pdf_bytes, f"Einzelabrechnungen_{period.end_date.year}.pdf")


def _render(html: str, request: Request) -> bytes:
    from app.pdf import render_pdf

    return render_pdf(html, base_url=str(request.base_url))


def _pdf_response(pdf_bytes: bytes, filename: str) -> Response:
    return Response(
        pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
