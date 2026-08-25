from __future__ import annotations

from datetime import datetime, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.value_engine.selection import ValueCandidate, build_value_candidates

_T = datetime(2024, 1, 1, tzinfo=timezone.utc)


def test_min_edge_and_min_ev_are_required_keyword_arguments() -> None:
    # Aucun defaut : un appel sans min_edge/min_ev doit echouer a
    # l'appel, pas silencieusement utiliser un seuil non assume.
    with pytest.raises(TypeError):
        build_value_candidates(  # type: ignore[call-arg]
            1, _T, (0.5, 0.3, 0.2), (0.4, 0.3, 0.3), {"home": 2.5, "draw": 3.3, "away": 5.0}
        )


def test_positive_ev_alone_does_not_pass_thresholds() -> None:
    # Construit un cas ou l'EV est strictement positive mais l'edge est
    # nul (model_prob == market_fair_prob) : precisement le cas que le
    # cahier des charges interdit de considerer comme "value" a lui seul.
    model_probs = (0.50, 0.30, 0.20)
    market_fair_probs = (0.50, 0.30, 0.20)  # edge = 0 pour toutes les issues
    odds = {"home": 2.10, "draw": 3.30, "away": 5.00}  # EV("home") = 0.5*2.10-1 = +0.05 > 0

    candidates = build_value_candidates(
        1, _T, model_probs, market_fair_probs, odds, min_edge=0.0, min_ev=0.0
    )
    home = next(c for c in candidates if c.selection == "home")
    assert home.ev > 0.0
    assert home.edge == pytest.approx(0.0, abs=1e-9)
    # edge=0 n'est pas STRICTEMENT superieur au seuil min_edge=0.0 :
    assert home.passes_thresholds is False


def test_both_edge_and_ev_must_exceed_thresholds() -> None:
    model_probs = (0.55, 0.25, 0.20)
    market_fair_probs = (0.50, 0.30, 0.20)  # edge("home") = +0.05
    odds = {"home": 2.10, "draw": 3.30, "away": 5.00}  # EV("home") = 0.55*2.10-1=+0.155

    passing = build_value_candidates(
        1, _T, model_probs, market_fair_probs, odds, min_edge=0.02, min_ev=0.02
    )
    home = next(c for c in passing if c.selection == "home")
    assert home.passes_thresholds is True

    # Seuil d'edge impossible a atteindre : plus aucun candidat ne passe,
    # meme si l'EV reste tres largement positive.
    stricter = build_value_candidates(
        1, _T, model_probs, market_fair_probs, odds, min_edge=0.50, min_ev=0.02
    )
    home_strict = next(c for c in stricter if c.selection == "home")
    assert home_strict.ev > 0.0
    assert home_strict.passes_thresholds is False


def test_build_value_candidates_skips_selections_missing_from_odds() -> None:
    model_probs = (0.5, 0.3, 0.2)
    market_fair_probs = (0.5, 0.3, 0.2)
    odds = {"home": 2.0, "draw": 3.3}  # pas de cote "away"

    candidates = build_value_candidates(
        1, _T, model_probs, market_fair_probs, odds, min_edge=0.0, min_ev=0.0
    )
    assert {c.selection for c in candidates} == {"home", "draw"}


def test_rejects_malformed_probability_tuples() -> None:
    with pytest.raises(ValueError):
        build_value_candidates(
            1, _T, (0.5, 0.5), (0.5, 0.3, 0.2), {"home": 2.0}, min_edge=0.0, min_ev=0.0
        )


@given(
    model_home=st.floats(min_value=0.05, max_value=0.95, allow_nan=False),
    market_home=st.floats(min_value=0.05, max_value=0.95, allow_nan=False),
    odds_home=st.floats(min_value=1.05, max_value=20.0, allow_nan=False),
    min_edge=st.floats(min_value=0.0, max_value=0.5, allow_nan=False),
    min_ev=st.floats(min_value=0.0, max_value=0.5, allow_nan=False),
)
@settings(max_examples=200)
def test_passes_thresholds_never_true_without_both_conditions(
    model_home, market_home, odds_home, min_edge, min_ev
) -> None:
    remainder_model = (1.0 - model_home) / 2
    remainder_market = (1.0 - market_home) / 2
    model_probs = (model_home, remainder_model, remainder_model)
    market_probs = (market_home, remainder_market, remainder_market)
    odds = {"home": odds_home, "draw": 5.0, "away": 5.0}

    candidates = build_value_candidates(
        1, _T, model_probs, market_probs, odds, min_edge=min_edge, min_ev=min_ev
    )
    home = next(c for c in candidates if c.selection == "home")
    if home.passes_thresholds:
        assert home.edge > min_edge
        assert home.ev > min_ev
    else:
        assert home.edge <= min_edge or home.ev <= min_ev
