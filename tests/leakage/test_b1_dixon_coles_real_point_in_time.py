"""B1 sur donnees reelles (docs/research_framework.md section B1) reutilise
SANS MODIFICATION le mecanisme point-in-time de ``real_data_walk_forward.py``,
deja couvert par ``test_real_data_walk_forward_point_in_time.py``. Ce
fichier verifie specifiquement les points propres a ce script :
- que poisson_simple et dixon_coles (variantes normale ET bas-score)
  ignorent completement le xG (aucune dependance, meme accidentelle) ;
- que le decoupage rodage/validation/test est chronologiquement disjoint,
  sans chevauchement, meme invariant que B3 ;
- que la comparaison n'utilise jamais que les matchs ou les DEUX modeles
  ont une prediction (aucun match orphelin cote a cote).
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from sys_foot_quant.football_model.dixon_coles import DixonColesModel
from sys_foot_quant.football_model.poisson import PoissonModel

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage5_b1_dixon_coles_real.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage5_b1_dixon_coles_real", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _goals_df() -> pd.DataFrame:
    return pd.DataFrame(
        [(0, 1, 2, 1, datetime(2024, 1, 1)), (1, 0, 0, 0, datetime(2024, 1, 2)), (0, 1, 1, 1, datetime(2024, 1, 3))],
        columns=["home_team_id", "away_team_id", "home_goals", "away_goals", "kickoff_time"],
    )


def test_poisson_and_dixon_coles_fits_ignore_xg_dataframe() -> None:
    script = _load_script()
    goals_df = _goals_df()
    xg_df_a = pd.DataFrame(
        [(0, 1, 9.9, 9.9, datetime(2024, 1, 1))],
        columns=["home_team_id", "away_team_id", "home_xg", "away_xg", "kickoff_time"],
    )
    xg_df_b = pd.DataFrame(columns=["home_team_id", "away_team_id", "home_xg", "away_xg", "kickoff_time"])

    poisson_a = script._fit_poisson_simple(goals_df, xg_df_a, datetime(2024, 1, 4))
    poisson_b = script._fit_poisson_simple(goals_df, xg_df_b, datetime(2024, 1, 4))
    assert isinstance(poisson_a, PoissonModel)
    assert poisson_a.predict_outcome_probabilities(0, 1) == pytest.approx(
        poisson_b.predict_outcome_probabilities(0, 1)
    )

    dc_a = script._fit_dixon_coles(goals_df, xg_df_a, datetime(2024, 1, 4))
    dc_b = script._fit_dixon_coles(goals_df, xg_df_b, datetime(2024, 1, 4))
    assert isinstance(dc_a, DixonColesModel)
    assert dc_a.predict_outcome_probabilities(0, 1) == pytest.approx(dc_b.predict_outcome_probabilities(0, 1))
    assert dc_a.rho_ == pytest.approx(dc_b.rho_)


def test_lowscore_fits_also_ignore_xg_dataframe() -> None:
    script = _load_script()
    goals_df = _goals_df()
    xg_df_a = pd.DataFrame(
        [(0, 1, 9.9, 9.9, datetime(2024, 1, 1))],
        columns=["home_team_id", "away_team_id", "home_xg", "away_xg", "kickoff_time"],
    )
    xg_df_b = pd.DataFrame(columns=["home_team_id", "away_team_id", "home_xg", "away_xg", "kickoff_time"])

    wrapped_a = script._fit_dixon_coles_lowscore(goals_df, xg_df_a, datetime(2024, 1, 4))
    wrapped_b = script._fit_dixon_coles_lowscore(goals_df, xg_df_b, datetime(2024, 1, 4))
    assert wrapped_a.predict(0, 1) == pytest.approx(wrapped_b.predict(0, 1))


def test_lowscore_wrapper_delegates_to_predict_low_score_probs() -> None:
    script = _load_script()
    goals_df = _goals_df()
    model = DixonColesModel(use_team_hfa=False).fit(goals_df)
    wrapper = script._LowScoreWrapper(model)
    assert wrapper.predict(0, 1) == model.predict_low_score_probs(0, 1)


def test_split_eval_ids_are_chronologically_disjoint_and_ordered() -> None:
    script = _load_script()

    class _Rec:
        def __init__(self, match_id: str, kickoff: datetime) -> None:
            self.match_id = match_id
            self.kickoff_utc = kickoff

    t0 = datetime(2024, 1, 1)
    records = [_Rec(str(i), t0 + timedelta(days=i)) for i in range(100)]
    validation_ids, test_ids = script._split_eval_ids(records)

    assert set(validation_ids).isdisjoint(set(test_ids))
    n_burn_in = 100 - len(validation_ids) - len(test_ids)
    assert n_burn_in == 40
    assert len(validation_ids) == 30
    assert len(test_ids) == 30
    # Rodage = les 40 plus anciens, validation = les 30 suivants, test = les 30 derniers.
    assert validation_ids == [str(i) for i in range(40, 70)]
    assert test_ids == [str(i) for i in range(70, 100)]


def test_low_score_records_only_uses_matches_where_both_models_predicted() -> None:
    script = _load_script()

    class _Ev:
        def __init__(self, home_goals, away_goals, predictions) -> None:
            self.home_goals = home_goals
            self.away_goals = away_goals
            self.predictions = predictions

    complete = _Ev(0, 0, {"poisson_simple_lowscore": (0.3, 0.2, 0.2, 0.1), "dixon_coles_lowscore": (0.28, 0.2, 0.2, 0.1)})
    missing_dc = _Ev(1, 0, {"poisson_simple_lowscore": (0.2, 0.3, 0.2, 0.1), "dixon_coles_lowscore": None})
    not_low_score = _Ev(3, 2, {"poisson_simple_lowscore": (0.2, 0.2, 0.2, 0.1), "dixon_coles_lowscore": (0.2, 0.2, 0.2, 0.1)})

    records = script._low_score_records([complete, missing_dc, not_low_score])
    assert len(records) == 1
    assert records.iloc[0]["cell"] == 0  # 0-0


def test_paired_metric_diffs_skip_matches_with_missing_predictions() -> None:
    from sys_foot_quant.calibration_engine.metrics import brier_score

    script = _load_script()

    class _Ev:
        def __init__(self, outcome, predictions) -> None:
            self.outcome = outcome
            self.predictions = predictions

    evals = [
        _Ev(0, {"poisson_simple": (0.6, 0.3, 0.1), "dixon_coles": (0.65, 0.25, 0.1)}),
        _Ev(1, {"poisson_simple": (0.4, 0.3, 0.3), "dixon_coles": None}),
    ]
    diffs = script._paired_metric_diffs(evals, "poisson_simple", "dixon_coles", brier_score)
    assert len(diffs) == 1
