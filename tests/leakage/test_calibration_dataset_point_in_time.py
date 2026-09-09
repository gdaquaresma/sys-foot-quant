"""Garde-fous anti-fuite et de non-regression pour
``calibration_engine.calibration_dataset.build_calibration_dataframe`` -
portage VERBATIM de
``scripts/run_stage15_e7_total_goals_distribution.build_lambda_mu_dataframe``
(E7), generalise uniquement sur la source des donnees (voir docstring du
module) :

- le mecanisme point-in-time est INTEGRALEMENT delegue aux fonctions deja
  testees de ``real_data_walk_forward`` (``_goals_train_df``/
  ``_xg_train_df``) - jamais reimplemente ici ;
- ajouter un match futur ne doit jamais changer le (lambda, mu) deja
  calcule pour un match anterieur (invariant walk-forward) ;
- pour CHAQUE ligne produite, (lambda, mu, rho) doivent etre identiques a
  un calcul manuel effectue en filtrant l'historique point-in-time
  independamment (memes garanties que
  ``tests/leakage/test_real_data_walk_forward_point_in_time.py``,
  appliquees ici au niveau de la fonction publique) ;
- non-regression : sur le corpus reel, la sortie de cette fonction doit
  correspondre EXACTEMENT (lambda/mu/rho) a celle deja publiee par E7
  (``build_lambda_mu_dataframe``) et par extension E8, sur le meme corpus.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sys_foot_quant.backtesting_engine.real_data_walk_forward import (
    RealMatchRecord,
    _goals_train_df,
    _xg_train_df,
)
from sys_foot_quant.calibration_engine.calibration_dataset import build_calibration_dataframe
from sys_foot_quant.football_model.dixon_coles import DixonColesModel
from sys_foot_quant.football_model.poisson import PoissonModel
from sys_foot_quant.football_model.xg_model import XGModel

_T0 = datetime(2024, 1, 1)
_MIN_TRAIN_MATCHES = 5

_SRC_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "src"
    / "sys_foot_quant"
    / "calibration_engine"
    / "calibration_dataset.py"
)
_STAGE8_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage8_diagnostic_total_goals_over_under.py"
_E7_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage15_e7_total_goals_distribution.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


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


# --- 1. point-in-time integralement delegue, jamais reimplemente -----------


def test_never_reimplements_point_in_time_filtering() -> None:
    source = _SRC_PATH.read_text()
    assert "_goals_train_df" in source
    assert "_xg_train_df" in source
    # aucun filtre de connaissance temporelle reimplemente localement
    assert "knowledge_time <=" not in source
    assert "knowledge_time >=" not in source
    assert "knowledge_time <" not in source


# --- 2. un match futur ne change jamais un (lambda, mu) deja calcule -------


def test_adding_a_future_match_never_changes_an_earlier_row() -> None:
    records = _synthetic_records(15)
    df_before = build_calibration_dataframe(records, min_train_matches=_MIN_TRAIN_MATCHES)

    future = _record("future", _T0 + timedelta(days=1000), 0, 1, home_goals=5, away_goals=0)
    df_after = build_calibration_dataframe(records + [future], min_train_matches=_MIN_TRAIN_MATCHES)

    merged = df_before.merge(df_after, on="match_id", suffixes=("_before", "_after"))
    assert len(merged) == len(df_before)
    for model in ("poisson_simple", "dixon_coles", "xg_model"):
        for suffix in ("lambda", "mu"):
            col = f"{model}_{suffix}"
            np.testing.assert_allclose(
                merged[f"{col}_before"].to_numpy(dtype=float),
                merged[f"{col}_after"].to_numpy(dtype=float),
                equal_nan=True,
            )


def test_inserting_a_match_between_two_others_never_changes_earlier_rows() -> None:
    """Meme garantie que ci-dessus, mais le match ajoute est intercale
    chronologiquement (pas seulement ajoute a la fin) - verifie que le tri
    interne ne cree pas de fuite indirecte."""
    records = _synthetic_records(15)
    df_before = build_calibration_dataframe(records, min_train_matches=_MIN_TRAIN_MATCHES)

    inserted = _record("inserted", _T0 + timedelta(days=9, hours=12), 2, 3, home_goals=2, away_goals=2)
    df_after = build_calibration_dataframe(records + [inserted], min_train_matches=_MIN_TRAIN_MATCHES)

    # Seuls les matchs strictement posterieurs a l'insertion peuvent changer.
    earlier_ids = [r.match_id for r in records if r.kickoff_utc <= inserted.kickoff_utc]
    merged = df_before[df_before["match_id"].isin(earlier_ids)].merge(
        df_after, on="match_id", suffixes=("_before", "_after")
    )
    assert len(merged) == len(earlier_ids)
    for model in ("poisson_simple", "dixon_coles", "xg_model"):
        for suffix in ("lambda", "mu"):
            col = f"{model}_{suffix}"
            np.testing.assert_allclose(
                merged[f"{col}_before"].to_numpy(dtype=float),
                merged[f"{col}_after"].to_numpy(dtype=float),
                equal_nan=True,
            )


# --- 3. chaque ligne == calcul manuel independant filtre point-in-time -----


def test_lambda_mu_matches_manual_point_in_time_fit_for_every_row() -> None:
    records = _synthetic_records(20)
    df = build_calibration_dataframe(records, min_train_matches=_MIN_TRAIN_MATCHES)

    for r in records:
        decision_time = r.kickoff_utc - timedelta(hours=2.0)
        goals_df = _goals_train_df(records, decision_time, exclude_match_id=r.match_id)
        xg_df = _xg_train_df(records, decision_time, exclude_match_id=r.match_id)
        row = df.loc[df["match_id"] == r.match_id].iloc[0]

        if len(goals_df) >= _MIN_TRAIN_MATCHES:
            poisson = PoissonModel(use_team_hfa=False).fit(goals_df)
            lam, mu = poisson.predict_lambda_mu(r.home_team_id, r.away_team_id)
            assert row["poisson_simple_lambda"] == pytest.approx(lam)
            assert row["poisson_simple_mu"] == pytest.approx(mu)

            dc = DixonColesModel(use_team_hfa=False).fit(goals_df)
            dc_lam, dc_mu = dc.predict_lambda_mu(r.home_team_id, r.away_team_id)
            assert row["dixon_coles_lambda"] == pytest.approx(dc_lam)
            assert row["dixon_coles_mu"] == pytest.approx(dc_mu)
            assert row["dixon_coles_rho"] == pytest.approx(dc.rho_)
        else:
            assert pd.isna(row["poisson_simple_lambda"])
            assert pd.isna(row["dixon_coles_rho"])

        if len(xg_df) >= _MIN_TRAIN_MATCHES:
            xg = XGModel(max_goals=20).fit(xg_df)
            xg_lam, xg_mu = xg.predict_lambda_mu(r.home_team_id, r.away_team_id)
            assert row["xg_model_lambda"] == pytest.approx(xg_lam)
            assert row["xg_model_mu"] == pytest.approx(xg_mu)
        else:
            assert pd.isna(row["xg_model_lambda"])


# --- 4. non-regression : corpus reel, identique a E7/E8 --------------------


@pytest.mark.skipif(
    not (Path(__file__).resolve().parent.parent.parent / "research" / "xg_feasibility" / "runs").exists(),
    reason="Fichiers Understat reels non presents.",
)
def test_real_corpus_matches_e7_build_lambda_mu_dataframe_exactly() -> None:
    stage8 = _load(_STAGE8_PATH, "run_stage8_diagnostic_total_goals_over_under_for_calibration_dataset_test")
    e7_module = _load(_E7_PATH, "run_stage15_e7_total_goals_distribution_for_calibration_dataset_test")

    new_parts = []
    for season, leagues in stage8._SEASONS.items():
        for name in leagues:
            season_records = stage8._load_records(name, season)
            new_parts.append(build_calibration_dataframe(season_records))
    new_df = pd.concat(new_parts, ignore_index=True)

    e7_df = e7_module.build_lambda_mu_dataframe(stage8)

    merged = new_df.merge(e7_df, on="match_id", suffixes=("_new", "_e7"))
    assert len(merged) > 2000  # les deux couvrent bien le meme corpus complet

    for model in ("poisson_simple", "dixon_coles", "xg_model"):
        for suffix in ("lambda", "mu"):
            col = f"{model}_{suffix}"
            both = merged[f"{col}_new"].notna() & merged[f"{col}_e7"].notna()
            assert both.sum() > 2000
            np.testing.assert_allclose(
                merged.loc[both, f"{col}_new"].to_numpy(),
                merged.loc[both, f"{col}_e7"].to_numpy(),
                atol=1e-9,
            )

    both_rho = merged["dixon_coles_rho_new"].notna() & merged["dixon_coles_rho_e7"].notna()
    assert both_rho.sum() > 2000
    np.testing.assert_allclose(
        merged.loc[both_rho, "dixon_coles_rho_new"].to_numpy(),
        merged.loc[both_rho, "dixon_coles_rho_e7"].to_numpy(),
        atol=1e-9,
    )
