"""Tests unitaires des fonctions PURES d'E11
(scripts/run_stage20_e11_probability_reliability_mapping.py) - avant
toute execution reelle."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage20_e11_probability_reliability_mapping.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage20_e11_probability_reliability_mapping", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e11_module():
    return _load_script()


# --- bin_index_for_prob -------------------------------------------------------


def test_bin_index_for_prob_matches_reliability_bins(e11_module) -> None:
    from sys_foot_quant.calibration_engine.reliability import reliability_bins

    rng = np.random.default_rng(0)
    p = rng.uniform(0, 1, size=200)
    y = rng.binomial(1, p).astype(float)
    base = reliability_bins(p, y, n_bins=10)
    bin_idx = e11_module.bin_index_for_prob(p, n_bins=10)
    for b in range(10):
        mask = bin_idx == b
        assert int(mask.sum()) == int(base.iloc[b]["count"])


def test_bin_index_for_prob_boundaries(e11_module) -> None:
    p = np.array([0.0, 0.05, 0.10, 0.55, 0.999, 1.0])
    idx = e11_module.bin_index_for_prob(p, n_bins=10)
    assert idx[0] == 0  # 0.0 -> premiere tranche
    assert idx[3] == 5  # 0.55 -> tranche [0.5,0.6)
    assert idx[5] == 9  # 1.0 -> derniere tranche


# --- calibration_table --------------------------------------------------------


def test_calibration_table_consistent_with_bin_index(e11_module) -> None:
    rng = np.random.default_rng(1)
    p = rng.uniform(0, 1, size=300)
    y = rng.binomial(1, p).astype(float)
    table = e11_module.calibration_table(p, y)
    bin_idx = e11_module.bin_index_for_prob(p)
    for b in range(10):
        assert int(table.iloc[b]["n"]) == int((bin_idx == b).sum())


def test_calibration_table_bias_matches_manual(e11_module) -> None:
    p = np.array([0.55] * 4)
    y = np.array([1.0, 1.0, 0.0, 0.0])
    table = e11_module.calibration_table(p, y)
    row = table[(table["bin_lo"] <= 0.55) & (table["bin_hi"] > 0.55)].iloc[0]
    assert row["p_moyen"] == pytest.approx(0.55)
    assert row["freq_observee"] == pytest.approx(0.5)
    assert row["biais"] == pytest.approx(0.5 - 0.55)


def test_calibration_table_empty_bin_flagged(e11_module) -> None:
    p = np.array([0.05] * 10)
    y = np.array([0.0, 1.0] * 5)
    table = e11_module.calibration_table(p, y)
    empty_bins = table[table["n"] == 0]
    assert not empty_bins.empty
    assert empty_bins["incertitude_elevee"].all()


def test_calibration_table_small_n_flagged_uncertain(e11_module) -> None:
    p = np.array([0.15] * 10)
    y = np.array([0.0, 1.0] * 5)
    table = e11_module.calibration_table(p, y)
    row = table[(table["bin_lo"] <= 0.15) & (table["bin_hi"] > 0.15)].iloc[0]
    assert row["n"] == 10
    assert bool(row["incertitude_elevee"]) is True  # n=10 < 30


# --- calibration_slope_intercept ---------------------------------------------


def test_calibration_slope_intercept_perfect_calibration_near_unit_slope(e11_module) -> None:
    rng = np.random.default_rng(2)
    p = rng.uniform(0.05, 0.95, size=2000)
    y = rng.binomial(1, p).astype(float)
    out = e11_module.calibration_slope_intercept(p, y)
    assert out["slope"] == pytest.approx(1.0, abs=0.25)
    assert out["intercept"] == pytest.approx(0.0, abs=0.25)


def test_calibration_slope_intercept_insufficient_data_returns_nan(e11_module) -> None:
    out = e11_module.calibration_slope_intercept(np.array([0.5]), np.array([1.0]))
    assert np.isnan(out["slope"])
    assert out["converged"] is False


def test_calibration_slope_intercept_never_modifies_p(e11_module) -> None:
    p = np.array([0.3, 0.5, 0.7, 0.9])
    p_copy = p.copy()
    e11_module.calibration_slope_intercept(p, np.array([0.0, 1.0, 1.0, 1.0]))
    np.testing.assert_array_equal(p, p_copy)


# --- point_biserial_correlation -----------------------------------------------


def test_point_biserial_correlation_perfect_discrimination(e11_module) -> None:
    p = np.array([0.1, 0.2, 0.8, 0.9])
    y = np.array([0.0, 0.0, 1.0, 1.0])
    out = e11_module.point_biserial_correlation(p, y)
    assert out > 0.9


def test_point_biserial_correlation_zero_variance_returns_nan(e11_module) -> None:
    p = np.array([0.5, 0.5, 0.5])
    y = np.array([0.0, 1.0, 0.0])
    assert np.isnan(e11_module.point_biserial_correlation(p, y))


# --- summarize_reliability ----------------------------------------------------


def test_summarize_reliability_flags_insufficient(e11_module) -> None:
    p = np.array([0.5] * 10)
    y = np.array([0.0, 1.0] * 5)
    out = e11_module.summarize_reliability(p, y)
    assert out["n"] == 10
    assert out["insuffisant"] is True


def test_summarize_reliability_empty(e11_module) -> None:
    out = e11_module.summarize_reliability(np.array([]), np.array([]))
    assert out["n"] == 0
    assert out["insuffisant"] is True


# --- compare_models_paired_brier ----------------------------------------------


def test_compare_models_paired_brier_uses_intersection_only(e11_module) -> None:
    df_a = pd.DataFrame({"match_id": ["1", "2", "3"], "p_over_2.5": [0.5, 0.6, 0.7], "outcome_over_2.5": [1.0, 0.0, 1.0]})
    df_b = pd.DataFrame({"match_id": ["2", "3", "4"], "p_over_2.5": [0.55, 0.65, 0.75], "outcome_over_2.5": [0.0, 1.0, 1.0]})
    out = e11_module.compare_models_paired_brier(df_a, df_b, 2.5)
    assert out is not None
    assert out["n"] == 2  # matchs "2" et "3" uniquement


def test_compare_models_paired_brier_none_when_no_overlap(e11_module) -> None:
    df_a = pd.DataFrame({"match_id": ["1"], "p_over_2.5": [0.5], "outcome_over_2.5": [1.0]})
    df_b = pd.DataFrame({"match_id": ["2"], "p_over_2.5": [0.5], "outcome_over_2.5": [1.0]})
    assert e11_module.compare_models_paired_brier(df_a, df_b, 2.5) is None


# --- reliable_bin_indices ------------------------------------------------------


def test_reliable_bin_indices_excludes_uncertain_and_significant(e11_module) -> None:
    table = pd.DataFrame(
        {
            "bin_lo": [0.0, 0.5],
            "bin_hi": [0.5, 1.0],
            "n": [50, 5],
            "biais_ic95_low": [-0.05, -0.05],
            "biais_ic95_high": [0.05, 0.05],
            "incertitude_elevee": [False, True],
        }
    )
    idx = e11_module.reliable_bin_indices(table)
    assert idx == {0}


def test_reliable_bin_indices_excludes_significant_bias(e11_module) -> None:
    table = pd.DataFrame(
        {
            "bin_lo": [0.0],
            "bin_hi": [0.5],
            "n": [50],
            "biais_ic95_low": [0.02],
            "biais_ic95_high": [0.10],
            "incertitude_elevee": [False],
        }
    )
    assert e11_module.reliable_bin_indices(table) == set()


# --- classify_price_diff / price_diff_table -----------------------------------


@pytest.mark.parametrize("pct,expected", [(0.0, "<2%"), (1.99, "<2%"), (2.0, "2-5%"), (4.99, "2-5%"), (5.0, "5-10%"), (9.99, "5-10%"), (10.0, ">=10%"), (50.0, ">=10%")])
def test_classify_price_diff_boundaries(e11_module, pct, expected) -> None:
    assert e11_module.classify_price_diff(pct) == expected


def test_price_diff_table_basic(e11_module) -> None:
    df = pd.DataFrame({"price_diff_pct": [1.0, 1.5, 3.0, 12.0], "p_model": [0.5, 0.5, 0.6, 0.7], "outcome": [1.0, 0.0, 1.0, 0.0]})
    table = e11_module.price_diff_table(df)
    row_lt2 = table[table["categorie"] == "<2%"].iloc[0]
    assert row_lt2["n"] == 2
    assert row_lt2["p_model_moyen"] == pytest.approx(0.5)
    assert not np.isnan(row_lt2["biais_ic95_low"])
    assert not np.isnan(row_lt2["biais_ic95_high"])


def test_price_diff_table_empty_category_has_nan_ci(e11_module) -> None:
    df = pd.DataFrame({"price_diff_pct": [1.0], "p_model": [0.5], "outcome": [1.0]})
    table = e11_module.price_diff_table(df)
    row_empty = table[table["categorie"] == ">=10%"].iloc[0]
    assert row_empty["n"] == 0
    assert np.isnan(row_empty["biais_ic95_low"])
