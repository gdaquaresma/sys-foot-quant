from __future__ import annotations

import numpy as np
import pytest

from sys_foot_quant.calibration_engine.reliability import reliability_bins


def test_reliability_bins_deterministic_two_clusters() -> None:
    probs = np.array([0.1] * 10 + [0.9] * 10)
    outcomes = np.array([0] * 10 + [1] * 10)  # parfaitement calibre
    table = reliability_bins(probs, outcomes, n_bins=10)

    non_empty = table[table["count"] > 0]
    assert len(non_empty) == 2
    low = non_empty[non_empty["mean_predicted"] < 0.5].iloc[0]
    high = non_empty[non_empty["mean_predicted"] >= 0.5].iloc[0]
    assert low["mean_predicted"] == pytest.approx(0.1, abs=1e-9)
    assert low["observed_frequency"] == pytest.approx(0.0, abs=1e-9)
    assert high["mean_predicted"] == pytest.approx(0.9, abs=1e-9)
    assert high["observed_frequency"] == pytest.approx(1.0, abs=1e-9)
    assert low["count"] == 10
    assert high["count"] == 10


def test_reliability_bins_total_count_matches_input() -> None:
    rng = np.random.default_rng(0)
    probs = rng.uniform(0, 1, size=200)
    outcomes = (rng.uniform(0, 1, size=200) < probs).astype(int)
    table = reliability_bins(probs, outcomes, n_bins=5)
    assert table["count"].sum() == 200


def test_reliability_bins_rejects_probs_outside_unit_interval() -> None:
    with pytest.raises(ValueError):
        reliability_bins(np.array([1.5]), np.array([1]), n_bins=5)


def test_reliability_bins_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError):
        reliability_bins(np.array([0.1, 0.2]), np.array([1]), n_bins=5)
