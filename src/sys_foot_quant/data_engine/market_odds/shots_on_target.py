"""Historique point-in-time des tirs cadres (HST/AST, Football-Data) -
Phase F (docs/sot_incremental_information_experiment.md, docs/next_signal_strategy.md).

Question posee : les tirs cadres apportent-ils une information PREDICTIVE
INCREMENTALE sur le total de buts / Over 2.5, au-dela de ce que le moteur
actuel (`poisson_simple` + correction E7/E8) et/ou le marche possedent
deja ? Ce module se limite STRICTEMENT a la construction du signal
(appariement + historique walk-forward) - AUCUNE comparaison de modele,
AUCUN test statistique ici (voir `scripts/run_stage27_phase_f_sot_incremental_information.py`).

RESERVE ABSOLUE (non negociable, protocole Phase F) : ``HST``/``AST``
sont des statistiques de match, connues seulement APRES le coup d'envoi
(meme moment de publication que le score final dans la meme ligne source
Football-Data) - JAMAIS un feature du match qu'elles decrivent
elles-memes. Elles ne sont exploitables QUE comme entree HISTORIQUE
(moyenne d'un match anterieur) d'un futur match. ``sot_knowledge_time``
reutilise EXACTEMENT ``DEFAULT_GOALS_KNOWLEDGE_DELAY_HOURS`` (kickoff+2h,
`real_data_walk_forward.py`) - meme moment de publication que le score
final, aucun nouveau delai invente.

Appariement Understat<->Football-Data REUTILISE SANS MODIFICATION
(`matching.build_understat_keys`/`match_league_season`, deja valide par
`over_under_odds.py`/`multi_bookmaker_odds.py`) - ``home_team_id``/
``away_team_id`` proviennent d'Understat (meme espace d'identifiants que
`poisson_simple`/`xg_model`/`RealMatchRecord`), jamais un nouvel
identifiant invente.

DECISIONS METHODOLOGIQUES FIGEES AVANT TOUTE EXECUTION SUR DONNEES
REELLES (Phase F, etape 4/9 du protocole) :

1. Minimum d'historique requis avant de produire une feature SOT pour un
   match : REUTILISE EXACTEMENT ``MIN_TRAIN_MATCHES`` (=10,
   `economic_dataset.py`) - le MEME seuil, sur le MEME type de pool
   (historique POOLE d'un championnat x saison, matchs strictement
   anterieurs a `decision_time`), que celui qui gouverne deja si
   `poisson_simple`/`xg_model` produisent une prediction du tout
   (`_goals_train_df`/`_xg_train_df`, `predict_match`). Aucun seuil
   distinct n'est invente pour SOT.
2. Comportement d'une equipe SANS historique dans le pool (alors que le
   pool poole depasse le seuil ci-dessus) : reutilise EXACTEMENT le
   mecanisme de repli neutre deja code par ``XGModel.fit`` (une equipe
   absente du pool recoit la valeur MOYENNE DU POOL, jamais une valeur
   inventee ni une exclusion du match) - translittere ici en unites de
   tirs cadres bruts (au lieu d'un ratio d'attaque/defense) puisque les
   deux features retenues (etape 3) sont des scalaires bruts, pas des
   ratios.
3. Features retenues (minimales, JAMAIS multipliees - protocole Phase F,
   etape 2/11) : exactement DEUX scalaires,
   ``sot_produced_total = moyenne_historique_tires_cadres_marques(domicile)
   + moyenne_historique_tires_cadres_marques(exterieur)`` et
   ``sot_conceded_total`` (son miroir pour les tirs cadres ENCAISSES).
   Aucune troisieme variante (ratio, difference, fenetre glissante courte,
   pondération temporelle) n'est testee.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd

from sys_foot_quant.backtesting_engine.real_data_walk_forward import DEFAULT_GOALS_KNOWLEDGE_DELAY_HOURS
from sys_foot_quant.data_engine.market_odds.economic_dataset import MIN_TRAIN_MATCHES
from sys_foot_quant.data_engine.market_odds.football_data_loader import FootballDataMatchRecord
from sys_foot_quant.data_engine.market_odds.matching import build_understat_keys, match_league_season

_EPS = 1e-9


@dataclass(frozen=True)
class ShotsOnTargetMatchRecord:
    match_id: str
    league: str
    season: str
    kickoff_utc: datetime
    home_team_id: int
    away_team_id: int
    home_shots_on_target: int
    away_shots_on_target: int
    sot_knowledge_time: datetime


@dataclass(frozen=True)
class ShotsOnTargetReport:
    league: str
    season: str
    n_understat: int
    n_football_data: int
    n_matched: int
    n_unmatched_understat: int
    n_unmatched_football_data: int
    records: tuple[ShotsOnTargetMatchRecord, ...]


def build_shots_on_target_dataset(
    league: str,
    season: str,
    understat_raw: list[dict],
    football_data_records: list[FootballDataMatchRecord],
    knowledge_delay_hours: float = DEFAULT_GOALS_KNOWLEDGE_DELAY_HOURS,
) -> ShotsOnTargetReport:
    """Construit, pour UN championnat et UNE saison, les enregistrements
    de tirs cadres appariés (Understat pour les identifiants d'equipe et
    le coup d'envoi, Football-Data pour HST/AST). Un match non apparie
    est simplement absent - jamais invente ni impute (meme discipline que
    `over_under_odds.py`)."""
    understat_keys = build_understat_keys(understat_raw, league, season)
    matching_report = match_league_season(understat_keys, football_data_records, league, season)

    records: list[ShotsOnTargetMatchRecord] = []
    for m in matching_report.matched:
        records.append(
            ShotsOnTargetMatchRecord(
                match_id=m.understat.match_id,
                league=league,
                season=season,
                kickoff_utc=m.understat.kickoff_utc,
                home_team_id=m.understat.home_team_id,
                away_team_id=m.understat.away_team_id,
                home_shots_on_target=m.football_data.home_shots_on_target,
                away_shots_on_target=m.football_data.away_shots_on_target,
                sot_knowledge_time=m.understat.kickoff_utc + timedelta(hours=knowledge_delay_hours),
            )
        )

    return ShotsOnTargetReport(
        league=league,
        season=season,
        n_understat=matching_report.n_understat,
        n_football_data=matching_report.n_football_data,
        n_matched=matching_report.n_matched,
        n_unmatched_understat=matching_report.n_unmatched_understat,
        n_unmatched_football_data=matching_report.n_unmatched_football_data,
        records=tuple(records),
    )


def sot_training_pool(
    records: list[ShotsOnTargetMatchRecord], decision_time: datetime, exclude_match_id: str
) -> pd.DataFrame:
    """Pool d'entrainement point-in-time pour UN match : tous les
    enregistrements dont `sot_knowledge_time <= decision_time`, a
    l'exclusion explicite du match lui-meme - EXACTEMENT le meme filtre,
    sur le meme type de pool, que `_goals_train_df`/`_xg_train_df`
    (`run_stage8...py`) pour les buts/xG. Structurellement,
    `sot_knowledge_time` (kickoff+2h) est toujours > `decision_time`
    (kickoff-2h) pour le match lui-meme ; `exclude_match_id` reste un
    garde-fou redondant explicite, jamais suppose suffisant a lui seul."""
    rows = [
        {
            "home_team_id": r.home_team_id,
            "away_team_id": r.away_team_id,
            "home_sot": r.home_shots_on_target,
            "away_sot": r.away_shots_on_target,
        }
        for r in records
        if r.match_id != exclude_match_id and r.sot_knowledge_time <= decision_time
    ]
    return pd.DataFrame(rows, columns=["home_team_id", "away_team_id", "home_sot", "away_sot"])


def historical_sot_averages(pool_df: pd.DataFrame) -> tuple[dict[int, float], dict[int, float], float, float]:
    """Moyenne (non ponderee) des tirs cadres MARQUES/ENCAISSES par
    equipe sur `pool_df` - translitteration directe de la boucle
    `scored_sum`/`conceded_sum`/`weight_total` de ``XGModel.fit``
    (poids plats, jamais un choix de ponderation different ici).
    Retourne aussi la moyenne du pool entier (marques, encaisses) -
    valeur de repli pour une equipe absente du pool (meme convention que
    le repli neutre de `XGModel`, translittere en unites brutes)."""
    if pool_df.empty:
        return {}, {}, 0.0, 0.0

    home_ids = pool_df["home_team_id"].to_numpy()
    away_ids = pool_df["away_team_id"].to_numpy()
    home_sot = pool_df["home_sot"].to_numpy(dtype=float)
    away_sot = pool_df["away_sot"].to_numpy(dtype=float)
    n = len(pool_df)

    pool_mean_for = float((home_sot.sum() + away_sot.sum()) / (2.0 * n))
    pool_mean_against = pool_mean_for  # meme pool, marque/encaisse sont le meme ensemble de valeurs vu des deux cotes

    teams = sorted(set(home_ids.tolist()) | set(away_ids.tolist()))
    scored_sum = {t: 0.0 for t in teams}
    conceded_sum = {t: 0.0 for t in teams}
    count = {t: 0 for t in teams}
    for i in range(n):
        h, a = home_ids[i], away_ids[i]
        scored_sum[h] += home_sot[i]
        scored_sum[a] += away_sot[i]
        conceded_sum[h] += away_sot[i]
        conceded_sum[a] += home_sot[i]
        count[h] += 1
        count[a] += 1

    avg_for = {t: (scored_sum[t] / count[t] if count[t] > 0 else pool_mean_for) for t in teams}
    avg_against = {t: (conceded_sum[t] / count[t] if count[t] > 0 else pool_mean_against) for t in teams}
    return avg_for, avg_against, pool_mean_for, pool_mean_against


def sot_features_for_match(
    pool_df: pd.DataFrame,
    home_team_id: int,
    away_team_id: int,
    min_train_matches: int = MIN_TRAIN_MATCHES,
) -> tuple[float, float, int] | None:
    """(`sot_produced_total`, `sot_conceded_total`, `n_pool`) pour UN
    match, ou ``None`` si le pool poole est strictement inferieur a
    `min_train_matches` (regle d'exclusion REUTILISEE, jamais une
    prediction de repli inventee - meme discipline que `predict_match`)."""
    n = len(pool_df)
    if n < min_train_matches:
        return None

    avg_for, avg_against, pool_mean_for, pool_mean_against = historical_sot_averages(pool_df)
    for_h = avg_for.get(home_team_id, pool_mean_for)
    for_a = avg_for.get(away_team_id, pool_mean_for)
    against_h = avg_against.get(home_team_id, pool_mean_against)
    against_a = avg_against.get(away_team_id, pool_mean_against)

    return for_h + for_a, against_h + against_a, n
