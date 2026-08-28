"""Cotes Over/Under 2.5 B365 point-in-time (E5, phase economique -
docs/decisions/0006-football-data-point-in-time.md, section extension).

Reutilise EXACTEMENT le meme mecanisme de point-in-time et d'appariement
que ``economic_dataset.py`` (deja valide pour le 1X2 en E1), applique ici
au marche Over/Under 2.5 : ``matching.match_league_season`` (INCHANGE),
``time_resolution.conservative_knowledge_time_utc`` (INCHANGE),
``DECISION_OFFSET_HOURS`` (reutilise depuis ``economic_dataset.py``, pas
redefini). AUCUNE nouvelle hypothese temporelle - les cotes 1X2 et
Over/Under proviennent de la meme ligne de fichier source (meme moment de
collecte suppose), donc la meme regle de connaissance conservatrice
s'applique identiquement.

Module delibrement separe d'``economic_dataset.py`` (qui reste inchange,
specifique au 1X2 et a ``poisson_simple``) plutot que de l'etendre :
``economic_dataset.py`` calcule aussi les predictions ``poisson_simple``
en interne, alors qu'E5 a besoin des probabilites CALIBREES des deux
modeles (``poisson_simple`` et ``xg_model``, deja produites par
E2/E3/stage10) - ce module se limite a la partie marche (appariement +
cotes O/U), l'assemblage avec les probabilites modele se fait dans le
script E5."""

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
class OverUnder25MatchRecord:
    match_id: str
    league: str
    season: str
    kickoff_utc: datetime
    decision_time_utc: datetime
    knowledge_time_utc: datetime
    timestamp_status: str
    b365_over_2_5: float
    b365_under_2_5: float


@dataclass(frozen=True)
class OverUnder25Report:
    league: str
    season: str
    n_understat: int
    n_football_data: int
    n_matched: int
    n_unmatched_understat: int
    n_unmatched_football_data: int
    n_duplicate_keys: int
    n_excluded_ambiguous_weekday: int
    n_excluded_incomplete_odds: int
    n_excluded_pit_violation: int
    n_exploitable: int
    records: tuple[OverUnder25MatchRecord, ...] = field(default_factory=tuple)


def build_over_under_25_dataset(
    league: str,
    season: str,
    understat_raw: list[dict],
    football_data_records: list[FootballDataMatchRecord],
) -> OverUnder25Report:
    """Construit les cotes Over/Under 2.5 exploitables (appariees,
    point-in-time valides) pour UN championnat et UNE saison. Tout match
    exclu (cote incomplete, jour ambigu, violation point-in-time) est
    comptabilise explicitement - jamais silencieusement absorbe."""
    understat_keys = build_understat_keys(understat_raw, league, season)
    matching_report = match_league_season(understat_keys, football_data_records, league, season)

    n_excluded_ambiguous_weekday = 0
    n_excluded_incomplete_odds = 0
    n_excluded_pit_violation = 0
    records: list[OverUnder25MatchRecord] = []
    for m in matching_report.matched:
        if not m.football_data.has_complete_over_under_2_5_odds:
            n_excluded_incomplete_odds += 1
            continue
        try:
            knowledge_time = conservative_knowledge_time_utc(m.understat.kickoff_utc)
        except AmbiguousCollectionWindowError:
            n_excluded_ambiguous_weekday += 1
            continue

        decision_time = m.understat.kickoff_utc - timedelta(hours=DECISION_OFFSET_HOURS)
        if not (knowledge_time <= decision_time):
            # Garde-fou explicite, verifie plutot que suppose (memes
            # deux datetimes tzinfo-aware UTC ici, comparaison directe -
            # voir economic_dataset.py pour la meme discipline).
            n_excluded_pit_violation += 1
            continue

        records.append(
            OverUnder25MatchRecord(
                match_id=m.understat.match_id,
                league=league,
                season=season,
                kickoff_utc=m.understat.kickoff_utc,
                decision_time_utc=decision_time,
                knowledge_time_utc=knowledge_time,
                timestamp_status=TIMESTAMP_STATUS_HYPOTHETICAL,
                b365_over_2_5=m.football_data.b365_over_2_5,
                b365_under_2_5=m.football_data.b365_under_2_5,
            )
        )

    return OverUnder25Report(
        league=league,
        season=season,
        n_understat=matching_report.n_understat,
        n_football_data=matching_report.n_football_data,
        n_matched=matching_report.n_matched,
        n_unmatched_understat=matching_report.n_unmatched_understat,
        n_unmatched_football_data=matching_report.n_unmatched_football_data,
        n_duplicate_keys=matching_report.n_duplicate_keys_understat + matching_report.n_duplicate_keys_football_data,
        n_excluded_ambiguous_weekday=n_excluded_ambiguous_weekday,
        n_excluded_incomplete_odds=n_excluded_incomplete_odds,
        n_excluded_pit_violation=n_excluded_pit_violation,
        n_exploitable=len(records),
        records=tuple(records),
    )
