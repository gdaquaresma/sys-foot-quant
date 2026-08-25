"""Generation des probabilites de score et d'issue 1N2 a partir de (lambda, mu).

Poisson simple : les buts marques par l'equipe a domicile et par l'equipe
a l'exterieur sont modelises comme deux variables de Poisson independantes.
Aucune correction d'interdependance (Dixon-Coles) n'est appliquee ici -
c'est explicitement hors perimetre de l'etape 2 (voir docs/research_framework.md,
section B1).
"""

from __future__ import annotations

import numpy as np
from scipy.stats import poisson


def score_matrix(lam: float, mu: float, max_goals: int = 15) -> np.ndarray:
    """Matrice P(X=x, Y=y) pour x, y dans [0, max_goals], X et Y independants.

    La troncature a ``max_goals`` laisse une masse de probabilite residuelle
    negligeable pour des lambda/mu realistes en football (< 1e-6 pour
    max_goals=15 et lambda/mu <= 6).
    """
    if lam <= 0 or mu <= 0:
        raise ValueError(f"lambda et mu doivent etre strictement positifs (lam={lam}, mu={mu}).")
    goals = np.arange(0, max_goals + 1)
    p_home = poisson.pmf(goals, lam)
    p_away = poisson.pmf(goals, mu)
    return np.outer(p_home, p_away)


def outcome_probabilities(matrix: np.ndarray) -> tuple[float, float, float]:
    """(P(victoire domicile), P(nul), P(victoire exterieur)) a partir de la matrice de score."""
    n = matrix.shape[0]
    rows, cols = np.indices((n, n))
    home_win = matrix[rows > cols].sum()
    draw = matrix[rows == cols].sum()
    away_win = matrix[rows < cols].sum()
    return float(home_win), float(draw), float(away_win)
