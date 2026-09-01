# WEG-Abrechnung – Anwenderhandbuch

Stand: siehe Git-Historie. Diese Anleitung beschreibt die Bedienung der
Webanwendung für die Jahresabrechnung einer kleinen Wohnungseigentümer­gemeinschaft.

---

## 1. Grundbegriffe

| Begriff | Bedeutung in der App |
|---|---|
| **Eigentümer** | Eine Einheit der WEG (E1 … E4) mit **Miteigentumsanteil (MEA)**. Die MEA aller Eigentümer sollen sich zu **1000** summieren. |
| **Konto** | Ein Bankkonto der WEG. Typ **Girokonto** (laufende Kosten, Hausgeld) oder **Rücklagenkonto**. Das Konto dient v. a. dem Abgleich mit dem Bankauszug – für die *Berechnung* zählt nur die Kostenart. |
| **Kostenart** | Die Bezeichnung einer Buchung (z. B. „Gebäudeversicherung"). Jede Kostenart hat einen **fachlichen Typ** und – bei umlagefähigen Kosten – einen **Umlageschlüssel**. |
| **Fachlicher Typ** | Steuert, *wie* eine Buchung in die Abrechnung einfließt: `Betriebskosten`, `Hausgeld`, `Sonderumlage`, `Investition`, `Rücklage`, `Erstattung/Nachzahlung`. |
| **Umlageschlüssel** | Bei Betriebskosten: `MEA` (nach Anteilen), `Zähler` (Direkteingabe je Eigentümer), `Vorauszahlung` (nicht umlegen), `Proportional`. |
| **Abrechnungsperiode / Wirtschaftsjahr** | Der Zeitraum, für den abgerechnet wird (z. B. 01.08.2025 – 31.07.2026). |
| **Buchung** | Eine Kontobewegung: Datum, Zahlungspartner, Kostenart, optional Eigentümer, Betrag (**+** = Einzahlung, **–** = Ausgabe), Notiz. |

---

## 2. Anmeldung

Standardmäßig ist **kein Login** aktiv – die App öffnet direkt (gedacht für den
Betrieb im vertrauten Netz / hinter Tailscale). Ist ein Verwalter-Login
eingerichtet (`WEG_REQUIRE_LOGIN=true`), meldest du dich mit Benutzername und
Passwort an.

---

## 3. Stammdaten pflegen

Menü oben: **Eigentümer · Konten · Kostenarten**.

### 3.1 Eigentümer

Kürzel (E1 …), Name, E-Mail, **MEA**. Die Liste zeigt unten die MEA-Summe und
warnt, wenn sie nicht 1000 ergibt.

### 3.2 Konten

Name, Typ (Girokonto / Rücklagenkonto), **Anfangssaldo** und Datum. Über
**Kontoauszug** siehst du je Konto alle Buchungen mit laufendem Saldo – ideal
zum Abgleich mit dem echten Bankauszug.

### 3.3 Kostenarten

Für jede Kostenart:

- **Kategorie** – nur für die Gliederung in der Einzelabrechnung
  (Heizen/Wasser/Betrieb, Versicherungen, Gebühren und Abgaben,
  Wartung und Dienstleistungen, Verwaltung).
- **Standard-Lieferant** – wird in der Einzelabrechnung angezeigt.
- **Fachlicher Typ** – siehe Tabelle unten. **Wichtigste Fehlerquelle!**
- **Umlageschlüssel** – nur bei Typ *Betriebskosten* relevant.

| Fachlicher Typ | Wofür | Wirkung in der Abrechnung |
|---|---|---|
| **Betriebskosten** | Umlagefähige laufende Kosten (Versicherung, Grundbesitzabgaben, Hausmeister, Gartenpflege, Bankgebühren, Heizung …) | Wird nach dem Umlageschlüssel auf die Eigentümer verteilt → *Kostenanteil*. |
| **Hausgeld** | Monatliche Hausgeld-Einzahlungen der Eigentümer | Summe je Eigentümer = *geleistetes Hausgeld*. **Eigentümer ist Pflicht.** |
| **Sonderumlage** | Von den Eigentümern beschlossene Sonderzahlung (z. B. zur Finanzierung einer Investition) | Einzahlung je Eigentümer, erhöht dessen *Endsaldo Hausgeld*. **Eigentümer ist Pflicht.** |
| **Investition** | Investive Ausgabe (z. B. Heizungseinbau) | Gesamtbetrag wird **nach MEA** verteilt und vom *Endsaldo Hausgeld* abgezogen. |
| **Rücklage** | Zuführung zur / Entnahme aus der Instandhaltungsrücklage | Positiv = Zuführung, negativ = Entnahme. Verschiebt zwischen *Endsaldo Rücklage* und *Endsaldo Hausgeld* (siehe 6.3). |
| **Erstattung/Nachzahlung** | Ausgleich aus der Vorjahresabrechnung | **Wird derzeit nicht automatisch verrechnet** – siehe 6.4. |

> **Merke:** „Sonderzahlung Heizung" (was die Eigentümer *einzahlen*) ist Typ
> **Sonderumlage**. „Heizungseinbau" (was an die Firma *ausgezahlt* wird) ist Typ
> **Investition**. Das sind zwei getrennte Kostenarten. Verwechslung führt zu
> Abweichungen von wenigen Euro je Eigentümer bei stimmiger Gesamtsumme.

---

## 4. Buchungen erfassen

Menü **Buchungen**.

### 4.1 Einzeln erfassen

**+ Buchung** → Konto, Datum, Zahlungspartner, Kostenart (Dropdown; über
*„+ neue Kostenart"* lässt sich direkt eine anlegen), Eigentümer (nur bei
eigentümerbezogenen Typen), Betrag, Notiz. Mit **Speichern & nächste** bleibt
das Formular für die nächste Buchung offen.

Vorzeichen: **Einzahlung positiv**, **Ausgabe negativ** (z. B. `-1.234,56`).
Deutsches Zahlenformat mit Komma und Punkt wird erkannt.

### 4.2 Filtern und Sortieren

Über der Liste: Filter nach Konto, Kostenart, Eigentümer, Zeitraum und
Volltext (Zahlungspartner/Notiz). Klick auf eine Spaltenüberschrift sortiert.
Importierte Buchungen tragen ein kleines **CSV**-Kennzeichen am Datum.

### 4.3 CSV-Import von Kontoauszügen

Menü **Import**.

1. **Hochladen** – CSV-Datei wählen und Zielkonto angeben. Zeichensatz
   (`UTF-8` / `Windows-1252`, auch mit BOM), Trennzeichen (`;` `,` Tab `|`) und
   Vorspann­zeilen werden automatisch erkannt.
2. **Spalten zuordnen** – nur beim ersten Import einer Bank. Ordne die Spalten
   den Feldern *Datum, Zahlungspartner, Verwendungszweck, Betrag* zu (drei
   Betragsvarianten: eine Spalte mit Vorzeichen / getrennte Soll-Haben-Spalten /
   Betrag + S/H-Kennzeichen). Enthält die CSV bereits **Kategorie-** und
   **Eigentümer-Spalten**, kannst du diese als Vorschlag mappen. Das Mapping wird
   pro CSV-Struktur als **Profil** gespeichert und beim nächsten Mal automatisch
   erkannt.
3. **Prüfen** – jede Zeile bekommt eine **Kostenart** (bei Hausgeld / Erstattung /
   Sonderumlage zusätzlich einen **Eigentümer**). Für bekannte Zahlungspartner
   wird eine Kostenart aus der Historie vorgeschlagen (blau markiert,
   überschreibbar). Bereits vorhandene Buchungen werden als **wahrscheinliches
   Duplikat** markiert und ausgeschlossen.
4. **Buchen** – erst nach Bestätigung entstehen die Buchungen. Der Button ist
   gesperrt, solange **nicht jede einbezogene Zeile** vollständig zugeordnet ist.

Zeilen, die keine WEG-Kostenart sind (interne Umbuchungen, „man. Buchungen"
o. ä.), einfach **abwählen** (Häkchen „einbeziehen" entfernen).

---

## 5. Abrechnungsperiode

Menü **Abrechnungen**.

### 5.1 Neue Periode eröffnen

**+ Abrechnungsperiode** → Bezeichnung, Zeitraum *von/bis*, **Rücklagen-Anfangssaldo
(gesamt)**. Nach dem Anlegen landest du in der Bearbeiten-Maske.

Dort erfasst du die **manuellen Anfangswerte**:

- **Saldovortrag Hausgeld je Eigentümer** – der Übertrag aus der Vorperiode
  (Endsaldo Hausgeld des Vorjahres). Inkl. evtl. Erstattung/Nachzahlung, siehe 6.4.
- **Zähler / Direkteingaben** – Beträge je Eigentümer aus externen
  Verbrauchsabrechnungen (z. B. Heizkostenabrechnung des Messdienstes). Nur für
  Kostenarten mit Umlageschlüssel *Zähler*.

**Salden aus Vorperiode übernehmen** (Schaltfläche neben „Saldovortrag Hausgeld"):
füllt Rücklagen-Anfangssaldo und den Saldovortrag je Eigentümer automatisch mit
den **Endsalden der vorigen Periode**. Danach prüfen und speichern.

### 5.2 Übersicht lesen

Die Perioden-Übersicht (`Abrechnungen → Bezeichnung`) zeigt:

- **Kostenübersicht** – Matrix *Kostenart × Eigentümer*, gruppiert nach Kategorie,
  mit WEG-Gesamtbetrag und Anteil je Eigentümer. Summenzeile = *Kostenanteil*.
- **Hausgeldübersicht** – je Eigentümer: Saldovortrag, Sonderumlage, ./. Investition,
  Hausgeld gezahlt, ./. Kostenanteil, Guthaben/Nachzahlung, **Endsaldo Hausgeld**.
- **Rücklagenübersicht** – Anfangssaldo (nach MEA), Zuführung, Entnahme, **Endsaldo Rücklage**.
- **Saldo gesamt je Eigentümer** = Endsaldo Hausgeld + Endsaldo Rücklage.

### 5.3 Einzelabrechnungen

Oben in der Übersicht: **Einzelabrechnung E1 / E2 / …** öffnet die Ansicht je
Eigentümer (Positionen, Lieferant, WEG-Gesamtkosten, Umlageschlüssel, „Ihr Anteil",
Summe, geleistetes Hausgeld, Guthaben/Nachzahlung, Hausgeldkonto- und
Rücklagen-Block, Saldo gesamt). Dort **PDF herunterladen**.
**Alle als PDF** erzeugt eine PDF mit allen Eigentümern (eine Seite pro Person).

### 5.4 Abrechnung abschließen

**Abrechnung abschließen** (Perioden-Übersicht) setzt den Status auf
*abgeschlossen*. Wirkung:

- **Buchungen im Zeitraum sind gesperrt** – Anlegen, Ändern und Löschen von
  Buchungen mit Datum im Periodenzeitraum wird abgelehnt (auch der CSV-Import).
- Die **Anfangswerte** der Periode lassen sich nicht mehr ändern.

Muss doch etwas korrigiert werden: **Wieder öffnen (Entwurf)**, korrigieren,
erneut abschließen.

---

## 6. Spezialfälle / How-To

### 6.1 Entnahme aus der Rücklage für eine Reparatur

1. Kostenart **„Instandhaltung"** (Typ *Betriebskosten*, Umlageschlüssel meist
   *MEA*) – die Rechnung der Handwerksfirma als **Ausgabe** buchen (Konto =
   das Konto, von dem gezahlt wurde).
2. Wurde direkt vom Rücklagenkonto gezahlt: die Ausgabe auf das **Rücklagenkonto**
   buchen. Zusätzlich eine Buchung Typ **Rücklage** mit **negativem** Betrag
   („Entnahme") in gleicher Höhe – damit sinkt der *Endsaldo Rücklage*, und der
   entsprechende Betrag wird dem *Endsaldo Hausgeld* gutgeschrieben (die
   Reparatur wird ja trotzdem über den Kostenanteil auf alle umgelegt).

### 6.2 Sonderumlage zur Finanzierung einer Investition

- Die Eigentümer zahlen ein → Kostenart **„Sonderzahlung …"** (Typ *Sonderumlage*),
  je Zahlung mit dem **Eigentümer**.
- Die Firma wird bezahlt → Kostenart **„… einbau"** (Typ *Investition*), als
  Ausgabe. Wird nach MEA verteilt.
- In der Hausgeldübersicht: *Sonderumlage* (was der Eigentümer einzahlte) steht
  seinem *MEA-Anteil an der Investition* gegenüber.

### 6.3 Umbuchung zwischen Rücklagen- und Hausgeldkonto

Eine Buchung Typ **Rücklage**:

| Betrag | Bedeutung | Wirkung |
|---|---|---|
| **positiv** | Zuführung (Hausgeld → Rücklage) | Endsaldo Rücklage **+**, Endsaldo Hausgeld **−** |
| **negativ** | Entnahme (Rücklage → Hausgeld) | Endsaldo Rücklage **−**, Endsaldo Hausgeld **+** |

Betrifft die Umbuchung nur **einen** Eigentümer, die Buchung **mit Eigentümer**
erfassen – dann wirkt sie nur bei ihm. Ohne Eigentümer wird sie nach MEA verteilt.
Der **Saldo gesamt** je Eigentümer bleibt bei einer reinen Umbuchung unverändert
(es wird nur zwischen den beiden Konten verschoben).

Damit der Bankauszug stimmt, die Gegenbuchung auf dem anderen Konto mit einer
neutralen Kostenart (Typ *Betriebskosten*, Umlageschlüssel **Vorauszahlung** –
zählt 0) erfassen; sie taucht dann im Kontoauszug auf, ohne die Abrechnung zu
verändern.

### 6.4 Erstattung / Nachzahlung aus dem Vorjahr

Die App verrechnet den Typ *Erstattung/Nachzahlung* **nicht automatisch** im
Endsaldo. Empfohlen: den Betrag je Eigentümer in den **Saldovortrag Hausgeld**
der neuen Periode einrechnen (Endsaldo Vorjahr **+** Erstattung bzw. **−**
Nachzahlung). Die Funktion „Salden aus Vorperiode übernehmen" nimmt den reinen
Endsaldo – die Vorjahres-Erstattung ggf. manuell ergänzen.

### 6.5 Heizkosten: Abschläge vs. Messdienst-Abrechnung

- Die monatlichen **Abschläge** an den Versorger: Kostenart mit Umlageschlüssel
  **Vorauszahlung** – sie erscheinen im Kontoauszug, werden aber **nicht** umgelegt.
- Die tatsächlichen Verbrauchskosten aus der **Messdienst-Abrechnung** (Techem
  o. ä.): Kostenart mit Umlageschlüssel **Zähler**; die Beträge je Eigentümer
  trägst du in der Perioden-Bearbeiten-Maske unter „Zähler / Direkteingaben" ein.

### 6.6 Nachträgliche Korrektur einer abgeschlossenen Periode

Perioden-Übersicht → **Wieder öffnen (Entwurf)** → Buchung/Anfangswert
korrigieren → erneut **abschließen**. Bereits verschickte PDFs neu erzeugen.

---

## 7. Fehlerdiagnose

| Symptom | Ursache / Lösung |
|---|---|
| „Saldo gesamt" je Eigentümer weicht um wenige Euro ab, Gesamtsumme stimmt | Kostenart-Typ falsch – meist Sonderumlage vs. Investition (6.2) oder eine Rücklagenbewegung falsch typisiert. |
| MEA-Summe ≠ 1000 (Warnung in der Eigentümerliste) | MEA eines Eigentümers korrigieren. |
| „… liegt im abgeschlossenen Zeitraum" beim Buchen | Periode zuerst „Wieder öffnen (Entwurf)". |
| Kostenanteil unerwartet 0 für eine Position | Umlageschlüssel steht auf *Vorauszahlung*, oder es fehlen die *Zähler*-Direkteingaben. |
| Buchung erscheint nicht in der Abrechnung | Datum außerhalb des Periodenzeitraums, oder fachlicher Typ passt nicht (z. B. *Erstattung/Nachzahlung*). |
| PDF „nicht verfügbar" | Auf dem Server fehlen die WeasyPrint-Systempakete – siehe technische Doku / `deploy/DEPLOY.md`. |
| CSV-Import findet Spalten nicht | Im Schritt „Spalten zuordnen" manuell zuordnen; wird als Profil gespeichert. |
