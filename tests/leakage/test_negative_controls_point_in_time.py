"""Verifie que les sous-groupes E1/E7 (controles negatifs, etape 5) sont
construits strictement point-in-time : aucun match ou resultat avec
``knowledge_time > decision_time`` ne doit influencer
``prior_kickoffs_for_team``/``prior_results_for_team``, et aucun match
posterieur ou egal a ``this_kickoff`` ne doit y apparaitre non plus.
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from sys_foot_quant.football_model.negative_controls import (
    prior_kickoffs_for_team,
    prior_results_for_team,
)


@given(team_id=st.integers(min_value=0, max_value=5))
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_prior_kickoffs_never_includes_matches_at_or_after_this_kickoff(repo, team_id: int) -> None:
    all_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
    if len(all_matches) < 3:
        return
    pivot = all_matches.iloc[len(all_matches) // 2]
    this_kickoff = pivot["kickoff_time"]
    decision_time = this_kickoff  # borne large volontaire : le test porte sur this_kickoff, pas decision_time

    prior = prior_kickoffs_for_team(repo, team_id, decision_time, this_kickoff)
    for k in prior:
        assert k < this_kickoff


@given(team_id=st.integers(min_value=0, max_value=5))
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_prior_kickoffs_never_includes_matches_unknown_at_decision_time(repo, team_id: int) -> None:
    all_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
    if len(all_matches) < 3:
        return
    this_kickoff = all_matches.iloc[-1]["kickoff_time"]
    # decision_time tres tot : avant l'annonce de la plupart des fixtures.
    decision_time = all_matches.iloc[0]["knowledge_time"]

    prior = prior_kickoffs_for_team(repo, team_id, decision_time, this_kickoff)
    visible_at_decision = repo.get_as_of("matches", decision_time)
    visible_kickoffs = set(visible_at_decision["kickoff_time"])
    for k in prior:
        assert k in visible_kickoffs


@given(team_id=st.integers(min_value=0, max_value=5))
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_prior_results_never_includes_results_unknown_at_decision_time(repo, team_id: int) -> None:
    all_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
    if len(all_matches) < 3:
        return
    this_kickoff = all_matches.iloc[-1]["kickoff_time"]
    mid_index = len(all_matches) // 2
    decision_time = all_matches.iloc[mid_index]["kickoff_time"]

    prior_results = prior_results_for_team(repo, team_id, decision_time, this_kickoff)

    results_asof = repo.get_as_of("match_results", decision_time)
    matches_asof = repo.get_as_of("matches", decision_time)
    merged = matches_asof.merge(results_asof, on="match_id", how="inner")
    known_kickoffs = set(merged["kickoff_time"])

    for kickoff, _won in prior_results:
        assert kickoff < this_kickoff
        assert kickoff in known_kickoffs


def test_prior_results_matches_manual_reference_computation(repo) -> None:
    all_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
    all_results = repo.debug_get_full_table("match_results")
    team_id = int(all_matches.iloc[0]["home_team_id"])
    this_kickoff = all_matches.iloc[-1]["kickoff_time"]
    decision_time = this_kickoff

    prior_results = prior_results_for_team(repo, team_id, decision_time, this_kickoff)

    merged = all_matches.merge(all_results, on="match_id", how="inner")
    merged = merged[merged["kickoff_time"] < this_kickoff]
    expected = []
    for _, row in merged[merged["home_team_id"] == team_id].iterrows():
        expected.append((row["kickoff_time"], bool(row["home_goals"] > row["away_goals"])))
    for _, row in merged[merged["away_team_id"] == team_id].iterrows():
        expected.append((row["kickoff_time"], bool(row["away_goals"] > row["home_goals"])))

    assert sorted(prior_results) == sorted(expected)
