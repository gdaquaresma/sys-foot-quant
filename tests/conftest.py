from __future__ import annotations

from pathlib import Path

import pytest

from sys_foot_quant.common.config import SyntheticDataConfig
from sys_foot_quant.data_engine.storage.repository import DuckDBRepository
from sys_foot_quant.data_engine.storage.writer import write_dataset
from sys_foot_quant.data_engine.synthetic.generator import (
    SyntheticDataset,
    generate_synthetic_dataset,
)

# Configuration reduite pour des tests rapides (identique en structure a
# configs/backtest_stage1.yaml, mais volume plus petit).
SMALL_SYNTHETIC_CONFIG = SyntheticDataConfig(
    seed=42,
    n_teams=6,
    n_matches=20,
    start_date="2024-08-01T00:00:00+00:00",
    days_between_matches=1.5,
    result_confirmation_delay_hours=2.0,
    fixture_announcement_days_before=14.0,
    odds_snapshot_offsets_hours=[72.0, 24.0, 1.0],
)


@pytest.fixture
def small_config() -> SyntheticDataConfig:
    return SMALL_SYNTHETIC_CONFIG.model_copy()


@pytest.fixture
def synthetic_dataset(small_config: SyntheticDataConfig) -> SyntheticDataset:
    return generate_synthetic_dataset(small_config)


@pytest.fixture
def repo(tmp_path: Path, synthetic_dataset: SyntheticDataset) -> DuckDBRepository:
    write_dataset(synthetic_dataset, tmp_path)
    with DuckDBRepository(tmp_path) as repository:
        yield repository
