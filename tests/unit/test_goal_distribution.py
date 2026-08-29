from __future__ import annotations

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.football_model.goal_distribution import (
    DEFAULT_MAX_BUCKET,
    DEFAULT_OU_THRESHOLDS,
    check_distribution_validity,
    check_over_under_matches_distribution,
    check_over_under_monotonic,
    over_under_probs,
    total_goals_distribution,
)
from sys_foot_quant.football_model.scoring import score_matrix


def _normalized_matrix(lam: float, mu: float, max_goals: int = 20) -> np.ndarray:
    m = score_matrix(lam, mu, max_goals=max_goals)
    return m / m.sum()


def test_default_thresholds_are_the_five_official_ou_lines() -> None:
    assert DEFAULT_OU_THRESHOLDS == (0.5, 1.5, 2.5, 3.5, 4.5)


def test_over_under_probs_matches_hand_computation_for_small_matrix() -> None:
    # Matrice 3x3 triviale : P(0,0)=0.5, P(1,0)=0.3, P(0,1)=0.2 (le reste nul).
    matrix = np.zeros((3, 3))
    matrix[0, 0] = 0.5
    matrix[1, 0] = 0.3
    matrix[0, 1] = 0.2
    ou = over_under_probs(matrix, thresholds=(0.5,))
    # total > 0.5 <=> total >= 1 : P(1,0)+P(0,1) = 0.5
    assert ou[0.5] == 0.5


def test_total_goals_distribution_sums_to_one_and_matches_buckets() -> None:
    matrix = _normalized_matrix(1.4, 1.1)
    dist = total_goals_distribution(matrix, max_bucket=DEFAULT_MAX_BUCKET)
    assert dist.shape == (DEFAULT_MAX_BUCKET + 1,)
    assert abs(dist.sum() - 1.0) < 1e-9


def test_check_distribution_validity_detects_invalid_distribution() -> None:
    valid = np.array([0.5, 0.5])
    invalid_sum = np.array([0.5, 0.4])
    invalid_negative = np.array([1.2, -0.2])
    assert check_distribution_validity(valid) == {"all_non_negative": True, "sums_to_one": True}
    assert check_distribution_validity(invalid_sum)["sums_to_one"] is False
    assert check_distribution_validity(invalid_negative)["all_non_negative"] is False


def test_check_over_under_monotonic_true_for_decreasing_sequence() -> None:
    assert check_over_under_monotonic({0.5: 0.9, 1.5: 0.7, 2.5: 0.5, 3.5: 0.3, 4.5: 0.1})


def test_check_over_under_monotonic_false_for_increasing_pair() -> None:
    assert not check_over_under_monotonic({1.5: 0.3, 2.5: 0.5})


def test_check_over_under_matches_distribution_true_for_consistent_pair() -> None:
    matrix = _normalized_matrix(1.4, 1.1)
    dist = total_goals_distribution(matrix)
    ou = over_under_probs(matrix, thresholds=(0.5, 1.5, 2.5, 3.5, 4.5))
    assert check_over_under_matches_distribution(dist, ou)


def test_check_over_under_matches_distribution_false_for_tampered_probability() -> None:
    matrix = _normalized_matrix(1.4, 1.1)
    dist = total_goals_distribution(matrix)
    ou = over_under_probs(matrix, thresholds=(2.5,))
    tampered = {2.5: ou[2.5] + 0.2}
    assert not check_over_under_matches_distribution(dist, tampered)


@given(
    lam=st.floats(min_value=0.1, max_value=5.0),
    mu=st.floats(min_value=0.1, max_value=5.0),
)
@settings(max_examples=100)
def test_property_monotonicity_and_consistency_hold_for_any_lambda_mu(lam: float, mu: float) -> None:
    """Propriete structurelle centrale du moteur (docs/final_engine_specification.md
    section 6) : quels que soient (lambda, mu), une distribution derivee
    d'une seule matrice est valide, monotone, et coherente avec elle-meme."""
    matrix = _normalized_matrix(lam, mu)
    dist = total_goals_distribution(matrix)
    ou = over_under_probs(matrix, thresholds=DEFAULT_OU_THRESHOLDS)

    validity = check_distribution_validity(dist)
    assert validity["all_non_negative"]
    assert validity["sums_to_one"]
    assert check_over_under_monotonic(ou)
    assert check_over_under_matches_distribution(dist, ou)
