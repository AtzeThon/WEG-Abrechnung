# WEG-Abrechnung – Technische Dokumentation

Für Entwicklung, Betrieb und Wartung. Ergänzt `README.md` (Kurzüberblick) und
`deploy/DEPLOY.md` (Raspberry-Pi-Installation).

---

## 1. Architektur

Serverseitig gerenderte Webanwendung, bewusst leichtgewichtig für den Dauerbetrieb
auf einem Raspberry Pi.

| Schicht | Technik |
|---|---|
| Web / HTTP | **FastAPI** (ASGI), **Uvicorn** |
| Templates | **Jinja2**, Interaktivität über **htmx**; CSS mit **Tailwind** (Standalone-CLI, kein Node-Build – `app/static/app.css` ist eingecheckt) |
| ORM / DB | **SQLAlchemy 2.0**, **SQLite** (WAL-Modus), Migrationen mit **Alembic** |
| PDF | **WeasyPrint** (optionale Abhängigkeit `.[pdf]`, lazy import) |
| Rechenkern | reines Python (`decimal.Decimal`), keine Fremdbibliotheken |
| CSV-Parser | nur `csv` aus der Standardbibliothek |
| Locale | **Babel** (`de_DE`) für Zahl-/Datums-/Währungsformat |
| Auth | optionaler Verwalter-Login, `bcrypt` + signiertes Session-Cookie |

Leitprinzip: **fachliche Logik ist DB-/Web-frei** und liegt in reinen Modulen
(`app/allocation/`, `app/imports/`, `app/formats.py`), die isoliert testbar sind.
Die Router sind dünne Adapter (ORM ↔ reine Eingaben ↔ Templates).

---

## 2. Verzeichnisstruktur

```
app/
  main.py            App-Factory, Middleware, Router-Registrierung
  config.py          Einstellungen (pydantic-settings, Prefix WEG_)
  database.py        Engine, SessionLocal, Base, get_db, SQLite-PRAGMAs
  auth.py            Login/Logout, require_login-Dependency
  templating.py      Jinja-Instanz, url_has(), AUTH_ENABLED
  locale.py          Jinja-Filter euro/dezimal/prozent/datum
  formats.py         parse_german_decimal / parse_german_date  (rein)
  web.py             Flash-Nachrichten, Formular-Parser (Wrapper um formats)
  pdf.py             WeasyPrint-Rendering + Druck-CSS

  models/            SQLAlchemy-Modelle (+ enums.py)
  allocation/        Berechnungs-Engine (rein): types, strategies, engine
  imports/           CSV-Parser (rein): types, parser
  services/          ORM-Adapter: billing.py, imports.py, periods.py, transfers.py, budget.py
  routers/           HTTP-Endpunkte je Bereich
  templates/         Jinja-Templates (base.html + je Bereich)
  static/            app.css (Tailwind-Output), htmx.min.js

migrations/          Alembic (env.py + versions/)
scripts/seed_2026.py  Demo-/Testdatensatz (anonymisiert)
tests/              pytest
deploy/            systemd-Unit, Caddyfile, backup.sh, DEPLOY.md
tailwind/          input.css, tailwind.config.js, tailwindcss(.exe) (nicht eingecheckt)
docs/              dieses Verzeichnis
```

---

## 3. Datenmodell

Tabellen (SQLite). Geldbeträge `NUMERIC(12,2)`, MEA `NUMERIC(12,4)`. Enums als
Strings (`Enum(..., native_enum=False)`).

| Tabelle | Zweck | Wichtige Spalten |
|---|---|---|
| `users` | Verwalter-Login | `username`, `password_hash` (bcrypt) |
| `owners` | Eigentümer | `code`, `name`, `email`, `mea`, `active`, `sort_order` |
| `accounts` | Bankkonten | `name`, `type` (`giro`/`ruecklage`), `opening_balance(_date)` |
| `cost_types` | Kostenarten | `name` (unique), `category`, `default_supplier`, `kind`, `allocation_strategy`, `proportional_to_id` |
| `transactions` | Buchungen | `account_id`, `booking_date`, `payee`, `cost_type_id`, `owner_id?`, `amount`, `note`, `source` (`manuell`/`csv_import`), `import_row_id?` |
| `billing_periods` | Abrechnungsperioden | `label`, `start_date`, `end_date`, `status` (`draft`/`final`), `reserve_opening_balance`, `finalized_at?` |
| `period_opening_balances` | Saldovortrag Hausgeld je Eigentümer/Periode | `period_id`, `owner_id`, `hausgeld_carryover` (unique je Paar) |
| `allocation_overrides` | Zähler-Direkteingaben je Kostenart×Eigentümer×Periode | `period_id`, `cost_type_id`, `owner_id`, `amount` |
| `budget_entries` | Wirtschaftsplan: manuell überschriebene Zelle | `period_id`, `month_index` (0 = erster Monat), `cost_type_id`, `amount` (unique je Tripel) |
| `import_profiles` | gemerkte CSV-Struktur | `signature` (unique, Hash der Kopfzeile), `delimiter`, `encoding`, `date_format`, `header_row`, `amount_mode`, `mapping` (JSON) |
| `import_batches` | hochgeladener Kontoauszug | `account_id`, `filename`, `raw_content` (BLOB), `profile_id?`, `status` (`entwurf`/`importiert`/`verworfen`) |
| `import_rows` | geparste CSV-Zeile + Zuordnung | `batch_id`, `line_no`, `booking_date?`, `payee`, `purpose`, `amount?`, `raw` (JSON), `parse_error`, `is_duplicate`, `include`, `cost_type_id?`, `owner_id?` |

Enums (`app/models/enums.py`): `AccountType`, `CostCategory`, `CostKind`
(inkl. `umbuchung` = neutrale Gegenbuchung, von der Engine ignoriert),
`AllocationStrategy`, `PeriodStatus`, `TransactionSource`, `ImportBatchStatus`.
`OWNER_REQUIRED_KINDS = {hausgeld, erstattung, sonderumlage}`. Der `kind`-Wert wird
als Enum-**Name** (Großbuchstaben) gespeichert; neue Werte brauchen keine Migration
(VARCHAR ohne CHECK).

`transactions.import_row_id → import_rows.id` und die (view-only) Beziehung
`ImportRow.transaction` bilden die Rückverfolgung; die FK `import_rows.transaction_id`
wurde bewusst **weggelassen**, um einen Zyklus zu vermeiden.

---

## 4. Berechnungs-Engine (`app/allocation/`)

Rein, ohne DB/Web. Öffentlich: `compute_billing(period, owners, cost_types,
transactions, overrides) -> BillingResult`.

**Eingaben** (`types.py`, `@dataclass(frozen=True)`): `PeriodInput`, `OwnerInput`,
`CostTypeInput`, `TxnInput`, `OverrideInput` – fachliche Typen/Strategien als
Strings, damit die Engine nicht von den ORM-Enums abhängt.

**Ablauf** (`engine.py`):

1. Buchungen des Zeitraums `[start, end]` je Kostenart summieren → Ist-Kosten
   (Ausgaben werden zu positiven Kosten: `-Σ amount`).
2. Je umlagefähiger Kostenart die **Strategie** anwenden → Anteil je Eigentümer.
   Kostenarten werden **topologisch** sortiert (für `proportional`).
3. Anteile je Eigentümer summieren → **Kostenanteil**.
4. `hausgeld`-Buchungen je Eigentümer → **geleistetes Hausgeld**.
5. **Guthaben/Nachzahlung** = Hausgeld − Kostenanteil.
6. **Endsaldo Hausgeld** = Saldovortrag + Sonderumlage − Investitionsanteil (MEA)
   + Guthaben/Nachzahlung (+ Erstattung = 0) **− Rücklagen-Zuführung + Rücklagen-Entnahme**.
7. **Endsaldo Rücklage** = Anfangssaldo·MEA + Zuführung − Entnahme (eigentümer­bezogen,
   wenn an der Buchung ein Eigentümer steht, sonst nach MEA).
8. **Saldo gesamt** = Endsaldo Hausgeld + Endsaldo Rücklage. Eine reine
   Rücklagenbewegung verschiebt nur zwischen 6 und 7 (Summe bleibt gleich).

**Bewusst nicht umgesetzt:** Erstattung/Nachzahlung fließt nicht in den Endsaldo
(Feld/Typ existieren, Betrag wird 0 gesetzt).

### Umlageschlüssel-Strategien (`strategies.py`)

Registry über `@register("name")`; `AllocationContext` liefert `actual_total`,
`mea_fraction`, `overrides`, `resolved` (bereits berechnete Kostenarten).

| Name | Verhalten |
|---|---|
| `mea` | Anteil = Ist-Kosten × MEA/ΣMEA |
| `zaehler` | Anteil = manueller Override je Eigentümer; WEG-Gesamt = Σ Overrides |
| `vorauszahlung` | Anteil = 0 (reine Abschlags-/Vorauszahlung) |
| `proportional` | verteilt `actual_total` im Verhältnis einer anderen, bereits berechneten Kostenart; Fallback `mea` |

**Neue Strategie hinzufügen:** Funktion in `strategies.py` mit `@register("xyz")`
dekorieren; in `AllocationStrategy` (enums) ergänzen; sie steht dann in der
Kostenart-UI zur Auswahl. Kein Eingriff in `engine.py` nötig (Topo-Sort über
`depends_on()`).

### Adapter (`app/services/billing.py`)

`compute_period(db, period) -> BillingResult` baut die `*Input`-Objekte aus dem
ORM (alle Buchungen im Zeitraum, **kontenübergreifend** – das Konto ist für die
Berechnung irrelevant) und ruft `compute_billing`.

`effective_reserve_opening(db, period) -> (Decimal, str)`: Rücklagen-Anfangssaldo
der Periode. Vorrang hat `period.reserve_opening_balance`; ist er 0, wird der
Stand des Rücklagenkontos zu Periodenbeginn genommen
(`Account.opening_balance + Σ Buchungen vor `start_date``). Der zweite Rückgabewert
ist eine Herkunftsbeschreibung für die Anzeige.

---

## 5. CSV-Import (`app/imports/` + `app/services/imports.py`)

**Parser** (`parser.py`, rein):

- `sniff(raw: bytes)` → `(text, CsvDialect)` – Encoding-Kette
  `utf-8-sig → utf-8 → cp1252 → latin-1`; Trennzeichen per `csv.Sniffer` mit
  Fallback (Zeichen zählen); Kopfzeile = Zeile mit den meisten bekannten Keywords.
- `detect_mapping(headers)` → `ColumnMapping` – umlaut-/case-normalisierte
  Keyword-Erkennung mit Ausschlusslisten (z. B. „Betrag Soll" vs. „Betrag" vs.
  „Soll/Haben-Kennzeichen"). Optional `category`- und `owner`-Spalte.
- `parse_rows(text, dialect, mapping)` → `list[ParsedRow]` – deutsches Zahl-/Datums­
  parsing über `app/formats.py`, Fehler je Zeile, Leerzeilen übersprungen
  (`line_no` bleibt korrekt), unbekannte Zusatzspalten landen in `raw`.
- `header_signature(headers, delimiter)` → 32-Hex – Fingerabdruck für `ImportProfile`.

**Service** (`services/imports.py`):

- `parse_batch(db, batch, profile)` – parst und befüllt `batch.rows`; leitet aus
  einer Kategorie-Spalte per Namensabgleich eine Kostenart ab, aus einer
  Eigentümer-Spalte das Kürzel (nur bei eigentümerbezogenem Typ).
- `mark_duplicates(db, batch)` – Duplikat = vorhandene `Transaction` mit gleichem
  `account_id` + `booking_date` + `amount` + normalisiertem `note == purpose`.
- `suggest(db, account_id, payee, purpose)` – Kostenart/Eigentümer aus der
  Historie: exakter `payee`-Match, dann Teilstring (ab 4 Zeichen); Vorschlag, wenn
  eine Zuordnung dominiert (> 80 % oder eindeutig).
- `commit_batch(db, batch)` – legt `Transaction`-Datensätze an
  (`source=csv_import`, `import_row_id`), setzt Batch auf `importiert`.

**Wizard-Status** liegt in `ImportBatch.status` + `ImportRow`-Feldern; die
Rohdatei bleibt in `raw_content` für erneutes Parsen bei Mapping-Änderung.

---

## 6. Perioden-Workflow (`app/services/periods.py`)

- `locked_period_for_date(db, when)` – finale Periode, in deren Zeitraum ein Datum
  fällt. Die Transaktions- und Import-Router lehnen Anlegen/Ändern/Löschen ab,
  wenn `booking_date` (alt oder neu) in einer solchen Periode liegt.
- `previous_period(db, period)` / `carry_forward_balances(db, period)` – übernimmt
  `reserve_endsaldo_total` und je Eigentümer `hausgeld_endsaldo` der Vorperiode
  als Anfangswerte.
- `set_status(db, period, final=...)` – Status + `finalized_at`.

`app/services/transfers.py::record_transfer(...)` – Umbuchung zwischen Konten:
legt zwei Buchungen an (Rücklagenkonto-Bein Typ `ruecklage`, anderes Bein Typ
`umbuchung`). Die benötigten Kostenarten werden bei Bedarf automatisch angelegt.

---

## 6a. Wirtschaftsplan (`app/services/budget.py`, `routers/budget.py`)

Reiner Aufbau eines Monats-Rasters je Periode; ändert keine Buchungen.

- `month_windows(period)` – Kalendermonate von `start_date` bis `end_date`,
  Rand­monate auf die Periodengrenzen geklammert, Label über Babel (`"LLLL y"`).
- `build_grid(db, period) -> BudgetGrid` – Dataclasses `BudgetCell` /
  `BudgetMonth` / `BudgetGrid` (keine ORM-Objekte im Template).
  - Spalten: aktive Kostenarten, `kind ∈ {hausgeld, sonderumlage}` als Einnahme,
    `kind ∈ {betriebskosten, investition, erstattung}` als Ausgabe
    (`ruecklage`/`umbuchung` bleiben außen vor), sortiert nach `sort_order, name`.
  - Zellwert `effective = manual ?? ist ?? vorschlag ?? 0`; `source` ∈
    `manuell | ist | prognose | leer`. `ist` = Summe der Buchungen dieser
    Kostenart im Monat (Ausgaben als positiver Betrag), `vorschlag` = dieselbe
    Summe im gleichen Monatsindex von `previous_period(db, period)`.
  - **Anfangssaldo** = Σ `account_balance_before(db, konto, start_date)` über
    alle Konten mit `type == GIRO`. Laufender Saldo = Vormonatssaldo + Differenz.
- `save_overrides(db, period, {(month_index, cost_type_id): Decimal|None})` –
  Upsert nur bei Abweichung vom Default (`ist ?? vorschlag ?? 0`); leerer/gleicher
  Wert löscht einen vorhandenen `BudgetEntry`.
- `reset(db, period)` – löscht alle `BudgetEntry` der Periode.

Router `prefix="/wirtschaftsplan"`: `budget_index` (Perioden-Auswahl, Redirect
bei genau einer), `budget_view` (Grid als `<form>`), `budget_save`,
`budget_reset`, `budget_pdf` (gleiche Vorlage, `pdf=1`; 303-Fallback ohne
WeasyPrint). Registrierung in `app/main.py::_register_routers`. Das Raster ist
`table-fixed` mit einheitlich schmalen Spalten; die Überschriften brechen um.
Für das PDF übergibt die Route `pdf.BUDGET_PRINT_CSS` an `render_pdf(..., extra_css=)`
(A4 quer, 6 pt, Tabelle auf volle Seitenbreite) und blendet Kostenart-Spalten
ohne Wert aus (`_grid_context`, nur bei `pdf=True`).
Jinja-Filter in `app/locale.py`: `betrag` für die Eingabefelder (zwei
Nachkommastellen, kein Tausendertrenner), `geld` für die Anzeigezahlen im
Raster (Tausendertrenner, zwei Nachkommastellen, kein €-Symbol).

---

## 7. Konfiguration

Umgebungsvariablen, Prefix `WEG_` (optional `.env` im Arbeitsverzeichnis).

| Variable | Default | Zweck |
|---|---|---|
| `WEG_DATABASE_PATH` | `data/weg.db` | Pfad zur SQLite-Datei |
| `WEG_REQUIRE_LOGIN` | `false` | Verwalter-Login erzwingen |
| `WEG_SECRET_KEY` | Dev-Platzhalter | Session-Signatur (Pflicht bei aktivem Login) |
| `WEG_SECURE_COOKIES` | `false` | Session-Cookie nur über HTTPS |
| `WEG_LOCALE` | `de_DE` | Zahl-/Datumsformat |
| `WEG_DEBUG` | `false` | SQL-Echo |

CLI (`python -m app.cli`): `initdb`, `create-admin <name> [--password …]`.

---

## 8. Datenbank & Migrationen

- Schema-Änderung: Modell anpassen → `alembic revision --autogenerate -m "…"` →
  generierte Datei prüfen (SQLite braucht `render_as_batch=True`, ist in
  `migrations/env.py` gesetzt; unbenannte Constraints bekommen einen Namen).
- `alembic upgrade head` / `alembic downgrade -1`.
- `migrations/env.py` bezieht Engine und Metadaten aus der App
  (`WEG_DATABASE_PATH` gilt also auch für Alembic).
- Bisherige Revisionen: `f5b2ccfd55a5` (Initialschema), `50dc58878cdf` (CSV-Import),
  `0b2add809501` (Wirtschaftsplan: `budget_entries`).

---

## 9. Betrieb

### Start (Entwicklung)

```
python -m venv .venv
.venv/bin/pip install -e ".[dev]"        # + ".[pdf]" für PDF
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
```

### Produktion (Raspberry Pi)

Siehe `deploy/DEPLOY.md`. Kurz: systemd-Dienst `weg-abrechnung.service` startet
Uvicorn auf `127.0.0.1:8000`, `ExecStartPre` führt `alembic upgrade head` aus.
Zugriff über Tailscale (`tailscale serve 8000`) oder Caddy als Reverse-Proxy.

**Update:**
```
cd <projekt> && git pull
.venv/bin/pip install -e ".[pdf]"        # nur wenn Abhängigkeiten geändert
sudo systemctl restart weg-abrechnung    # führt die Migration selbst aus
```

### Backup / Restore

`deploy/backup.sh` (per `weg-backup.timer` täglich): konsistentes
`sqlite3 … ".backup"` + gzip, 30-Tage-Rotation nach `backups/`.
Restore: Dienst stoppen, `gunzip -c backups/… > data/weg.db`, Dienst starten.
Zusätzlich das Backup-Verzeichnis regelmäßig auf ein anderes Gerät spiegeln.

### Logs

`journalctl -u weg-abrechnung -e` (bzw. `-f`).

### Frontend-CSS neu bauen (nur bei Template-Änderungen)

```
tailwind/tailwindcss -c tailwind/tailwind.config.js -i tailwind/input.css -o app/static/app.css --minify
```

Das Ergebnis `app/static/app.css` **einchecken**. Für die PDF gilt zusätzlich das
Druck-CSS in `app/pdf.py::_PRINT_CSS`.

---

## 10. Tests

```
.venv/bin/pytest            # ~115 Tests, < 3 s
.venv/bin/ruff check .
```

| Datei | Prüft |
|---|---|
| `test_engine.py` | Engine gegen die reale Beispiel-Abrechnung 2026 (cent-genau); Rücklagen-Umbuchung |
| `test_strategies.py` | jede Umlage-Strategie isoliert |
| `test_billing_service.py` | DB → `compute_period` reproduziert die Sollwerte; `periods_update` |
| `test_formats.py` | deutsches Zahl-/Datumsparsing inkl. Edge Cases |
| `test_csv_parser.py` | `sniff` / `detect_mapping` / `parse_rows` gegen Fixtures (`tests/fixtures/bank_csv/`) |
| `test_imports_flow.py` | Upload → Mapping → Prüfen → Buchen; Duplikat-Zweitimport; Historien-Vorschlag; Kategorie-/Eigentümer-Spalte |
| `test_period_workflow.py` | Abschluss-Sperre; Salden aus Vorperiode |
| `test_budget.py` | Wirtschaftsplan: Monatsfenster, Ist vor Prognose, Anfangssaldo (nur Giro), Saldo/Summen, Speichern/Zurücksetzen (Service + Routen) |
| `test_transfer.py` | Umbuchung zwischen Konten (zwei Beine, Auto-Kostenarten) |
| `test_statements.py` | Einzelabrechnung Web + PDF-Route + „Alle als PDF" |
| `test_transactions.py` / `test_crud.py` / `test_smoke.py` | CRUD, Filter (auch leere Query-Parameter), Auth |

`tests/conftest.py`: In-Memory-SQLite je Test, `client`-Fixture (offen), Fixture
`login_required` für Login-Tests.

---

## 11. Bekannte Grenzen / geplante Erweiterungen

- **Erstattung/Nachzahlung** wird nicht automatisch verrechnet (bewusst; Plumbing
  vorhanden). Workaround: in den Saldovortrag einrechnen.
- **Umlageschlüssel `proportional`** ist in der Engine implementiert und getestet,
  aber in der Kostenart-UI noch nicht speziell erklärt.
- **E-Mail-Versand** der PDF: nicht umgesetzt; `app/pdf.py` liefert Bytes, ein
  SMTP-Service ließe sich andocken.
- **Eigentümer-Login** mit Zugriff nur auf die eigene Abrechnung: nicht umgesetzt
  (`User`-Modell vorhanden, keine Owner-Verknüpfung).
- **Mehrjahresvergleich / Diagramme**: nicht umgesetzt.
- **Wirtschaftsplan**: Prognose nur aus der unmittelbaren Vorperiode (kein
  Mittelwert mehrerer Jahre, keine Indexierung/Steigerungssätze).
- **Plausibilitätswarnungen** in der Perioden-Übersicht (z. B. „Investitions-
  Kostenart mit Einzahlungen") wären hilfreich, fehlen noch.
- Der lazy Router von FastAPI ≥ 0.115 liefert `app.routes` als `_IncludedRouter`-
  Platzhalter; `templating.url_has()` löst Routennamen über `.original_router` auf
  und cached sie in `app.state.route_names`.
