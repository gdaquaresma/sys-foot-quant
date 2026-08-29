from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.football_model.goal_distribution import (
    DEFAULT_MAX_BUCKET,
    DEFAULT_OU_THRESHOLDS,
    asian_handicap_probabilities,
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


# --------------------------------------------------------------------------
# asian_handicap_probabilities (Phase H, docs/ah_experiment_specification.md
# section 2.3) - lignes entieres (push possible), demi-entieres (jamais de
# push), quart de ligne (decomposition en deux jambes propres).
# --------------------------------------------------------------------------


def _settle(d: int, h: float) -> float:
    """Reimplementation INDEPENDANTE (brute force, jamais copiee de
    ``asian_handicap_probabilities``) du reglement reel d'un pari domicile
    unitaire, utilisee ici uniquement comme oracle de test - decompose une
    ligne quart en deux jambes a demi-mise, comme le veut la definition
    reelle de l'instrument (section 2.2/2.7 du protocole)."""
    frac = abs(h) % 1.0
    is_quarter = min(abs(frac - 0.25), abs(frac - 0.75)) < 1e-9
    legs = [h - 0.25, h + 0.25] if is_quarter else [h]
    total = 0.0
    for leg in legs:
        m = d + leg
        if m > 1e-9:
            total += 1.0
        elif m < -1e-9:
            total += -1.0
        # sinon push sur cette jambe : contribution nulle
    return total / len(legs)


def test_ah_integer_line_push_possible_and_probabilities_sum_to_one() -> None:
    matrix = _normalized_matrix(1.4, 1.1)
    probs = asian_handicap_probabilities(matrix, 0.0)
    assert probs["push"] > 0.0  # d=0 (nul) est possible et donne un push exact sur h=0
    assert probs["home"] + probs["push"] + probs["away"] == pytest.approx(1.0)


def test_ah_half_line_never_pushes() -> None:
    matrix = _normalized_matrix(1.4, 1.1)
    for h in (-2.5, -0.5, 0.5, 1.5):
        probs = asian_handicap_probabilities(matrix, h)
        assert probs["push"] == 0.0
        assert probs["home"] + probs["away"] == pytest.approx(1.0)


def test_ah_more_negative_line_makes_covering_harder_for_home() -> None:
    """Convention domicile (section 2.1 du protocole) : une ligne PLUS
    NEGATIVE exige une victoire domicile PLUS large pour couvrir - a
    matrice identique, P(Home) doit donc etre strictement plus petit a
    -1.5 (il faut gagner par 2+) qu'a +1.5 (il suffit de ne pas perdre
    par 2+)."""
    matrix = _normalized_matrix(1.6, 1.0)
    strict_line = asian_handicap_probabilities(matrix, -1.5)
    generous_line = asian_handicap_probabilities(matrix, 1.5)
    assert strict_line["home"] < generous_line["home"]


def test_ah_quarter_line_equals_average_of_two_adjacent_clean_lines() -> None:
    """Definition structurelle (section 2.2/2.3 du protocole) - jamais une
    approximation : verifiee directement sur l'implementation."""
    matrix = _normalized_matrix(1.3, 1.2)
    quarter = asian_handicap_probabilities(matrix, -0.25)
    lo = asian_handicap_probabilities(matrix, -0.5)
    hi = asian_handicap_probabilities(matrix, 0.0)
    for key in ("home", "push", "away"):
        assert quarter[key] == pytest.approx(0.5 * lo[key] + 0.5 * hi[key])


@pytest.mark.parametrize("h", [-2.0, -1.75, -1.5, -1.25, -1.0, -0.75, -0.5, -0.25, 0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0])
@pytest.mark.parametrize("d", list(range(-6, 7)))
def test_ah_quarter_decomposition_matches_independent_settlement_oracle(d: int, h: float) -> None:
    """Preuve directe (protocole section 2.3) : pour CHAQUE resultat entier
    possible d et CHAQUE ligne (propre ou quart), la contribution de ce
    resultat a (P(Home)-P(Away)) doit correspondre exactement a la
    fraction de mise reglee par l'oracle independant ``_settle`` - verifie
    en construisant une matrice qui concentre toute la masse sur un seul
    (home,away) compatible avec d, jamais en reutilisant le code teste."""
    max_goals = 20
    matrix = np.zeros((max_goals + 1, max_goals + 1))
    # place toute la masse sur UN SEUL couple (home,away) tel que home-away=d
    home_goals = max(d, 0) + 3
    away_goals = home_goals - d
    if not (0 <= home_goals <= max_goals and 0 <= away_goals <= max_goals):
        pytest.skip("couple hors bornes pour ce d")
    matrix[home_goals, away_goals] = 1.0

    probs = asian_handicap_probabilities(matrix, h)
    expected_settle = _settle(d, h)
    observed_settle = probs["home"] * 1.0 + probs["away"] * (-1.0)  # push contribue 0
    assert observed_settle == pytest.approx(expected_settle)


def test_ah_probabilities_always_sum_to_one_property() -> None:
    for lam, mu in [(0.8, 0.8), (2.5, 0.3), (1.0, 3.0)]:
        matrix = _normalized_matrix(lam, mu)
        for h in (-3.0, -1.75, -1.0, -0.25, 0.0, 0.25, 1.0, 2.5):
            probs = asian_handicap_probabilities(matrix, h)
            assert sum(probs.values()) == pytest.approx(1.0)
            for v in probs.values():
                assert -1e-9 <= v <= 1.0 + 1e-9
