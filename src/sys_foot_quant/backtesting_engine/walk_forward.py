"""Walk-forward hors echantillon : orchestration point-in-time des modeles
et benchmarks de l'etape 2.

Pour chaque match evalue, a l'instant de decision T (= kickoff - offset) :

1. Le Repository fournit, via ``get_as_of``, exactement les matchs dont le
   resultat etait connu a T (jointure matches/match_results filtree par
   knowledge_time) - c'est la seule source de verite sur ce qui est
   "visible" a cet instant, aucune autre logique de filtrage temporel
   n'est appliquee ici.
2. Chaque configuration de modele est (re)entrainee sur cet historique
   uniquement, puis interrogee pour le match evalue.
3. Le benchmark marche (sans marge) est lu, si disponible, a partir du
   dernier snapshot de cotes connu a T.
4. Le resultat reel du match (connu APRES T) sert uniquement a
   l'evaluation a posteriori des predictions deja figees - jamais a une
   decision de modele.

Limite de portee assumee : chaque modele est re-entraine integralement a
chaque point de decision (pas d'incrementalite), ce qui est simple et
correct mais ne passerait pas a l'echelle sur un historique de plusieurs
dizaines de milliers de matchs sans optimisation - suffisant pour la
taille de jeu de donnees synthetique de l'etape 2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Protocol

import numpy as np
import pandas as pd

from sys_foot_quant.common.time_utils import to_utc
from sys_foot_quant.data_engine.storage.repository import DuckDBRepository
from sys_foot_quant.market_engine.overround import remove_overround_proportional

_HOME, _DRAW, _AWAY = 0, 1, 2


class FittedPredictor(Protocol):
    def predict(self, home_team_id: int, away_team_id: int) -> tuple[float, float, float]: ...


@dataclass(frozen=True)
class ModelConfig:
    name: str
    # (training_df avec colonnes home_team_id/away_team_id/home_goals/away_goals/kickoff_time,
    #  decision_time) -> objet expose une methode predict(home,away)->(p_home,p_draw,p_away)
    fit: Callable[[pd.DataFrame, datetime], FittedPredictor]


@dataclass(frozen=True)
class MatchEvaluation:
    match_id: int
    decision_time: datetime
    home_team_id: int
    away_team_id: int
    outcome: int  # 0=domicile, 1=nul, 2=exterieur
    predictions: dict[str, tuple[float, float, float] | None] = field(default_factory=dict)


def _outcome_index(home_goals: int, away_goals: int) -> int:
    if home_goals > away_goals:
        return _HOME
    if home_goals == away_goals:
        return _DRAW
    return _AWAY


def market_benchmark_probs(
    repository: DuckDBRepository, match_id: int, decision_time: datetime
) -> tuple[float, float, float] | None:
    """Derniere cote 1X2 connue a ``decision_time`` pour ``match_id``, marge retiree.

    Retourne None si aucune cote n'est encore disponible a cet instant
    (marche pas encore ouvert) ou si les trois selections ne sont pas
    toutes presentes dans le dernier snapshot.
    """
    snapshots = repository.get_as_of("odds_snapshots", decision_time)
    match_snapshots = snapshots[snapshots["match_id"] == match_id]
    if match_snapshots.empty:
        return None
    latest_time = match_snapshots["knowledge_time"].max()
    latest = match_snapshots[match_snapshots["knowledge_time"] == latest_time]
    odds = dict(zip(latest["selection"], latest["odds_value"]))
    if not {"home", "draw", "away"}.issubset(odds):
        return None
    fair = remove_overround_proportional(odds)
    return (fair["home"], fair["draw"], fair["away"])


def run_walk_forward(
    repository: DuckDBRepository,
    eval_match_ids: list[int],
    decision_offset_hours: float,
    model_configs: list[ModelConfig],
    include_market_benchmark: bool = True,
) -> list[MatchEvaluation]:
    all_matches = repository.debug_get_full_table("matches")
    all_results = repository.debug_get_full_table("match_results")
    fixtures_by_id = all_matches.set_index("match_id")
    results_by_id = all_results.set_index("match_id")

    eval_kickoffs = [
        (mid, to_utc(fixtures_by_id.loc[mid, "kickoff_time"].to_pydatetime()))
        for mid in eval_match_ids
    ]
    eval_kickoffs.sort(key=lambda pair: pair[1])

    evaluations: list[MatchEvaluation] = []
    for match_id, kickoff in eval_kickoffs:
        decision_time = kickoff - timedelta(hours=decision_offset_hours)

        matches_asof = repository.get_as_of("matches", decision_time)
        results_asof = repository.get_as_of("match_results", decision_time)
        train_df = matches_asof.merge(results_asof, on="match_id", how="inner")
        train_df = train_df[train_df["match_id"] != match_id]
        train_df = train_df[
            ["home_team_id", "away_team_id", "home_goals", "away_goals", "kickoff_time"]
        ]

        fixture = fixtures_by_id.loc[match_id]
        home_team_id = int(fixture["home_team_id"])
        away_team_id = int(fixture["away_team_id"])
        result = results_by_id.loc[match_id]
        outcome = _outcome_index(int(result["home_goals"]), int(result["away_goals"]))

        predictions: dict[str, tuple[float, float, float] | None] = {}
        if len(train_df) == 0:
            for cfg in model_configs:
                predictions[cfg.name] = None
        else:
            for cfg in model_configs:
                model = cfg.fit(train_df, decision_time)
                predictions[cfg.name] = model.predict(home_team_id, away_team_id)

        if include_market_benchmark:
            predictions["market_no_vig"] = market_benchmark_probs(
                repository, match_id, decision_time
            )

        evaluations.append(
            MatchEvaluation(
                match_id=match_id,
                decision_time=decision_time,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                outcome=outcome,
                predictions=predictions,
            )
        )

    return evaluations


def to_probs_and_outcomes(
    evaluations: list[MatchEvaluation], model_name: str
) -> tuple[np.ndarray, np.ndarray]:
    """Extrait (probs, outcomes) pour un modele donne, en ignorant les
    matchs ou ce modele n'a pas produit de prediction (ex: marche
    indisponible)."""
    rows = []
    outcomes = []
    for ev in evaluations:
        p = ev.predictions.get(model_name)
        if p is None:
            continue
        rows.append(p)
        outcomes.append(ev.outcome)
    return np.array(rows), np.array(outcomes)
