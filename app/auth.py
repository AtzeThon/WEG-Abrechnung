"""Einfacher Verwalter-Login über signiertes Session-Cookie."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.templating import templates

router = APIRouter(tags=["auth"])

SESSION_USER_KEY = "user"
ANONYMOUS = "Verwaltung"


def current_user(request: Request) -> str | None:
    return request.session.get(SESSION_USER_KEY)


def require_login(request: Request) -> str:
    """Dependency für geschützte Routen.

    Ist ``WEG_REQUIRE_LOGIN`` nicht gesetzt (Standard), ist die Anwendung offen
    zugänglich. Andernfalls wird ohne gültige Session per 303 zur Loginseite
    weitergeleitet.
    """
    if not settings.require_login:
        return current_user(request) or ANONYMOUS
    user = current_user(request)
    if not user:
        raise _RedirectToLogin(request.url.path)
    return user


class _RedirectToLogin(Exception):
    def __init__(self, next_path: str) -> None:
        self.next_path = next_path


def install_auth(app) -> None:
    """Exception-Handler registrieren (Import-Zyklus vermeiden)."""

    @app.exception_handler(_RedirectToLogin)
    async def _handle(request: Request, exc: _RedirectToLogin):  # noqa: ANN202
        url = request.url_for("login_form").include_query_params(next=exc.next_path)
        return RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/login", response_class=HTMLResponse, name="login_form")
def login_form(request: Request, next: str = "/"):
    if not settings.require_login or current_user(request):
        return RedirectResponse(next or "/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request, "auth/login.html", {"next": next, "error": None})


@router.post("/login", name="login_submit")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
    db: Session = Depends(get_db),
):
    user = db.scalar(select(User).where(User.username == username.strip()))
    if user is None or not user.verify_password(password):
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {"next": next, "error": "Benutzername oder Passwort falsch."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    request.session[SESSION_USER_KEY] = user.username
    return RedirectResponse(next or "/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/logout", name="logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(
        request.url_for("login_form"), status_code=status.HTTP_303_SEE_OTHER
    )
