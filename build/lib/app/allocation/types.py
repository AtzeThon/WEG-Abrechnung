"""Ein- und Ausgabe-Datenstrukturen der Berechnungs-Engine.

Alle Geldbeträge sind ``decimal.Decimal``. Die Engine rundet **nicht** – Rundung
auf Cent erfolgt ausschließlich bei der Anzeige (Web/PDF).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

# Fachliche Typen / Strategien werden als einfache Strings übergeben, damit die
# Engine nicht von den ORM-Enums abhängt. Gültige Werte siehe app.models.enums.
Kind = str
Strategy = str
Category = str

ZERO = Decimal("0")


# --------------------------------------------------------------------------- #
# Eingaben
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class OwnerInput:
    code: str
    mea: Decimal
    name: str = ""
    email: str = ""


@dataclass(frozen=True)
class CostTypeInput:
    name: str
    kind: Kind = "betriebskosten"
    strategy: Strategy = "mea"
    category: Category = "sonstiges"
    supplier: str = ""
    proportional_to: str | None = None


@dataclass(frozen=True)
class TxnInput:
    booking_date: date
    cost_type: str
    amount: Decimal          # positiv = Einzahlung, negativ = Ausgabe
    owner: str | None = None
    payee: str = ""


@dataclass(frozen=True)
class OverrideInput:
    cost_type: str
    owner: str
    amount: Decimal


@dataclass(frozen=True)
class PeriodInput:
    start_date: date
    end_date: date
    reserve_opening_balance: Decimal = ZERO
    # Saldovortrag Hausgeld je Eigentümer-Code (manuell erfasst).
    hausgeld_carryover: dict[str, Decimal] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Ergebnisse
# --------------------------------------------------------------------------- #
@dataclass
class CostTypeResult:
    """Ergebnis einer einzelnen umlagefähigen Kostenart."""

    name: str
    category: Category
    supplier: str
    strategy: Strategy
    strategy_label: str
    actual_cash: Decimal                  # Ist-Zahlungen laut Buchungen (Ausgaben positiv)
    weg_total: Decimal                    # umgelegter Gesamtbetrag (= Summe der Anteile)
    shares: dict[str, Decimal]            # Anteil je Eigentümer-Code

    def share(self, code: str) -> Decimal:
        return self.shares.get(code, ZERO)


@dataclass
class OwnerBillingResult:
    code: str
    name: str
    mea: Decimal
    mea_fraction: Decimal

    # Kostenumlage
    cost_share_total: Decimal = ZERO

    # Hausgeld
    hausgeld_paid: Decimal = ZERO
    guthaben: Decimal = ZERO              # hausgeld_paid - cost_share_total (Guthaben>0 / Nachzahlung<0)

    # Hausgeld-Endsaldo-Bausteine
    carryover: Decimal = ZERO             # Saldovortrag (manuell)
    sonderumlage_paid: Decimal = ZERO     # eigentümerbezogene Sonderzahlungen
    investition_share: Decimal = ZERO     # Anteil an investiven Ausgaben (nach MEA)
    erstattung: Decimal = ZERO            # aktuell immer 0 (nicht verrechnet)
    hausgeld_endsaldo: Decimal = ZERO

    # Rücklage
    reserve_opening: Decimal = ZERO
    reserve_zufuehrung: Decimal = ZERO
    reserve_entnahme: Decimal = ZERO
    reserve_endsaldo: Decimal = ZERO

    # Gesamt
    total_saldo: Decimal = ZERO


@dataclass
class BillingResult:
    period_start: date
    period_end: date
    total_mea: Decimal

    owner_order: list[str]
    owners: dict[str, OwnerBillingResult]

    # Kostenmatrix in Anzeige-Reihenfolge
    cost_type_order: list[str]
    cost_types: dict[str, CostTypeResult]

    # Aggregierte Summen (WEG-weit)
    cost_share_total: Decimal = ZERO
    hausgeld_paid_total: Decimal = ZERO
    sonderumlage_total: Decimal = ZERO
    investition_total: Decimal = ZERO
    reserve_opening_total: Decimal = ZERO
    reserve_endsaldo_total: Decimal = ZERO

    def owner_result(self, code: str) -> OwnerBillingResult:
        return self.owners[code]

    def cost_lines_for(self, code: str) -> list[CostTypeResult]:
        """Kostenarten mit einem von 0 verschiedenen Anteil für diesen Eigentümer
        oder einem umgelegten Gesamtbetrag (für die Einzelabrechnung)."""
        out = []
        for name in self.cost_type_order:
            ct = self.cost_types[name]
            if ct.weg_total != ZERO or ct.share(code) != ZERO:
                out.append(ct)
        return out
