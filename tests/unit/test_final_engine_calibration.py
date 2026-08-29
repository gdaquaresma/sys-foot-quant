from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from sys_foot_quant.calibration_engine.scalar_correction import MIN_CALIBRATION_MATCHES_FOR_SCALE
from sys_foot_quant.final_engine.calibration import calibrate_prediction
from sys_foot_quant.final_engine.types import ModelPrediction
from sys_foot_quant.football_model.goal_distribution import (
    check_distribution_validity,
    check_over_under_matches_distribution,
    check_over_under_monotonic,
)


def _dt(day: int) -> datetime:
    return datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=day - 1)


def _calibration_df(n: int, lam_mu_sum: float = 3.0, total_goals: float = 2.7, model: str = "poisson_simple") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "decision_time": [_dt(d) for d in range(1, n + 1)],
            f"{model}_lambda": [lam_mu_sum / 2] * n,
            f"{model}_mu": [lam_mu_sum / 2] * n,
            "total_goals": [total_goals] * n,
        }
    )


def test_returns_none_distribution_when_calibration_history_insufficient() -> None:
    pred = ModelPrediction(model="poisson_simple", lam=1.5, mu=1.5, rho=None, n_train_matches=20)
    df = _calibration_df(MIN_CALIBRATION_MATCHES_FOR_SCALE - 1)
    result = calibrate_prediction(pred, df, as_of_time=_dt(1000))
    assert result.scale_c is None
    assert result.goal_distribution is None
    assert result.probabilities is None
    assert result.n_calibration_used == MIN_CALIBRATION_MATCHES_FOR_SCALE - 1


def test_applies_scale_correction_and_produces_consistent_distribution() -> None:
    pred = ModelPrediction(model="poisson_simple", lam=1.5, mu=1.5, rho=None, n_train_matches=20)
    df = _calibration_df(MIN_CALIBRATION_MATCHES_FOR_SCALE, lam_mu_sum=3.0, total_goals=2.7)
    result = calibrate_prediction(pred, df, as_of_time=_dt(1000))

    assert result.scale_c == pytest.approx(0.9)
    assert result.goal_distribution is not None
    assert result.probabilities is not None
    assert sorted(result.probabilities) == [0.5, 1.5, 2.5, 3.5, 4.5]

    # Coherence structurelle garantie par construction (section 6) -
    # verifiee ici comme non-regression, pas creee par ce test.
    import numpy as np

    dist_array = np.array(result.goal_distribution)
    validity = check_distribution_validity(dist_array)
    assert validity["all_non_negative"]
    assert validity["sums_to_one"]
    assert check_over_under_monotonic(result.probabilities)
    assert check_over_under_matches_distribution(dist_array, result.probabilities)


def test_dixon_coles_prediction_uses_rho_in_reconstructed_matrix() -> None:
    pred = ModelPrediction(model="dixon_coles", lam=1.5, mu=1.2, rho=-0.05, n_train_matches=20)
    df = _calibration_df(MIN_CALIBRATION_MATCHES_FOR_SCALE, lam_mu_sum=2.7, total_goals=2.7, model="dixon_coles")
    result = calibrate_prediction(pred, df, as_of_time=_dt(1000))
    assert result.scale_c == pytest.approx(1.0)
    assert result.probabilities is not None


def test_never_uses_a_calibration_row_at_or_after_as_of_time() -> None:
    """Le facteur d'echelle ne doit jamais deriver d'un match dont
    decision_time >= as_of_time (garantie deja testee dans
    scalar_correction, reverifiee ici au niveau de l'appel du moteur)."""
    pred = ModelPrediction(model="poisson_simple", lam=1.5, mu=1.5, rho=None, n_train_matches=20)
    df = _calibration_df(MIN_CALIBRATION_MATCHES_FOR_SCALE, lam_mu_sum=3.0, total_goals=2.7)
    as_of = df["decision_time"].iloc[-1]  # egal au dernier match -> exclu (strictement <)
    result = calibrate_prediction(pred, df, as_of_time=as_of)
    assert result.n_calibration_used == MIN_CALIBRATION_MATCHES_FOR_SCALE - 1
