"""Handicap asiatique point-in-time (Phase H -
docs/ah_experiment_specification.md).

Reutilise EXACTEMENT le meme mecanisme de point-in-time et d'appariement
que ``betfair_exchange_odds.py``/``over_under_odds.py`` (deja valide en
E5/E9/Phase G) : ``matching.build_understat_keys``/``match_league_season``
(INCHANGES), ``time_resolution.conservative_knowledge_time_utc``
(INCHANGE), ``DECISION_OFFSET_HOURS`` (reutilise, pas redefini). AUCUNE
nouvelle hypothese temporelle - la ligne et les prix AH proviennent de la
MEME ligne de fichier source que B365 1X2/O-U.

Module isole, JAMAIS importe par ``final_engine``. Un match est
exploitable des lors que B365 AH est complet (ligne + les deux prix) -
Pinnacle AH absent ou partiel n'exclut jamais le match, simplement absent
du snapshot correspondant (meme discipline que BW/PS/Pinnacle partout
ailleurs dans le projet)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sys_foot_quant.data_engine.market_odds.economic_dataset import DECISION_OFFSET_HOURS
from sys_foot_quant.data_engine.market_odds.football_data_loader import FootballDataMatchRecord
from sys_foot_quant.data_engine.market_odds.matching import build_understat_keys, match_league_season
from sys_foot_quant.data_engine.market_odds.time_resolution import (
    TIMESTAMP_STATUS_HYPOTHETICAL,
    AmbiguousCollectionWindowError,
    conservative_knowledge_time_utc,
)


@dataclass(frozen=True)
class AsianHandicapMatchRecord:
    match_id: str
    league: str
    season: str
    kickoff_utc: datetime
    decision_time_utc: datetime
    knowledge_time_utc: datetime
    timestamp_status: str
    home_goals: int
    away_goals: int
    # B365 : condition d'exploitabilite du match (toujours complet).
    ah_line: float
    b365_ah_home: float
    b365_ah_away: float
    # Pinnacle : absent (``None``) si incomplet sur ce match - jamais invente.
    p_ah_home: float | None
    p_ah_away: float | None


@dataclass(frozen=True)
class AsianHandicapReport:
    league: str
    season: str
    n_understat: int
    n_football_data: int
    n_matched: int
    n_unmatched_understat: int
    n_unmatched_football_data: int
    n_excluded_ambiguous_weekday: int
    n_excluded_incomplete_b365_ah: int
    n_excluded_pit_violation: int
    n_exploitable: int
    n_with_pinnacle_ah: int
    records: tuple[AsianHandicapMatchRecord, ...] = field(default_factory=tuple)


def build_asian_handicap_dataset(
    league: str,
    season: str,
    understat_raw: list[dict],
    football_data_records: list[FootballDataMatchRecord],
) -> AsianHandicapReport:
    """Construit, pour UN championnat et UNE saison, les enregistrements
    de handicap asiatique exploitables (apparies, point-in-time
    valides). Un match est exclu s'il n'a pas B365 AH complet (ligne +
    les deux prix) ; Pinnacle est ajoute des qu'il est disponible, sans
    jamais conditionner l'inclusion du match. Tout match exclu est
    comptabilise explicitement."""
    understat_keys = build_understat_keys(understat_raw, league, season)
    matching_report = match_league_season(understat_keys, football_data_records, league, season)

    n_excluded_ambiguous_weekday = 0
    n_excluded_incomplete_b365_ah = 0
    n_excluded_pit_violation = 0
    n_with_pinnacle_ah = 0
    records: list[AsianHandicapMatchRecord] = []
    for m in matching_report.matched:
        b365_ah = m.football_data.b365_asian_handicap()
        if b365_ah is None:
            n_excluded_incomplete_b365_ah += 1
            continue
        try:
            knowledge_time = conservative_knowledge_time_utc(m.understat.kickoff_utc)
        except AmbiguousCollectionWindowError:
            n_excluded_ambiguous_weekday += 1
            continue

        decision_time = m.understat.kickoff_utc - timedelta(hours=DECISION_OFFSET_HOURS)
        if not (knowledge_time <= decision_time):
            n_excluded_pit_violation += 1
            continue

        p_ah = m.football_data.p_asian_handicap()
        if p_ah is not None:
            n_with_pinnacle_ah += 1

        records.append(
            AsianHandicapMatchRecord(
                match_id=m.understat.match_id,
                league=league,
                season=season,
                kickoff_utc=m.understat.kickoff_utc,
                decision_time_utc=decision_time,
                knowledge_time_utc=knowledge_time,
                timestamp_status=TIMESTAMP_STATUS_HYPOTHETICAL,
                home_goals=m.football_data.home_goals,
                away_goals=m.football_data.away_goals,
                ah_line=b365_ah["line"],
                b365_ah_home=b365_ah["home"],
                b365_ah_away=b365_ah["away"],
                p_ah_home=(p_ah["home"] if p_ah is not None else None),
                p_ah_away=(p_ah["away"] if p_ah is not None else None),
            )
        )

    return AsianHandicapReport(
        league=league,
        season=season,
        n_understat=matching_report.n_understat,
        n_football_data=matching_report.n_football_data,
        n_matched=matching_report.n_matched,
        n_unmatched_understat=matching_report.n_unmatched_understat,
        n_unmatched_football_data=matching_report.n_unmatched_football_data,
        n_excluded_ambiguous_weekday=n_excluded_ambiguous_weekday,
        n_excluded_incomplete_b365_ah=n_excluded_incomplete_b365_ah,
        n_excluded_pit_violation=n_excluded_pit_violation,
        n_exploitable=len(records),
        n_with_pinnacle_ah=n_with_pinnacle_ah,
        records=tuple(records),
    )
