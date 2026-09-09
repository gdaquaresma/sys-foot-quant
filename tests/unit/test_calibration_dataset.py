from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

from sys_foot_quant.backtesting_engine.real_data_walk_forward import RealMatchRecord
from sys_foot_quant.calibration_engine.calibration_dataset import (
    MODELS,
    build_calibration_dataframe,
    split_calibration_df_by_model,
)

_T0 = datetime(2024, 1, 1)
_MIN_TRAIN_MATCHES = 5


def _record(
    match_id: str,
    kickoff: datetime,
    home_team_id: int,
    away_team_id: int,
    home_goals: int,
    away_goals: int,
) -> RealMatchRecord:
    return RealMatchRecord(
        match_id=match_id,
        league="TEST",
        kickoff_utc=kickoff,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        home_goals=home_goals,
        away_goals=away_goals,
        home_xg=1.0 + 0.1 * home_goals,
        away_xg=0.8 + 0.1 * away_goals,
        goals_knowledge_time=kickoff + timedelta(hours=2.0),
        xg_knowledge_time=kickoff + timedelta(hours=48.0),
    )


def _synthetic_records(n: int) -> list[RealMatchRecord]:
    teams = [0, 1, 2, 3]
    return [
        _record(
            str(i),
            _T0 + timedelta(days=i),
            teams[i % 4],
            teams[(i + 1) % 4],
            home_goals=i % 3,
            away_goals=(i + 1) % 2,
        )
        for i in range(n)
    ]


def test_base_columns_and_decision_time() -> None:
    records = _synthetic_records(10)
    df = build_calibration_dataframe(records, min_train_matches=_MIN_TRAIN_MATCHES)

    assert len(df) == 10
    for col in ("match_id", "league", "decision_time", "home_goals", "away_goals", "total_goals"):
        assert col in df.columns
    for r in records:
        row = df.loc[df["match_id"] == r.match_id].iloc[0]
        assert row["decision_time"] == r.kickoff_utc - timedelta(hours=2.0)
        assert row["total_goals"] == r.home_goals + r.away_goals


def test_lambda_mu_columns_present_for_every_model() -> None:
    records = _synthetic_records(10)
    df = build_calibration_dataframe(records, min_train_matches=_MIN_TRAIN_MATCHES)
    for model in MODELS:
        assert f"{model}_lambda" in df.columns
        assert f"{model}_mu" in df.columns
    assert "dixon_coles_rho" in df.columns


def test_nan_below_min_train_matches_never_a_fabricated_value() -> None:
    """Les tout premiers matchs (aucun historique anterieur suffisant)
    doivent recevoir NaN - jamais une valeur de repli inventee, meme
    comportement que build_lambda_mu_dataframe (E7)."""
    records = _synthetic_records(2 * _MIN_TRAIN_MATCHES)
    df = build_calibration_dataframe(records, min_train_matches=_MIN_TRAIN_MATCHES)
    ordered = df.sort_values("decision_time").reset_index(drop=True)

    # Le tout premier match n'a par construction aucun historique anterieur.
    first_row = ordered.iloc[0]
    for model in MODELS:
        assert pd.isna(first_row[f"{model}_lambda"])
        assert pd.isna(first_row[f"{model}_mu"])
    assert pd.isna(first_row["dixon_coles_rho"])

    # Une fois assez de matchs ecoules, l'historique doit devenir suffisant.
    last_row = ordered.iloc[-1]
    for model in MODELS:
        assert pd.notna(last_row[f"{model}_lambda"])
        assert pd.notna(last_row[f"{model}_mu"])
    assert pd.notna(last_row["dixon_coles_rho"])


def test_records_do_not_need_to_be_pre_sorted() -> None:
    records = _synthetic_records(10)
    shuffled = [records[i] for i in (3, 0, 7, 1, 9, 2, 8, 4, 6, 5)]
    df_sorted_input = build_calibration_dataframe(records, min_train_matches=_MIN_TRAIN_MATCHES)
    df_shuffled_input = build_calibration_dataframe(shuffled, min_train_matches=_MIN_TRAIN_MATCHES)

    merged = df_sorted_input.merge(df_shuffled_input, on="match_id", suffixes=("_sorted", "_shuffled"))
    assert len(merged) == 10
    for model in MODELS:
        for suffix in ("lambda", "mu"):
            col = f"{model}_{suffix}"
            pd.testing.assert_series_equal(
                merged[f"{col}_sorted"], merged[f"{col}_shuffled"], check_names=False
            )


def test_split_calibration_df_by_model_output_format() -> None:
    records = _synthetic_records(10)
    df = build_calibration_dataframe(records, min_train_matches=_MIN_TRAIN_MATCHES)
    split = split_calibration_df_by_model(df)

    assert set(split.keys()) == set(MODELS)
    for model in MODELS:
        model_df = split[model]
        assert list(model_df.columns) == ["decision_time", f"{model}_lambda", f"{model}_mu", "total_goals"]
        # Aucun pre-filtrage des NaN : meme nombre de lignes que le df source
        # (fit_scale_correction_as_of applique deja son propre dropna).
        assert len(model_df) == len(df)


def test_split_calibration_df_by_model_accepts_a_custom_model_subset() -> None:
    records = _synthetic_records(10)
    df = build_calibration_dataframe(records, min_train_matches=_MIN_TRAIN_MATCHES)
    split = split_calibration_df_by_model(df, models=("poisson_simple",))
    assert set(split.keys()) == {"poisson_simple"}


@pytest.mark.parametrize("min_train_matches", [1, 3, 8])
def test_min_train_matches_is_respected(min_train_matches: int) -> None:
    records = _synthetic_records(12)
    df = build_calibration_dataframe(records, min_train_matches=min_train_matches)
    ordered = df.sort_values("decision_time").reset_index(drop=True)
    # Les min_train_matches premiers matchs n'ont jamais assez d'historique
    # anterieur (au plus i matchs anterieurs disponibles pour le i-eme).
    for i in range(min_train_matches):
        assert pd.isna(ordered.iloc[i]["poisson_simple_lambda"])
