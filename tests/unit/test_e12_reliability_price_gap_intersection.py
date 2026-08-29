"""Tests unitaires des fonctions PURES d'E12
(scripts/run_stage21_e12_reliability_price_gap_intersection.py) - avant
toute execution reelle."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage21_e12_reliability_price_gap_intersection.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage21_e12_reliability_price_gap_intersection", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e12_module():
    return _load_script()


# --- classify_bin_reliability -------------------------------------------------


def test_classify_bin_reliability_fiable(e12_module) -> None:
    assert e12_module.classify_bin_reliability(50, -0.05, 0.05) == e12_module.FIABLE


def test_classify_bin_reliability_non_fiable_positive(e12_module) -> None:
    assert e12_module.classify_bin_reliability(50, 0.02, 0.10) == e12_module.NON_FIABLE


def test_classify_bin_reliability_non_fiable_negative(e12_module) -> None:
    assert e12_module.classify_bin_reliability(50, -0.10, -0.02) == e12_module.NON_FIABLE


def test_classify_bin_reliability_insufficient_n(e12_module) -> None:
    assert e12_module.classify_bin_reliability(10, -0.05, 0.05) == e12_module.INSUFFISANT


def test_classify_bin_reliability_insufficient_nan_ci(e12_module) -> None:
    assert e12_module.classify_bin_reliability(50, float("nan"), float("nan")) == e12_module.INSUFFISANT


def test_classify_bin_reliability_boundary_n_exactly_min(e12_module) -> None:
    assert e12_module.classify_bin_reliability(30, -0.05, 0.05) == e12_module.FIABLE
    assert e12_module.classify_bin_reliability(29, -0.05, 0.05) == e12_module.INSUFFISANT


# --- classify_hypothesis_verdict ----------------------------------------------


def test_classify_hypothesis_verdict_demontree(e12_module) -> None:
    boot = {"ci_low": 0.01, "ci_high": 0.05, "mean_diff": 0.03}
    assert e12_module.classify_hypothesis_verdict(boot) == e12_module.VERDICT_DEMONTREE


def test_classify_hypothesis_verdict_contradictoire(e12_module) -> None:
    boot = {"ci_low": -0.05, "ci_high": -0.01, "mean_diff": -0.03}
    assert e12_module.classify_hypothesis_verdict(boot) == e12_module.VERDICT_CONTRADICTOIRE


def test_classify_hypothesis_verdict_directionnelle(e12_module) -> None:
    boot = {"ci_low": -0.02, "ci_high": 0.08, "mean_diff": 0.03}
    assert e12_module.classify_hypothesis_verdict(boot) == e12_module.VERDICT_DIRECTIONNELLE


def test_classify_hypothesis_verdict_absence_de_preuve(e12_module) -> None:
    boot = {"ci_low": -0.08, "ci_high": 0.02, "mean_diff": -0.03}
    assert e12_module.classify_hypothesis_verdict(boot) == e12_module.VERDICT_ABSENCE_PREUVE


def test_classify_hypothesis_verdict_absence_de_preuve_zero_diff(e12_module) -> None:
    boot = {"ci_low": -0.05, "ci_high": 0.05, "mean_diff": 0.0}
    assert e12_module.classify_hypothesis_verdict(boot) == e12_module.VERDICT_ABSENCE_PREUVE


# --- joint_bin_table -----------------------------------------------------------


def _cal_table_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "bin_lo": [0.0, 0.5],
            "bin_hi": [0.5, 1.0],
            "n": [50, 40],
            "p_moyen": [0.3, 0.7],
            "freq_observee": [0.32, 0.55],
            "biais": [0.02, -0.15],
            "biais_ic95_low": [-0.05, -0.25],
            "biais_ic95_high": [0.09, -0.05],
        }
    )


def test_joint_bin_table_merges_calibration_and_market(e12_module) -> None:
    cal_table = _cal_table_fixture()
    market_df = pd.DataFrame(
        {
            "bin_idx": [0, 0, 1],
            "p_model": [0.3, 0.32, 0.7],
            "p_market_raw": [0.28, 0.30, 0.68],
            "p_market_normalized": [0.27, 0.29, 0.65],
            "fair_odds_model": [3.33, 3.125, 1.43],
            "b365_odds_over": [3.5, 3.4, 1.5],
        }
    )
    joint = e12_module.joint_bin_table(cal_table, market_df)
    assert len(joint) == 2
    row0 = joint.iloc[0]
    assert row0["n"] == 50
    assert row0["n_marche"] == 2
    assert row0["classification_fiabilite"] == e12_module.FIABLE
    row1 = joint.iloc[1]
    assert row1["n_marche"] == 1
    assert row1["classification_fiabilite"] == e12_module.NON_FIABLE
    assert row1["gap_moyen"] == pytest.approx(0.7 - 0.65)


def test_joint_bin_table_nan_when_no_market_data(e12_module) -> None:
    cal_table = _cal_table_fixture()
    market_df = pd.DataFrame({"bin_idx": [], "p_model": [], "p_market_raw": [], "p_market_normalized": [], "fair_odds_model": [], "b365_odds_over": []})
    joint = e12_module.joint_bin_table(cal_table, market_df)
    assert joint.iloc[0]["n_marche"] == 0
    assert np.isnan(joint.iloc[0]["gap_moyen"])


# --- test_reliable_bins_have_larger_gaps --------------------------------------


def test_reliable_bins_have_larger_gaps_excludes_insufficient(e12_module) -> None:
    cal_table = pd.DataFrame(
        {
            "n": [50, 50, 10],
            "biais_ic95_low": [-0.05, 0.02, -0.05],
            "biais_ic95_high": [0.05, 0.10, 0.05],
        }
    )  # bin 0 fiable, bin 1 non fiable, bin 2 insuffisant (exclu des deux groupes)
    rng = np.random.default_rng(0)
    market_df = pd.DataFrame(
        {
            "bin_idx": [0] * 40 + [1] * 40 + [2] * 40,
            "p_model": rng.uniform(0.1, 0.9, 120),
            "p_market_normalized": rng.uniform(0.1, 0.9, 120),
        }
    )
    out = e12_module.test_reliable_bins_have_larger_gaps(cal_table, market_df)
    assert out["n_fiable"] == 40
    assert out["n_non_fiable"] == 40
    assert out["boot"] is not None
    assert out["verdict"] in {
        e12_module.VERDICT_DEMONTREE,
        e12_module.VERDICT_CONTRADICTOIRE,
        e12_module.VERDICT_DIRECTIONNELLE,
        e12_module.VERDICT_ABSENCE_PREUVE,
    }


def test_reliable_bins_have_larger_gaps_insufficient_data(e12_module) -> None:
    cal_table = pd.DataFrame({"n": [50], "biais_ic95_low": [-0.05], "biais_ic95_high": [0.05]})
    market_df = pd.DataFrame({"bin_idx": [0], "p_model": [0.5], "p_market_normalized": [0.5]})
    out = e12_module.test_reliable_bins_have_larger_gaps(cal_table, market_df)
    assert out["boot"] is None
    assert "insuffisantes" in out["verdict"]


def test_reliable_bins_have_larger_gaps_detects_real_difference(e12_module) -> None:
    cal_table = pd.DataFrame(
        {
            "n": [50, 50],
            "biais_ic95_low": [-0.05, 0.05],
            "biais_ic95_high": [0.05, 0.20],
        }
    )
    rng = np.random.default_rng(1)
    # bin fiable (0) : GRAND gap ; bin non fiable (1) : petit gap - construit
    # deliberement pour que "fiable" ait un |gap| plus grand que "non fiable",
    # donc diff(fiable-non_fiable) > 0 -> verdict attendu : demontree.
    market_df = pd.DataFrame(
        {
            "bin_idx": [0] * 50 + [1] * 50,
            "p_model": np.concatenate([rng.uniform(0.45, 0.55, 50), rng.uniform(0.45, 0.55, 50)]),
            "p_market_normalized": np.concatenate([rng.uniform(0.20, 0.30, 50), rng.uniform(0.44, 0.56, 50)]),
        }
    )
    out = e12_module.test_reliable_bins_have_larger_gaps(cal_table, market_df)
    assert out["verdict"] == e12_module.VERDICT_DEMONTREE
