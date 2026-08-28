"""Construction du jeu de donnees economique (premiere experience economique
reelle - `poisson_simple` vs marche B365 1X2, docs/research_framework.md,
section H a venir).

Assemble, pour un championnat et une saison donnes, EXACTEMENT les memes
briques deja validees separement :

- ``backtesting_engine.real_data_walk_forward`` (INCHANGE) pour les
  probabilites ``poisson_simple`` point-in-time (buts connus a kickoff+2h,
  meme convention que B1/A2/B2/B3.3) ;
- ``data_engine.market_odds.matching`` (INCHANGE) pour l'appariement
  Understat <-> Football-Data ;
- ``data_engine.market_odds.time_resolution`` (INCHANGE) pour la regle
  point-in-time conservatrice des cotes (voir
  docs/decisions/0006-football-data-point-in-time.md) ;
- ``market_engine.model_vs_market`` et ``value_engine.edge`` (INCHANGES)
  pour la comparaison modele/marche et le calcul d'EV/edge.

Ce module ne calcule NI ROI, NI strategie, NI selection de pari - il ne
fait que produire, match par match, un enregistrement economique complet et
la liste explicite des matchs exclus avec leur raison (jamais un residu
silencieux). Aucun des modules reutilises n'est modifie."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sys_foot_quant.backtesting_engine.real_data_walk_forward import (
    RealModelConfig,
    build_real_match_records,
    run_real_data_walk_forward,
)
from sys_foot_quant.data_engine.market_odds.football_data_loader import FootballDataMatchRecord
from sys_foot_quant.data_engine.market_odds.matching import (
    UnderstatMatchKey,
    build_understat_keys,
    match_league_season,
)
from sys_foot_quant.data_engine.market_odds.time_resolution import (
    TIMESTAMP_STATUS_HYPOTHETICAL,
    AmbiguousCollectionWindowError,
    conservative_knowledge_time_utc,
)
from sys_foot_quant.football_model.poisson import PoissonModel
from sys_foot_quant.market_engine.model_vs_market import compare_model_to_market
from sys_foot_quant.value_engine.edge import edge as compute_edge
from sys_foot_quant.value_engine.edge import expected_value

DECISION_OFFSET_HOURS = 2.0
MIN_TRAIN_MATCHES = 10

_HOME, _DRAW, _AWAY = "home", "draw", "away"
SELECTIONS = (_HOME, _DRAW, _AWAY)

_OUTCOME_TO_SELECTION = {0: _HOME, 1: _DRAW, 2: _AWAY}


def _fit_poisson_simple(goals_df, xg_df, decision_time):
    return PoissonModel(use_team_hfa=False).fit(goals_df)


@dataclass(frozen=True)
class EconomicMatchRecord:
    match_id: str
    league: str
    season: str
    kickoff_utc: datetime
    decision_time_utc: datetime
    knowledge_time_utc: datetime
    timestamp_status: str
    home_team: str
    away_team: str
    outcome: int  # 0 domicile, 1 nul, 2 exterieur (meme convention que real_data_walk_forward)
    outcome_selection: str  # "home" / "draw" / "away"
    model_probs: dict[str, float]
    market_odds: dict[str, float]
    implied_prob_raw: dict[str, float]
    implied_prob_normalized: dict[str, float]
    overround: float
    edge_raw: dict[str, float]
    edge_norm: dict[str, float]
    ev: dict[str, float]


@dataclass(frozen=True)
class EconomicDatasetReport:
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
    n_excluded_insufficient_history: int
    n_excluded_pit_violation: int
    n_exploitable: int
    records: tuple[EconomicMatchRecord, ...] = field(default_factory=tuple)


def build_economic_dataset(
    league: str,
    season: str,
    understat_raw: list[dict],
    football_data_records: list[FootballDataMatchRecord],
) -> EconomicDatasetReport:
    """Construit le jeu de donnees economique exploitable pour UN
    championnat et UNE saison. ``understat_raw`` : schema brut Understat
    complet (tous les matchs, utilise aussi pour reconstruire l'historique
    d'entrainement point-in-time de ``poisson_simple``, pas seulement les
    matchs finalement exploitables)."""
    understat_keys: list[UnderstatMatchKey] = build_understat_keys(understat_raw, league, season)
    matching_report = match_league_season(understat_keys, football_data_records, league, season)

    real_records = build_real_match_records(understat_raw, league=league)

    n_excluded_ambiguous_weekday = 0
    n_excluded_incomplete_odds = 0
    eval_candidates: list[tuple] = []  # (MatchedRecord, knowledge_time_utc)
    for m in matching_report.matched:
        if not m.football_data.has_complete_odds:
            n_excluded_incomplete_odds += 1
            continue
        try:
            knowledge_time = conservative_knowledge_time_utc(m.understat.kickoff_utc)
        except AmbiguousCollectionWindowError:
            n_excluded_ambiguous_weekday += 1
            continue
        eval_candidates.append((m, knowledge_time))

    eval_match_ids = [m.understat.match_id for m, _ in eval_candidates]
    model_configs = [
        RealModelConfig(name="poisson_simple", fit=_fit_poisson_simple, min_train_matches=MIN_TRAIN_MATCHES)
    ]
    evaluations = run_real_data_walk_forward(
        real_records,
        eval_match_ids=eval_match_ids,
        decision_offset_hours=DECISION_OFFSET_HOURS,
        model_configs=model_configs,
    )
    eval_by_id = {ev.match_id: ev for ev in evaluations}

    n_excluded_insufficient_history = 0
    n_excluded_pit_violation = 0
    records: list[EconomicMatchRecord] = []
    for m, knowledge_time in eval_candidates:
        ev = eval_by_id[m.understat.match_id]
        p = ev.predictions.get("poisson_simple")
        if p is None:
            n_excluded_insufficient_history += 1
            continue
        # ``ev.decision_time`` provient de ``real_data_walk_forward`` (kickoff
        # naif, jamais tzinfo-aware - convention deja utilisee, non modifiee
        # ici) alors que ``knowledge_time`` (time_resolution) est UTC
        # tzinfo-aware ; les deux representent la meme grandeur UTC (memes
        # chaines source Understat), seule la representation differe - on
        # normalise ici, uniquement pour la comparaison, sans toucher aux
        # deux modules geles.
        if not (knowledge_time.replace(tzinfo=None) <= ev.decision_time):
            # N'est jamais cense se produire par construction (voir
            # time_resolution.conservative_knowledge_time_utc), mais
            # verifie explicitement plutot que suppose - exclu et compte
            # separement si jamais ce n'etait pas le cas, jamais une
            # fuite silencieuse.
            n_excluded_pit_violation += 1
            continue

        model_probs = {_HOME: p[0], _DRAW: p[1], _AWAY: p[2]}
        market_odds = {
            _HOME: m.football_data.b365_home,
            _DRAW: m.football_data.b365_draw,
            _AWAY: m.football_data.b365_away,
        }
        comparison = compare_model_to_market(model_probs, market_odds)
        edge_raw = {
            s: compute_edge(model_probs[s], comparison["implied_prob_raw"][s]) for s in SELECTIONS
        }
        ev_dict = {s: expected_value(model_probs[s], market_odds[s]) for s in SELECTIONS}

        records.append(
            EconomicMatchRecord(
                match_id=m.understat.match_id,
                league=league,
                season=season,
                kickoff_utc=m.understat.kickoff_utc,
                decision_time_utc=ev.decision_time,
                knowledge_time_utc=knowledge_time,
                timestamp_status=TIMESTAMP_STATUS_HYPOTHETICAL,
                home_team=m.understat.home_team_name,
                away_team=m.understat.away_team_name,
                outcome=ev.outcome,
                outcome_selection=_OUTCOME_TO_SELECTION[ev.outcome],
                model_probs=model_probs,
                market_odds=market_odds,
                implied_prob_raw=comparison["implied_prob_raw"],
                implied_prob_normalized=comparison["implied_prob_normalized"],
                overround=comparison["overround"],
                edge_raw=edge_raw,
                edge_norm=comparison["model_minus_market"],
                ev=ev_dict,
            )
        )

    return EconomicDatasetReport(
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
        n_excluded_insufficient_history=n_excluded_insufficient_history,
        n_excluded_pit_violation=n_excluded_pit_violation,
        n_exploitable=len(records),
        records=tuple(records),
    )
