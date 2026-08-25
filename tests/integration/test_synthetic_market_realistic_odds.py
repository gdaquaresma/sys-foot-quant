"""Regression : le marche synthetique ne doit jamais produire de cotes
irrealistes, meme sur le scenario de derive (ou des correspondances tres
desequilibrees peuvent survenir).

Trouve lors de la validation de l'etape 3 : le Value Engine (EV brute =
probabilite x cote) amplifie un desequilibre invisible sur les metriques
bornees [0,1] de l'etape 2 (Brier/log loss) - un plancher de probabilite
de marche a ete ajoute dans le generateur (voir generator.py) precisement
pour cette raison. Ce test verrouille le plancher realiste des cotes
produites.
"""

from __future__ import annotations

from sys_foot_quant.common.config import SyntheticDataConfig
from sys_foot_quant.data_engine.synthetic.generator import generate_synthetic_dataset

_DRIFT_CONFIG = SyntheticDataConfig(
    seed=2024,
    n_teams=14,
    n_matches=900,
    start_date="2021-08-01T00:00:00+00:00",
    days_between_matches=1.0,
    team_attack_log_std=0.35,
    team_defense_log_std=0.35,
    team_attack_drift_log_std_per_day=0.0015,
    team_defense_drift_log_std_per_day=0.0015,
    market_margin=0.05,
    market_noise_concentration=40.0,
)


def test_drift_scenario_odds_stay_within_realistic_bounds() -> None:
    dataset = generate_synthetic_dataset(_DRIFT_CONFIG)
    odds = dataset.odds_snapshots["odds_value"]
    # Bornes theoriques 1/0.995 et 1/0.005, avec une marge pour l'arrondi
    # a 3 decimales applique par le generateur (round(odds_value, 3)).
    assert odds.min() >= 1.004
    assert odds.max() <= 200.001
    # Regression precise : avant le correctif, jusqu'a ~13% des lignes
    # atteignaient le plancher degenere (cote = 1 000 000).
    assert (odds > 1000).mean() < 0.01
