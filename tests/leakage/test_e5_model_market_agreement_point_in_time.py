"""Garde-fous anti-fuite pour E5
(scripts/run_stage13_e5_model_market_agreement_over25.py) :
- la courbe isotonique n'est ajustee QUE sur la calibration, jamais le
  test (meme garantie que E2/E3, reverifiee ici avec match_id conserve) ;
- E5 ne reimplemente AUCUNE logique temporelle propre - tout le
  mecanisme point-in-time vient de over_under_odds.py (deja teste),
  jamais duplique ni modifie ici ;
- la probabilite de marche est EXACTEMENT le retrait d'overround deja
  existant, jamais une nouvelle formule."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage13_e5_model_market_agreement_over25.py"
)


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage13_e5_model_market_agreement_over25", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e5_module():
    return _load_script()


def _synthetic_calib_test(seed_calib=1, seed_test=2, n=1000):
    rng_c = np.random.default_rng(seed_calib)
    calib = pd.DataFrame(
        {
            "match_id": [f"c{i}" for i in range(n)],
            "total_goals": rng_c.poisson(2.5, size=n),
            "poisson_simple_p_over_2.5": rng_c.uniform(0.2, 0.8, size=n),
        }
    )
    rng_t = np.random.default_rng(seed_test)
    test = pd.DataFrame(
        {
            "match_id": [f"t{i}" for i in range(300)],
            "total_goals": rng_t.poisson(2.5, size=300),
            "poisson_simple_p_over_2.5": rng_t.uniform(0.2, 0.8, size=300),
        }
    )
    return calib, test


def test_compute_calibrated_probs_independent_of_test_outcomes(e5_module) -> None:
    """Changer radicalement les resultats du TEST (jamais la calibration)
    ne doit rien changer aux probabilites calibrees produites pour les
    memes p_test_before - la courbe ne depend que de la calibration."""
    calib, test_a = _synthetic_calib_test()
    test_b = test_a.copy()
    test_b["total_goals"] = np.where(test_b["total_goals"] > 2.5, 0, 5)  # resultats inverses

    probs_a = e5_module.compute_calibrated_probs(calib, test_a, "poisson_simple")
    probs_b = e5_module.compute_calibrated_probs(calib, test_b, "poisson_simple")
    pd.testing.assert_series_equal(probs_a.sort_index(), probs_b.sort_index())


def test_compute_calibrated_probs_matches_stage10_isotonic_curve_directly(e5_module) -> None:
    from sys_foot_quant.calibration_engine.isotonic_calibration import fit_isotonic_calibration

    calib, test = _synthetic_calib_test()
    probs = e5_module.compute_calibrated_probs(calib, test, "poisson_simple")

    curve = fit_isotonic_calibration(
        calib["poisson_simple_p_over_2.5"].to_numpy(), (calib["total_goals"] > 2.5).astype(float).to_numpy()
    )
    expected = curve.predict(test["poisson_simple_p_over_2.5"].to_numpy())
    np.testing.assert_allclose(probs.reindex(test["match_id"]).to_numpy(), expected)


def test_e5_script_never_reimplements_temporal_logic() -> None:
    """E5 doit deleguer TOUTE la logique point-in-time a over_under_odds.py
    (deja teste) - aucune reimplementation locale de fuseau horaire,
    fenetre de connaissance ou exclusion de jour."""
    source = Path(_SCRIPT_PATH).read_text()
    for forbidden in ("conservative_knowledge_time_utc", "AmbiguousCollectionWindowError", "timedelta", "ZoneInfo"):
        assert forbidden not in source, f"E5 ne doit pas reimplementer '{forbidden}' - deleguer a over_under_odds.py."


def test_e5_script_reuses_overround_removal_unchanged() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    assert "remove_overround_proportional" in source
    assert "def remove_overround_proportional" not in source  # jamais redefinie localement


def test_market_probability_never_uses_model_probability() -> None:
    """La probabilite de marche calculee dans build_agreement_dataframe ne
    doit dependre QUE des cotes B365 O/U - jamais de p_model."""
    import ast

    module = _load_script()
    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "build_agreement_dataframe"
    )
    # localise l'appel a remove_overround_proportional et verifie que ses
    # arguments ne referencent jamais 'p_model'.
    call = next(
        n
        for n in ast.walk(func)
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "remove_overround_proportional"
    )
    call_source = ast.unparse(call)
    assert "p_model" not in call_source
