"""Künftiger monatlicher Hausgeld-Abschlag je Eigentümer (reine Rechnung).

Grundlage laut Anforderung: die geleisteten Hausgeldzahlungen der Periode
zzgl. einer Nachzahlung bzw. abzgl. eines Guthabens, geteilt durch 12, danach
um die Inflationsrate angehoben und **kaufmännisch auf volle Euro** gerundet.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal("0")
_CENT = Decimal("0.01")
_EURO = Decimal("1")


@dataclass(frozen=True)
class NextAdvance:
    hausgeld_paid: Decimal        # geleistete Hausgeldzahlungen der Periode
    settlement: Decimal           # + Nachzahlung / − Guthaben (verändert die Grundlage)
    base: Decimal                 # hausgeld_paid + settlement
    months: int                   # Teiler (i. d. R. 12)
    monthly: Decimal              # base / months, auf Cent
    inflation_rate: Decimal       # Prozent
    monthly_inflated: Decimal     # monthly inkl. Inflation, auf Cent
    amount: Decimal               # Endbetrag, kaufmännisch auf volle Euro


def compute_next_advance(
    hausgeld_paid: Decimal,
    guthaben: Decimal,
    inflation_rate: Decimal | None = None,
    *,
    months: int = 12,
) -> NextAdvance:
    """``guthaben`` positiv = Guthaben (senkt den Abschlag), negativ = Nachzahlung."""
    rate = inflation_rate or ZERO
    settlement = -guthaben  # Nachzahlung -> positiv, Guthaben -> negativ
    base = hausgeld_paid + settlement
    monthly_exact = base / months
    inflated_exact = monthly_exact * (Decimal(1) + rate / 100)
    return NextAdvance(
        hausgeld_paid=hausgeld_paid,
        settlement=settlement,
        base=base,
        months=months,
        monthly=monthly_exact.quantize(_CENT, rounding=ROUND_HALF_UP),
        inflation_rate=rate,
        monthly_inflated=inflated_exact.quantize(_CENT, rounding=ROUND_HALF_UP),
        amount=inflated_exact.quantize(_EURO, rounding=ROUND_HALF_UP),
    )
