"""Isolierte Tests der einzelnen Umlageschlüssel-Strategien."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.allocation.strategies import (
    AllocationContext,
    available_strategies,
    get_strategy,
)
from app.allocation.types import CostTypeInput, OwnerInput

OWNERS = [
    OwnerInput("E1", Decimal("266.01")),
    OwnerInput("E2", Decimal("382")),
    OwnerInput("E3", Decimal("152.5")),
    OwnerInput("E4", Decimal("199.49")),
]
TOTAL_MEA = sum((o.mea for o in OWNERS), Decimal("0"))
FRAC = {o.code: o.mea / TOTAL_MEA for o in OWNERS}


def ctx(cost_type, actual_total="0", overrides=None, resolved=None):
    return AllocationContext(
        cost_type=cost_type,
        owners=OWNERS,
        mea_fraction=FRAC,
        actual_total=Decimal(actual_total),
        overrides=overrides or {},
        resolved=resolved or {},
    )


def test_registry_kennt_alle_schluessel():
    assert set(available_strategies()) == {"mea", "zaehler", "vorauszahlung", "proportional"}


def test_unbekannter_schluessel_wirft():
    with pytest.raises(ValueError):
        get_strategy("gibtsnicht")


def test_mea_verteilt_nach_anteilen():
    ct = CostTypeInput("X", strategy="mea")
    shares = get_strategy("mea")(ctx(ct, actual_total="1000"))
    assert sum(shares.values()) == Decimal("1000")
    assert shares["E2"] == Decimal("1000") * FRAC["E2"]


def test_zaehler_nimmt_direkteingaben():
    ct = CostTypeInput("X", strategy="zaehler")
    ov = {"E1": Decimal("100"), "E2": Decimal("200")}
    shares = get_strategy("zaehler")(ctx(ct, actual_total="0", overrides=ov))
    assert shares == {"E1": Decimal("100"), "E2": Decimal("200"), "E3": Decimal("0"), "E4": Decimal("0")}


def test_vorauszahlung_ist_immer_null():
    ct = CostTypeInput("X", strategy="vorauszahlung")
    shares = get_strategy("vorauszahlung")(ctx(ct, actual_total="5000"))
    assert set(shares.values()) == {Decimal("0")}


def test_proportional_folgt_bezugskostenart():
    ct = CostTypeInput("Abschlag", strategy="proportional", proportional_to="Heiz")
    base = {"E1": Decimal("60"), "E2": Decimal("40"), "E3": Decimal("0"), "E4": Decimal("0")}
    shares = get_strategy("proportional")(
        ctx(ct, actual_total="1000", resolved={"Heiz": base})
    )
    assert shares["E1"] == Decimal("600")
    assert shares["E2"] == Decimal("400")
    assert sum(shares.values()) == Decimal("1000")


def test_proportional_faellt_auf_mea_zurueck_wenn_basis_null():
    ct = CostTypeInput("Abschlag", strategy="proportional", proportional_to="Heiz")
    shares = get_strategy("proportional")(
        ctx(ct, actual_total="1000", resolved={"Heiz": dict.fromkeys(FRAC, Decimal("0"))})
    )
    assert sum(shares.values()) == Decimal("1000")
    assert shares["E2"] == Decimal("1000") * FRAC["E2"]
