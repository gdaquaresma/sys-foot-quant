from __future__ import annotations

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from sys_foot_quant.market_engine.overround import (
    hold_percentage,
    remove_overround_proportional,
)


def test_remove_overround_sums_to_one() -> None:
    odds = {"home": 2.00, "draw": 3.40, "away": 4.00}
    fair = remove_overround_proportional(odds)
    assert sum(fair.values()) == pytest.approx(1.0, abs=1e-9)


def test_remove_overround_preserves_relative_ordering() -> None:
    odds = {"home": 1.50, "draw": 4.00, "away": 6.00}
    fair = remove_overround_proportional(odds)
    assert fair["home"] > fair["draw"] > fair["away"]


def test_hold_percentage_known_value() -> None:
    # -110/-110 americain classique ~ 1.909/1.909 decimal -> hold ~4.76%
    odds = {"a": 1.909, "b": 1.909}
    hold = hold_percentage(odds)
    assert hold == pytest.approx(0.0476, abs=1e-3)


def test_remove_overround_rejects_odds_at_or_below_one() -> None:
    with pytest.raises(ValueError):
        remove_overround_proportional({"home": 1.0, "away": 2.0})
    with pytest.raises(ValueError):
        remove_overround_proportional({"home": 0.9, "away": 2.0})


def test_remove_overround_rejects_empty_market() -> None:
    with pytest.raises(ValueError):
        remove_overround_proportional({})


@given(
    odds=st.lists(
        st.floats(min_value=1.01, max_value=50.0, allow_nan=False),
        min_size=2,
        max_size=5,
    )
)
@settings(max_examples=150)
def test_remove_overround_always_sums_to_one_and_stays_in_bounds(odds: list[float]) -> None:
    market = {f"sel_{i}": o for i, o in enumerate(odds)}
    fair = remove_overround_proportional(market)
    assert sum(fair.values()) == pytest.approx(1.0, abs=1e-6)
    for p in fair.values():
        assert 0.0 < p < 1.0


# ---------------------------------------------------------------------------
# Verification mathematique du round-trip : probabilites connues -> marge
# connue -> cotes -> retrait de marge -> probabilites reconstruites.
#
# C'est la preuve, demandee explicitement avant toute utilisation du
# benchmark "marche sans marge", que remove_overround_proportional
# reconstruit exactement les probabilites d'origine quand la marge a ete
# appliquee proportionnellement (ce que fait le generateur synthetique
# corrige, voir data_engine/synthetic/generator.py).
# ---------------------------------------------------------------------------


def _odds_from_probs_and_margin(probs: dict[str, float], margin: float) -> dict[str, float]:
    return {selection: 1.0 / (p * (1.0 + margin)) for selection, p in probs.items()}


def test_known_probabilities_and_margin_are_recovered_exactly() -> None:
    true_probs = {"home": 0.45, "draw": 0.28, "away": 0.27}
    margin = 0.05
    odds = _odds_from_probs_and_margin(true_probs, margin)

    # Sanity check intermediaire : le hold mesure doit correspondre exactement
    # a la marge appliquee (proprete du montage du test lui-meme).
    assert hold_percentage(odds) == pytest.approx(margin, abs=1e-9)

    recovered = remove_overround_proportional(odds)
    for selection, p in true_probs.items():
        assert recovered[selection] == pytest.approx(p, abs=1e-9)


def test_known_probabilities_survive_realistic_rounding_of_odds() -> None:
    # Reproduit la precision reelle du generateur (cotes arrondies a 3
    # decimales) : la reconstruction n'est plus exacte au bit pres, mais
    # doit rester tres proche (erreur induite par l'arrondi uniquement).
    true_probs = {"home": 0.52, "draw": 0.23, "away": 0.25}
    margin = 0.05
    raw_odds = _odds_from_probs_and_margin(true_probs, margin)
    rounded_odds = {selection: round(o, 3) for selection, o in raw_odds.items()}

    recovered = remove_overround_proportional(rounded_odds)
    for selection, p in true_probs.items():
        assert recovered[selection] == pytest.approx(p, abs=5e-4)


@given(
    raw=st.lists(
        st.floats(min_value=0.01, max_value=1.0, allow_nan=False), min_size=3, max_size=3
    ),
    margin=st.floats(min_value=0.0, max_value=0.20, allow_nan=False),
)
@settings(max_examples=150)
def test_round_trip_recovers_arbitrary_probability_simplex(raw: list[float], margin: float) -> None:
    total = sum(raw)
    true_probs = {f"sel_{i}": r / total for i, r in enumerate(raw)}
    # Cas limite hors perimetre de ce test : si une probabilite "vraie" est
    # si dominante qu'ajouter la marge la ferait depasser 1.0, la cote
    # decimale correspondante serait <= 1 (mathematiquement invalide) - ce
    # cas degenere (favori ecrasant + marge) est gere separement par un
    # garde-fou explicite au niveau du generateur synthetique, pas ici.
    assume(max(true_probs.values()) * (1.0 + margin) < 0.999)

    odds = _odds_from_probs_and_margin(true_probs, margin)
    recovered = remove_overround_proportional(odds)
    for selection in true_probs:
        assert recovered[selection] == pytest.approx(true_probs[selection], abs=1e-6)
    assert hold_percentage(odds) == pytest.approx(margin, abs=1e-9)
