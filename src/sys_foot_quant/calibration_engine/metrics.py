"""Brier score et log loss multi-classes pour un marche a 3 issues (1N2).

Convention : ``probs`` est un tableau (N, K) de probabilites predites par
match (K=3 : domicile/nul/exterieur), ``outcomes`` un tableau (N,) d'indices
de classe reellement observee (0=domicile, 1=nul, 2=exterieur).
"""

from __future__ import annotations

import numpy as np

_LOG_LOSS_EPS = 1e-12


def _validate(probs: np.ndarray, outcomes: np.ndarray) -> None:
    if probs.shape[0] != outcomes.shape[0]:
        raise ValueError(
            f"probs et outcomes doivent avoir le meme nombre de lignes "
            f"({probs.shape[0]} vs {outcomes.shape[0]})."
        )
    row_sums = probs.sum(axis=1)
    if not np.allclose(row_sums, 1.0, atol=1e-6):
        raise ValueError("Chaque ligne de probs doit sommer a 1.0.")


def brier_score(probs: np.ndarray, outcomes: np.ndarray) -> float:
    """Brier score multi-classes (formulation originale de Brier, 1950) :
    moyenne sur les matchs de la somme, sur les K categories, de
    (probabilite predite - indicatrice observee)^2.

    Borne dans [0, 2] pour un marche a 3 issues. 0 = prediction parfaite.
    """
    _validate(probs, outcomes)
    n, k = probs.shape
    one_hot = np.zeros((n, k))
    one_hot[np.arange(n), outcomes] = 1.0
    return float(np.mean(np.sum((probs - one_hot) ** 2, axis=1)))


def log_loss(probs: np.ndarray, outcomes: np.ndarray) -> float:
    """Log loss (negative log-likelihood) moyenne, avec clipping pour
    eviter log(0) sur une probabilite predite exactement nulle."""
    _validate(probs, outcomes)
    n = probs.shape[0]
    p_true = probs[np.arange(n), outcomes]
    p_true_clipped = np.clip(p_true, _LOG_LOSS_EPS, 1.0)
    return float(-np.mean(np.log(p_true_clipped)))
