"""Diagnostic de Chi-Deux : la distribution des scores predite par le
modele est-elle compatible avec la distribution des scores observee ?

Hypothese A4 du Research Framework (docs/research_framework.md, classee
"Fondation") : test d'adequation de Pearson entre la distribution
empirique des scores et la distribution theorique implicite du modele.

USAGE IMPORTANT (voir aussi les limites ci-dessous) : ce test est un
DIAGNOSTIC COMPLEMENTAIRE de la forme fonctionnelle du modele (detecte
par exemple une sous-representation des scores 0-0/1-1 caracteristique
d'un Poisson sans correction d'interdependance, cf. Dixon-Coles). Ce
n'est PAS un critere d'acceptation ou de rejet du modele a lui seul :
Brier score et log loss hors echantillon (calibration_engine.metrics)
restent les criteres de decision. Un modele peut avoir un bon Brier/log
loss et neanmoins echouer ce test (mauvaise forme mais bon rang), ou
inversement.

Limites documentees :

1. Puisque chaque match a son propre (lambda, mu) predit par le modele
   (contrairement au test de Pearson classique sur UNE distribution
   theorique fixe), l'effectif "attendu" par categorie est la SOMME, sur
   tous les matchs evalues, de la probabilite que ce match tombe dans
   cette categorie. C'est la maniere standard d'agreger un test
   d'adequation sur des observations heterogenes, mais ce n'est valide
   comme approximation Chi-Deux que si les probabilites par match ne
   sont pas trop dispersees a l'interieur de chaque categorie - non
   verifie explicitement ici.
2. Regle empirique usuelle : la statistique Chi-Deux n'est une
   approximation fiable que si l'effectif attendu de chaque categorie est
   >= 5. Avec un echantillon de test modeste et des categories de score
   rares, cette condition peut etre violee - ``is_valid`` l'indique
   explicitement, et le nombre de degres de liberte n'est PAS ajuste
   automatiquement en fusionnant les categories creuses.
3. Le nombre de degres de liberte utilise (``n_categories - 1``) ne
   corrige PAS le nombre de parametres estimes a partir des memes
   donnees (attaque/defense/HFA sont estimes sur l'historique
   d'entrainement, pas sur l'echantillon de test lui-meme si utilise en
   walk-forward - donc cette simplification est raisonnable en usage
   hors-echantillon strict, mais resterait optimiste si le test etait
   applique sur les donnees d'entrainement elles-memes).
4. Ce test verifie la FORME de la distribution des scores (independance
   Poisson, structure des scores bas/hauts), pas la calibration des
   probabilites d'issue 1N2 elles-memes (pour cela, voir
   calibration_engine.reliability).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import chi2 as chi2_dist
from scipy.stats import poisson as scipy_poisson

_MIN_EXPECTED_COUNT = 5.0


@dataclass(frozen=True)
class GoodnessOfFitResult:
    statistic: float
    p_value: float
    dof: int
    n_matches: int
    min_expected_count: float
    is_valid: bool  # False si au moins une categorie a un effectif attendu < 5
    table: pd.DataFrame


def _category_label(h: int, a: int, max_goals_per_side: int) -> str:
    if h > max_goals_per_side or a > max_goals_per_side:
        return "autre"
    return f"{h}-{a}"


def poisson_goodness_of_fit(
    predicted_lambda_mu: list[tuple[float, float]],
    observed_home_goals: np.ndarray,
    observed_away_goals: np.ndarray,
    max_goals_per_side: int = 3,
) -> GoodnessOfFitResult:
    n = len(predicted_lambda_mu)
    if n == 0:
        raise ValueError("predicted_lambda_mu ne peut pas etre vide.")
    observed_home_goals = np.asarray(observed_home_goals, dtype=int)
    observed_away_goals = np.asarray(observed_away_goals, dtype=int)
    if observed_home_goals.shape[0] != n or observed_away_goals.shape[0] != n:
        raise ValueError("predicted_lambda_mu et les buts observes doivent avoir la meme longueur.")
    if max_goals_per_side < 0:
        raise ValueError("max_goals_per_side doit etre >= 0.")

    grid = list(range(max_goals_per_side + 1))
    categories = [f"{h}-{a}" for h in grid for a in grid] + ["autre"]
    expected = {cat: 0.0 for cat in categories}
    observed = {cat: 0 for cat in categories}

    for i in range(n):
        lam, mu = predicted_lambda_mu[i]
        p_h = scipy_poisson.pmf(grid, lam)
        p_a = scipy_poisson.pmf(grid, mu)
        in_grid_mass = 0.0
        for hi, h in enumerate(grid):
            for ai, a in enumerate(grid):
                p = float(p_h[hi] * p_a[ai])
                expected[f"{h}-{a}"] += p
                in_grid_mass += p
        expected["autre"] += max(0.0, 1.0 - in_grid_mass)

        obs_cat = _category_label(
            int(observed_home_goals[i]), int(observed_away_goals[i]), max_goals_per_side
        )
        observed[obs_cat] += 1

    table = pd.DataFrame(
        {
            "category": categories,
            "observed": [observed[c] for c in categories],
            "expected": [expected[c] for c in categories],
        }
    )

    statistic = float(
        np.sum((table["observed"] - table["expected"]) ** 2 / table["expected"])
    )
    dof = len(categories) - 1
    p_value = float(chi2_dist.sf(statistic, dof))
    min_expected = float(table["expected"].min())

    return GoodnessOfFitResult(
        statistic=statistic,
        p_value=p_value,
        dof=dof,
        n_matches=n,
        min_expected_count=min_expected,
        is_valid=min_expected >= _MIN_EXPECTED_COUNT,
        table=table,
    )


def contribution_table(result: GoodnessOfFitResult) -> pd.DataFrame:
    """Decompose la statistique Chi-Deux par categorie, triee par
    contribution decroissante : ``(observe - attendu)^2 / attendu``.

    Sert a diagnostiquer QUELLES categories de score expliquent
    principalement un Chi-Deux eleve, avant toute conclusion sur la cause
    (modele mal specifie vs anomalie du generateur). Voir
    docs/research_framework.md et le rapport de diagnostic associe : sur
    le scenario de derive, un chi2 eleve pour ``poisson_simple`` s'est
    revele explique par un exces simultane de scores 0-0 et de scores
    eleves (signature classique de sous-dispersion du modele quand la
    vraie force des equipes est plus heterogene, a un instant donne, que
    ce que le modele - qui ne suit pas la derive - parvient a capturer).
    """
    table = result.table.copy()
    table["contribution"] = (table["observed"] - table["expected"]) ** 2 / table["expected"]
    table["contribution_share"] = (
        table["contribution"] / result.statistic if result.statistic > 0 else 0.0
    )
    return table.sort_values("contribution", ascending=False).reset_index(drop=True)
