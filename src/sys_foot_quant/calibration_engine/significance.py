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


def two_by_two_association_test(
    labels_a: np.ndarray, labels_b: np.ndarray, small_cell_threshold: int = 5
) -> dict[str, float | int | str]:
    """Test d'association entre deux variables binaires appariees sur les
    memes observations (ex : "favori pre-match" et "Over 2.5 buts" pour le
    meme match - hypothese C7, docs/research_framework.md section C7).

    Construit le tableau de contingence 2x2 (A et B, A et non-B, non-A et
    B, non-A et non-B) et retourne P(B), P(B|A), P(B|non-A), leur
    difference, un intervalle de confiance a 95% (approximation normale de
    Wald, erreur-type non regroupee - methode standard pour un intervalle
    de difference de deux proportions), et une p-value bilaterale :
    - test du Chi-deux (2x2, sans correction de continuite) si les quatre
      effectifs de cellule sont >= ``small_cell_threshold`` ;
    - test exact de Fisher sinon (effectif trop faible pour l'approximation
      asymptotique du Chi-deux).
    """
    a = np.asarray(labels_a, dtype=bool)
    b = np.asarray(labels_b, dtype=bool)
    if a.shape != b.shape:
        raise ValueError("labels_a et labels_b doivent avoir la meme taille (observations appariees).")
    n = a.size
    if n == 0:
        raise ValueError("Echantillon vide.")

    n_a, n_not_a = int(a.sum()), int((~a).sum())
    if n_a == 0 or n_not_a == 0:
        raise ValueError("Les deux groupes (A et non-A) doivent contenir au moins une observation.")

    n_a_b = int((a & b).sum())
    n_a_notb = n_a - n_a_b
    n_nota_b = int((~a & b).sum())
    n_nota_notb = n_not_a - n_nota_b

    p_b = float(b.sum()) / n
    p_b_given_a = n_a_b / n_a
    p_b_given_not_a = n_nota_b / n_not_a
    diff = p_b_given_a - p_b_given_not_a

    se = float(
        np.sqrt(
            p_b_given_a * (1 - p_b_given_a) / n_a
            + p_b_given_not_a * (1 - p_b_given_not_a) / n_not_a
        )
    )
    z_975 = 1.959963984540054
    ci_low = diff - z_975 * se
    ci_high = diff + z_975 * se

    table = [[n_a_b, n_a_notb], [n_nota_b, n_nota_notb]]
    min_cell = min(n_a_b, n_a_notb, n_nota_b, n_nota_notb)
    if min_cell < small_cell_threshold:
        _, p_value = stats.fisher_exact(table)
        test_used = "fisher_exact"
    else:
        _, p_value, _, _ = stats.chi2_contingency(table, correction=False)
        test_used = "chi2"

    return {
        "n": n,
        "n_a": n_a,
        "n_not_a": n_not_a,
        "p_b": p_b,
        "p_b_given_a": p_b_given_a,
        "p_b_given_not_a": p_b_given_not_a,
        "diff": diff,
        "ci_low": float(ci_low),
        "ci_high": float(ci_high),
        "p_value": float(p_value),
        "test_used": test_used,
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
