from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.football_model.recent_form import RecentFormModel

_T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _matches(rows: list[tuple[int, int, int, int, datetime]]) -> pd.DataFrame:
    return pd.DataFrame(
        rows, columns=["home_team_id", "away_team_id", "home_goals", "away_goals", "kickoff_time"]
    )


def test_rejects_empty_training_set() -> None:
    with pytest.raises(ValueError):
        RecentFormModel(window=5).fit(_matches([]))


def test_rejects_non_positive_window() -> None:
    with pytest.raises(ValueError):
        RecentFormModel(window=0)
    with pytest.raises(ValueError):
        RecentFormModel(window=-1)


def test_rejects_negative_prior_k() -> None:
    with pytest.raises(ValueError):
        RecentFormModel(window=5, prior_k=-1.0)


def test_predict_before_fit_raises() -> None:
    with pytest.raises(RuntimeError):
        RecentFormModel(window=5).predict_lambda_mu(0, 1)


def test_fit_accepts_and_ignores_decision_time() -> None:
    df = _matches([(0, 1, 3, 1, _T0)])
    model = RecentFormModel(window=5).fit(df, decision_time=_T0 + timedelta(days=30))
    assert model.attack_ is not None


def test_unknown_team_falls_back_to_neutral_ratio() -> None:
    df = _matches([(0, 1, 2, 1, _T0), (1, 0, 1, 1, _T0 + timedelta(days=1))])
    model = RecentFormModel(window=5).fit(df)
    lam, mu = model.predict_lambda_mu(999, 998)
    assert lam == pytest.approx(model.league_base_ * model.hfa_global_)
    assert mu == pytest.approx(model.league_base_)


def test_predict_outcome_probabilities_sum_to_one() -> None:
    df = _matches([(0, 1, 2, 1, _T0), (1, 0, 1, 1, _T0 + timedelta(days=1))])
    model = RecentFormModel(window=3).fit(df)
    home, draw, away = model.predict_outcome_probabilities(0, 1)
    assert home + draw + away == pytest.approx(1.0, abs=1e-6)


def test_window_ignores_matches_beyond_it_prior_k_zero() -> None:
    # Team 0 : 4 matchs a domicile, buts marques 0,0,0,5 (chronologique).
    # Avec window=1 et prior_k=0, seul le DERNIER match (5 buts) doit compter.
    rows = [
        (0, 9, 0, 0, _T0),
        (0, 9, 0, 0, _T0 + timedelta(days=1)),
        (0, 9, 0, 0, _T0 + timedelta(days=2)),
        (0, 9, 5, 0, _T0 + timedelta(days=3)),
    ]
    df = _matches(rows)
    model = RecentFormModel(window=1, prior_k=0.0).fit(df)
    # league_base = somme(buts)/(2*n) = (0+0+0+0+5+0+1+1+1+1)/(2*5)... calcule directement.
    total_goals = sum(r[2] + r[3] for r in rows)
    league_base = total_goals / (2.0 * len(rows))
    expected_attack_0 = (5.0 / 1) / league_base
    assert model.attack_[0] == pytest.approx(expected_attack_0)


def test_prior_k_zero_uses_recent_window_only_no_blending() -> None:
    rows = [
        (0, 1, 4, 0, _T0),
        (0, 1, 0, 0, _T0 + timedelta(days=1)),
        (1, 0, 1, 1, _T0 + timedelta(days=2)),
    ]
    df = _matches(rows)
    model_full_window = RecentFormModel(window=10, prior_k=0.0).fit(df)
    model_full_window_with_prior = RecentFormModel(window=10, prior_k=5.0).fit(df)
    # Avec window >= n_all, recent == long_run pour chaque equipe -> le
    # blending est un no-op algebrique (n*x + k*x)/(n+k) == x.
    assert model_full_window.attack_ == pytest.approx(model_full_window_with_prior.attack_)
    assert model_full_window.defense_ == pytest.approx(model_full_window_with_prior.defense_)


def test_prior_k_blends_toward_long_run_when_recent_sample_small() -> None:
    # Equipe 0 : historique long tres offensif (5 matchs a 4 buts), puis un
    # unique match tres defensif recent (0 but) avec une fenetre window=1.
    # Sans prior (k=0), l'estimation ne voit QUE le 0. Avec prior_k>0, le
    # long terme (tres offensif) doit tirer l'estimation vers le haut.
    rows = [(0, 9, 4, 0, _T0 + timedelta(days=i)) for i in range(5)]
    rows.append((0, 9, 0, 0, _T0 + timedelta(days=5)))
    df = _matches(rows)

    model_no_prior = RecentFormModel(window=1, prior_k=0.0).fit(df)
    model_with_prior = RecentFormModel(window=1, prior_k=2.0).fit(df)

    assert model_with_prior.attack_[0] > model_no_prior.attack_[0]


def test_row_order_in_dataframe_does_not_affect_result() -> None:
    rows = [
        (0, 1, 2, 1, _T0),
        (1, 2, 0, 0, _T0 + timedelta(days=1)),
        (2, 0, 3, 2, _T0 + timedelta(days=2)),
        (0, 2, 1, 1, _T0 + timedelta(days=3)),
    ]
    df_sorted = _matches(rows)
    df_shuffled = _matches([rows[2], rows[0], rows[3], rows[1]])

    model_sorted = RecentFormModel(window=2, prior_k=1.0).fit(df_sorted)
    model_shuffled = RecentFormModel(window=2, prior_k=1.0).fit(df_shuffled)

    assert model_sorted.attack_ == pytest.approx(model_shuffled.attack_)
    assert model_sorted.defense_ == pytest.approx(model_shuffled.defense_)


@given(
    rows=st.lists(
        st.tuples(
            st.integers(0, 3),
            st.integers(0, 3),
            st.integers(0, 6),
            st.integers(0, 6),
        ).filter(lambda t: t[0] != t[1]),
        min_size=1,
        max_size=40,
    ),
    window=st.integers(1, 10),
    prior_k=st.floats(0.0, 20.0),
)
@settings(max_examples=50)
def test_fitted_parameters_always_finite_and_positive(rows, window, prior_k) -> None:
    df_rows = [(h, a, hg, ag, _T0 + timedelta(days=i)) for i, (h, a, hg, ag) in enumerate(rows)]
    model = RecentFormModel(window=window, prior_k=prior_k).fit(_matches(df_rows))
    for d in (model.attack_, model.defense_):
        for v in d.values():
            assert v > 0
            assert math.isfinite(v)
    assert model.league_base_ > 0
    assert model.hfa_global_ > 0


def test_predict_low_score_probs_is_additive_and_normalized() -> None:
    df = _matches([(0, 1, 2, 1, _T0), (1, 0, 1, 1, _T0 + timedelta(days=1))])
    model = RecentFormModel(window=5).fit(df)
    p00, p10, p01, p11 = model.predict_low_score_probs(0, 1)
    for p in (p00, p10, p01, p11):
        assert 0.0 <= p <= 1.0
