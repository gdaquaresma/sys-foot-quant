"""Tests unitaires des fonctions PURES d'E10
(scripts/run_stage19_e10_disagreement_reliability.py) - avant toute
execution reelle."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage19_e10_disagreement_reliability.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage19_e10_disagreement_reliability", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e10_module():
    return _load_script()


# --- classify_gap_bin --------------------------------------------------------


@pytest.mark.parametrize(
    "gap,expected",
    [
        # Convention identique a pd.cut(..., right=False) d'E5 : bornes
        # fermees a gauche, ouvertes a droite - la valeur exacte de la
        # borne appartient donc a la tranche SUIVANTE (superieure).
        (-0.50, "<=-15pts"),
        (-0.1501, "<=-15pts"),
        (-0.15, "-15/-10"),
        (-0.1499, "-15/-10"),
        (-0.10, "-10/-5"),
        (-0.0999, "-10/-5"),
        (-0.05, "-5/+5"),
        (-0.0499, "-5/+5"),
        (0.0, "-5/+5"),
        (0.0499, "-5/+5"),
        (0.05, "+5/+10"),
        (0.0999, "+5/+10"),
        (0.10, "+10/+15"),
        (0.1499, "+10/+15"),
        (0.15, ">=+15pts"),
        (0.90, ">=+15pts"),
    ],
)
def test_classify_gap_bin_boundaries(e10_module, gap, expected) -> None:
    assert e10_module.classify_gap_bin(gap) == expected


def test_classify_gap_bin_never_takes_outcome_argument(e10_module) -> None:
    import inspect

    sig = inspect.signature(e10_module.classify_gap_bin)
    assert list(sig.parameters) == ["gap"]


# --- classify_agreement_zone -------------------------------------------------


@pytest.mark.parametrize(
    "gap,expected_zone",
    [
        (0.0, "accord (|gap|<5)"),
        (0.049, "accord (|gap|<5)"),
        (-0.049, "accord (|gap|<5)"),
        (0.05, "desaccord modere (5-10)"),
        (-0.05, "desaccord modere (5-10)"),
        (0.099, "desaccord modere (5-10)"),
        (0.10, "desaccord important (10-15)"),
        (0.149, "desaccord important (10-15)"),
        (0.15, "desaccord extreme (>=15)"),
        (0.90, "desaccord extreme (>=15)"),
        (-0.90, "desaccord extreme (>=15)"),
    ],
)
def test_classify_agreement_zone_boundaries(e10_module, gap, expected_zone) -> None:
    assert e10_module.classify_agreement_zone(gap) == expected_zone


def test_classify_agreement_zone_never_takes_outcome_argument(e10_module) -> None:
    import inspect

    sig = inspect.signature(e10_module.classify_agreement_zone)
    assert list(sig.parameters) == ["gap"]


# --- reliability_table --------------------------------------------------------


def _synthetic_df(n_per_bin: int = 40) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    rows = []
    for label, base_p in zip(["A", "B"], [0.4, 0.6]):
        p = np.clip(rng.normal(base_p, 0.02, size=n_per_bin), 0.01, 0.99)
        y = rng.binomial(1, base_p, size=n_per_bin).astype(float)
        for pi, yi in zip(p, y):
            rows.append({"gap_bin": label, "p_model": pi, "outcome": yi})
    return pd.DataFrame(rows)


def test_reliability_table_basic_columns(e10_module) -> None:
    df = _synthetic_df()
    table = e10_module.reliability_table(df, "gap_bin", ["A", "B"])
    assert list(table["categorie"]) == ["A", "B"]
    assert (table["n"] == 40).all()
    assert not table["incertitude_elevee"].any()


def test_reliability_table_empty_bin_flagged_uncertain(e10_module) -> None:
    df = _synthetic_df()
    table = e10_module.reliability_table(df, "gap_bin", ["A", "B", "C"])
    row_c = table[table["categorie"] == "C"].iloc[0]
    assert row_c["n"] == 0
    assert row_c["incertitude_elevee"] is True or bool(row_c["incertitude_elevee"]) is True


def test_reliability_table_small_bin_flagged_uncertain(e10_module) -> None:
    df = pd.DataFrame({"gap_bin": ["A"] * 5, "p_model": [0.5] * 5, "outcome": [1.0, 0.0, 1.0, 0.0, 1.0]})
    table = e10_module.reliability_table(df, "gap_bin", ["A"])
    assert bool(table.iloc[0]["incertitude_elevee"]) is True  # n=5 < 30


def test_reliability_table_bias_matches_manual(e10_module) -> None:
    df = pd.DataFrame({"gap_bin": ["A"] * 4, "p_model": [0.5, 0.5, 0.5, 0.5], "outcome": [1.0, 1.0, 0.0, 0.0]})
    table = e10_module.reliability_table(df, "gap_bin", ["A"])
    row = table.iloc[0]
    assert row["p_model_moyen"] == pytest.approx(0.5)
    assert row["frequence_observee"] == pytest.approx(0.5)
    assert row["biais"] == pytest.approx(0.0)


# --- asymmetry_test -----------------------------------------------------------


def test_asymmetry_test_splits_by_gap_sign(e10_module) -> None:
    df = pd.DataFrame(
        {
            "gap": [0.10, 0.08, -0.08, -0.12],
            "p_model": [0.6, 0.55, 0.45, 0.40],
            "outcome": [1.0, 0.0, 1.0, 0.0],
        }
    )
    out = e10_module.asymmetry_test(df)
    assert out["n_model_above_market"] == 2
    assert out["n_model_below_market"] == 2
    assert out["boot"] is not None


def test_asymmetry_test_insufficient_data_returns_none_boot(e10_module) -> None:
    df = pd.DataFrame({"gap": [0.10], "p_model": [0.6], "outcome": [1.0]})
    out = e10_module.asymmetry_test(df)
    assert out["boot"] is None


# --- brier_diff_vs_agreement_zone --------------------------------------------


def test_brier_diff_vs_agreement_zone_computes_when_enough_data(e10_module) -> None:
    rng = np.random.default_rng(1)
    n = 20
    df = pd.DataFrame(
        {
            "zone": ["accord (|gap|<5)"] * n + ["desaccord modere (5-10)"] * n,
            "p_model": np.concatenate([rng.uniform(0.4, 0.6, n), rng.uniform(0.4, 0.6, n)]),
            "outcome": rng.binomial(1, 0.5, size=2 * n).astype(float),
        }
    )
    out = e10_module.brier_diff_vs_agreement_zone(df, "desaccord modere (5-10)")
    assert out is not None
    assert out["n_accord"] == n
    assert out["n_desaccord"] == n


def test_brier_diff_vs_agreement_zone_none_when_insufficient(e10_module) -> None:
    df = pd.DataFrame({"zone": ["accord (|gap|<5)"], "p_model": [0.5], "outcome": [1.0]})
    out = e10_module.brier_diff_vs_agreement_zone(df, "desaccord extreme (>=15)")
    assert out is None
