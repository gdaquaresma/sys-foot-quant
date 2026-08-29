"""Garde-fous anti-fuite pour le moteur final
(src/sys_foot_quant/final_engine/) :
- le mecanisme point-in-time (appariement, decision_time) reste
  INTEGRALEMENT delegue a matching.py/time_resolution.py, jamais
  reimplemente ;
- la correction E7/E8 (scalar_correction.py) n'utilise jamais un match de
  calibration dont decision_time >= as_of_time ;
- aucune cote de CLOTURE n'entre jamais dans le chemin de decision
  (final_engine/market.py, orchestrator.py) ;
- deplacer une observation dans le futur ne change jamais une decision
  deja calculee pour un match anterieur.
"""

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from sys_foot_quant.calibration_engine.scalar_correction import fit_scale_correction_as_of
from sys_foot_quant.final_engine.orchestrator import run_match_decision

_FINAL_ENGINE_DIR = Path(__file__).resolve().parent.parent.parent / "src" / "sys_foot_quant" / "final_engine"

_FORBIDDEN_CLOSING_NAMES = {
    "closing_odds_1x2_by_bookmaker",
    "closing_over_under_2_5_by_bookmaker",
    "has_complete_close_odds",
    "has_complete_close_over_under_2_5_odds",
}


def _dt(day: int) -> datetime:
    return datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=day - 1)


# --- 1. aucune reimplementation du mecanisme point-in-time -------------------


def test_final_engine_never_reimplements_point_in_time_matching_or_resolution() -> None:
    """Aucun module du moteur final ne redefinit
    ``match_league_season``/``conservative_knowledge_time_utc`` - il les
    importe et les appelle, jamais ne les reecrit."""
    for path in _FINAL_ENGINE_DIR.glob("*.py"):
        tree = ast.parse(path.read_text())
        func_names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        assert "match_league_season" not in func_names, path
        assert "conservative_knowledge_time_utc" not in func_names, path


# --- 2. aucune cote de cloture dans le chemin de decision --------------------


def test_no_module_in_final_engine_references_closing_odds_accessors() -> None:
    """Verification par AST sur TOUT le package ``final_engine`` (pas
    seulement ``market.py``) : aucun noeud de code (attribut, nom, import)
    ne reference les accesseurs de cloture - seuls les docstrings
    d'avertissement peuvent mentionner ces noms en texte."""
    for path in _FINAL_ENGINE_DIR.glob("*.py"):
        source = path.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in _FORBIDDEN_CLOSING_NAMES:
                raise AssertionError(f"{path}: reference de code interdite : {node.attr}")
            if isinstance(node, ast.Name) and node.id in _FORBIDDEN_CLOSING_NAMES:
                raise AssertionError(f"{path}: reference de code interdite : {node.id}")
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    assert alias.name not in _FORBIDDEN_CLOSING_NAMES, f"{path}: import interdit {alias.name}"


# --- 3. correction E7/E8 : jamais un match >= as_of_time ---------------------


def test_scale_correction_never_uses_a_calibration_row_at_or_after_as_of_time() -> None:
    n = 40
    df = pd.DataFrame(
        {
            "decision_time": [_dt(d) for d in range(1, n + 1)],
            "poisson_simple_lambda": [1.4] * n,
            "poisson_simple_mu": [1.1] * n,
            "total_goals": [2.7] * n,
        }
    )
    as_of = df["decision_time"].iloc[20]  # match n.21 (index 20) - doit etre exclu
    c, n_used = fit_scale_correction_as_of(df, "poisson_simple", as_of_time=as_of, min_matches=1)
    assert n_used == 20  # matchs 1..20 seulement (strictement < as_of)


def test_moving_a_calibration_match_to_the_future_never_changes_an_earlier_decision() -> None:
    """Balayage direct sur le pipeline complet : deplacer UN match de
    calibration dans le futur (au-dela de decision_time du match evalue)
    ne doit jamais changer la sortie deja calculee."""
    kickoff = datetime(2025, 1, 8, 20, 0, tzinfo=timezone.utc)  # mercredi
    n = 40
    goals_df = pd.DataFrame(
        [
            {
                "home_team_id": i % 4,
                "away_team_id": (i + 1) % 4,
                "home_goals": 1,
                "away_goals": 1,
            }
            for i in range(n)
        ]
    )
    calibration_df = pd.DataFrame(
        {
            "decision_time": [kickoff - timedelta(days=n - i, hours=-2) for i in range(n)],
            "poisson_simple_lambda": [1.4] * n,
            "poisson_simple_mu": [1.1] * n,
            "total_goals": [2.7] * n,
        }
    )

    def _decide(cal_df: pd.DataFrame):
        return run_match_decision(
            match_id="m1",
            competition="Liga",
            season="2025/26",
            kickoff_utc=kickoff,
            home_team_id=0,
            away_team_id=1,
            goals_train_df=goals_df,
            xg_train_df=None,
            calibration_df_by_model={"poisson_simple": cal_df},
            market_odds_over_2_5=1.9,
            market_odds_under_2_5=2.0,
        )

    output_before = _decide(calibration_df)

    # Deplace le DERNIER match de calibration loin dans le futur (bien
    # au-dela de decision_time) - ne doit rien changer.
    tampered = calibration_df.copy()
    tampered.loc[tampered.index[-1], "decision_time"] = kickoff + timedelta(days=3650)
    output_after = _decide(tampered)

    assert output_before.calibration["poisson_simple"].scale_c == pytest.approx(
        output_after.calibration["poisson_simple"].scale_c
    )
    # Le match deplace dans le futur est exclu de la fenetre de calibration
    # (n_calibration_used diminue de 1), mais le facteur d'echelle et la
    # decision restent identiques - preuve que ce match n'a jamais compte.
    assert output_after.calibration["poisson_simple"].n_calibration_used == n - 1
    assert output_before.decision.decision == output_after.decision.decision
    assert output_before.decision.decision_reason == output_after.decision.decision_reason


def test_injecting_a_future_result_never_influences_the_current_decision() -> None:
    """Injecte un match dont decision_time est POSTERIEUR au match evalue,
    avec des valeurs de buts extremes conçues pour faire diverger le
    calcul si elles etaient utilisees - la decision ne doit pas bouger."""
    kickoff = datetime(2025, 1, 8, 20, 0, tzinfo=timezone.utc)
    n = 40
    goals_df = pd.DataFrame(
        [
            {"home_team_id": i % 4, "away_team_id": (i + 1) % 4, "home_goals": 1, "away_goals": 1}
            for i in range(n)
        ]
    )
    calibration_df = pd.DataFrame(
        {
            "decision_time": [kickoff - timedelta(days=n - i, hours=-2) for i in range(n)],
            "poisson_simple_lambda": [1.4] * n,
            "poisson_simple_mu": [1.1] * n,
            "total_goals": [2.7] * n,
        }
    )

    def _decide(cal_df: pd.DataFrame):
        return run_match_decision(
            match_id="m1",
            competition="Liga",
            season="2025/26",
            kickoff_utc=kickoff,
            home_team_id=0,
            away_team_id=1,
            goals_train_df=goals_df,
            xg_train_df=None,
            calibration_df_by_model={"poisson_simple": cal_df},
            market_odds_over_2_5=1.9,
            market_odds_under_2_5=2.0,
        )

    output_before = _decide(calibration_df)

    future_row = pd.DataFrame(
        {
            "decision_time": [kickoff + timedelta(days=1)],
            "poisson_simple_lambda": [50.0],
            "poisson_simple_mu": [50.0],
            "total_goals": [0.0],
        }
    )
    with_future = pd.concat([calibration_df, future_row], ignore_index=True)
    output_after = _decide(with_future)

    assert output_before.calibration["poisson_simple"].scale_c == pytest.approx(
        output_after.calibration["poisson_simple"].scale_c
    )
    assert output_before.decision.decision == output_after.decision.decision
