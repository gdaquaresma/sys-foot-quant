from __future__ import annotations

import numpy as np
import pytest

from sys_foot_quant.calibration_engine.significance import (
    paired_bootstrap_test,
    paired_t_test,
    two_sample_bootstrap_test,
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


def test_two_sample_bootstrap_identical_distributions_not_significant() -> None:
    rng = np.random.default_rng(4)
    a = rng.normal(loc=0.0, scale=1.0, size=1000)
    b = rng.normal(loc=0.0, scale=1.0, size=1000)
    result = two_sample_bootstrap_test(a, b, n_resamples=2000, seed=4)
    assert result["ci_low"] <= 0.0 <= result["ci_high"]
    assert result["p_value"] > 0.05


def test_two_sample_bootstrap_detects_clear_difference() -> None:
    rng = np.random.default_rng(5)
    a = rng.normal(loc=1.0, scale=0.1, size=200)
    b = rng.normal(loc=0.0, scale=0.1, size=200)
    result = two_sample_bootstrap_test(a, b, n_resamples=2000, seed=5)
    assert result["mean_diff"] == pytest.approx(1.0, abs=0.05)
    assert result["ci_low"] > 0.0
    assert result["p_value"] < 0.01


def test_two_sample_bootstrap_reproducible_with_fixed_seed() -> None:
    rng = np.random.default_rng(6)
    a = rng.normal(size=100)
    b = rng.normal(size=120)
    r1 = two_sample_bootstrap_test(a, b, n_resamples=1000, seed=42)
    r2 = two_sample_bootstrap_test(a, b, n_resamples=1000, seed=42)
    assert r1 == r2


def test_two_sample_bootstrap_rejects_empty_input() -> None:
    with pytest.raises(ValueError):
        two_sample_bootstrap_test(np.array([]), np.array([1.0, 2.0]), n_resamples=100, seed=0)
    with pytest.raises(ValueError):
        two_sample_bootstrap_test(np.array([1.0]), np.array([]), n_resamples=100, seed=0)


def test_two_sample_bootstrap_handles_different_sample_sizes() -> None:
    rng = np.random.default_rng(7)
    a = rng.normal(loc=0.5, size=50)
    b = rng.normal(loc=0.0, size=500)
    result = two_sample_bootstrap_test(a, b, n_resamples=1000, seed=7)
    assert np.isfinite(result["mean_diff"])
    assert result["ci_low"] <= result["mean_diff"] <= result["ci_high"]
