"""B2 sur donnees reelles (docs/research_framework.md section B2) reutilise
SANS MODIFICATION le mecanisme point-in-time de ``real_data_walk_forward.py``,
deja couvert par ``test_real_data_walk_forward_point_in_time.py``. Ce
fichier verifie specifiquement les points propres a ce script :
- que poisson_simple et b2_bayesian ignorent completement le xG ;
- que le decoupage rodage/validation/test est chronologiquement disjoint,
  meme convention que B1/A2/B3 ;
- que b2_bayesian n'affecte pas le comportement de poisson_simple ;
- que la mise a jour sequentielle de BayesianSequentialModel respecte
  l'ordre chronologique meme si le DataFrame d'entree recu du walk-forward
  n'est pas deja trie (garde-fou specifique a ce modele, deja code dans
  ``bayesian_sequential.py`` via un tri stable explicite - verifie ici
  dans le contexte de ce script).
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from sys_foot_quant.football_model.bayesian_sequential import BayesianSequentialModel
from sys_foot_quant.football_model.poisson import PoissonModel

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage5_b2_bayesian_real.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage5_b2_bayesian_real", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _goals_df() -> pd.DataFrame:
    rows = [
        (0, 1, 2, 1, datetime(2024, 1, 1)),
        (1, 0, 1, 1, datetime(2024, 1, 2)),
        (0, 2, 3, 0, datetime(2024, 1, 3)),
    ]
    return pd.DataFrame(rows, columns=["home_team_id", "away_team_id", "home_goals", "away_goals", "kickoff_time"])


def test_poisson_and_b2_fits_ignore_xg_dataframe() -> None:
    script = _load_script()
    goals_df = _goals_df()
    xg_df_a = pd.DataFrame(
        [(0, 1, 9.9, 9.9, datetime(2024, 1, 1))],
        columns=["home_team_id", "away_team_id", "home_xg", "away_xg", "kickoff_time"],
    )
    xg_df_b = pd.DataFrame(columns=["home_team_id", "away_team_id", "home_xg", "away_xg", "kickoff_time"])

    poisson_a = script._fit_poisson_simple(goals_df, xg_df_a, datetime(2024, 1, 4))
    poisson_b = script._fit_poisson_simple(goals_df, xg_df_b, datetime(2024, 1, 4))
    assert poisson_a.predict_outcome_probabilities(0, 1) == pytest.approx(
        poisson_b.predict_outcome_probabilities(0, 1)
    )

    b2_a = script._fit_b2_bayesian(goals_df, xg_df_a, datetime(2024, 1, 4))
    b2_b = script._fit_b2_bayesian(goals_df, xg_df_b, datetime(2024, 1, 4))
    assert b2_a.predict_outcome_probabilities(0, 1) == pytest.approx(b2_b.predict_outcome_probabilities(0, 1))


def test_b2_does_not_modify_poisson_simple_behavior() -> None:
    goals_df = _goals_df()
    poisson_before = PoissonModel(use_team_hfa=False).fit(goals_df).predict_outcome_probabilities(0, 1)

    script = _load_script()
    script._fit_b2_bayesian(goals_df, xg_df=None, decision_time=None)

    poisson_after = PoissonModel(use_team_hfa=False).fit(goals_df).predict_outcome_probabilities(0, 1)
    assert poisson_before == pytest.approx(poisson_after)


def test_b2_sequential_update_is_order_invariant_to_input_row_order() -> None:
    """Le walk-forward peut fournir goals_df dans un ordre arbitraire
    (le Repository ne garantit pas l'ordre des lignes) - BayesianSequentialModel
    doit produire le MEME resultat quel que soit l'ordre d'entree, puisqu'il
    re-trie explicitement par kickoff_time avant la boucle sequentielle."""
    script = _load_script()
    goals_df = _goals_df()
    shuffled = goals_df.iloc[[2, 0, 1]].reset_index(drop=True)

    model_ordered = script._fit_b2_bayesian(goals_df, xg_df=None, decision_time=None)
    model_shuffled = script._fit_b2_bayesian(shuffled, xg_df=None, decision_time=None)

    assert model_ordered.predict_outcome_probabilities(0, 1) == pytest.approx(
        model_shuffled.predict_outcome_probabilities(0, 1)
    )


def test_split_eval_ids_are_chronologically_disjoint() -> None:
    from datetime import timedelta

    script = _load_script()

    class _Rec:
        def __init__(self, match_id: str, kickoff) -> None:
            self.match_id = match_id
            self.kickoff_utc = kickoff

    t0 = datetime(2024, 1, 1)
    records = [_Rec(str(i), t0 + timedelta(days=i)) for i in range(50)]
    validation_ids, test_ids = script._split_eval_ids(records)
    assert set(validation_ids).isdisjoint(set(test_ids))
    n_burn_in = 50 - len(validation_ids) - len(test_ids)
    assert n_burn_in == 20
    burn_in_ids = {str(i) for i in range(20)}
    assert (set(validation_ids) | set(test_ids)).isdisjoint(burn_in_ids)


def test_paired_metric_diffs_skip_matches_with_missing_predictions() -> None:
    from sys_foot_quant.calibration_engine.metrics import brier_score

    script = _load_script()

    class _Ev:
        def __init__(self, outcome, predictions) -> None:
            self.outcome = outcome
            self.predictions = predictions

    evals = [
        _Ev(0, {"poisson_simple": (0.6, 0.3, 0.1), "b2_bayesian": (0.65, 0.25, 0.1)}),
        _Ev(1, {"poisson_simple": (0.4, 0.3, 0.3), "b2_bayesian": None}),
    ]
    diffs = script._paired_metric_diffs(evals, "poisson_simple", "b2_bayesian", brier_score)
    assert len(diffs) == 1
