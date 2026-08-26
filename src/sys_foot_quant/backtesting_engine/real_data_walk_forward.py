"""Walk-forward hors echantillon pour donnees REELLES (Understat), avec deux
flux de connaissance point-in-time INDEPENDANTS par match (hypothese B3,
docs/research_framework.md section B3) :

- ``goals_knowledge_time`` : quand le score reel du match devient connu
  (analogue au ``result_confirmation_delay_hours`` du generateur
  synthetique - meme convention, kickoff + 2h).
- ``xg_knowledge_time`` : quand la valeur xG du match devient connue.

AVERTISSEMENT DE TRANSPARENCE (a lire avant toute conclusion) : Understat
ne publie AUCUN horodatage officiel de publication par match. La valeur
``DEFAULT_XG_KNOWLEDGE_DELAY_HOURS`` ci-dessous est une hypothese
deliberement conservatrice (48h, superieure a la pratique habituelle du
secteur qui publie les statistiques de tirs en heures/jour suivant un
match), documentee comme telle - PAS un fait verifie. Ce delai ne doit
jamais etre confondu avec une fuite de donnees (look-ahead) : l'invariant
strict "aucun match a l'instant T ou apres n'influence la prediction du
match a T" reste garanti quel que soit ce delai, par construction (voir
``_as_of``) - ce qui est en question ici est seulement le REALISME de la
date a laquelle une valeur DEJA PASSEE devient disponible, pas l'ordre
chronologique des matchs eux-memes.

Ce module est deliberement separe de ``backtesting_engine/walk_forward.py``
(qui reste inchange, utilise par toutes les etapes precedentes sur donnees
synthetiques) : reutilise le MECANISME point-in-time (filtrage explicite
knowledge_time <= decision_time, meme principe que
``Repository.get_as_of``), mais sur des DataFrames en memoire plutot que
via DuckDB - une nouvelle table PIT par source (buts, xG) n'a pas a
transiter par le Repository existant pour cette experience isolee.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Protocol

import numpy as np
import pandas as pd

_HOME, _DRAW, _AWAY = 0, 1, 2

DEFAULT_GOALS_KNOWLEDGE_DELAY_HOURS = 2.0
DEFAULT_XG_KNOWLEDGE_DELAY_HOURS = 48.0


@dataclass(frozen=True)
class RealMatchRecord:
    match_id: str
    league: str
    kickoff_utc: datetime
    home_team_id: int
    away_team_id: int
    home_goals: int
    away_goals: int
    home_xg: float
    away_xg: float
    goals_knowledge_time: datetime
    xg_knowledge_time: datetime


def build_real_match_records(
    raw_matches: list[dict],
    league: str,
    goals_delay_hours: float = DEFAULT_GOALS_KNOWLEDGE_DELAY_HOURS,
    xg_delay_hours: float = DEFAULT_XG_KNOWLEDGE_DELAY_HOURS,
) -> list[RealMatchRecord]:
    """Construit les enregistrements PIT a partir du schema brut Understat
    (identique a celui deja utilise par ``research.xg_feasibility``, mais
    duplique ici deliberement - ce module de production ne doit jamais
    dependre du paquet de recherche isole, voir son propre avertissement
    d'isolation). Fonction PURE, aucun acces reseau."""
    records: list[RealMatchRecord] = []
    for raw in raw_matches:
        if not raw.get("isResult", False):
            continue
        kickoff = datetime.strptime(raw["datetime"], "%Y-%m-%d %H:%M:%S")
        records.append(
            RealMatchRecord(
                match_id=str(raw["id"]),
                league=league,
                kickoff_utc=kickoff,
                home_team_id=int(raw["h"]["id"]),
                away_team_id=int(raw["a"]["id"]),
                home_goals=int(raw["goals"]["h"]),
                away_goals=int(raw["goals"]["a"]),
                home_xg=float(raw["xG"]["h"]),
                away_xg=float(raw["xG"]["a"]),
                goals_knowledge_time=kickoff + timedelta(hours=goals_delay_hours),
                xg_knowledge_time=kickoff + timedelta(hours=xg_delay_hours),
            )
        )
    return records


def _outcome_index(home_goals: int, away_goals: int) -> int:
    if home_goals > away_goals:
        return _HOME
    if home_goals == away_goals:
        return _DRAW
    return _AWAY


def _goals_train_df(
    records: list[RealMatchRecord], decision_time: datetime, exclude_match_id: str
) -> pd.DataFrame:
    """Matchs dont le SCORE REEL est connu a ``decision_time`` - jamais le
    match evalue lui-meme (``exclude_match_id``), meme s'il etait par
    construction toujours strictement anterieur (garde-fou explicite,
    pas une simple consequence indirecte du filtre temporel)."""
    rows = [
        {
            "home_team_id": r.home_team_id,
            "away_team_id": r.away_team_id,
            "home_goals": r.home_goals,
            "away_goals": r.away_goals,
            "kickoff_time": r.kickoff_utc,
        }
        for r in records
        if r.match_id != exclude_match_id and r.goals_knowledge_time <= decision_time
    ]
    return pd.DataFrame(
        rows, columns=["home_team_id", "away_team_id", "home_goals", "away_goals", "kickoff_time"]
    )


def _xg_train_df(
    records: list[RealMatchRecord], decision_time: datetime, exclude_match_id: str
) -> pd.DataFrame:
    """Matchs dont le xG est connu a ``decision_time`` - meme garde-fou
    explicite que ``_goals_train_df`` pour le match evalue lui-meme."""
    rows = [
        {
            "home_team_id": r.home_team_id,
            "away_team_id": r.away_team_id,
            "home_xg": r.home_xg,
            "away_xg": r.away_xg,
            "kickoff_time": r.kickoff_utc,
        }
        for r in records
        if r.match_id != exclude_match_id and r.xg_knowledge_time <= decision_time
    ]
    return pd.DataFrame(rows, columns=["home_team_id", "away_team_id", "home_xg", "away_xg", "kickoff_time"])


class RealFittedPredictor(Protocol):
    def predict(self, home_team_id: int, away_team_id: int) -> tuple[float, float, float]: ...


@dataclass(frozen=True)
class RealModelConfig:
    name: str
    # (goals_train_df, xg_train_df, decision_time) -> objet expose predict(home,away).
    # Un modele qui n'utilise pas l'un des deux df l'ignore simplement -
    # interface unifiee pour eviter deux boucles de walk-forward paralleles.
    fit: Callable[[pd.DataFrame, pd.DataFrame, datetime], RealFittedPredictor]
    # Nombre minimal de matchs requis dans le(s) df utilise(s) par ce
    # modele avant de tenter fit() - permet a XGModel de ne pas etre
    # entraine avant qu'assez de xG soit disponible, independamment du
    # nombre de scores reels deja connus (les deux flux ont des delais
    # differents, voir avertissement en tete de module).
    min_train_matches: int = 1


@dataclass(frozen=True)
class RealMatchEvaluation:
    match_id: str
    league: str
    decision_time: datetime
    home_team_id: int
    away_team_id: int
    home_goals: int
    away_goals: int
    outcome: int
    predictions: dict[str, tuple[float, float, float] | None] = field(default_factory=dict)


def run_real_data_walk_forward(
    records: list[RealMatchRecord],
    eval_match_ids: list[str],
    decision_offset_hours: float,
    model_configs: list[RealModelConfig],
) -> list[RealMatchEvaluation]:
    by_id = {r.match_id: r for r in records}
    eval_records = sorted((by_id[mid] for mid in eval_match_ids), key=lambda r: r.kickoff_utc)

    evaluations: list[RealMatchEvaluation] = []
    for r in eval_records:
        decision_time = r.kickoff_utc - timedelta(hours=decision_offset_hours)
        goals_df = _goals_train_df(records, decision_time, exclude_match_id=r.match_id)
        xg_df = _xg_train_df(records, decision_time, exclude_match_id=r.match_id)

        predictions: dict[str, tuple[float, float, float] | None] = {}
        for cfg in model_configs:
            relevant_len = max(len(goals_df), len(xg_df)) if cfg.min_train_matches else 0
            # Chaque config decide elle-meme, via son propre df, si elle a
            # assez de donnees - on ne bloque tout le monde que si NI les
            # buts NI le xG n'atteignent le minimum (garde-fou large,
            # le vrai controle se fait dans le fit() de chaque modele).
            if len(goals_df) < cfg.min_train_matches and len(xg_df) < cfg.min_train_matches:
                predictions[cfg.name] = None
                continue
            model = cfg.fit(goals_df, xg_df, decision_time)
            predictions[cfg.name] = model.predict(r.home_team_id, r.away_team_id)

        evaluations.append(
            RealMatchEvaluation(
                match_id=r.match_id,
                league=r.league,
                decision_time=decision_time,
                home_team_id=r.home_team_id,
                away_team_id=r.away_team_id,
                home_goals=r.home_goals,
                away_goals=r.away_goals,
                outcome=_outcome_index(r.home_goals, r.away_goals),
                predictions=predictions,
            )
        )
    return evaluations


def to_probs_and_outcomes(
    evaluations: list[RealMatchEvaluation], model_name: str
) -> tuple[np.ndarray, np.ndarray]:
    rows, outcomes = [], []
    for ev in evaluations:
        p = ev.predictions.get(model_name)
        if p is None:
            continue
        rows.append(p)
        outcomes.append(ev.outcome)
    return np.array(rows), np.array(outcomes)
