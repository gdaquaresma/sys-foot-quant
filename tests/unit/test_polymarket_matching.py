from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sys_foot_quant.polymarket import matching, reason_codes
from sys_foot_quant.polymarket.matching import FootballDataMatchCandidate, match_market_to_football_data, normalize_team_name
from sys_foot_quant.polymarket.schemas import Market

_KICKOFF = datetime(2025, 1, 8, 20, 0, tzinfo=timezone.utc)


def test_normalize_team_name_strips_accents_case_and_punctuation() -> None:
    assert normalize_team_name("Athlético-Madrid") == normalize_team_name("athletico madrid")


def test_canonical_aliases_table_is_empty_until_real_data_is_observed() -> None:
    """Etape 6 : aucune entree ne doit exister tant qu'aucun nom
    d'equipe Polymarket reel n'a ete verifie individuellement (meme
    exigence que team_mapping.py/elo_team_mapping.py en Phase K)."""
    assert matching.CANONICAL_TEAM_ALIASES == {}


def test_market_without_teams_is_unmatched(monkeypatch) -> None:
    m = Market(market_id="pm1", source="polymarket_gamma_api", league="synthetic_league")
    result = match_market_to_football_data(m, candidates=[])
    assert result.match_id is None
    assert result.reason_code == reason_codes.POLYMARKET_MATCH_UNMATCHED


def test_market_with_teams_absent_from_mapping_is_unmatched(monkeypatch) -> None:
    monkeypatch.setattr(matching, "CANONICAL_TEAM_ALIASES", {})
    m = Market(market_id="pm1", source="polymarket_gamma_api", league="synthetic_league", home_team="Team A", away_team="Team B")
    result = match_market_to_football_data(m, candidates=[])
    assert result.reason_code == reason_codes.POLYMARKET_MATCH_UNMATCHED


def test_unique_match_resolves_via_canonical_mapping(monkeypatch) -> None:
    monkeypatch.setattr(
        matching,
        "CANONICAL_TEAM_ALIASES",
        {"synthetic_league": {"Team A": "Team A FC", "Team B": "Team B United"}},
    )
    m = Market(
        market_id="pm1", source="polymarket_gamma_api", league="synthetic_league",
        home_team="Team A", away_team="Team B", start_time=_KICKOFF,
    )
    candidate = FootballDataMatchCandidate(
        match_id="fd_1", competition="synthetic_league", season="2025/26",
        kickoff_utc=_KICKOFF, home_team="Team A FC", away_team="Team B United",
    )
    result = match_market_to_football_data(m, candidates=[candidate])
    assert result.match_id == "fd_1"
    assert result.reason_code is None


def test_no_candidate_within_date_tolerance_is_unmatched(monkeypatch) -> None:
    monkeypatch.setattr(
        matching, "CANONICAL_TEAM_ALIASES", {"synthetic_league": {"Team A": "Team A FC", "Team B": "Team B United"}}
    )
    m = Market(
        market_id="pm1", source="polymarket_gamma_api", league="synthetic_league",
        home_team="Team A", away_team="Team B", start_time=_KICKOFF,
    )
    far_candidate = FootballDataMatchCandidate(
        match_id="fd_1", competition="synthetic_league", season="2025/26",
        kickoff_utc=_KICKOFF + timedelta(days=30), home_team="Team A FC", away_team="Team B United",
    )
    result = match_market_to_football_data(m, candidates=[far_candidate])
    assert result.reason_code == reason_codes.POLYMARKET_MATCH_UNMATCHED


def test_multiple_matching_candidates_is_ambiguous_never_forced(monkeypatch) -> None:
    monkeypatch.setattr(
        matching, "CANONICAL_TEAM_ALIASES", {"synthetic_league": {"Team A": "Team A FC", "Team B": "Team B United"}}
    )
    m = Market(
        market_id="pm1", source="polymarket_gamma_api", league="synthetic_league",
        home_team="Team A", away_team="Team B", start_time=_KICKOFF,
    )
    candidates = [
        FootballDataMatchCandidate(
            match_id="fd_1", competition="synthetic_league", season="2025/26",
            kickoff_utc=_KICKOFF, home_team="Team A FC", away_team="Team B United",
        ),
        FootballDataMatchCandidate(
            match_id="fd_2", competition="synthetic_league", season="2025/26",
            kickoff_utc=_KICKOFF + timedelta(hours=1), home_team="Team A FC", away_team="Team B United",
        ),
    ]
    result = match_market_to_football_data(m, candidates=candidates)
    assert result.match_id is None
    assert result.reason_code == reason_codes.POLYMARKET_MATCH_AMBIGUOUS
    assert set(result.candidates) == {"fd_1", "fd_2"}
