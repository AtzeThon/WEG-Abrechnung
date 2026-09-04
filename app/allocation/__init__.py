"""Reine Berechnungs-Engine der WEG-Abrechnung – ohne DB- oder UI-Abhängigkeit.

Öffentliche API:
    compute_billing(period, owners, cost_types, transactions, overrides) -> BillingResult
"""

from app.allocation.advance import NextAdvance, compute_next_advance
from app.allocation.engine import compute_billing
from app.allocation.types import (
    BillingResult,
    CostTypeInput,
    CostTypeResult,
    OverrideInput,
    OwnerBillingResult,
    OwnerInput,
    PeriodInput,
    TxnInput,
)

__all__ = [
    "compute_billing",
    "compute_next_advance",
    "NextAdvance",
    "BillingResult",
    "CostTypeInput",
    "CostTypeResult",
    "OverrideInput",
    "OwnerBillingResult",
    "OwnerInput",
    "PeriodInput",
    "TxnInput",
]
