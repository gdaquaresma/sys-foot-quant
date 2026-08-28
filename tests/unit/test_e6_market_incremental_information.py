"""Tests unitaires des fonctions PURES d'E6
(scripts/run_stage14_e6_market_incremental_information.py) - avant toute
execution reelle."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage14_e6_market_incremental_information.py"
)


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage14_e6_market_incremental_information", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e6_module():
    return _load_script()


def _synthetic_df(n=2000, seed=0, market_informative=True, model_informative=True) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    expected_goals = rng.uniform(1.0, 4.5, size=n)
    # market_latent est INDEPENDANT de expected_goals par construction -
    # evite qu'un decoupage par p_market, a l'interieur d'une tranche
    # d'esperance, ne reintroduise silencieusement de la variation
    # residuelle d'esperance (confusion), ce qui fausserait un test de
    # "marche non-informatif a esperance controlee".
    market_latent = rng.normal(0, 1, size=n)
    p_market = np.clip(0.5 + 0.1 * market_latent, 0.05, 0.95)
    p_model = np.clip(expected_goals / 5.0 + rng.normal(0, 0.05, size=n), 0.05, 0.95)

    true_p = np.full(n, 0.5)
    if market_informative:
        true_p += (p_market - 0.5) * 0.6
    if model_informative:
        true_p += (expected_goals - 2.75) * 0.05
    true_p = np.clip(true_p, 0.02, 0.98)
    outcome = (rng.uniform(0, 1, size=n) < true_p).astype(float)
    total_goals = np.where(outcome == 1, 3, 2)

    return pd.DataFrame(
        {
            "match_id": [f"m{i}" for i in range(n)],
            "league": rng.choice(["premier_league", "ligue1", "liga"], size=n),
            "season": rng.choice(["2024_25", "2025_26"], size=n),
            "expected_goals": expected_goals,
            "p_model_over25": p_model,
            "p_market_over25": p_market,
            "total_goals": total_goals.astype(float),
            "outcome_over25": outcome,
        }
    )


# --- correlation_matrix --------------------------------------------------


def test_correlation_matrix_has_expected_shape_and_diag(e6_module) -> None:
    df = _synthetic_df()
    corr = e6_module.correlation_matrix(df)
    assert list(corr.columns) == ["expected_goals", "p_model_over25", "p_market_over25"]
    assert np.allclose(np.diag(corr.to_numpy()), 1.0)


# --- expected_goals_bin_table ---------------------------------------------


def test_expected_goals_bin_table_covers_all_rows(e6_module) -> None:
    df = _synthetic_df()
    table = e6_module.expected_goals_bin_table(df)
    assert int(table["n"].sum()) == len(df)
    assert list(table["tranche"]) == e6_module._EXPECTED_GOALS_LABELS


def test_expected_goals_bin_table_reports_empty_bins(e6_module) -> None:
    df = _synthetic_df()
    df = df[df["expected_goals"] >= 2.0]  # vide la tranche "<2.0"
    table = e6_module.expected_goals_bin_table(df)
    empty = table[table["tranche"] == "<2.0"].iloc[0]
    assert empty["n"] == 0
    assert np.isnan(empty["expected_moy"])


def test_expected_goals_bin_boundaries_are_fixed_constants(e6_module) -> None:
    assert e6_module._EXPECTED_GOALS_EDGES == [-np.inf, 2.0, 2.5, 3.0, 3.5, np.inf]
    assert e6_module._EXPECTED_GOALS_LABELS == ["<2.0", "2.0-2.5", "2.5-3.0", "3.0-3.5", ">=3.5"]
    assert e6_module._MARKET_PROB_EDGES == [-np.inf, 0.45, 0.50, 0.55, 0.60, np.inf]
    assert e6_module._MARKET_PROB_LABELS == ["<45%", "45-50%", "50-55%", "55-60%", ">=60%"]
    assert e6_module._MARKET_NATURAL_SPLIT == 0.50
    assert e6_module._MODEL_NATURAL_SPLIT == 2.5


# --- conditional_grid ------------------------------------------------------


def test_conditional_grid_covers_all_rows(e6_module) -> None:
    df = _synthetic_df()
    grid = e6_module.conditional_grid(df)
    assert int(grid["n"].sum()) == len(df)
    assert len(grid) == len(e6_module._EXPECTED_GOALS_LABELS) * len(e6_module._MARKET_PROB_LABELS)


# --- market_incremental_info_test ------------------------------------------


def test_market_incremental_info_detects_real_market_signal(e6_module) -> None:
    df = _synthetic_df(n=4000, seed=1, market_informative=True, model_informative=False)
    result = e6_module.market_incremental_info_test(df)
    # au moins une tranche doit montrer un IC95% entierement positif
    # (marche_haut > marche_bas) - le marche est construit pour etre
    # informatif independamment de l'esperance ici.
    assert (result["ci_low"] > 0).any()


def test_market_incremental_info_no_signal_when_market_uninformative(e6_module) -> None:
    df = _synthetic_df(n=4000, seed=2, market_informative=False, model_informative=True)
    result = e6_module.market_incremental_info_test(df)
    # aucune tranche ne doit montrer un IC95% entierement d'un cote (le
    # marche est construit pour n'apporter aucune info conditionnelle ici)
    assert not (result["ci_low"] > 0).any()
    assert not (result["ci_high"] < 0).any()


def test_market_incremental_info_flags_low_n(e6_module) -> None:
    df = _synthetic_df(n=60, seed=3)
    result = e6_module.market_incremental_info_test(df)
    assert result["incertitude_elevee"].any()


# --- model_incremental_info_test -------------------------------------------


def test_model_incremental_info_detects_real_model_signal(e6_module) -> None:
    df = _synthetic_df(n=4000, seed=4, market_informative=False, model_informative=True)
    result = e6_module.model_incremental_info_test(df)
    assert (result["ci_low"] > 0).any()


def test_model_and_market_tests_use_natural_thresholds_not_searched(e6_module) -> None:
    import ast

    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    source = Path(_SCRIPT_PATH).read_text()
    assert "_MARKET_NATURAL_SPLIT = 0.50" in source
    assert "_MODEL_NATURAL_SPLIT = 2.5" in source
    # aucune boucle de recherche de seuil (ex. range() sur un seuil) dans le module
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and "incremental_info" in node.name:
            func_source = ast.unparse(node)
            assert "range(" not in func_source
            assert "argmin" not in func_source and "argmax" not in func_source


# --- discrimination_summary -------------------------------------------------


def test_discrimination_summary_reuses_brier_decomposition_keys(e6_module) -> None:
    df = _synthetic_df()
    summary = e6_module.discrimination_summary(df)
    assert set(summary["decomp_model"]) >= {"reliability", "resolution", "uncertainty"}
    assert set(summary["decomp_market"]) >= {"reliability", "resolution", "uncertainty"}
    assert -1.0 <= summary["corr_expected_total"] <= 1.0


# --- build_e6_dataframe (integration-light, synthetic stage8/stage13-like inputs) --


def test_build_e6_dataframe_excludes_matches_without_market_odds(e6_module) -> None:
    stage13 = e6_module._load_stage13()

    calibration_df = pd.DataFrame(
        {
            "match_id": [f"c{i}" for i in range(200)],
            "total_goals": np.random.default_rng(0).poisson(2.5, size=200),
            "poisson_simple_p_over_2.5": np.random.default_rng(1).uniform(0.2, 0.8, size=200),
            "poisson_simple_lambda_plus_mu": np.random.default_rng(2).uniform(1.5, 4.0, size=200),
        }
    )
    test_df = pd.DataFrame(
        {
            "match_id": ["t1", "t2"],
            "league": ["premier_league", "premier_league"],
            "season": ["2024_25", "2024_25"],
            "total_goals": [3, 2],
            "poisson_simple_p_over_2.5": [0.55, 0.45],
            "poisson_simple_lambda_plus_mu": [2.8, 2.2],
        }
    )
    odds_by_match_id = {"t1": (1.8, 2.0)}  # t2 absent

    df = e6_module.build_e6_dataframe("poisson_simple", calibration_df, test_df, odds_by_match_id, stage13)
    assert list(df["match_id"]) == ["t1"]


def test_build_e6_dataframe_market_prob_matches_overround_removal(e6_module) -> None:
    from sys_foot_quant.market_engine.overround import remove_overround_proportional

    stage13 = e6_module._load_stage13()
    calibration_df = pd.DataFrame(
        {
            "match_id": [f"c{i}" for i in range(200)],
            "total_goals": np.random.default_rng(0).poisson(2.5, size=200),
            "xg_model_p_over_2.5": np.random.default_rng(1).uniform(0.2, 0.8, size=200),
            "xg_model_lambda_plus_mu": np.random.default_rng(2).uniform(1.5, 4.0, size=200),
        }
    )
    test_df = pd.DataFrame(
        {
            "match_id": ["t1"],
            "league": ["ligue1"],
            "season": ["2025_26"],
            "total_goals": [4],
            "xg_model_p_over_2.5": [0.6],
            "xg_model_lambda_plus_mu": [3.1],
        }
    )
    odds_by_match_id = {"t1": (1.7, 2.1)}
    df = e6_module.build_e6_dataframe("xg_model", calibration_df, test_df, odds_by_match_id, stage13)
    expected = remove_overround_proportional({"over": 1.7, "under": 2.1})["over"]
    assert df.iloc[0]["p_market_over25"] == pytest.approx(expected)
