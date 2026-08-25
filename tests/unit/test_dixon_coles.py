from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.football_model.dixon_coles import (
    DixonColesModel,
    apply_dixon_coles_correction,
    dixon_coles_tau,
    rho_valid_bounds,
)
from sys_foot_quant.football_model.poisson import PoissonModel
from sys_foot_quant.football_model.scoring import score_matrix

_T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _matches(rows: list[tuple[int, int, int, int, datetime]]) -> pd.DataFrame:
    return pd.DataFrame(
        rows, columns=["home_team_id", "away_team_id", "home_goals", "away_goals", "kickoff_time"]
    )


# --- tau : formule et bornes --------------------------------------------


def test_tau_formula_matches_dixon_coles_1997_definition() -> None:
    lam, mu, rho = 1.4, 1.1, -0.13
    assert dixon_coles_tau(0, 0, lam, mu, rho) == pytest.approx(1.0 - lam * mu * rho)
    assert dixon_coles_tau(1, 0, lam, mu, rho) == pytest.approx(1.0 + mu * rho)
    assert dixon_coles_tau(0, 1, lam, mu, rho) == pytest.approx(1.0 + lam * rho)
    assert dixon_coles_tau(1, 1, lam, mu, rho) == pytest.approx(1.0 - rho)


@pytest.mark.parametrize("x,y", [(2, 0), (0, 2), (2, 2), (3, 1), (5, 5)])
def test_tau_is_one_outside_low_score_cells(x: int, y: int) -> None:
    assert dixon_coles_tau(x, y, lam=1.4, mu=1.1, rho=-0.2) == 1.0


def test_tau_is_identity_at_rho_zero() -> None:
    for x, y in [(0, 0), (1, 0), (0, 1), (1, 1), (3, 2)]:
        assert dixon_coles_tau(x, y, lam=1.7, mu=0.9, rho=0.0) == pytest.approx(1.0)


def test_rho_valid_bounds_negative_rho_typically_allowed() -> None:
    lo, hi = rho_valid_bounds(lam=1.4, mu=1.1)
    assert lo < 0.0 < hi
    # rho litteraire (Dixon & Coles 1997, ordre de grandeur) doit rester valide
    # pour des lambda/mu typiques de football.
    assert lo <= -0.13 <= hi


def test_rho_valid_bounds_rejects_non_positive_lambda_mu() -> None:
    with pytest.raises(ValueError):
        rho_valid_bounds(lam=0.0, mu=1.0)
    with pytest.raises(ValueError):
        rho_valid_bounds(lam=1.0, mu=-1.0)


@given(
    lam=st.floats(min_value=0.1, max_value=6.0),
    mu=st.floats(min_value=0.1, max_value=6.0),
)
@settings(max_examples=100)
def test_tau_nonnegative_on_low_score_cells_within_valid_bounds(lam: float, mu: float) -> None:
    lo, hi = rho_valid_bounds(lam, mu)
    for rho in (lo, 0.0, hi):
        for x, y in [(0, 0), (1, 0), (0, 1), (1, 1)]:
            assert dixon_coles_tau(x, y, lam, mu, rho) >= -1e-9


# --- application a une matrice de score ----------------------------------


def test_apply_correction_is_identity_at_rho_zero() -> None:
    matrix = score_matrix(1.4, 1.1, max_goals=10)
    matrix = matrix / matrix.sum()
    corrected = apply_dixon_coles_correction(matrix, lam=1.4, mu=1.1, rho=0.0)
    assert np.allclose(corrected, matrix)


def test_apply_correction_sums_to_one() -> None:
    matrix = score_matrix(1.4, 1.1, max_goals=15)
    matrix = matrix / matrix.sum()
    corrected = apply_dixon_coles_correction(matrix, lam=1.4, mu=1.1, rho=-0.13)
    assert corrected.sum() == pytest.approx(1.0, abs=1e-9)
    assert (corrected >= 0.0).all()


def test_apply_correction_negative_rho_increases_00_and_11_decreases_10_and_01() -> None:
    lam, mu, rho = 1.4, 1.1, -0.13
    matrix = score_matrix(lam, mu, max_goals=15)
    matrix = matrix / matrix.sum()
    corrected = apply_dixon_coles_correction(matrix, lam, mu, rho)
    # Effet qualitatif reel de Dixon & Coles (1997) pour rho < 0, verifie
    # directement sur la formule tau (voir dixon_coles_tau) : 0-0 et 1-1
    # PLUS probables, 1-0 et 0-1 MOINS probables qu'au Poisson independant
    # - c'est l'inverse de l'intuition "l'equipe menee attaque davantage"
    # parfois avancee de maniere approximative ; l'effet empirique
    # documente par les auteurs est que le Poisson independant SOUS-estime
    # la frequence des matchs nuls a score bas (0-0, 1-1).
    assert corrected[0, 0] > matrix[0, 0]
    assert corrected[1, 1] > matrix[1, 1]
    assert corrected[1, 0] < matrix[1, 0]
    assert corrected[0, 1] < matrix[0, 1]


# --- DixonColesModel -------------------------------------------------------


def test_rejects_non_positive_max_goals() -> None:
    with pytest.raises(ValueError):
        DixonColesModel(max_goals=0)


def test_predict_before_fit_raises() -> None:
    with pytest.raises(RuntimeError):
        DixonColesModel().predict_score_matrix(0, 1)


def test_rejects_empty_training_set() -> None:
    with pytest.raises(ValueError):
        DixonColesModel().fit(_matches([]))


def test_rho_zero_reproduces_poisson_model_exactly() -> None:
    rows = [
        (h, a, hg, ag, _T0 + timedelta(days=i))
        for i, (h, a, hg, ag) in enumerate(
            [(0, 1, 2, 1), (1, 2, 0, 0), (2, 0, 3, 2), (0, 2, 1, 1), (1, 0, 2, 2), (2, 1, 0, 3)]
        )
    ]
    df = _matches(rows)
    dc = DixonColesModel(use_team_hfa=False).fit(df)
    dc.rho_ = 0.0  # force explicitement, independamment de l'estimation MLE
    poisson = PoissonModel(use_team_hfa=False).fit(df)

    for home, away in [(0, 1), (2, 0), (1, 2)]:
        assert dc.predict(home, away) == pytest.approx(poisson.predict(home, away), abs=1e-9)
        assert dc.predict_low_score_probs(home, away) == pytest.approx(
            poisson.predict_low_score_probs(home, away), abs=1e-9
        )
        assert dc.predict_lambda_mu(home, away) == pytest.approx(poisson.predict_lambda_mu(home, away))


def test_predict_outcome_probabilities_sum_to_one() -> None:
    rows = [
        (h, a, hg, ag, _T0 + timedelta(days=i))
        for i, (h, a, hg, ag) in enumerate(
            [(0, 1, 2, 1), (1, 2, 0, 0), (2, 0, 3, 2), (0, 2, 1, 1)]
        )
    ]
    model = DixonColesModel(use_team_hfa=False).fit(_matches(rows))
    home, draw, away = model.predict_outcome_probabilities(0, 1)
    assert home + draw + away == pytest.approx(1.0, abs=1e-6)


def test_predict_low_score_probs_matches_score_matrix_cells() -> None:
    rows = [
        (h, a, hg, ag, _T0 + timedelta(days=i))
        for i, (h, a, hg, ag) in enumerate(
            [(0, 1, 2, 1), (1, 2, 0, 0), (2, 0, 3, 2), (0, 2, 1, 1)]
        )
    ]
    model = DixonColesModel(use_team_hfa=False).fit(_matches(rows))
    matrix = model.predict_score_matrix(0, 1)
    p00, p10, p01, p11 = model.predict_low_score_probs(0, 1)
    assert p00 == pytest.approx(matrix[0, 0])
    assert p10 == pytest.approx(matrix[1, 0])
    assert p01 == pytest.approx(matrix[0, 1])
    assert p11 == pytest.approx(matrix[1, 1])


def test_estimated_rho_stays_within_valid_bounds_for_training_data() -> None:
    rows = [
        (h, a, hg, ag, _T0 + timedelta(days=i))
        for i, (h, a, hg, ag) in enumerate(
            [
                (0, 1, 0, 0), (1, 2, 1, 1), (2, 0, 0, 0), (0, 2, 1, 1),
                (1, 0, 0, 0), (2, 1, 1, 0), (0, 1, 1, 1), (1, 2, 0, 1),
            ]
        )
    ]
    model = DixonColesModel(use_team_hfa=False).fit(_matches(rows))
    assert model.rho_ is not None
    for home_id in {r[0] for r in rows} | {r[1] for r in rows}:
        for away_id in {r[0] for r in rows} | {r[1] for r in rows}:
            if home_id == away_id:
                continue
            lam, mu = model.predict_lambda_mu(home_id, away_id)
            lo, hi = rho_valid_bounds(lam, mu)
            assert lo - 1e-6 <= model.rho_ <= hi + 1e-6


@given(
    rows=st.lists(
        st.tuples(
            st.integers(0, 3),
            st.integers(0, 3),
            st.integers(0, 5),
            st.integers(0, 5),
        ).filter(lambda t: t[0] != t[1]),
        min_size=4,
        max_size=30,
    )
)
@settings(max_examples=40)
def test_fitted_rho_always_finite(rows) -> None:
    df_rows = [(h, a, hg, ag, _T0 + timedelta(days=i)) for i, (h, a, hg, ag) in enumerate(rows)]
    model = DixonColesModel(use_team_hfa=False).fit(_matches(df_rows))
    assert model.rho_ is not None
    assert np.isfinite(model.rho_)
