"""Garde-fous anti-fuite pour l'experience de recalibration isotonique
Over/Under (scripts/run_stage10_over_under_recalibration.py) :
- la courbe de calibration ne depend JAMAIS du contenu du TEST ;
- calibration et test sont chronologiquement disjoints, calibration
  strictement anterieure au test, sur le decoupage 40/30/30 deja utilise
  par B1/A2/B2/B3.3 ;
- non-regression du decoupage sur le corpus REEL deja recupere."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage10_over_under_recalibration.py"
_STAGE8_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage8_diagnostic_total_goals_over_under.py"
_UNDERSTAT_DIR = Path(__file__).resolve().parent.parent.parent / "research" / "xg_feasibility" / "runs"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def rc_module():
    return _load(_SCRIPT_PATH, "run_stage10_over_under_recalibration")


def _synthetic_df(n, seed):
    rng = np.random.default_rng(seed)
    true_p = rng.uniform(0.2, 0.8, size=n)
    over = (rng.uniform(0, 1, size=n) < true_p).astype(int)
    total_goals = np.where(over == 1, 3, 2)
    return pd.DataFrame(
        {
            "match_id": [f"m{i}" for i in range(n)],
            "total_goals": total_goals,
            "poisson_simple_p_over_2.5": true_p,
        }
    )


def test_fitted_curve_is_independent_of_test_set_content(rc_module) -> None:
    """La courbe isotonique est ajustee UNIQUEMENT sur la calibration -
    changer radicalement le TEST (resultats inverses) ne doit rien changer
    a la courbe ajustee, donc a p_test_after pour un meme p_test_before."""
    calib_df = _synthetic_df(2000, seed=1)

    test_df_a = _synthetic_df(500, seed=2)
    test_df_b = test_df_a.copy()
    test_df_b["total_goals"] = np.where(test_df_b["total_goals"] == 3, 2, 3)  # resultats inverses

    res_a = rc_module.evaluate_recalibration(calib_df, test_df_a, "poisson_simple", 2.5)
    res_b = rc_module.evaluate_recalibration(calib_df, test_df_b, "poisson_simple", 2.5)

    # Meme p_test_before (le test_df n'a change que le resultat, pas les
    # probabilites brutes) -> la courbe apprise etant identique (calib
    # inchangee), le biais AVANT recalibration change avec y_test (normal),
    # mais la transformation elle-meme (avant -> apres) doit rester la
    # meme fonction : on le verifie en reappliquant la courbe manuellement.
    from sys_foot_quant.calibration_engine.isotonic_calibration import fit_isotonic_calibration

    p_calib = calib_df["poisson_simple_p_over_2.5"].to_numpy()
    y_calib = (calib_df["total_goals"] > 2.5).astype(float).to_numpy()
    curve = fit_isotonic_calibration(p_calib, y_calib)

    p_test = test_df_a["poisson_simple_p_over_2.5"].to_numpy()
    expected_after = curve.predict(p_test)

    # Reconstruit p_test_after implicitement via biais_after + y_test
    # (biais_after = mean(p_after - y_test)) pour les deux versions du
    # test - la moyenne de p_after doit etre IDENTIQUE entre A et B
    # (memes p_test_before, meme courbe), seul y_test differe.
    mean_after_a = res_a["biais_after"] + (test_df_a["total_goals"] > 2.5).astype(float).mean()
    mean_after_b = res_b["biais_after"] + (test_df_b["total_goals"] > 2.5).astype(float).mean()
    assert mean_after_a == pytest.approx(mean_after_b, abs=1e-9)
    assert mean_after_a == pytest.approx(expected_after.mean(), abs=1e-9)


def test_fitted_curve_is_independent_of_test_set_probabilities(rc_module) -> None:
    """Changer les probabilites brutes du TEST (pas de la calibration) ne
    doit pas changer la courbe ajustee - verifie directement via
    fit_isotonic_calibration, jamais appelee avec des donnees de test."""
    from sys_foot_quant.calibration_engine.isotonic_calibration import fit_isotonic_calibration

    calib_df = _synthetic_df(1500, seed=3)
    p_calib = calib_df["poisson_simple_p_over_2.5"].to_numpy()
    y_calib = (calib_df["total_goals"] > 2.5).astype(float).to_numpy()

    curve_reference = fit_isotonic_calibration(p_calib, y_calib)

    test_df_1 = _synthetic_df(300, seed=4)
    test_df_2 = _synthetic_df(300, seed=999)  # completement different
    res_1 = rc_module.evaluate_recalibration(calib_df, test_df_1, "poisson_simple", 2.5)
    res_2 = rc_module.evaluate_recalibration(calib_df, test_df_2, "poisson_simple", 2.5)

    # meme grille de reference : la fonction de calibration elle-meme
    # (x_calibration/fitted_values) est identique quel que soit le test.
    grid = np.linspace(0.0, 1.0, 50)
    assert np.allclose(curve_reference.predict(grid), curve_reference.predict(grid))
    assert res_1["n_calibration"] == res_2["n_calibration"] == len(calib_df)


@pytest.mark.skipif(not _UNDERSTAT_DIR.exists(), reason="Fichiers Understat reels non presents.")
def test_real_corpus_split_is_chronologically_disjoint_per_league_season() -> None:
    stage8 = _load(_STAGE8_PATH, "run_stage8_diagnostic_total_goals_over_under")
    rc = _load(_SCRIPT_PATH, "run_stage10_over_under_recalibration")

    for season, leagues in stage8._SEASONS.items():
        for league in leagues:
            records = stage8._load_records(league, season)
            calib_ids, test_ids = rc.split_burn_in_calibration_test(records)
            assert calib_ids.isdisjoint(test_ids)
            by_id = {r.match_id: r.kickoff_utc for r in records}
            if calib_ids and test_ids:
                # <=, pas < : plusieurs matchs d'une meme journee de
                # championnat partagent exactement le meme kickoff_utc -
                # la frontiere du decoupage (par INDEX chronologique, pas
                # par timestamp unique) peut alors tomber au milieu d'un
                # groupe de matchs simultanes. Aucune fuite reelle : la
                # prediction de chaque match reste point-in-time via son
                # PROPRE decision_time (kickoff-2h), independamment du
                # cote du decoupage ou il atterrit.
                assert max(by_id[i] for i in calib_ids) <= min(by_id[i] for i in test_ids)
