from __future__ import annotations

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from sys_foot_quant.market_engine.overround import remove_overround_proportional
from sys_foot_quant.market_engine.shin import (
    compare_overround_methods,
    remove_overround_shin,
    shin_z,
)


def test_shin_degenerates_to_proportional_when_no_margin() -> None:
    # Cotes construites pour sommer exactement a 1 en probabilite implicite
    # (Total=1) : z=0 est solution triviale, Shin == proportionnel.
    odds = {"home": 2.0, "draw": 4.0, "away": 4.0}  # 0.5+0.25+0.25 = 1.0
    prop = remove_overround_proportional(odds)
    shin = remove_overround_shin(odds)
    z = shin_z(odds)

    assert z == pytest.approx(0.0, abs=1e-9)
    for sel in odds:
        assert shin[sel] == pytest.approx(prop[sel], abs=1e-9)


def test_shin_probabilities_sum_to_one() -> None:
    odds = {"home": 1.80, "draw": 3.60, "away": 4.50}
    fair = remove_overround_shin(odds)
    assert sum(fair.values()) == pytest.approx(1.0, abs=1e-6)


def test_shin_z_is_non_negative_and_bounded() -> None:
    odds = {"home": 1.50, "draw": 4.20, "away": 6.50}
    z = shin_z(odds)
    assert 0.0 <= z < 0.5


def test_shin_differs_from_proportional_when_margin_present() -> None:
    odds = {"home": 1.80, "draw": 3.60, "away": 4.50}
    prop = remove_overround_proportional(odds)
    shin = remove_overround_shin(odds)
    assert any(abs(prop[s] - shin[s]) > 1e-6 for s in odds)


def test_compare_overround_methods_returns_consistent_summary() -> None:
    odds = {"home": 1.80, "draw": 3.60, "away": 4.50}
    result = compare_overround_methods(odds)
    assert set(result.keys()) == {"proportional", "shin", "shin_z", "hold", "max_abs_diff"}
    assert result["hold"] > 0.0
    assert result["max_abs_diff"] >= 0.0
    assert sum(result["proportional"].values()) == pytest.approx(1.0, abs=1e-6)
    assert sum(result["shin"].values()) == pytest.approx(1.0, abs=1e-6)


def test_shin_rejects_invalid_odds() -> None:
    with pytest.raises(ValueError):
        remove_overround_shin({"home": 1.0, "away": 2.0})
    with pytest.raises(ValueError):
        remove_overround_shin({})


def test_shin_rejects_arbitrage_market() -> None:
    # Somme des probabilites implicites < 1 (marche d'arbitrage) : Shin
    # suppose une marge non negative, cas explicitement hors perimetre.
    odds = {"home": 2.20, "away": 2.20}  # 1/2.2 + 1/2.2 = 0.909 < 1
    with pytest.raises(ValueError, match="marge non negative"):
        remove_overround_shin(odds)
    with pytest.raises(ValueError, match="marge non negative"):
        shin_z(odds)


def test_shin_raises_clearly_on_unrealistically_extreme_margin() -> None:
    # Marge de 60% (deux cotes a 1.25) : hors du domaine de validite
    # numerique retenu (z borne a [0, 0.5]) - aucun bookmaker reel ne
    # publie une marge de cet ordre ; on verifie une erreur explicite
    # plutot qu'un resultat silencieusement faux.
    odds = {"home": 1.25, "away": 1.25}
    with pytest.raises(ValueError, match="Impossible de resoudre"):
        remove_overround_shin(odds)


def _realistic_market(raw_probs: list[float], margin: float) -> dict[str, float]:
    """Construit un marche a marge REALISTE et CONNUE par construction
    (plutot que de filtrer des cotes tirees au hasard, dont la marge
    resultante est presque toujours degenree - trop faible/negative ou
    absurdement elevee). Evite l'ecueil "filtre trop d'exemples" tout en
    couvrant un large espace de distributions de probabilite."""
    total = sum(raw_probs)
    true_probs = [r / total for r in raw_probs]
    implied_with_margin = [p * (1.0 + margin) for p in true_probs]
    return {f"sel_{i}": 1.0 / p for i, p in enumerate(implied_with_margin)}


@given(
    raw_probs=st.lists(
        st.floats(min_value=0.01, max_value=1.0, allow_nan=False), min_size=2, max_size=5
    ),
    margin=st.floats(min_value=0.0, max_value=0.20, allow_nan=False),
)
@settings(max_examples=150)
def test_shin_always_sums_to_one_and_stays_in_bounds(raw_probs, margin) -> None:
    market = _realistic_market(raw_probs, margin)
    # Cas limite hors perimetre (favori si ecrasant que la cote impliquee
    # touche 1.0) : deja couvert explicitement par
    # test_shin_raises_clearly_on_unrealistically_extreme_margin.
    assume(min(market.values()) > 1.01)
    fair = remove_overround_shin(market)
    assert sum(fair.values()) == pytest.approx(1.0, abs=1e-6)
    for p in fair.values():
        assert 0.0 < p < 1.0


@given(
    raw_probs=st.lists(
        st.floats(min_value=0.01, max_value=1.0, allow_nan=False), min_size=2, max_size=5
    ),
    margin=st.floats(min_value=0.0, max_value=0.20, allow_nan=False),
)
@settings(max_examples=150)
def test_shin_z_always_in_valid_range(raw_probs, margin) -> None:
    market = _realistic_market(raw_probs, margin)
    assume(min(market.values()) > 1.01)
    z = shin_z(market)
    assert 0.0 <= z < 0.5
