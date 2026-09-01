"""Berechnungskette einer Abrechnungsperiode (rein, testbar).

Schritte (entsprechen der fachlichen Vorgabe):
  1. Buchungen des Zeitraums je Kostenart summieren  -> Ist-Kosten
  2. Umlageschlüssel-Strategie anwenden               -> Anteil je Eigentümer/Kostenart
  3. Anteile je Eigentümer summieren                  -> Kostenanteil
  4. Hausgeld-Buchungen je Eigentümer summieren       -> geleistetes Hausgeld
  5. Guthaben/Nachzahlung = Hausgeld - Kostenanteil
  6. Endsaldo Hausgeld = Saldovortrag + Sonderumlage - Investitionsanteil
                         + Guthaben/Nachzahlung  (+ Erstattung, aktuell 0)
                         - Rücklagen-Zuführung + Rücklagen-Entnahme
  7. Rücklage je Eigentümer: Anfangssaldo (nach MEA) + Zuführung - Entnahme
  8. Saldo gesamt = Endsaldo Hausgeld + Endsaldo Rücklage
     (eine Rücklagenbewegung verschiebt nur zwischen 6 und 7, Summe bleibt gleich)
"""

from __future__ import annotations

from decimal import Decimal

from app.allocation.strategies import AllocationContext, depends_on, get_strategy
from app.allocation.types import (
    ZERO,
    BillingResult,
    CostTypeInput,
    CostTypeResult,
    OverrideInput,
    OwnerBillingResult,
    OwnerInput,
    PeriodInput,
    TxnInput,
)

# Anzeige-Beschriftungen der Strategien (Duplikat der Enum-Labels, aber die
# Engine soll frei von ORM-Importen bleiben).
_STRATEGY_LABELS = {
    "mea": "Nach Anteilen (MEA)",
    "zaehler": "Zähler / Direkteingabe",
    "vorauszahlung": "Vorauszahlung (nicht umgelegt)",
    "proportional": "Proportional zu anderer Kostenart",
}

_UMLAGE_KINDS = {"betriebskosten"}  # fließen in den Kostenanteil ein


def _sum(values) -> Decimal:
    return sum(values, ZERO)


def _order_cost_types(cost_types: list[CostTypeInput]) -> list[CostTypeInput]:
    """Topologische Sortierung: eine 'proportional'-Kostenart wird nach ihrer
    Bezugskostenart berechnet."""
    by_name = {ct.name: ct for ct in cost_types}
    ordered: list[CostTypeInput] = []
    seen: set[str] = set()
    visiting: set[str] = set()

    def visit(ct: CostTypeInput) -> None:
        if ct.name in seen:
            return
        if ct.name in visiting:
            raise ValueError(f"Zyklische Abhängigkeit bei Kostenart {ct.name!r}")
        visiting.add(ct.name)
        dep = depends_on(ct)
        if dep and dep in by_name:
            visit(by_name[dep])
        visiting.discard(ct.name)
        seen.add(ct.name)
        ordered.append(ct)

    for ct in cost_types:
        visit(ct)
    return ordered


def compute_billing(
    period: PeriodInput,
    owners: list[OwnerInput],
    cost_types: list[CostTypeInput],
    transactions: list[TxnInput],
    overrides: list[OverrideInput] | None = None,
) -> BillingResult:
    overrides = overrides or []
    if not owners:
        raise ValueError("Keine Eigentümer übergeben.")

    total_mea = _sum(o.mea for o in owners)
    if total_mea <= ZERO:
        raise ValueError("Die Summe der Miteigentumsanteile muss größer als 0 sein.")

    mea_fraction = {o.code: (o.mea / total_mea) for o in owners}
    owner_codes = [o.code for o in owners]
    ct_by_name = {ct.name: ct for ct in cost_types}

    # --- 1. Buchungen des Zeitraums je Kostenart ----------------------------- #
    in_period = [
        t for t in transactions if period.start_date <= t.booking_date <= period.end_date
    ]

    cash_by_cost_type: dict[str, Decimal] = {}
    hausgeld_paid: dict[str, Decimal] = dict.fromkeys(owner_codes, ZERO)
    sonderumlage_paid: dict[str, Decimal] = dict.fromkeys(owner_codes, ZERO)
    erstattung_paid: dict[str, Decimal] = dict.fromkeys(owner_codes, ZERO)
    investition_cash = ZERO
    reserve_zufuehrung: dict[str, Decimal] = dict.fromkeys(owner_codes, ZERO)
    reserve_entnahme: dict[str, Decimal] = dict.fromkeys(owner_codes, ZERO)

    for t in in_period:
        ct = ct_by_name.get(t.cost_type)
        kind = ct.kind if ct else "betriebskosten"

        if kind in ("betriebskosten", "investition"):
            # Ist-Kosten: Ausgaben (negativ) werden zu positiven Kosten.
            cash_by_cost_type[t.cost_type] = cash_by_cost_type.get(t.cost_type, ZERO) - t.amount
            if kind == "investition":
                investition_cash += -t.amount
        elif kind == "hausgeld":
            if t.owner in hausgeld_paid:
                hausgeld_paid[t.owner] += t.amount
        elif kind == "sonderumlage":
            if t.owner in sonderumlage_paid:
                sonderumlage_paid[t.owner] += t.amount
        elif kind == "erstattung":
            if t.owner in erstattung_paid:
                erstattung_paid[t.owner] += t.amount
        elif kind == "ruecklage":
            _apply_reserve_movement(
                t, owners, mea_fraction, reserve_zufuehrung, reserve_entnahme
            )

    override_by_ct: dict[str, dict[str, Decimal]] = {}
    for ov in overrides:
        override_by_ct.setdefault(ov.cost_type, {})[ov.owner] = ov.amount

    # --- 2. Umlageschlüssel je (umlagefähiger) Kostenart -------------------- #
    resolved: dict[str, dict[str, Decimal]] = {}
    cost_type_results: dict[str, CostTypeResult] = {}
    cost_type_order: list[str] = []

    umlage_cost_types = [
        ct for ct in cost_types if ct.kind in _UMLAGE_KINDS or ct.name in override_by_ct
    ]
    # Kostenarten ohne Stammsatz, aber mit Buchungen (defensiv):
    for name in cash_by_cost_type:
        if name not in ct_by_name:
            umlage_cost_types.append(CostTypeInput(name=name))

    for ct in _order_cost_types(umlage_cost_types):
        actual_total = cash_by_cost_type.get(ct.name, ZERO)
        ctx = AllocationContext(
            cost_type=ct,
            owners=owners,
            mea_fraction=mea_fraction,
            actual_total=actual_total,
            overrides=override_by_ct.get(ct.name, {}),
            resolved=resolved,
        )
        shares = get_strategy(ct.strategy)(ctx)
        # nur echte Eigentümer-Codes, in definierter Reihenfolge
        shares = {code: shares.get(code, ZERO) for code in owner_codes}
        resolved[ct.name] = shares

        cost_type_results[ct.name] = CostTypeResult(
            name=ct.name,
            category=ct.category,
            supplier=ct.supplier,
            strategy=ct.strategy,
            strategy_label=_STRATEGY_LABELS.get(ct.strategy, ct.strategy),
            actual_cash=actual_total,
            weg_total=_sum(shares.values()),
            shares=shares,
        )
        cost_type_order.append(ct.name)

    # --- 3.-8. je Eigentümer --------------------------------------------- #
    owner_results: dict[str, OwnerBillingResult] = {}
    for o in owners:
        cost_share = _sum(
            cost_type_results[name].share(o.code)
            for name in cost_type_order
            if ct_by_name.get(name, CostTypeInput(name=name)).kind in _UMLAGE_KINDS
            or name not in ct_by_name
        )
        investition_share = investition_cash * mea_fraction[o.code]
        guthaben = hausgeld_paid[o.code] - cost_share
        carryover = period.hausgeld_carryover.get(o.code, ZERO)
        erstattung = ZERO  # bewusst nicht verrechnet (siehe Plan)

        # Rücklagenbewegungen sind Umbuchungen zwischen Hausgeld- und Rücklagenkonto:
        # eine Zuführung fließt vom Hausgeldkonto ab, eine Entnahme fließt ihm zu.
        hausgeld_endsaldo = (
            carryover
            + sonderumlage_paid[o.code]
            - investition_share
            + guthaben
            + erstattung
            - reserve_zufuehrung[o.code]
            + reserve_entnahme[o.code]
        )

        reserve_opening = period.reserve_opening_balance * mea_fraction[o.code]
        reserve_endsaldo = (
            reserve_opening + reserve_zufuehrung[o.code] - reserve_entnahme[o.code]
        )

        owner_results[o.code] = OwnerBillingResult(
            code=o.code,
            name=o.name,
            mea=o.mea,
            mea_fraction=mea_fraction[o.code],
            cost_share_total=cost_share,
            hausgeld_paid=hausgeld_paid[o.code],
            guthaben=guthaben,
            carryover=carryover,
            sonderumlage_paid=sonderumlage_paid[o.code],
            investition_share=investition_share,
            erstattung=erstattung,
            hausgeld_endsaldo=hausgeld_endsaldo,
            reserve_opening=reserve_opening,
            reserve_zufuehrung=reserve_zufuehrung[o.code],
            reserve_entnahme=reserve_entnahme[o.code],
            reserve_endsaldo=reserve_endsaldo,
            total_saldo=hausgeld_endsaldo + reserve_endsaldo,
        )

    return BillingResult(
        period_start=period.start_date,
        period_end=period.end_date,
        total_mea=total_mea,
        owner_order=owner_codes,
        owners=owner_results,
        cost_type_order=cost_type_order,
        cost_types=cost_type_results,
        cost_share_total=_sum(r.cost_share_total for r in owner_results.values()),
        hausgeld_paid_total=_sum(r.hausgeld_paid for r in owner_results.values()),
        sonderumlage_total=_sum(r.sonderumlage_paid for r in owner_results.values()),
        investition_total=investition_cash,
        reserve_opening_total=period.reserve_opening_balance,
        reserve_endsaldo_total=_sum(r.reserve_endsaldo for r in owner_results.values()),
    )


def _apply_reserve_movement(
    t: TxnInput,
    owners: list[OwnerInput],
    mea_fraction: dict[str, Decimal],
    zufuehrung: dict[str, Decimal],
    entnahme: dict[str, Decimal],
) -> None:
    """Rücklagenbewegung verbuchen: eigentümerbezogen direkt, sonst nach MEA."""
    target = zufuehrung if t.amount >= ZERO else entnahme
    value = abs(t.amount)
    if t.owner in mea_fraction:
        target[t.owner] += value
    else:
        for o in owners:
            target[o.code] += value * mea_fraction[o.code]
