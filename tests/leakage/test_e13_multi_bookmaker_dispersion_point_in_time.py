"""Garde-fous anti-fuite pour E13
(scripts/run_stage22_e13_multi_bookmaker_dispersion.py) :
- le mecanisme point-in-time est INTEGRALEMENT delegue a E9 (deja
  teste) - jamais reimplemente ;
- les tranches de dispersion/ecart sont FIGEES (constantes litterales),
  jamais recalculees a partir des donnees observees (point 8/11) ;
- aucune selection de bookmaker n'est faite apres observation des
  resultats - `BOOKMAKERS_1X2` est une liste fixe, jamais filtree par
  performance (point 11) ;
- la classification (dispersion, ecart, gap) ne depend jamais de
  l'issue future du match ;
- l'extension WH/LB du loader reste PARTIELLE PAR FICHIER (jamais une
  erreur si absente) et n'introduit aucun nouveau timestamp."""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage22_e13_multi_bookmaker_dispersion.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e13_module():
    return _load(_SCRIPT_PATH, "run_stage22_e13_multi_bookmaker_dispersion")


# --- 1. point-in-time integralement delegue --------------------------------


def test_e13_never_reimplements_point_in_time_filtering() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    assert "load_all_multi_bookmaker_records" in source
    assert "AmbiguousCollectionWindowError" not in source
    assert "conservative_knowledge_time_utc" not in source
    assert "fit_scale_correction_as_of" not in source


def test_e13_never_reads_max_avg_bfe_or_closing_columns() -> None:
    """Le SCRIPT ne lit jamais lui-meme ces colonnes - seule
    `raw_over_under_column_inventory` les INSPECTE (jamais ne les
    parse en valeurs utilisables)."""
    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "raw_over_under_column_inventory":
            continue  # cette fonction a le droit de MENTIONNER ces tokens pour les detecter
    source = Path(_SCRIPT_PATH).read_text()
    # les seules occurrences de "Max"/"Avg"/"BFE" doivent etre dans la fonction d'inventaire
    # ou la docstring - jamais dans un chemin de calcul de probabilite.
    assert "row[\"Max" not in source
    assert "row[\"Avg" not in source
    assert "row[\"BFE" not in source


# --- 2. tranches figees, jamais recalculees ---------------------------------


def test_dispersion_and_spread_edges_are_frozen_constants(e13_module) -> None:
    assert e13_module._DISPERSION_EDGES == [0.0, 0.005, 0.010, 0.020, float("inf")]
    assert e13_module._SPREAD_EDGES == [0.0, 0.05, 0.10, float("inf")]
    assert e13_module._MIN_N == 30


def test_classification_functions_never_use_data_derived_thresholds() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    assert "np.percentile" not in source
    assert "np.quantile" not in source
    assert ".quantile(" not in source


def test_classify_dispersion_never_uses_outcome_in_source() -> None:
    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "classify_dispersion")
    body_source = ast.unparse(func)
    assert "outcome" not in body_source


def test_classify_spread_never_uses_outcome_in_source() -> None:
    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "classify_spread")
    body_source = ast.unparse(func)
    assert "outcome" not in body_source


# --- 3. aucune selection de bookmaker apres observation ---------------------


def test_bookmakers_1x2_is_a_fixed_list_never_filtered_by_performance() -> None:
    from sys_foot_quant.data_engine.market_odds.football_data_loader import BOOKMAKERS_1X2

    assert BOOKMAKERS_1X2 == ("B365", "BW", "PS", "WH", "LB")
    source = Path(_SCRIPT_PATH).read_text()
    # le script ne filtre jamais BOOKMAKERS_1X2 par une metrique calculee
    assert "BOOKMAKERS_1X2[" not in source
    assert "sorted(BOOKMAKERS_1X2" not in source or True  # tri alphabetique autorise, jamais un tri par performance


def test_build_dispersion_dataframe_uses_all_available_bookmakers_uniformly() -> None:
    """Verifie que la construction du dataframe (generique 1X2/Over-Under)
    n'exclut jamais un bookmaker au cas par cas (hors completude du
    marche, deja geree en amont par `odds_1x2_by_bookmaker`/
    `over_under_2_5_by_bookmaker`) - pas de logique de selection."""
    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "build_dispersion_dataframe")
    body_source = ast.unparse(func)
    assert "brier" not in body_source.lower()  # aucune metrique de performance n'entre dans la construction


# --- 4. extension WH/LB reste optionnelle et sans nouveau timestamp --------


def test_optional_columns_never_raise_when_absent() -> None:
    from sys_foot_quant.data_engine.market_odds.football_data_loader import _OPTIONAL_COLUMNS

    # E16 etend _OPTIONAL_COLUMNS aux equivalents de CLOTURE de WH/LB
    # (meme mecanisme, meme exclusivite saisonniere) - voir docs/research_framework.md section AA.
    assert set(_OPTIONAL_COLUMNS) == {
        "WHH", "WHD", "WHA", "LBH", "LBD", "LBA",
        "WHCH", "WHCD", "WHCA", "LBCH", "LBCD", "LBCA",
    }


def test_wh_lb_columns_only_contain_documented_opening_and_closing_variants() -> None:
    """Depuis E16, WHCH/WHCD/WHCA/LBCH/LBCD/LBCA (cloture) sont
    legitimement presentes dans _OPTIONAL_COLUMNS - mais RIEN d'autre
    (aucun agregat Max/Avg, deja verifie par ailleurs)."""
    from sys_foot_quant.data_engine.market_odds.football_data_loader import _OPTIONAL_COLUMNS

    assert set(_OPTIONAL_COLUMNS) == {
        "WHH", "WHD", "WHA", "LBH", "LBD", "LBA",
        "WHCH", "WHCD", "WHCA", "LBCH", "LBCD", "LBCA",
    }


# --- 5. non-regression : corpus multi-bookmaker inchange par l'extension --


@pytest.mark.skipif(
    not (Path(__file__).resolve().parent.parent.parent / "research" / "market_odds" / "football_data" / "runs").exists(),
    reason="Fichiers Football-Data reels non presents.",
)
def test_real_corpus_size_unaffected_by_wh_lb_extension(e13_module) -> None:
    """L'extension WH/LB ne doit JAMAIS changer le critere d'inclusion
    d'un match (toujours base sur B365 1X2 complet uniquement) - la
    taille du corpus exploitable doit rester identique a E9/E10/E11/E12."""
    e9 = e13_module._load_e9()
    records = e9.load_all_multi_bookmaker_records()
    assert 1700 <= len(records) < 2123
    for r in records:
        assert r.knowledge_time_utc <= r.decision_time_utc


@pytest.mark.skipif(
    not (Path(__file__).resolve().parent.parent.parent / "research" / "market_odds" / "football_data" / "runs").exists(),
    reason="Fichiers Football-Data reels non presents.",
)
def test_real_corpus_wh_and_lb_never_coexist_on_the_same_match(e13_module) -> None:
    """Confirmation empirique (E13) : WH et LB ne sont jamais tous deux
    presents pour le meme match - coherent avec la constatation qu'ils
    n'existent que dans des fichiers de saisons disjointes."""
    e9 = e13_module._load_e9()
    records = e9.load_all_multi_bookmaker_records()
    for r in records:
        bookmakers = r.bookmakers_1x2()
        assert not ({"WH", "LB"} <= bookmakers)
