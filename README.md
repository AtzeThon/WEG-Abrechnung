# WEG-Abrechnung

Selbst gehostete Web­anwendung für die **Hausgeld- und Betriebskosten­abrechnung**
einer kleinen Wohnungs­eigentümer­gemeinschaft (4 Einheiten). Ersetzt die bisher in
Excel geführte Jahresabrechnung. Läuft dauerhaft auf einem Raspberry Pi.

## Technik

| Bereich    | Wahl |
|------------|------|
| Backend    | Python 3.11+, FastAPI, SQLAlchemy 2, Alembic |
| Datenbank  | SQLite (eine Datei, WAL-Modus) |
| Frontend   | Server-Rendering mit Jinja2 + htmx, Tailwind CSS (Standalone-CLI, kein Node-Build) |
| PDF        | WeasyPrint (gleiche HTML/CSS-Vorlage wie die Web-Ansicht) |
| Auth       | ein Verwalter-Login (signiertes Session-Cookie) |
| Locale     | Deutsch (`de_DE`) – Komma als Dezimaltrenner, `TT.MM.JJJJ`, Euro |

## Entwicklung

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"          # Windows
# .venv/bin/pip install -e ".[dev]"            # Linux/macOS

cp .env.example .env                            # WEG_SECRET_KEY setzen

.venv/Scripts/alembic upgrade head              # Schema anlegen
.venv/Scripts/python -m app.cli create-admin admin

.venv/Scripts/uvicorn app.main:app --reload     # http://127.0.0.1:8000
```

### Tests

```bash
.venv/Scripts/python -m pytest
```

Die Berechnungs-Engine (`app/allocation/`) ist rein (ohne DB/UI) und wird in
`tests/test_engine.py` gegen eine reale Beispiel-Abrechnung (Wirtschaftsjahr
01.08.2025–31.07.2026) validiert.

### Frontend-CSS neu bauen (nur bei Template-Änderungen nötig)

```bash
tailwind/tailwindcss.exe -c tailwind/tailwind.config.js -i tailwind/input.css -o app/static/app.css --minify
```

Die fertige `app/static/app.css` ist eingecheckt; die Binärdatei `tailwindcss.exe`
nicht (siehe `.gitignore`). Download: <https://github.com/tailwindlabs/tailwindcss/releases>

## Deployment

Siehe [`deploy/DEPLOY.md`](deploy/DEPLOY.md) – systemd-Service für Uvicorn, Caddy als
Reverse-Proxy mit automatischem HTTPS, tägliches SQLite-Backup. Für den Fernzugriff
wird Tailscale empfohlen (keine offene Portfreigabe).

## Fachliche Logik

Die vollständige Berechnungskette (Ist-Kosten → Umlageschlüssel → Kostenanteil →
Hausgeld-Endsaldo → Rücklage → Saldo gesamt) ist in
[`app/allocation/engine.py`](app/allocation/engine.py) dokumentiert. Umlageschlüssel
sind austauschbare Strategien (`app/allocation/strategies.py`): `mea`, `zaehler`,
`vorauszahlung`, `proportional`.
