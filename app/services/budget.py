"""Wirtschaftsplan / Prognoserechnung – Aufbau des Monats-Grids.

Je Zelle (Monat × Kostenart) gilt: **manueller Wert** vor **Ist-Wert** (falls für
diesen Monat schon Buchungen vorliegen) vor **Vorschlag** (Wert desselben
Monats­index der Vorperiode). Der Anfangssaldo ist der Stand der Girokonten zu
Periodenbeginn; der laufende Saldo je Monat = vorheriger Saldo + Differenz.
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.locale import LOCALE
from app.models import Account, BillingPeriod, BudgetEntry, CostType, Transaction
from app.models.enums import AccountType, CostKind
from app.services.billing import account_balance_before
from app.services.periods import previous_period

ZERO = Decimal("0")

INCOME_KINDS = {CostKind.HAUSGELD, CostKind.SONDERUMLAGE}
EXPENSE_KINDS = {CostKind.BETRIEBSKOSTEN, CostKind.INVESTITION, CostKind.ERSTATTUNG}


# --------------------------------------------------------------------------- #
# Monatsfenster
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class MonthWindow:
    index: int
    label: str
    first_of_month: date
    start: date
    end: date


def _month_label(d: date) -> str:
    from babel.dates import format_date

    return format_date(d, "LLLL y", locale=LOCALE)


def month_windows(period: BillingPeriod) -> list[MonthWindow]:
    s, e = period.start_date, period.end_date
    n = (e.year - s.year) * 12 + (e.month - s.month) + 1
    out: list[MonthWindow] = []
    for i in range(max(n, 1)):
        y = s.year + (s.month - 1 + i) // 12
        m = (s.month - 1 + i) % 12 + 1
        first = date(y, m, 1)
        last = date(y, m, calendar.monthrange(y, m)[1])
        out.append(
            MonthWindow(
                index=i,
                label=_month_label(first),
                first_of_month=first,
                start=max(first, s),
                end=min(last, e),
            )
        )
    return out


def _window_index(windows: list[MonthWindow], d: date) -> int | None:
    for w in windows:
        if w.start <= d <= w.end:
            return w.index
    return None


def _signed(kind: CostKind, amount: Decimal) -> Decimal:
    """Ausgaben als positive Beträge, Einnahmen ebenfalls positiv."""
    return amount if kind in INCOME_KINDS else -amount


def _sums_by_cell(db: Session, windows: list[MonthWindow]) -> dict[tuple[int, int], Decimal]:
    """(cost_type_id, month_index) -> Summe (nur Zellen mit mindestens einer Buchung)."""
    if not windows:
        return {}
    overall_start = min(w.start for w in windows)
    overall_end = max(w.end for w in windows)
    rows = db.execute(
        select(Transaction.cost_type_id, Transaction.booking_date, Transaction.amount, CostType.kind)
        .join(CostType, Transaction.cost_type_id == CostType.id)
        .where(Transaction.booking_date >= overall_start, Transaction.booking_date <= overall_end)
    ).all()
    acc: dict[tuple[int, int], Decimal] = defaultdict(lambda: ZERO)
    for ct_id, bdate, amount, kind in rows:
        mi = _window_index(windows, bdate)
        if mi is None:
            continue
        acc[(ct_id, mi)] += _signed(kind, amount)
    return dict(acc)


# --------------------------------------------------------------------------- #
# Grid
# --------------------------------------------------------------------------- #
@dataclass
class BudgetCell:
    month_index: int
    cost_type_id: int
    manual: Decimal | None = None
    ist: Decimal | None = None
    vorschlag: Decimal | None = None

    @property
    def default_value(self) -> Decimal:
        if self.ist is not None:
            return self.ist
        if self.vorschlag is not None:
            return self.vorschlag
        return ZERO

    @property
    def effective(self) -> Decimal:
        return self.manual if self.manual is not None else self.default_value

    @property
    def source(self) -> str:
        if self.manual is not None:
            return "manuell"
        if self.ist is not None:
            return "ist"
        if self.vorschlag is not None:
            return "prognose"
        return "leer"


@dataclass
class BudgetMonth:
    index: int
    label: str
    start: date
    end: date
    cells: dict[int, BudgetCell]
    einnahmen: Decimal = ZERO
    ausgaben: Decimal = ZERO
    differenz: Decimal = ZERO
    saldo: Decimal = ZERO


@dataclass
class BudgetGrid:
    period: BillingPeriod
    anfangssaldo: Decimal
    anfangssaldo_source: str
    months: list[BudgetMonth]
    income_types: list[CostType]
    expense_types: list[CostType]
    totals: dict[int, Decimal] = field(default_factory=dict)
    total_einnahmen: Decimal = ZERO
    total_ausgaben: Decimal = ZERO
    total_differenz: Decimal = ZERO
    previous_period_label: str | None = None

    @property
    def endsaldo(self) -> Decimal:
        return self.months[-1].saldo if self.months else self.anfangssaldo


def _giro_opening(db: Session, period: BillingPeriod) -> tuple[Decimal, str]:
    accounts = list(
        db.scalars(select(Account).where(Account.type == AccountType.GIRO).order_by(Account.sort_order))
    )
    if not accounts:
        return ZERO, "kein Girokonto"
    total = sum((account_balance_before(db, a, period.start_date) for a in accounts), ZERO)
    names = ", ".join(f"„{a.name}“" for a in accounts)
    return total, f"Girokonto {names} zu Periodenbeginn"


def build_grid(db: Session, period: BillingPeriod) -> BudgetGrid:
    windows = month_windows(period)

    cost_types = list(
        db.scalars(select(CostType).where(CostType.active).order_by(CostType.sort_order, CostType.name))
    )
    income_types = [c for c in cost_types if c.kind in INCOME_KINDS]
    expense_types = [c for c in cost_types if c.kind in EXPENSE_KINDS]
    col_types = income_types + expense_types

    ist = _sums_by_cell(db, windows)
    prev = previous_period(db, period)
    vorschlag = _sums_by_cell(db, month_windows(prev)) if prev is not None else {}
    manual = {
        (e.month_index, e.cost_type_id): e.amount
        for e in db.scalars(select(BudgetEntry).where(BudgetEntry.period_id == period.id))
    }

    anfangssaldo, anfangssaldo_source = _giro_opening(db, period)

    months: list[BudgetMonth] = []
    totals: dict[int, Decimal] = {c.id: ZERO for c in col_types}
    running = anfangssaldo
    for w in windows:
        cells = {
            c.id: BudgetCell(
                month_index=w.index,
                cost_type_id=c.id,
                manual=manual.get((w.index, c.id)),
                ist=ist.get((c.id, w.index)),
                vorschlag=vorschlag.get((c.id, w.index)),
            )
            for c in col_types
        }
        einnahmen = sum((cells[c.id].effective for c in income_types), ZERO)
        ausgaben = sum((cells[c.id].effective for c in expense_types), ZERO)
        differenz = einnahmen - ausgaben
        running += differenz
        for c in col_types:
            totals[c.id] += cells[c.id].effective
        months.append(
            BudgetMonth(
                index=w.index, label=w.label, start=w.start, end=w.end, cells=cells,
                einnahmen=einnahmen, ausgaben=ausgaben, differenz=differenz, saldo=running,
            )
        )

    total_einnahmen = sum((totals[c.id] for c in income_types), ZERO)
    total_ausgaben = sum((totals[c.id] for c in expense_types), ZERO)
    return BudgetGrid(
        period=period,
        anfangssaldo=anfangssaldo,
        anfangssaldo_source=anfangssaldo_source,
        months=months,
        income_types=income_types,
        expense_types=expense_types,
        totals=totals,
        total_einnahmen=total_einnahmen,
        total_ausgaben=total_ausgaben,
        total_differenz=total_einnahmen - total_ausgaben,
        previous_period_label=prev.label if prev is not None else None,
    )


# --------------------------------------------------------------------------- #
# Speichern / Zurücksetzen
# --------------------------------------------------------------------------- #
def save_overrides(
    db: Session, period: BillingPeriod, values: dict[tuple[int, int], Decimal | None]
) -> int:
    """Nur Zellen speichern, die vom berechneten Default abweichen."""
    grid = build_grid(db, period)
    defaults = {
        (m.index, cid): cell.default_value
        for m in grid.months
        for cid, cell in m.cells.items()
    }
    existing = {
        (e.month_index, e.cost_type_id): e
        for e in db.scalars(select(BudgetEntry).where(BudgetEntry.period_id == period.id))
    }
    changed = 0
    for key, val in values.items():
        entry = existing.get(key)
        if val is None or val == defaults.get(key, ZERO):
            if entry is not None:
                db.delete(entry)
                changed += 1
        elif entry is not None:
            if entry.amount != val:
                entry.amount = val
                changed += 1
        else:
            db.add(
                BudgetEntry(
                    period_id=period.id, month_index=key[0], cost_type_id=key[1], amount=val
                )
            )
            changed += 1
    return changed


def reset(db: Session, period: BillingPeriod) -> int:
    n = db.query(BudgetEntry).filter(BudgetEntry.period_id == period.id).delete()
    return n


# --------------------------------------------------------------------------- #
# Jahresvergleich (zwei Wirtschaftspläne gegenüberstellen)
# --------------------------------------------------------------------------- #
@dataclass
class DiffPair:
    """Wert des Wirtschaftsjahres (``a``) und des Vergleichsjahres (``b``)."""

    a: Decimal = ZERO
    b: Decimal = ZERO

    @property
    def diff(self) -> Decimal:
        return self.a - self.b


@dataclass
class CompareMonth:
    index: int
    label: str
    einnahmen: DiffPair
    ausgaben: DiffPair
    differenz: DiffPair
    cells: dict[int, DiffPair]


@dataclass
class CompareGrid:
    period: BillingPeriod
    base_period: BillingPeriod
    months: list[CompareMonth]
    income_types: list[CostType]
    expense_types: list[CostType]
    totals: dict[int, DiffPair]
    total_einnahmen: DiffPair
    total_ausgaben: DiffPair
    total_differenz: DiffPair
    anfangssaldo: DiffPair


def _union_cost_types(xs: list[CostType], ys: list[CostType]) -> list[CostType]:
    by_id: dict[int, CostType] = {c.id: c for c in xs}
    for c in ys:
        by_id.setdefault(c.id, c)
    return sorted(by_id.values(), key=lambda c: (c.sort_order, c.name))


def build_comparison(
    db: Session, period: BillingPeriod, base_period: BillingPeriod
) -> CompareGrid:
    """Stellt die Wirtschaftsplan-Werte zweier Perioden je Monat und Kostenart
    gegenüber (Monatsindex ↔ Monatsindex). Angezeigt wird jeweils die Differenz
    ``Wirtschaftsjahr − Vergleichsjahr``."""
    ga = build_grid(db, period)
    gb = build_grid(db, base_period)

    income_types = _union_cost_types(ga.income_types, gb.income_types)
    expense_types = _union_cost_types(ga.expense_types, gb.expense_types)
    col_types = income_types + expense_types

    a_by_i = {m.index: m for m in ga.months}
    b_by_i = {m.index: m for m in gb.months}

    def _cell(m: BudgetMonth | None, ct_id: int) -> Decimal:
        if m is None or ct_id not in m.cells:
            return ZERO
        return m.cells[ct_id].effective

    months: list[CompareMonth] = []
    for i in sorted(set(a_by_i) | set(b_by_i)):
        ma, mb = a_by_i.get(i), b_by_i.get(i)
        months.append(
            CompareMonth(
                index=i,
                label=(ma or mb).label,
                einnahmen=DiffPair(ma.einnahmen if ma else ZERO, mb.einnahmen if mb else ZERO),
                ausgaben=DiffPair(ma.ausgaben if ma else ZERO, mb.ausgaben if mb else ZERO),
                differenz=DiffPair(ma.differenz if ma else ZERO, mb.differenz if mb else ZERO),
                cells={c.id: DiffPair(_cell(ma, c.id), _cell(mb, c.id)) for c in col_types},
            )
        )

    return CompareGrid(
        period=period,
        base_period=base_period,
        months=months,
        income_types=income_types,
        expense_types=expense_types,
        totals={
            c.id: DiffPair(ga.totals.get(c.id, ZERO), gb.totals.get(c.id, ZERO))
            for c in col_types
        },
        total_einnahmen=DiffPair(ga.total_einnahmen, gb.total_einnahmen),
        total_ausgaben=DiffPair(ga.total_ausgaben, gb.total_ausgaben),
        total_differenz=DiffPair(ga.total_differenz, gb.total_differenz),
        anfangssaldo=DiffPair(ga.anfangssaldo, gb.anfangssaldo),
    )
