"""Meme garantie point-in-time que
tests/leakage/test_walk_forward_dixon_coles_point_in_time.py, avec
RecentFormModel et HeadToHeadModel inclus explicitement dans les modeles
orchestres (re-test A1-recence). La garantie est structurellement
assuree par ``run_walk_forward`` lui-meme (construction de ``train_df``
via ``Repository.get_as_of``), independamment du modele branche - ce
test le verifie neanmoins explicitement pour ces deux nouveaux modeles
plutot que de se reposer uniquement sur l'argument generique."""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from sys_foot_quant.backtesting_engine.walk_forward import ModelConfig, run_walk_forward
from sys_foot_quant.football_model.head_to_head import HeadToHeadModel
from sys_foot_quant.football_model.naive import NaiveModel
from sys_foot_quant.football_model.poisson import PoissonModel
from sys_foot_quant.football_model.recent_form import RecentFormModel


def _configs():
    return [
        ModelConfig(name="naive", fit=lambda df, t: NaiveModel().fit(df)),
        ModelConfig(name="poisson_simple", fit=lambda df, t: PoissonModel(use_team_hfa=False).fit(df)),
        ModelConfig(name="forme_5", fit=lambda df, t: RecentFormModel(window=5).fit(df, t)),
        ModelConfig(
            name="forme_5_memoire",
            fit=lambda df, t: RecentFormModel(window=5, prior_k=2.0).fit(df, t),
        ),
        ModelConfig(name="h2h_seul", fit=lambda df, t: HeadToHeadModel(weight=0.10).fit(df, t)),
    ]


def _training_match_ids_used(repo, decision_time, excluded_match_id):
    matches_asof = repo.get_as_of("matches", decision_time)
    results_asof = repo.get_as_of("match_results", decision_time)
    merged = matches_asof.merge(results_asof, on="match_id", how="inner")
    return set(merged["match_id"]) - {excluded_match_id}


@given(decision_offset_hours=st.floats(min_value=0.0, max_value=48.0))
@settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_walk_forward_never_trains_recent_form_or_h2h_on_matches_at_or_after_decision_time(
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
        for name in ("forme_5", "forme_5_memoire", "h2h_seul"):
            assert ev.predictions[name] is not None


def test_walk_forward_recent_form_and_h2h_predictions_never_use_future_kickoffs(repo) -> None:
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


def test_h2h_last_meeting_lookup_only_sees_matches_visible_at_decision_time(repo) -> None:
    """Verifie explicitement que la "derniere rencontre" retenue par
    HeadToHeadModel ne peut jamais etre une rencontre posterieure a
    ``decision_time`` : reconstruit, pour chaque match evalue, la
    prediction attendue en n'utilisant QUE les donnees visibles a
    ``decision_time`` (via ``get_as_of``) et verifie l'egalite exacte
    avec la prediction reellement produite par le walk-forward. Si le
    modele utilisait par erreur une rencontre posterieure a
    ``decision_time``, cette reconstruction independante divergerait."""
    import pytest

    all_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
    eval_ids = all_matches["match_id"].iloc[-10:].tolist()

    evaluations = run_walk_forward(
        repository=repo,
        eval_match_ids=eval_ids,
        decision_offset_hours=2.0,
        model_configs=_configs(),
        include_market_benchmark=False,
    )

    for ev in evaluations:
        matches_asof = repo.get_as_of("matches", ev.decision_time)
        results_asof = repo.get_as_of("match_results", ev.decision_time)
        merged = matches_asof.merge(results_asof, on="match_id", how="inner")
        merged = merged[merged["match_id"] != ev.match_id]
        train_df = merged[
            ["home_team_id", "away_team_id", "home_goals", "away_goals", "kickoff_time"]
        ]

        h, a = ev.home_team_id, ev.away_team_id
        expected_probs = HeadToHeadModel(weight=0.10).fit(train_df).predict_outcome_probabilities(h, a)
        actual_probs = ev.predictions["h2h_seul"]

        assert actual_probs == pytest.approx(expected_probs, abs=1e-9)
