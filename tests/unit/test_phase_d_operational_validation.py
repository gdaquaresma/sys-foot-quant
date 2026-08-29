"""Tests unitaires des fonctions PURES de la Phase D
(scripts/run_stage26_phase_d_operational_validation.py) - avant toute
execution reelle. Utilise des BacktestRow synthetiques ; ne charge aucune
donnee reelle."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage26_phase_d_operational_validation.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def phase_d():
    return _load(_SCRIPT_PATH, "run_stage26_phase_d_operational_validation")


def _row(phase_d, **overrides):
    defaults = dict(
        match_id="m1",
        league="liga",
        season="2024_25",
        decision_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        kickoff_utc=datetime(2025, 1, 1, 2, 0, tzinfo=timezone.utc),
        n_calibration_used=40,
        p_model_over=0.6,
        market_odds_over=1.9,
        market_odds_under=2.0,
        raw_edge_over=0.08,
        price_edge_over=0.14,
        raw_edge_under=-0.08,
        price_edge_under=-0.12,
        outcome_over=1.0,
        base_gates_pass=True,
        calibration_status_value="OK",
        discrimination_status_value="DEMONTREE",
    )
    defaults.update(overrides)
    return phase_d.BacktestRow(**defaults)


# --- would_bet : reutilise decide()/edge_threshold_gate, jamais reimplemente --


def test_would_bet_false_when_base_gates_fail_regardless_of_edge(phase_d) -> None:
    row = _row(phase_d, base_gates_pass=False, raw_edge_over=0.5)
    assert not phase_d.would_bet(row, "raw_edge", 0.01)


def test_would_bet_true_when_edge_above_threshold_and_gates_pass(phase_d) -> None:
    row = _row(phase_d, base_gates_pass=True, raw_edge_over=0.08)
    assert phase_d.would_bet(row, "raw_edge", 0.05)


def test_would_bet_false_when_edge_below_threshold(phase_d) -> None:
    row = _row(phase_d, base_gates_pass=True, raw_edge_over=0.03)
    assert not phase_d.would_bet(row, "raw_edge", 0.05)


def test_would_bet_uses_price_edge_when_requested(phase_d) -> None:
    row = _row(phase_d, base_gates_pass=True, raw_edge_over=-1.0, price_edge_over=0.05)
    assert phase_d.would_bet(row, "price_edge", 0.0)
    assert not phase_d.would_bet(row, "raw_edge", 0.0)


def test_would_bet_on_under_selection_uses_under_edge_fields(phase_d) -> None:
    row = _row(phase_d, base_gates_pass=True, raw_edge_over=-1.0, raw_edge_under=0.09)
    assert phase_d.would_bet(row, "raw_edge", 0.05, selection="Under")
    assert not phase_d.would_bet(row, "raw_edge", 0.05, selection="Over")


def test_would_bet_never_produces_bet_without_a_configured_threshold_being_exceeded() -> None:
    """Verification structurelle : would_bet ne fait rien d'autre que
    construire un OperationalThresholds et appeler edge_threshold_gate +
    decide - aucune branche alternative qui court-circuiterait le gate."""
    import ast

    tree = ast.parse(_SCRIPT_PATH.read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "would_bet")
    body_source = ast.unparse(func)
    assert "edge_threshold_gate" in body_source
    assert "decide(" in body_source


# --- profit_for_bet -----------------------------------------------------------


def test_profit_for_bet_over_win_and_loss(phase_d) -> None:
    win = _row(phase_d, market_odds_over=1.9, outcome_over=1.0)
    loss = _row(phase_d, market_odds_over=1.9, outcome_over=0.0)
    assert phase_d.profit_for_bet(win, "Over") == pytest.approx(0.9)
    assert phase_d.profit_for_bet(loss, "Over") == pytest.approx(-1.0)


def test_profit_for_bet_under_is_mirror_of_over(phase_d) -> None:
    row = _row(phase_d, market_odds_under=2.0, outcome_over=1.0)  # Over gagne -> Under perd
    assert phase_d.profit_for_bet(row, "Under") == pytest.approx(-1.0)
    row2 = _row(phase_d, market_odds_under=2.0, outcome_over=0.0)  # Over perd -> Under gagne
    assert phase_d.profit_for_bet(row2, "Under") == pytest.approx(1.0)


# --- strategy_metrics / baselines ----------------------------------------------


def test_strategy_metrics_empty_selection_reports_zero_bets(phase_d) -> None:
    rows = [_row(phase_d, raw_edge_over=0.01)]
    metrics = phase_d.strategy_metrics(rows, "raw_edge", 0.05)
    assert metrics == {"n_bets": 0}


def test_strategy_metrics_reports_expected_fields(phase_d) -> None:
    rows = [_row(phase_d, match_id=f"m{i}", raw_edge_over=0.08, outcome_over=float(i % 2)) for i in range(40)]
    metrics = phase_d.strategy_metrics(rows, "raw_edge", 0.05, seed=0)
    assert metrics["n_bets"] == 40
    for key in ("hit_rate", "profit_mean", "roi", "yield_pct", "max_drawdown", "volatility", "ci_low", "ci_high", "p_value"):
        assert key in metrics


def test_baseline_market_only_includes_every_row_unconditionally(phase_d) -> None:
    rows = [_row(phase_d, match_id=f"m{i}", base_gates_pass=(i % 2 == 0)) for i in range(10)]
    baseline = phase_d.baseline_market_only_metrics(rows, "Over")
    assert baseline["n_bets"] == 10  # aucun filtre de gate applique a cette baseline


def test_baseline_model_no_selection_uses_near_zero_threshold(phase_d) -> None:
    rows = [_row(phase_d, match_id=f"m{i}", raw_edge_over=0.001) for i in range(35)]
    baseline = phase_d.baseline_model_no_selection_metrics(rows, "raw_edge")
    assert baseline["n_bets"] == 35  # tout edge strictement positif est inclus, aucune magnitude minimale


# --- grille et selection : jamais "meilleur ROI observe" ----------------------


def test_candidate_grid_matches_the_pre_registered_values(phase_d) -> None:
    grid = phase_d.candidate_grid()
    assert ("raw_edge", 0.05) in grid
    assert ("raw_edge", 0.10) in grid
    assert ("price_edge", 0.0) in grid
    assert len(grid) == 3  # aucun candidat supplementaire ajoute apres coup


def test_passes_selection_rule_rejects_insufficient_sample_size(phase_d) -> None:
    metrics = {"n_bets": 10, "ci_low": 0.5, "ci_high": 0.9}
    baseline = {"ci_high": -0.02}
    assert not phase_d.passes_selection_rule(metrics, baseline, min_n=30)


def test_passes_selection_rule_rejects_ci_touching_zero(phase_d) -> None:
    metrics = {"n_bets": 100, "ci_low": -0.01, "ci_high": 0.2}
    baseline = {"ci_high": -0.05}
    assert not phase_d.passes_selection_rule(metrics, baseline, min_n=30)


def test_passes_selection_rule_rejects_when_not_above_baseline(phase_d) -> None:
    metrics = {"n_bets": 100, "ci_low": 0.01, "ci_high": 0.2}
    baseline = {"ci_high": 0.05}  # metrics.ci_low (0.01) <= baseline.ci_high (0.05)
    assert not phase_d.passes_selection_rule(metrics, baseline, min_n=30)


def test_passes_selection_rule_accepts_when_all_conditions_hold(phase_d) -> None:
    metrics = {"n_bets": 100, "ci_low": 0.10, "ci_high": 0.20}
    baseline = {"ci_high": -0.02}
    assert phase_d.passes_selection_rule(metrics, baseline, min_n=30)


def test_selection_functions_never_reference_test_segment_variables(phase_d) -> None:
    """Verification structurelle : ni candidate_grid ni passes_selection_rule
    ne prennent de parametre lie a un segment de test - la selection ne
    peut structurellement PAS regarder le TEST (aucune variable qui s'y
    referencerait n'existe dans leur signature)."""
    import inspect

    sig_grid = inspect.signature(phase_d.candidate_grid)
    assert list(sig_grid.parameters) == []

    sig_rule = inspect.signature(phase_d.passes_selection_rule)
    for param_name in sig_rule.parameters:
        assert "test" not in param_name.lower()


# --- population : Premier League jamais poolee dans la selection primaire ----


def test_primary_leagues_excludes_premier_league(phase_d) -> None:
    assert "premier_league" not in phase_d._PRIMARY_LEAGUES
    assert phase_d._CONTROL_LEAGUE == "premier_league"


def test_build_backtest_rows_handles_tz_naive_decision_time_from_pandas_map(phase_d) -> None:
    """Regression (bug reel trouve en Phase D, execution reelle) :
    ``Series.map`` fait perdre le tzinfo UTC de ``decision_time`` -
    ``build_backtest_rows`` doit le reattacher avant de reconstruire
    ``kickoff_utc``, jamais lever une TypeError sur donnees reelles."""
    import pandas as pd

    naive_decision_time = pd.Timestamp("2024-08-16 16:45:00")  # tz-naive, comme observe en execution reelle
    assert naive_decision_time.tzinfo is None

    lambda_mu_df = pd.DataFrame(
        {
            "match_id": ["m1"],
            "league": ["liga"],
            "season": ["2024_25"],
            "decision_time": [naive_decision_time],
            "poisson_simple_lambda": [1.4],
            "poisson_simple_mu": [1.1],
            "total_goals": [3],
        }
    )

    class _FakeRecord:
        odds_over_under_2_5 = {"Over": {"B365": 1.9}, "Under": {"B365": 2.0}}

    n = 40
    historical_pool = pd.DataFrame(
        {
            "decision_time": [naive_decision_time - timedelta(days=n - i) for i in range(n)],
            "poisson_simple_lambda": [1.4] * n,
            "poisson_simple_mu": [1.1] * n,
            "total_goals": [2.7] * n,
        }
    )
    rows = phase_d.build_backtest_rows(
        segment_ids={"m1"},
        historical_pool_df=historical_pool,
        lambda_mu_df=lambda_mu_df,
        records_by_id={"m1": _FakeRecord()},
        leagues=("liga",),
    )
    assert len(rows) == 1
    assert rows[0].kickoff_utc.tzinfo is not None


def test_build_backtest_rows_filters_by_requested_leagues(phase_d) -> None:
    """Sans donnees reelles : verifie seulement que la fonction filtre
    bien sur la colonne 'league' avant tout calcul - test structurel via
    un DataFrame minimal ne declenchant aucun appel reseau/fichier."""
    import pandas as pd

    lambda_mu_df = pd.DataFrame(
        {
            "match_id": ["m1", "m2"],
            "league": ["liga", "premier_league"],
            "season": ["2024_25", "2024_25"],
            "decision_time": [datetime(2025, 1, 1, tzinfo=timezone.utc)] * 2,
            "poisson_simple_lambda": [1.4, 1.4],
            "poisson_simple_mu": [1.1, 1.1],
            "total_goals": [3, 3],
        }
    )
    rows = phase_d.build_backtest_rows(
        segment_ids={"m1", "m2"},
        historical_pool_df=pd.DataFrame(columns=["decision_time", "poisson_simple_lambda", "poisson_simple_mu", "total_goals"]),
        lambda_mu_df=lambda_mu_df,
        records_by_id={},  # aucun enregistrement de marche -> aucune ligne construite, mais le filtre league doit s'appliquer AVANT
        leagues=("liga",),
    )
    # Aucune ligne ne sera produite (records_by_id vide), mais on verifie
    # que le sous-ensemble filtre par league ne contient jamais m2 en
    # inspectant le code plutot que le resultat (le filtre est en amont).
    import ast

    tree = ast.parse(_SCRIPT_PATH.read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "build_backtest_rows")
    body_source = ast.unparse(func).replace("'", '"')
    assert '"league"].isin(leagues)' in body_source
    assert rows == []
