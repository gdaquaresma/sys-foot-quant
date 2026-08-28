"""Tests unitaires des fonctions PURES d'E3 (agregation de rapport
uniquement - aucune nouvelle metrique statistique, voir
scripts/run_stage11_e3_reliability_validation.py) - avant toute
execution reelle."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage11_e3_reliability_validation.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage11_e3_reliability_validation", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e3_module():
    return _load_script()


def _bins_df(rows: dict[float, tuple[int, float, float]]) -> pd.DataFrame:
    """``rows`` : {bin_lo: (count, mean_predicted, observed_frequency)}
    pour toutes les tranches 0.0..0.9 - construit un DataFrame au meme
    format que ``reliability_bins`` (10 tranches fixes)."""
    edges = np.linspace(0.0, 1.0, 11)
    out = []
    for i in range(10):
        lo = round(edges[i], 1)
        count, mp, of = rows.get(lo, (0, float("nan"), float("nan")))
        out.append({"bin_lo": lo, "bin_hi": round(edges[i + 1], 1), "mean_predicted": mp, "observed_frequency": of, "count": count})
    return pd.DataFrame(out)


def test_merge_bins_80_plus_weighted_average(e3_module) -> None:
    bins = _bins_df({0.8: (100, 0.85, 0.80), 0.9: (50, 0.95, 0.90)})
    merged = e3_module.merge_bins_80_plus(bins)
    assert merged["count"] == 150
    expected_predicted = (100 * 0.85 + 50 * 0.95) / 150
    expected_observed = (100 * 0.80 + 50 * 0.90) / 150
    assert merged["mean_predicted"] == pytest.approx(expected_predicted)
    assert merged["observed_frequency"] == pytest.approx(expected_observed)


def test_merge_bins_80_plus_ignores_empty_sub_bin(e3_module) -> None:
    bins = _bins_df({0.8: (20, 0.83, 0.75)})  # 0.9 reste vide (count=0)
    merged = e3_module.merge_bins_80_plus(bins)
    assert merged["count"] == 20
    assert merged["mean_predicted"] == pytest.approx(0.83)
    assert merged["observed_frequency"] == pytest.approx(0.75)


def test_merge_bins_80_plus_both_empty_returns_nan(e3_module) -> None:
    bins = _bins_df({})
    merged = e3_module.merge_bins_80_plus(bins)
    assert merged["count"] == 0
    assert np.isnan(merged["mean_predicted"])
    assert np.isnan(merged["observed_frequency"])


def test_merge_bins_80_plus_never_touches_other_bins(e3_module) -> None:
    bins = _bins_df({0.5: (40, 0.55, 0.50), 0.8: (10, 0.85, 0.9), 0.9: (10, 0.95, 1.0)})
    merged = e3_module.merge_bins_80_plus(bins)
    assert merged["count"] == 20  # ne compte pas la tranche 0.5


def test_practical_zone_readout_returns_four_zones_in_order(e3_module) -> None:
    bins = _bins_df(
        {
            0.5: (30, 0.55, 0.52),
            0.6: (40, 0.65, 0.60),
            0.7: (50, 0.75, 0.70),
            0.8: (20, 0.85, 0.80),
            0.9: (10, 0.95, 0.90),
        }
    )
    rows = e3_module.practical_zone_readout(bins)
    assert [r["zone"] for r in rows] == ["50-60%", "60-70%", "70-80%", "80%+"]
    assert rows[0]["count"] == 30
    assert rows[1]["count"] == 40
    assert rows[2]["count"] == 50
    assert rows[3]["count"] == 30  # fusion 0.8+0.9


def test_practical_zone_readout_matches_source_bins_exactly() -> None:
    module = _load_script()
    bins = _bins_df({0.5: (77, 0.53, 0.49), 0.6: (0, float("nan"), float("nan")), 0.7: (12, 0.71, 0.83)})
    rows = module.practical_zone_readout(bins)
    zone_60 = next(r for r in rows if r["zone"] == "60-70%")
    assert zone_60["count"] == 0
    zone_50 = next(r for r in rows if r["zone"] == "50-60%")
    assert zone_50["mean_predicted"] == pytest.approx(0.53)
    assert zone_50["observed_frequency"] == pytest.approx(0.49)


def test_practical_zone_readout_reuses_reliability_bins_output_directly() -> None:
    from sys_foot_quant.calibration_engine.reliability import reliability_bins

    module = _load_script()
    rng = np.random.default_rng(0)
    probs = rng.uniform(0, 1, size=1000)
    outcomes = (rng.uniform(0, 1, size=1000) < probs).astype(float)
    bins = reliability_bins(probs, outcomes, n_bins=10)
    rows = module.practical_zone_readout(bins)
    total_from_zones = sum(r["count"] for r in rows)
    total_from_bins = int(bins[bins["bin_lo"] >= 0.5]["count"].sum())
    assert total_from_zones == total_from_bins
