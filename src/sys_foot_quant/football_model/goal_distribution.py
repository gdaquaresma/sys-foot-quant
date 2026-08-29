"""Distribution de buts et probabilites Over/Under derivees d'UNE SEULE
matrice de score - brique VALIDEE SCIENTIFIQUEMENT (E7, section R de
docs/research_framework.md ; voir aussi docs/final_engine_specification.md
section 6).

Portage VERBATIM (aucune nouvelle logique, aucune reinterpretation) des
fonctions pures deja testees dans
``scripts/run_stage15_e7_total_goals_distribution.py`` (elles-memes
identiques a celles de ``scripts/run_stage8_diagnostic_total_goals_over_under.py``,
verifie par E7 section 6 - "reproduction exacte verifiee"). Promues ici de
``scripts/`` vers ``src/`` pour etre reutilisables par le moteur de
production (docs/final_engine_specification.md, section 1) sans dependre
de l'import dynamique reserve aux scripts de recherche.

Propriete structurelle garantie PAR CONSTRUCTION (jamais par verification
a posteriori) : ``total_goals_distribution`` et ``over_under_probs`` sont
toutes deux calculees a partir de la MEME matrice ``matrix`` - la
monotonicite ``P(O0.5) >= P(O1.5) >= P(O2.5) >= P(O3.5) >= P(O4.5)`` en
decoule automatiquement (``totals > t`` est un ensemble decroissant en
``t``). Les fonctions de controle ci-dessous verifient cette propriete en
continu (non-regression), elles ne la creent pas.
"""

from __future__ import annotations

import numpy as np

# Seuils Over/Under officiels du moteur (docs/final_engine_specification.md
# section 6/7) - 0.5/1.5/2.5/3.5/4.5, exactement ceux utilises par E11
# (``scripts/run_stage20_e11_probability_reliability_mapping.py::_THRESHOLDS``).
DEFAULT_OU_THRESHOLDS: tuple[float, ...] = (0.5, 1.5, 2.5, 3.5, 4.5)

# 0..5 buts puis "6+" - identique a E7/E8 (``_MAX_BUCKET = 6``).
DEFAULT_MAX_BUCKET = 6


def over_under_probs(
    matrix: np.ndarray, thresholds: tuple[float, ...] = DEFAULT_OU_THRESHOLDS
) -> dict[float, float]:
    """P(total > seuil) pour chaque seuil, a partir d'une matrice de score
    deja normalisee - fonction pure, aucun etat. Identique a
    ``run_stage15_e7_total_goals_distribution.over_under_probs``."""
    n = matrix.shape[0]
    totals = np.add.outer(np.arange(n), np.arange(n))
    return {t: float(matrix[totals > t].sum()) for t in thresholds}


def total_goals_distribution(matrix: np.ndarray, max_bucket: int = DEFAULT_MAX_BUCKET) -> np.ndarray:
    """P(total=0), P(total=1), ..., P(total=max_bucket-1), P(total>=max_bucket).
    Identique a ``run_stage15_e7_total_goals_distribution.total_goals_distribution``."""
    n = matrix.shape[0]
    totals = np.add.outer(np.arange(n), np.arange(n))
    out = np.zeros(max_bucket + 1)
    for k in range(max_bucket):
        out[k] = matrix[totals == k].sum()
    out[max_bucket] = matrix[totals >= max_bucket].sum()
    return out


def asian_handicap_probabilities(matrix: np.ndarray, handicap: float) -> dict[str, float]:
    """P(Home)/P(Push)/P(Away) pour une ligne de handicap asiatique
    ``handicap`` (convention domicile : negatif favorise le domicile),
    a partir d'UNE SEULE matrice de score deja corrigee - meme principe
    que ``over_under_probs``, mais sur la difference de buts plutot que
    le total (Phase H, docs/ah_experiment_specification.md section 2.3).

    Ligne PROPRE (entiere ou demi-entiere, ``handicap % 0.5 == 0``) :
    partition exacte de la matrice sur ``i - j + handicap`` positif/nul/
    negatif - les trois valeurs somment exactement a 1.

    Ligne QUART (``handicap % 0.5 in {0.25, 0.75}``) : PAS une ligne
    unique - par definition du handicap asiatique (jamais une
    approximation), une mise a quart de ligne est divisee en deux
    demi-mises egales sur les deux lignes propres adjacentes
    ``handicap - 0.25``/``handicap + 0.25``. La probabilite retournee est
    la moyenne simple (poids 0.5/0.5) des deux distributions propres -
    demontre, terme a terme sur chaque resultat reel possible, identique
    a la fraction de mise reellement remboursee/perdue/gagnee (voir
    section 2.3 du protocole et les tests dedies)."""
    frac = abs(handicap) % 1.0
    is_quarter = min(abs(frac - 0.25), abs(frac - 0.75)) < 1e-9

    if is_quarter:
        lo = asian_handicap_probabilities(matrix, handicap - 0.25)
        hi = asian_handicap_probabilities(matrix, handicap + 0.25)
        return {k: 0.5 * lo[k] + 0.5 * hi[k] for k in ("home", "push", "away")}

    n = matrix.shape[0]
    diffs = np.subtract.outer(np.arange(n), np.arange(n))
    margin = diffs + handicap
    return {
        "home": float(matrix[margin > 1e-9].sum()),
        "push": float(matrix[np.abs(margin) <= 1e-9].sum()),
        "away": float(matrix[margin < -1e-9].sum()),
    }


def check_distribution_validity(dist: np.ndarray, atol: float = 1e-9) -> dict:
    """Identique a ``run_stage15_e7_total_goals_distribution.check_distribution_validity``."""
    return {
        "all_non_negative": bool(np.all(dist >= -atol)),
        "sums_to_one": bool(abs(float(dist.sum()) - 1.0) < 1e-6),
    }


def check_over_under_monotonic(ou: dict[float, float]) -> bool:
    """P(Over t1) >= P(Over t2) pour t1 < t2 - doit toujours etre vrai par
    construction quand ``ou`` provient d'une seule matrice. Identique a
    ``run_stage15_e7_total_goals_distribution.check_over_under_monotonic``."""
    sorted_thresholds = sorted(ou)
    values = [ou[t] for t in sorted_thresholds]
    return all(values[i] >= values[i + 1] - 1e-9 for i in range(len(values) - 1))


def check_over_under_matches_distribution(
    dist: np.ndarray, ou: dict[float, float], atol: float = 1e-6
) -> bool:
    """P(Over t) doit exactement egaler sum(P(total>=k_min)) issu de la MEME
    distribution. Identique a
    ``run_stage15_e7_total_goals_distribution.check_over_under_matches_distribution``."""
    ok = True
    for t, p in ou.items():
        k_min = int(np.floor(t)) + 1  # ex: Over 2.5 -> total >= 3
        if k_min >= len(dist):
            continue  # seuil au-dela du bucket agrege - rien a comparer (jamais rencontre avec les seuils officiels)
        expected = float(dist[k_min:].sum())
        ok = ok and abs(expected - p) < atol
    return ok
