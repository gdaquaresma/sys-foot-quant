"""Garde-fous anti-fuite pour E9
(scripts/run_stage18_e9_multi_bookmaker_market_layer.py) :
- le mecanisme point-in-time est INTEGRALEMENT delegue a
  ``multi_bookmaker_odds.build_multi_bookmaker_dataset`` (deja teste,
  reutilise ``matching``/``time_resolution``/``DECISION_OFFSET_HOURS``
  SANS reimplementation) ;
- la probabilite modele Over 2.5 utilisee pour la comparaison au marche
  est INTEGRALEMENT deleguee au pipeline E8 deja valide (walk-forward,
  jamais recalculee ni reajustee ici) ;
- aucune cote de cloture n'est jamais lue (delegue a
  ``football_data_loader._ALLOWED_COLUMNS``, deja teste) ;
- l'overround est retire PAR BOOKMAKER, jamais sur un agregat brut de
  plusieurs bookmakers ;
- l'arbitrage n'est jamais evalue sur une selection sans aucun bookmaker
  disponible (jamais une cote "supposee")."""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage18_e9_multi_bookmaker_market_layer.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e9_module():
    return _load(_SCRIPT_PATH, "run_stage18_e9_multi_bookmaker_market_layer")


# --- 1. point-in-time integralement delegue --------------------------------


def test_e9_never_reimplements_point_in_time_filtering() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    assert "build_multi_bookmaker_dataset" in source
    # aucune reimplementation d'un filtre de connaissance par date ni d'un nouveau timestamp
    assert "AmbiguousCollectionWindowError" not in source
    assert "conservative_knowledge_time_utc" not in source
    assert "knowledge_time" not in source


def test_e9_never_reads_closing_columns() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    for token in ("B365CH", "B365CD", "B365CA", "BWCH", "PSCH", "B365C>2.5", "B365C<2.5", "Close", "close_odds"):
        assert token not in source


# --- 2. probabilite modele deleguee au pipeline E8 deja valide -------------


def test_model_over25_probs_delegates_to_e8_walk_forward_pipeline() -> None:
    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "model_over25_probs_walk_forward")
    body_source = ast.unparse(func)
    assert "attach_walk_forward_scale" in body_source
    assert "fit_scale_correction_as_of" not in body_source  # jamais reimplemente ici
    assert "build_calibration_and_test_sets" in body_source  # meme split que E8, jamais un nouveau split


def test_model_over25_probs_restricted_to_test_split(e9_module) -> None:
    """La fonction doit filtrer sur les IDs du split TEST d'E8 (jamais le
    split calibration/rodage) - verifie par inspection du corps."""
    import ast

    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "model_over25_probs_walk_forward")
    body_source = ast.unparse(func)
    assert "test_ids" in body_source
    assert "test_df" in body_source


# --- 3. overround jamais mele entre bookmakers ------------------------------


def test_normalized_probs_never_average_raw_odds_across_bookmakers(e9_module) -> None:
    # deux bookmakers avec des cotes tres differentes -> si l'overround
    # etait retire sur un agregat brut plutot que par bookmaker, le
    # resultat ne serait PAS une probabilite valide par bookmaker.
    odds = {"H": {"B365": 1.50, "BW": 10.0}, "D": {"B365": 4.00, "BW": 4.00}, "A": {"B365": 6.00, "BW": 1.10}}
    out = e9_module.normalized_probs_by_selection(odds)
    b365_sum = out["H"]["B365"] + out["D"]["B365"] + out["A"]["B365"]
    bw_sum = out["H"]["BW"] + out["D"]["BW"] + out["A"]["BW"]
    assert b365_sum == pytest.approx(1.0)
    assert bw_sum == pytest.approx(1.0)
    # les deux bookmakers, tres differents en cotes brutes, restent
    # DISTINCTS apres normalisation - jamais fusionnes en un seul chiffre
    assert out["H"]["B365"] != pytest.approx(out["H"]["BW"], rel=0.1)


# --- 4. arbitrage jamais evalue sur une cote absente ------------------------


def test_arbitrage_never_evaluated_with_a_missing_selection(e9_module) -> None:
    odds = {"Over": {"B365": 1.90}, "Under": {}}  # Under indisponible a la decision
    assert e9_module.arbitrage_for_market(odds) is None


def test_arbitrage_never_invents_a_bookmaker_price() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    tree = ast.parse(source)
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "arbitrage_for_market")
    body_source = ast.unparse(func)
    assert "detect_mathematical_arbitrage" in body_source
    assert "default" not in body_source.lower()


# --- 5. non-regression : corpus multi-bookmaker == corpus E1/E5 -----------


@pytest.mark.skipif(
    not (Path(__file__).resolve().parent.parent.parent / "research" / "market_odds" / "football_data" / "runs").exists(),
    reason="Fichiers Football-Data reels non presents.",
)
def test_real_corpus_multi_bookmaker_matches_e1_e5_baseline(e9_module) -> None:
    """``load_all_multi_bookmaker_records`` retourne les matchs EXPLOITABLES
    (apres exclusion jour ambigu + violation PIT), donc strictement moins
    que les 2123 matchs APPARIES (deja verifie au niveau du module dans
    test_multi_bookmaker_odds_point_in_time.py) - non-regression large
    plutot qu'une egalite exacte, plus l'invariant PIT sur chaque match."""
    records = e9_module.load_all_multi_bookmaker_records()
    assert 1700 <= len(records) < 2123
    for r in records:
        assert r.knowledge_time_utc <= r.decision_time_utc
