from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.risk_engine.simulation import (
    BetScenario,
    MonteCarloSummary,
    _generate_outcomes,
    compare_flat_vs_kelly,
    flat_stake_fn,
    kelly_stake_fn,
    simulate_bankroll_paths,
    summarize_paths,
)


def test_bet_scenario_rejects_invalid_prob() -> None:
    with pytest.raises(ValueError):
        BetScenario(true_prob=-0.1, odds=2.0)
    with pytest.raises(ValueError):
        BetScenario(true_prob=1.1, odds=2.0)


def test_bet_scenario_rejects_invalid_odds() -> None:
    with pytest.raises(ValueError):
        BetScenario(true_prob=0.5, odds=1.0)


def test_generate_outcomes_reproducible_with_same_seed() -> None:
    scenarios = [BetScenario(0.5, 2.0) for _ in range(10)]
    out1 = _generate_outcomes(scenarios, n_simulations=20, seed=42)
    out2 = _generate_outcomes(scenarios, n_simulations=20, seed=42)
    assert np.array_equal(out1, out2)


def test_generate_outcomes_differs_with_different_seed() -> None:
    scenarios = [BetScenario(0.5, 2.0) for _ in range(20)]
    out1 = _generate_outcomes(scenarios, n_simulations=20, seed=1)
    out2 = _generate_outcomes(scenarios, n_simulations=20, seed=2)
    assert not np.array_equal(out1, out2)


def test_generate_outcomes_rejects_empty_scenarios() -> None:
    with pytest.raises(ValueError):
        _generate_outcomes([], n_simulations=10, seed=0)


def test_simulate_bankroll_paths_deterministic_when_always_wins() -> None:
    scenarios = [BetScenario(true_prob=1.0, odds=2.0)] * 3
    outcomes = np.ones((5, 3), dtype=bool)
    stake_fn = flat_stake_fn(1000.0, 0.1)
    paths = simulate_bankroll_paths(1000.0, scenarios, stake_fn, outcomes)
    expected_row = [1000.0, 1100.0, 1200.0, 1300.0]
    for row in paths:
        assert list(row) == pytest.approx(expected_row)


def test_simulate_bankroll_paths_never_goes_negative_with_oversized_stake_fn() -> None:
    scenarios = [BetScenario(true_prob=0.5, odds=2.0)] * 5
    outcomes = _generate_outcomes(scenarios, n_simulations=10, seed=7)

    def _oversized_stake_fn(balance: float, scenario: BetScenario) -> float:
        return balance * 10.0  # deliberately absurd, must be capped

    paths = simulate_bankroll_paths(1000.0, scenarios, _oversized_stake_fn, outcomes)
    assert np.all(paths >= 0.0)


def test_simulate_bankroll_paths_rejects_shape_mismatch() -> None:
    scenarios = [BetScenario(0.5, 2.0)] * 3
    outcomes = np.ones((2, 4), dtype=bool)
    with pytest.raises(ValueError):
        simulate_bankroll_paths(1000.0, scenarios, flat_stake_fn(1000.0, 0.1), outcomes)


def test_kelly_stake_fn_rejects_non_positive_multiplier() -> None:
    with pytest.raises(ValueError):
        kelly_stake_fn(0.0)
    with pytest.raises(ValueError):
        kelly_stake_fn(-0.5)


def test_kelly_stake_fn_no_bet_without_edge() -> None:
    # true_prob correspond exactement a la probabilite implicite de la
    # cote -> edge nul -> kelly_fraction <= 0 -> mise nulle.
    fn = kelly_stake_fn(1.0)
    stake = fn(1000.0, BetScenario(true_prob=0.5, odds=2.0))
    assert stake == pytest.approx(0.0)


def test_summarize_paths_known_values() -> None:
    paths = np.array(
        [
            [1000.0, 1100.0, 1200.0],
            [1000.0, 900.0, 800.0],
        ]
    )
    summary = summarize_paths(paths, "test", ruin_threshold_fraction=0.85)
    assert isinstance(summary, MonteCarloSummary)
    assert summary.n_simulations == 2
    assert summary.median_final_balance == pytest.approx((1200.0 + 800.0) / 2)
    # Simulation 2 finit a 800 < 850 (85% de 1000) -> ruine ; simulation 1 non.
    assert summary.prob_ruin == pytest.approx(0.5)
    assert summary.median_max_drawdown_pct == pytest.approx((0.0 + -20.0) / 2)


def test_compare_flat_vs_kelly_paired_on_same_outcomes() -> None:
    # Avec true_prob=0 (aucun gain possible), Kelly (edge toujours <= 0)
    # ne mise jamais -> bankroll inchangee ; Flat mise a chaque pas ->
    # perte garantie. Le contraste isole bien l'effet de la strategie de
    # mise sur un flux d'issues identique.
    scenarios = [BetScenario(true_prob=0.0, odds=2.0)] * 10
    result = compare_flat_vs_kelly(
        initial_bankroll=1000.0,
        scenarios=scenarios,
        flat_fraction=0.05,
        kelly_multiplier=0.5,
        n_simulations=20,
        seed=3,
    )
    assert result["kelly"].median_final_balance == pytest.approx(1000.0)
    assert result["flat"].median_final_balance < 1000.0


def test_compare_flat_vs_kelly_full_kelly_has_higher_volatility_than_quarter() -> None:
    # Scenario avec edge reel et constant (true_prob > implied prob) :
    # Full Kelly doit presenter une volatilite inter-simulations plus
    # elevee que Quarter-Kelly - propriete classique de la litterature
    # Kelly (research framework, section D1), pas un choix ajuste ici.
    scenarios = [BetScenario(true_prob=0.55, odds=2.0)] * 40
    result_full = compare_flat_vs_kelly(
        initial_bankroll=1000.0,
        scenarios=scenarios,
        flat_fraction=0.02,
        kelly_multiplier=1.0,
        n_simulations=300,
        seed=11,
    )
    result_quarter = compare_flat_vs_kelly(
        initial_bankroll=1000.0,
        scenarios=scenarios,
        flat_fraction=0.02,
        kelly_multiplier=0.25,
        n_simulations=300,
        seed=11,
    )
    assert result_full["kelly"].volatility_pct > result_quarter["kelly"].volatility_pct


@given(
    true_prob=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    odds=st.floats(min_value=1.01, max_value=10.0, allow_nan=False),
    kelly_multiplier=st.floats(min_value=0.01, max_value=1.0, allow_nan=False),
)
@settings(max_examples=40)
def test_kelly_strategy_paths_never_negative(true_prob, odds, kelly_multiplier) -> None:
    scenarios = [BetScenario(true_prob=true_prob, odds=odds)] * 5
    outcomes = _generate_outcomes(scenarios, n_simulations=10, seed=99)
    paths = simulate_bankroll_paths(1000.0, scenarios, kelly_stake_fn(kelly_multiplier), outcomes)
    assert np.all(paths >= -1e-9)
