"""Verifie que l'orchestrateur de walk-forward (etape 2) respecte la
garantie point-in-time deja etablie a l'etape 1 : aucun match utilise pour
entrainer un modele a l'instant de decision T ne doit avoir kickoff_time
>= T, et le match evalue lui-meme ne doit jamais apparaitre dans son
propre ensemble d'entrainement.
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from sys_foot_quant.backtesting_engine.walk_forward import ModelConfig, run_walk_forward
from sys_foot_quant.football_model.bayesian_sequential import BayesianSequentialModel
from sys_foot_quant.football_model.naive import NaiveModel
from sys_foot_quant.football_model.poisson import PoissonModel


def _configs():
    return [
        ModelConfig(name="naive", fit=lambda df, t: NaiveModel().fit(df)),
        ModelConfig(name="poisson", fit=lambda df, t: PoissonModel().fit(df)),
        ModelConfig(name="bayesian_seq", fit=lambda df, t: BayesianSequentialModel().fit(df, t)),
    ]


@given(decision_offset_hours=st.floats(min_value=0.0, max_value=48.0))
@settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_walk_forward_never_trains_on_matches_at_or_after_decision_time(
    repo, decision_offset_hours: float
) -> None:
    all_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
    eval_ids = all_matches["match_id"].iloc[-5:].tolist()

    evaluations = run_walk_forward(
        repository=repo,
        eval_match_ids=eval_ids,
        decision_offset_hours=decision_offset_hours,
        model_configs=_configs(),
        include_market_benchmark=False,
    )

    kickoff_by_id = all_matches.set_index("match_id")["kickoff_time"]

    for ev in evaluations:
        # Le match evalue lui-meme ne doit jamais fournir son propre resultat.
        assert ev.match_id not in _training_match_ids_used(repo, ev.decision_time, ev.match_id)
        # L'instant de decision doit rester strictement avant le coup d'envoi
        # du match evalue (sinon la definition meme de "decision pre-match"
        # est violee).
        assert ev.decision_time <= kickoff_by_id.loc[ev.match_id]


def _training_match_ids_used(repo, decision_time, excluded_match_id):
    matches_asof = repo.get_as_of("matches", decision_time)
    results_asof = repo.get_as_of("match_results", decision_time)
    merged = matches_asof.merge(results_asof, on="match_id", how="inner")
    return set(merged["match_id"]) - {excluded_match_id}


def test_walk_forward_predictions_never_use_future_kickoffs(repo) -> None:
    all_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
    eval_ids = all_matches["match_id"].iloc[-8:].tolist()

    evaluations = run_walk_forward(
        repository=repo,
        eval_match_ids=eval_ids,
        decision_offset_hours=2.0,
        model_configs=_configs(),
        include_market_benchmark=False,
    )

    kickoff_by_id = all_matches.set_index("match_id")["kickoff_time"]

    for ev in evaluations:
        matches_asof = repo.get_as_of("matches", ev.decision_time)
        results_asof = repo.get_as_of("match_results", ev.decision_time)
        merged = matches_asof.merge(results_asof, on="match_id", how="inner")
        for mid in merged["match_id"]:
            if mid == ev.match_id:
                continue
            assert kickoff_by_id.loc[mid] < ev.decision_time


def test_walk_forward_produces_a_prediction_per_configured_model(repo) -> None:
    all_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
    eval_ids = all_matches["match_id"].iloc[-3:].tolist()

    evaluations = run_walk_forward(
        repository=repo,
        eval_match_ids=eval_ids,
        decision_offset_hours=1.0,
        model_configs=_configs(),
        include_market_benchmark=True,
    )

    for ev in evaluations:
        assert set(ev.predictions.keys()) == {"naive", "poisson", "bayesian_seq", "market_no_vig"}
        assert ev.outcome in (0, 1, 2)
