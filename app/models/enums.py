"""Aufzählungstypen der Stammdaten. Werte werden als Strings in SQLite abgelegt."""

from __future__ import annotations

import enum


class AccountType(str, enum.Enum):
    GIRO = "giro"            # laufende Kosten + Hausgeldeinzahlungen
    RUECKLAGE = "ruecklage"  # Instandhaltungsrücklage


class CostCategory(str, enum.Enum):
    """Gliederung der Positionen in der Einzelabrechnung."""

    HEIZEN_WASSER_BETRIEB = "heizen_wasser_betrieb"
    VERSICHERUNGEN = "versicherungen"
    GEBUEHREN_ABGABEN = "gebuehren_abgaben"
    WARTUNG_DIENSTLEISTUNG = "wartung_dienstleistung"
    VERWALTUNG = "verwaltung"
    SONSTIGES = "sonstiges"

    @property
    def label(self) -> str:
        return _CATEGORY_LABELS[self]


_CATEGORY_LABELS = {
    CostCategory.HEIZEN_WASSER_BETRIEB: "Heizen, Wasser, Betrieb",
    CostCategory.VERSICHERUNGEN: "Versicherungen",
    CostCategory.GEBUEHREN_ABGABEN: "Gebühren und Abgaben",
    CostCategory.WARTUNG_DIENSTLEISTUNG: "Wartung und Dienstleistungen",
    CostCategory.VERWALTUNG: "Verwaltung",
    CostCategory.SONSTIGES: "Sonstiges",
}


class CostKind(str, enum.Enum):
    """Fachlicher Typ einer Kostenart – steuert die Verarbeitung in der Engine."""

    BETRIEBSKOSTEN = "betriebskosten"   # umlagefähig, wird auf alle Eigentümer verteilt
    HAUSGELD = "hausgeld"               # monatliche Einzahlung des Eigentümers
    ERSTATTUNG = "erstattung"           # Ausgleich aus Vorjahresabrechnung (aktuell nicht verrechnet)
    RUECKLAGE = "ruecklage"             # Zuführung/Entnahme Instandhaltungsrücklage
    SONDERUMLAGE = "sonderumlage"       # eigentümerbezogene Sonderzahlung (z. B. Heizungsmodernisierung)
    INVESTITION = "investition"         # investive Ausgabe, getrennt von der laufenden Umlage geführt

    @property
    def label(self) -> str:
        return _KIND_LABELS[self]


_KIND_LABELS = {
    CostKind.BETRIEBSKOSTEN: "Umlagefähige Betriebskosten",
    CostKind.HAUSGELD: "Hausgeld",
    CostKind.ERSTATTUNG: "Erstattung / Nachzahlung",
    CostKind.RUECKLAGE: "Rücklage",
    CostKind.SONDERUMLAGE: "Sonderumlage",
    CostKind.INVESTITION: "Investition",
}


class AllocationStrategy(str, enum.Enum):
    """Umlageschlüssel einer umlagefähigen Kostenart (austauschbare Strategie)."""

    MEA = "mea"                    # Anteil = Ist-Kosten × MEA / Gesamt-MEA
    ZAEHLER = "zaehler"            # Betrag je Eigentümer direkt erfasst (Verbrauchsabrechnung)
    VORAUSZAHLUNG = "vorauszahlung"  # nicht umlegen (reine Abschlags-/Vorauszahlung)
    PROPORTIONAL = "proportional"  # proportional zu einer anderen, bereits berechneten Kostenart

    @property
    def label(self) -> str:
        return _STRATEGY_LABELS[self]


_STRATEGY_LABELS = {
    AllocationStrategy.MEA: "Nach Anteilen (MEA)",
    AllocationStrategy.ZAEHLER: "Zähler / Direkteingabe",
    AllocationStrategy.VORAUSZAHLUNG: "Vorauszahlung (nicht umlegen)",
    AllocationStrategy.PROPORTIONAL: "Proportional zu anderer Kostenart",
}


class PeriodStatus(str, enum.Enum):
    DRAFT = "draft"
    FINAL = "final"


class TransactionSource(str, enum.Enum):
    """Herkunft einer Buchung."""

    MANUAL = "manuell"
    CSV_IMPORT = "csv_import"


class ImportBatchStatus(str, enum.Enum):
    ENTWURF = "entwurf"          # hochgeladen, noch nicht gebucht
    IMPORTIERT = "importiert"    # Buchungen wurden angelegt
    VERWORFEN = "verworfen"      # abgebrochen

    @property
    def label(self) -> str:
        return {
            ImportBatchStatus.ENTWURF: "Entwurf",
            ImportBatchStatus.IMPORTIERT: "importiert",
            ImportBatchStatus.VERWORFEN: "verworfen",
        }[self]


# Fachliche Typen, die eine Eigentümer-Zuordnung an der Buchung erfordern.
OWNER_REQUIRED_KINDS = {CostKind.HAUSGELD, CostKind.ERSTATTUNG, CostKind.SONDERUMLAGE}
