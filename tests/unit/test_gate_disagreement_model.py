from __future__ import annotations

import pandas as pd
import pytest

from sys_foot_quant.football_model.gate_disagreement_model import GateDisagreementModel
from sys_foot_quant.football_model.poisson import PoissonModel
from sys_foot_quant.football_model.scoring import total_variation_distance
from sys_foot_quant.football_model.xg_model import XGModel

_GOALS_COLS = ["home_team_id", "away_team_id", "home_goals", "away_goals", "kickoff_time"]
_XG_COLS = ["home_team_id", "away_team_id", "home_xg", "away_xg", "kickoff_time"]


def _goals_df() -> pd.DataFrame:
    return pd.DataFrame([(0, 1, 2, 1, 0), (1, 0, 1, 1, 1)], columns=_GOALS_COLS)


def _xg_df_agreeing() -> pd.DataFrame:
    # xG historique choisi pour reproduire (approximativement) les memes
    # ratios attaque/defense que les buts reels ci-dessus - TVD proche de 0.
    return pd.DataFrame([(0, 1, 2.0, 1.0, 0), (1, 0, 1.0, 1.0, 1)], columns=_XG_COLS)


def _xg_df_disagreeing() -> pd.DataFrame:
    # xG historique tres different des buts reels - TVD elevee attendue.
    return pd.DataFrame([(0, 1, 0.2, 3.5, 0), (1, 0, 3.5, 0.2, 1)], columns=_XG_COLS)


def test_predict_before_fit_raises() -> None:
    with pytest.raises(RuntimeError):
        GateDisagreementModel().predict_outcome_probabilities(0, 1)


def test_perfect_agreement_reduces_exactly_to_poisson_simple() -> None:
    goals_df = _goals_df()
    poisson = PoissonModel(use_team_hfa=False).fit(goals_df)
    xg = XGModel().fit(goals_df.rename(columns={"home_goals": "home_xg", "away_goals": "away_xg"}))
    p_poisson = poisson.predict_outcome_probabilities(0, 1)
    p_xg = xg.predict_outcome_probabilities(0, 1)
    # Verifie d'abord que ce jeu de donnees produit bien un desaccord nul
    # (meme historique, exactement recopie de buts vers xG) - condition
    # necessaire pour que ce test ait un sens.
    assert total_variation_distance(p_poisson, p_xg) == pytest.approx(0.0, abs=1e-9)

    gate = GateDisagreementModel().fit(
        goals_df, goals_df.rename(columns={"home_goals": "home_xg", "away_goals": "away_xg"})
    )
    assert gate.predict_outcome_probabilities(0, 1) == pytest.approx(p_poisson)


def test_blend_matches_hand_computation_with_tvd_as_weight() -> None:
    goals_df, xg_df = _goals_df(), _xg_df_disagreeing()
    gate = GateDisagreementModel().fit(goals_df, xg_df)

    poisson = PoissonModel(use_team_hfa=False).fit(goals_df)
    xg = XGModel().fit(xg_df)
    p_poisson = poisson.predict_outcome_probabilities(0, 1)
    p_xg = xg.predict_outcome_probabilities(0, 1)
    w = total_variation_distance(p_poisson, p_xg)
    assert w > 0.01  # ce jeu de donnees doit produire un desaccord non trivial

    expected = tuple((1 - w) * p + w * x for p, x in zip(p_poisson, p_xg))
    assert gate.predict_outcome_probabilities(0, 1) == pytest.approx(expected)


@pytest.mark.parametrize("xg_df_fn", [_xg_df_agreeing, _xg_df_disagreeing])
def test_probabilities_always_sum_to_one(xg_df_fn) -> None:
    gate = GateDisagreementModel().fit(_goals_df(), xg_df_fn())
    home, draw, away = gate.predict_outcome_probabilities(0, 1)
    assert home + draw + away == pytest.approx(1.0, abs=1e-9)
    assert home >= 0 and draw >= 0 and away >= 0


def test_does_not_modify_poisson_or_xg_model_behavior() -> None:
    goals_df, xg_df = _goals_df(), _xg_df_disagreeing()
    poisson_before = PoissonModel(use_team_hfa=False).fit(goals_df).predict_outcome_probabilities(0, 1)
    xg_before = XGModel().fit(xg_df).predict_outcome_probabilities(0, 1)

    GateDisagreementModel().fit(goals_df, xg_df).predict_outcome_probabilities(0, 1)

    poisson_after = PoissonModel(use_team_hfa=False).fit(goals_df).predict_outcome_probabilities(0, 1)
    xg_after = XGModel().fit(xg_df).predict_outcome_probabilities(0, 1)
    assert poisson_before == pytest.approx(poisson_after)
    assert xg_before == pytest.approx(xg_after)


def test_gate_has_no_free_parameters_beyond_max_goals_grid() -> None:
    """Garde de specification : le constructeur ne doit exposer aucun
    coefficient/seuil ajustable pour le melange lui-meme (seul
    ``max_goals``, une grille de calcul partagee avec les autres modeles,
    pas un parametre du gate)."""
    import inspect

    params = list(inspect.signature(GateDisagreementModel.__init__).parameters)
    assert params == ["self", "max_goals"]
