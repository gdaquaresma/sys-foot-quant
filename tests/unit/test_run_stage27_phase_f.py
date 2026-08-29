"""Tests des fonctions pures de run_stage27 (Phase F) - AVANT toute
execution sur donnees reelles (protocole etape 14). Le script complet est
charge via importlib (meme convention que les tests d'E8/E9/E16 pour un
script `scripts/*.py` non package)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "run_stage27_phase_f_sot_incremental_information.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage27_phase_f_sot_incremental_information", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def stage27():
    return _load_script()


# --------------------------------------------------------------------------
# eligible_dataset : ne garde que les lignes ou Modele O ET SOT sont
# simultanement disponibles - jamais une comparaison sur des ensembles
# differents.
# --------------------------------------------------------------------------


def test_eligible_dataset_drops_rows_missing_either_model(stage27) -> None:
    df = pd.DataFrame(
        {
            "decision_time": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "p_model_over": [0.5, np.nan, 0.6],
            "sot_produced_total": [8.0, 8.0, np.nan],
            "sot_conceded_total": [7.0, 7.0, 7.0],
        }
    )
    out = stage27.eligible_dataset(df)
    assert len(out) == 1
    assert out.iloc[0]["p_model_over"] == 0.5


def test_eligible_dataset_sorted_by_decision_time(stage27) -> None:
    df = pd.DataFrame(
        {
            "decision_time": pd.to_datetime(["2024-01-03", "2024-01-01", "2024-01-02"]),
            "p_model_over": [0.5, 0.5, 0.5],
            "sot_produced_total": [8.0, 8.0, 8.0],
            "sot_conceded_total": [7.0, 7.0, 7.0],
        }
    )
    out = stage27.eligible_dataset(df)
    assert list(out["decision_time"]) == sorted(out["decision_time"])


# --------------------------------------------------------------------------
# build_o_vs_osot : walk-forward logistique (E16, REUTILISE) - NaN pendant
# le rodage (`min_train`), predictions ensuite pour chaque ligne
# EXCLUSIVEMENT a partir des lignes PRECEDENTES.
# --------------------------------------------------------------------------


def _synthetic_eligible(n: int, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    p_o = rng.uniform(0.3, 0.7, size=n)
    sot_produced = rng.uniform(5, 10, size=n)
    sot_conceded = rng.uniform(5, 10, size=n)
    outcome = rng.integers(0, 2, size=n).astype(float)
    return pd.DataFrame(
        {
            "decision_time": pd.date_range("2024-01-01", periods=n, freq="D"),
            "league": ["liga"] * n,
            "season": ["2024_25"] * n,
            "p_model_over": p_o,
            "sot_produced_total": sot_produced,
            "sot_conceded_total": sot_conceded,
            "outcome": outcome,
        }
    )


def test_build_o_vs_osot_drops_warmup_rows_below_min_train(stage27) -> None:
    e16 = stage27._load_e16()
    elig = _synthetic_eligible(50)
    compared = stage27.build_o_vs_osot(elig, e16)
    # min_train=30 -> au plus 20 lignes exploitables (predictions a partir de l'indice 30)
    assert len(compared) <= 20
    assert compared["p_osot"].notna().all()
    assert compared["p_o_recal"].notna().all()


def test_build_o_vs_osot_never_uses_future_rows(stage27) -> None:
    """Reproduit la garantie deja testee dans E16 (walk_forward_logistic)
    au niveau de CE script : perturber une ligne FUTURE ne doit changer
    AUCUNE prediction anterieure a cette ligne."""
    e16 = stage27._load_e16()
    elig = _synthetic_eligible(40)
    compared_a = stage27.build_o_vs_osot(elig, e16)

    elig_perturbed = elig.copy()
    elig_perturbed.loc[elig_perturbed.index[-1], "sot_produced_total"] = 999.0
    elig_perturbed.loc[elig_perturbed.index[-1], "outcome"] = 1.0 - elig_perturbed.loc[elig_perturbed.index[-1], "outcome"]
    compared_b = stage27.build_o_vs_osot(elig_perturbed, e16)

    # toutes les predictions SAUF potentiellement la toute derniere doivent etre identiques
    n_common = min(len(compared_a), len(compared_b)) - 1
    np.testing.assert_allclose(
        compared_a["p_osot"].to_numpy()[:n_common], compared_b["p_osot"].to_numpy()[:n_common]
    )


# --------------------------------------------------------------------------
# evaluate_o_vs_osot : Brier/logloss/calibration/resolution + bootstrap.
# --------------------------------------------------------------------------


def test_evaluate_identical_predictions_yields_zero_diff(stage27) -> None:
    stage8 = stage27._load_e8()._load_e7()._load_stage10()._load_stage8()
    n = 50
    rng = np.random.default_rng(1)
    p = rng.uniform(0.3, 0.7, size=n)
    y = rng.integers(0, 2, size=n).astype(float)
    compared = pd.DataFrame({"p_model_over": p, "p_o_recal": p, "p_osot": p, "outcome": y})
    res = stage27.evaluate_o_vs_osot(compared, stage8)
    assert res["brier_o"] == pytest.approx(res["brier_osot"])
    assert res["boot_brier_osot_minus_o"]["mean_diff"] == pytest.approx(0.0)
    assert res["boot_brier_osot_minus_o_recal"]["mean_diff"] == pytest.approx(0.0)
    assert res["boot_brier_osot_minus_o_recal"]["ci_low"] == pytest.approx(0.0)
    assert res["boot_brier_osot_minus_o_recal"]["ci_high"] == pytest.approx(0.0)


def test_evaluate_perfect_osot_beats_uninformative_o_and_control(stage27) -> None:
    """Le TEST PRINCIPAL compare O+SOT au CONTROLE O-recalibre (jamais au
    seul O brut) - meme quand le controle est aussi non-informatif, la
    comparaison determinante reste O+SOT vs O-recalibre."""
    stage8 = stage27._load_e8()._load_e7()._load_stage10()._load_stage8()
    n = 200
    y = np.array([0.0, 1.0] * (n // 2))
    p_o = np.full(n, 0.5)  # O totalement non-informatif
    p_o_recal = np.full(n, 0.5)  # le controle, sans SOT, reste non-informatif ici
    p_osot = y * 0.95 + (1 - y) * 0.05  # O+SOT quasi parfait
    compared = pd.DataFrame({"p_model_over": p_o, "p_o_recal": p_o_recal, "p_osot": p_osot, "outcome": y})
    res = stage27.evaluate_o_vs_osot(compared, stage8)
    assert res["brier_osot"] < res["brier_o"]
    assert res["brier_osot"] < res["brier_o_recal"]
    assert res["boot_brier_osot_minus_o_recal"]["ci_high"] < 0.0  # amelioration statistiquement nette vs le CONTROLE


def test_evaluate_recalibration_alone_explains_the_gain_is_not_falsely_validated(stage27) -> None:
    """Cas critique motivant le controle O-recalibre : si O+SOT n'apporte
    RIEN au-dela d'une simple re-calibration (memes valeurs que le
    controle), le test principal doit rester NON concluant, meme si
    O+SOT bat largement le O BRUT (non recalibre)."""
    stage8 = stage27._load_e8()._load_e7()._load_stage10()._load_stage8()
    n = 200
    rng = np.random.default_rng(2)
    y = rng.integers(0, 2, size=n).astype(float)
    p_o = np.full(n, 0.9)  # O brut deliberement mal calibre
    p_recalibrated = rng.uniform(0.3, 0.7, size=n)  # une simple re-calibration corrige deja tout
    compared = pd.DataFrame({"p_model_over": p_o, "p_o_recal": p_recalibrated, "p_osot": p_recalibrated, "outcome": y})
    res = stage27.evaluate_o_vs_osot(compared, stage8)
    assert res["brier_osot"] < res["brier_o"]  # bat largement le O BRUT...
    # ...mais AUCUNE amelioration au-dela du controle (memes valeurs) : IC95% = [0,0]
    assert res["boot_brier_osot_minus_o_recal"]["ci_low"] == pytest.approx(0.0)
    assert res["boot_brier_osot_minus_o_recal"]["ci_high"] == pytest.approx(0.0)


# --------------------------------------------------------------------------
# classify_verdict : grille figee (etape 10) - appliquee mecaniquement.
# --------------------------------------------------------------------------


def test_verdict_non_valide_when_ci_overlaps_zero(stage27) -> None:
    global_res = {
        "boot_brier_osot_minus_o_recal": {"ci_low": -0.01, "ci_high": 0.01},
        "calibration_weighted_error_o_recal": 0.05,
        "calibration_weighted_error_osot": 0.05,
    }
    assert stage27.classify_verdict(global_res, []) == "NON VALIDE"


def test_verdict_valide_when_improvement_significant_and_stable(stage27) -> None:
    global_res = {
        "boot_brier_osot_minus_o_recal": {"ci_low": -0.05, "ci_high": -0.01},
        "calibration_weighted_error_o_recal": 0.05,
        "calibration_weighted_error_osot": 0.05,
    }
    scope_boots = [{"ci_low": -0.06, "ci_high": -0.005}, {"ci_low": -0.04, "ci_high": -0.002}]
    assert stage27.classify_verdict(global_res, scope_boots) == "VALIDE"


def test_verdict_non_valide_when_a_scope_inverts(stage27) -> None:
    global_res = {
        "boot_brier_osot_minus_o_recal": {"ci_low": -0.05, "ci_high": -0.01},
        "calibration_weighted_error_o_recal": 0.05,
        "calibration_weighted_error_osot": 0.05,
    }
    scope_boots = [{"ci_low": 0.001, "ci_high": 0.02}]  # inversion dans une decoupe
    assert stage27.classify_verdict(global_res, scope_boots) == "NON VALIDE"


def test_verdict_non_valide_when_calibration_degrades_sharply(stage27) -> None:
    global_res = {
        "boot_brier_osot_minus_o_recal": {"ci_low": -0.05, "ci_high": -0.01},
        "calibration_weighted_error_o_recal": 0.02,
        "calibration_weighted_error_osot": 0.10,  # degradation majeure
    }
    assert stage27.classify_verdict(global_res, []) == "NON VALIDE"


def test_verdict_non_valide_when_only_raw_o_is_beaten_not_the_control(stage27) -> None:
    """Cas critique (motivant le controle) : IC95% vs O brut entierement
    negatif, mais vs le CONTROLE O-recalibre chevauchant 0 - le verdict
    doit rester NON VALIDE (information non demontree AU-DELA d'une
    simple re-calibration)."""
    global_res = {
        "boot_brier_osot_minus_o": {"ci_low": -0.05, "ci_high": -0.01},  # bat le O brut...
        "boot_brier_osot_minus_o_recal": {"ci_low": -0.01, "ci_high": 0.01},  # ...mais pas le controle
        "calibration_weighted_error_o_recal": 0.05,
        "calibration_weighted_error_osot": 0.05,
    }
    assert stage27.classify_verdict(global_res, []) == "NON VALIDE"
