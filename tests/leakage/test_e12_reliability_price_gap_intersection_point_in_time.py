"""Garde-fous anti-fuite pour E12
(scripts/run_stage21_e12_reliability_price_gap_intersection.py) :
- toute la mecanique point-in-time (probabilite modele, cotes marche) est
  INTEGRALEMENT deleguee aux pipelines E7/E8/E9/E11 deja valides -
  jamais reimplementee ;
- les tranches de probabilite sont FIXEES ex ante (deleguees a
  `bin_index_for_prob`/`calibration_table` d'E11 - jamais recalculees
  ici) ;
- la classification de fiabilite d'une tranche et le verdict de
  l'hypothese centrale ne dependent QUE de statistiques deja agregees
  (n, bornes d'IC95%) - jamais d'une observation individuelle future ;
- aucune information posterieure au decision_time n'intervient dans la
  definition d'une zone de fiabilite ou d'un seuil (point 7 du
  protocole)."""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage21_e12_reliability_price_gap_intersection.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e12_module():
    return _load(_SCRIPT_PATH, "run_stage21_e12_reliability_price_gap_intersection")


# --- 1. point-in-time integralement delegue --------------------------------


def test_e12_never_reimplements_point_in_time_filtering() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    assert "build_threshold_dataframe" in source
    assert "build_market_comparison_dataframe" in source
    assert "load_all_multi_bookmaker_records" in source
    assert "AmbiguousCollectionWindowError" not in source
    assert "conservative_knowledge_time_utc" not in source
    assert "fit_scale_correction_as_of" not in source  # jamais reimplemente, delegue a E8
    assert "attach_walk_forward_scale" not in source  # delegue a build_threshold_dataframe (E11)


def test_e12_never_reads_closing_columns_or_bfe() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    for token in ("B365CH", "B365CD", "B365CA", "BWCH", "PSCH", "B365C>2.5", "B365C<2.5", "BFE"):
        assert token not in source


# --- 2. tranches de probabilite jamais recalculees ici ----------------------


def test_e12_never_redefines_probability_bins() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    assert "np.linspace" not in source  # les bornes de tranche viennent d'E11, jamais redefinies
    assert "np.digitize" not in source


# --- 3. classification ne depend que de statistiques deja agregees --------


def test_classify_bin_reliability_signature_is_pure_summary_stats() -> None:
    import inspect

    e12 = _load(_SCRIPT_PATH, "run_stage21_e12_reliability_price_gap_intersection_sig")
    sig = inspect.signature(e12.classify_bin_reliability)
    assert list(sig.parameters) == ["n", "ci_low", "ci_high", "min_n"]
    # jamais un DataFrame brut, jamais une issue individuelle, jamais un match_id


def test_classify_hypothesis_verdict_signature_is_pure_summary_stats() -> None:
    import inspect

    e12 = _load(_SCRIPT_PATH, "run_stage21_e12_reliability_price_gap_intersection_sig2")
    sig = inspect.signature(e12.classify_hypothesis_verdict)
    assert list(sig.parameters) == ["boot"]


def test_classify_bin_reliability_never_uses_outcome_in_source() -> None:
    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "classify_bin_reliability")
    body_source = ast.unparse(func)
    assert "outcome" not in body_source
    assert "total_goals" not in body_source


# --- 4. le test central n'utilise que des donnees deja construites par les
# pipelines en amont - jamais un nouveau calcul de probabilite/correction --


def test_reliable_bins_have_larger_gaps_never_recomputes_model_probability() -> None:
    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "test_reliable_bins_have_larger_gaps")
    body_source = ast.unparse(func)
    assert "matrix_for_row" not in body_source
    assert "over_under_probs" not in body_source
    assert "attach_walk_forward_scale" not in body_source


def test_joint_bin_table_never_recomputes_market_probability() -> None:
    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "joint_bin_table")
    body_source = ast.unparse(func)
    assert "remove_overround_proportional" not in body_source
    assert "hold_percentage" not in body_source


# --- 5. non-regression : delegue au meme split TEST walk-forward qu'E8/E11 --


def test_main_uses_e11_build_threshold_dataframe_not_a_new_split() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    assert "e11.build_threshold_dataframe" in source
    assert "e11.calibration_table" in source
    assert "e11.build_market_comparison_dataframe" in source
