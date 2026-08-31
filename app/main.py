"""FastAPI-Anwendung: Zusammenbau von Middleware, Routern und statischen Dateien."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app import auth
from app.config import settings
from app.templating import set_route_names, templates

logger = logging.getLogger("weg")

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(title="WEG-Abrechnung", docs_url=None, redoc_url=None)

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        max_age=settings.session_max_age,
        same_site="lax",
        https_only=settings.secure_cookies,
    )

    if settings.is_secret_key_insecure:
        logger.warning(
            "WEG_SECRET_KEY ist nicht gesetzt – nur fuer lokale Entwicklung zulaessig."
        )

    STATIC_DIR.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    auth.install_auth(app)
    app.include_router(auth.router)

    _register_routers(app)

    set_route_names(
        {r.name for r in app.routes if getattr(r, "name", None)}
    )

    @app.get("/gesundheit", include_in_schema=False)
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse, name="dashboard")
    def dashboard(request: Request, user: str = Depends(auth.require_login)):
        return templates.TemplateResponse(request, "dashboard.html", {"user": user})

    return app


def _register_routers(app: FastAPI) -> None:
    """Feature-Router werden hier registriert, sobald sie existieren."""
    for module_name in ("owners", "accounts", "cost_types", "transactions", "periods", "statements"):
        try:
            module = __import__(f"app.routers.{module_name}", fromlist=["router"])
        except ModuleNotFoundError:
            continue
        router = getattr(module, "router", None)
        if router is not None:
            app.include_router(router)


app = create_app()
