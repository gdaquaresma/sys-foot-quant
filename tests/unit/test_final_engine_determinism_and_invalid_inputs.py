from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from sys_foot_quant.final_engine import reason_codes
from sys_foot_quant.final_engine.orchestrator import run_match_decision


_KICKOFF = datetime(2025, 1, 8, 20, 0, tzinfo=timezone.utc)  # mercredi


def _goals_df(n: int) -> pd.DataFrame:
    return pd.DataFrame(
        [{"home_team_id": i % 4, "away_team_id": (i + 1) % 4, "home_goals": 1, "away_goals": 1} for i in range(n)]
    )


def _calibration_df(n: int, kickoff: datetime) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "decision_time": [kickoff - timedelta(days=n - i, hours=-2) for i in range(n)],
            "poisson_simple_lambda": [1.4] * n,
            "poisson_simple_mu": [1.1] * n,
            "total_goals": [2.7] * n,
        }
    )


def _run(**overrides):
    kwargs = dict(
        match_id="m1",
        competition="Liga",
        season="2025/26",
        kickoff_utc=_KICKOFF,
        home_team_id=0,
        away_team_id=1,
        goals_train_df=_goals_df(40),
        xg_train_df=None,
        calibration_df_by_model={"poisson_simple": _calibration_df(40, _KICKOFF)},
        market_odds_over_2_5=1.9,
        market_odds_under_2_5=2.0,
    )
    kwargs.update(overrides)
    return run_match_decision(**kwargs)


# --- Determinism --------------------------------------------------------------


def test_same_inputs_produce_the_same_output_object() -> None:
    output_1 = _run()
    output_2 = _run()
    assert output_1.decision == output_2.decision
    assert output_1.calibration["poisson_simple"].probabilities == output_2.calibration["poisson_simple"].probabilities
    assert output_1.qualification.calibration_status == output_2.qualification.calibration_status
    assert output_1.qualification.discrimination_status == output_2.qualification.discrimination_status
    assert [g.failure_code for g in output_1.qualification.scientific_gates] == [
        g.failure_code for g in output_2.qualification.scientific_gates
    ]


# --- Invalid inputs -------------------------------------------------------------


def test_missing_market_odds_never_raises_and_yields_no_bet() -> None:
    output = _run(market_odds_over_2_5=None, market_odds_under_2_5=None)
    assert output.market is None
    assert output.decision.decision == "NO_BET"


def test_zero_row_goals_train_df_never_raises() -> None:
    empty = pd.DataFrame(columns=["home_team_id", "away_team_id", "home_goals", "away_goals"])
    output = _run(goals_train_df=empty)
    assert output.models["poisson_simple"] is None
    assert output.decision.decision == "NO_BET"


def test_missing_calibration_dataframe_for_primary_model_never_raises() -> None:
    output = _run(calibration_df_by_model={})
    assert output.calibration["poisson_simple"].probabilities is None
    assert output.decision.decision == "NO_BET"


def test_invalid_market_odds_below_one_never_raises_and_yields_no_bet() -> None:
    output = _run(market_odds_over_2_5=0.5, market_odds_under_2_5=2.0)
    assert output.decision.decision == "NO_BET"


def test_nan_market_odds_never_raises_and_yields_no_bet() -> None:
    """Audit pre-production : ``float('nan') <= 1.0`` vaut ``False`` en
    Python, donc ``validate_odds`` laissait passer une cote NaN, qui se
    propageait ensuite jusqu'a une ValueError non capturee plus loin dans
    le pipeline (``market_fair_prob doit etre dans [0, 1]``) au lieu de
    produire un NO_BET motive."""
    output = _run(market_odds_over_2_5=math.nan, market_odds_under_2_5=2.0)
    assert output.market is None
    assert output.decision.decision == "NO_BET"
    assert reason_codes.MARKET_DATA_UNAVAILABLE in output.decision.decision_reason


def test_infinite_market_odds_never_raises_and_yields_no_bet() -> None:
    """Meme defaut structurel que le NaN : ``float('inf') <= 1.0`` vaut
    ``False``, donc une cote infinie contournait aussi ``validate_odds``."""
    output = _run(market_odds_over_2_5=math.inf, market_odds_under_2_5=2.0)
    assert output.market is None
    assert output.decision.decision == "NO_BET"
    assert reason_codes.MARKET_DATA_UNAVAILABLE in output.decision.decision_reason


def test_corrupted_total_goals_in_calibration_history_never_raises_and_yields_no_bet() -> None:
    """Audit pre-production : ``fit_scale_correction_as_of`` (E7/E8, portage
    verbatim, jamais modifie) ne filtre les NaN que sur les colonnes
    ``{model}_lambda``/``{model}_mu``, jamais sur ``total_goals`` - une
    corruption de cette colonne (merge fautif, ligne malformee en amont)
    produit un ``scale_c`` NaN qui se propage jusqu'a une ValueError non
    capturee (``model_prob doit etre dans [0, 1]``). Le filtrage
    supplementaire vit dans ``final_engine.calibration`` (couche
    production), jamais dans le module scientifique fige."""
    n = 40
    corrupted_calibration_df = _calibration_df(n, _KICKOFF)
    corrupted_calibration_df["total_goals"] = float("nan")
    output = _run(calibration_df_by_model={"poisson_simple": corrupted_calibration_df})
    assert output.calibration["poisson_simple"].probabilities is None
    assert output.decision.decision == "NO_BET"
    assert reason_codes.INSUFFICIENT_HISTORY in output.decision.decision_reason


def test_ambiguous_kickoff_day_never_raises_and_yields_no_bet() -> None:
    monday_kickoff = datetime(2025, 1, 6, 20, 0, tzinfo=timezone.utc)
    output = _run(kickoff_utc=monday_kickoff, goals_train_df=_goals_df(40), calibration_df_by_model={"poisson_simple": _calibration_df(40, monday_kickoff)})
    assert output.decision.decision == "NO_BET"
