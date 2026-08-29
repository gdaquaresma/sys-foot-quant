from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from sys_foot_quant.final_engine import reason_codes
from sys_foot_quant.final_engine.gates import OperationalThresholds
from sys_foot_quant.final_engine.orchestrator import MARKET_COMPARISON_THRESHOLD, run_match_decision
from sys_foot_quant.final_engine.prediction import PRIMARY_MODEL

_KICKOFF_WEDNESDAY = datetime(2025, 1, 8, 20, 0, tzinfo=timezone.utc)  # mercredi -> jamais ambigu
_KICKOFF_MONDAY = datetime(2025, 1, 6, 20, 0, tzinfo=timezone.utc)  # lundi -> toujours ambigu


def _goals_train_df(n: int, kickoff: datetime) -> pd.DataFrame:
    rows = []
    for i in range(n):
        rows.append(
            {
                "home_team_id": i % 4,
                "away_team_id": (i + 1) % 4,
                "home_goals": 1,
                "away_goals": 1,
                "kickoff_time": kickoff - timedelta(days=n - i),
            }
        )
    return pd.DataFrame(rows)


def _calibration_df(n: int, kickoff: datetime, model: str = "poisson_simple") -> pd.DataFrame:
    decision_times = [kickoff - timedelta(days=n - i, hours=-2) for i in range(n)]
    return pd.DataFrame(
        {
            "decision_time": decision_times,
            f"{model}_lambda": [1.4] * n,
            f"{model}_mu": [1.1] * n,
            "total_goals": [2.5] * n,
        }
    )


def _run(
    kickoff: datetime,
    competition: str = "Liga",
    n_goals_train: int = 40,
    n_calibration: int = 40,
    market_odds_over_2_5: float | None = 1.9,
    market_odds_under_2_5: float | None = 2.0,
    operational_thresholds: OperationalThresholds | None = None,
):
    return run_match_decision(
        match_id="m1",
        competition=competition,
        season="2025/26",
        kickoff_utc=kickoff,
        home_team_id=0,
        away_team_id=1,
        goals_train_df=_goals_train_df(n_goals_train, kickoff),
        xg_train_df=None,
        calibration_df_by_model={"poisson_simple": _calibration_df(n_calibration, kickoff)},
        market_odds_over_2_5=market_odds_over_2_5,
        market_odds_under_2_5=market_odds_under_2_5,
        operational_thresholds=operational_thresholds,
    )


def test_full_pipeline_produces_a_complete_output_object() -> None:
    output = _run(_KICKOFF_WEDNESDAY)
    assert output.primary_model == PRIMARY_MODEL
    assert output.models["poisson_simple"] is not None
    assert output.calibration["poisson_simple"].probabilities is not None
    assert output.pricing["poisson_simple"] is not None
    assert output.market is not None
    assert output.qualification.calibration_status
    assert output.qualification.discrimination_status == "DEMONTREE"  # Liga
    assert output.decision.decision in {"BET", "NO_BET"}


def test_mvp_default_configuration_always_produces_no_bet_with_edge_code() -> None:
    """docs/research_synthesis_e1_e16.md section 13 : le MVP ne produit
    jamais BET par une regle validee (min_edge_threshold non fixe)."""
    output = _run(_KICKOFF_WEDNESDAY)
    assert output.decision.decision == "NO_BET"
    assert reason_codes.EDGE_BELOW_THRESHOLD in output.decision.decision_reason


def test_insufficient_history_yields_no_bet() -> None:
    output = _run(_KICKOFF_WEDNESDAY, n_goals_train=3)
    assert output.decision.decision == "NO_BET"
    assert reason_codes.INSUFFICIENT_HISTORY in output.decision.decision_reason


def test_insufficient_calibration_history_yields_no_bet() -> None:
    output = _run(_KICKOFF_WEDNESDAY, n_calibration=5)
    assert output.decision.decision == "NO_BET"
    assert reason_codes.INSUFFICIENT_HISTORY in output.decision.decision_reason
    assert output.calibration["poisson_simple"].probabilities is None


def test_ambiguous_day_yields_no_bet() -> None:
    output = _run(_KICKOFF_MONDAY)
    assert output.decision.decision == "NO_BET"
    assert reason_codes.AMBIGUOUS_COLLECTION_DAY in output.decision.decision_reason


def test_missing_market_odds_yields_no_bet_and_no_market_comparison() -> None:
    output = _run(_KICKOFF_WEDNESDAY, market_odds_over_2_5=None, market_odds_under_2_5=None)
    assert output.market is None
    assert output.decision.decision == "NO_BET"
    assert reason_codes.MARKET_DATA_UNAVAILABLE in output.decision.decision_reason


def test_premier_league_yields_no_bet_with_discrimination_code_but_probabilities_still_produced() -> None:
    """E15 : l'absence de discrimination demontree n'empeche jamais la
    projection elle-meme d'etre produite (docs/final_engine_specification.md
    section 9) - seule la decision est bloquee."""
    output = _run(_KICKOFF_WEDNESDAY, competition="Premier League")
    assert output.calibration["poisson_simple"].probabilities is not None
    assert output.qualification.discrimination_status == "NON_DEMONTREE"
    assert output.decision.decision == "NO_BET"
    assert reason_codes.DISCRIMINATION_NOT_DEMONSTRATED in output.decision.decision_reason


def test_e14_is_never_applied_probability_in_biased_zone_stays_unmodified() -> None:
    """E14 est NON VALIDEE - la probabilite Over 2.5 dans la zone
    [0.6,0.7) ne doit JAMAIS etre corrigee, uniquement flaguee. Construit
    deliberement un cas ou lambda+mu corrige = 3.3 (P(Over2.5) ~= 0.6406,
    verifie hors-ligne), pour exercer reellement la zone plutot que de
    dependre du hasard."""
    kickoff = _KICKOFF_WEDNESDAY
    # Historique 1-1 uniforme -> raw (lambda, mu) = (1.0, 1.0) pour
    # n'importe quelle paire d'equipes (verifie separement).
    goals_df = _goals_train_df(40, kickoff)
    n_cal = 40
    calibration_df = pd.DataFrame(
        {
            "decision_time": [kickoff - timedelta(days=n_cal - i, hours=-2) for i in range(n_cal)],
            "poisson_simple_lambda": [1.0] * n_cal,
            "poisson_simple_mu": [1.0] * n_cal,
            # mean(total_goals)/mean(lambda+mu) = 3.3/2.0 = 1.65 -> corrige
            # (lambda, mu) = (1.65, 1.65), P(Over2.5) ~= 0.6406 (zone biaisee).
            "total_goals": [3.3] * n_cal,
        }
    )
    output = run_match_decision(
        match_id="m2",
        competition="Liga",
        season="2025/26",
        kickoff_utc=kickoff,
        home_team_id=0,
        away_team_id=1,
        goals_train_df=goals_df,
        xg_train_df=None,
        calibration_df_by_model={"poisson_simple": calibration_df},
        market_odds_over_2_5=1.9,
        market_odds_under_2_5=2.0,
    )
    p_over_2_5 = output.calibration["poisson_simple"].probabilities[MARKET_COMPARISON_THRESHOLD]
    status = output.qualification.calibration_status[MARKET_COMPARISON_THRESHOLD]

    assert 0.6 <= p_over_2_5 < 0.7, f"le cas construit devait tomber dans la zone biaisee, obtenu {p_over_2_5}"
    assert status == "ZONE_BIAISEE_NON_CORRIGEE"
    assert reason_codes.INSUFFICIENT_CONFIDENCE_CALIBRATION_ZONE in output.decision.decision_reason
    # La probabilite elle-meme reste une probabilite valide non corrigee -
    # aucune isotonic/logistic recalibration (E14) ne l'a modifiee.
    assert p_over_2_5 == pytest.approx(0.6405735336528743, abs=1e-6)


def test_control_models_are_computed_but_never_drive_the_decision() -> None:
    """dixon_coles/xg_model restent des modeles de CONTROLE - aucun
    ensemble, aucune ponderation, jamais utilises pour la decision
    (docs/final_engine_specification.md section 5)."""
    output = _run(_KICKOFF_WEDNESDAY)
    assert output.models["dixon_coles"] is not None
    # dixon_coles n'a pas de calibration_df dedie fourni ici -> non calibre,
    # mais sa PREDICTION brute existe bien, prouvant qu'il est calcule
    # independamment sans jamais influencer market/qualification/decision
    # (qui ne referencent que `calibrated[PRIMARY_MODEL]`).
    assert output.calibration["dixon_coles"].probabilities is None
    assert output.market.market_odds == {"Over": 1.9, "Under": 2.0}
