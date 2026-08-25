from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.football_model.elo import EloModel


def _matches(rows):
    return pd.DataFrame(rows, columns=["home_team_id", "away_team_id", "home_goals", "away_goals"])


def test_elo_predict_before_fit_raises() -> None:
    with pytest.raises(RuntimeError):
        EloModel().predict(1, 2)


def test_elo_rejects_empty_training_set() -> None:
    with pytest.raises(ValueError):
        EloModel().fit(_matches([]))


def test_elo_winner_rating_increases_loser_decreases() -> None:
    df = _matches([(1, 2, 3, 0)])  # equipe 1 ecrase l'equipe 2 a domicile
    model = EloModel(initial_rating=1500.0).fit(df)
    assert model.ratings_[1] > 1500.0
    assert model.ratings_[2] < 1500.0


def test_elo_home_advantage_favors_home_team_on_average() -> None:
    # Ligue synthetique avec un biais domicile leaguewide (55% domicile /
    # 25% nul / 20% exterieur, independant de l'identite des equipes) :
    # le score attendu Elo (via home_advantage) doit capturer ce biais et
    # se traduire, une fois calibre, par home > away en moyenne sur des
    # paires d'equipes de force comparable.
    rng = np.random.default_rng(7)
    n_teams = 6
    rows = []
    for _ in range(400):
        h, a = rng.choice(n_teams, size=2, replace=False)
        outcome = rng.choice(["H", "D", "A"], p=[0.55, 0.25, 0.20])
        if outcome == "H":
            hg, ag = 2, 0
        elif outcome == "D":
            hg, ag = 1, 1
        else:
            hg, ag = 0, 2
        rows.append((int(h), int(a), hg, ag))
    df = _matches(rows)
    model = EloModel(home_advantage=100.0).fit(df)

    home_probs, away_probs = [], []
    for h in range(n_teams):
        for a in range(n_teams):
            if h != a:
                home, draw, away = model.predict(h, a)
                home_probs.append(home)
                away_probs.append(away)
    assert np.mean(home_probs) > np.mean(away_probs)


def test_elo_unseen_team_uses_initial_rating() -> None:
    df = _matches([(1, 2, 1, 0)])
    model = EloModel(initial_rating=1500.0).fit(df)
    assert model.ratings_.get(99, model.initial_rating) == pytest.approx(1500.0)
    home, draw, away = model.predict(99, 100)
    assert home + draw + away == pytest.approx(1.0, abs=1e-6)


def test_elo_predict_probabilities_valid() -> None:
    df = _matches([(1, 2, 2, 1), (2, 3, 0, 0), (3, 1, 1, 2), (1, 3, 1, 1)])
    model = EloModel().fit(df)
    for h, a in [(1, 2), (2, 3), (3, 1)]:
        home, draw, away = model.predict(h, a)
        assert home + draw + away == pytest.approx(1.0, abs=1e-6)
        for p in (home, draw, away):
            assert -1e-9 <= p <= 1.0 + 1e-9


def test_elo_is_deterministic() -> None:
    df = _matches([(1, 2, 2, 1), (2, 3, 0, 0), (3, 1, 1, 2)])
    m1 = EloModel().fit(df)
    m2 = EloModel().fit(df)
    assert m1.ratings_ == pytest.approx(m2.ratings_)
    assert m1.predict(1, 2) == pytest.approx(m2.predict(1, 2))


@given(
    rows=st.lists(
        st.tuples(
            st.integers(1, 4),
            st.integers(1, 4),
            st.integers(0, 5),
            st.integers(0, 5),
        ).filter(lambda t: t[0] != t[1]),
        min_size=1,
        max_size=60,
    )
)
@settings(max_examples=50)
def test_elo_ratings_always_finite_and_predictions_valid(rows) -> None:
    df = _matches(rows)
    model = EloModel().fit(df)
    for rating in model.ratings_.values():
        assert rating == rating  # not NaN
        assert abs(rating) < 1e6
    home, draw, away = model.predict(rows[0][0], rows[0][1])
    assert home + draw + away == pytest.approx(1.0, abs=1e-6)
