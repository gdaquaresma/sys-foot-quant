from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.calibration_engine.goodness_of_fit import poisson_goodness_of_fit


def test_rejects_empty_input() -> None:
    with pytest.raises(ValueError):
        poisson_goodness_of_fit([], np.array([]), np.array([]))


def test_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError):
        poisson_goodness_of_fit([(1.0, 1.0), (1.0, 1.0)], np.array([1]), np.array([1]))


def test_table_observed_sums_to_n_matches() -> None:
    rng = np.random.default_rng(0)
    lambdas_mus = [(1.4, 1.1)] * 200
    home = rng.poisson(1.4, size=200)
    away = rng.poisson(1.1, size=200)
    result = poisson_goodness_of_fit(lambdas_mus, home, away, max_goals_per_side=3)
    assert result.table["observed"].sum() == 200
    assert result.n_matches == 200


def test_table_expected_sums_close_to_n_matches() -> None:
    lambdas_mus = [(1.4, 1.1)] * 50
    home = np.zeros(50, dtype=int)
    away = np.zeros(50, dtype=int)
    result = poisson_goodness_of_fit(lambdas_mus, home, away, max_goals_per_side=3)
    assert result.table["expected"].sum() == pytest.approx(50, abs=1e-6)


def test_data_generated_from_the_model_itself_is_not_rejected() -> None:
    # Les scores sont tires EXACTEMENT de la loi que le modele predit :
    # le test ne doit (tres probablement) pas rejeter H0.
    rng = np.random.default_rng(42)
    n = 800
    lambdas = rng.uniform(0.8, 2.2, size=n)
    mus = rng.uniform(0.6, 1.8, size=n)
    home = rng.poisson(lambdas)
    away = rng.poisson(mus)
    lambdas_mus = list(zip(lambdas.tolist(), mus.tolist()))

    result = poisson_goodness_of_fit(lambdas_mus, home, away, max_goals_per_side=3)
    assert result.is_valid
    assert result.p_value > 0.05


def test_clearly_mismatched_predictions_are_rejected() -> None:
    # Le modele predit des scores tres faibles (lambda=0.3) alors que les
    # buts observes suivent en realite une loi tres offensive (lambda=4) :
    # inadequation flagrante, doit etre detectee.
    rng = np.random.default_rng(1)
    n = 500
    home = rng.poisson(4.0, size=n)
    away = rng.poisson(4.0, size=n)
    lambdas_mus = [(0.3, 0.3)] * n

    result = poisson_goodness_of_fit(lambdas_mus, home, away, max_goals_per_side=3)
    assert result.p_value < 0.001


def test_is_valid_false_when_sample_too_small_for_grid() -> None:
    # 5 matchs pour une grille (max_goals_per_side=5) a 37 categories :
    # effectifs attendus necessairement tres inferieurs a 5.
    lambdas_mus = [(1.3, 1.1)] * 5
    home = np.array([1, 0, 2, 1, 0])
    away = np.array([1, 1, 0, 0, 1])
    result = poisson_goodness_of_fit(lambdas_mus, home, away, max_goals_per_side=5)
    assert not result.is_valid
    assert result.min_expected_count < 5.0


def test_statistic_and_dof_are_consistent() -> None:
    lambdas_mus = [(1.3, 1.1)] * 30
    home = np.zeros(30, dtype=int)
    away = np.zeros(30, dtype=int)
    result = poisson_goodness_of_fit(lambdas_mus, home, away, max_goals_per_side=2)
    # grille 3x3 + 'autre' = 10 categories -> dof = 9
    assert result.dof == 9
    assert result.statistic >= 0


@given(
    lambdas=st.lists(st.floats(min_value=0.1, max_value=5.0), min_size=5, max_size=60),
)
@settings(max_examples=30)
def test_statistic_always_non_negative_and_p_value_in_unit_interval(lambdas) -> None:
    rng = np.random.default_rng(7)
    n = len(lambdas)
    lambdas_arr = np.array(lambdas)
    mus_arr = np.array(lambdas[::-1])
    home = rng.poisson(lambdas_arr)
    away = rng.poisson(mus_arr)
    lambdas_mus = list(zip(lambdas_arr.tolist(), mus_arr.tolist()))

    result = poisson_goodness_of_fit(lambdas_mus, home, away, max_goals_per_side=3)
    assert result.statistic >= 0
    assert 0.0 <= result.p_value <= 1.0
