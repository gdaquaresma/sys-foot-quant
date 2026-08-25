from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.value_engine.edge import edge, expected_value


def test_expected_value_known_case() -> None:
    # p=0.5, cote=2.10 -> EV = 0.5*2.10 - 1 = 0.05
    assert expected_value(0.5, 2.10) == pytest.approx(0.05, abs=1e-9)


def test_expected_value_fair_odds_gives_zero_ev() -> None:
    # cote "juste" (sans marge) pour p=0.4 est 1/0.4=2.5 -> EV=0
    assert expected_value(0.4, 2.5) == pytest.approx(0.0, abs=1e-9)


def test_expected_value_rejects_invalid_prob() -> None:
    with pytest.raises(ValueError):
        expected_value(-0.1, 2.0)
    with pytest.raises(ValueError):
        expected_value(1.1, 2.0)


def test_expected_value_rejects_invalid_odds() -> None:
    with pytest.raises(ValueError):
        expected_value(0.5, 1.0)
    with pytest.raises(ValueError):
        expected_value(0.5, 0.5)


def test_edge_known_case() -> None:
    assert edge(0.55, 0.50) == pytest.approx(0.05, abs=1e-9)
    assert edge(0.40, 0.50) == pytest.approx(-0.10, abs=1e-9)


def test_edge_rejects_invalid_probs() -> None:
    with pytest.raises(ValueError):
        edge(-0.1, 0.5)
    with pytest.raises(ValueError):
        edge(0.5, 1.5)


@given(
    model_prob=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    odds=st.floats(min_value=1.001, max_value=1000.0, allow_nan=False),
)
@settings(max_examples=150)
def test_expected_value_bounds(model_prob: float, odds: float) -> None:
    ev = expected_value(model_prob, odds)
    assert ev >= -1.0
    assert ev <= model_prob * odds  # borne triviale mais verifie l'absence d'explosion


@given(
    model_prob=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    market_fair_prob=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
)
@settings(max_examples=150)
def test_edge_bounds(model_prob: float, market_fair_prob: float) -> None:
    e = edge(model_prob, market_fair_prob)
    assert -1.0 <= e <= 1.0


@given(
    model_prob=st.floats(min_value=0.001, max_value=0.999, allow_nan=False),
)
@settings(max_examples=100)
def test_expected_value_is_zero_at_fair_odds(model_prob: float) -> None:
    fair_odds = 1.0 / model_prob
    assert expected_value(model_prob, fair_odds) == pytest.approx(0.0, abs=1e-9)
