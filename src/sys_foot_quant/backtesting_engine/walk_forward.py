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
from sys_foot_quant.market_engine.snapshot import latest_odds_as_of

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
    home_goals: int
    away_goals: int
    outcome: int  # 0=domicile, 1=nul, 2=exterieur
    predictions: dict[str, tuple[float, float, float] | None] = field(default_factory=dict)
    # (lambda, mu) predits, uniquement pour les modeles qui exposent
    # predict_lambda_mu (PoissonModel) - None sinon (naive/elo/marche).
    # Utilise exclusivement par le diagnostic de Chi-Deux
    # (calibration_engine.goodness_of_fit), jamais par les metriques de
    # decision (Brier/log loss, qui restent bases sur ``predictions``).
    lambda_mu: dict[str, tuple[float, float] | None] = field(default_factory=dict)
    # (P(0-0), P(1-0), P(0-1), P(1-1)) predits, uniquement pour les
    # modeles qui exposent predict_low_score_probs (PoissonModel,
    # DixonColesModel) - None sinon. AJOUT PUR pour le protocole B1
    # (docs/research_framework.md section B1) : ne modifie ni le contenu
    # ni le calcul de ``predictions``/``lambda_mu`` pour aucun modele
    # existant. Utilise exclusivement par
    # calibration_engine.low_score_metrics.
    low_score_probs: dict[str, tuple[float, float, float, float] | None] = field(
        default_factory=dict
    )


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
    odds = latest_odds_as_of(repository, match_id, decision_time)
    if odds is None or not {"home", "draw", "away"}.issubset(odds):
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
        lambda_mu: dict[str, tuple[float, float] | None] = {}
        low_score_probs: dict[str, tuple[float, float, float, float] | None] = {}
        if len(train_df) == 0:
            for cfg in model_configs:
                predictions[cfg.name] = None
                lambda_mu[cfg.name] = None
                low_score_probs[cfg.name] = None
        else:
            for cfg in model_configs:
                model = cfg.fit(train_df, decision_time)
                predictions[cfg.name] = model.predict(home_team_id, away_team_id)
                predict_lm = getattr(model, "predict_lambda_mu", None)
                lambda_mu[cfg.name] = (
                    predict_lm(home_team_id, away_team_id) if predict_lm is not None else None
                )
                predict_lsp = getattr(model, "predict_low_score_probs", None)
                low_score_probs[cfg.name] = (
                    predict_lsp(home_team_id, away_team_id) if predict_lsp is not None else None
                )

        if include_market_benchmark:
            predictions["market_no_vig"] = market_benchmark_probs(
                repository, match_id, decision_time
            )
            lambda_mu["market_no_vig"] = None
            low_score_probs["market_no_vig"] = None

        evaluations.append(
            MatchEvaluation(
                match_id=match_id,
                decision_time=decision_time,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                home_goals=int(result["home_goals"]),
                away_goals=int(result["away_goals"]),
                outcome=outcome,
                predictions=predictions,
                lambda_mu=lambda_mu,
                low_score_probs=low_score_probs,
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


def to_low_score_probs_and_goals(
    evaluations: list[MatchEvaluation], model_name: str
) -> tuple[list[tuple[float, float, float, float]], np.ndarray, np.ndarray]:
    """Extrait les (P(0-0), P(1-0), P(0-1), P(1-1)) predits et les buts
    reellement observes, pour les matchs ou ``model_name`` expose
    predict_low_score_probs (voir calibration_engine.low_score_metrics,
    protocole B1)."""
    probs = []
    home_goals = []
    away_goals = []
    for ev in evaluations:
        p = ev.low_score_probs.get(model_name)
        if p is None:
            continue
        probs.append(p)
        home_goals.append(ev.home_goals)
        away_goals.append(ev.away_goals)
    return probs, np.array(home_goals), np.array(away_goals)


def to_lambda_mu_and_goals(
    evaluations: list[MatchEvaluation], model_name: str
) -> tuple[list[tuple[float, float]], np.ndarray, np.ndarray]:
    """Extrait (lambda, mu) predits et les buts reellement observes, pour
    les matchs ou ``model_name`` expose predict_lambda_mu (voir
    calibration_engine.goodness_of_fit)."""
    lambdas_mus = []
    home_goals = []
    away_goals = []
    for ev in evaluations:
        lm = ev.lambda_mu.get(model_name)
        if lm is None:
            continue
        lambdas_mus.append(lm)
        home_goals.append(ev.home_goals)
        away_goals.append(ev.away_goals)
    return lambdas_mus, np.array(home_goals), np.array(away_goals)
