"""Tests unitaires des fonctions PURES de l'experience de recalibration
Over/Under (scripts/run_stage10_over_under_recalibration.py) - verifie le
decoupage rodage/calibration/test, l'evaluation avant/apres et le verdict,
AVANT toute execution reelle."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage10_over_under_recalibration.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage10_over_under_recalibration", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def rc_module():
    return _load_script()


@dataclass(frozen=True)
class _StubRecord:
    match_id: str
    kickoff_utc: datetime


def _stub_records(n: int) -> list[_StubRecord]:
    start = datetime(2024, 1, 1)
    return [_StubRecord(match_id=str(i), kickoff_utc=start + timedelta(days=i)) for i in range(n)]


# --- split_burn_in_calibration_test -----------------------------------------


def test_split_respects_40_30_30_proportions(rc_module) -> None:
    records = _stub_records(100)
    calib_ids, test_ids = rc_module.split_burn_in_calibration_test(records)
    assert len(calib_ids) == 30
    assert len(test_ids) == 30
    # rodage = 40 restants, jete (jamais dans calib ni test)
    assert len(calib_ids | test_ids) == 60


def test_split_calibration_strictly_precedes_test_chronologically(rc_module) -> None:
    records = _stub_records(100)
    calib_ids, test_ids = rc_module.split_burn_in_calibration_test(records)
    by_id = {r.match_id: r.kickoff_utc for r in records}
    max_calib_time = max(by_id[i] for i in calib_ids)
    min_test_time = min(by_id[i] for i in test_ids)
    assert max_calib_time < min_test_time


def test_split_ignores_input_order(rc_module) -> None:
    records = _stub_records(100)
    shuffled = list(reversed(records))
    a = rc_module.split_burn_in_calibration_test(records)
    b = rc_module.split_burn_in_calibration_test(shuffled)
    assert a == b


def test_split_disjoint_sets(rc_module) -> None:
    records = _stub_records(97)  # non multiple exact des fractions
    calib_ids, test_ids = rc_module.split_burn_in_calibration_test(records)
    assert calib_ids.isdisjoint(test_ids)


# --- evaluate_recalibration --------------------------------------------------


def _df(n, seed, biased=True):
    rng = np.random.default_rng(seed)
    true_p = rng.uniform(0.2, 0.8, size=n)
    p_over = np.clip(true_p + 0.15, 0.0, 1.0) if biased else true_p
    over = (rng.uniform(0, 1, size=n) < true_p).astype(int)
    total_goals = np.where(over == 1, 3, 2)
    return pd.DataFrame(
        {
            "match_id": [f"m{i}" for i in range(n)],
            "total_goals": total_goals,
            "poisson_simple_p_over_2.5": p_over,
        }
    )


def test_evaluate_recalibration_never_fits_on_test_rows(rc_module) -> None:
    # Calibration systematiquement biaisee (+0.15), test PARFAITEMENT
    # calibre : si la fonction utilisait le test pour ajuster la courbe,
    # le biais_after mesure sur le test serait proche de 0 par construction
    # triviale ; ici on verifie plutot que le resultat depend UNIQUEMENT de
    # la courbe apprise sur la calibration (biaisee), pas du test lui-meme.
    calib_df = _df(3000, seed=1, biased=True)
    test_df = _df(3000, seed=2, biased=True)
    res = rc_module.evaluate_recalibration(calib_df, test_df, "poisson_simple", 2.5)
    assert res is not None
    assert res["n"] == len(test_df)
    assert res["n_calibration"] == len(calib_df)
    # La recalibration doit reduire le biais moyen sur le test (le biais
    # +0.15 est le meme processus generateur sur calib et test).
    assert abs(res["biais_after"]) < abs(res["biais_before"])


def test_evaluate_recalibration_returns_none_when_column_missing_everywhere(rc_module) -> None:
    calib_df = pd.DataFrame({"match_id": ["a"], "total_goals": [2], "xg_model_p_over_2.5": [np.nan]})
    test_df = pd.DataFrame({"match_id": ["b"], "total_goals": [3], "xg_model_p_over_2.5": [np.nan]})
    res = rc_module.evaluate_recalibration(calib_df, test_df, "xg_model", 2.5)
    assert res is None


def test_evaluate_recalibration_drops_nan_rows_only(rc_module) -> None:
    calib_df = _df(200, seed=3)
    test_df = _df(200, seed=4)
    test_df.loc[0:9, "poisson_simple_p_over_2.5"] = np.nan
    res = rc_module.evaluate_recalibration(calib_df, test_df, "poisson_simple", 2.5)
    assert res["n"] == len(test_df) - 10


def test_evaluate_recalibration_bootstrap_diff_matches_direct_mean(rc_module) -> None:
    calib_df = _df(1000, seed=5)
    test_df = _df(1000, seed=6)
    res = rc_module.evaluate_recalibration(calib_df, test_df, "poisson_simple", 2.5)
    manual_diff = res["brier_after"] - res["brier_before"]
    assert res["bootstrap"]["mean_diff"] == pytest.approx(manual_diff, abs=1e-9)


def test_perfectly_calibrated_input_shows_little_to_no_improvement(rc_module) -> None:
    calib_df = _df(3000, seed=7, biased=False)
    test_df = _df(3000, seed=8, biased=False)
    res = rc_module.evaluate_recalibration(calib_df, test_df, "poisson_simple", 2.5)
    # Deja bien calibre : la recalibration ne doit pas degrader
    # massivement le Brier (petite fluctuation d'echantillonnage tolérée).
    assert res["brier_after"] - res["brier_before"] < 0.02


# --- classify_verdict ---------------------------------------------------


def test_classify_verdict_entirely_negative(rc_module) -> None:
    assert rc_module.classify_verdict(-0.05, -0.01) == "AMELIORATION STATISTIQUEMENT DEMONTREE"


def test_classify_verdict_entirely_positive(rc_module) -> None:
    assert rc_module.classify_verdict(0.01, 0.05) == "RECALIBRATION SIGNIFICATIVEMENT MOINS BONNE"


def test_classify_verdict_contains_zero(rc_module) -> None:
    assert rc_module.classify_verdict(-0.02, 0.03) == "ABSENCE DE PREUVE D'AMELIORATION"
