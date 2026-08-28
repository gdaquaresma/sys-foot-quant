"""Tests unitaires des fonctions PURES du diagnostic de calibration
Over/Under (scripts/run_stage9_over_under_calibration_diagnostic.py) -
verifie les calculs avant toute execution reelle."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage9_over_under_calibration_diagnostic.py"
)


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage9_over_under_calibration_diagnostic", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def diag_module():
    return _load_script()


def _synthetic_df(n: int = 400, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    leagues = rng.choice(["premier_league", "ligue1", "liga"], size=n)
    seasons = rng.choice(["2024_25", "2025_26"], size=n)
    p_over_25 = rng.uniform(0.2, 0.8, size=n)
    total_goals = rng.poisson(3.0, size=n)
    p_over_25_xg = np.clip(p_over_25 + rng.normal(0, 0.05, size=n), 0.01, 0.99)
    return pd.DataFrame(
        {
            "league": leagues,
            "season": seasons,
            "total_goals": total_goals,
            "poisson_simple_p_over_2.5": p_over_25,
            "xg_model_p_over_2.5": p_over_25_xg,
        }
    )


def test_analyze_over_under_returns_expected_keys(diag_module) -> None:
    df = _synthetic_df()
    res = diag_module.analyze_over_under(df, "poisson_simple", 2.5)
    assert set(res) == {"n", "bins", "decomposition", "monotonicity"}
    assert res["n"] == len(df)
    assert isinstance(res["bins"], pd.DataFrame)
    assert "biais" in res["bins"].columns


def test_analyze_over_under_bias_column_matches_manual_diff(diag_module) -> None:
    df = _synthetic_df()
    res = diag_module.analyze_over_under(df, "poisson_simple", 2.5)
    bins = res["bins"]
    manual = bins["mean_predicted"] - bins["observed_frequency"]
    assert np.allclose(bins["biais"].to_numpy(), manual.to_numpy(), equal_nan=True)


def test_analyze_over_under_drops_nan_predictions(diag_module) -> None:
    df = _synthetic_df()
    df.loc[0:9, "poisson_simple_p_over_2.5"] = np.nan
    res = diag_module.analyze_over_under(df, "poisson_simple", 2.5)
    assert res["n"] == len(df) - 10


def test_stability_by_group_covers_all_matches(diag_module) -> None:
    df = _synthetic_df()
    stab = diag_module.stability_by_group(df, "poisson_simple", 2.5, "league")
    total_n = sum(v["n"] for v in stab.values())
    assert total_n == len(df)
    assert set(stab.keys()) == set(df["league"].unique())


def test_stability_by_group_bias_matches_direct_computation(diag_module) -> None:
    df = _synthetic_df()
    stab = diag_module.stability_by_group(df, "poisson_simple", 2.5, "season")
    for season, s in stab.items():
        sub = df[df["season"] == season]
        expected = float(
            sub["poisson_simple_p_over_2.5"].mean() - (sub["total_goals"] > 2.5).astype(float).mean()
        )
        assert s["biais"] == pytest.approx(expected)


def test_perfectly_calibrated_synthetic_probabilities_have_near_zero_bias(diag_module) -> None:
    # Construit des probabilites Over 2.5 EXACTEMENT calibrees par
    # construction (resultat tire selon la probabilite predite elle-meme)
    # - le biais par tranche doit etre proche de 0 partout.
    rng = np.random.default_rng(3)
    n = 5000
    p = rng.uniform(0.1, 0.9, size=n)
    over = (rng.uniform(0, 1, size=n) < p).astype(int)
    total_goals = np.where(over == 1, 3, 2)  # cale sur le seuil 2.5
    df = pd.DataFrame(
        {
            "league": ["premier_league"] * n,
            "season": ["2024_25"] * n,
            "total_goals": total_goals,
            "poisson_simple_p_over_2.5": p,
        }
    )
    res = diag_module.analyze_over_under(df, "poisson_simple", 2.5)
    non_empty = res["bins"][res["bins"]["count"] > 0]
    assert non_empty["biais"].abs().mean() < 0.05
    assert res["decomposition"]["resolution"] > 0  # discrimination reelle presente
