from __future__ import annotations

from datetime import timedelta

import pytest

from sys_foot_quant.data_engine.storage.repository import DuckDBRepository, UnknownEntityError


def test_generated_dataset_has_expected_volumes(synthetic_dataset, small_config) -> None:
    assert len(synthetic_dataset.teams) == small_config.n_teams
    assert len(synthetic_dataset.matches) == small_config.n_matches
    assert len(synthetic_dataset.match_results) == small_config.n_matches
    # 3 selections (home/draw/away) x 3 offsets par match
    assert len(synthetic_dataset.odds_snapshots) == small_config.n_matches * 3 * 3


def test_repository_rejects_non_point_in_time_entity(repo: DuckDBRepository) -> None:
    with pytest.raises(UnknownEntityError):
        repo.get_as_of("teams", repo.debug_get_full_table("matches")["kickoff_time"].iloc[0])


def test_result_invisible_before_confirmation_visible_after(repo: DuckDBRepository) -> None:
    full_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
    full_results = repo.debug_get_full_table("match_results")

    first_match = full_matches.iloc[0]
    match_id = int(first_match["match_id"])
    result_row = full_results.loc[full_results["match_id"] == match_id].iloc[0]
    result_known_at = result_row["knowledge_time"]

    just_before = result_known_at - timedelta(seconds=1)
    visible_before = repo.get_as_of("match_results", just_before)
    assert match_id not in set(visible_before["match_id"])

    visible_at = repo.get_as_of("match_results", result_known_at)
    assert match_id in set(visible_at["match_id"])


def test_odds_snapshots_accumulate_over_time_before_kickoff(repo: DuckDBRepository) -> None:
    # Offsets configures : cotes publiees a T-72h, T-24h et T-1h avant le
    # coup d'envoi (3 selections home/draw/away par publication).
    full_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
    match_id = int(full_matches.iloc[0]["match_id"])
    kickoff = full_matches.iloc[0]["kickoff_time"]

    before_any_snapshot = repo.get_as_of("odds_snapshots", kickoff - timedelta(hours=73))
    after_first_snapshot = repo.get_as_of("odds_snapshots", kickoff - timedelta(hours=30))
    after_second_snapshot = repo.get_as_of("odds_snapshots", kickoff - timedelta(hours=12))
    after_all_snapshots = repo.get_as_of("odds_snapshots", kickoff - timedelta(minutes=30))

    def count_for_match(df, mid_: int) -> int:
        return int((df["match_id"] == mid_).sum())

    assert count_for_match(before_any_snapshot, match_id) == 0
    assert count_for_match(after_first_snapshot, match_id) == 3  # T-72h uniquement
    assert count_for_match(after_second_snapshot, match_id) == 6  # T-72h + T-24h
    assert count_for_match(after_all_snapshots, match_id) == 9  # T-72h + T-24h + T-1h
