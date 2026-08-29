from __future__ import annotations

import pandas as pd

from sys_foot_quant.final_engine.prediction import PRIMARY_MODEL, predict_match


def _goals_df(n: int) -> pd.DataFrame:
    rows = []
    for i in range(n):
        rows.append({"home_team_id": i % 4, "away_team_id": (i + 1) % 4, "home_goals": 1, "away_goals": 1})
    return pd.DataFrame(rows)


def _xg_df(n: int) -> pd.DataFrame:
    rows = []
    for i in range(n):
        rows.append({"home_team_id": i % 4, "away_team_id": (i + 1) % 4, "home_xg": 1.2, "away_xg": 0.9})
    return pd.DataFrame(rows)


def test_primary_model_is_poisson_simple() -> None:
    assert PRIMARY_MODEL == "poisson_simple"


def test_returns_none_for_all_models_when_history_insufficient() -> None:
    predictions = predict_match(0, 1, _goals_df(5), _xg_df(5), min_train_matches=10)
    assert predictions["poisson_simple"] is None
    assert predictions["dixon_coles"] is None
    assert predictions["xg_model"] is None


def test_returns_predictions_when_history_sufficient() -> None:
    predictions = predict_match(0, 1, _goals_df(20), _xg_df(20), min_train_matches=10)
    assert predictions["poisson_simple"] is not None
    assert predictions["poisson_simple"].lam > 0
    assert predictions["poisson_simple"].mu > 0
    assert predictions["poisson_simple"].n_train_matches == 20
    assert predictions["poisson_simple"].rho is None

    assert predictions["dixon_coles"] is not None
    assert predictions["dixon_coles"].rho is not None

    assert predictions["xg_model"] is not None
    assert predictions["xg_model"].n_train_matches == 20


def test_xg_model_independently_gated_from_goals_models() -> None:
    """L'historique xG insuffisant ne doit jamais empecher
    poisson_simple/dixon_coles d'etre predits, et inversement
    (docs/final_engine_specification.md section 4.1)."""
    predictions = predict_match(0, 1, _goals_df(20), _xg_df(3), min_train_matches=10)
    assert predictions["poisson_simple"] is not None
    assert predictions["dixon_coles"] is not None
    assert predictions["xg_model"] is None


def test_missing_xg_dataframe_never_raises() -> None:
    predictions = predict_match(0, 1, _goals_df(20), None, min_train_matches=10)
    assert predictions["poisson_simple"] is not None
    assert predictions["xg_model"] is None
