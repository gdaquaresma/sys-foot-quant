from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from sys_foot_quant.calibration_engine.scalar_correction import (
    MIN_CALIBRATION_MATCHES_FOR_SCALE,
    attach_walk_forward_scale,
    fit_scale_correction_as_of,
)


def _dt(day: int) -> datetime:
    return datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=day - 1)


def _calibration_df(n: int, lam_mu_sum: float = 3.0, total_goals: float = 2.7) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "decision_time": [_dt(d) for d in range(1, n + 1)],
            "poisson_simple_lambda": [lam_mu_sum / 2] * n,
            "poisson_simple_mu": [lam_mu_sum / 2] * n,
            "total_goals": [total_goals] * n,
        }
    )


def test_returns_none_when_history_below_min_matches() -> None:
    df = _calibration_df(MIN_CALIBRATION_MATCHES_FOR_SCALE - 1)
    c, n = fit_scale_correction_as_of(df, "poisson_simple", as_of_time=_dt(1000))
    assert c is None
    assert n == MIN_CALIBRATION_MATCHES_FOR_SCALE - 1


def test_returns_scale_factor_when_history_sufficient() -> None:
    df = _calibration_df(MIN_CALIBRATION_MATCHES_FOR_SCALE, lam_mu_sum=3.0, total_goals=2.7)
    c, n = fit_scale_correction_as_of(df, "poisson_simple", as_of_time=_dt(1000))
    assert c == pytest.approx(2.7 / 3.0)
    assert n == MIN_CALIBRATION_MATCHES_FOR_SCALE


def test_never_uses_a_match_whose_decision_time_is_not_strictly_before_as_of() -> None:
    """Coeur de la garantie anti-fuite : un match dont decision_time >=
    as_of_time (y compris EGAL) ne doit jamais entrer dans le calcul."""
    df = _calibration_df(MIN_CALIBRATION_MATCHES_FOR_SCALE, lam_mu_sum=3.0, total_goals=2.7)
    # as_of_time = decision_time exact du dernier match de calibration :
    # ce match ne doit PAS etre inclus (strictement <, jamais <=).
    as_of = df["decision_time"].iloc[-1]
    c, n = fit_scale_correction_as_of(df, "poisson_simple", as_of_time=as_of)
    assert n == MIN_CALIBRATION_MATCHES_FOR_SCALE - 1


def test_adding_a_future_row_never_changes_an_earlier_scale_estimate() -> None:
    df = _calibration_df(MIN_CALIBRATION_MATCHES_FOR_SCALE, lam_mu_sum=3.0, total_goals=2.7)
    as_of = _dt(1000)
    c_before, n_before = fit_scale_correction_as_of(df, "poisson_simple", as_of_time=as_of)

    future_row = pd.DataFrame(
        {
            "decision_time": [_dt(2000)],
            "poisson_simple_lambda": [10.0],
            "poisson_simple_mu": [10.0],
            "total_goals": [0.0],
        }
    )
    df_with_future = pd.concat([df, future_row], ignore_index=True)
    c_after, n_after = fit_scale_correction_as_of(df_with_future, "poisson_simple", as_of_time=as_of)

    assert c_after == c_before
    assert n_after == n_before


def test_rows_with_missing_lambda_or_mu_are_excluded() -> None:
    df = _calibration_df(MIN_CALIBRATION_MATCHES_FOR_SCALE)
    df.loc[0, "poisson_simple_lambda"] = float("nan")
    c, n = fit_scale_correction_as_of(df, "poisson_simple", as_of_time=_dt(1000))
    assert n == MIN_CALIBRATION_MATCHES_FOR_SCALE - 1


def test_attach_walk_forward_scale_never_uses_test_df_to_compute_scale() -> None:
    calibration_df = _calibration_df(MIN_CALIBRATION_MATCHES_FOR_SCALE, lam_mu_sum=3.0, total_goals=2.7)
    test_df = pd.DataFrame(
        {
            "decision_time": [_dt(2000), _dt(2001)],
            "poisson_simple_lambda": [1.5, 1.5],
            "poisson_simple_mu": [1.5, 1.5],
            # valeurs absurdes : si elles influencaient scale_c, le test echouerait
            "total_goals": [999.0, -999.0],
        }
    )
    out = attach_walk_forward_scale(calibration_df, test_df, "poisson_simple")
    assert out["scale_c"].tolist() == pytest.approx([2.7 / 3.0, 2.7 / 3.0])
    assert out["n_calibration_used"].tolist() == [MIN_CALIBRATION_MATCHES_FOR_SCALE] * 2
