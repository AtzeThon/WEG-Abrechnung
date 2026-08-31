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


def url_has(request, name: str) -> bool:
    """True, wenn zu ``name`` eine Route existiert (für optionale Navigationslinks)."""
    try:
        request.url_for(name)
        return True
    except Exception:
        return False


templates.env.globals["url_has"] = url_has
