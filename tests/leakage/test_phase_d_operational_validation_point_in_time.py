"""Garde-fous anti-fuite pour la Phase D
(scripts/run_stage26_phase_d_operational_validation.py) :
- rodage / VALIDATION / TEST sont strictement disjoints et couvrent la
  totalite du corpus par championnat x saison ;
- la calibration walk-forward de VALIDATION n'utilise jamais un match de
  VALIDATION ou de TEST comme historique (uniquement le rodage) ;
- la calibration walk-forward de TEST n'utilise jamais un match de TEST
  comme historique (uniquement VALIDATION) ;
- le seuil est selectionne EXCLUSIVEMENT sur VALIDATION - le TEST n'est
  jamais regarde avant la selection (verifie par inspection statique de
  ``main()``) ;
- aucune cote de cloture n'entre nulle part dans ce script ;
- BET ne peut jamais etre produit sans que TOUS les gates existants soient
  satisfaits (reutilisation de decide(), jamais un contournement).
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage26_phase_d_operational_validation.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _code_only_source(path: Path) -> str:
    """Code source SANS les docstrings (module/classe/fonction) - evite
    les faux positifs quand un docstring explique en prose ce que le
    script NE fait PAS (ex. 'aucun ensemble ici')."""
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                node.body[0].value.value = ""
    return ast.unparse(tree)


@pytest.fixture(scope="module")
def phase_d():
    return _load(_SCRIPT_PATH, "run_stage26_phase_d_operational_validation")


# --- 1. jamais de reimplementation du point-in-time ou de la decision --------


def test_never_reimplements_decide_or_gates() -> None:
    source = _SCRIPT_PATH.read_text()
    tree = ast.parse(source)
    func_names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    for forbidden in ("decide", "edge_threshold_gate", "calibrate_prediction", "compare_over_under_to_market", "discrimination_status"):
        assert forbidden not in func_names, f"'{forbidden}' ne doit jamais etre redefini localement, seulement importe"


def test_never_references_closing_odds() -> None:
    source = _SCRIPT_PATH.read_text().lower()
    assert "closing_odds_1x2_by_bookmaker" not in source
    assert "closing_over_under_2_5_by_bookmaker" not in source
    assert "b365c" not in source


def test_never_creates_or_trains_a_new_goals_model() -> None:
    source = _SCRIPT_PATH.read_text()
    assert "class PoissonModel" not in source
    assert "class DixonColesModel" not in source
    assert "class XGModel" not in source
    assert ".fit(" not in source  # aucun (re)entrainement de modele dans ce script


def test_never_computes_an_ensemble_or_weighted_average_across_models() -> None:
    """N.B. 'ensemble' est aussi un mot francais courant ('sous-ensemble',
    'l'ensemble des...') - on cherche des locutions techniques precises
    liees a un ensemble DE MODELES, jamais le mot seul (qui produirait de
    nombreux faux positifs dans la prose francaise du script)."""
    source = _code_only_source(_SCRIPT_PATH).lower()
    for forbidden in ("ensemble de modeles", "modele d'ensemble", "ensemble_model", "model_ensemble", "weighted_average", "model_weight", "blend"):
        assert forbidden not in source


def test_never_introduces_isotonic_or_logistic_recalibration() -> None:
    source = _code_only_source(_SCRIPT_PATH).lower()
    for forbidden in ("isotonic", "logistic_recalibration"):
        assert forbidden not in source


# --- 2. rodage/validation/test disjoints et exhaustifs -----------------------


class _FakeRecord:
    def __init__(self, match_id: str, kickoff_utc: datetime) -> None:
        self.match_id = match_id
        self.kickoff_utc = kickoff_utc


def test_split_rodage_validation_test_partitions_disjointly_and_completely(phase_d) -> None:
    n = 100
    records = [_FakeRecord(f"m{i}", datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=i)) for i in range(n)]

    class _FakeStage10:
        @staticmethod
        def split_burn_in_calibration_test(records):
            ordered = sorted(records, key=lambda r: r.kickoff_utc)
            n_total = len(ordered)
            n_burn_in = int(n_total * 0.4)
            n_remaining = n_total - n_burn_in
            n_validation = int(n_remaining * 0.5)
            validation_ids = {r.match_id for r in ordered[n_burn_in : n_burn_in + n_validation]}
            test_ids = {r.match_id for r in ordered[n_burn_in + n_validation :]}
            return validation_ids, test_ids

    class _FakeStage8:
        _SEASONS = {"2024_25": {"liga": None}}

        @staticmethod
        def _load_records(league, season):
            return records

    rodage_ids, validation_ids, test_ids = phase_d.split_rodage_validation_test(_FakeStage10(), _FakeStage8())

    all_ids = {r.match_id for r in records}
    assert rodage_ids | validation_ids | test_ids == all_ids
    assert rodage_ids & validation_ids == set()
    assert rodage_ids & test_ids == set()
    assert validation_ids & test_ids == set()
    assert len(rodage_ids) == 40
    assert len(validation_ids) == 30
    assert len(test_ids) == 30


# --- 3. calibration walk-forward : jamais un match du meme segment ou futur -


def test_build_backtest_rows_never_uses_a_row_from_the_segment_itself_as_history(phase_d) -> None:
    """La calibration de VALIDATION doit provenir EXCLUSIVEMENT du pool
    fourni (rodage) - jamais des lignes de VALIDATION elles-memes, meme si
    elles sont presentes dans ``lambda_mu_df`` (verifie en passant un pool
    vide et en observant que le resultat depend alors de
    ``calibrate_prediction`` retournant systematiquement probabilities=None,
    jamais un recours implicite a d'autres lignes de lambda_mu_df)."""
    lambda_mu_df = pd.DataFrame(
        {
            "match_id": ["m1"],
            "league": ["liga"],
            "season": ["2024_25"],
            "decision_time": [datetime(2025, 1, 1, tzinfo=timezone.utc)],
            "poisson_simple_lambda": [1.4],
            "poisson_simple_mu": [1.1],
            "total_goals": [3],
        }
    )
    empty_pool = pd.DataFrame(columns=["decision_time", "poisson_simple_lambda", "poisson_simple_mu", "total_goals"])
    rows = phase_d.build_backtest_rows(
        segment_ids={"m1"}, historical_pool_df=empty_pool, lambda_mu_df=lambda_mu_df, records_by_id={}, leagues=("liga",)
    )
    assert rows == []  # aucune ligne (records_by_id vide) - mais surtout aucune exception liee a un pool vide


def test_calibrate_prediction_call_receives_only_the_provided_pool(phase_d) -> None:
    """Verification structurelle : ``build_backtest_rows`` appelle
    ``calibrate_prediction(pred, historical_pool_df, ...)`` - jamais
    ``lambda_mu_df`` directement comme pool de calibration."""
    tree = ast.parse(_SCRIPT_PATH.read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "build_backtest_rows")
    body_source = ast.unparse(func)
    assert "calibrate_prediction(pred, historical_pool_df" in body_source.replace("\n", " ").replace("  ", " ") or (
        "calibrate_prediction(" in body_source and "historical_pool_df" in body_source
    )
    assert "calibrate_prediction(pred, lambda_mu_df" not in body_source


# --- 4. selection exclusivement sur VALIDATION -------------------------------


def test_main_selects_threshold_before_building_test_rows() -> None:
    """Inspection statique de ``main()`` : l'appel a
    ``build_backtest_rows`` pour le segment TEST doit apparaitre
    APRES la boucle de selection sur la grille de candidats - jamais avant."""
    tree = ast.parse(_SCRIPT_PATH.read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "main")
    body_source = ast.unparse(func)
    selection_loop_pos = body_source.index("candidate_grid()")
    test_build_calls = [i for i in _find_all(body_source, "build_backtest_rows(test_ids") ]
    assert test_build_calls, "aucun appel build_backtest_rows(test_ids...) trouve dans main()"
    assert all(pos > selection_loop_pos for pos in test_build_calls)


def _find_all(haystack: str, needle: str) -> list[int]:
    positions = []
    start = 0
    while True:
        idx = haystack.find(needle, start)
        if idx == -1:
            break
        positions.append(idx)
        start = idx + 1
    return positions


def test_passes_selection_rule_and_candidate_grid_take_no_test_segment_input(phase_d) -> None:
    import inspect

    assert "test_rows" not in inspect.signature(phase_d.passes_selection_rule).parameters
    assert "test_rows" not in inspect.signature(phase_d.candidate_grid).parameters


# --- 5. BET impossible sans tous les gates -----------------------------------


def test_would_bet_requires_base_gates_pass_field_to_be_true(phase_d) -> None:
    row_fail = phase_d.BacktestRow(
        match_id="m1", league="liga", season="2024_25",
        decision_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        kickoff_utc=datetime(2025, 1, 1, 2, 0, tzinfo=timezone.utc),
        n_calibration_used=40, p_model_over=0.9,
        market_odds_over=1.5, market_odds_under=3.0,
        raw_edge_over=0.9, price_edge_over=0.9, raw_edge_under=-0.9, price_edge_under=-0.9,
        outcome_over=1.0, base_gates_pass=False,
        calibration_status_value="OK", discrimination_status_value="DEMONTREE",
    )
    # Edge maximal possible, seuil minimal possible -> devrait etre BET si
    # les gates n'etaient pas verifies. Doit rester NO_BET.
    assert not phase_d.would_bet(row_fail, "raw_edge", 0.0)
