"""Integration bout en bout : walk-forward (etape 2) -> Value Engine
(etape 3), sur donnees synthetiques. Valide la MECANIQUE du pipeline
(assemblage, coherence des colonnes, CLV calculee quand disponible) - ne
constitue en aucun cas une preuve d'edge reel (voir le rapport de
validation de l'etape 3).
"""

from __future__ import annotations

from sys_foot_quant.backtesting_engine.walk_forward import ModelConfig, run_walk_forward
from sys_foot_quant.football_model.naive import NaiveModel
from sys_foot_quant.football_model.poisson import PoissonModel
from sys_foot_quant.value_engine.pipeline import build_value_log
from sys_foot_quant.value_engine.storage import read_value_log, write_value_log


def _configs():
    return [
        ModelConfig(name="naive", fit=lambda df, t: NaiveModel().fit(df)),
        ModelConfig(name="poisson_simple", fit=lambda df, t: PoissonModel(use_team_hfa=False).fit(df)),
    ]


def test_value_log_built_from_walk_forward_evaluations(repo) -> None:
    all_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
    eval_ids = all_matches["match_id"].iloc[-15:].tolist()
    kickoff_by_id = dict(zip(all_matches["match_id"], all_matches["kickoff_time"]))

    evaluations = run_walk_forward(
        repository=repo,
        eval_match_ids=eval_ids,
        decision_offset_hours=3.0,
        model_configs=_configs(),
        include_market_benchmark=True,
    )

    log = build_value_log(
        repo, evaluations, "poisson_simple", kickoff_by_id, min_edge=0.0, min_ev=0.0
    )

    assert not log.empty
    expected_cols = {
        "match_id", "decision_time", "model", "selection", "model_prob",
        "market_fair_prob", "odds_taken", "edge", "ev", "passes_thresholds",
        "selection_won", "clv_pct",
    }
    assert set(log.columns) == expected_cols
    assert (log["model"] == "poisson_simple").all()
    assert log["selection"].isin(["home", "draw", "away"]).all()
    # Exactement une selection gagnante par match (le resultat reel).
    won_counts = log.groupby("match_id")["selection_won"].sum()
    assert (won_counts == 1).all()
    # CLV calculee pour l'immense majorite des lignes (cloture posterieure
    # au decision_time, snapshot toujours disponible a kickoff_time dans
    # ce jeu de donnees).
    assert log["clv_pct"].notna().mean() > 0.9


def test_value_log_round_trips_through_storage(repo, tmp_path) -> None:
    all_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
    eval_ids = all_matches["match_id"].iloc[-5:].tolist()
    kickoff_by_id = dict(zip(all_matches["match_id"], all_matches["kickoff_time"]))

    evaluations = run_walk_forward(
        repository=repo,
        eval_match_ids=eval_ids,
        decision_offset_hours=3.0,
        model_configs=_configs(),
        include_market_benchmark=True,
    )
    log = build_value_log(
        repo, evaluations, "poisson_simple", kickoff_by_id, min_edge=0.02, min_ev=0.02
    )

    path = write_value_log(log, tmp_path / "value_log.parquet")
    reloaded = read_value_log(path)
    assert len(reloaded) == len(log)
    assert set(reloaded.columns) == set(log.columns)


def test_value_log_never_flags_ev_only_candidates_as_passing(repo) -> None:
    all_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
    eval_ids = all_matches["match_id"].iloc[-15:].tolist()
    kickoff_by_id = dict(zip(all_matches["match_id"], all_matches["kickoff_time"]))

    evaluations = run_walk_forward(
        repository=repo,
        eval_match_ids=eval_ids,
        decision_offset_hours=3.0,
        model_configs=_configs(),
        include_market_benchmark=True,
    )
    # Seuil d'edge strictement positif : une EV positive seule (edge<=seuil)
    # ne doit jamais suffire.
    log = build_value_log(
        repo, evaluations, "poisson_simple", kickoff_by_id, min_edge=0.05, min_ev=0.0
    )
    passing = log[log["passes_thresholds"]]
    assert (passing["edge"] > 0.05).all()
    assert (passing["ev"] > 0.0).all()
