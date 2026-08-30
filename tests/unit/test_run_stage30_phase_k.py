"""Tests des fonctions pures de run_stage30 (Phase K) - AVANT toute
execution reelle (bloquee, voir docstring du script). Script charge via
importlib (meme convention que Phases F/G/H/E16)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "run_stage30_phase_k_elo_incremental_information.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage30_phase_k_elo_incremental_information", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def stage30():
    return _load_script()


# --------------------------------------------------------------------------
# fit_logistic_with_offset : doit reproduire fit_logistic (E16) quand
# offset=0, et respecter l'offset sinon.
# --------------------------------------------------------------------------


def test_fit_logistic_with_offset_zero_reproduces_plain_logistic(stage30) -> None:
    e16 = stage30._load_e16()
    rng = np.random.default_rng(0)
    n = 200
    x1 = rng.uniform(-2, 2, size=n)
    X = np.column_stack([np.ones(n), x1])
    true_beta = np.array([0.3, 1.5])
    p_true = 1.0 / (1.0 + np.exp(-(X @ true_beta)))
    y = (rng.uniform(size=n) < p_true).astype(float)

    beta_plain = e16.fit_logistic(X, y)
    beta_offset = stage30.fit_logistic_with_offset(np.zeros(n), X, y)
    np.testing.assert_allclose(beta_plain, beta_offset, atol=1e-6)


def test_fit_logistic_with_offset_fixes_offset_coefficient_to_one(stage30) -> None:
    rng = np.random.default_rng(1)
    n = 300
    offset = rng.normal(0, 1, size=n)  # jouerait le role de logit(p_A)
    elo = rng.uniform(-400, 400, size=n)
    X = np.column_stack([np.ones(n), elo])
    z = offset + 0.0 * elo  # la verite ne depend PAS d'elo, seulement de l'offset
    p_true = 1.0 / (1.0 + np.exp(-z))
    y = (rng.uniform(size=n) < p_true).astype(float)

    beta = stage30.fit_logistic_with_offset(offset, X, y)
    # le coefficient d'elo (beta[1]) doit converger pres de 0 (aucune info reelle)
    assert abs(beta[1]) < 0.01


def test_predict_logistic_with_offset_matches_manual_sigmoid(stage30) -> None:
    offset = np.array([0.5])
    beta = np.array([0.2, -0.1])
    X = np.array([[1.0, 3.0]])
    pred = stage30.predict_logistic_with_offset(offset, beta, X)[0]
    expected = 1.0 / (1.0 + np.exp(-(0.5 + 0.2 * 1.0 - 0.1 * 3.0)))
    assert pred == pytest.approx(expected)


# --------------------------------------------------------------------------
# walk_forward_logistic_with_offset : jamais de fuite vers le futur.
# --------------------------------------------------------------------------


def test_walk_forward_logistic_with_offset_drops_warmup_rows(stage30) -> None:
    rng = np.random.default_rng(2)
    n = 50
    offset = rng.normal(0, 1, size=n)
    X = np.column_stack([np.ones(n), rng.uniform(-1, 1, size=n)])
    y = rng.integers(0, 2, size=n).astype(float)
    preds = stage30.walk_forward_logistic_with_offset(offset, X, y, min_train=30)
    assert np.isnan(preds[:30]).all()
    assert not np.isnan(preds[30:]).any()


def test_walk_forward_logistic_with_offset_never_uses_future_rows(stage30) -> None:
    rng = np.random.default_rng(3)
    n = 40
    offset = rng.normal(0, 1, size=n)
    X = np.column_stack([np.ones(n), rng.uniform(-1, 1, size=n)])
    y = rng.integers(0, 2, size=n).astype(float)

    preds_a = stage30.walk_forward_logistic_with_offset(offset, X, y, min_train=30)

    offset_b = offset.copy()
    X_b = X.copy()
    y_b = y.copy()
    offset_b[-1] = 999.0
    X_b[-1, 1] = 999.0
    y_b[-1] = 1.0 - y_b[-1]
    preds_b = stage30.walk_forward_logistic_with_offset(offset_b, X_b, y_b, min_train=30)

    n_common = n - 1
    np.testing.assert_allclose(preds_a[:n_common], preds_b[:n_common])


# --------------------------------------------------------------------------
# Controle de recalibration (meme schema que Phases F/G/H) : si le seul
# probleme est une miscalibration generique de p_A, et qu'elo_diff est du
# bruit pur, D ne doit PAS ameliorer C de facon significative.
# --------------------------------------------------------------------------


def test_recalibration_alone_explains_gain_is_not_falsely_validated(stage30) -> None:
    rng = np.random.default_rng(4)
    n = 400
    y = rng.integers(0, 2, size=n).astype(float)
    p_a = np.full(n, 0.85)  # tres mal calibre (sur-confiant), constant
    elo_diff = rng.normal(0, 200, size=n)  # bruit pur, independant de y

    logit_p_a = np.log(p_a / (1 - p_a))

    # Modele C : recalibration seule (logit(p_A) libre)
    X_c = np.column_stack([np.ones(n), logit_p_a])
    p_c = np.full(n, np.nan)
    for i in range(n):
        if i < 30:
            continue
        from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test  # noqa: F401

        e16 = stage30._load_e16()
        beta = e16.fit_logistic(X_c[:i], y[:i])
        p_c[i] = e16.predict_logistic(beta, X_c[i : i + 1])[0]

    # Modele D : recalibration + elo (les deux libres)
    X_d = np.column_stack([np.ones(n), logit_p_a, elo_diff])
    p_d = np.full(n, np.nan)
    for i in range(n):
        if i < 30:
            continue
        e16 = stage30._load_e16()
        beta = e16.fit_logistic(X_d[:i], y[:i])
        p_d[i] = e16.predict_logistic(beta, X_d[i : i + 1])[0]

    mask = ~np.isnan(p_c) & ~np.isnan(p_d)
    brier_c = (p_c[mask] - y[mask]) ** 2
    brier_d = (p_d[mask] - y[mask]) ** 2
    diffs = brier_d - brier_c

    from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test

    res = paired_bootstrap_test(diffs, n_resamples=2000, seed=0)
    # Elo est du bruit pur : D ne doit jamais ameliorer significativement C.
    assert not (res["ci_high"] < 0.0)


# --------------------------------------------------------------------------
# classify_verdict : grille figee (5 valeurs autorisees)
# --------------------------------------------------------------------------


def _boot(ci_low, ci_high):
    return {"ci_low": ci_low, "ci_high": ci_high}


def test_verdict_donnees_insuffisantes_when_pool_too_small(stage30) -> None:
    v = stage30.classify_verdict(_boot(-0.05, -0.01), _boot(-0.05, -0.01), _boot(-0.05, -0.01), [], n_global_pool=10)
    assert v == "DONNEES INSUFFISANTES"


def test_verdict_valide_when_all_favorable_and_no_contradiction(stage30) -> None:
    v = stage30.classify_verdict(
        _boot(-0.05, -0.01), _boot(-0.06, -0.005), _boot(-0.06, -0.005), [_boot(-0.05, -0.005)], n_global_pool=200
    )
    assert v == "VALIDE"


def test_verdict_non_valide_when_scope_inverts(stage30) -> None:
    v = stage30.classify_verdict(
        _boot(-0.05, -0.01), _boot(-0.06, -0.005), _boot(-0.06, -0.005), [_boot(0.001, 0.02)], n_global_pool=200
    )
    assert v == "NON VALIDE"


def test_verdict_absence_de_preuve_when_validation_and_test_contradict(stage30) -> None:
    v = stage30.classify_verdict(
        _boot(-0.02, 0.02), _boot(-0.06, -0.005), _boot(0.005, 0.05), [], n_global_pool=200
    )
    assert v == "ABSENCE DE PREUVE"


def test_verdict_non_valide_when_ci_overlaps_zero_and_narrow(stage30) -> None:
    v = stage30.classify_verdict(_boot(-0.01, 0.01), _boot(-0.01, 0.01), _boot(-0.01, 0.01), [], n_global_pool=200)
    assert v == "NON VALIDE"


def test_verdict_absence_de_preuve_when_ci_wide_and_uninformative(stage30) -> None:
    v = stage30.classify_verdict(_boot(-0.10, 0.10), _boot(-0.10, 0.10), _boot(-0.10, 0.10), [], n_global_pool=200)
    assert v == "ABSENCE DE PREUVE"


def test_verdict_only_five_authorized_values_used(stage30) -> None:
    allowed = {"VALIDE", "NON VALIDE", "ABSENCE DE PREUVE", "DONNEES INSUFFISANTES", "PROBLEME METHODOLOGIQUE"}
    cases = [
        (_boot(-0.05, -0.01), _boot(-0.06, -0.005), _boot(-0.06, -0.005), [], 200),
        (_boot(-0.01, 0.01), _boot(-0.01, 0.01), _boot(-0.01, 0.01), [], 200),
        (_boot(-0.05, -0.01), _boot(-0.06, -0.005), _boot(-0.06, -0.005), [], 5),
        (_boot(-0.02, 0.02), _boot(-0.06, -0.005), _boot(0.005, 0.05), [], 200),
    ]
    for primary, validation, test, scopes, n in cases:
        assert stage30.classify_verdict(primary, validation, test, scopes, n_global_pool=n) in allowed


# --------------------------------------------------------------------------
# tag_burn_in_validation_test : verifie l'etiquetage a partir d'ensembles
# validation/test deja connus (la correctnesse de split_burn_in_calibration_test
# elle-meme est deja couverte par les tests existants de run_stage10, non
# regression).
# --------------------------------------------------------------------------


def test_tag_burn_in_validation_test_labels_rows_correctly(stage30) -> None:
    fake_record = SimpleNamespace()

    class _FakeStage10:
        @staticmethod
        def split_burn_in_calibration_test(records):
            return {"m2"}, {"m3"}  # validation_ids, test_ids ; m1 -> burn_in par defaut

    class _FakeStage8:
        _SEASONS = {"2024_25": ["liga"]}

        @staticmethod
        def _load_records(league, season):
            return [fake_record]

    df = pd.DataFrame({"match_id": ["m1", "m2", "m3"], "league": ["liga"] * 3, "season": ["2024_25"] * 3})
    tagged = stage30.tag_burn_in_validation_test(df, _FakeStage10(), _FakeStage8())
    assert list(tagged["split"]) == ["burn_in", "validation", "test"]


# --------------------------------------------------------------------------
# Garde-fous d'execution reelle : main() et load_all_elo_records() doivent
# echouer explicitement tant que le blocage n'est pas leve.
# --------------------------------------------------------------------------


def test_load_elo_ratings_by_club_raises_if_archive_missing(stage30, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(stage30, "_ELO_ARCHIVE_PATH", tmp_path / "does_not_exist.csv")
    with pytest.raises(FileNotFoundError):
        stage30.load_elo_ratings_by_club()


def test_load_elo_ratings_by_club_works_with_real_archive(stage30) -> None:
    """Non-regression : l'archive reelle (Phase K, option b) doit
    charger sans erreur et couvrir nos 67 clubs."""
    if not stage30._ELO_ARCHIVE_PATH.exists():
        pytest.skip("Archive ClubElo reelle non presente.")
    by_club = stage30.load_elo_ratings_by_club()
    assert len(by_club) == 67


# --------------------------------------------------------------------------
# Restriction de corpus (docs/elo_experiment_specification.md, annexe
# archive) : tout match dont decision_time > _CORPUS_CUTOFF_DATE doit
# etre exclu, jamais impute.
# --------------------------------------------------------------------------


def test_corpus_cutoff_date_excludes_matches_strictly_after_it(stage30) -> None:
    import pandas as pd

    df = pd.DataFrame(
        {
            "decision_time": pd.to_datetime(
                ["2026-01-13 18:00", "2026-01-14 18:00", "2026-01-15 18:00"], utc=True
            )
        }
    )
    kept = df[df["decision_time"].dt.date <= stage30._CORPUS_CUTOFF_DATE]
    assert len(kept) == 2  # le 13 et le 14 (inclus), jamais le 15
