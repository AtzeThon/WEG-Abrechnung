"""Zentrale Jinja2Templates-Instanz mit deutschen Formatfiltern."""

from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.config import settings
from app.locale import register_filters

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
register_filters(templates.env)
templates.env.globals["APP_NAME"] = "WEG-Abrechnung"
templates.env.globals["AUTH_ENABLED"] = settings.require_login


def _all_route_names(app) -> set[str]:
    """Alle Routennamen der App – auch aus lazy eingebundenen Routern (FastAPI 0.141)."""
    names: set[str] = set()

    def visit(routes) -> None:
        for route in routes or ():
            if getattr(route, "name", None):
                names.add(route.name)
            original = getattr(route, "original_router", None)
            if original is not None:
                visit(getattr(original, "routes", None))

    visit(getattr(app, "routes", None))
    return names


def url_has(request, name: str) -> bool:
    """True, wenn zu ``name`` eine Route existiert (für optionale Navigationslinks)."""
    cache = getattr(request.app.state, "route_names", None)
    if cache is None:
        cache = _all_route_names(request.app)
        request.app.state.route_names = cache
    return name in cache


templates.env.globals["url_has"] = url_has
