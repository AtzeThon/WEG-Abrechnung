"""Zentrale Jinja2Templates-Instanz mit deutschen Formatfiltern."""

from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.locale import register_filters

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
register_filters(templates.env)
templates.env.globals["APP_NAME"] = "WEG-Abrechnung"

# Namen der tatsächlich registrierten Routen (von app.main befüllt), damit
# Navigationslinks nur erscheinen, wenn der zugehörige Router existiert.
_ROUTE_NAMES: set[str] = set()
templates.env.globals["url_has"] = _ROUTE_NAMES.__contains__


def set_route_names(names) -> None:
    _ROUTE_NAMES.clear()
    _ROUTE_NAMES.update(names)
