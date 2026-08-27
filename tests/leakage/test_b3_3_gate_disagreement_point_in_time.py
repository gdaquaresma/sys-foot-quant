"""B3.3 (docs/research_framework.md section B3.3) reutilise SANS
MODIFICATION le mecanisme point-in-time de ``real_data_walk_forward.py``,
deja couvert par ``test_real_data_walk_forward_point_in_time.py``. Ce
fichier verifie specifiquement les points propres a cette specification :
- que le gate n'accede jamais a l'issue du match, aux buts, au xG du
  match lui-meme, ou a une erreur realisee - uniquement aux sorties
  pre-match de poisson_simple et XGModel ;
- que le decoupage rodage/calibration/test est chronologiquement
  disjoint, meme convention que B1/A2/B2 ;
- que la phase de calibration est purement diagnostique : ses resultats
  (statistiques de TVD) ne peuvent structurellement influencer le
  comportement du gate (aucune fonction de fit ne prend ces
  diagnostics en argument) ;
- que w=0 exactement quand les deux modeles sont d'accord, et que le
  gate ne modifie jamais poisson_simple/XGModel eux-memes.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from sys_foot_quant.football_model.gate_disagreement_model import GateDisagreementModel
from sys_foot_quant.football_model.poisson import PoissonModel
from sys_foot_quant.football_model.xg_model import XGModel

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage5_b3_3_gate_disagreement.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage5_b3_3_gate_disagreement", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _goals_df() -> pd.DataFrame:
    return pd.DataFrame(
        [(0, 1, 2, 1, datetime(2024, 1, 1)), (1, 0, 1, 1, datetime(2024, 1, 2))],
        columns=["home_team_id", "away_team_id", "home_goals", "away_goals", "kickoff_time"],
    )


def _xg_df() -> pd.DataFrame:
    return pd.DataFrame(
        [(0, 1, 0.2, 3.0, datetime(2024, 1, 1)), (1, 0, 3.0, 0.2, datetime(2024, 1, 2))],
        columns=["home_team_id", "away_team_id", "home_xg", "away_xg", "kickoff_time"],
    )


def test_gate_fit_signature_receives_only_goals_and_xg_dataframes() -> None:
    """Garde structurelle : la fonction de fit du gate n'accepte que
    (goals_df, xg_df, decision_time) - la meme interface que tous les
    autres modeles reels - jamais l'issue du match ni une erreur realisee."""
    import inspect

    script = _load_script()
    sig = inspect.signature(script._fit_gate)
    assert list(sig.parameters) == ["goals_df", "xg_df", "decision_time"]


def test_gate_never_depends_on_match_outcome_or_realized_error() -> None:
    script = _load_script()
    goals_df, xg_df = _goals_df(), _xg_df()
    model_a = script._fit_gate(goals_df, xg_df, datetime(2024, 1, 3))
    model_b = script._fit_gate(goals_df, xg_df, datetime(2024, 1, 3))
    # Meme donnees d'entree -> memes predictions, quel que soit ce qui se
    # passera reellement dans le match evalue (jamais fourni ici).
    assert model_a.predict(0, 1) == pytest.approx(model_b.predict(0, 1))


def test_weight_is_exactly_zero_under_perfect_agreement() -> None:
    goals_df = _goals_df()
    xg_df_matching = goals_df.rename(columns={"home_goals": "home_xg", "away_goals": "away_xg"})
    gate = GateDisagreementModel().fit(goals_df, xg_df_matching)
    poisson = PoissonModel(use_team_hfa=False).fit(goals_df)
    assert gate.predict_outcome_probabilities(0, 1) == pytest.approx(
        poisson.predict_outcome_probabilities(0, 1), abs=1e-9
    )


def test_calibration_diagnostics_are_pure_and_do_not_feed_back_into_fits() -> None:
    """``_tvd_diagnostics`` ne fait que lire des predictions deja
    calculees et retourne un dict de statistiques descriptives - il n'est
    jamais passe en argument a ``_fit_gate``/``_fit_poisson_simple``/
    ``_fit_xg`` (verifie par inspection de signature, garde anti-fuite
    structurelle contre un futur ajout accidentel)."""
    import inspect

    script = _load_script()
    for fn in (script._fit_poisson_simple, script._fit_xg, script._fit_gate):
        params = list(inspect.signature(fn).parameters)
        assert "diagnostics" not in params
        assert "calibration" not in " ".join(params).lower()


def test_split_eval_ids_are_chronologically_disjoint() -> None:
    from datetime import timedelta

    script = _load_script()

    class _Rec:
        def __init__(self, match_id: str, kickoff) -> None:
            self.match_id = match_id
            self.kickoff_utc = kickoff

    t0 = datetime(2024, 1, 1)
    records = [_Rec(str(i), t0 + timedelta(days=i)) for i in range(100)]
    calibration_ids, test_ids = script._split_eval_ids(records)
    assert set(calibration_ids).isdisjoint(set(test_ids))
    assert len(calibration_ids) == 30
    assert len(test_ids) == 30
    assert calibration_ids == [str(i) for i in range(40, 70)]
    assert test_ids == [str(i) for i in range(70, 100)]


def test_gate_does_not_modify_poisson_or_xg_model_behavior() -> None:
    goals_df, xg_df = _goals_df(), _xg_df()
    poisson_before = PoissonModel(use_team_hfa=False).fit(goals_df).predict_outcome_probabilities(0, 1)
    xg_before = XGModel().fit(xg_df).predict_outcome_probabilities(0, 1)

    GateDisagreementModel().fit(goals_df, xg_df).predict_outcome_probabilities(0, 1)

    poisson_after = PoissonModel(use_team_hfa=False).fit(goals_df).predict_outcome_probabilities(0, 1)
    xg_after = XGModel().fit(xg_df).predict_outcome_probabilities(0, 1)
    assert poisson_before == pytest.approx(poisson_after)
    assert xg_before == pytest.approx(xg_after)


def test_paired_metric_diffs_skip_matches_with_missing_predictions() -> None:
    from sys_foot_quant.calibration_engine.metrics import brier_score

    script = _load_script()

    class _Ev:
        def __init__(self, outcome, predictions) -> None:
            self.outcome = outcome
            self.predictions = predictions

    evals = [
        _Ev(0, {"poisson_simple": (0.6, 0.3, 0.1), "gate": (0.65, 0.25, 0.1)}),
        _Ev(1, {"poisson_simple": (0.4, 0.3, 0.3), "gate": None}),
    ]
    diffs = script._paired_metric_diffs(evals, "poisson_simple", "gate", brier_score)
    assert len(diffs) == 1
