from __future__ import annotations

import math

import pytest

from sys_foot_quant.final_engine.pricing import compute_fair_price


def test_fair_price_is_inverse_of_probability() -> None:
    fair_price = compute_fair_price({2.5: 0.5, 1.5: 0.8})
    assert fair_price[2.5] == pytest.approx(2.0)
    assert fair_price[1.5] == pytest.approx(1.25)


def test_zero_probability_yields_infinite_fair_price_not_an_error() -> None:
    fair_price = compute_fair_price({2.5: 0.0})
    assert math.isinf(fair_price[2.5])


def test_never_derives_fair_price_from_market_data() -> None:
    """La cote juste n'est calculee qu'a partir de la probabilite modele -
    verification par inspection de la signature (aucun parametre de marche
    possible)."""
    import inspect

    sig = inspect.signature(compute_fair_price)
    assert list(sig.parameters) == ["probabilities"]
