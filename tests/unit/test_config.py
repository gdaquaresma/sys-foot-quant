from __future__ import annotations

from pathlib import Path

from sys_foot_quant.common.config import load_config

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_load_stage1_config() -> None:
    cfg = load_config(REPO_ROOT / "configs" / "backtest_stage1.yaml")
    assert cfg.synthetic_data.seed == 42
    assert cfg.synthetic_data.n_teams == 8
    assert cfg.synthetic_data.n_matches == 60
    assert cfg.decision_offset_hours_before_kickoff == 1.0
    assert cfg.synthetic_data.odds_snapshot_offsets_hours == [72.0, 24.0, 1.0]
