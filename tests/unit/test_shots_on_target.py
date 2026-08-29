from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from sys_foot_quant.data_engine.market_odds.football_data_loader import FootballDataMatchRecord
from sys_foot_quant.data_engine.market_odds.shots_on_target import (
    ShotsOnTargetMatchRecord,
    build_shots_on_target_dataset,
    historical_sot_averages,
    sot_features_for_match,
    sot_training_pool,
)


def _fd(date_str, home, away, hst, ast, league="premier_league", season="2024_25"):
    return FootballDataMatchRecord(
        league=league, season=season, source="football_data", bookmaker="B365", market="1x2",
        date_str=date_str, time_str="15:00", home_team_fd=home, away_team_fd=away,
        home_goals=1, away_goals=0, b365_home=1.5, b365_draw=4.0, b365_away=6.0,
        home_shots_on_target=hst, away_shots_on_target=ast,
    )


def _us_raw(match_id, date_str, home, away, home_id=1, away_id=2):
    return {
        "id": match_id,
        "isResult": True,
        "datetime": f"{date_str} 15:00:00",
        "h": {"id": home_id, "title": home},
        "a": {"id": away_id, "title": away},
    }


def _record(match_id, kickoff, home_team_id, away_team_id, home_sot, away_sot, league="premier_league", season="2024_25"):
    return ShotsOnTargetMatchRecord(
        match_id=match_id, league=league, season=season, kickoff_utc=kickoff,
        home_team_id=home_team_id, away_team_id=away_team_id,
        home_shots_on_target=home_sot, away_shots_on_target=away_sot,
        sot_knowledge_time=kickoff + timedelta(hours=2.0),
    )


# --------------------------------------------------------------------------
# build_shots_on_target_dataset : appariement + sot_knowledge_time
# --------------------------------------------------------------------------


def test_build_dataset_joins_understat_ids_with_football_data_sot() -> None:
    us_raw = [_us_raw("1", "2024-08-16", "Manchester United", "Fulham", home_id=41, away_id=54)]
    fd = [_fd("16/08/2024", "Man United", "Fulham", hst=6, ast=2)]
    report = build_shots_on_target_dataset("premier_league", "2024_25", us_raw, fd)
    assert report.n_matched == 1
    r = report.records[0]
    assert r.match_id == "1"
    assert r.home_team_id == 41
    assert r.away_team_id == 54
    assert r.home_shots_on_target == 6
    assert r.away_shots_on_target == 2


def test_sot_knowledge_time_is_kickoff_plus_two_hours_same_as_goals() -> None:
    """Reutilise EXACTEMENT DEFAULT_GOALS_KNOWLEDGE_DELAY_HOURS - meme
    moment de publication que le score final (meme ligne source)."""
    us_raw = [_us_raw("1", "2024-08-16", "Arsenal", "Chelsea")]
    fd = [_fd("16/08/2024", "Arsenal", "Chelsea", hst=4, ast=3)]
    report = build_shots_on_target_dataset("premier_league", "2024_25", us_raw, fd)
    r = report.records[0]
    assert r.sot_knowledge_time == r.kickoff_utc.replace(hour=17)  # 15:00 + 2h


def test_unmatched_match_is_simply_absent_never_invented() -> None:
    us_raw = [_us_raw("1", "2024-08-16", "Arsenal", "Chelsea")]
    fd = [_fd("16/08/2024", "Man United", "Fulham", hst=4, ast=3)]  # equipes differentes -> pas d'appariement
    report = build_shots_on_target_dataset("premier_league", "2024_25", us_raw, fd)
    assert report.n_matched == 0
    assert report.records == ()


# --------------------------------------------------------------------------
# sot_training_pool : filtre point-in-time pur
# --------------------------------------------------------------------------


def test_training_pool_excludes_the_match_itself() -> None:
    decision_time = datetime(2024, 9, 1, tzinfo=timezone.utc)
    r = _record("1", datetime(2024, 8, 20, tzinfo=timezone.utc), 1, 2, 5, 3)
    pool = sot_training_pool([r], decision_time, exclude_match_id="1")
    assert pool.empty


def test_training_pool_includes_strictly_prior_matches() -> None:
    decision_time = datetime(2024, 9, 1, tzinfo=timezone.utc)
    r = _record("1", datetime(2024, 8, 20, tzinfo=timezone.utc), 1, 2, 5, 3)
    pool = sot_training_pool([r], decision_time, exclude_match_id="99")
    assert len(pool) == 1
    assert pool.iloc[0]["home_sot"] == 5


def test_training_pool_excludes_matches_with_knowledge_time_after_decision_time() -> None:
    decision_time = datetime(2024, 9, 1, tzinfo=timezone.utc)
    future = _record("2", datetime(2024, 9, 5, tzinfo=timezone.utc), 1, 3, 15, 15)
    pool = sot_training_pool([future], decision_time, exclude_match_id="99")
    assert pool.empty


def test_training_pool_boundary_is_inclusive_le() -> None:
    """`sot_knowledge_time == decision_time` est INCLUS (`<=`), meme
    convention que `_goals_train_df`/`_xg_train_df`."""
    kickoff = datetime(2024, 8, 20, 13, 0, tzinfo=timezone.utc)  # knowledge = 15:00
    decision_time = datetime(2024, 8, 20, 15, 0, tzinfo=timezone.utc)
    r = _record("1", kickoff, 1, 2, 5, 3)
    pool = sot_training_pool([r], decision_time, exclude_match_id="99")
    assert len(pool) == 1


# --------------------------------------------------------------------------
# historical_sot_averages : moyenne par equipe + repli neutre (pool mean)
# --------------------------------------------------------------------------


def test_historical_averages_computed_per_team_produced_and_conceded() -> None:
    pool = pd.DataFrame(
        [
            {"home_team_id": 1, "away_team_id": 2, "home_sot": 6, "away_sot": 2},
            {"home_team_id": 2, "away_team_id": 1, "home_sot": 4, "away_sot": 8},
        ]
    )
    avg_for, avg_against, pool_mean_for, pool_mean_against = historical_sot_averages(pool)
    # equipe 1 : marque 6 (dom, match1) et 8 (ext, match2) -> moyenne 7 ; encaisse 2 et 4 -> moyenne 3
    assert avg_for[1] == pytest.approx(7.0)
    assert avg_against[1] == pytest.approx(3.0)
    # equipe 2 : marque 2 et 4 -> moyenne 3 ; encaisse 6 et 8 -> moyenne 7
    assert avg_for[2] == pytest.approx(3.0)
    assert avg_against[2] == pytest.approx(7.0)
    assert pool_mean_for == pytest.approx((6 + 2 + 4 + 8) / 4)


def test_team_absent_from_pool_falls_back_to_pool_mean_never_invented_or_excluded() -> None:
    """Repli neutre translittere de ``XGModel.fit`` : une equipe SANS
    historique dans le pool recoit la moyenne du pool, jamais une valeur
    arbitraire ni une exclusion du match."""
    pool = pd.DataFrame(
        [
            {"home_team_id": 1, "away_team_id": 2, "home_sot": 6, "away_sot": 2},
        ]
    )
    avg_for, avg_against, pool_mean_for, pool_mean_against = historical_sot_averages(pool)
    unseen_team = 999
    assert unseen_team not in avg_for
    assert avg_for.get(unseen_team, pool_mean_for) == pytest.approx(pool_mean_for)


# --------------------------------------------------------------------------
# sot_features_for_match : gate MIN_TRAIN_MATCHES + assemblage final
# --------------------------------------------------------------------------


def test_features_none_when_pool_below_min_train_matches() -> None:
    pool = pd.DataFrame([{"home_team_id": 1, "away_team_id": 2, "home_sot": 6, "away_sot": 2}])
    assert sot_features_for_match(pool, 1, 2, min_train_matches=10) is None


def test_features_computed_when_pool_meets_min_train_matches() -> None:
    rows = [{"home_team_id": (i % 4) + 1, "away_team_id": ((i + 1) % 4) + 1, "home_sot": 5, "away_sot": 3} for i in range(10)]
    pool = pd.DataFrame(rows)
    result = sot_features_for_match(pool, 1, 2, min_train_matches=10)
    assert result is not None
    sot_produced_total, sot_conceded_total, n = result
    assert n == 10
    assert sot_produced_total > 0
    assert sot_conceded_total > 0


def test_features_are_exactly_two_scalars_no_extra_variant() -> None:
    """Protocole Phase F etape 2/11 : minimal, jamais multiplie."""
    rows = [{"home_team_id": (i % 4) + 1, "away_team_id": ((i + 1) % 4) + 1, "home_sot": 5, "away_sot": 3} for i in range(10)]
    pool = pd.DataFrame(rows)
    result = sot_features_for_match(pool, 1, 2, min_train_matches=10)
    assert len(result) == 3  # (sot_produced_total, sot_conceded_total, n) - pas une quatrieme variable
