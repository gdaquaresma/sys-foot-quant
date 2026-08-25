"""Ponderation temporelle des matchs historiques (hypothese A1 du Research
Framework, docs/research_framework.md, classee "Fondation").

Trois configurations concurrentes, a comparer entre elles et contre
l'absence de ponderation lors du walk-forward :

- ``flat_weights`` : aucune decroissance (configuration de reference,
  "Poisson simple").
- ``rolling_window_weights`` : fenetre glissante en nombre de matchs
  (poids binaire 1/0).
- ``exponential_decay_weights`` : lissage exponentiel continu par
  demi-vie en jours.

Ces fonctions sont pures (aucun acces au Repository) : c'est a
l'orchestrateur (walk-forward) de calculer l'age de chaque match par
rapport a l'instant de decision et de choisir la fonction de ponderation.
"""

from __future__ import annotations

import numpy as np


def flat_weights(n: int) -> np.ndarray:
    """Aucune ponderation : tous les matchs comptent egalement."""
    return np.ones(n, dtype=float)


def exponential_decay_weights(age_days: np.ndarray, half_life_days: float) -> np.ndarray:
    """Poids = 0.5 ** (age / half_life). age=0 (match le plus recent) -> poids 1."""
    if half_life_days <= 0:
        raise ValueError("half_life_days doit etre strictement positif.")
    age = np.asarray(age_days, dtype=float)
    return np.power(0.5, age / half_life_days)


def rolling_window_weights(recency_rank: np.ndarray, window_matches: int) -> np.ndarray:
    """Poids binaire : 1 si le match fait partie des ``window_matches`` plus
    recents (rang de recence 0 = le plus recent), 0 sinon."""
    if window_matches < 1:
        raise ValueError("window_matches doit etre >= 1.")
    rank = np.asarray(recency_rank, dtype=float)
    return (rank < window_matches).astype(float)
