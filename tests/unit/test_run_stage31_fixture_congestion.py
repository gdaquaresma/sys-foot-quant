"""Tests des fonctions pures de run_stage31 (congestion intra-championnat,
Brique 1) - script charge via importlib (meme convention que Phases
F/G/H/K, voir tests/unit/test_run_stage30_phase_k.py)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "run_stage31_fixture_congestion_incremental_information.py"


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "run_stage31_fixture_congestion_incremental_information", _SCRIPT_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def stage31():
    return _load_script()


# --------------------------------------------------------------------------
# fit_logistic_with_offset / walk_forward_logistic_with_offset : non-
# regression (translitteres de Phase K) - l'offset (logit(p_A)) a un
# coefficient fixe a 1, jamais de fuite vers le futur.
# --------------------------------------------------------------------------


def test_fit_logistic_with_offset_zero_reproduces_plain_logistic(stage31) -> None:
    e16 = stage31._load_e16()
    rng = np.random.default_rng(0)
    n = 200
    x1 = rng.uniform(-2, 2, size=n)
    X = np.column_stack([np.ones(n), x1])
    true_beta = np.array([0.3, 1.5])
    p_true = 1.0 / (1.0 + np.exp(-(X @ true_beta)))
    y = (rng.uniform(size=n) < p_true).astype(float)

    beta_plain = e16.fit_logistic(X, y)
    beta_offset = stage31.fit_logistic_with_offset(np.zeros(n), X, y)
    np.testing.assert_allclose(beta_plain, beta_offset, atol=1e-6)


def test_predict_logistic_with_offset_matches_manual_sigmoid(stage31) -> None:
    offset = np.array([0.5])
    beta = np.array([0.2, -0.1])
    X = np.array([[1.0, 3.0]])
    pred = stage31.predict_logistic_with_offset(offset, beta, X)[0]
    expected = 1.0 / (1.0 + np.exp(-(0.5 + 0.2 * 1.0 - 0.1 * 3.0)))
    assert pred == pytest.approx(expected)


def test_walk_forward_logistic_with_offset_drops_warmup_rows(stage31) -> None:
    rng = np.random.default_rng(2)
    n = 50
    offset = rng.normal(0, 1, size=n)
    X = np.column_stack([np.ones(n), rng.uniform(-1, 1, size=n), rng.uniform(-1, 1, size=n)])
    y = rng.integers(0, 2, size=n).astype(float)
    preds = stage31.walk_forward_logistic_with_offset(offset, X, y, min_train=30)
    assert np.isnan(preds[:30]).all()
    assert not np.isnan(preds[30:]).any()


def test_walk_forward_logistic_with_offset_never_uses_future_rows(stage31) -> None:
    rng = np.random.default_rng(3)
    n = 40
    offset = rng.normal(0, 1, size=n)
    X = np.column_stack([np.ones(n), rng.uniform(-1, 1, size=n), rng.uniform(-1, 1, size=n)])
    y = rng.integers(0, 2, size=n).astype(float)

    preds_a = stage31.walk_forward_logistic_with_offset(offset, X, y, min_train=30)

    offset_b, X_b, y_b = offset.copy(), X.copy(), y.copy()
    offset_b[-1] = 999.0
    X_b[-1, 1:] = 999.0
    y_b[-1] = 1.0 - y_b[-1]
    preds_b = stage31.walk_forward_logistic_with_offset(offset_b, X_b, y_b, min_train=30)

    n_common = n - 1
    np.testing.assert_allclose(preds_a[:n_common], preds_b[:n_common])


# --------------------------------------------------------------------------
# Deux covariables separees (home/away) - le point methodologique central
# de cette etape (section 1/6 du protocole) : le modele D doit pouvoir
# capter un effet ASYMETRIQUE que la seule variante rest_days_diff (E)
# confondrait.
# --------------------------------------------------------------------------


def test_separate_home_away_covariates_capture_asymmetric_effect_that_diff_cannot() -> None:
    e16_spec = importlib.util.spec_from_file_location(
        "run_stage25_e16", _REPO_ROOT / "scripts" / "run_stage25_e16_market_movement_information.py"
    )
    e16 = importlib.util.module_from_spec(e16_spec)
    sys.modules[e16_spec.name] = e16
    e16_spec.loader.exec_module(e16)

    rng = np.random.default_rng(7)
    n = 400
    home_rest = rng.uniform(3, 10, size=n)
    away_rest = rng.uniform(3, 10, size=n)
    # Verite : SEUL home_rest_days compte (effet positif fort) ; away_rest_days
    # n'a aucun effet. rest_days_diff = home - away mélange les deux par
    # construction (un diff eleve peut venir d'un home_rest eleve OU d'un
    # away_rest faible) - un modele a covariable unique ne peut pas
    # distinguer ces deux cas, un modele a deux covariables separees le peut.
    z_true = -1.0 + 0.5 * home_rest
    p_true = 1.0 / (1.0 + np.exp(-z_true))
    y = (rng.uniform(size=n) < p_true).astype(float)
    ones = np.ones(n)

    # Modele D : deux covariables separees.
    X_d = np.column_stack([ones, home_rest, away_rest])
    beta_d = e16.fit_logistic(X_d, y)

    # Modele E : covariable unique (diff).
    rest_diff = home_rest - away_rest
    X_e = np.column_stack([ones, rest_diff])
    beta_e = e16.fit_logistic(X_e, y)

    # D doit recuperer un coefficient fort et correctement signe sur
    # home_rest_days (beta_d[1]), bien plus grand en magnitude que le
    # coefficient que E peut attribuer a un diff qui melange les deux cotes.
    assert beta_d[1] > 0.3
    assert abs(beta_d[1]) > abs(beta_e[1])


# --------------------------------------------------------------------------
# Controle de recalibration : si la congestion est du bruit pur (independant
# du resultat), le modele D ne doit jamais ameliorer significativement C -
# meme schema que Phases F/G/H/K (test_run_stage30_phase_k.py).
# --------------------------------------------------------------------------


def test_recalibration_alone_explains_gain_is_not_falsely_validated(stage31) -> None:
    e16 = stage31._load_e16()
    rng = np.random.default_rng(4)
    n = 400
    y = rng.integers(0, 2, size=n).astype(float)
    p_a = np.full(n, 0.85)  # tres mal calibre (sur-confiant), constant
    home_rest = rng.uniform(3, 10, size=n)  # bruit pur, independant de y
    away_rest = rng.uniform(3, 10, size=n)  # idem

    logit_p_a = np.log(p_a / (1 - p_a))
    ones = np.ones(n)

    X_c = np.column_stack([ones, logit_p_a])
    X_d = np.column_stack([ones, logit_p_a, home_rest, away_rest])

    p_c = np.full(n, np.nan)
    p_d = np.full(n, np.nan)
    for i in range(30, n):
        p_c[i] = e16.predict_logistic(e16.fit_logistic(X_c[:i], y[:i]), X_c[i : i + 1])[0]
        p_d[i] = e16.predict_logistic(e16.fit_logistic(X_d[:i], y[:i]), X_d[i : i + 1])[0]

    mask = ~np.isnan(p_c) & ~np.isnan(p_d)
    diffs = (p_d[mask] - y[mask]) ** 2 - (p_c[mask] - y[mask]) ** 2

    from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test

    res = paired_bootstrap_test(diffs, n_resamples=2000, seed=0)
    # Congestion = bruit pur : D ne doit jamais ameliorer significativement C.
    assert not (res["ci_high"] < 0.0)


# --------------------------------------------------------------------------
# classify_verdict : grille figee (3 valeurs autorisees uniquement,
# section 10 du protocole).
# --------------------------------------------------------------------------


def _boot(mean_diff, ci_low, ci_high):
    return {"mean_diff": mean_diff, "ci_low": ci_low, "ci_high": ci_high}


def test_verdict_donnees_insuffisantes_when_pool_too_small(stage31) -> None:
    v = stage31.classify_verdict(_boot(-0.01, -0.02, -0.005), n_primary=10, season_mean_diffs=[], season_ns=[])
    assert v == "DONNEES INSUFFISANTES"


def test_verdict_signal_demontre_when_favorable_and_replicated(stage31) -> None:
    v = stage31.classify_verdict(
        _boot(-0.01, -0.02, -0.005), n_primary=200, season_mean_diffs=[-0.01, -0.008], season_ns=[100, 100]
    )
    assert v == "SIGNAL DEMONTRE"


def test_verdict_signal_non_demontre_when_ci_overlaps_zero(stage31) -> None:
    v = stage31.classify_verdict(
        _boot(0.001, -0.001, 0.003), n_primary=200, season_mean_diffs=[0.001, 0.001], season_ns=[100, 100]
    )
    assert v == "SIGNAL NON DEMONTRE"


def test_verdict_signal_non_demontre_when_ci_entirely_positive(stage31) -> None:
    v = stage31.classify_verdict(
        _boot(0.01, 0.005, 0.02), n_primary=200, season_mean_diffs=[0.01, 0.01], season_ns=[100, 100]
    )
    assert v == "SIGNAL NON DEMONTRE"


def test_verdict_donnees_insuffisantes_when_direction_unstable_across_seasons(stage31) -> None:
    v = stage31.classify_verdict(
        _boot(-0.01, -0.02, -0.005), n_primary=200, season_mean_diffs=[-0.02, 0.01], season_ns=[100, 100]
    )
    assert v == "DONNEES INSUFFISANTES"


def test_verdict_donnees_insuffisantes_when_fewer_than_two_powered_seasons(stage31) -> None:
    v = stage31.classify_verdict(
        _boot(-0.01, -0.02, -0.005), n_primary=200, season_mean_diffs=[-0.02, float("nan")], season_ns=[100, 10]
    )
    assert v == "DONNEES INSUFFISANTES"


def test_verdict_only_three_authorized_values_used(stage31) -> None:
    allowed = {"SIGNAL DEMONTRE", "SIGNAL NON DEMONTRE", "DONNEES INSUFFISANTES"}
    cases = [
        (_boot(-0.01, -0.02, -0.005), 200, [-0.01, -0.008], [100, 100]),
        (_boot(0.001, -0.001, 0.003), 200, [0.001, 0.001], [100, 100]),
        (_boot(-0.01, -0.02, -0.005), 5, [], []),
        (_boot(-0.01, -0.02, -0.005), 200, [-0.02, 0.01], [100, 100]),
    ]
    for primary, n, diffs, ns in cases:
        assert stage31.classify_verdict(primary, n, diffs, ns) in allowed


# --------------------------------------------------------------------------
# tag_burn_in_validation_test : meme schema que Phase K (deja non-
# regression testee pour split_burn_in_calibration_test lui-meme ailleurs).
# --------------------------------------------------------------------------


def test_tag_burn_in_validation_test_labels_rows_correctly(stage31) -> None:
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
    tagged = stage31.tag_burn_in_validation_test(df, _FakeStage10(), _FakeStage8())
    assert list(tagged["split"]) == ["burn_in", "validation", "test"]


# --------------------------------------------------------------------------
# load_all_congestion_features : non-regression sur les donnees reelles
# deja catalogues (match_catalog, INCHANGE) - aucune acquisition.
# --------------------------------------------------------------------------


def test_load_all_congestion_features_covers_every_catalogued_match(stage31) -> None:
    from sys_foot_quant.data_engine.market_odds import match_catalog

    features = stage31.load_all_congestion_features()
    expected_n = sum(len(match_catalog.list_matches(c, s)) for c, s in stage31._LEAGUES_SEASONS)
    assert len(features) == expected_n


def test_load_all_congestion_features_has_none_only_for_first_matches(stage31) -> None:
    features = stage31.load_all_congestion_features()
    n_missing_home = sum(1 for home, _away in features.values() if home is None)
    n_missing_away = sum(1 for _home, away in features.values() if away is None)
    # Au moins une equipe par (competition, saison) joue son premier match
    # sans historique - jamais zero exclusion sur 6 (competition, saison).
    assert n_missing_home > 0
    assert n_missing_away > 0


# --------------------------------------------------------------------------
# build_full_dataset : exclusion explicite des matchs sans historique de
# repos complet (synthetique, rapide - aucune lecture de fichier reel).
# --------------------------------------------------------------------------


def test_build_full_dataset_excludes_rows_with_missing_congestion(stage31, monkeypatch) -> None:
    class _FakeE7:
        @staticmethod
        def build_lambda_mu_dataframe(stage8_module):
            return pd.DataFrame(
                {
                    "match_id": ["m1", "m2", "m3"],
                    "poisson_simple_lambda": [1.2, 1.3, 1.1],
                    "poisson_simple_mu": [1.0, 1.1, 0.9],
                    "total_goals": [3, 1, 4],
                }
            )

    class _FakeE8:
        @staticmethod
        def build_decision_time_lookup(stage8_module):
            return pd.Series(
                pd.to_datetime(["2025-08-09 18:00", "2025-08-16 18:00", "2025-08-23 18:00"], utc=True),
                index=["m1", "m2", "m3"],
            )

    class _FakeCalibrated:
        probabilities = {2.5: 0.5}

    monkeypatch.setattr(
        stage31, "calibrate_prediction", lambda pred, pool, as_of_time: _FakeCalibrated()
    )

    # m1 : historique de repos complet ; m2 : away manquant ; m3 : absent du dict.
    congestion_by_match_id = {"m1": (7.0, 6.0), "m2": (7.0, None)}

    df, n_excluded = stage31.build_full_dataset(_FakeE7(), _FakeE8(), SimpleNamespace(), congestion_by_match_id)
    assert list(df["match_id"]) == ["m1"]
    assert n_excluded == 2
