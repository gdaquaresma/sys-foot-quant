"""Sanite du generateur synthetique Dixon-Coles (hypothese B1) : les
scores generes avec ``dixon_coles_rho != 0.0`` suivent-ils reellement la
loi JOINTE theorique corrigee par tau(x,y;rho), et PAS un Poisson
independant (rho=0) ?

Si le premier test ci-dessous echoue, cela indique une regression du
generateur (son tirage ne suit plus tau tel qu'annonce), pas un probleme
de modelisation du Football Model - meme logique que
tests/integration/test_generator_goodness_of_fit_sanity.py, appliquee a
la loi JOINTE plutot qu'aux lois marginales. Le second test est la
contre-preuve : la meme distribution generee DOIT etre rejetee par un
Chi-Deux qui suppose (a tort) l'independance, sinon rho n'aurait aucun
effet mesurable sur l'echantillon et le premier test ne prouverait rien
de specifique a Dixon-Coles.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import chi2 as chi2_dist

from sys_foot_quant.common.config import SyntheticDataConfig
from sys_foot_quant.data_engine.synthetic.generator import (
    _BASE_AWAY_LAMBDA,
    _BASE_HOME_LAMBDA,
    _dixon_coles_score_matrix,
    generate_synthetic_dataset,
)

_RHO = -0.13
# n_matches=3000 (plutot que 900, convention stage2) : constate
# empiriquement en construisant ce test qu'a n=900, le chi-deux restreint
# aux 4 cellules bas-score ne rejette l'hypothese (a tort) independante
# qu'a p~0.07 - signal reel mais insuffisamment puissant pour une
# assertion de regression fiable. Ce constat de puissance statistique a
# ete fait AVANT de fixer le nombre de matchs du scenario de decision B1
# lui-meme (configs/stage5_dixon_coles.yaml) - voir sa note dediee.
_CONFIG = SyntheticDataConfig(
    seed=2024,
    n_teams=14,
    n_matches=3000,
    start_date="2021-08-01T00:00:00+00:00",
    days_between_matches=1.0,
    team_attack_log_std=0.35,
    team_defense_log_std=0.35,
    dixon_coles_rho=_RHO,
)

# Grille RESTREINTE aux quatre cellules bas-score cibles par tau, plus
# "autre" (5 categories). Un chi-deux sur la grille complete (ex. 4x4 +
# "autre" comme dans test_generator_goodness_of_fit_sanity.py) DILUE
# l'effet de rho sur seulement 4 cellules parmi 17 categories - observe
# empiriquement lors de la construction de ce test (chi2 non significatif
# malgre un effet reel et deja verifie unitairement sur ces 4 cellules,
# voir test_generator_dixon_coles.py). C'est la meme raison, au niveau
# diagnostic, pour laquelle le protocole de decision B1 lui-meme restreint
# Brier/log loss a ces quatre cellules plutot que d'evaluer sur l'ensemble
# des scores (voir calibration_engine.low_score_metrics).
_LOW_SCORE_CELLS = ((0, 0), (1, 0), (0, 1), (1, 1))


def _reconstruct_true_lambda_mu(dataset, config: SyntheticDataConfig):
    """Reproduit exactement le calcul interne du generateur (voir
    generate_synthetic_dataset), meme technique que
    test_generator_goodness_of_fit_sanity.py."""
    truth = dataset.true_team_strength.set_index("team_id")
    matches = dataset.matches.sort_values("match_id")

    lambdas_mus = []
    for _, m in matches.iterrows():
        i = int(m["match_id"]) - 1
        days = config.days_between_matches * i
        h, a = int(m["home_team_id"]), int(m["away_team_id"])
        attack_h = truth.loc[h, "true_attack"] * np.exp(truth.loc[h, "true_attack_drift_rate"] * days)
        defense_h = truth.loc[h, "true_defense"] * np.exp(truth.loc[h, "true_defense_drift_rate"] * days)
        attack_a = truth.loc[a, "true_attack"] * np.exp(truth.loc[a, "true_attack_drift_rate"] * days)
        defense_a = truth.loc[a, "true_defense"] * np.exp(truth.loc[a, "true_defense_drift_rate"] * days)
        lam = _BASE_HOME_LAMBDA * attack_h * defense_a
        mu = _BASE_AWAY_LAMBDA * attack_a * defense_h
        lambdas_mus.append((lam, mu))
    return lambdas_mus


def _low_score_category_label(h: int, a: int) -> str:
    pair = (h, a)
    if pair in _LOW_SCORE_CELLS:
        return f"{h}-{a}"
    return "autre"


def _chi_square_against(
    lambdas_mus: list[tuple[float, float]],
    rho_for_expected: float,
    home_goals: np.ndarray,
    away_goals: np.ndarray,
) -> tuple[float, float]:
    """Chi-deux restreint aux 4 cellules bas-score + "autre" (voir
    commentaire sur ``_LOW_SCORE_CELLS`` ci-dessus)."""
    categories = [f"{h}-{a}" for h, a in _LOW_SCORE_CELLS] + ["autre"]
    expected = {c: 0.0 for c in categories}
    observed = {c: 0 for c in categories}

    for i, (lam, mu) in enumerate(lambdas_mus):
        matrix = _dixon_coles_score_matrix(lam, mu, rho_for_expected, max_goals=15)
        in_grid_mass = 0.0
        for h, a in _LOW_SCORE_CELLS:
            p = float(matrix[h, a])
            expected[f"{h}-{a}"] += p
            in_grid_mass += p
        expected["autre"] += max(0.0, 1.0 - in_grid_mass)

        obs_cat = _low_score_category_label(int(home_goals[i]), int(away_goals[i]))
        observed[obs_cat] += 1

    statistic = sum((observed[c] - expected[c]) ** 2 / expected[c] for c in categories)
    dof = len(categories) - 1
    p_value = float(chi2_dist.sf(statistic, dof))
    return statistic, p_value


def test_generated_scores_match_dixon_coles_theoretical_distribution() -> None:
    dataset = generate_synthetic_dataset(_CONFIG)
    lambdas_mus = _reconstruct_true_lambda_mu(dataset, _CONFIG)
    results = dataset.match_results.set_index("match_id").loc[dataset.matches["match_id"]]
    home_goals = results["home_goals"].to_numpy()
    away_goals = results["away_goals"].to_numpy()

    stat_dc, p_dc = _chi_square_against(lambdas_mus, _RHO, home_goals, away_goals)
    assert p_dc > 0.5, (
        f"Les scores generes avec rho={_RHO} s'ecartent significativement de "
        f"la distribution Dixon-Coles theorique (chi2={stat_dc:.2f}, "
        f"p={p_dc:.4f}) : possible regression du generateur."
    )


def test_generated_scores_reject_plain_independent_poisson_when_rho_nonzero() -> None:
    dataset = generate_synthetic_dataset(_CONFIG)
    lambdas_mus = _reconstruct_true_lambda_mu(dataset, _CONFIG)
    results = dataset.match_results.set_index("match_id").loc[dataset.matches["match_id"]]
    home_goals = results["home_goals"].to_numpy()
    away_goals = results["away_goals"].to_numpy()

    stat_plain, p_plain = _chi_square_against(lambdas_mus, 0.0, home_goals, away_goals)
    assert p_plain < 0.01, (
        f"La distribution generee devrait etre rejetee par un Chi-Deux "
        f"qui suppose (a tort) l'independance, sinon la correction "
        f"rho={_RHO} n'aurait aucun effet mesurable sur l'echantillon "
        f"(chi2={stat_plain:.2f}, p={p_plain:.4f})."
    )
