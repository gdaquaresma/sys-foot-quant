"""Consensus multi-bookmaker Max/Avg Over/Under 2.5 (Stage32,
docs/multi_bookmaker_consensus_experiment_specification.md) - AJOUT PUR,
miroir de `matching.opening_over_under_2_5_by_match_id` (INCHANGE) mais
pour Max/Avg, DELIBEREMENT dans un module separe pour ne jamais toucher
`matching.py` (deja gele, utilise par `historical_evaluation.py`/
`run_prediction` en production) ni `over_under_2_5_by_bookmaker()`/
`OVER_UNDER_25_BOOKMAKERS` (geles, E9/E13/Phase D).

Question posee : le consensus multi-bookmaker (Avg, panel plus large que
B365 seul) apporte-t-il une information PREDICTIVE INCREMENTALE sur
Over/Under 2.5, au-dela de ce que le moteur actuel possede deja ? Ce
module se limite STRICTEMENT a la construction du signal (appariement +
extraction des cotes D'OUVERTURE) - AUCUNE comparaison de modele, AUCUN
test statistique ici (voir
`scripts/run_stage32_multi_bookmaker_consensus_incremental_information.py`).

RESERVE ABSOLUE (non negociable) : seules les cotes D'OUVERTURE
(``Max>2.5``/``Avg>2.5``, via
``FootballDataMatchRecord.max_avg_over_under_2_5()``) sont lues - JAMAIS
``MaxC>2.5``/``AvgC>2.5`` (cloture, qui n'existent meme pas dans
``_ALLOWED_COLUMNS`` - voir docstring de ``football_data_loader``).
Aucun nouveau delai de connaissance n'est necessaire : les cotes
d'ouverture sont publiees bien avant ``decision_time``, exactement comme
B365 (``matching.opening_over_under_2_5_by_match_id``, INCHANGE).

Appariement Understat<->Football-Data REUTILISE SANS MODIFICATION
(``matching.build_understat_keys``/``match_league_season``, deja valide)."""

from __future__ import annotations

from dataclasses import dataclass

from sys_foot_quant.data_engine.market_odds.football_data_loader import FootballDataMatchRecord
from sys_foot_quant.data_engine.market_odds.matching import (
    MatchingReport,
    build_understat_keys,
    match_league_season,
)

AGGREGATES = ("Max", "Avg")


@dataclass(frozen=True)
class MultiBookmakerOverUnderRecord:
    match_id: str
    league: str
    season: str
    b365_over_2_5: float | None
    b365_under_2_5: float | None
    max_over_2_5: float | None
    max_under_2_5: float | None
    avg_over_2_5: float | None
    avg_under_2_5: float | None

    @property
    def has_complete_b365(self) -> bool:
        return self.b365_over_2_5 is not None and self.b365_under_2_5 is not None

    @property
    def has_complete_max(self) -> bool:
        return self.max_over_2_5 is not None and self.max_under_2_5 is not None

    @property
    def has_complete_avg(self) -> bool:
        return self.avg_over_2_5 is not None and self.avg_under_2_5 is not None


@dataclass(frozen=True)
class MultiBookmakerOverUnderReport:
    league: str
    season: str
    n_understat: int
    n_football_data: int
    n_matched: int
    n_unmatched_understat: int
    n_unmatched_football_data: int
    records: tuple[MultiBookmakerOverUnderRecord, ...]


def build_multi_bookmaker_over_under_dataset(
    league: str,
    season: str,
    understat_raw: list[dict],
    football_data_records: list[FootballDataMatchRecord],
) -> MultiBookmakerOverUnderReport:
    """Construit, pour UN championnat et UNE saison, les enregistrements
    B365/Max/Avg Over/Under 2.5 D'OUVERTURE apparies. Un match non
    apparie est simplement absent (jamais invente) ; un agregat
    incomplet sur un match apparie reste ``None`` pour cet agregat
    uniquement (jamais impute - couverture Max/Avg constatee a 100% sur
    le corpus reel, voir docstring de ``football_data_loader``, donc cette
    absence ne devrait pas survenir en pratique mais n'est jamais
    supposee impossible)."""
    understat_keys = build_understat_keys(understat_raw, league, season)
    matching_report: MatchingReport = match_league_season(understat_keys, football_data_records, league, season)

    records: list[MultiBookmakerOverUnderRecord] = []
    for m in matching_report.matched:
        b365 = m.football_data.over_under_2_5_by_bookmaker().get("B365")
        max_avg = m.football_data.max_avg_over_under_2_5()
        max_odds = max_avg.get("Max")
        avg_odds = max_avg.get("Avg")
        records.append(
            MultiBookmakerOverUnderRecord(
                match_id=m.understat.match_id,
                league=league,
                season=season,
                b365_over_2_5=b365["Over"] if b365 else None,
                b365_under_2_5=b365["Under"] if b365 else None,
                max_over_2_5=max_odds["Over"] if max_odds else None,
                max_under_2_5=max_odds["Under"] if max_odds else None,
                avg_over_2_5=avg_odds["Over"] if avg_odds else None,
                avg_under_2_5=avg_odds["Under"] if avg_odds else None,
            )
        )

    return MultiBookmakerOverUnderReport(
        league=league,
        season=season,
        n_understat=matching_report.n_understat,
        n_football_data=matching_report.n_football_data,
        n_matched=matching_report.n_matched,
        n_unmatched_understat=matching_report.n_unmatched_understat,
        n_unmatched_football_data=matching_report.n_unmatched_football_data,
        records=tuple(records),
    )
