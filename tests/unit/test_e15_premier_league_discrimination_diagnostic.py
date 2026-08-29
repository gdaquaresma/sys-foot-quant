"""Tests unitaires des fonctions PURES d'E15
(scripts/run_stage24_e15_premier_league_discrimination_diagnostic.py) -
avant toute execution reelle."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage24_e15_premier_league_discrimination_diagnostic.py"
)


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage24_e15_premier_league_discrimination_diagnostic", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e15_module():
    return _load_script()


# --- frequency_table / distribution_moments -----------------------------------


def test_frequency_table_sums_to_one(e15_module) -> None:
    goals = np.array([0, 1, 1, 2, 3, 6, 7, 8])
    freq = e15_module.frequency_table(goals)
    assert sum(freq.values()) == pytest.approx(1.0)
    assert freq["6+"] == pytest.approx(3 / 8)  # 6, 7, 8


def test_distribution_moments_poisson_like_dispersion_near_one(e15_module) -> None:
    rng = np.random.default_rng(0)
    goals = rng.poisson(2.7, size=5000)
    out = e15_module.distribution_moments(goals)
    assert out["dispersion_index"] == pytest.approx(1.0, abs=0.1)


def test_distribution_moments_reports_all_fields(e15_module) -> None:
    out = e15_module.distribution_moments(np.array([0.0, 1.0, 2.0, 3.0, 4.0]))
    assert set(out) == {"n", "mean", "var", "dispersion_index", "skewness", "excess_kurtosis"}
    assert out["n"] == 5


# --- bootstrap_statistic_diff ---------------------------------------------------


def test_bootstrap_statistic_diff_zero_when_identical_samples(e15_module) -> None:
    a = np.array([1.0, 2.0, 3.0, 4.0, 5.0] * 10)
    out = e15_module.bootstrap_statistic_diff(a, a, np.mean, n_resamples=500)
    assert out["mean_diff"] == pytest.approx(0.0)
    assert out["ci_low"] <= 0.0 <= out["ci_high"]


def test_bootstrap_statistic_diff_detects_large_difference(e15_module) -> None:
    rng = np.random.default_rng(0)
    a = rng.normal(10.0, 0.5, size=200)
    b = rng.normal(0.0, 0.5, size=200)
    out = e15_module.bootstrap_statistic_diff(a, b, np.mean, n_resamples=500)
    assert out["ci_low"] > 0.0  # difference significative et positive


# --- prediction_spread_summary --------------------------------------------------


def test_prediction_spread_summary_basic(e15_module) -> None:
    expected = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    out = e15_module.prediction_spread_summary(expected)
    assert out["n"] == 5
    assert out["mean"] == pytest.approx(3.0)
    assert out["median"] == pytest.approx(3.0)
    assert out["iqr"] == pytest.approx(out["q75"] - out["q25"])


def test_prediction_spread_summary_detects_compression(e15_module) -> None:
    wide = np.array([1.0, 2.0, 3.0, 4.0, 5.0] * 20)
    narrow = np.array([2.9, 3.0, 3.1] * 20)
    s_wide = e15_module.prediction_spread_summary(wide)
    s_narrow = e15_module.prediction_spread_summary(narrow)
    assert s_narrow["std"] < s_wide["std"]
    assert s_narrow["iqr"] < s_wide["iqr"]


# --- bootstrap_correlation_ci / bootstrap_correlation_diff ----------------------


def test_bootstrap_correlation_ci_perfect_correlation(e15_module) -> None:
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0] * 10)
    y = x.copy()
    out = e15_module.bootstrap_correlation_ci(x, y, n_resamples=500)
    assert out["corr"] == pytest.approx(1.0)
    assert out["ci_low"] > 0.9


def test_bootstrap_correlation_diff_zero_when_same_relationship(e15_module) -> None:
    rng = np.random.default_rng(0)
    x_a = rng.uniform(0, 5, size=200)
    y_a = x_a + rng.normal(0, 0.5, size=200)
    x_b = rng.uniform(0, 5, size=200)
    y_b = x_b + rng.normal(0, 0.5, size=200)
    out = e15_module.bootstrap_correlation_diff(x_a, y_a, x_b, y_b, n_resamples=500)
    assert out["ci_low"] <= 0.0 <= out["ci_high"]


def test_bootstrap_correlation_diff_detects_real_difference(e15_module) -> None:
    rng = np.random.default_rng(0)
    x_a = rng.uniform(0, 5, size=300)
    y_a = x_a + rng.normal(0, 0.2, size=300)  # forte correlation
    x_b = rng.uniform(0, 5, size=300)
    y_b = rng.normal(0, 1, size=300)  # aucune correlation
    out = e15_module.bootstrap_correlation_diff(x_a, y_a, x_b, y_b, n_resamples=500)
    assert out["ci_low"] > 0.0


# --- permutation_test_correlation_diff -----------------------------------------


def test_permutation_test_correlation_diff_high_p_when_no_real_difference(e15_module) -> None:
    rng = np.random.default_rng(0)
    x = rng.uniform(0, 5, size=400)
    y = x + rng.normal(0, 0.5, size=400)  # meme relation partout, groupe non informatif
    group_mask = rng.uniform(size=400) < 0.5
    out = e15_module.permutation_test_correlation_diff(x, y, group_mask, n_permutations=300)
    assert out["p_value"] > 0.05


def test_permutation_test_correlation_diff_low_p_when_real_difference(e15_module) -> None:
    rng = np.random.default_rng(0)
    n = 200
    x_a = rng.uniform(0, 5, size=n)
    y_a = x_a + rng.normal(0, 0.2, size=n)
    x_b = rng.uniform(0, 5, size=n)
    y_b = rng.normal(0, 1, size=n)
    x = np.concatenate([x_a, x_b])
    y = np.concatenate([y_a, y_b])
    group_mask = np.concatenate([np.ones(n, dtype=bool), np.zeros(n, dtype=bool)])
    out = e15_module.permutation_test_correlation_diff(x, y, group_mask, n_permutations=500)
    assert out["p_value"] < 0.05


# --- classify_calibration_discrimination ----------------------------------------


def test_classify_a_when_uncalibrated_and_not_discriminant(e15_module) -> None:
    out = e15_module.classify_calibration_discrimination((0.05, 0.15), 0.01, (-0.05, 0.07), [0.1, 0.15])
    assert out.startswith("A")


def test_classify_b_when_calibrated_not_discriminant_and_not_comparable(e15_module) -> None:
    out = e15_module.classify_calibration_discrimination((-0.02, 0.03), 0.01, (-0.05, 0.07), [0.1, 0.15])
    assert out.startswith("B")


def test_classify_c_when_calibrated_not_demonstrated_but_comparable_magnitude(e15_module) -> None:
    out = e15_module.classify_calibration_discrimination((-0.02, 0.03), 0.12, (-0.05, 0.20), [0.1, 0.15])
    assert out.startswith("C")


def test_classify_d_when_discrimination_demonstrated(e15_module) -> None:
    out = e15_module.classify_calibration_discrimination((-0.02, 0.03), 0.20, (0.05, 0.35), [0.1, 0.15])
    assert out.startswith("D")


# --- audit_league_season / cross_season_team_consistency ------------------------


def _write_raw_match(match_id: str, home_id: str, home_title: str, away_id: str, away_title: str, dt: str, hg: int = 1, ag: int = 0) -> dict:
    return {
        "id": match_id,
        "isResult": True,
        "h": {"id": home_id, "title": home_title, "short_title": home_title[:3].upper()},
        "a": {"id": away_id, "title": away_title, "short_title": away_title[:3].upper()},
        "goals": {"h": str(hg), "a": str(ag)},
        "xG": {"h": "1.2", "a": "0.8"},
        "datetime": dt,
    }


class _FakeStage8:
    """Reutilise `build_real_match_records` (production, deja teste) pour
    generer des `RealMatchRecord` a partir de fixtures minimales - jamais
    une reimplementation du parsing point-in-time."""

    def __init__(self, seasons: dict) -> None:
        self._SEASONS = seasons

    def _load_records(self, league: str, season: str):
        from sys_foot_quant.backtesting_engine.real_data_walk_forward import build_real_match_records

        league_id, path = self._SEASONS[season][league]
        with open(path) as f:
            raw = json.load(f)
        return build_real_match_records(raw, league=league_id)


def test_audit_league_season_clean_round_robin(e15_module, tmp_path: Path) -> None:
    raw = [
        _write_raw_match("1", "10", "A", "20", "B", "2024-08-01 15:00:00"),
        _write_raw_match("2", "20", "B", "10", "A", "2024-08-08 15:00:00"),
    ]
    path = tmp_path / "league.json"
    path.write_text(json.dumps(raw))
    stage8 = _FakeStage8({"2024_25": {"testleague": ("TL", path)}})
    audit = e15_module.audit_league_season("testleague", "2024_25", stage8)
    assert audit["n_matches"] == 2
    assert audit["n_teams"] == 2
    assert audit["matches_equal_round_robin"] is True
    assert audit["n_duplicate_match_ids"] == 0
    assert audit["n_team_name_conflicts"] == 0
    assert audit["n_home_away_imbalance"] == 0  # chaque equipe joue 1 fois a domicile, 1 fois a l'exterieur


def test_audit_league_season_detects_duplicate_match_id(e15_module, tmp_path: Path) -> None:
    raw = [
        _write_raw_match("1", "10", "A", "20", "B", "2024-08-01 15:00:00"),
        _write_raw_match("1", "20", "B", "10", "A", "2024-08-08 15:00:00"),  # meme id, different match
    ]
    path = tmp_path / "league.json"
    path.write_text(json.dumps(raw))
    stage8 = _FakeStage8({"2024_25": {"testleague": ("TL", path)}})
    audit = e15_module.audit_league_season("testleague", "2024_25", stage8)
    assert audit["n_duplicate_match_ids"] == 1


def test_audit_league_season_detects_team_name_conflict(e15_module, tmp_path: Path) -> None:
    raw = [
        _write_raw_match("1", "10", "A", "20", "B", "2024-08-01 15:00:00"),
        _write_raw_match("2", "20", "B", "10", "A-Renamed", "2024-08-08 15:00:00"),  # meme id "10", nom different
    ]
    path = tmp_path / "league.json"
    path.write_text(json.dumps(raw))
    stage8 = _FakeStage8({"2024_25": {"testleague": ("TL", path)}})
    audit = e15_module.audit_league_season("testleague", "2024_25", stage8)
    assert audit["n_team_name_conflicts"] == 1


def test_audit_league_season_detects_home_away_imbalance(e15_module, tmp_path: Path) -> None:
    raw = [
        _write_raw_match("1", "10", "A", "20", "B", "2024-08-01 15:00:00"),
        _write_raw_match("2", "10", "A", "30", "C", "2024-08-08 15:00:00"),  # "A" toujours a domicile
    ]
    path = tmp_path / "league.json"
    path.write_text(json.dumps(raw))
    stage8 = _FakeStage8({"2024_25": {"testleague": ("TL", path)}})
    audit = e15_module.audit_league_season("testleague", "2024_25", stage8)
    assert audit["n_home_away_imbalance"] > 0


def test_cross_season_team_consistency_flags_id_reused_for_different_team(e15_module, tmp_path: Path) -> None:
    raw1 = [_write_raw_match("1", "10", "A", "20", "B", "2024-08-01 15:00:00")]
    raw2 = [_write_raw_match("2", "10", "A-Different-Team", "20", "B", "2025-08-01 15:00:00")]
    path1, path2 = tmp_path / "s1.json", tmp_path / "s2.json"
    path1.write_text(json.dumps(raw1))
    path2.write_text(json.dumps(raw2))
    stage8 = _FakeStage8({"2024_25": {"testleague": ("TL", path1)}, "2025_26": {"testleague": ("TL", path2)}})
    cross = e15_module.cross_season_team_consistency("testleague", stage8)
    assert cross["n_id_name_conflicts_across_seasons"] == 1


def test_cross_season_team_consistency_no_conflict_on_normal_turnover(e15_module, tmp_path: Path) -> None:
    raw1 = [_write_raw_match("1", "10", "A", "20", "B", "2024-08-01 15:00:00")]
    raw2 = [_write_raw_match("2", "10", "A", "30", "C-Promoted", "2025-08-01 15:00:00")]  # "B" descend, "C" monte
    path1, path2 = tmp_path / "s1.json", tmp_path / "s2.json"
    path1.write_text(json.dumps(raw1))
    path2.write_text(json.dumps(raw2))
    stage8 = _FakeStage8({"2024_25": {"testleague": ("TL", path1)}, "2025_26": {"testleague": ("TL", path2)}})
    cross = e15_module.cross_season_team_consistency("testleague", stage8)
    assert cross["n_id_name_conflicts_across_seasons"] == 0  # "A" coherent, "B"/"C" simplement absents d'une saison
