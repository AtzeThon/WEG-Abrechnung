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
body { font-size: 8pt; line-height: 1.22; }

.no-print, header, nav { display: none !important; }

/* volle Seitenbreite statt zentriertem max-width-Container */
main { max-width: none !important; width: 100% !important; margin: 0 !important; padding: 0 !important; }

h1 { font-size: 12pt; margin: 0 0 1mm; }
h2 { font-size: 8.5pt; margin: 0 0 0.8mm; }
p  { margin: 0 0 0.8mm; }
.text-base { font-size: 8pt !important; }
.text-lg { font-size: 9.5pt !important; }
.text-xl { font-size: 12pt !important; }

/* Abstände fürs Papier zusammenstreichen */
.mb-6 { margin-bottom: 2.5mm !important; }
.mt-6 { margin-top: 2.5mm !important; }
.mt-4 { margin-top: 1.5mm !important; }
.mb-4 { margin-bottom: 1.5mm !important; }
.gap-6 { gap: 2.5mm !important; }

/* Karten flach, kein Schatten */
.card { background: #fff !important; border: 1px solid #cbd5e1; border-radius: 0;
        padding: 1.2mm 2mm !important; }

/* Tabellen kompakt */
table { width: 100% !important; border-collapse: collapse; }
.th, .td { padding: 0.6mm 1.3mm !important; }
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

# Wirtschaftsplan: viele Spalten -> Querformat, sehr kompakt.
BUDGET_PRINT_CSS = """
@page { size: A4 landscape; margin: 8mm 7mm; }

* { box-shadow: none !important; }
html, body { background: #fff !important; color: #0f172a; }
body { font-size: 6pt !important; line-height: 1.15 !important; }
.no-print, header, nav { display: none !important; }

main { max-width: none !important; width: 100% !important; margin: 0 !important; padding: 0 !important; }
h1 { font-size: 11pt !important; margin: 0 0 1mm; }
p  { font-size: 6.5pt !important; margin: 0 0 1mm; }
.card { background: #fff !important; border: 1px solid #cbd5e1; border-radius: 0;
        padding: 1mm 1.5mm !important; margin-bottom: 2mm !important; }
.mb-4 { margin-bottom: 2mm !important; }

table { width: 100% !important; table-layout: fixed; border-collapse: collapse; }
caption { font-size: 6pt !important; text-align: left; padding-bottom: 1mm; }
.th, .td, th, td { padding: 0.4mm 0.7mm !important; vertical-align: bottom; }
th, td, th *, td *, caption { font-size: 6pt !important; line-height: 1.1 !important; }
thead th { white-space: normal !important; overflow-wrap: anywhere; word-break: break-word;
           border-bottom: 0.6pt solid #64748b; }
tbody td, tfoot td { white-space: nowrap; border-bottom: 0.3pt solid #e2e8f0; }
tr, thead, tbody, tfoot, table { page-break-inside: avoid; }
"""


def render_pdf(html: str, base_url: str, extra_css: str | None = None) -> bytes:
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
    if extra_css:
        stylesheets.append(CSS(string=extra_css))
    return HTML(string=html, base_url=base_url).write_pdf(stylesheets=stylesheets)
