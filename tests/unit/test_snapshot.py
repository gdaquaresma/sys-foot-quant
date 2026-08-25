from __future__ import annotations

from datetime import timedelta

from sys_foot_quant.market_engine.snapshot import latest_odds_as_of


def test_latest_odds_as_of_returns_none_before_any_snapshot(repo) -> None:
    full_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
    match_id = int(full_matches.iloc[0]["match_id"])
    kickoff = full_matches.iloc[0]["kickoff_time"]
    result = latest_odds_as_of(repo, match_id, kickoff - timedelta(hours=73))
    assert result is None


def test_latest_odds_as_of_returns_the_most_recent_snapshot(repo) -> None:
    full_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
    match_id = int(full_matches.iloc[0]["match_id"])
    kickoff = full_matches.iloc[0]["kickoff_time"]

    odds = latest_odds_as_of(repo, match_id, kickoff - timedelta(minutes=30))
    assert odds is not None
    assert set(odds.keys()) == {"home", "draw", "away"}
    for o in odds.values():
        assert o > 1.0


def test_latest_odds_as_of_matches_debug_full_table_latest_row(repo) -> None:
    full_odds = repo.debug_get_full_table("odds_snapshots")
    full_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
    match_id = int(full_matches.iloc[0]["match_id"])
    kickoff = full_matches.iloc[0]["kickoff_time"]

    match_odds = full_odds[full_odds["match_id"] == match_id]
    expected_latest_time = match_odds["knowledge_time"].max()
    expected = dict(
        zip(
            match_odds[match_odds["knowledge_time"] == expected_latest_time]["selection"],
            match_odds[match_odds["knowledge_time"] == expected_latest_time]["odds_value"],
        )
    )

    result = latest_odds_as_of(repo, match_id, kickoff)
    assert result == expected
