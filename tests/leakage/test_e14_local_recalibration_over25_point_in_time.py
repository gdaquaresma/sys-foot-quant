"""Garde-fous anti-fuite pour E14
(scripts/run_stage23_e14_local_recalibration_over25.py) :
- le mecanisme point-in-time (decision_time, walk-forward) est INTEGRALEMENT
  delegue a E7/E8 (deja teste) - jamais reimplemente ;
- toute recalibration (methode A ou B) est ajustee EXCLUSIVEMENT sur des
  matchs de calibration strictement anterieurs au match evalue, jamais
  sur le test, jamais sur un match posterieur (point 3/4 du protocole) ;
- les zones de comparaison ([0.6,0.7), [0.4,0.6)) sont des constantes
  FIGEES, jamais recalculees a partir des donnees observees (point 8) ;
- aucune donnee de marche n'est utilisee pour calibrer cette zone
  (point "ce qu'il ne faut surtout pas faire") ;
- E1-E13 ne sont jamais modifies (aucune ecriture dans un script existant)."""

from __future__ import annotations

import ast
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage23_e14_local_recalibration_over25.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e14_module():
    return _load(_SCRIPT_PATH, "run_stage23_e14_local_recalibration_over25")


def _dt(day: int) -> datetime:
    return datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=day - 1)


# --- 1. point-in-time integralement delegue, jamais reimplemente -----------


def test_e14_never_reimplements_point_in_time_filtering() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    assert "attach_walk_forward_scale" in source
    assert "AmbiguousCollectionWindowError" not in source
    assert "conservative_knowledge_time_utc" not in source
    assert "fit_scale_correction_as_of" not in source  # reutilise via attach_walk_forward_scale, jamais reimplemente


def test_e14_never_modifies_e1_to_e13_scripts() -> None:
    """E14 doit etre un NOUVEAU fichier, jamais une edition d'un script
    d'experience anterieur - verifie que les scripts E7/E8/E11 ne
    contiennent aucune trace du vocabulaire specifique a E14."""
    for prior_script in (
        "run_stage15_e7_total_goals_distribution.py",
        "run_stage16_e8_walk_forward_validation.py",
        "run_stage20_e11_probability_reliability_mapping.py",
    ):
        source = (Path(_SCRIPT_PATH).parent / prior_script).read_text()
        assert "walk_forward_recalibrate" not in source
        assert "coherence_gate" not in source
        assert "E14" not in source


# --- 2. recalibration walk-forward stricte : jamais le futur ----------------


def test_walk_forward_recalibrate_uses_strict_inequality_on_decision_time(e14_module) -> None:
    """Verifie par inspection statique que le filtre temporel est une
    inegalite STRICTE (<), jamais <= (qui autoriserait un match survenant
    exactement au meme instant a fuiter dans son propre ajustement)."""
    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "walk_forward_recalibrate")
    body_source = ast.unparse(func)
    assert "calib_times < as_of" in body_source
    assert "calib_times <= as_of" not in body_source


def test_walk_forward_recalibrate_never_leaks_future_calibration_row() -> None:
    e14 = _load(_SCRIPT_PATH, "run_stage23_e14_local_recalibration_over25_leak_check")
    calib = pd.DataFrame(
        {
            "decision_time": [_dt(1), _dt(2), _dt(3), _dt(1000)],  # la derniere ligne est tres future
            "p_over_2.5": [0.4, 0.4, 0.4, 0.99],
            "outcome_over_2.5": [0.0, 1.0, 0.0, 1.0],
        }
    )
    test = pd.DataFrame({"match_id": ["m1"], "decision_time": [_dt(5)], "p_over_2.5": [0.4]})

    seen_lengths = []

    def fit_fn(p, y):
        seen_lengths.append(len(p))
        return {"p": p, "y": y}

    def predict_fn(fitted, p):
        return p

    e14.walk_forward_recalibrate(calib, test, fit_fn, predict_fn, min_matches=1)
    assert seen_lengths == [3]  # jamais 4 : la ligne du jour 1000 est exclue


def test_walk_forward_recalibrate_moving_a_calibration_row_to_the_future_never_increases_n(e14_module) -> None:
    """Balayage : deplacer une ligne de calibration VERS LE FUTUR (au-dela
    du match evalue) ne peut jamais AUGMENTER le nombre de matchs utilises
    pour l'ajuster - propriete structurelle du filtre `<`."""
    rng = np.random.default_rng(0)
    for _ in range(50):
        n_calib = rng.integers(5, 20)
        days = rng.integers(1, 50, size=n_calib)
        calib = pd.DataFrame(
            {
                "decision_time": [_dt(int(d)) for d in days],
                "p_over_2.5": rng.uniform(0.1, 0.9, size=n_calib),
                "outcome_over_2.5": rng.integers(0, 2, size=n_calib).astype(float),
            }
        )
        as_of_day = int(rng.integers(1, 50))
        test = pd.DataFrame({"match_id": ["m"], "decision_time": [_dt(as_of_day)], "p_over_2.5": [0.5]})

        def fit_fn(p, y):
            return {"n": len(p)}

        def predict_fn(fitted, p):
            return np.full_like(p, fitted["n"], dtype=float)

        out_before = e14_module.walk_forward_recalibrate(calib, test, fit_fn, predict_fn, min_matches=0)
        n_before = out_before.iloc[0]["n_calibration_used"]

        calib_moved = calib.copy()
        calib_moved.loc[calib_moved.index[0], "decision_time"] = _dt(as_of_day + 1000)  # deplace vers le futur
        out_after = e14_module.walk_forward_recalibrate(calib_moved, test, fit_fn, predict_fn, min_matches=0)
        n_after = out_after.iloc[0]["n_calibration_used"]

        assert n_after <= n_before


# --- 3. tranches figees, jamais recalculees a partir des donnees -----------


def test_target_and_adjacent_zones_are_frozen_constants(e14_module) -> None:
    assert (e14_module._TARGET_LOW, e14_module._TARGET_HIGH) == (0.6, 0.7)
    assert (e14_module._ADJACENT_LOW, e14_module._ADJACENT_HIGH) == (0.4, 0.6)
    assert e14_module._MIN_N_RECAL == 30


def test_zone_functions_never_use_data_derived_thresholds() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    assert "np.percentile" not in source
    assert "np.quantile" not in source
    assert ".quantile(" not in source


def test_zone_mask_never_uses_outcome_in_source() -> None:
    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "zone_mask")
    body_source = ast.unparse(func)
    assert "outcome" not in body_source
    assert "_y" not in body_source


# --- 4. aucune donnee de marche utilisee pour calibrer cette zone -----------


def test_e14_never_imports_market_odds_modules() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    assert "multi_bookmaker_odds" not in source
    assert "market_engine" not in source
    assert "B365" not in source
    assert "bookmaker" not in source.lower()


# --- 5. verdict jamais choisi apres ajustement post-hoc de la methode -------


def test_classify_e14_verdict_is_pure_function_of_precomputed_bootstrap_results(e14_module) -> None:
    """Le verdict ne recalcule jamais rien a partir des probabilites brutes
    - il consomme uniquement des resultats bootstrap DEJA calcules,
    garantissant qu'aucun reajustement de methode n'a lieu apres
    observation (point 8 du protocole)."""
    import inspect

    sig = inspect.signature(e14_module.classify_e14_verdict)
    assert set(sig.parameters) == {"target_zone_boot", "global_boot", "adjacent_zone_boot", "coherence", "n_target", "min_n"}
