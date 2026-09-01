"""PDF-Erzeugung der Einzelabrechnung mit WeasyPrint.

Import von ``weasyprint`` erfolgt verzögert, damit die App auch ohne installierte
GTK-Bibliotheken (z. B. unter Windows) startet. Auf dem Raspberry Pi wird
``pip install .[pdf]`` + die System-Pakete installiert (siehe deploy/DEPLOY.md).
"""

from __future__ import annotations

from pathlib import Path

_STATIC = Path(__file__).resolve().parent / "static"

_PRINT_CSS = """
@page { size: A4; margin: 14mm 13mm; }

* { box-shadow: none !important; }
html, body { background: #fff !important; color: #0f172a; }
body { font-size: 9pt; line-height: 1.28; }

.no-print, header, nav { display: none !important; }

/* volle Seitenbreite statt zentriertem max-width-Container */
main { max-width: none !important; width: 100% !important; margin: 0 !important; padding: 0 !important; }

h1 { font-size: 13pt; margin: 0 0 1mm; }
h2 { font-size: 9.5pt; margin: 0 0 1mm; }
p  { margin: 0 0 1mm; }

/* Abstände fürs Papier zusammenstreichen */
.mb-6 { margin-bottom: 3mm !important; }
.mt-6 { margin-top: 3mm !important; }
.mt-4 { margin-top: 2mm !important; }
.gap-6 { gap: 3mm !important; }

/* Karten flach, kein Schatten */
.card { background: #fff !important; border: 1px solid #cbd5e1; border-radius: 0;
        padding: 1.5mm 2.5mm !important; }

/* Tabellen kompakt */
table { width: 100% !important; border-collapse: collapse; }
.th, .td { padding: 0.8mm 1.6mm !important; }
.th { border-bottom: 0.6pt solid #64748b; }
.td { border-bottom: 0.4pt solid #e2e8f0; }
td.text-right, th.text-right { white-space: nowrap; }

/* die beiden Konten-Kästen nebeneinander */
.grid { display: grid !important; grid-template-columns: 1fr 1fr; gap: 3mm !important; }

/* nichts unschön umbrechen */
table, section, .card { page-break-inside: avoid; }
h1, h2 { page-break-after: avoid; }
.statement-page { page-break-before: always; }
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
