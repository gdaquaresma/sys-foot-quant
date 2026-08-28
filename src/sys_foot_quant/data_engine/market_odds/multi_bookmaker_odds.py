"""Cotes multi-bookmakers point-in-time (E9, phase economique -
docs/decisions/0006-football-data-point-in-time.md, section extension).

Reutilise EXACTEMENT le meme mecanisme de point-in-time et d'appariement
que ``economic_dataset.py``/``over_under_odds.py`` (deja valide pour le
1X2 en E1 puis pour l'Over/Under 2.5 en E5) : ``matching.build_understat_keys``/
``match_league_season`` (INCHANGES), ``time_resolution.conservative_knowledge_time_utc``
(INCHANGE), ``DECISION_OFFSET_HOURS`` (reutilise depuis ``economic_dataset.py``,
pas redefini). AUCUNE nouvelle hypothese temporelle.

Different d'``over_under_odds.py`` par la FORME de la sortie uniquement :
au lieu d'exposer un seul bookmaker par marche, chaque enregistrement
porte une representation generique ``bookmaker -> marche -> selection ->
cote``, couvrant a la fois le 1X2 (B365/BW/PS, cf.
``football_data_loader.BOOKMAKERS_1X2``) et l'Over/Under 2.5 (B365
uniquement - aucune colonne BW/PS Over/Under n'existe dans les fichiers
sources, perimetre volontairement limite a ce qui existe reellement).

Un match reste exploitable des lors que B365 (le seul bookmaker complet a
100%) est disponible sur au moins un des deux marches - un bookmaker
secondaire (BW, PS) absent ou partiel sur un match donne n'exclut jamais
le match, il est simplement absent de son dictionnaire ``bookmaker ->
cote`` (jamais invente ni impute)."""

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

MARKET_1X2 = "1x2"
MARKET_OVER_UNDER_25 = "over_under_2.5"


@dataclass(frozen=True)
class MultiBookmakerMatchRecord:
    match_id: str
    league: str
    season: str
    kickoff_utc: datetime
    decision_time_utc: datetime
    knowledge_time_utc: datetime
    timestamp_status: str
    # selection -> {bookmaker: cote} ; un bookmaker absent d'une selection
    # n'apparait simplement pas (jamais invente).
    odds_1x2: dict[str, dict[str, float]]
    odds_over_under_2_5: dict[str, dict[str, float]]

    def bookmakers_1x2(self) -> set[str]:
        return {bk for by_bk in self.odds_1x2.values() for bk in by_bk}

    def bookmakers_over_under_2_5(self) -> set[str]:
        return {bk for by_bk in self.odds_over_under_2_5.values() for bk in by_bk}


@dataclass(frozen=True)
class MultiBookmakerReport:
    league: str
    season: str
    n_understat: int
    n_football_data: int
    n_matched: int
    n_unmatched_understat: int
    n_unmatched_football_data: int
    n_duplicate_keys: int
    n_excluded_ambiguous_weekday: int
    n_excluded_incomplete_b365: int
    n_excluded_pit_violation: int
    n_exploitable: int
    records: tuple[MultiBookmakerMatchRecord, ...] = field(default_factory=tuple)


def _odds_1x2_snapshot(fd: FootballDataMatchRecord) -> dict[str, dict[str, float]]:
    """selection ("H"/"D"/"A") -> {bookmaker: cote}, reutilise
    ``odds_1x2_by_bookmaker`` (INCHANGE) puis transpose bookmaker->selection
    en selection->bookmaker (forme demandee par le protocole E9)."""
    by_bookmaker = fd.odds_1x2_by_bookmaker()
    out: dict[str, dict[str, float]] = {"H": {}, "D": {}, "A": {}}
    for bookmaker, prices in by_bookmaker.items():
        for selection, odds in prices.items():
            out[selection][bookmaker] = odds
    return out


def _odds_over_under_snapshot(fd: FootballDataMatchRecord) -> dict[str, dict[str, float]]:
    """B365 uniquement - aucune colonne O/U BW/PS dans les fichiers
    sources (verifie, pas artificiellement ajoute)."""
    out: dict[str, dict[str, float]] = {"Over": {}, "Under": {}}
    if fd.has_complete_over_under_2_5_odds:
        out["Over"]["B365"] = fd.b365_over_2_5
        out["Under"]["B365"] = fd.b365_under_2_5
    return out


def build_multi_bookmaker_dataset(
    league: str,
    season: str,
    understat_raw: list[dict],
    football_data_records: list[FootballDataMatchRecord],
) -> MultiBookmakerReport:
    """Construit les cotes multi-bookmakers exploitables (appariees,
    point-in-time valides) pour UN championnat et UNE saison. Un match est
    exclu s'il n'a pas B365 complet sur le 1X2 (seul bookmaker garanti a
    100% - condition d'exploitabilite identique a ``economic_dataset.py``/
    ``over_under_odds.py``) ; BW/PS et l'Over/Under 2.5 sont ajoutes des
    qu'ils sont disponibles, sans jamais conditionner l'inclusion du
    match. Tout match exclu est comptabilise explicitement."""
    understat_keys = build_understat_keys(understat_raw, league, season)
    matching_report = match_league_season(understat_keys, football_data_records, league, season)

    n_excluded_ambiguous_weekday = 0
    n_excluded_incomplete_b365 = 0
    n_excluded_pit_violation = 0
    records: list[MultiBookmakerMatchRecord] = []
    for m in matching_report.matched:
        if not m.football_data.has_complete_odds:
            n_excluded_incomplete_b365 += 1
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

        records.append(
            MultiBookmakerMatchRecord(
                match_id=m.understat.match_id,
                league=league,
                season=season,
                kickoff_utc=m.understat.kickoff_utc,
                decision_time_utc=decision_time,
                knowledge_time_utc=knowledge_time,
                timestamp_status=TIMESTAMP_STATUS_HYPOTHETICAL,
                odds_1x2=_odds_1x2_snapshot(m.football_data),
                odds_over_under_2_5=_odds_over_under_snapshot(m.football_data),
            )
        )

    return MultiBookmakerReport(
        league=league,
        season=season,
        n_understat=matching_report.n_understat,
        n_football_data=matching_report.n_football_data,
        n_matched=matching_report.n_matched,
        n_unmatched_understat=matching_report.n_unmatched_understat,
        n_unmatched_football_data=matching_report.n_unmatched_football_data,
        n_duplicate_keys=matching_report.n_duplicate_keys_understat + matching_report.n_duplicate_keys_football_data,
        n_excluded_ambiguous_weekday=n_excluded_ambiguous_weekday,
        n_excluded_incomplete_b365=n_excluded_incomplete_b365,
        n_excluded_pit_violation=n_excluded_pit_violation,
        n_exploitable=len(records),
        records=tuple(records),
    )
