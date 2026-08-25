"""Tests statistiques pour comparer deux configurations de modele.

Principe du projet (voir CLAUDE du depot / docs/research_framework.md,
section G) : une amelioration de Brier score ou de log loss entre deux
configurations n'est jamais consideree acquise sur la seule comparaison
des moyennes - elle doit passer un test statistique explicite sur les
differences appariees match par match.

Deux methodes complementaires :
- ``paired_bootstrap_test`` : ne suppose aucune forme de distribution,
  methode primaire recommandee (les differences de score ne sont pas
  necessairement gaussiennes).
- ``paired_t_test`` : test parametrique classique, fourni en verification
  croisee.
"""

from __future__ import annotations

import numpy as np
from scipy import stats


def paired_bootstrap_test(
    diffs: np.ndarray, n_resamples: int = 10_000, seed: int | None = None
) -> dict[str, float]:
    """Bootstrap apparie sur un vecteur de differences (score_A - score_B).

    Retourne la moyenne observee, un intervalle de confiance a 95% par
    bootstrap percentile, et une p-value bilaterale approximee par
    inversion de l'intervalle de confiance bootstrap (proportion de
    reechantillonnages du meme signe que 0 exclu).
    """
    diffs = np.asarray(diffs, dtype=float)
    if diffs.size == 0:
        raise ValueError("diffs ne peut pas etre vide.")

    rng = np.random.default_rng(seed)
    n = diffs.size
    idx = rng.integers(0, n, size=(n_resamples, n))
    resample_means = diffs[idx].mean(axis=1)

    mean_diff = float(diffs.mean())
    ci_low, ci_high = np.percentile(resample_means, [2.5, 97.5])

    # p-value bilaterale : deux fois la proportion de reechantillonnages
    # du cote oppose a la moyenne observee (methode percentile standard).
    if mean_diff >= 0:
        p_value = 2.0 * float(np.mean(resample_means <= 0))
    else:
        p_value = 2.0 * float(np.mean(resample_means >= 0))
    p_value = min(p_value, 1.0)

    return {
        "mean_diff": mean_diff,
        "ci_low": float(ci_low),
        "ci_high": float(ci_high),
        "p_value": p_value,
    }


def two_sample_bootstrap_test(
    sample_a: np.ndarray, sample_b: np.ndarray, n_resamples: int = 10_000, seed: int | None = None
) -> dict[str, float]:
    """Bootstrap NON apparie (deux echantillons independants) sur la
    difference de moyennes (a - b).

    A utiliser quand les deux groupes compares ne portent pas sur les
    memes observations (ex : sous-groupe "calendrier charge" vs le reste,
    section E du research framework) - contrairement a
    ``paired_bootstrap_test``, qui suppose des observations appariees sur
    le MEME echantillon de matchs (deux configurations de modele evaluees
    sur les memes matchs), hypothese qui ne tient pas ici.
    """
    a = np.asarray(sample_a, dtype=float)
    b = np.asarray(sample_b, dtype=float)
    if a.size == 0 or b.size == 0:
        raise ValueError("Les deux echantillons doivent etre non vides.")

    rng = np.random.default_rng(seed)
    mean_diff = float(a.mean() - b.mean())

    idx_a = rng.integers(0, a.size, size=(n_resamples, a.size))
    idx_b = rng.integers(0, b.size, size=(n_resamples, b.size))
    resample_diffs = a[idx_a].mean(axis=1) - b[idx_b].mean(axis=1)

    ci_low, ci_high = np.percentile(resample_diffs, [2.5, 97.5])
    if mean_diff >= 0:
        p_value = 2.0 * float(np.mean(resample_diffs <= 0))
    else:
        p_value = 2.0 * float(np.mean(resample_diffs >= 0))
    p_value = min(p_value, 1.0)

    return {
        "mean_diff": mean_diff,
        "ci_low": float(ci_low),
        "ci_high": float(ci_high),
        "p_value": p_value,
    }


def paired_t_test(diffs: np.ndarray) -> dict[str, float]:
    """Test t apparie classique (test t a un echantillon sur les
    differences), fourni en verification croisee du bootstrap."""
    diffs = np.asarray(diffs, dtype=float)
    if diffs.size < 2:
        raise ValueError("paired_t_test necessite au moins 2 observations.")
    if np.std(diffs) == 0:
        # Cas degenere : les deux configurations produisent des scores
        # identiques sur chaque match, la variance est nulle et le test t
        # (division par l'erreur standard) est indefini. Aucune difference
        # possible par construction.
        return {"t_stat": 0.0, "p_value": 1.0}
    t_stat, p_value = stats.ttest_1samp(diffs, popmean=0.0)
    return {"t_stat": float(t_stat), "p_value": float(p_value)}
