"""Validation par simulation : l'estimateur retrouve-t-il un signal connu ?

Principe (voir docs/research_framework.md) : avant de faire confiance a un
estimateur sur des donnees reelles, on verifie qu'il retrouve correctement
des parametres connus sur des donnees simulees ou la "verite" est
disponible. Le generateur synthetique de l'etape 1 a ete etendu (etape 2)
pour simuler une vraie force d'attaque/defense par equipe
(``true_team_strength``), precisement pour ce test.
"""

from __future__ import annotations

import numpy as np

from sys_foot_quant.common.config import SyntheticDataConfig
from sys_foot_quant.data_engine.synthetic.generator import generate_synthetic_dataset
from sys_foot_quant.football_model.poisson import PoissonModel

_CONFIG = SyntheticDataConfig(
    seed=123,
    n_teams=12,
    n_matches=700,
    start_date="2022-08-01T00:00:00+00:00",
    days_between_matches=1.0,
    team_attack_log_std=0.45,
    team_defense_log_std=0.45,
)


def test_poisson_model_recovers_simulated_attack_and_defense() -> None:
    dataset = generate_synthetic_dataset(_CONFIG)
    train_df = dataset.matches.merge(dataset.match_results, on="match_id")[
        ["home_team_id", "away_team_id", "home_goals", "away_goals", "kickoff_time"]
    ]

    model = PoissonModel().fit(train_df)

    truth = dataset.true_team_strength.set_index("team_id")
    fitted_attack = np.array([model.attack_[t] for t in truth.index])
    fitted_defense = np.array([model.defense_[t] for t in truth.index])
    true_attack = truth["true_attack"].to_numpy()
    true_defense = truth["true_defense"].to_numpy()

    corr_attack = np.corrcoef(fitted_attack, true_attack)[0, 1]
    corr_defense = np.corrcoef(fitted_defense, true_defense)[0, 1]

    assert corr_attack > 0.6, f"Correlation attaque trop faible : {corr_attack:.3f}"
    assert corr_defense > 0.6, f"Correlation defense trop faible : {corr_defense:.3f}"
