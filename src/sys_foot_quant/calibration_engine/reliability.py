"""Donnees de reliability diagram (courbe de calibration).

Reduit un probleme multi-classes a une analyse "one-vs-rest" : pour une
categorie donnee (ex: victoire domicile), on regroupe les observations par
tranche de probabilite predite et on compare la probabilite predite
moyenne a la frequence reellement observee dans chaque tranche. Un modele
parfaitement calibre a une frequence observee egale a la probabilite
predite dans chaque tranche.

Ce module calcule uniquement les donnees (DataFrame) ; le rendu graphique
relevera d'une etape ulterieure de reporting.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def reliability_bins(probs: np.ndarray, outcomes: np.ndarray, n_bins: int = 10) -> pd.DataFrame:
    """``probs`` : probabilite predite pour UNE categorie (ex: domicile), par match.
    ``outcomes`` : indicatrice binaire (0/1) de la realisation de cette categorie.

    Retourne un DataFrame avec, par tranche : bornes, probabilite predite
    moyenne, frequence observee, nombre d'observations.
    """
    probs = np.asarray(probs, dtype=float)
    outcomes = np.asarray(outcomes, dtype=float)
    if probs.shape[0] != outcomes.shape[0]:
        raise ValueError("probs et outcomes doivent avoir la meme longueur.")
    if probs.size and ((probs < 0).any() or (probs > 1).any()):
        raise ValueError("Toutes les probabilites doivent etre dans [0, 1].")
    if n_bins < 1:
        raise ValueError("n_bins doit etre >= 1.")

    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_idx = np.clip(np.digitize(probs, edges[1:-1], right=True), 0, n_bins - 1)

    rows = []
    for b in range(n_bins):
        mask = bin_idx == b
        count = int(mask.sum())
        rows.append(
            {
                "bin_lo": edges[b],
                "bin_hi": edges[b + 1],
                "mean_predicted": float(probs[mask].mean()) if count else float("nan"),
                "observed_frequency": float(outcomes[mask].mean()) if count else float("nan"),
                "count": count,
            }
        )
    return pd.DataFrame(rows)
