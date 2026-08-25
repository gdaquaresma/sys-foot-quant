from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from sys_foot_quant.calibration_engine.low_score_metrics import (
    LOW_SCORE_CELLS,
    LOW_SCORE_LABELS,
    cell_contribution_table,
    low_score_category_row,
    low_score_outcome_index,
)


@pytest.mark.parametrize(
    "home_goals,away_goals,expected",
    [(0, 0, 0), (1, 0, 1), (0, 1, 2), (1, 1, 3), (2, 0, None), (0, 2, None), (3, 3, None)],
)
def test_low_score_outcome_index(home_goals: int, away_goals: int, expected: int | None) -> None:
    assert low_score_outcome_index(home_goals, away_goals) == expected


def test_low_score_cells_and_labels_are_aligned() -> None:
    assert len(LOW_SCORE_CELLS) == len(LOW_SCORE_LABELS) == 4
    assert LOW_SCORE_CELLS[low_score_outcome_index(1, 1)] == (1, 1)


def test_category_row_sums_to_one_and_matches_input() -> None:
    row = low_score_category_row((0.05, 0.08, 0.07, 0.10))
    assert row.shape == (5,)
    assert row.sum() == pytest.approx(1.0)
    assert row[:4] == pytest.approx([0.05, 0.08, 0.07, 0.10])
    assert row[4] == pytest.approx(1.0 - (0.05 + 0.08 + 0.07 + 0.10))


def test_category_row_clips_negative_residual_to_zero() -> None:
    # residu negatif de l'ordre de l'epsilon flottant, jamais un ecart reel.
    row = low_score_category_row((0.3, 0.3, 0.3, 0.3 + 1e-13))
    assert row[4] >= 0.0


def test_category_row_rejects_wrong_shape() -> None:
    with pytest.raises(ValueError):
        low_score_category_row((0.1, 0.2, 0.3))  # type: ignore[arg-type]


def test_cell_contribution_table_requires_expected_columns() -> None:
    with pytest.raises(ValueError):
        cell_contribution_table(pd.DataFrame({"cell": [0]}))


def test_cell_contribution_table_groups_by_cell_and_computes_diffs() -> None:
    records = pd.DataFrame(
        {
            "cell": [0, 0, 1, 3],
            "brier_a": [0.20, 0.30, 0.50, 0.10],
            "brier_b": [0.10, 0.20, 0.55, 0.05],
            "log_loss_a": [1.0, 1.2, 0.8, 0.5],
            "log_loss_b": [0.8, 1.0, 0.9, 0.4],
        }
    )
    table = cell_contribution_table(records)
    assert list(table["cell"]) == list(LOW_SCORE_LABELS)

    row_00 = table[table["cell"] == "0-0"].iloc[0]
    assert row_00["n"] == 2
    assert row_00["brier_a_mean"] == pytest.approx(0.25)
    assert row_00["brier_b_mean"] == pytest.approx(0.15)
    assert row_00["brier_diff_b_minus_a"] == pytest.approx(-0.10)

    row_10 = table[table["cell"] == "1-0"].iloc[0]
    assert row_10["n"] == 1
    assert row_10["brier_diff_b_minus_a"] == pytest.approx(0.05)

    row_01 = table[table["cell"] == "0-1"].iloc[0]
    assert row_01["n"] == 0
    assert np.isnan(row_01["brier_a_mean"])

    row_11 = table[table["cell"] == "1-1"].iloc[0]
    assert row_11["n"] == 1
    assert row_11["log_loss_diff_b_minus_a"] == pytest.approx(-0.1)
