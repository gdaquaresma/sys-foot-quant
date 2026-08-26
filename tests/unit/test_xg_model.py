from __future__ import annotations

import math

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.football_model.xg_model import XGModel


def _matches(rows: list[tuple[int, int, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["home_team_id", "away_team_id", "home_xg", "away_xg"])


def test_rejects_empty_training_set() -> None:
    with pytest.raises(ValueError):
        XGModel().fit(_matches([]))


def test_predict_before_fit_raises() -> None:
    with pytest.raises(RuntimeError):
        XGModel().predict_lambda_mu(0, 1)


def test_single_match_matches_hand_computation() -> None:
    # league_base = (2.0+1.0)/2 = 1.5, hfa_global = 2.0/1.0 = 2.0
    df = _matches([(0, 1, 2.0, 1.0)])
    model = XGModel().fit(df)

    assert model.league_base_ == pytest.approx(1.5)
    assert model.hfa_global_ == pytest.approx(2.0)
    assert model.attack_[0] == pytest.approx(2.0 / 1.5)
    assert model.defense_[0] == pytest.approx(1.0 / 1.5)
    assert model.attack_[1] == pytest.approx(1.0 / 1.5)
    assert model.defense_[1] == pytest.approx(2.0 / 1.5)

    lam, mu = model.predict_lambda_mu(0, 1)
    assert lam == pytest.approx(1.5 * (2.0 / 1.5) * (2.0 / 1.5) * 2.0)
    assert mu == pytest.approx(1.5 * (1.0 / 1.5) * (1.0 / 1.5))


def test_unknown_team_falls_back_to_neutral_ratio() -> None:
    df = _matches([(0, 1, 1.4, 0.9), (1, 0, 0.8, 1.1)])
    model = XGModel().fit(df)
    lam, mu = model.predict_lambda_mu(999, 998)
    assert lam == pytest.approx(model.league_base_ * model.hfa_global_)
    assert mu == pytest.approx(model.league_base_)


def test_predict_outcome_probabilities_sum_to_one() -> None:
    df = _matches([(0, 1, 1.4, 0.9), (1, 0, 0.8, 1.1)])
    model = XGModel().fit(df)
    home, draw, away = model.predict_outcome_probabilities(0, 1)
    assert home + draw + away == pytest.approx(1.0, abs=1e-6)


def test_no_goals_columns_required() -> None:
    # Verifie explicitement qu'aucune colonne de buts reels n'est utilisee -
    # le DataFrame ne contient meme pas les colonnes home_goals/away_goals.
    df = _matches([(0, 1, 1.4, 0.9)])
    assert "home_goals" not in df.columns
    assert "away_goals" not in df.columns
    model = XGModel().fit(df)
    assert model.attack_ is not None


@given(
    rows=st.lists(
        st.tuples(
            st.integers(0, 3),
            st.integers(0, 3),
            st.floats(0.05, 6.0),
            st.floats(0.05, 6.0),
        ).filter(lambda t: t[0] != t[1]),
        min_size=1,
        max_size=40,
    )
)
@settings(max_examples=50)
def test_fitted_parameters_always_finite_and_positive(rows) -> None:
    model = XGModel().fit(_matches(rows))
    for d in (model.attack_, model.defense_):
        for v in d.values():
            assert v > 0
            assert math.isfinite(v)
    assert model.league_base_ > 0
    assert model.hfa_global_ > 0
