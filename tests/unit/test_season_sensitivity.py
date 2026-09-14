"""Tests de data_engine.market_odds.season_sensitivity - donnees
SYNTHETIQUES uniquement (jamais de vraie donnee 2026/27, qui n'existe pas
encore dans ce depot). Verifie que la comparaison BASELINE/CURRENT
fonctionne, qu'elle reste independante de toute ponderation
(weighting.py/recent_form.py non importes par ce module, non testes ici)
et qu'elle ne modifie aucun comportement de final_engine (reutilise
run_match_decision INCHANGE)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from sys_foot_quant.backtesting_engine.real_data_walk_forward import RealMatchRecord
from sys_foot_quant.data_engine.market_odds.season_sensitivity import (
    compute_season_sensitivity,
)

_T0 = datetime(2020, 1, 1)
_HOME = 0  # analogue "Brest"
_AWAY = 1  # analogue "PSG"
_OTHERS = (2, 3)
_DECISION_OFFSET_HOURS = 2.0


def _record(match_id: str, kickoff: datetime, home_id: int, away_id: int, home_goals: int, away_goals: int) -> RealMatchRecord:
    return RealMatchRecord(
        match_id=match_id,
        league="ligue1",
        kickoff_utc=kickoff,
        home_team_id=home_id,
        away_team_id=away_id,
        home_goals=home_goals,
        away_goals=away_goals,
        home_xg=float(home_goals) + 0.2,
        away_xg=float(away_goals) + 0.2,
        goals_knowledge_time=kickoff + timedelta(hours=2.0),
        xg_knowledge_time=kickoff + timedelta(hours=48.0),
    )


def _round_robin_history(n_matches: int, start: datetime, id_prefix: str = "b") -> list[RealMatchRecord]:
    """Historique synthetique round-robin entre 4 equipes (0,1,2,3), assez
    volumineux pour satisfaire MIN_TRAIN_MATCHES(10)/MIN_CALIBRATION_MATCHES_FOR_SCALE(30)
    de final_engine (INCHANGES, jamais reimplementes ici)."""
    pairs = [(0, 1), (2, 3), (1, 2), (3, 0), (0, 2), (1, 3)]
    records = []
    for i in range(n_matches):
        home_id, away_id = pairs[i % len(pairs)]
        records.append(
            _record(
                f"{id_prefix}{i}",
                start + timedelta(days=4 * i),
                home_id,
                away_id,
                home_goals=1 + (i % 3),
                away_goals=1 + ((i + 1) % 2),
            )
        )
    return records


def _current_season_extension(n_matches: int, start: datetime, id_prefix: str = "c") -> list[RealMatchRecord]:
    """Quelques matchs "deja joues" d'une saison courante, impliquant
    explicitement _HOME et _AWAY, pour verifier qu'ils influencent bien
    attack/defense (et pas seulement qu'ils sont charges)."""
    pairs = [(_HOME, 2), (_AWAY, 3), (_HOME, _AWAY), (2, _AWAY)]
    records = []
    for i in range(n_matches):
        home_id, away_id = pairs[i % len(pairs)]
        records.append(
            _record(f"{id_prefix}{i}", start + timedelta(days=3 * i), home_id, away_id, home_goals=3, away_goals=0)
        )
    return records


_BASELINE = _round_robin_history(50, _T0, id_prefix="b")
_TARGET_KICKOFF = _T0 + timedelta(days=250)
_EXTENSION = _current_season_extension(6, _T0 + timedelta(days=210), id_prefix="c")
_CURRENT = sorted(_BASELINE + _EXTENSION, key=lambda r: r.kickoff_utc)


def _run_comparison(baseline=None, current=None, market_odds=(1.9, 2.0)):
    return compute_season_sensitivity(
        baseline_records=baseline if baseline is not None else _BASELINE,
        current_records=current if current is not None else _CURRENT,
        match_id="target-brest-psg",
        competition="ligue1",
        season="2026_27",
        home_team_id=_HOME,
        away_team_id=_AWAY,
        kickoff_utc=_TARGET_KICKOFF,
        decision_offset_hours=_DECISION_OFFSET_HOURS,
        market_odds_over_2_5=market_odds[0],
        market_odds_under_2_5=market_odds[1],
    )


def test_current_has_more_training_matches_than_baseline() -> None:
    comparison = _run_comparison()
    assert comparison.current.n_train_matches > comparison.baseline.n_train_matches
    assert comparison.current.n_train_matches == comparison.baseline.n_train_matches + len(_EXTENSION)


def test_both_regimes_produce_a_full_decision_output() -> None:
    comparison = _run_comparison()
    for metrics in (comparison.baseline, comparison.current):
        assert metrics.decision_output.decision.decision in {"BET", "NO_BET"}
        assert metrics.attack_home is not None
        assert metrics.defense_home is not None
        assert metrics.attack_away is not None
        assert metrics.defense_away is not None
        assert metrics.lambda_home is not None
        assert metrics.lambda_away is not None
        assert metrics.total_lambda == pytest.approx(metrics.lambda_home + metrics.lambda_away)
        assert metrics.p_over_2_5 is not None
        assert metrics.fair_odds_over_2_5 is not None


def test_delta_properties_are_populated_when_both_regimes_have_data() -> None:
    comparison = _run_comparison()
    assert comparison.delta_attack_home is not None
    assert comparison.delta_defense_home is not None
    assert comparison.delta_attack_away is not None
    assert comparison.delta_defense_away is not None
    assert comparison.delta_lambda_home is not None
    assert comparison.delta_lambda_away is not None
    assert comparison.delta_total_lambda is not None
    assert comparison.delta_p_over_2_5 is not None
    assert comparison.delta_fair_odds_over_2_5 is not None


def test_extension_matches_measurably_change_attack_and_defense() -> None:
    """L'ajout des matchs de saison courante doit changer QUELQUE CHOSE -
    sinon le pipeline ne les utiliserait pas reellement (regression contre
    un chargement silencieusement ignore)."""
    comparison = _run_comparison()
    changed = (
        comparison.delta_attack_home != 0.0
        or comparison.delta_defense_home != 0.0
        or comparison.delta_attack_away != 0.0
        or comparison.delta_defense_away != 0.0
    )
    assert changed


def test_delta_is_exactly_zero_when_current_equals_baseline() -> None:
    comparison = _run_comparison(current=_BASELINE)
    assert comparison.delta_attack_home == 0.0
    assert comparison.delta_defense_home == 0.0
    assert comparison.delta_attack_away == 0.0
    assert comparison.delta_defense_away == 0.0
    assert comparison.delta_lambda_home == 0.0
    assert comparison.delta_lambda_away == 0.0
    assert comparison.delta_total_lambda == 0.0
    assert comparison.delta_p_over_2_5 == 0.0
    assert comparison.delta_fair_odds_over_2_5 == 0.0


def test_delta_is_none_when_a_regime_has_insufficient_history() -> None:
    tiny_baseline = _BASELINE[:3]  # sous MIN_TRAIN_MATCHES=10
    comparison = _run_comparison(baseline=tiny_baseline)
    assert comparison.baseline.lambda_home is None
    assert comparison.delta_lambda_home is None
    assert comparison.delta_total_lambda is None


def test_market_odds_flow_through_to_the_decision_unaffected_by_season_extension() -> None:
    """Le snapshot de marche (ici de simples cotes) reste independant du
    regime BASELINE/CURRENT - meme cote injectee, seule la probabilite
    modele peut differer."""
    comparison = _run_comparison(market_odds=(1.32, 2.92))
    assert comparison.baseline.decision_output.market is not None
    assert comparison.current.decision_output.market is not None
    assert comparison.baseline.decision_output.market.market_odds == {"Over": 1.32, "Under": 2.92}
    assert comparison.current.decision_output.market.market_odds == {"Over": 1.32, "Under": 2.92}
