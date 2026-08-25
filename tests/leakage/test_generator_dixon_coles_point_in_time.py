"""Regression anti-look-ahead pour le scenario Dixon-Coles (hypothese B1) :
verifie que le nouveau chemin de tirage joint (matrice de score corrigee
par tau, remplace les deux tirages rng.poisson() independants quand
``dixon_coles_rho != 0.0``) n'a pas modifie la semantique de
``knowledge_time`` deja etablie et testee aux etapes 1-5 - meme principe
que tests/leakage/test_generator_correction_point_in_time.py, applique au
scenario Dixon-Coles."""

from __future__ import annotations

from datetime import timedelta

import pandas as pd
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from sys_foot_quant.common.config import SyntheticDataConfig
from sys_foot_quant.data_engine.storage.repository import DuckDBRepository
from sys_foot_quant.data_engine.storage.writer import write_dataset
from sys_foot_quant.data_engine.synthetic.generator import generate_synthetic_dataset

_DIXON_COLES_CONFIG = SyntheticDataConfig(
    seed=17,
    n_teams=8,
    n_matches=120,
    start_date="2022-03-01T00:00:00+00:00",
    days_between_matches=1.5,
    team_attack_log_std=0.3,
    team_defense_log_std=0.3,
    market_margin=0.05,
    market_noise_concentration=40.0,
    dixon_coles_rho=-0.13,
)


def test_results_still_invisible_before_confirmation_on_dixon_coles_dataset(tmp_path) -> None:
    dataset = generate_synthetic_dataset(_DIXON_COLES_CONFIG)
    write_dataset(dataset, tmp_path)
    with DuckDBRepository(tmp_path) as repo:
        full_results = repo.debug_get_full_table("match_results")
        earliest = full_results.sort_values("knowledge_time").iloc[0]
        just_before = earliest["knowledge_time"] - timedelta(seconds=1)
        visible = repo.get_as_of("match_results", just_before)
        assert int(earliest["match_id"]) not in set(visible["match_id"])


def test_odds_knowledge_time_invariant_holds_on_dixon_coles_market(tmp_path) -> None:
    dataset = generate_synthetic_dataset(_DIXON_COLES_CONFIG)
    write_dataset(dataset, tmp_path)
    with DuckDBRepository(tmp_path) as repo:
        from datetime import datetime, timezone

        base = datetime.fromisoformat(_DIXON_COLES_CONFIG.start_date)
        if base.tzinfo is None:
            base = base.replace(tzinfo=timezone.utc)

        @given(offset_minutes=st.integers(min_value=-5 * 24 * 60, max_value=40 * 24 * 60))
        @settings(
            max_examples=100,
            deadline=None,
            suppress_health_check=[HealthCheck.function_scoped_fixture],
        )
        def _check(offset_minutes: int) -> None:
            as_of = base + timedelta(minutes=offset_minutes)
            visible = repo.get_as_of("odds_snapshots", as_of)
            if visible.empty:
                return
            assert (visible["knowledge_time"] <= pd.Timestamp(as_of)).all(), (
                f"Fuite detectee sur odds_snapshots (marche Dixon-Coles) a as_of={as_of}."
            )

        _check()


def test_dixon_coles_market_uses_dixon_coles_probabilities_not_plain_poisson_path(
    monkeypatch,
) -> None:
    """Preuve directe de l'Option A (validee, ADR 0005 point 4) : quand
    ``dixon_coles_rho != 0.0``, la generation du marche synthetique
    n'emprunte JAMAIS ``_true_outcome_probabilities`` (le chemin
    "independant Poisson" utilise aux etapes 1-5) - seule
    ``_dixon_coles_outcome_probabilities`` doit etre appelee. On force
    ``_true_outcome_probabilities`` a lever une exception : si le
    generateur produit un dataset sans lever, c'est la preuve qu'il ne
    l'a jamais appelee sur ce scenario."""
    import sys_foot_quant.data_engine.synthetic.generator as generator_module

    def _boom(lam, mu):
        raise AssertionError(
            "_true_outcome_probabilities ne doit jamais etre appelee quand "
            "dixon_coles_rho != 0.0 (Option A : le marche doit utiliser les "
            "vraies probabilites Dixon-Coles, pas l'hypothese d'independance)."
        )

    monkeypatch.setattr(generator_module, "_true_outcome_probabilities", _boom)
    # Ne doit pas lever : prouve que le marche du scenario Dixon-Coles
    # n'appelle jamais la fonction "independante" desormais piegee.
    generate_synthetic_dataset(_DIXON_COLES_CONFIG)


def test_zero_rho_market_still_uses_plain_poisson_path(monkeypatch) -> None:
    """Symetrique du test precedent : a rho=0.0 (comportement des etapes
    1-5, inchange), c'est ``_dixon_coles_outcome_probabilities`` qui ne
    doit JAMAIS etre appelee - piege la fonction Dixon-Coles pour le
    prouver."""
    import sys_foot_quant.data_engine.synthetic.generator as generator_module

    def _boom(lam, mu, rho):
        raise AssertionError(
            "_dixon_coles_outcome_probabilities ne doit jamais etre appelee "
            "quand dixon_coles_rho == 0.0 (comportement des etapes 1-5, "
            "rigoureusement inchange)."
        )

    monkeypatch.setattr(generator_module, "_dixon_coles_outcome_probabilities", _boom)
    zero_rho_config = _DIXON_COLES_CONFIG.model_copy(update={"dixon_coles_rho": 0.0})
    generate_synthetic_dataset(zero_rho_config)
