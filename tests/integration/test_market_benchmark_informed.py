"""Verifie que le marche synthetique corrige est reellement "informe" : ses
probabilites (marge retiree) doivent etre plus proches de la realite que
le benchmark naif, puisqu'elles sont maintenant centrees sur les vraies
probabilites d'issue du match (voir data_engine/synthetic/generator.py).

Ce test couvre bout en bout : generation -> Repository point-in-time ->
retrait de marge -> comparaison Brier au benchmark naif. Il ne remplace
pas la verification mathematique pure (tests/unit/test_overround.py),
mais valide que le pipeline complet produit bien un marche informe.
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np

from sys_foot_quant.calibration_engine.metrics import brier_score
from sys_foot_quant.common.config import SyntheticDataConfig
from sys_foot_quant.data_engine.storage.repository import DuckDBRepository
from sys_foot_quant.data_engine.storage.writer import write_dataset
from sys_foot_quant.data_engine.synthetic.generator import generate_synthetic_dataset
from sys_foot_quant.football_model.naive import NaiveModel
from sys_foot_quant.backtesting_engine.walk_forward import market_benchmark_probs

_CONFIG = SyntheticDataConfig(
    seed=99,
    n_teams=10,
    n_matches=500,
    start_date="2023-08-01T00:00:00+00:00",
    days_between_matches=1.0,
    team_attack_log_std=0.4,
    team_defense_log_std=0.4,
    market_margin=0.05,
    market_noise_concentration=40.0,
)


def test_informed_market_beats_naive_baseline_on_brier(tmp_path) -> None:
    dataset = generate_synthetic_dataset(_CONFIG)
    write_dataset(dataset, tmp_path)

    train_df = dataset.matches.merge(dataset.match_results, on="match_id")[
        ["home_team_id", "away_team_id", "home_goals", "away_goals"]
    ]
    naive = NaiveModel().fit(train_df)
    naive_probs_row = np.array(naive.predict(0, 1))

    with DuckDBRepository(tmp_path) as repo:
        matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
        results = repo.debug_get_full_table("match_results").set_index("match_id")

        market_probs = []
        outcomes = []
        for _, row in matches.iterrows():
            decision_time = row["kickoff_time"] - timedelta(hours=2)
            probs = market_benchmark_probs(repo, int(row["match_id"]), decision_time)
            if probs is None:
                continue
            result = results.loc[row["match_id"]]
            if result["home_goals"] > result["away_goals"]:
                outcome = 0
            elif result["home_goals"] == result["away_goals"]:
                outcome = 1
            else:
                outcome = 2
            market_probs.append(probs)
            outcomes.append(outcome)

    market_probs_arr = np.array(market_probs)
    outcomes_arr = np.array(outcomes)
    naive_probs_arr = np.tile(naive_probs_row, (len(outcomes_arr), 1))

    market_brier = brier_score(market_probs_arr, outcomes_arr)
    naive_brier = brier_score(naive_probs_arr, outcomes_arr)

    assert len(outcomes_arr) > 400  # le marche doit etre disponible pour l'immense majorite
    assert market_brier < naive_brier, (
        f"Le marche synthetique (brier={market_brier:.4f}) ne bat pas le naif "
        f"(brier={naive_brier:.4f}) : il n'est pas 'informe' comme attendu."
    )
