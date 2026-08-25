"""Verifie le mecanisme de derive temporelle de la force d'equipe, ajoute
pour tester l'hypothese A1 (ponderation temporelle) sur un scenario ou une
derive reelle existe - par opposition au scenario de controle a force
constante (tests/integration/test_poisson_recovers_true_strength.py).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from sys_foot_quant.common.config import SyntheticDataConfig
from sys_foot_quant.data_engine.synthetic.generator import generate_synthetic_dataset


def test_zero_drift_std_gives_exactly_zero_drift_rate() -> None:
    cfg = SyntheticDataConfig(
        seed=1,
        n_teams=6,
        n_matches=30,
        start_date="2022-01-01T00:00:00+00:00",
        team_attack_drift_log_std_per_day=0.0,
        team_defense_drift_log_std_per_day=0.0,
    )
    dataset = generate_synthetic_dataset(cfg)
    assert (dataset.true_team_strength["true_attack_drift_rate"] == 0.0).all()
    assert (dataset.true_team_strength["true_defense_drift_rate"] == 0.0).all()


def test_nonzero_drift_std_produces_nonzero_drift_rates() -> None:
    cfg = SyntheticDataConfig(
        seed=1,
        n_teams=6,
        n_matches=30,
        start_date="2022-01-01T00:00:00+00:00",
        team_attack_drift_log_std_per_day=0.002,
        team_defense_drift_log_std_per_day=0.002,
    )
    dataset = generate_synthetic_dataset(cfg)
    assert (dataset.true_team_strength["true_attack_drift_rate"] != 0.0).any()


def _team_scoring_rate(df: pd.DataFrame, team_id: int) -> float:
    home_goals = df.loc[df["home_team_id"] == team_id, "home_goals"]
    away_goals = df.loc[df["away_team_id"] == team_id, "away_goals"]
    all_goals = pd.concat([home_goals, away_goals])
    return float(all_goals.mean()) if len(all_goals) else float("nan")


def test_realized_scoring_rate_drifts_in_the_configured_direction() -> None:
    # Derive suffisamment marquee pour etre detectable sur un echantillon
    # modeste, mais toujours "connue et reproductible" (meme seed => meme
    # derive exacte).
    cfg = SyntheticDataConfig(
        seed=5,
        n_teams=10,
        n_matches=900,
        start_date="2022-01-01T00:00:00+00:00",
        days_between_matches=1.0,
        team_attack_log_std=0.2,
        team_defense_log_std=0.2,
        team_attack_drift_log_std_per_day=0.0025,
        team_defense_drift_log_std_per_day=0.0025,
    )
    dataset = generate_synthetic_dataset(cfg)
    truth = dataset.true_team_strength.set_index("team_id")

    merged = dataset.matches.merge(dataset.match_results, on="match_id").sort_values(
        "kickoff_time"
    )
    n = len(merged)
    first_third = merged.iloc[: n // 3]
    last_third = merged.iloc[-(n // 3) :]

    deltas = []
    for t in truth.index:
        early = _team_scoring_rate(first_third, t)
        late = _team_scoring_rate(last_third, t)
        deltas.append(late - early)

    deltas = np.array(deltas)
    corr = np.corrcoef(deltas, truth["true_attack_drift_rate"])[0, 1]
    assert corr > 0.4, (
        f"La derive realisee (buts marques : fin de periode - debut) ne "
        f"correle pas assez avec le taux de derive configure (corr={corr:.3f})."
    )
