from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from sys_foot_quant.football_model.head_to_head import HeadToHeadModel
from sys_foot_quant.football_model.poisson import PoissonModel

_T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _matches(rows: list[tuple[int, int, int, int, datetime]]) -> pd.DataFrame:
    return pd.DataFrame(
        rows, columns=["home_team_id", "away_team_id", "home_goals", "away_goals", "kickoff_time"]
    )


def test_rejects_empty_training_set() -> None:
    with pytest.raises(ValueError):
        HeadToHeadModel().fit(_matches([]))


def test_rejects_out_of_range_weight() -> None:
    with pytest.raises(ValueError):
        HeadToHeadModel(weight=-0.01)
    with pytest.raises(ValueError):
        HeadToHeadModel(weight=1.01)


def test_predict_before_fit_raises() -> None:
    with pytest.raises(RuntimeError):
        HeadToHeadModel().predict_outcome_probabilities(0, 1)


def test_no_prior_meeting_falls_back_exactly_to_poisson_simple() -> None:
    df = _matches(
        [
            (0, 1, 2, 1, _T0),
            (1, 0, 1, 1, _T0 + timedelta(days=1)),
            (2, 3, 0, 0, _T0 + timedelta(days=2)),
        ]
    )
    h2h_model = HeadToHeadModel(weight=0.10).fit(df)
    base_model = PoissonModel(use_team_hfa=False).fit(df)

    # 2 vs 3 n'ont jamais joue l'un contre l'autre dans df.
    h2h_probs = h2h_model.predict_outcome_probabilities(2, 3)
    base_probs = base_model.predict_outcome_probabilities(2, 3)
    assert h2h_probs == pytest.approx(base_probs)


def test_prior_meeting_blends_toward_its_outcome_home_perspective() -> None:
    rows = [
        (0, 1, 2, 1, _T0),  # 0 a battu 1 a domicile - UNIQUE confrontation directe 0 vs 1
        (2, 3, 1, 1, _T0 + timedelta(days=1)),  # match sans rapport (autres equipes)
    ]
    df = _matches(rows)
    weight = 0.10
    h2h_model = HeadToHeadModel(weight=weight).fit(df)
    base_model = PoissonModel(use_team_hfa=False).fit(df)

    # Meme orientation domicile/exterieur que la derniere rencontre (0 domicile, 1 exterieur).
    h2h_probs = h2h_model.predict_outcome_probabilities(0, 1)
    base_probs = base_model.predict_outcome_probabilities(0, 1)
    expected = tuple(
        (1 - weight) * b + weight * o for b, o in zip(base_probs, (1.0, 0.0, 0.0))
    )
    assert h2h_probs == pytest.approx(expected)
    assert sum(h2h_probs) == pytest.approx(1.0, abs=1e-9)


def test_prior_meeting_perspective_is_flipped_when_venue_reversed() -> None:
    rows = [
        (0, 1, 2, 1, _T0),  # 0 a battu 1 a domicile -> derniere (et unique) rencontre : "0 gagne"
        (2, 3, 1, 1, _T0 + timedelta(days=1)),  # match sans rapport (autres equipes)
    ]
    df = _matches(rows)
    weight = 0.10
    h2h_model = HeadToHeadModel(weight=weight).fit(df)
    base_model = PoissonModel(use_team_hfa=False).fit(df)

    # Ici le match a predire a l'orientation inverse (1 domicile, 0 exterieur) :
    # la derniere rencontre (0 gagnant) doit se traduire en "exterieur gagne".
    h2h_probs = h2h_model.predict_outcome_probabilities(1, 0)
    base_probs = base_model.predict_outcome_probabilities(1, 0)
    expected = tuple(
        (1 - weight) * b + weight * o for b, o in zip(base_probs, (0.0, 0.0, 1.0))
    )
    assert h2h_probs == pytest.approx(expected)


def test_weight_zero_is_exactly_poisson_simple() -> None:
    df = _matches([(0, 1, 2, 1, _T0), (1, 0, 3, 0, _T0 + timedelta(days=1))])
    h2h_model = HeadToHeadModel(weight=0.0).fit(df)
    base_model = PoissonModel(use_team_hfa=False).fit(df)
    assert h2h_model.predict_outcome_probabilities(0, 1) == pytest.approx(
        base_model.predict_outcome_probabilities(0, 1)
    )


def test_only_last_meeting_is_used_not_earlier_ones() -> None:
    rows = [
        (0, 1, 5, 0, _T0),  # ancienne rencontre : 0 ecrase 1
        # derniere rencontre (domicile=1, exterieur=0) : home_goals=0, away_goals=2 -> equipe 0 gagne.
        (1, 0, 0, 2, _T0 + timedelta(days=10)),
    ]
    df = _matches(rows)
    weight = 0.10
    h2h_model = HeadToHeadModel(weight=weight).fit(df)
    base_model = PoissonModel(use_team_hfa=False).fit(df)

    h2h_probs = h2h_model.predict_outcome_probabilities(0, 1)
    base_probs = base_model.predict_outcome_probabilities(0, 1)
    # Derniere rencontre : equipe 0 a gagne (peu importe le sens) -> one-hot
    # "domicile gagne" dans le repere du match a predire (0 est domicile ici).
    expected = tuple(
        (1 - weight) * b + weight * o for b, o in zip(base_probs, (1.0, 0.0, 0.0))
    )
    assert h2h_probs == pytest.approx(expected)


def test_draw_last_meeting_blends_toward_draw() -> None:
    # Unique confrontation directe 0 vs 1, nulle - un nul se traduit en
    # "match nul" quelle que soit l'orientation domicile/exterieur du
    # match a predire (symetrique par construction).
    df = _matches([(0, 1, 1, 1, _T0), (2, 3, 0, 0, _T0 + timedelta(days=1))])
    weight = 0.10
    h2h_model = HeadToHeadModel(weight=weight).fit(df)
    base_model = PoissonModel(use_team_hfa=False).fit(df)
    h2h_probs = h2h_model.predict_outcome_probabilities(1, 0)
    base_probs = base_model.predict_outcome_probabilities(1, 0)
    expected = tuple(
        (1 - weight) * b + weight * o for b, o in zip(base_probs, (0.0, 1.0, 0.0))
    )
    assert h2h_probs == pytest.approx(expected)
