"""Walk-forward Over/Under 2.5 avec ponderation temporelle explicite -
coeur de l'experience (voir ``__init__.py``/``README.md``).

Reutilise SANS MODIFICATION :
- ``football_model.weighting.flat_weights``/``exponential_decay_weights``
  (formule ``weight(age_days) = 0.5 ** (age_days/half_life_days)`` DEJA
  presente dans le depot, exactement celle demandee - aucune nouvelle
  formule de ponderation ecrite ici) ;
- ``football_model.poisson.PoissonModel`` (accepte deja un parametre
  ``weights`` optionnel dans son API existante - jamais modifiee, jamais
  une nouvelle branche de code ajoutee au modele) ;
- ``football_model.scoring.score_matrix`` / ``football_model.goal_distribution.over_under_probs`` ;
- ``backtesting_engine.real_data_walk_forward._goals_train_df`` (filtrage
  point-in-time, IDENTIQUE a celui utilise par E7/E8/final_engine).

La SEULE logique nouvelle : calculer l'age (en jours) de chaque match
d'entrainement par rapport a ``decision_time``, et orchestrer la boucle
walk-forward multi-schema (A0 plat, A1-A5 decroissance) sur EXACTEMENT le
meme historique/cible pour chaque schema - aucune correction d'echelle
E7/E8 appliquee ICI (voir README.md, limite assumee et documentee : cette
correction n'a ete validee scientifiquement que sous ponderation plate ;
l'appliquer sous une autre ponderation sans revalidation introduirait un
facteur de confusion non controle - la meme absence de correction
s'applique identiquement a A0-A5, donc la comparaison RELATIVE entre
schemas reste valide)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from sys_foot_quant.backtesting_engine.real_data_walk_forward import (
    RealMatchRecord,
    _goals_train_df,
)
from sys_foot_quant.football_model.goal_distribution import over_under_probs
from sys_foot_quant.football_model.poisson import PoissonModel
from sys_foot_quant.football_model.scoring import score_matrix
from sys_foot_quant.football_model.weighting import exponential_decay_weights, flat_weights

MIN_TRAIN_MATCHES = 10  # identique a economic_dataset.MIN_TRAIN_MATCHES (INCHANGE, jamais redefini ici)
DECISION_OFFSET_HOURS = 2.0  # identique a economic_dataset.DECISION_OFFSET_HOURS (INCHANGE)
DEFAULT_MAX_GOALS = 20
OU_THRESHOLD = 2.5


@dataclass(frozen=True)
class WeightingScheme:
    """Un schema de ponderation nomme. ``half_life_days=None`` => poids
    plat (A0, methode de production actuelle) ; sinon decroissance
    exponentielle de demi-vie ``half_life_days`` jours (A1-A5)."""

    name: str
    half_life_days: float | None


FLAT_SCHEME = WeightingScheme(name="A0_flat", half_life_days=None)
DECAY_SCHEMES = (
    WeightingScheme(name="A1_halflife_30d", half_life_days=30.0),
    WeightingScheme(name="A2_halflife_60d", half_life_days=60.0),
    WeightingScheme(name="A3_halflife_90d", half_life_days=90.0),
    WeightingScheme(name="A4_halflife_180d", half_life_days=180.0),
    WeightingScheme(name="A5_halflife_365d", half_life_days=365.0),
)
ALL_SCHEMES = (FLAT_SCHEME, *DECAY_SCHEMES)


def compute_weights_for_scheme(
    kickoff_times: pd.Series, decision_time: datetime, scheme: WeightingScheme
) -> np.ndarray:
    """Poids de chaque match d'entrainement, fonction UNIQUEMENT de son
    age (en jours) par rapport a ``decision_time`` - reutilise
    ``flat_weights``/``exponential_decay_weights`` (INCHANGES), aucune
    nouvelle formule. Leve explicitement si un age negatif est trouve
    (match d'entrainement posterieur a ``decision_time``) - jamais tolere
    silencieusement, meme si ``_goals_train_df`` l'a deja normalement
    exclu en amont (garde-fou redondant, meme discipline que le reste du
    projet)."""
    n = len(kickoff_times)
    if scheme.half_life_days is None:
        return flat_weights(n)
    age_days = np.array(
        [(decision_time - kt).total_seconds() / 86400.0 for kt in kickoff_times], dtype=float
    )
    if age_days.size and (age_days < 0).any():
        raise ValueError(
            "Match d'entrainement d'age negatif detecte (kickoff posterieur a decision_time) - "
            "fuite temporelle potentielle, jamais tolere silencieusement."
        )
    return exponential_decay_weights(age_days, scheme.half_life_days)


def predict_over_2_5_probability(
    goals_train_df: pd.DataFrame,
    weights: np.ndarray,
    home_team_id: int,
    away_team_id: int,
    max_goals: int = DEFAULT_MAX_GOALS,
) -> float:
    """P(Over 2.5) BRUTE (``poisson_simple``, ``use_team_hfa=False`` -
    IDENTIQUE au choix de construction de ``final_engine/prediction.py``),
    SANS correction d'echelle E7/E8 (voir limite documentee en tete de
    module) - IDENTIQUE pour tout schema de ponderation, seule ``weights``
    varie entre appels."""
    model = PoissonModel(use_team_hfa=False).fit(goals_train_df, weights=weights)
    lam, mu = model.predict_lambda_mu(home_team_id, away_team_id)
    matrix = score_matrix(lam, mu, max_goals=max_goals)
    return over_under_probs(matrix, thresholds=(OU_THRESHOLD,))[OU_THRESHOLD]


def run_walkforward(
    records: list[RealMatchRecord],
    schemes: tuple[WeightingScheme, ...] = ALL_SCHEMES,
    decision_offset_hours: float = DECISION_OFFSET_HOURS,
    min_train_matches: int = MIN_TRAIN_MATCHES,
    max_goals: int = DEFAULT_MAX_GOALS,
) -> pd.DataFrame:
    """Walk-forward complet, un flux chronologique unique (ex. UNE
    competition) : pour CHAQUE match de ``records`` (trie par
    ``kickoff_utc``), calcule P(Over 2.5) pour CHAQUE schema, sur
    EXACTEMENT le meme historique d'entrainement filtre point-in-time
    (``_goals_train_df``, INCHANGE, exclusion explicite du match evalue
    lui-meme) - seule la ponderation differe entre schemas, jamais
    l'ensemble de matchs d'entrainement disponibles ni le match cible
    (garantit le critere "meme ensemble de matchs cibles pour toutes les
    methodes").

    Une ligne ``NaN`` (toutes colonnes ``p_over_2_5_*``) si l'historique
    disponible est strictement inferieur a ``min_train_matches`` - jamais
    une valeur de repli inventee, meme comportement que
    ``final_engine.prediction.predict_match``."""
    ordered = sorted(records, key=lambda r: r.kickoff_utc)
    rows: list[dict] = []
    for r in ordered:
        decision_time = r.kickoff_utc - timedelta(hours=decision_offset_hours)
        goals_df = _goals_train_df(ordered, decision_time, exclude_match_id=r.match_id)
        row: dict = {
            "match_id": r.match_id,
            "league": r.league,
            "kickoff_utc": r.kickoff_utc,
            "decision_time": decision_time,
            "home_team_id": r.home_team_id,
            "away_team_id": r.away_team_id,
            "total_goals": r.home_goals + r.away_goals,
            "y_over_2_5": 1.0 if (r.home_goals + r.away_goals) > OU_THRESHOLD else 0.0,
            "n_train_matches": len(goals_df),
        }
        eligible = len(goals_df) >= min_train_matches
        for scheme in schemes:
            col = f"p_over_2_5_{scheme.name}"
            if not eligible:
                row[col] = float("nan")
                continue
            weights = compute_weights_for_scheme(goals_df["kickoff_time"], decision_time, scheme)
            row[col] = predict_over_2_5_probability(
                goals_df, weights, r.home_team_id, r.away_team_id, max_goals=max_goals
            )
        rows.append(row)
    return pd.DataFrame(rows)


def binary_brier_score(probs: np.ndarray, outcomes: np.ndarray) -> np.ndarray:
    """Brier score binaire standard PAR MATCH : ``(p - y)**2`` - forme
    canonique (Brier, 1950) pour une prevision binaire, distincte de
    ``calibration_engine.metrics.brier_score`` (specifique au marche 1X2
    a 3 issues, jamais reutilisable telle quelle pour Over/Under sans
    reinterpretation ambigue). Retourne le vecteur PAR MATCH (pas la
    moyenne) pour permettre un test apparie (``paired_bootstrap_test``)."""
    probs = np.asarray(probs, dtype=float)
    outcomes = np.asarray(outcomes, dtype=float)
    return (probs - outcomes) ** 2


def binary_log_loss(probs: np.ndarray, outcomes: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    """Log loss binaire PAR MATCH, avec clipping (meme epsilon que
    ``calibration_engine.metrics.log_loss``) pour eviter ``log(0)``."""
    probs = np.clip(np.asarray(probs, dtype=float), eps, 1.0 - eps)
    outcomes = np.asarray(outcomes, dtype=float)
    return -(outcomes * np.log(probs) + (1.0 - outcomes) * np.log(1.0 - probs))
