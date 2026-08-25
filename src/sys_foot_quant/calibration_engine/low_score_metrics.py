"""Metriques Brier/log loss restreintes au sous-ensemble bas-score (0-0,
1-0, 0-1, 1-1), protocole de test de l'hypothese B1 (Dixon-Coles) du
Research Framework (docs/research_framework.md, section B1 ; voir aussi
docs/decisions/0005-protocole-generateur-dixon-coles.md).

Principe : la correction tau de Dixon-Coles ne modifie QUE la masse de
probabilite jointe sur ces quatre cellules - c'est donc precisement le
sous-ensemble ou un gain, s'il existe, doit apparaitre. Evaluer
Brier/log loss sur l'ensemble complet des scores (ou sur le triplet
d'issue 1N2 deja utilise aux etapes 2-5, rapporte separement comme metrique
"globale") diluerait un eventuel signal localise dans une moyenne dominee
par les matchs hors de ce sous-ensemble.

Construction en 5 categories (les 4 cellules bas-score + "autre" = 1 moins
leur somme) plutot qu'en 4 categories renormalisees sur le seul
sous-ensemble : preserve l'information sur la masse de probabilite
ABSOLUE que le modele attribue au fait meme d'etre un score bas - c'est
precisement ce que tau deplace, pas seulement le poids RELATIF entre les
4 cellules une fois qu'on sait deja qu'on est dans l'une d'elles.
Reutilise directement ``calibration_engine.metrics.brier_score``/``log_loss``
(deja testes) : aucune nouvelle formule de score n'est introduite, cette
categorisation a 5 classes est juste une facon de leur presenter les
donnees.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

LOW_SCORE_CELLS: tuple[tuple[int, int], ...] = ((0, 0), (1, 0), (0, 1), (1, 1))
LOW_SCORE_LABELS: tuple[str, ...] = ("0-0", "1-0", "0-1", "1-1")
N_LOW_SCORE_CATEGORIES = len(LOW_SCORE_CELLS) + 1  # + "autre"


def low_score_outcome_index(home_goals: int, away_goals: int) -> int | None:
    """Index 0-3 dans LOW_SCORE_CELLS si (home_goals, away_goals) y
    figure, None sinon (le match n'appartient pas au sous-ensemble
    bas-score cible par B1)."""
    pair = (int(home_goals), int(away_goals))
    if pair in LOW_SCORE_CELLS:
        return LOW_SCORE_CELLS.index(pair)
    return None


def low_score_category_row(cell_probs: tuple[float, float, float, float]) -> np.ndarray:
    """(p00, p10, p01, p11, p_autre) a partir des 4 probabilites brutes
    issues de la distribution de score complete d'un modele (deja
    renormalisee a somme 1 sur toute la grille -
    PoissonModel/DixonColesModel.predict_low_score_probs). ``p_autre``
    capture le reste de la masse ; ecrete a 0 pour absorber un residu
    negatif de l'ordre de l'epsilon flottant (jamais un ecart
    substantiel, sinon c'est un bug du modele appelant, pas quelque chose
    a masquer ici)."""
    arr = np.asarray(cell_probs, dtype=float)
    if arr.shape != (4,):
        raise ValueError(f"cell_probs doit contenir exactement 4 valeurs, recu forme {arr.shape}.")
    other = max(0.0, 1.0 - float(arr.sum()))
    return np.concatenate([arr, [other]])


def cell_contribution_table(records: pd.DataFrame) -> pd.DataFrame:
    """Decompose les metriques agregees bas-score PAR CELLULE de score
    reellement observee.

    ``records`` : une ligne par match du sous-ensemble bas-score, colonnes
    ``cell`` (index 0-3, voir LOW_SCORE_CELLS/LOW_SCORE_LABELS),
    ``brier_a``, ``brier_b``, ``log_loss_a``, ``log_loss_b`` (scores PAR
    MATCH pour deux configurations comparees A et B - pas des moyennes
    deja agregees).

    Retourne, pour chacune des 4 cellules, l'effectif et les moyennes de
    chaque metrique pour A et B, plus la difference appariee (B - A) :
    negative => B (typiquement Dixon-Coles) fait moins d'erreur que A
    (typiquement poisson_simple) sur cette cellule precise. Meme principe
    que ``calibration_engine.goodness_of_fit.contribution_table``, adapte
    a une comparaison de deux configurations plutot qu'a un diagnostic
    d'ajustement unique.
    """
    required = {"cell", "brier_a", "brier_b", "log_loss_a", "log_loss_b"}
    missing = required - set(records.columns)
    if missing:
        raise ValueError(f"records doit contenir les colonnes {sorted(required)}, manque {sorted(missing)}.")

    rows = []
    for idx, label in enumerate(LOW_SCORE_LABELS):
        sub = records[records["cell"] == idx]
        if sub.empty:
            rows.append(
                {
                    "cell": label,
                    "n": 0,
                    "brier_a_mean": float("nan"),
                    "brier_b_mean": float("nan"),
                    "brier_diff_b_minus_a": float("nan"),
                    "log_loss_a_mean": float("nan"),
                    "log_loss_b_mean": float("nan"),
                    "log_loss_diff_b_minus_a": float("nan"),
                }
            )
            continue
        rows.append(
            {
                "cell": label,
                "n": int(len(sub)),
                "brier_a_mean": float(sub["brier_a"].mean()),
                "brier_b_mean": float(sub["brier_b"].mean()),
                "brier_diff_b_minus_a": float((sub["brier_b"] - sub["brier_a"]).mean()),
                "log_loss_a_mean": float(sub["log_loss_a"].mean()),
                "log_loss_b_mean": float(sub["log_loss_b"].mean()),
                "log_loss_diff_b_minus_a": float((sub["log_loss_b"] - sub["log_loss_a"]).mean()),
            }
        )
    return pd.DataFrame(rows)
