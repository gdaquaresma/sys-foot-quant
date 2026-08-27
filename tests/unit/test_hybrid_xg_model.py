from __future__ import annotations

import pandas as pd
import pytest

from sys_foot_quant.football_model.hybrid_xg_model import HybridXGModel
from sys_foot_quant.football_model.poisson import PoissonModel
from sys_foot_quant.football_model.xg_model import XGModel

_GOALS_COLS = ["home_team_id", "away_team_id", "home_goals", "away_goals", "kickoff_time"]
_XG_COLS = ["home_team_id", "away_team_id", "home_xg", "away_xg", "kickoff_time"]


def _goals_df() -> pd.DataFrame:
    return pd.DataFrame(
        [(0, 1, 2, 1, 0), (1, 0, 1, 1, 1)], columns=_GOALS_COLS
    )


def _xg_df() -> pd.DataFrame:
    return pd.DataFrame(
        [(0, 1, 1.4, 0.9, 0), (1, 0, 0.8, 1.1, 1)], columns=_XG_COLS
    )


def test_rejects_out_of_range_weight() -> None:
    with pytest.raises(ValueError):
        HybridXGModel(w=-0.01)
    with pytest.raises(ValueError):
        HybridXGModel(w=1.01)


def test_predict_before_fit_raises() -> None:
    with pytest.raises(RuntimeError):
        HybridXGModel(w=0.5).predict_outcome_probabilities(0, 1)


def test_weight_zero_is_exactly_poisson_simple() -> None:
    hybrid = HybridXGModel(w=0.0).fit(_goals_df(), _xg_df())
    poisson = PoissonModel(use_team_hfa=False).fit(_goals_df())
    assert hybrid.predict_outcome_probabilities(0, 1) == pytest.approx(
        poisson.predict_outcome_probabilities(0, 1)
    )


def test_weight_one_is_exactly_xg_model() -> None:
    hybrid = HybridXGModel(w=1.0).fit(_goals_df(), _xg_df())
    xg = XGModel().fit(_xg_df())
    assert hybrid.predict_outcome_probabilities(0, 1) == pytest.approx(
        xg.predict_outcome_probabilities(0, 1)
    )


def test_blend_matches_hand_computation() -> None:
    w = 0.25
    hybrid = HybridXGModel(w=w).fit(_goals_df(), _xg_df())
    poisson = PoissonModel(use_team_hfa=False).fit(_goals_df())
    xg = XGModel().fit(_xg_df())

    p_poisson = poisson.predict_outcome_probabilities(0, 1)
    p_xg = xg.predict_outcome_probabilities(0, 1)
    expected = tuple((1 - w) * p + w * x for p, x in zip(p_poisson, p_xg))

    assert hybrid.predict_outcome_probabilities(0, 1) == pytest.approx(expected)


@pytest.mark.parametrize("w", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_probabilities_always_sum_to_one(w: float) -> None:
    hybrid = HybridXGModel(w=w).fit(_goals_df(), _xg_df())
    home, draw, away = hybrid.predict_outcome_probabilities(0, 1)
    assert home + draw + away == pytest.approx(1.0, abs=1e-9)
    assert home >= 0 and draw >= 0 and away >= 0


def test_does_not_modify_poisson_or_xg_model_behavior() -> None:
    # Verifie explicitement que faire tourner HybridXGModel ne change rien
    # aux predictions de PoissonModel/XGModel utilises independamment -
    # aucun etat partage, aucun effet de bord.
    goals_df, xg_df = _goals_df(), _xg_df()
    poisson_before = PoissonModel(use_team_hfa=False).fit(goals_df).predict_outcome_probabilities(0, 1)
    xg_before = XGModel().fit(xg_df).predict_outcome_probabilities(0, 1)

    HybridXGModel(w=0.5).fit(goals_df, xg_df).predict_outcome_probabilities(0, 1)

    poisson_after = PoissonModel(use_team_hfa=False).fit(goals_df).predict_outcome_probabilities(0, 1)
    xg_after = XGModel().fit(xg_df).predict_outcome_probabilities(0, 1)
    assert poisson_before == pytest.approx(poisson_after)
    assert xg_before == pytest.approx(xg_after)
