"""Jointure Elo pre-match, point-in-time (Phase K -
docs/elo_experiment_specification.md).

Reutilise EXACTEMENT le meme mecanisme de point-in-time et d'appariement
que ``asian_handicap_odds.py``/``betfair_exchange_odds.py`` :
``matching.build_understat_keys``/``match_league_season`` (INCHANGES),
``time_resolution.conservative_knowledge_time_utc`` (INCHANGE),
``DECISION_OFFSET_HOURS`` (reutilise, pas redefini). AUCUNE nouvelle
hypothese temporelle.

Regle de selection PIT du rating (``elo_lookup_date = decision_time.date()``,
ligne ``valid_from <= date <= valid_to`` de ``elo_ratings.elo_as_of``,
INCHANGEE) - demontree comme structurellement sure en section 2 du
protocole. Module isole, JAMAIS importe par ``final_engine``."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sys_foot_quant.data_engine.market_odds.economic_dataset import DECISION_OFFSET_HOURS
from sys_foot_quant.data_engine.market_odds.elo_ratings import AmbiguousEloWindowError, EloRatingRow, elo_as_of
from sys_foot_quant.data_engine.market_odds.elo_team_mapping import resolve_clubelo_name
from sys_foot_quant.data_engine.market_odds.football_data_loader import FootballDataMatchRecord
from sys_foot_quant.data_engine.market_odds.matching import build_understat_keys, match_league_season
from sys_foot_quant.data_engine.market_odds.time_resolution import (
    TIMESTAMP_STATUS_HYPOTHETICAL,
    AmbiguousCollectionWindowError,
    conservative_knowledge_time_utc,
)


@dataclass(frozen=True)
class EloMatchRecord:
    match_id: str
    league: str
    season: str
    kickoff_utc: datetime
    decision_time_utc: datetime
    knowledge_time_utc: datetime
    timestamp_status: str
    home_goals: int
    away_goals: int
    elo_home: float
    elo_away: float
    elo_diff: float


@dataclass(frozen=True)
class EloJoinReport:
    league: str
    season: str
    n_understat: int
    n_football_data: int
    n_matched: int
    n_unmatched_understat: int
    n_unmatched_football_data: int
    n_excluded_ambiguous_weekday: int
    n_excluded_pit_violation: int
    n_excluded_team_not_mapped: int
    n_excluded_no_elo_rating: int
    n_excluded_ambiguous_elo_window: int
    n_exploitable: int
    unmapped_teams: tuple[str, ...] = field(default_factory=tuple)
    records: tuple[EloMatchRecord, ...] = field(default_factory=tuple)


def build_elo_dataset(
    league: str,
    season: str,
    understat_raw: list[dict],
    football_data_records: list[FootballDataMatchRecord],
    elo_ratings_by_club: dict[str, list[EloRatingRow]],
    *,
    allow_unverified_mapping: bool = False,
) -> EloJoinReport:
    """Construit, pour UN championnat et UNE saison, les enregistrements
    Elo exploitables (apparies, point-in-time valides, equipe mappee,
    rating disponible a la date PIT). Toute exclusion est comptabilisee
    explicitement, jamais absorbee silencieusement (docs/elo_experiment_specification.md
    sections 3, 6, 14). ``allow_unverified_mapping`` ne doit JAMAIS etre
    ``True`` en dehors des tests sur donnees synthetiques (section 4)."""
    understat_keys = build_understat_keys(understat_raw, league, season)
    matching_report = match_league_season(understat_keys, football_data_records, league, season)

    n_excluded_ambiguous_weekday = 0
    n_excluded_pit_violation = 0
    n_excluded_team_not_mapped = 0
    n_excluded_no_elo_rating = 0
    n_excluded_ambiguous_elo_window = 0
    unmapped: set[str] = set()
    records: list[EloMatchRecord] = []

    for m in matching_report.matched:
        try:
            knowledge_time = conservative_knowledge_time_utc(m.understat.kickoff_utc)
        except AmbiguousCollectionWindowError:
            n_excluded_ambiguous_weekday += 1
            continue

        decision_time = m.understat.kickoff_utc - timedelta(hours=DECISION_OFFSET_HOURS)
        if not (knowledge_time <= decision_time):
            n_excluded_pit_violation += 1
            continue

        try:
            elo_home_name = resolve_clubelo_name(
                league, m.football_data.home_team_fd, allow_unverified=allow_unverified_mapping
            )
            elo_away_name = resolve_clubelo_name(
                league, m.football_data.away_team_fd, allow_unverified=allow_unverified_mapping
            )
        except KeyError:
            unmapped.add(m.football_data.home_team_fd)
            unmapped.add(m.football_data.away_team_fd)
            n_excluded_team_not_mapped += 1
            continue

        home_rows = elo_ratings_by_club.get(elo_home_name)
        away_rows = elo_ratings_by_club.get(elo_away_name)
        if not home_rows or not away_rows:
            n_excluded_no_elo_rating += 1
            continue

        elo_lookup_date = decision_time.date()
        try:
            elo_home = elo_as_of(home_rows, elo_lookup_date)
            elo_away = elo_as_of(away_rows, elo_lookup_date)
        except AmbiguousEloWindowError:
            n_excluded_ambiguous_elo_window += 1
            continue

        if elo_home is None or elo_away is None:
            n_excluded_no_elo_rating += 1
            continue

        records.append(
            EloMatchRecord(
                match_id=m.understat.match_id,
                league=league,
                season=season,
                kickoff_utc=m.understat.kickoff_utc,
                decision_time_utc=decision_time,
                knowledge_time_utc=knowledge_time,
                timestamp_status=TIMESTAMP_STATUS_HYPOTHETICAL,
                home_goals=m.football_data.home_goals,
                away_goals=m.football_data.away_goals,
                elo_home=elo_home,
                elo_away=elo_away,
                elo_diff=elo_home - elo_away,
            )
        )

    return EloJoinReport(
        league=league,
        season=season,
        n_understat=matching_report.n_understat,
        n_football_data=matching_report.n_football_data,
        n_matched=matching_report.n_matched,
        n_unmatched_understat=matching_report.n_unmatched_understat,
        n_unmatched_football_data=matching_report.n_unmatched_football_data,
        n_excluded_ambiguous_weekday=n_excluded_ambiguous_weekday,
        n_excluded_pit_violation=n_excluded_pit_violation,
        n_excluded_team_not_mapped=n_excluded_team_not_mapped,
        n_excluded_no_elo_rating=n_excluded_no_elo_rating,
        n_excluded_ambiguous_elo_window=n_excluded_ambiguous_elo_window,
        n_exploitable=len(records),
        unmapped_teams=tuple(sorted(unmapped)),
        records=tuple(records),
    )
