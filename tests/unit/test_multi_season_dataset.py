from __future__ import annotations

from datetime import datetime

import pytest

from sys_foot_quant.data_engine.market_odds.multi_season_dataset import (
    DuplicateMatchIdError,
    build_real_match_records_multi_season,
)


def _raw(match_id: str, dt: str, home_id: str = "10", away_id: str = "20") -> dict:
    return {
        "id": match_id,
        "isResult": True,
        "datetime": dt,
        "h": {"id": home_id, "title": "Brest"},
        "a": {"id": away_id, "title": "Paris SG"},
        "goals": {"h": "1", "a": "2"},
        "xG": {"h": "1.1", "a": "1.9"},
    }


def test_concatenates_and_sorts_chronologically_across_sources() -> None:
    season_a = [_raw("3", "2024-09-01 20:00:00"), _raw("1", "2024-08-01 20:00:00")]
    season_b = [_raw("2", "2024-08-15 20:00:00")]
    records = build_real_match_records_multi_season([(season_a, "ligue1"), (season_b, "ligue1")])
    assert [r.match_id for r in records] == ["1", "2", "3"]
    assert all(records[i].kickoff_utc <= records[i + 1].kickoff_utc for i in range(len(records) - 1))


def test_preserves_all_fields_from_build_real_match_records() -> None:
    records = build_real_match_records_multi_season([([_raw("1", "2024-08-01 20:00:00")], "ligue1")])
    r = records[0]
    assert r.league == "ligue1"
    assert r.home_team_id == 10 and r.away_team_id == 20
    assert r.home_goals == 1 and r.away_goals == 2
    assert r.home_xg == pytest.approx(1.1) and r.away_xg == pytest.approx(1.9)
    assert r.kickoff_utc == datetime(2024, 8, 1, 20, 0, 0)


def test_duplicate_match_id_across_sources_raises() -> None:
    season_a = [_raw("1", "2024-08-01 20:00:00")]
    season_b = [_raw("1", "2024-08-01 20:00:00")]
    with pytest.raises(DuplicateMatchIdError):
        build_real_match_records_multi_season([(season_a, "ligue1"), (season_b, "ligue1")])


def test_duplicate_match_id_within_same_source_raises() -> None:
    season_a = [_raw("1", "2024-08-01 20:00:00"), _raw("1", "2024-09-01 20:00:00")]
    with pytest.raises(DuplicateMatchIdError):
        build_real_match_records_multi_season([(season_a, "ligue1")])


def test_empty_sources_returns_empty_list() -> None:
    assert build_real_match_records_multi_season([]) == []


def test_unplayed_matches_are_still_ignored_like_build_real_match_records() -> None:
    raw = _raw("1", "2024-08-01 20:00:00")
    raw["isResult"] = False
    records = build_real_match_records_multi_season([([raw], "ligue1")])
    assert records == []


def test_three_sources_concatenate_in_kickoff_order_regardless_of_input_order() -> None:
    season_2025_26 = [_raw("20", "2025-08-15 20:00:00")]
    season_2024_25 = [_raw("10", "2024-08-15 20:00:00")]
    current_season = [_raw("30", "2026-08-15 20:00:00")]
    records = build_real_match_records_multi_season(
        [(current_season, "ligue1"), (season_2024_25, "ligue1"), (season_2025_26, "ligue1")]
    )
    assert [r.match_id for r in records] == ["10", "20", "30"]
