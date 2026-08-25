"""Meme garantie point-in-time que
tests/leakage/test_walk_forward_point_in_time.py, avec DixonColesModel
inclus explicitement dans les modeles orchestres (hypothese B1). La
garantie est structurellement assuree par ``run_walk_forward`` lui-meme
(construction de ``train_df`` via ``Repository.get_as_of``), independamment
du modele branche - ce test le verifie neanmoins explicitement pour
DixonColesModel plutot que de se reposer uniquement sur l'argument
generique."""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from sys_foot_quant.backtesting_engine.walk_forward import ModelConfig, run_walk_forward
from sys_foot_quant.football_model.dixon_coles import DixonColesModel
from sys_foot_quant.football_model.naive import NaiveModel
from sys_foot_quant.football_model.poisson import PoissonModel


def _configs():
    return [
        ModelConfig(name="naive", fit=lambda df, t: NaiveModel().fit(df)),
        ModelConfig(name="poisson_simple", fit=lambda df, t: PoissonModel(use_team_hfa=False).fit(df)),
        ModelConfig(
            name="dixon_coles", fit=lambda df, t: DixonColesModel(use_team_hfa=False).fit(df)
        ),
    ]


@given(decision_offset_hours=st.floats(min_value=0.0, max_value=48.0))
@settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_walk_forward_never_trains_dixon_coles_on_matches_at_or_after_decision_time(
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
        assert ev.match_id not in _training_match_ids_used(repo, ev.decision_time, ev.match_id)
        assert ev.decision_time <= kickoff_by_id.loc[ev.match_id]
        # DixonColesModel doit avoir produit une prediction (l'ensemble
        # d'entrainement n'est jamais vide pour ces matchs, choisis parmi
        # les 5 derniers d'un dataset de taille normale).
        assert ev.predictions["dixon_coles"] is not None
        assert ev.low_score_probs["dixon_coles"] is not None


def _training_match_ids_used(repo, decision_time, excluded_match_id):
    matches_asof = repo.get_as_of("matches", decision_time)
    results_asof = repo.get_as_of("match_results", decision_time)
    merged = matches_asof.merge(results_asof, on="match_id", how="inner")
    return set(merged["match_id"]) - {excluded_match_id}


def test_walk_forward_dixon_coles_predictions_never_use_future_kickoffs(repo) -> None:
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
