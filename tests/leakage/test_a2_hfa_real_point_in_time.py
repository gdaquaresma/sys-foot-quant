"""A2 sur donnees reelles (docs/research_framework.md section A2) reutilise
SANS MODIFICATION le mecanisme point-in-time de ``real_data_walk_forward.py``,
deja couvert par ``test_real_data_walk_forward_point_in_time.py``. Ce
fichier verifie specifiquement les points propres a ce script :
- que poisson_simple et a2_hfa ignorent completement le xG ;
- que le decoupage rodage/validation/test est chronologiquement disjoint ;
- que a2_hfa n'affecte pas le comportement de poisson_simple (aucun etat
  partage) ;
- que le HFA par equipe differe reellement d'un HFA global constant une
  fois entraine (sinon le test complet n'aurait aucune chance de detecter
  quoi que ce soit).
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from sys_foot_quant.football_model.poisson import PoissonModel

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage5_a2_hfa_real.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage5_a2_hfa_real", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _goals_df() -> pd.DataFrame:
    # Equipe 0 tres majoritairement a domicile avec de bons resultats -
    # doit produire un HFA specifique different du HFA global.
    rows = [(0, 1, 3, 0, datetime(2024, 1, 1)), (0, 2, 2, 0, datetime(2024, 1, 3))]
    rows += [(1, 2, 1, 1, datetime(2024, 1, 2)), (2, 1, 1, 1, datetime(2024, 1, 4))]
    return pd.DataFrame(rows, columns=["home_team_id", "away_team_id", "home_goals", "away_goals", "kickoff_time"])


def test_poisson_and_a2_fits_ignore_xg_dataframe() -> None:
    script = _load_script()
    goals_df = _goals_df()
    xg_df_a = pd.DataFrame(
        [(0, 1, 9.9, 9.9, datetime(2024, 1, 1))],
        columns=["home_team_id", "away_team_id", "home_xg", "away_xg", "kickoff_time"],
    )
    xg_df_b = pd.DataFrame(columns=["home_team_id", "away_team_id", "home_xg", "away_xg", "kickoff_time"])

    poisson_a = script._fit_poisson_simple(goals_df, xg_df_a, datetime(2024, 1, 5))
    poisson_b = script._fit_poisson_simple(goals_df, xg_df_b, datetime(2024, 1, 5))
    assert poisson_a.predict_outcome_probabilities(0, 1) == pytest.approx(
        poisson_b.predict_outcome_probabilities(0, 1)
    )

    a2_a = script._fit_a2_hfa(goals_df, xg_df_a, datetime(2024, 1, 5))
    a2_b = script._fit_a2_hfa(goals_df, xg_df_b, datetime(2024, 1, 5))
    assert a2_a.predict_outcome_probabilities(0, 1) == pytest.approx(a2_b.predict_outcome_probabilities(0, 1))


def test_a2_does_not_modify_poisson_simple_behavior() -> None:
    goals_df = _goals_df()
    poisson_before = PoissonModel(use_team_hfa=False).fit(goals_df).predict_outcome_probabilities(0, 1)

    script = _load_script()
    script._fit_a2_hfa(goals_df, xg_df=None, decision_time=None)

    poisson_after = PoissonModel(use_team_hfa=False).fit(goals_df).predict_outcome_probabilities(0, 1)
    assert poisson_before == pytest.approx(poisson_after)


def test_a2_hfa_actually_differs_from_global_hfa_once_fitted() -> None:
    """Garde-fou de sanite du protocole : si le HFA par equipe convergeait
    toujours vers le HFA global sur des donnees asymetriques, le test A2
    n'aurait structurellement aucune chance de detecter un signal."""
    script = _load_script()
    goals_df = _goals_df()
    model = script._fit_a2_hfa(goals_df, xg_df=None, decision_time=None)
    assert model.hfa_team_ is not None
    assert model.hfa_global_ is not None
    hfa_values = set(round(v, 6) for v in model.hfa_team_.values())
    # Au moins une equipe doit avoir un HFA specifique different du HFA
    # global une fois shrink (sinon use_team_hfa=True serait un no-op).
    assert any(abs(v - model.hfa_global_) > 1e-9 for v in model.hfa_team_.values())
    assert len(hfa_values) > 1


def test_split_eval_ids_are_chronologically_disjoint_and_ordered() -> None:
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
    assert n_burn_in == 20  # 40% de 50
    all_eval_ids = set(validation_ids) | set(test_ids)
    burn_in_ids = {str(i) for i in range(20)}
    assert all_eval_ids.isdisjoint(burn_in_ids)


def test_paired_metric_diffs_skip_matches_with_missing_predictions() -> None:
    from sys_foot_quant.calibration_engine.metrics import brier_score

    script = _load_script()

    class _Ev:
        def __init__(self, outcome, predictions) -> None:
            self.outcome = outcome
            self.predictions = predictions

    evals = [
        _Ev(0, {"poisson_simple": (0.6, 0.3, 0.1), "a2_hfa": (0.65, 0.25, 0.1)}),
        _Ev(1, {"poisson_simple": (0.4, 0.3, 0.3), "a2_hfa": None}),
    ]
    diffs = script._paired_metric_diffs(evals, "poisson_simple", "a2_hfa", brier_score)
    assert len(diffs) == 1
