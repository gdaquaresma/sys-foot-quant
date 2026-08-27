from __future__ import annotations

import pytest

from sys_foot_quant.market_engine.model_vs_market import compare_model_to_market


def test_implied_prob_raw_is_one_over_odds() -> None:
    result = compare_model_to_market(
        model_probs={"home": 0.5, "draw": 0.3, "away": 0.2},
        market_odds={"home": 2.0, "draw": 3.5, "away": 4.0},
    )
    assert result["implied_prob_raw"]["home"] == pytest.approx(0.5)
    assert result["implied_prob_raw"]["draw"] == pytest.approx(1 / 3.5)
    assert result["implied_prob_raw"]["away"] == pytest.approx(0.25)


def test_overround_matches_hand_computation() -> None:
    odds = {"home": 2.0, "draw": 3.5, "away": 4.0}
    result = compare_model_to_market(model_probs={"home": 0.5, "draw": 0.3, "away": 0.2}, market_odds=odds)
    expected_overround = (1 / 2.0 + 1 / 3.5 + 1 / 4.0) - 1.0
    assert result["overround"] == pytest.approx(expected_overround)


def test_normalized_probabilities_sum_to_one() -> None:
    result = compare_model_to_market(
        model_probs={"home": 0.5, "draw": 0.3, "away": 0.2},
        market_odds={"home": 1.9, "draw": 3.6, "away": 4.2},
    )
    total = sum(result["implied_prob_normalized"].values())
    assert total == pytest.approx(1.0)


def test_model_minus_market_diff_matches_hand_computation() -> None:
    model_probs = {"home": 0.55, "draw": 0.25, "away": 0.20}
    market_odds = {"home": 1.9, "draw": 3.6, "away": 4.2}
    result = compare_model_to_market(model_probs=model_probs, market_odds=market_odds)
    for sel in model_probs:
        expected = model_probs[sel] - result["implied_prob_normalized"][sel]
        assert result["model_minus_market"][sel] == pytest.approx(expected)


def test_mismatched_selections_raise() -> None:
    with pytest.raises(ValueError):
        compare_model_to_market(
            model_probs={"home": 0.5, "draw": 0.3, "away": 0.2},
            market_odds={"home": 2.0, "draw": 3.5},
        )


def test_invalid_odds_below_one_raises() -> None:
    with pytest.raises(ValueError):
        compare_model_to_market(
            model_probs={"home": 0.5, "draw": 0.3, "away": 0.2},
            market_odds={"home": 0.9, "draw": 3.5, "away": 4.0},
        )


def test_output_never_computes_roi_yield_clv_or_staking_fields() -> None:
    result = compare_model_to_market(
        model_probs={"home": 0.5, "draw": 0.3, "away": 0.2},
        market_odds={"home": 2.0, "draw": 3.5, "away": 4.0},
    )
    forbidden = {"roi", "yield", "clv", "stake", "kelly", "edge_threshold", "pnl", "profit"}
    assert forbidden.isdisjoint(result.keys())
