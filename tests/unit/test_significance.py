from __future__ import annotations

import numpy as np
import pytest

from sys_foot_quant.calibration_engine.significance import (
    paired_bootstrap_test,
    paired_t_test,
)


def test_bootstrap_test_zero_diffs_not_significant() -> None:
    diffs = np.zeros(200)
    result = paired_bootstrap_test(diffs, n_resamples=2000, seed=0)
    assert result["mean_diff"] == pytest.approx(0.0, abs=1e-9)
    assert result["ci_low"] <= 0.0 <= result["ci_high"]
    assert result["p_value"] > 0.5


def test_bootstrap_test_detects_clear_difference() -> None:
    rng = np.random.default_rng(1)
    diffs = rng.normal(loc=0.5, scale=0.05, size=300)
    result = paired_bootstrap_test(diffs, n_resamples=2000, seed=1)
    assert result["ci_low"] > 0.0
    assert result["p_value"] < 0.01


def test_bootstrap_test_is_reproducible_with_fixed_seed() -> None:
    rng = np.random.default_rng(2)
    diffs = rng.normal(loc=0.1, scale=0.2, size=100)
    r1 = paired_bootstrap_test(diffs, n_resamples=1000, seed=42)
    r2 = paired_bootstrap_test(diffs, n_resamples=1000, seed=42)
    assert r1 == r2


def test_bootstrap_test_rejects_empty_input() -> None:
    with pytest.raises(ValueError):
        paired_bootstrap_test(np.array([]), n_resamples=100, seed=0)


def test_paired_t_test_zero_diffs_not_significant() -> None:
    diffs = np.zeros(50)
    result = paired_t_test(diffs)
    assert result["p_value"] > 0.9


def test_paired_t_test_detects_clear_difference() -> None:
    rng = np.random.default_rng(3)
    diffs = rng.normal(loc=1.0, scale=0.1, size=100)
    result = paired_t_test(diffs)
    assert result["p_value"] < 0.01
    assert result["t_stat"] > 0
