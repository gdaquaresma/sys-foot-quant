"""Regression anti-look-ahead suite a la correction de l'etape 2
(derive de force d'equipe + marche synthetique informe) : verifie que ces
changements, qui ne touchent que la generation des VALEURS (buts, cotes),
n'ont pas modifie ou casse la semantique de ``knowledge_time`` deja
etablie et testee a l'etape 1.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from sys_foot_quant.common.config import SyntheticDataConfig
from sys_foot_quant.data_engine.storage.repository import DuckDBRepository
from sys_foot_quant.data_engine.storage.writer import write_dataset
from sys_foot_quant.data_engine.synthetic.generator import generate_synthetic_dataset

_DRIFT_CONFIG = SyntheticDataConfig(
    seed=17,
    n_teams=8,
    n_matches=120,
    start_date="2022-03-01T00:00:00+00:00",
    days_between_matches=1.5,
    team_attack_log_std=0.3,
    team_defense_log_std=0.3,
    team_attack_drift_log_std_per_day=0.002,
    team_defense_drift_log_std_per_day=0.002,
    market_margin=0.05,
    market_noise_concentration=40.0,
)


def test_results_still_invisible_before_confirmation_on_drift_dataset(tmp_path) -> None:
    dataset = generate_synthetic_dataset(_DRIFT_CONFIG)
    write_dataset(dataset, tmp_path)
    with DuckDBRepository(tmp_path) as repo:
        full_results = repo.debug_get_full_table("match_results")
        earliest = full_results.sort_values("knowledge_time").iloc[0]
        just_before = earliest["knowledge_time"] - timedelta(seconds=1)
        visible = repo.get_as_of("match_results", just_before)
        assert int(earliest["match_id"]) not in set(visible["match_id"])


def test_odds_knowledge_time_invariant_holds_on_informed_market(tmp_path) -> None:
    dataset = generate_synthetic_dataset(_DRIFT_CONFIG)
    write_dataset(dataset, tmp_path)
    with DuckDBRepository(tmp_path) as repo:
        base = datetime.fromisoformat(_DRIFT_CONFIG.start_date)
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
                f"Fuite detectee sur odds_snapshots (marche informe) a as_of={as_of}."
            )

        _check()
