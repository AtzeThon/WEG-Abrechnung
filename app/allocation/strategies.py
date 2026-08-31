"""Umlageschlüssel als austauschbare Strategien (Funktions-Registry).

Eine Strategie berechnet aus dem :class:`AllocationContext` den Anteil je
Eigentümer (``dict[owner_code -> Decimal]``). Neue Schlüssel werden durch
``@register("name")`` ergänzt – ohne Änderung an der Engine.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal

from app.allocation.types import ZERO, CostTypeInput, OwnerInput

StrategyFn = Callable[["AllocationContext"], dict[str, Decimal]]

_REGISTRY: dict[str, StrategyFn] = {}


@dataclass
class AllocationContext:
    cost_type: CostTypeInput
    owners: list[OwnerInput]
    mea_fraction: dict[str, Decimal]
    actual_total: Decimal                       # Ist-Kosten laut Buchungen (Ausgaben positiv)
    overrides: dict[str, Decimal] = field(default_factory=dict)
    # Bereits berechnete Anteile anderer Kostenarten (für 'proportional').
    resolved: dict[str, dict[str, Decimal]] = field(default_factory=dict)

    @property
    def owner_codes(self) -> list[str]:
        return [o.code for o in self.owners]


def register(name: str) -> Callable[[StrategyFn], StrategyFn]:
    def deco(fn: StrategyFn) -> StrategyFn:
        _REGISTRY[name] = fn
        return fn

    return deco


def get_strategy(name: str) -> StrategyFn:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise ValueError(
            f"Unbekannter Umlageschlüssel {name!r}. Bekannt: {sorted(_REGISTRY)}"
        ) from None


def available_strategies() -> list[str]:
    return sorted(_REGISTRY)


def depends_on(cost_type: CostTypeInput) -> str | None:
    """Name der Kostenart, von der diese Kostenart abhängt (oder None)."""
    if cost_type.strategy == "proportional":
        return cost_type.proportional_to
    return None


# --------------------------------------------------------------------------- #
# Konkrete Strategien
# --------------------------------------------------------------------------- #
@register("mea")
def _mea(ctx: AllocationContext) -> dict[str, Decimal]:
    """Anteil = Ist-Kosten × (MEA des Eigentümers / Gesamt-MEA)."""
    return {o.code: ctx.actual_total * ctx.mea_fraction[o.code] for o in ctx.owners}


@register("zaehler")
def _zaehler(ctx: AllocationContext) -> dict[str, Decimal]:
    """Betrag je Eigentümer wird direkt erfasst (externe Verbrauchsabrechnung).
    Der WEG-Gesamtbetrag ergibt sich als Summe dieser Direkteingaben."""
    return {o.code: ctx.overrides.get(o.code, ZERO) for o in ctx.owners}


@register("vorauszahlung")
def _vorauszahlung(ctx: AllocationContext) -> dict[str, Decimal]:
    """Reine Abschlags-/Vorauszahlung – wird nicht auf die Eigentümer umgelegt
    (die tatsächlichen Kosten kommen über eine andere Kostenart, z. B. 'Zähler')."""
    return {o.code: ZERO for o in ctx.owners}


@register("proportional")
def _proportional(ctx: AllocationContext) -> dict[str, Decimal]:
    """Verteilung im gleichen Verhältnis wie eine bereits berechnete Kostenart.
    Fällt auf MEA zurück, wenn die Bezugskostenart in Summe 0 ergibt."""
    target = ctx.cost_type.proportional_to
    base = ctx.resolved.get(target or "", {})
    base_total = sum(base.values(), ZERO)
    if base_total == ZERO:
        return _mea(ctx)
    return {
        o.code: ctx.actual_total * (base.get(o.code, ZERO) / base_total) for o in ctx.owners
    }
