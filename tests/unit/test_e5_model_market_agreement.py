"""Tests unitaires des fonctions PURES d'E5
(scripts/run_stage13_e5_model_market_agreement_over25.py) - avant toute
execution reelle."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage13_e5_model_market_agreement_over25.py"
)


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage13_e5_model_market_agreement_over25", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e5_module():
    return _load_script()


def _agreement_df(rows: list[tuple[str, float, float, float]]) -> pd.DataFrame:
    """rows: (match_id, p_model, p_market, outcome)."""
    return pd.DataFrame(
        [
            {"match_id": m, "p_model": pm, "p_market": pk, "gap": pm - pk, "outcome": o}
            for m, pm, pk, o in rows
        ]
    )


# --- gap_bin_table -------------------------------------------------------


def test_gap_bin_table_covers_all_rows(e5_module) -> None:
    rng = np.random.default_rng(0)
    n = 500
    p_model = rng.uniform(0.1, 0.9, size=n)
    p_market = rng.uniform(0.1, 0.9, size=n)
    outcome = rng.integers(0, 2, size=n).astype(float)
    df = pd.DataFrame(
        {"match_id": [f"m{i}" for i in range(n)], "p_model": p_model, "p_market": p_market, "gap": p_model - p_market, "outcome": outcome}
    )
    table = e5_module.gap_bin_table(df)
    assert int(table["n"].sum()) == n
    assert list(table["tranche"]) == e5_module._GAP_LABELS


def test_gap_bin_table_diff_matches_manual_formula(e5_module) -> None:
    # gap = 0.65-0.50=+0.15 -> tranche ">=+15pts"
    df = _agreement_df([("a", 0.65, 0.50, 1.0), ("b", 0.70, 0.50, 0.0)])
    table = e5_module.gap_bin_table(df)
    row = table[table["tranche"] == ">=+15pts"].iloc[0]
    assert row["n"] == 2
    assert row["p_model_moy"] == pytest.approx(0.675)
    assert row["frequence_over_reelle"] == pytest.approx(0.5)
    assert row["diff"] == pytest.approx(0.5 - 0.675)


def test_gap_bin_table_reports_empty_bins(e5_module) -> None:
    df = _agreement_df([("a", 0.5, 0.5, 1.0)])  # gap=0, tranche "-5/+5"
    table = e5_module.gap_bin_table(df)
    assert len(table) == len(e5_module._GAP_LABELS)
    empty = table[table["tranche"] == "<=-15pts"].iloc[0]
    assert empty["n"] == 0
    assert np.isnan(empty["diff"])


def test_gap_bin_edges_are_fixed_constants(e5_module) -> None:
    assert e5_module._GAP_EDGES == [-np.inf, -0.15, -0.10, -0.05, 0.05, 0.10, 0.15, np.inf]
    assert e5_module._GAP_LABELS == ["<=-15pts", "-15/-10", "-10/-5", "-5/+5", "+5/+10", "+10/+15", ">=+15pts"]


# --- brier_comparison_by_bin ---------------------------------------------


def test_brier_comparison_matches_manual_computation(e5_module) -> None:
    df = _agreement_df([("a", 0.8, 0.5, 1.0), ("b", 0.8, 0.5, 0.0), ("c", 0.8, 0.5, 1.0)])
    # gap = +0.3 -> tranche ">=+15pts"
    table = e5_module.brier_comparison_by_bin(df)
    row = table[table["tranche"] == ">=+15pts"].iloc[0]
    expected_brier_model = np.mean([(0.8 - 1) ** 2, (0.8 - 0) ** 2, (0.8 - 1) ** 2])
    expected_brier_market = np.mean([(0.5 - 1) ** 2, (0.5 - 0) ** 2, (0.5 - 1) ** 2])
    assert row["brier_model"] == pytest.approx(expected_brier_model)
    assert row["brier_market"] == pytest.approx(expected_brier_market)
    assert row["diff_moy"] == pytest.approx(expected_brier_model - expected_brier_market)


def test_brier_comparison_flags_low_n_as_high_uncertainty(e5_module) -> None:
    df = _agreement_df([("a", 0.8, 0.5, 1.0)])  # n=1 < seuil
    table = e5_module.brier_comparison_by_bin(df)
    row = table[table["tranche"] == ">=+15pts"].iloc[0]
    assert bool(row["incertitude_elevee"]) is True


def test_brier_comparison_does_not_flag_populated_bin(e5_module) -> None:
    rng = np.random.default_rng(1)
    n = 50
    rows = [(f"m{i}", 0.75, 0.55, float(rng.integers(0, 2))) for i in range(n)]
    df = _agreement_df(rows)
    table = e5_module.brier_comparison_by_bin(df)
    row = table[table["tranche"] == ">=+15pts"].iloc[0]
    assert bool(row["incertitude_elevee"]) is False


# --- concentration_table --------------------------------------------------


def test_concentration_table_sums_to_one(e5_module) -> None:
    rng = np.random.default_rng(2)
    n = 300
    p_model = rng.uniform(0.1, 0.9, size=n)
    p_market = rng.uniform(0.1, 0.9, size=n)
    df = pd.DataFrame(
        {"match_id": [f"m{i}" for i in range(n)], "p_model": p_model, "p_market": p_market, "gap": p_model - p_market, "outcome": rng.integers(0, 2, size=n).astype(float)}
    )
    table = e5_module.concentration_table(df)
    assert table["part_du_test"].sum() == pytest.approx(1.0)
    assert int(table["n"].sum()) == n


# --- build_agreement_dataframe -------------------------------------------


def test_build_agreement_dataframe_excludes_matches_without_market_odds(e5_module) -> None:
    p_model = pd.Series({"m1": 0.6, "m2": 0.55}, name="p")
    test_df = pd.DataFrame({"match_id": ["m1", "m2"], "total_goals": [3, 2]})
    odds_by_match_id = {"m1": (1.8, 2.0)}  # m2 absent
    df, info = e5_module.build_agreement_dataframe(p_model, test_df, odds_by_match_id)
    assert len(df) == 1
    assert df.iloc[0]["match_id"] == "m1"
    assert info["n_excluded_no_market_odds"] == 1
    assert info["n_joined"] == 1


def test_build_agreement_dataframe_market_prob_matches_overround_removal(e5_module) -> None:
    from sys_foot_quant.market_engine.overround import remove_overround_proportional

    p_model = pd.Series({"m1": 0.6})
    test_df = pd.DataFrame({"match_id": ["m1"], "total_goals": [3]})
    odds_by_match_id = {"m1": (1.8, 2.0)}
    df, _ = e5_module.build_agreement_dataframe(p_model, test_df, odds_by_match_id)
    expected = remove_overround_proportional({"over": 1.8, "under": 2.0})["over"]
    assert df.iloc[0]["p_market"] == pytest.approx(expected)
    assert df.iloc[0]["gap"] == pytest.approx(0.6 - expected)


def test_build_agreement_dataframe_outcome_matches_over_2_5(e5_module) -> None:
    p_model = pd.Series({"m1": 0.6, "m2": 0.6})
    test_df = pd.DataFrame({"match_id": ["m1", "m2"], "total_goals": [3, 2]})
    odds_by_match_id = {"m1": (1.8, 2.0), "m2": (1.8, 2.0)}
    df, _ = e5_module.build_agreement_dataframe(p_model, test_df, odds_by_match_id)
    outcome_by_id = dict(zip(df["match_id"], df["outcome"]))
    assert outcome_by_id["m1"] == 1.0  # 3 buts > 2.5
    assert outcome_by_id["m2"] == 0.0  # 2 buts <= 2.5
