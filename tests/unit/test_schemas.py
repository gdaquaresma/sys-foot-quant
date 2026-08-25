from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from sys_foot_quant.data_engine.schemas.entities import Match, MatchResult, OddsSnapshot

KICKOFF = datetime(2024, 8, 1, 18, 0, tzinfo=timezone.utc)


def test_match_rejects_knowledge_time_after_kickoff() -> None:
    with pytest.raises(ValidationError, match="connue apres"):
        Match(
            match_id=1,
            home_team_id=1,
            away_team_id=2,
            kickoff_time=KICKOFF,
            knowledge_time=KICKOFF + timedelta(hours=1),
        )


def test_match_rejects_identical_home_and_away_team() -> None:
    with pytest.raises(ValidationError, match="differer"):
        Match(
            match_id=1,
            home_team_id=1,
            away_team_id=1,
            kickoff_time=KICKOFF,
            knowledge_time=KICKOFF - timedelta(days=1),
        )


def test_match_accepts_valid_fixture() -> None:
    match = Match(
        match_id=1,
        home_team_id=1,
        away_team_id=2,
        kickoff_time=KICKOFF,
        knowledge_time=KICKOFF - timedelta(days=14),
    )
    assert match.knowledge_time < match.kickoff_time


def test_match_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError, match="naif"):
        Match(
            match_id=1,
            home_team_id=1,
            away_team_id=2,
            kickoff_time=datetime(2024, 8, 1, 18, 0),
            knowledge_time=KICKOFF - timedelta(days=1),
        )


def test_match_result_rejects_negative_goals() -> None:
    with pytest.raises(ValidationError):
        MatchResult(match_id=1, home_goals=-1, away_goals=0, knowledge_time=KICKOFF)


def test_odds_snapshot_rejects_odds_below_one() -> None:
    with pytest.raises(ValidationError):
        OddsSnapshot(
            match_id=1,
            bookmaker="synthetic_book",
            selection="home",
            odds_value=0.9,
            knowledge_time=KICKOFF,
        )
