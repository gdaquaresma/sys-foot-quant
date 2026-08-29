"""Betfair Exchange point-in-time (Phase G -
docs/bfe_incremental_information_experiment.md).

Reutilise EXACTEMENT le meme mecanisme de point-in-time et d'appariement
que ``over_under_odds.py``/``multi_bookmaker_odds.py`` (deja valide en
E5/E9) : ``matching.build_understat_keys``/``match_league_season``
(INCHANGES), ``time_resolution.conservative_knowledge_time_utc``
(INCHANGE), ``DECISION_OFFSET_HOURS`` (reutilise depuis
``economic_dataset.py``, pas redefini). AUCUNE nouvelle hypothese
temporelle - les cotes B365 et Betfair Exchange (``BFE*``) proviennent de
la MEME ligne de fichier source (meme moment de collecte suppose), donc
la meme regle de connaissance conservatrice s'applique identiquement.

Module DELIBEREMENT SEPARE de ``multi_bookmaker_odds.py`` (qui reste
INCHANGE) plutot que de l'etendre : ``BFE`` est volontairement ISOLE de
``FootballDataMatchRecord.odds_1x2_by_bookmaker``/
``over_under_2_5_by_bookmaker``/``BOOKMAKERS_1X2`` (deja utilises par des
scripts GELES E9/E13 - voir ``football_data_loader.py``), donc ce module
lit BFE via les methodes DEDIEES ``bfe_odds_1x2()``/
``bfe_over_under_2_5()`` plutot que par la couche generique.

Un match est exploitable des lors que B365 est complet sur le marche
considere (1X2 ou Over/Under 2.5) - BFE absent ou partiel sur un match
donne (BFE est absent sur ~5-8% des matchs 2025/26, voir
``football_data_loader.py``) n'exclut JAMAIS le match, il est simplement
absent du snapshot BFE (jamais invente ni impute) - meme discipline que
BW/PS/WH/LB (E9/E13)."""

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
class BetfairExchangeMatchRecord:
    match_id: str
    league: str
    season: str
    kickoff_utc: datetime
    decision_time_utc: datetime
    knowledge_time_utc: datetime
    timestamp_status: str
    home_goals: int
    away_goals: int
    total_goals: int
    # B365 : baseline deja validee (E1-E16), TOUJOURS complet (condition
    # d'exploitabilite du match, voir build_betfair_exchange_dataset).
    b365_1x2: dict[str, float]
    b365_over_under_2_5: dict[str, float]
    # BFE : absent (``None``) si incomplet sur ce match - jamais invente.
    bfe_1x2: dict[str, float] | None
    bfe_over_under_2_5: dict[str, float] | None


@dataclass(frozen=True)
class BetfairExchangeReport:
    league: str
    season: str
    n_understat: int
    n_football_data: int
    n_matched: int
    n_unmatched_understat: int
    n_unmatched_football_data: int
    n_excluded_ambiguous_weekday: int
    n_excluded_incomplete_b365_1x2: int
    n_excluded_pit_violation: int
    n_exploitable: int
    n_with_bfe_1x2: int
    n_with_bfe_over_under_2_5: int
    records: tuple[BetfairExchangeMatchRecord, ...] = field(default_factory=tuple)


def build_betfair_exchange_dataset(
    league: str,
    season: str,
    understat_raw: list[dict],
    football_data_records: list[FootballDataMatchRecord],
) -> BetfairExchangeReport:
    """Construit, pour UN championnat et UNE saison, les enregistrements
    B365 + Betfair Exchange exploitables (apparies, point-in-time
    valides). Un match est exclu s'il n'a pas B365 1X2 complet (meme
    condition d'exploitabilite que ``multi_bookmaker_odds.py``) ; BFE est
    ajoute des qu'il est disponible sur chaque marche, sans jamais
    conditionner l'inclusion du match. Tout match exclu est comptabilise
    explicitement."""
    understat_keys = build_understat_keys(understat_raw, league, season)
    matching_report = match_league_season(understat_keys, football_data_records, league, season)

    n_excluded_ambiguous_weekday = 0
    n_excluded_incomplete_b365_1x2 = 0
    n_excluded_pit_violation = 0
    n_with_bfe_1x2 = 0
    n_with_bfe_over_under_2_5 = 0
    records: list[BetfairExchangeMatchRecord] = []
    for m in matching_report.matched:
        b365_1x2 = m.football_data.odds_1x2_by_bookmaker().get("B365")
        if b365_1x2 is None:
            n_excluded_incomplete_b365_1x2 += 1
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

        b365_ou = m.football_data.over_under_2_5_by_bookmaker().get("B365", {})
        bfe_1x2 = m.football_data.bfe_odds_1x2()
        bfe_ou = m.football_data.bfe_over_under_2_5()
        if bfe_1x2 is not None:
            n_with_bfe_1x2 += 1
        if bfe_ou is not None:
            n_with_bfe_over_under_2_5 += 1

        records.append(
            BetfairExchangeMatchRecord(
                match_id=m.understat.match_id,
                league=league,
                season=season,
                kickoff_utc=m.understat.kickoff_utc,
                decision_time_utc=decision_time,
                knowledge_time_utc=knowledge_time,
                timestamp_status=TIMESTAMP_STATUS_HYPOTHETICAL,
                home_goals=m.football_data.home_goals,
                away_goals=m.football_data.away_goals,
                total_goals=m.football_data.home_goals + m.football_data.away_goals,
                b365_1x2=b365_1x2,
                b365_over_under_2_5=b365_ou,
                bfe_1x2=bfe_1x2,
                bfe_over_under_2_5=bfe_ou,
            )
        )

    return BetfairExchangeReport(
        league=league,
        season=season,
        n_understat=matching_report.n_understat,
        n_football_data=matching_report.n_football_data,
        n_matched=matching_report.n_matched,
        n_unmatched_understat=matching_report.n_unmatched_understat,
        n_unmatched_football_data=matching_report.n_unmatched_football_data,
        n_excluded_ambiguous_weekday=n_excluded_ambiguous_weekday,
        n_excluded_incomplete_b365_1x2=n_excluded_incomplete_b365_1x2,
        n_excluded_pit_violation=n_excluded_pit_violation,
        n_exploitable=len(records),
        n_with_bfe_1x2=n_with_bfe_1x2,
        n_with_bfe_over_under_2_5=n_with_bfe_over_under_2_5,
        records=tuple(records),
    )
