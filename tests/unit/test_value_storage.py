from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from sys_foot_quant.value_engine.storage import read_value_log, write_value_log


def test_write_and_read_value_log_round_trip(tmp_path) -> None:
    df = pd.DataFrame(
        {
            "match_id": [1, 2],
            "decision_time": [datetime(2024, 1, 1, tzinfo=timezone.utc)] * 2,
            "selection": ["home", "away"],
            "edge": [0.05, -0.02],
            "ev": [0.10, -0.05],
            "passes_thresholds": [True, False],
            "clv_pct": [1.2, None],
        }
    )
    path = write_value_log(df, tmp_path / "value_log.parquet")
    assert path.exists()

    loaded = read_value_log(path)
    pd.testing.assert_frame_equal(
        loaded.reset_index(drop=True), df.reset_index(drop=True), check_dtype=False
    )


def test_write_value_log_creates_parent_directories(tmp_path) -> None:
    df = pd.DataFrame({"match_id": [1], "edge": [0.01]})
    nested_path = tmp_path / "nested" / "dir" / "log.parquet"
    write_value_log(df, nested_path)
    assert nested_path.exists()


def test_read_value_log_raises_on_missing_file(tmp_path) -> None:
    with pytest.raises(Exception):
        read_value_log(tmp_path / "does_not_exist.parquet")
