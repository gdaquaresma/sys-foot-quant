from __future__ import annotations

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.football_model.naive import NaiveModel


def _matches(rows):
    return pd.DataFrame(rows, columns=["home_team_id", "away_team_id", "home_goals", "away_goals"])


def test_naive_model_matches_empirical_frequency() -> None:
    # 2 victoires domicile, 1 nul, 1 victoire exterieur => 50%/25%/25%
    df = _matches(
        [
            (1, 2, 2, 0),
            (2, 1, 1, 0),
            (1, 2, 1, 1),
            (2, 1, 0, 3),
        ]
    )
    model = NaiveModel().fit(df)
    home, draw, away = model.predict(1, 2)
    assert home == pytest.approx(0.5)
    assert draw == pytest.approx(0.25)
    assert away == pytest.approx(0.25)


def test_naive_model_ignores_team_identity() -> None:
    df = _matches([(1, 2, 1, 0), (3, 4, 0, 0), (5, 6, 0, 2)])
    model = NaiveModel().fit(df)
    p_a = model.predict(1, 2)
    p_b = model.predict(99, 100)
    assert p_a == p_b


def test_naive_model_predict_before_fit_raises() -> None:
    with pytest.raises(RuntimeError):
        NaiveModel().predict(1, 2)


def test_naive_model_rejects_empty_training_set() -> None:
    with pytest.raises(ValueError):
        NaiveModel().fit(_matches([]))


@given(
    rows=st.lists(
        st.tuples(
            st.integers(1, 5),
            st.integers(1, 5),
            st.integers(0, 6),
            st.integers(0, 6),
        ),
        min_size=1,
        max_size=100,
    )
)
@settings(max_examples=50)
def test_naive_model_probabilities_always_valid(rows) -> None:
    df = _matches(rows)
    model = NaiveModel().fit(df)
    home, draw, away = model.predict(1, 2)
    assert home + draw + away == pytest.approx(1.0, abs=1e-9)
    for p in (home, draw, away):
        assert -1e-9 <= p <= 1.0 + 1e-9
