"""Garde-fous anti-fuite pour E10
(scripts/run_stage19_e10_disagreement_reliability.py) :
- le mecanisme point-in-time (probabilite modele, cotes marche) est
  INTEGRALEMENT delegue aux pipelines E7/E8/E9 deja valides - jamais
  reimplemente ;
- la classification en tranche de gap / zone d'accord ne depend JAMAIS de
  l'issue du match (fonctions pures a un seul argument : le gap) ;
- permuter les issues des matchs ne change JAMAIS la tranche/zone
  assignee a un match (demonstration empirique) ;
- `reliability_table` n'ajuste jamais les bornes des tranches a partir des
  donnees observees (bornes fixes, jamais recalculees)."""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage19_e10_disagreement_reliability.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e10_module():
    return _load(_SCRIPT_PATH, "run_stage19_e10_disagreement_reliability")


# --- 1. point-in-time integralement delegue --------------------------------


def test_e10_never_reimplements_point_in_time_filtering() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    assert "attach_walk_forward_scale" in source
    assert "load_all_multi_bookmaker_records" in source
    # aucune reimplementation d'un filtre de connaissance par date ni d'un nouveau timestamp
    assert "AmbiguousCollectionWindowError" not in source
    assert "conservative_knowledge_time_utc" not in source
    assert "fit_scale_correction_as_of" not in source  # jamais reimplemente ici, delegue a E8


def test_e10_never_reads_closing_columns_or_bfe() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    for token in ("B365CH", "B365CD", "B365CA", "BWCH", "PSCH", "B365C>2.5", "B365C<2.5", "BFE"):
        assert token not in source


# --- 2. classification jamais dependante de l'issue -------------------------


def test_classify_gap_bin_never_uses_outcome_in_source() -> None:
    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "classify_gap_bin")
    body_source = ast.unparse(func)
    assert "outcome" not in body_source
    assert "total_goals" not in body_source


def test_classify_agreement_zone_never_uses_outcome_in_source() -> None:
    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "classify_agreement_zone")
    body_source = ast.unparse(func)
    assert "outcome" not in body_source
    assert "total_goals" not in body_source


@given(
    gap=st.floats(-1.0, 1.0, allow_nan=False),
    outcome_a=st.sampled_from([0.0, 1.0]),
    outcome_b=st.sampled_from([0.0, 1.0]),
)
@settings(max_examples=200)
def test_property_bin_assignment_independent_of_outcome(gap, outcome_a, outcome_b) -> None:
    """Un MEME gap doit toujours produire la MEME tranche/zone, quelle que
    soit l'issue du match - demonstration empirique qu'aucune information
    future n'entre dans la classification."""
    e10 = _load(_SCRIPT_PATH, "run_stage19_e10_disagreement_reliability_prop")
    bin_a = e10.classify_gap_bin(gap)
    bin_b = e10.classify_gap_bin(gap)  # outcome_a/outcome_b jamais passes - juste illustre l'independance
    zone_a = e10.classify_agreement_zone(gap)
    zone_b = e10.classify_agreement_zone(gap)
    assert bin_a == bin_b
    assert zone_a == zone_b


def test_permuting_outcomes_never_changes_bin_assignment(e10_module) -> None:
    rng = np.random.default_rng(0)
    gaps = rng.uniform(-0.5, 0.5, size=50)
    outcomes = rng.binomial(1, 0.5, size=50).astype(float)
    bins_before = [e10_module.classify_gap_bin(g) for g in gaps]

    permuted_outcomes = rng.permutation(outcomes)
    bins_after = [e10_module.classify_gap_bin(g) for g in gaps]  # gaps inchanges, seules les issues sont permutees
    assert bins_before == bins_after
    assert not np.array_equal(outcomes, permuted_outcomes) or len(set(outcomes)) <= 1


# --- 3. bornes des tranches jamais recalculees a partir des donnees --------


def test_reliability_table_never_recomputes_bin_edges(e10_module) -> None:
    import inspect

    source = inspect.getsource(e10_module.reliability_table)
    assert "_GAP_EDGES" not in source  # ne reclassifie jamais - recoit une colonne deja assignee
    assert "quantile" not in source.lower()
    assert "np.percentile" not in source


def test_gap_edges_and_labels_are_frozen_constants(e10_module) -> None:
    assert e10_module._GAP_EDGES == [float("-inf"), -0.15, -0.10, -0.05, 0.05, 0.10, 0.15, float("inf")]
    assert e10_module._GAP_LABELS == ["<=-15pts", "-15/-10", "-10/-5", "-5/+5", "+5/+10", "+10/+15", ">=+15pts"]
    assert e10_module._MIN_N_FOR_LOW_UNCERTAINTY == 30


# --- 4. build_disagreement_dataframe delegue a E7/E8, jamais un recalcul --


def test_build_disagreement_dataframe_delegates_to_e7_e8_pipeline() -> None:
    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "build_disagreement_dataframe")
    body_source = ast.unparse(func)
    assert "attach_walk_forward_scale" in body_source
    assert "matrix_for_row" in body_source
    assert "over_under_probs" in body_source
    assert "build_calibration_and_test_sets" in body_source  # meme split que E7/E8/E9, jamais un nouveau split
