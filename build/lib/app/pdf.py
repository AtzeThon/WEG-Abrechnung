"""PDF-Erzeugung der Einzelabrechnung mit WeasyPrint.

Import von ``weasyprint`` erfolgt verzögert, damit die App auch ohne installierte
GTK-Bibliotheken (z. B. unter Windows) startet. Auf dem Raspberry Pi wird
``pip install .[pdf]`` + die System-Pakete installiert (siehe deploy/DEPLOY.md).
"""

from __future__ import annotations

from pathlib import Path

_STATIC = Path(__file__).resolve().parent / "static"

_PRINT_CSS = """
@page { size: A4; margin: 18mm 16mm; }
body { background: #fff; font-size: 11px; }
.no-print { display: none !important; }
header, nav { display: none !important; }
main { max-width: none; padding: 0; margin: 0; }
table { page-break-inside: auto; }
tr { page-break-inside: avoid; }
"""


def render_pdf(html: str, base_url: str) -> bytes:
    try:
        from weasyprint import CSS, HTML
    except (ImportError, OSError) as exc:  # pragma: no cover - umgebungsabhängig
        raise RuntimeError(
            "PDF-Export nicht verfügbar: WeasyPrint bzw. dessen System-Bibliotheken "
            "sind nicht installiert (pip install '.[pdf]' und GTK/Pango, siehe DEPLOY.md)."
        ) from exc

    stylesheets = [CSS(string=_PRINT_CSS)]
    app_css = _STATIC / "app.css"
    if app_css.exists():
        stylesheets.insert(0, CSS(filename=str(app_css)))
    return HTML(string=html, base_url=base_url).write_pdf(stylesheets=stylesheets)
