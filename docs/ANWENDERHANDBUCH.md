# WEG-Abrechnung – Anwenderhandbuch

Stand: September 2026. Diese Anleitung beschreibt die Bedienung der
Webanwendung für die Jahresabrechnung einer kleinen Wohnungseigentümer­gemeinschaft.

---

## 1. Grundbegriffe

| Begriff | Bedeutung in der App |
|---|---|
| **Eigentümer** | Eine Einheit der WEG (E1 … E4) mit **Miteigentumsanteil (MEA)**. Die MEA aller Eigentümer sollen sich zu **1000** summieren. |
| **Konto** | Ein Bankkonto der WEG. Typ **Girokonto** (laufende Kosten, Hausgeld) oder **Rücklagenkonto**. Das Konto dient v. a. dem Abgleich mit dem Bankauszug – für die *Berechnung* zählt nur die Kostenart. |
| **Kostenart** | Die Bezeichnung einer Buchung (z. B. „Gebäudeversicherung"). Jede Kostenart hat einen **fachlichen Typ** und – bei umlagefähigen Kosten – einen **Umlageschlüssel**. |
| **Fachlicher Typ** | Steuert, *wie* eine Buchung in die Abrechnung einfließt: `Betriebskosten`, `Hausgeld`, `Sonderumlage`, `Investition`, `Rücklage`, `Erstattung/Nachzahlung`, `Umbuchung` (neutral). |
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

Der **Anfangssaldo des Rücklagenkontos** fließt in die Abrechnung ein: Solange in
einer Abrechnungsperiode kein eigener „Rücklagen-Anfangssaldo" erfasst ist
(Wert 0), verwendet die Abrechnung den **Stand des Rücklagenkontos zu
Periodenbeginn** (Anfangssaldo + Buchungen davor) und verteilt ihn nach MEA.

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
| **Rücklage** | Zuführung zur / Entnahme aus der Rücklage | Positiv = Zuführung, negativ = Entnahme. Verschiebt zwischen *Endsaldo Rücklage* und *Endsaldo Hausgeld* (siehe 6.3). |
| **Erstattung/Nachzahlung** | Ausgleich aus der Vorjahresabrechnung | **Wird derzeit nicht automatisch verrechnet** – siehe 6.4. |
| **Umbuchung (neutral)** | Gegenbuchung einer Umbuchung zwischen Konten | **Keine** Wirkung auf die Abrechnung; nur für den Kontoauszug. Wird vom Umbuchungs-Assistenten automatisch verwendet (6.3). |

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

Mit **PDF** (oben rechts) wird die aktuell **gefilterte** Liste als PDF
ausgegeben – chronologisch sortiert (älteste Buchung oben), mit Filterangabe im
Kopf und der Gesamtsumme am Ende der letzten Seite (auf dem Raspberry Pi, sonst
erscheint ein Hinweis).

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

### 4.4 Umbuchung zwischen Konten

**Buchungen → ↔ Umbuchung** – verschiebt Geld zwischen Rücklagen- und
Hausgeldkonto und legt dabei automatisch die zwei korrekten Buchungen an.
Details siehe 6.3.

---

## 5. Abrechnungsperiode

Menü **Abrechnungen**.

### 5.0 Typischer Ablauf eines Wirtschaftsjahres

1. **Am Jahresanfang:** neue Abrechnungsperiode anlegen (5.1), Anfangswerte
   erfassen bzw. **„Salden aus Vorperiode übernehmen"**.
2. **Laufend:** Buchungen erfassen – einzeln (4.1) oder per **CSV-Import** (4.3).
   Zwischendurch die Perioden-Übersicht (5.2) zur Kontrolle ansehen.
3. **Nach Jahresende:** Heizkostenabrechnung des Messdienstes eingetragen (6.5),
   Rücklagen-Zuführungen/-Entnahmen als Umbuchung erfasst (6.3), alles geprüft.
4. **Abschluss:** Einzelabrechnungen als PDF erzeugen (5.3), an die Eigentümer
   verteilen, dann **„Abrechnung abschließen"** (5.4) – die Buchungen des
   Zeitraums sind danach gesperrt.

### 5.1 Neue Periode eröffnen

**+ Abrechnungsperiode** → Bezeichnung, Zeitraum *von/bis*, **Rücklagen-Anfangssaldo
(gesamt)**. Nach dem Anlegen landest du in der Bearbeiten-Maske.

> Lässt du „Rücklagen-Anfangssaldo (gesamt)" auf **0**, nimmt die Abrechnung
> automatisch den Stand des Rücklagenkontos zu Periodenbeginn (siehe 3.2). Ein
> von 0 verschiedener Wert hat Vorrang. Die Perioden-Übersicht zeigt unter der
> Rücklagentabelle an, welche Quelle verwendet wurde.

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

### 5.5 Wirtschaftsplan (Prognoserechnung)

Der Menüpunkt **Wirtschaftsplan** zeigt für ein Wirtschaftsjahr eine monatliche
Vorschau der Einnahmen und Ausgaben mit laufendem Kontostand. Er ändert **keine**
Buchungen und ist unabhängig davon, ob die Periode Entwurf oder abgeschlossen ist.

**Aufbau der Tabelle**

- Eine Zeile je Kalendermonat der Periode, dazu die Zeilen *Anfangssaldo* und
  *Summe*.
- Spalten von links nach rechts: **Monat**, **Saldo** (Vormonatssaldo +
  Differenz), **Einnahmen**, **Ausgaben gesamt**, **Differenz** (Einnahmen −
  Ausgaben), danach je Einnahme-Kostenart (Typ *Hausgeld*, *Sonderumlage*,
  *Erstattung/Nachzahlung*) und je Ausgabe-Kostenart (Typ *Betriebskosten*,
  *Investition*) ein Eingabefeld.
- Neue Kostenarten erscheinen automatisch als zusätzliche Spalte.
- Über den Spaltenköpfen fassen die Gruppen­überschriften **Gesamt**,
  **Einnahmen** und **Ausgaben** die jeweiligen Spalten zusammen.
- **Erstattung/Nachzahlung** zählt zu den *Einnahmen*: eine Nachzahlung des
  Eigentümers ist ein Geldzufluss (positiv), eine Erstattung an ihn ein Abfluss
  (negativ). Auf die *Differenz* und den *Saldo* wirkt sich das nicht aus – nur
  auf die Aufteilung Einnahmen / Ausgaben.

**Woher die Werte kommen** – je Zelle in dieser Reihenfolge:

1. **manuell** (blau) – ein von dir eingetragener und gespeicherter Wert.
2. **Ist** (grün) – es liegen für diese Kostenart in diesem Monat bereits
   Buchungen der laufenden Periode vor; angezeigt wird deren Summe.
3. **Prognose** (grau) – sonst der Betrag derselben Kostenart im gleichen
   Monat der **vorherigen Abrechnungsperiode**. Gibt es keine Vorperiode,
   bleibt das Feld leer.

Der **Anfangssaldo** ist der Stand der **Girokonten** zu Periodenbeginn
(Kontostand aus allen Buchungen vor dem Startdatum). Das Rücklagenkonto zählt
hier nicht mit.

**Bearbeiten**

- Feld überschreiben und **Speichern**. Gespeichert werden nur Felder, die vom
  automatischen Wert abweichen; setzt du ein Feld wieder auf den Ist-/Prognose-
  Wert (oder leerst es), wird die Überschreibung entfernt.
- **Auf Ist/Prognose zurücksetzen** verwirft alle Überschreibungen der Periode.
- **PDF** erzeugt die Tabelle als PDF im Querformat (auf dem Raspberry Pi; ohne
  WeasyPrint erscheint stattdessen ein Hinweis). Für ein kompaktes Blatt werden
  im PDF Kostenart-Spalten **ohne Wert weggelassen**; die Bildschirmansicht zeigt
  weiterhin alle.

### 5.6 Jahresvergleich

Der Menüpunkt **Jahresvergleich** stellt die Wirtschaftsplan-Werte zweier
Wirtschaftsjahre gegenüber. Zwei Auswahlfelder:

- **Wirtschaftsjahr** – vorbelegt mit dem aktuellen (jüngsten) Wirtschaftsjahr.
- **Vergleichswirtschaftsjahr** – vorbelegt mit dem unmittelbar vorangehenden.

Über der Kopftabelle stehen die Gesamtwerte beider Jahre (Anfangssaldo,
Einnahmen, Ausgaben, Differenz) samt Differenz. Das Monatsraster ist wie beim
Wirtschaftsplan aufgebaut – **ohne die Spalte *Saldo***. In jeder Zelle steht
die **Differenz** *Wirtschaftsjahr − Vergleichswirtschaftsjahr* (die beiden
Einzelwerte erscheinen im Tooltip). Negative Differenzen sind rot. Auch hier
gibt es einen **PDF**-Export im Querformat.

---

## 6. Spezialfälle / How-To

### 6.1 Entnahme aus der Rücklage für eine Reparatur

1. Die **Rechnung der Handwerksfirma** als Ausgabe buchen – Kostenart z. B.
   „Instandhaltung" (Typ *Betriebskosten*, Umlageschlüssel meist *MEA*), Konto =
   das Konto, von dem tatsächlich gezahlt wurde. Die Kosten werden über den
   Kostenanteil auf alle Eigentümer umgelegt.
2. Falls die Rücklage die Kosten (mit-)tragen soll: über **Buchungen → ↔ Umbuchung**
   den Betrag vom Rücklagenkonto auf das Girokonto umbuchen (= *Entnahme*, siehe
   6.3). Der *Endsaldo Rücklage* sinkt, der *Endsaldo Hausgeld* steigt entsprechend.

### 6.2 Sonderumlage zur Finanzierung einer Investition

- Die Eigentümer zahlen ein → Kostenart **„Sonderzahlung …"** (Typ *Sonderumlage*),
  je Zahlung mit dem **Eigentümer**.
- Die Firma wird bezahlt → Kostenart **„… einbau"** (Typ *Investition*), als
  Ausgabe. Wird nach MEA verteilt.
- In der Hausgeldübersicht: *Sonderumlage* (was der Eigentümer einzahlte) steht
  seinem *MEA-Anteil an der Investition* gegenüber.

### 6.3 Umbuchung zwischen Rücklagen- und Hausgeldkonto

Dafür gibt es einen eigenen Assistenten: **Buchungen → ↔ Umbuchung**.

Eingabe: **Von Konto**, **Nach Konto**, **Betrag** (immer positiv), Datum,
optional ein Eigentümer, Notiz. Die App legt automatisch **zwei Buchungen** an:

- die Buchung **auf dem Rücklagenkonto** bekommt den fachlichen Typ *Rücklage* –
  sie erhöht bzw. senkt den **Endsaldo Rücklage** und wirkt **gegengleich** auf den
  **Endsaldo Hausgeld**;
- die Gegenbuchung auf dem anderen Konto ist **neutral** (Typ *Umbuchung*) und
  taucht nur im Kontoauszug auf, ohne die Abrechnung zu verändern.

| Richtung | Bedeutung | Wirkung |
|---|---|---|
| Girokonto → Rücklagenkonto | **Zuführung** | Endsaldo Rücklage **+**, Endsaldo Hausgeld **−** |
| Rücklagenkonto → Girokonto | **Entnahme** | Endsaldo Rücklage **−**, Endsaldo Hausgeld **+** |

Ohne Eigentümer wird die Umbuchung nach MEA auf alle verteilt; mit Eigentümer
wirkt sie nur bei diesem. Der **Saldo gesamt** je Eigentümer bleibt bei einer
reinen Umbuchung **unverändert** – es wird nur zwischen den beiden Konten
verschoben.

> Du kannst dieselben zwei Buchungen auch von Hand anlegen (eine Kostenart Typ
> *Rücklage* auf dem Rücklagenkonto, eine Kostenart Typ *Umbuchung* auf dem
> Girokonto). Buche **nicht** dieselbe Rücklage-Kostenart auf beiden Konten – dann
> heben sich Zuführung und Entnahme gegenseitig auf und es passiert nichts.

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
| Rücklagenkonto / Anfangssaldo taucht nicht in der Abrechnung auf | Der Rücklagen-Anfangssaldo steht am **Rücklagenkonto** (Menü Konten). Ist der Perioden-Wert ≠ 0, hat dieser Vorrang – dann in der Perioden-Bearbeiten-Maske auf 0 setzen. |
| PDF „nicht verfügbar" | Auf dem Server fehlen die WeasyPrint-Systempakete – siehe technische Doku / `deploy/DEPLOY.md`. |
| CSV-Import findet Spalten nicht | Im Schritt „Spalten zuordnen" manuell zuordnen; wird als Profil gespeichert. |
