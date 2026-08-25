"""Regression stricte : les scenarios EXISTANTS (deja valides aux etapes
1-5) doivent produire des donnees BIT-IDENTIQUES apres l'ajout du
parametre ``dixon_coles_rho`` (hypothese B1). Les hash ci-dessous ont ete
captures a partir du generateur AVANT toute modification pour B1 (meme
code que celui deja valide aux etapes 1-5), sur les trois configurations
de reference du projet.

Un echec de ce test signifie une regression reelle introduite par les
changements du generateur pour B1 - c'est le garde-fou le plus direct
possible contre "ne modifie aucun resultat des etapes 1 a 4"."""

from __future__ import annotations

import hashlib

import numpy as np

from sys_foot_quant.common.config import SyntheticDataConfig
from sys_foot_quant.data_engine.synthetic.generator import generate_synthetic_dataset


def _dataset_digest(cfg: SyntheticDataConfig) -> str:
    dataset = generate_synthetic_dataset(cfg)
    home_goals = dataset.match_results.sort_values("match_id")["home_goals"].to_numpy()
    away_goals = dataset.match_results.sort_values("match_id")["away_goals"].to_numpy()
    odds = dataset.odds_snapshots.sort_values(["match_id", "knowledge_time", "selection"])[
        "odds_value"
    ].to_numpy()

    digest = hashlib.sha256()
    digest.update(home_goals.tobytes())
    digest.update(away_goals.tobytes())
    digest.update(np.round(odds, 3).tobytes())
    return digest.hexdigest()


# Hash captures directement sur le generateur AVANT toute modification
# pour B1 (dernier etat valide aux etapes 1-5), avant d'ecrire la moindre
# ligne de code pour cette hypothese.
_GOLDEN_HASHES = {
    "small_default": (
        SyntheticDataConfig(
            seed=42,
            n_teams=6,
            n_matches=20,
            start_date="2024-08-01T00:00:00+00:00",
            days_between_matches=1.5,
            result_confirmation_delay_hours=2.0,
            fixture_announcement_days_before=14.0,
            odds_snapshot_offsets_hours=[72.0, 24.0, 1.0],
        ),
        "9cf642db453fe2f51dc3f9d777604cb099dd9a339e4c340446399647fb6c7fa0",
    ),
    "stage2_constant": (
        SyntheticDataConfig(
            seed=2024,
            n_teams=14,
            n_matches=900,
            start_date="2021-08-01T00:00:00+00:00",
            days_between_matches=1.0,
            result_confirmation_delay_hours=2.0,
            fixture_announcement_days_before=14.0,
            odds_snapshot_offsets_hours=[72.0, 24.0, 1.0],
            team_attack_log_std=0.35,
            team_defense_log_std=0.35,
            market_margin=0.05,
            market_noise_concentration=40.0,
        ),
        "91d79b5989bb4464b474904cd3a084ecc1d30f2ccb43ef94c65033e4e9ee6705",
    ),
    "stage2_drift": (
        SyntheticDataConfig(
            seed=2024,
            n_teams=14,
            n_matches=900,
            start_date="2021-08-01T00:00:00+00:00",
            days_between_matches=1.0,
            result_confirmation_delay_hours=2.0,
            fixture_announcement_days_before=14.0,
            odds_snapshot_offsets_hours=[72.0, 24.0, 1.0],
            team_attack_log_std=0.35,
            team_defense_log_std=0.35,
            team_attack_drift_log_std_per_day=0.0015,
            team_defense_drift_log_std_per_day=0.0015,
            market_margin=0.05,
            market_noise_concentration=40.0,
        ),
        "adc9991ccb4b9ac411a629350da3bb6a9d0693a62e81940d4cc077ef7aa0ab06",
    ),
}


def test_existing_scenarios_produce_bit_identical_datasets_after_b1_changes() -> None:
    for name, (cfg, expected_digest) in _GOLDEN_HASHES.items():
        assert cfg.dixon_coles_rho == 0.0  # sanite : ces scenarios n'utilisent jamais B1
        actual_digest = _dataset_digest(cfg)
        assert actual_digest == expected_digest, (
            f"Regression detectee sur le scenario '{name}' (dixon_coles_rho=0.0) : "
            f"le dataset genere a change alors qu'aucun changement de comportement "
            f"n'est attendu pour ce chemin de code."
        )
