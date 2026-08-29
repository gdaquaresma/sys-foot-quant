"""Tests des fonctions pures de run_stage28 (Phase G) - AVANT toute
execution sur donnees reelles (protocole etape 15). Script charge via
importlib (meme convention que Phase F/E16 pour un script `scripts/*.py`
non package)."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "run_stage28_phase_g_bfe_incremental_information.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage28_phase_g_bfe_incremental_information", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def stage28():
    return _load_script()


class _FakeRecord:
    def __init__(self, match_id, decision_time_utc, home_goals, away_goals, b365_1x2, bfe_1x2, b365_ou, bfe_ou, league="liga", season="2024_25"):
        self.match_id = match_id
        self.league = league
        self.season = season
        self.decision_time_utc = decision_time_utc
        self.home_goals = home_goals
        self.away_goals = away_goals
        self.total_goals = home_goals + away_goals
        self.b365_1x2 = b365_1x2
        self.bfe_1x2 = bfe_1x2
        self.b365_over_under_2_5 = b365_ou
        self.bfe_over_under_2_5 = bfe_ou


def _dt(days: int) -> datetime:
    return datetime(2024, 8, 1, tzinfo=timezone.utc) + timedelta(days=days)


# --------------------------------------------------------------------------
# build_market_dataframe / _actual_1x2_selection
# --------------------------------------------------------------------------


def test_actual_1x2_selection_home_draw_away(stage28) -> None:
    home_win = _FakeRecord("1", _dt(0), 2, 0, {"H": 1.8, "D": 3.6, "A": 4.5}, None, {}, None)
    draw = _FakeRecord("2", _dt(1), 1, 1, {"H": 1.8, "D": 3.6, "A": 4.5}, None, {}, None)
    away_win = _FakeRecord("3", _dt(2), 0, 2, {"H": 1.8, "D": 3.6, "A": 4.5}, None, {}, None)
    assert stage28._actual_1x2_selection(home_win) == "H"
    assert stage28._actual_1x2_selection(draw) == "D"
    assert stage28._actual_1x2_selection(away_win) == "A"


def test_build_market_dataframe_normalizes_probabilities_and_marks_missing_bfe(stage28) -> None:
    records = [
        _FakeRecord("1", _dt(0), 2, 0, {"H": 1.8, "D": 3.6, "A": 4.5}, {"H": 1.85, "D": 3.7, "A": 4.4}, {}, None),
        _FakeRecord("2", _dt(1), 0, 0, {"H": 1.8, "D": 3.6, "A": 4.5}, None, {}, None),  # BFE absent
    ]
    df = stage28.build_market_dataframe(records, "H")
    assert len(df) == 2
    # normalisation : somme des probas sur les 3 issues doit valoir 1 (retire de la marge)
    total = sum(stage28.remove_overround_proportional({"H": 1.8, "D": 3.6, "A": 4.5}).values())
    assert total == pytest.approx(1.0)
    assert df.loc[df["match_id"] == "1", "p_bfe"].notna().all()
    assert df.loc[df["match_id"] == "2", "p_bfe"].isna().all()
    assert df.loc[df["match_id"] == "1", "outcome"].iloc[0] == 1.0  # domicile a gagne
    assert df.loc[df["match_id"] == "2", "outcome"].iloc[0] == 0.0


def test_build_market_dataframe_over_selection_uses_over_under_odds(stage28) -> None:
    records = [
        _FakeRecord("1", _dt(0), 3, 1, {}, None, {"Over": 1.85, "Under": 1.95}, {"Over": 1.90, "Under": 1.90}),
    ]
    df = stage28.build_market_dataframe(records, "Over")
    assert len(df) == 1
    assert df.iloc[0]["outcome"] == 1.0  # 4 buts > 2.5
    assert df.iloc[0]["p_bfe"] == pytest.approx(0.5)  # cotes egales -> 50/50 apres retrait de marge


def test_build_market_dataframe_sorted_by_decision_time(stage28) -> None:
    records = [
        _FakeRecord("1", _dt(2), 1, 0, {"H": 1.8, "D": 3.6, "A": 4.5}, {"H": 1.85, "D": 3.7, "A": 4.4}, {}, None),
        _FakeRecord("2", _dt(0), 1, 0, {"H": 1.8, "D": 3.6, "A": 4.5}, {"H": 1.85, "D": 3.7, "A": 4.4}, {}, None),
    ]
    df = stage28.build_market_dataframe(records, "H")
    assert list(df["match_id"]) == ["2", "1"]


# --------------------------------------------------------------------------
# eligible_dataset
# --------------------------------------------------------------------------


def test_eligible_dataset_drops_rows_missing_bfe(stage28) -> None:
    df = pd.DataFrame(
        {
            "decision_time": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "p_b365": [0.5, 0.6],
            "p_bfe": [0.5, np.nan],
            "outcome": [1.0, 0.0],
        }
    )
    out = stage28.eligible_dataset(df)
    assert len(out) == 1
    assert out.iloc[0]["p_b365"] == 0.5


# --------------------------------------------------------------------------
# build_b365_vs_bfe : walk-forward logistique (E16, REUTILISE)
# --------------------------------------------------------------------------


def _synthetic_eligible(n: int, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    p_b365 = rng.uniform(0.3, 0.7, size=n)
    p_bfe = rng.uniform(0.3, 0.7, size=n)
    outcome = rng.integers(0, 2, size=n).astype(float)
    return pd.DataFrame(
        {
            "decision_time": pd.date_range("2024-01-01", periods=n, freq="D"),
            "league": ["liga"] * n,
            "season": ["2024_25"] * n,
            "p_b365": p_b365,
            "p_bfe": p_bfe,
            "outcome": outcome,
        }
    )


def test_build_b365_vs_bfe_drops_warmup_rows(stage28) -> None:
    e16 = stage28._load_e16()
    elig = _synthetic_eligible(50)
    compared = stage28.build_b365_vs_bfe(elig, e16)
    assert len(compared) <= 20  # min_train=30
    assert compared["p_b365_recal"].notna().all()
    assert compared["p_b365_bfe"].notna().all()


def test_build_b365_vs_bfe_never_uses_future_rows(stage28) -> None:
    e16 = stage28._load_e16()
    elig = _synthetic_eligible(40)
    compared_a = stage28.build_b365_vs_bfe(elig, e16)

    elig_perturbed = elig.copy()
    elig_perturbed.loc[elig_perturbed.index[-1], "p_bfe"] = 0.999
    elig_perturbed.loc[elig_perturbed.index[-1], "outcome"] = 1.0 - elig_perturbed.loc[elig_perturbed.index[-1], "outcome"]
    compared_b = stage28.build_b365_vs_bfe(elig_perturbed, e16)

    n_common = min(len(compared_a), len(compared_b)) - 1
    np.testing.assert_allclose(
        compared_a["p_b365_bfe"].to_numpy()[:n_common], compared_b["p_b365_bfe"].to_numpy()[:n_common]
    )


# --------------------------------------------------------------------------
# evaluate_b365_vs_bfe : Brier/logloss/calibration/resolution + bootstrap
# --------------------------------------------------------------------------


def test_evaluate_identical_predictions_yields_zero_diff(stage28) -> None:
    n = 50
    rng = np.random.default_rng(1)
    p = rng.uniform(0.3, 0.7, size=n)
    y = rng.integers(0, 2, size=n).astype(float)
    compared = pd.DataFrame({"p_b365": p, "p_b365_recal": p, "p_b365_bfe": p, "outcome": y})
    res = stage28.evaluate_b365_vs_bfe(compared)
    assert res["brier_b365"] == pytest.approx(res["brier_combo"])
    assert res["boot_brier_combo_minus_recal"]["ci_low"] == pytest.approx(0.0)
    assert res["boot_brier_combo_minus_recal"]["ci_high"] == pytest.approx(0.0)


def test_evaluate_recalibration_alone_explains_gain_is_not_falsely_validated(stage28) -> None:
    """Cas critique motivant le controle (lecon Phase F) : si B365+BFE
    n'apporte RIEN au-dela d'une simple re-calibration, le test principal
    doit rester NON concluant meme si B365+BFE bat largement B365 brut."""
    n = 200
    rng = np.random.default_rng(2)
    y = rng.integers(0, 2, size=n).astype(float)
    p_b365 = np.full(n, 0.9)  # B365 brut deliberement mal represente ici
    p_recalibrated = rng.uniform(0.3, 0.7, size=n)
    compared = pd.DataFrame({"p_b365": p_b365, "p_b365_recal": p_recalibrated, "p_b365_bfe": p_recalibrated, "outcome": y})
    res = stage28.evaluate_b365_vs_bfe(compared)
    assert res["brier_combo"] < res["brier_b365"]
    assert res["boot_brier_combo_minus_recal"]["ci_low"] == pytest.approx(0.0)
    assert res["boot_brier_combo_minus_recal"]["ci_high"] == pytest.approx(0.0)


# --------------------------------------------------------------------------
# classify_verdict : grille figee (etape 11)
# --------------------------------------------------------------------------


def test_verdict_non_valide_when_ci_overlaps_zero(stage28) -> None:
    global_res = {
        "boot_brier_combo_minus_recal": {"ci_low": -0.01, "ci_high": 0.01},
        "calibration_recal": 0.05,
        "calibration_combo": 0.05,
    }
    assert stage28.classify_verdict(global_res, []) == "NON VALIDE"


def test_verdict_valide_when_improvement_significant_and_stable(stage28) -> None:
    global_res = {
        "boot_brier_combo_minus_recal": {"ci_low": -0.05, "ci_high": -0.01},
        "calibration_recal": 0.05,
        "calibration_combo": 0.05,
    }
    scope_boots = [{"ci_low": -0.06, "ci_high": -0.005}, {"ci_low": -0.04, "ci_high": -0.002}]
    assert stage28.classify_verdict(global_res, scope_boots) == "VALIDE"


def test_verdict_non_valide_when_a_scope_inverts(stage28) -> None:
    global_res = {
        "boot_brier_combo_minus_recal": {"ci_low": -0.05, "ci_high": -0.01},
        "calibration_recal": 0.05,
        "calibration_combo": 0.05,
    }
    scope_boots = [{"ci_low": 0.001, "ci_high": 0.02}]
    assert stage28.classify_verdict(global_res, scope_boots) == "NON VALIDE"


def test_verdict_non_valide_when_only_raw_b365_is_beaten_not_the_control(stage28) -> None:
    global_res = {
        "boot_brier_combo_minus_b365": {"ci_low": -0.05, "ci_high": -0.01},
        "boot_brier_combo_minus_recal": {"ci_low": -0.01, "ci_high": 0.01},
        "calibration_recal": 0.05,
        "calibration_combo": 0.05,
    }
    assert stage28.classify_verdict(global_res, []) == "NON VALIDE"
