"""Tests des fonctions pures de run_stage32 (consensus multi-bookmaker
Max/Avg) - script charge via importlib (meme convention que
Phases F/G/H/K et Brique 1 - voir tests/unit/test_run_stage31_fixture_congestion.py)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "run_stage32_multi_bookmaker_consensus_incremental_information.py"


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "run_stage32_multi_bookmaker_consensus_incremental_information", _SCRIPT_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def stage32():
    return _load_script()


# --------------------------------------------------------------------------
# _normalized_over_prob : jamais de fuite, jamais de valeur inventee.
# --------------------------------------------------------------------------


def test_normalized_over_prob_matches_remove_overround_proportional(stage32) -> None:
    from sys_foot_quant.market_engine.overround import remove_overround_proportional

    expected = remove_overround_proportional({"Over": 1.85, "Under": 1.95})["Over"]
    assert stage32._normalized_over_prob(1.85, 1.95) == pytest.approx(expected)


def test_normalized_over_prob_is_none_when_either_side_missing(stage32) -> None:
    assert stage32._normalized_over_prob(None, 1.95) is None
    assert stage32._normalized_over_prob(1.85, None) is None
    assert stage32._normalized_over_prob(None, None) is None


# --------------------------------------------------------------------------
# classify_verdict : grille figee (3 valeurs autorisees uniquement,
# identique a Brique 1).
# --------------------------------------------------------------------------


def _boot(mean_diff, ci_low, ci_high):
    return {"mean_diff": mean_diff, "ci_low": ci_low, "ci_high": ci_high}


def test_verdict_donnees_insuffisantes_when_pool_too_small(stage32) -> None:
    v = stage32.classify_verdict(_boot(-0.01, -0.02, -0.005), n_primary=10, season_mean_diffs=[], season_ns=[])
    assert v == "DONNEES INSUFFISANTES"


def test_verdict_signal_demontre_when_favorable_and_replicated(stage32) -> None:
    v = stage32.classify_verdict(
        _boot(-0.01, -0.02, -0.005), n_primary=200, season_mean_diffs=[-0.01, -0.008], season_ns=[100, 100]
    )
    assert v == "SIGNAL DEMONTRE"


def test_verdict_signal_non_demontre_when_ci_overlaps_zero(stage32) -> None:
    v = stage32.classify_verdict(
        _boot(0.001, -0.001, 0.003), n_primary=200, season_mean_diffs=[0.001, 0.001], season_ns=[100, 100]
    )
    assert v == "SIGNAL NON DEMONTRE"


def test_verdict_donnees_insuffisantes_when_direction_unstable(stage32) -> None:
    v = stage32.classify_verdict(
        _boot(-0.01, -0.02, -0.005), n_primary=200, season_mean_diffs=[-0.02, 0.01], season_ns=[100, 100]
    )
    assert v == "DONNEES INSUFFISANTES"


def test_verdict_only_three_authorized_values_used(stage32) -> None:
    allowed = {"SIGNAL DEMONTRE", "SIGNAL NON DEMONTRE", "DONNEES INSUFFISANTES"}
    cases = [
        (_boot(-0.01, -0.02, -0.005), 200, [-0.01, -0.008], [100, 100]),
        (_boot(0.001, -0.001, 0.003), 200, [0.001, 0.001], [100, 100]),
        (_boot(-0.01, -0.02, -0.005), 5, [], []),
        (_boot(-0.01, -0.02, -0.005), 200, [-0.02, 0.01], [100, 100]),
    ]
    for primary, n, diffs, ns in cases:
        assert stage32.classify_verdict(primary, n, diffs, ns) in allowed


# --------------------------------------------------------------------------
# tag_burn_in_validation_test : meme schema que Phase K/Brique 1.
# --------------------------------------------------------------------------


def test_tag_burn_in_validation_test_labels_rows_correctly(stage32) -> None:
    fake_record = SimpleNamespace()

    class _FakeStage10:
        @staticmethod
        def split_burn_in_calibration_test(records):
            return {"m2"}, {"m3"}

    class _FakeStage8:
        _SEASONS = {"2024_25": ["liga"]}

        @staticmethod
        def _load_records(league, season):
            return [fake_record]

    df = pd.DataFrame({"match_id": ["m1", "m2", "m3"], "league": ["liga"] * 3, "season": ["2024_25"] * 3})
    tagged = stage32.tag_burn_in_validation_test(df, _FakeStage10(), _FakeStage8())
    assert list(tagged["split"]) == ["burn_in", "validation", "test"]


# --------------------------------------------------------------------------
# load_all_multi_bookmaker_records : non-regression sur le corpus reel.
# --------------------------------------------------------------------------


def test_load_all_multi_bookmaker_records_covers_the_real_corpus(stage32) -> None:
    records = stage32.load_all_multi_bookmaker_records()
    assert len(records) > 2000  # 2123 matchs apparies attendus (ADR 0006)
    sample = next(iter(records.values()))
    assert sample.has_complete_b365 is True  # couverture B365 100% deja etablie


def test_load_all_multi_bookmaker_records_avg_coverage_is_near_complete(stage32) -> None:
    records = stage32.load_all_multi_bookmaker_records()
    n_with_avg = sum(1 for r in records.values() if r.has_complete_avg)
    # Couverture Avg constatee a 100% sur les six fichiers (section 0 du
    # protocole) - au moins 99% attendu apres appariement Understat (une
    # marge est laissee pour les tres rares residus deja documentes par
    # l'ADR 0006, jamais lies a Avg lui-meme).
    assert n_with_avg / len(records) >= 0.99


# --------------------------------------------------------------------------
# build_full_dataset : exclusion explicite si un marche est incomplet
# (synthetique, rapide).
# --------------------------------------------------------------------------


def test_build_full_dataset_excludes_rows_with_missing_market(stage32, monkeypatch) -> None:
    class _FakeE7:
        @staticmethod
        def build_lambda_mu_dataframe(stage8_module):
            return pd.DataFrame(
                {
                    "match_id": ["m1", "m2"],
                    "poisson_simple_lambda": [1.2, 1.3],
                    "poisson_simple_mu": [1.0, 1.1],
                    "total_goals": [3, 1],
                }
            )

    class _FakeE8:
        @staticmethod
        def build_decision_time_lookup(stage8_module):
            return pd.Series(
                pd.to_datetime(["2025-08-09 18:00", "2025-08-16 18:00"], utc=True), index=["m1", "m2"]
            )

    class _FakeCalibrated:
        probabilities = {2.5: 0.5}

    monkeypatch.setattr(stage32, "calibrate_prediction", lambda pred, pool, as_of_time: _FakeCalibrated())

    class _FakeRecord:
        def __init__(self, b365, avg, max_):
            self.b365_over_2_5, self.b365_under_2_5 = b365
            self.avg_over_2_5, self.avg_under_2_5 = avg
            self.max_over_2_5, self.max_under_2_5 = max_

    # m1 : les trois marches complets ; m2 : Avg manquant.
    multi_bk = {
        "m1": _FakeRecord((1.85, 1.95), (1.87, 1.90), (1.92, 1.98)),
        "m2": _FakeRecord((1.85, 1.95), (None, None), (1.92, 1.98)),
    }

    df, n_excluded = stage32.build_full_dataset(_FakeE7(), _FakeE8(), SimpleNamespace(), multi_bk)
    assert list(df["match_id"]) == ["m1"]
    assert n_excluded["no_avg"] == 1
    assert n_excluded["total_excluded"] == 1


# --------------------------------------------------------------------------
# Controle de recalibration : si le marche (Avg) est du bruit pur
# (independant du resultat), le modele test_Avg ne doit jamais ameliorer
# significativement C - meme schema que Phases F/G/H/K/Brique 1.
# --------------------------------------------------------------------------


def test_recalibration_alone_explains_gain_is_not_falsely_validated(stage32) -> None:
    e16 = stage32._load_e16()
    rng = np.random.default_rng(4)
    n = 400
    y = rng.integers(0, 2, size=n).astype(float)
    p_a = np.full(n, 0.85)  # tres mal calibre (sur-confiant), constant
    p_market_noise = np.clip(rng.uniform(0.3, 0.7, size=n), 1e-3, 1 - 1e-3)  # bruit pur, independant de y

    logit_p_a = np.log(p_a / (1 - p_a))
    logit_market = np.log(p_market_noise / (1 - p_market_noise))
    ones = np.ones(n)

    X_c = np.column_stack([ones, logit_p_a])
    X_test = np.column_stack([ones, logit_p_a, logit_market])

    p_c = np.full(n, np.nan)
    p_test = np.full(n, np.nan)
    for i in range(30, n):
        p_c[i] = e16.predict_logistic(e16.fit_logistic(X_c[:i], y[:i]), X_c[i : i + 1])[0]
        p_test[i] = e16.predict_logistic(e16.fit_logistic(X_test[:i], y[:i]), X_test[i : i + 1])[0]

    mask = ~np.isnan(p_c) & ~np.isnan(p_test)
    diffs = (p_test[mask] - y[mask]) ** 2 - (p_c[mask] - y[mask]) ** 2

    from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test

    res = paired_bootstrap_test(diffs, n_resamples=2000, seed=0)
    assert not (res["ci_high"] < 0.0)
