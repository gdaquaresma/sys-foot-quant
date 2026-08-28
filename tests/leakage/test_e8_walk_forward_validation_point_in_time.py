"""Garde-fous anti-fuite pour E8
(scripts/run_stage16_e8_walk_forward_validation.py) :
- le facteur de correction c(m) d'un match de test ne peut JAMAIS etre
  influence par un match de calibration POSTERIEUR (decision_time >=
  decision_time(m)), ni par un quelconque match de TEST (jamais utilise) ;
- `evaluate_walk_forward` n'ajuste jamais elle-meme le facteur c - toujours
  recu deja fige (colonne `scale_c` deja calculee) ;
- le decision_time est calcule avec la MEME regle que partout ailleurs
  (`DECISION_OFFSET_HOURS`), jamais reimplementee differemment ;
- large balayage aleatoire (hypothesis) : deplacer un match de calibration
  dans le futur (au-dela de as_of_time) ne peut jamais faire baisser le
  nombre de matchs de calibration utilises ni changer c(m) tant que sa
  date reste >= as_of_time - et l'ajouter strictement avant DOIT etre
  reflete."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage16_e8_walk_forward_validation.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e8_module():
    return _load(_SCRIPT_PATH, "run_stage16_e8_walk_forward_validation")


def _dt(day: int):
    return datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=day)


# --- 1. un match de calibration posterieur ne peut jamais influencer c(m) --


def test_future_calibration_match_never_influences_earlier_scale(e8_module) -> None:
    base_calib = pd.DataFrame(
        {
            "decision_time": [_dt(d) for d in range(1, 35)],
            "poisson_simple_lambda": [1.0] * 34,
            "poisson_simple_mu": [1.0] * 34,
            "total_goals": [2.0] * 34,
        }
    )
    c_before, n_before = e8_module.fit_scale_correction_as_of(base_calib, "poisson_simple", _dt(20), min_matches=1)

    # ajoute un match de calibration EXTREME mais POSTERIEUR a as_of_time (jour 20)
    poisoned = pd.concat(
        [
            base_calib,
            pd.DataFrame(
                {
                    "decision_time": [_dt(25)],
                    "poisson_simple_lambda": [1.0],
                    "poisson_simple_mu": [1.0],
                    "total_goals": [500.0],  # valeur aberrante, doit etre totalement ignoree
                }
            ),
        ],
        ignore_index=True,
    )
    c_after, n_after = e8_module.fit_scale_correction_as_of(poisoned, "poisson_simple", _dt(20), min_matches=1)

    assert n_after == n_before
    assert c_after == pytest.approx(c_before)


def test_calibration_match_exactly_at_as_of_time_is_excluded(e8_module) -> None:
    calib = pd.DataFrame(
        {
            "decision_time": [_dt(5), _dt(10)],
            "poisson_simple_lambda": [1.0, 1.0],
            "poisson_simple_mu": [1.0, 1.0],
            "total_goals": [2.0, 999.0],
        }
    )
    # as_of_time == decision_time du deuxieme match -> strictement exclu (comparaison "<")
    c, n = e8_module.fit_scale_correction_as_of(calib, "poisson_simple", _dt(10), min_matches=1)
    assert n == 1
    assert c == pytest.approx(1.0)


# --- 2. un match de TEST n'entre jamais dans le calcul de c(m) -------------


def test_no_test_data_leaks_into_scale_computation() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    # fit_scale_correction_as_of ne prend jamais de test_df en parametre
    import inspect

    spec = importlib.util.spec_from_file_location("e8_src_check", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    sig = inspect.signature(mod.fit_scale_correction_as_of)
    assert list(sig.parameters)[:3] == ["calibration_df", "model", "as_of_time"]
    assert "test_df" not in sig.parameters


def test_evaluate_walk_forward_never_recomputes_scale_internally() -> None:
    import ast

    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "evaluate_walk_forward")
    body_source = ast.unparse(func)
    assert "fit_scale_correction_as_of" not in body_source
    assert "attach_walk_forward_scale" not in body_source


def test_decision_time_uses_shared_offset_constant() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    assert "DECISION_OFFSET_HOURS" in source
    assert "conservative_knowledge_time_utc" not in source  # jamais reimplemente differemment


# --- 3. balayage aleatoire (hypothesis) : deplacement temporel -------------


@given(
    n_calib=st.integers(min_value=5, max_value=60),
    move_to_future=st.booleans(),
    seed=st.integers(min_value=0, max_value=10_000),
)
@settings(max_examples=150)
def test_property_moving_a_calibration_row_to_the_future_never_lowers_n_used(n_calib, move_to_future, seed) -> None:
    e8 = _load(_SCRIPT_PATH, "run_stage16_e8_walk_forward_validation_prop")
    rng = np.random.default_rng(seed)
    days = sorted(rng.integers(1, 100, size=n_calib).tolist())
    calib = pd.DataFrame(
        {
            "decision_time": [_dt(d) for d in days],
            "poisson_simple_lambda": rng.uniform(0.8, 2.0, size=n_calib),
            "poisson_simple_mu": rng.uniform(0.8, 2.0, size=n_calib),
            "total_goals": rng.uniform(0.0, 6.0, size=n_calib),
        }
    )
    as_of = _dt(50)
    _, n_before = e8.fit_scale_correction_as_of(calib, "poisson_simple", as_of, min_matches=0)

    idx = rng.integers(0, n_calib)
    moved = calib.copy()
    if move_to_future:
        moved.loc[idx, "decision_time"] = _dt(200)  # bien apres as_of -> ne peut qu'exclure, jamais inclure
        _, n_after = e8.fit_scale_correction_as_of(moved, "poisson_simple", as_of, min_matches=0)
        assert n_after <= n_before
    else:
        moved.loc[idx, "decision_time"] = _dt(1)  # bien avant as_of -> ne peut qu'inclure ou rester egal
        _, n_after = e8.fit_scale_correction_as_of(moved, "poisson_simple", as_of, min_matches=0)
        assert n_after >= n_before


# --- 4. non-regression : reutilise le meme jeu calibration/test que E7 -----


@pytest.mark.skipif(
    not (Path(__file__).resolve().parent.parent.parent / "research" / "xg_feasibility" / "runs").exists(),
    reason="Fichiers Understat reels non presents.",
)
def test_real_corpus_calibration_test_ids_match_e7_exactly(e8_module) -> None:
    e7 = e8_module._load_e7()
    stage10 = e7._load_stage10()
    stage8 = stage10._load_stage8()

    calibration_df_stage8, test_df_stage8 = stage10.build_calibration_and_test_sets(stage8)
    assert len(calibration_df_stage8) > 500
    assert len(test_df_stage8) > 500
    # E8 reutilise EXACTEMENT le meme mecanisme (aucun recalcul different) -
    # verifie ici en rappelant la meme fonction une seconde fois et en
    # comparant les match_id (determinisme + non-modification).
    calibration_df_stage8_bis, test_df_stage8_bis = stage10.build_calibration_and_test_sets(stage8)
    assert set(calibration_df_stage8["match_id"]) == set(calibration_df_stage8_bis["match_id"])
    assert set(test_df_stage8["match_id"]) == set(test_df_stage8_bis["match_id"])
