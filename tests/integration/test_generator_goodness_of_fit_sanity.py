"""Test de sanite du generateur synthetique : les buts qu'il produit
sont-ils reellement issus d'un processus de Poisson avec les parametres
(lambda, mu) reellement simules (y compris derive) ?

Contexte (diagnostic mene suite au rapport de correction de l'etape 2) :
le diagnostic de Chi-Deux a signale un mauvais ajustement (chi2=54.66,
p<0.0001) pour ``poisson_simple`` sur le scenario de derive. Ce test
verifie explicitement que la cause n'est PAS un defaut du generateur : en
utilisant les VRAIS lambda/mu (reconstruits a partir de
``true_team_strength`` et de la derive connue, exactement comme le fait
le generateur en interne), le Chi-Deux ne doit PAS rejeter l'adequation.

Si ce test echoue un jour, cela indique une regression dans le
generateur (ses tirages ne suivraient plus la loi de Poisson annoncee),
PAS un probleme de modelisation Football Model.
"""

from __future__ import annotations

import numpy as np

from sys_foot_quant.calibration_engine.goodness_of_fit import poisson_goodness_of_fit
from sys_foot_quant.common.config import SyntheticDataConfig
from sys_foot_quant.data_engine.synthetic.generator import (
    _BASE_AWAY_LAMBDA,
    _BASE_HOME_LAMBDA,
    generate_synthetic_dataset,
)

_CONFIG = SyntheticDataConfig(
    seed=2024,
    n_teams=14,
    n_matches=900,
    start_date="2021-08-01T00:00:00+00:00",
    days_between_matches=1.0,
    team_attack_log_std=0.35,
    team_defense_log_std=0.35,
    team_attack_drift_log_std_per_day=0.0015,
    team_defense_drift_log_std_per_day=0.0015,
)


def _reconstruct_true_lambda_mu(dataset, config: SyntheticDataConfig):
    """Reproduit exactement le calcul interne du generateur (voir
    generate_synthetic_dataset) a partir de ``true_team_strength`` seule,
    sans acceder a aucun etat interne prive du generateur autre que les
    deux constantes de base (deliberement importees, pas redefinies, pour
    eviter toute divergence silencieuse entre le test et le generateur)."""
    truth = dataset.true_team_strength.set_index("team_id")
    matches = dataset.matches.sort_values("match_id")

    lambdas_mus = []
    for _, m in matches.iterrows():
        i = int(m["match_id"]) - 1  # match_id = i + 1 dans le generateur
        days = config.days_between_matches * i
        h, a = int(m["home_team_id"]), int(m["away_team_id"])
        attack_h = truth.loc[h, "true_attack"] * np.exp(
            truth.loc[h, "true_attack_drift_rate"] * days
        )
        defense_h = truth.loc[h, "true_defense"] * np.exp(
            truth.loc[h, "true_defense_drift_rate"] * days
        )
        attack_a = truth.loc[a, "true_attack"] * np.exp(
            truth.loc[a, "true_attack_drift_rate"] * days
        )
        defense_a = truth.loc[a, "true_defense"] * np.exp(
            truth.loc[a, "true_defense_drift_rate"] * days
        )
        lam = _BASE_HOME_LAMBDA * attack_h * defense_a
        mu = _BASE_AWAY_LAMBDA * attack_a * defense_h
        lambdas_mus.append((lam, mu))
    return lambdas_mus


def test_generated_goals_are_not_rejected_against_their_true_lambda_mu() -> None:
    dataset = generate_synthetic_dataset(_CONFIG)
    lambdas_mus = _reconstruct_true_lambda_mu(dataset, _CONFIG)

    results = dataset.match_results.set_index("match_id").loc[dataset.matches["match_id"]]
    home_goals = results["home_goals"].to_numpy()
    away_goals = results["away_goals"].to_numpy()

    result = poisson_goodness_of_fit(lambdas_mus, home_goals, away_goals, max_goals_per_side=3)

    # Seuil genereux (observe empiriquement : p=0.997) : on ne cherche pas
    # a figer une valeur exacte, seulement a detecter une vraie regression.
    assert result.p_value > 0.5, (
        f"Les buts generes s'ecartent significativement de la loi de "
        f"Poisson theorique (chi2={result.statistic:.2f}, p={result.p_value:.4f}) "
        f": possible regression dans le generateur synthetique."
    )
