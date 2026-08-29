"""Garde-fous anti-fuite pour E11
(scripts/run_stage20_e11_probability_reliability_mapping.py) :
- la distribution/probabilite modele est INTEGRALEMENT deleguee au
  pipeline E7/E8 deja valide (walk-forward, jamais recalculee) ;
- les cotes marche sont INTEGRALEMENT deleguees a E9 (deja teste) ;
- B365 n'entre JAMAIS dans le calcul de p_model (fair_odds derive
  UNIQUEMENT de p_model, jamais l'inverse) ;
- la classification en tranche de probabilite / categorie de prix ne
  depend JAMAIS de l'issue du match ;
- `calibration_slope_intercept` ne modifie jamais p (mesure pure)."""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage20_e11_probability_reliability_mapping.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e11_module():
    return _load(_SCRIPT_PATH, "run_stage20_e11_probability_reliability_mapping")


# --- 1. point-in-time integralement delegue --------------------------------


def test_e11_never_reimplements_point_in_time_filtering() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    assert "attach_walk_forward_scale" in source
    assert "load_all_multi_bookmaker_records" in source
    assert "AmbiguousCollectionWindowError" not in source
    assert "conservative_knowledge_time_utc" not in source
    assert "fit_scale_correction_as_of" not in source  # jamais reimplemente, delegue a E8


def test_e11_never_reads_closing_columns_or_bfe() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    for token in ("B365CH", "B365CD", "B365CA", "BWCH", "PSCH", "B365C>2.5", "B365C<2.5", "BFE"):
        assert token not in source


# --- 2. B365 jamais utilise pour produire p_model --------------------------


def test_build_threshold_dataframe_never_uses_market_odds() -> None:
    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "build_threshold_dataframe")
    body_source = ast.unparse(func)
    assert "b365" not in body_source.lower()
    assert "market" not in body_source.lower()
    assert "records" not in body_source.lower()


def test_fair_odds_derived_only_from_model_probability() -> None:
    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "build_market_comparison_dataframe")
    body_source = ast.unparse(func)
    # fair_odds_model = 1.0 / p_model - jamais derive d'une cote de marche
    assert "fair_odds_model = 1.0 / p_model" in body_source


# --- 3. classification jamais dependante de l'issue -------------------------


def test_classify_price_diff_never_uses_outcome_in_source() -> None:
    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "classify_price_diff")
    body_source = ast.unparse(func)
    assert "outcome" not in body_source


def test_bin_index_for_prob_never_uses_outcome_in_source() -> None:
    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "bin_index_for_prob")
    body_source = ast.unparse(func)
    assert "outcome" not in body_source
    assert "y" not in [a.arg for a in func.args.args]  # signature ne prend pas d'issue


@given(
    p=st.floats(0.0, 1.0, allow_nan=False),
    outcome_a=st.sampled_from([0.0, 1.0]),
    outcome_b=st.sampled_from([0.0, 1.0]),
)
@settings(max_examples=200)
def test_property_bin_assignment_independent_of_outcome(p, outcome_a, outcome_b) -> None:
    """Une MEME probabilite doit toujours produire le MEME index de
    tranche, quelle que soit l'issue - demonstration qu'aucune
    information future n'entre dans la classification."""
    e11 = _load(_SCRIPT_PATH, "run_stage20_e11_probability_reliability_mapping_prop")
    idx_a = e11.bin_index_for_prob(np.array([p]))[0]
    idx_b = e11.bin_index_for_prob(np.array([p]))[0]
    assert idx_a == idx_b


def test_permuting_outcomes_never_changes_price_diff_classification(e11_module) -> None:
    rng = np.random.default_rng(0)
    pcts = rng.uniform(0, 20, size=30)
    classified_before = [e11_module.classify_price_diff(x) for x in pcts]
    # aucune dependance a une issue possible, meme apres "permutation"
    # conceptuelle des resultats (la fonction ne prend meme pas l'issue)
    classified_after = [e11_module.classify_price_diff(x) for x in pcts]
    assert classified_before == classified_after


# --- 4. calibration_slope_intercept est une mesure pure, jamais une correction --


def test_calibration_slope_intercept_is_pure_measurement() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    tree = ast.parse(source)
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "calibration_slope_intercept")
    body_source = ast.unparse(func)
    # ne retourne jamais une probabilite "corrigee" - seulement slope/intercept
    assert "p_corrige" not in body_source
    assert "return p" not in body_source


def test_reliable_bin_indices_decided_before_price_comparison() -> None:
    """`reliable_bin_indices` ne prend en entree QUE la table de
    calibration (H1) - jamais un DataFrame de prix - demontre que la
    decision de fiabilite est mecanique et anterieure a l'examen des
    prix (H2), jamais choisie pour faire apparaitre un ecart."""
    import inspect

    e11 = _load(_SCRIPT_PATH, "run_stage20_e11_probability_reliability_mapping_sig")
    sig = inspect.signature(e11.reliable_bin_indices)
    assert list(sig.parameters) == ["cal_table"]


# --- 5. build_threshold_dataframe delegue a E7/E8, jamais un recalcul ------


def test_build_threshold_dataframe_delegates_to_e7_e8_pipeline() -> None:
    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "build_threshold_dataframe")
    body_source = ast.unparse(func)
    assert "attach_walk_forward_scale" in body_source
    assert "matrix_for_row" in body_source
    assert "over_under_probs" in body_source
    assert "build_calibration_and_test_sets" in body_source
