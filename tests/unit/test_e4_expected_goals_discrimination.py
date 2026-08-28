"""Tests unitaires des fonctions PURES d'E4 (discrimination de
l'esperance totale de buts, scripts/run_stage12_e4_expected_goals_discrimination.py)
- avant toute execution reelle."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage12_e4_expected_goals_discrimination.py"
)


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage12_e4_expected_goals_discrimination", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e4_module():
    return _load_script()


# --- fixed_bin_table ---------------------------------------------------


def test_fixed_bin_table_covers_all_matches_exactly_once(e4_module) -> None:
    rng = np.random.default_rng(0)
    expected = rng.uniform(0.5, 5.0, size=500)
    actual = np.round(expected + rng.normal(0, 0.5, size=500)).clip(0, None)
    table = e4_module.fixed_bin_table(expected, actual)
    assert int(table["n"].sum()) == 500
    assert list(table["tranche"]) == e4_module._FIXED_BIN_LABELS


def test_fixed_bin_table_bias_matches_manual_formula(e4_module) -> None:
    expected = np.array([1.6, 1.8, 2.2, 2.2, 4.0])
    actual = np.array([1.5, 2.5, 3.0, 1.0, 5.0])
    table = e4_module.fixed_bin_table(expected, actual)
    row_15_20 = table[table["tranche"] == "1.5-2.0"].iloc[0]
    assert row_15_20["n"] == 2
    assert row_15_20["predit_moy"] == pytest.approx(1.7)
    assert row_15_20["observe_moy"] == pytest.approx(2.0)
    assert row_15_20["biais"] == pytest.approx(0.3)


def test_fixed_bin_table_reports_empty_bins_with_nan_not_dropped(e4_module) -> None:
    expected = np.array([0.5, 0.6])  # tout dans "<1.5"
    actual = np.array([1.0, 2.0])
    table = e4_module.fixed_bin_table(expected, actual)
    assert len(table) == len(e4_module._FIXED_BIN_LABELS)  # aucune tranche supprimee
    empty_row = table[table["tranche"] == "3.5+"].iloc[0]
    assert empty_row["n"] == 0
    assert np.isnan(empty_row["biais"])


def test_fixed_bin_table_boundaries_are_fixed_constants(e4_module) -> None:
    # Non-regression : les frontieres ne doivent jamais changer apres coup.
    assert e4_module._FIXED_BIN_EDGES == [-np.inf, 1.5, 2.0, 2.5, 3.0, 3.5, np.inf]
    assert e4_module._FIXED_BIN_LABELS == ["<1.5", "1.5-2.0", "2.0-2.5", "2.5-3.0", "3.0-3.5", "3.5+"]


# --- quintile_table / monotonicity --------------------------------------


def test_quintile_table_covers_all_matches(e4_module) -> None:
    rng = np.random.default_rng(1)
    expected = rng.uniform(0.5, 5.0, size=1000)
    actual = expected + rng.normal(0, 0.3, size=1000)
    table = e4_module.quintile_table(expected, actual)
    assert int(table["n"].sum()) == 1000
    assert len(table) == 5


def test_quintile_table_detects_perfect_monotonic_relationship(e4_module) -> None:
    rng = np.random.default_rng(2)
    expected = rng.uniform(0.5, 5.0, size=2000)
    actual = expected + rng.normal(0, 0.1, size=2000)  # bruit faible, relation forte
    table = e4_module.quintile_table(expected, actual)
    assert e4_module.is_monotonic_non_decreasing(table["observe_moy"].to_numpy())


def test_quintile_table_detects_non_monotonic_relationship(e4_module) -> None:
    rng = np.random.default_rng(3)
    expected = rng.uniform(0.5, 5.0, size=2000)
    actual = -expected + rng.normal(0, 0.1, size=2000)  # relation INVERSE
    table = e4_module.quintile_table(expected, actual)
    assert not e4_module.is_monotonic_non_decreasing(table["observe_moy"].to_numpy())


def test_is_monotonic_non_decreasing_basic_cases(e4_module) -> None:
    assert e4_module.is_monotonic_non_decreasing([1.0, 2.0, 2.0, 3.0])
    assert not e4_module.is_monotonic_non_decreasing([1.0, 3.0, 2.0])
    assert e4_module.is_monotonic_non_decreasing([5.0])
    assert e4_module.is_monotonic_non_decreasing([])


def test_quintile_boundaries_never_use_actual_outcome(e4_module) -> None:
    # Deux vecteurs "actual" totalement differents pour le MEME "expected"
    # doivent produire EXACTEMENT les memes quintiles (n et predit_moy) -
    # preuve que le decoupage ne depend pas du resultat reel.
    rng = np.random.default_rng(4)
    expected = rng.uniform(0.5, 5.0, size=500)
    actual_a = rng.uniform(0, 6, size=500)
    actual_b = rng.uniform(0, 6, size=500)
    table_a = e4_module.quintile_table(expected, actual_a)
    table_b = e4_module.quintile_table(expected, actual_b)
    assert list(table_a["n"]) == list(table_b["n"])
    assert np.allclose(table_a["predit_moy"].to_numpy(), table_b["predit_moy"].to_numpy())


# --- regression_diagnostics / bootstrap ---------------------------------


def test_regression_diagnostics_correlation_matches_numpy(e4_module) -> None:
    rng = np.random.default_rng(5)
    expected = rng.uniform(0, 5, size=300)
    actual = expected * 1.1 + rng.normal(0, 0.2, size=300)
    diag = e4_module.regression_diagnostics(expected, actual)
    assert diag["correlation"] == pytest.approx(float(np.corrcoef(expected, actual)[0, 1]))


def test_regression_diagnostics_mae_and_bias_match_manual(e4_module) -> None:
    expected = np.array([1.0, 2.0, 3.0])
    actual = np.array([1.5, 1.5, 4.0])
    diag = e4_module.regression_diagnostics(expected, actual)
    assert diag["mae"] == pytest.approx(np.mean(np.abs(actual - expected)))
    assert diag["biais_moyen"] == pytest.approx(np.mean(actual - expected))


def test_regression_diagnostics_handles_perfect_prediction() -> None:
    module = _load_script()
    expected = np.array([1.0, 2.0, 3.0, 4.0])
    actual = expected.copy()
    diag = module.regression_diagnostics(expected, actual)
    assert diag["correlation"] == pytest.approx(1.0)
    assert diag["mae"] == pytest.approx(0.0)
    assert diag["biais_moyen"] == pytest.approx(0.0)


def test_bootstrap_bias_and_mae_reuses_paired_bootstrap_test(e4_module) -> None:
    rng = np.random.default_rng(6)
    expected = rng.uniform(0.5, 5.0, size=200)
    actual = expected + 0.3 + rng.normal(0, 0.2, size=200)  # biais systematique +0.3
    boot = e4_module.bootstrap_bias_and_mae(expected, actual)
    assert boot["biais"]["ci_low"] > 0.0  # biais positif detecte avec IC entierement > 0
    assert boot["mae"]["mean_diff"] > 0.0


# --- over_25_rate_by_fixed_bin -------------------------------------------


def test_over_25_rate_increases_with_expected_goals_bin_when_relationship_is_real(e4_module) -> None:
    rng = np.random.default_rng(7)
    n = 3000
    expected = rng.uniform(0.5, 5.0, size=n)
    p_over = np.clip(expected / 5.0, 0.02, 0.98)
    total_goals = np.where(rng.uniform(0, 1, size=n) < p_over, 3, 1)
    table = e4_module.over_25_rate_by_fixed_bin(expected, total_goals)
    rates = table["p_over_2_5_observe"].to_numpy()
    non_nan = rates[~np.isnan(rates)]
    assert e4_module.is_monotonic_non_decreasing(non_nan)


def test_over_25_rate_by_fixed_bin_reports_all_bins(e4_module) -> None:
    expected = np.array([0.5, 1.8, 2.6])
    total_goals = np.array([1, 2, 4])
    table = e4_module.over_25_rate_by_fixed_bin(expected, total_goals)
    assert len(table) == len(e4_module._FIXED_BIN_LABELS)
