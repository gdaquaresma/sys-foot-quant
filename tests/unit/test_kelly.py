from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.risk_engine.kelly import (
    HALF_KELLY,
    QUARTER_KELLY,
    KellyGateLockedError,
    KellyGateThresholds,
    KellyQualityGateResult,
    evaluate_kelly_quality_gate,
    evaluate_kelly_quality_gate_from_value_log,
    kelly_fraction,
    kelly_stake,
)

_T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)

_UNLOCKED = KellyQualityGateResult(unlocked=True, reasons_blocked=())
_LOCKED = KellyQualityGateResult(unlocked=False, reasons_blocked=("raison de test",))


# ---------------------------------------------------------------------------
# kelly_fraction
# ---------------------------------------------------------------------------


def test_kelly_fraction_known_value() -> None:
    # (0.6*2.5 - 1) / (2.5 - 1) = 0.5 / 1.5
    assert kelly_fraction(0.6, 2.5) == pytest.approx(1.0 / 3.0)


def test_kelly_fraction_negative_when_no_edge() -> None:
    # p=0.3 sur une cote a 2.0 (probabilite implicite 0.5) : pas d'edge.
    f = kelly_fraction(0.3, 2.0)
    assert f < 0.0


def test_kelly_fraction_is_one_at_certainty() -> None:
    assert kelly_fraction(1.0, 3.0) == pytest.approx(1.0)


def test_kelly_fraction_rejects_invalid_prob() -> None:
    with pytest.raises(ValueError):
        kelly_fraction(-0.1, 2.0)
    with pytest.raises(ValueError):
        kelly_fraction(1.1, 2.0)


def test_kelly_fraction_rejects_invalid_odds() -> None:
    with pytest.raises(ValueError):
        kelly_fraction(0.5, 1.0)
    with pytest.raises(ValueError):
        kelly_fraction(0.5, 0.5)


@given(
    model_prob=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    odds=st.floats(min_value=1.01, max_value=50.0, allow_nan=False),
)
@settings(max_examples=200)
def test_kelly_fraction_never_exceeds_one(model_prob: float, odds: float) -> None:
    assert kelly_fraction(model_prob, odds) <= 1.0 + 1e-9


# ---------------------------------------------------------------------------
# evaluate_kelly_quality_gate
# ---------------------------------------------------------------------------


def test_gate_unlocked_when_all_three_conditions_pass() -> None:
    result = evaluate_kelly_quality_gate(
        n_clv_observations=500,
        clv_bootstrap_result={"mean_diff": 1.0, "ci_low": 0.5, "ci_high": 1.5, "p_value": 0.001},
        manual_human_approval=True,
        thresholds=KellyGateThresholds(min_observations=200, min_clv_ci_low=0.0),
    )
    assert result.unlocked is True
    assert result.reasons_blocked == ()


def test_gate_blocked_by_insufficient_sample_size() -> None:
    result = evaluate_kelly_quality_gate(
        n_clv_observations=50,
        clv_bootstrap_result={"mean_diff": 1.0, "ci_low": 0.5, "ci_high": 1.5, "p_value": 0.001},
        manual_human_approval=True,
        thresholds=KellyGateThresholds(min_observations=200, min_clv_ci_low=0.0),
    )
    assert result.unlocked is False
    assert any("Echantillon" in r for r in result.reasons_blocked)


def test_gate_blocked_by_non_significant_clv() -> None:
    result = evaluate_kelly_quality_gate(
        n_clv_observations=500,
        clv_bootstrap_result={"mean_diff": -0.2, "ci_low": -0.8, "ci_high": 0.3, "p_value": 0.4},
        manual_human_approval=True,
        thresholds=KellyGateThresholds(min_observations=200, min_clv_ci_low=0.0),
    )
    assert result.unlocked is False
    assert any("significativement positif" in r for r in result.reasons_blocked)


def test_gate_blocked_when_no_bootstrap_result_provided() -> None:
    result = evaluate_kelly_quality_gate(
        n_clv_observations=500,
        clv_bootstrap_result=None,
        manual_human_approval=True,
        thresholds=KellyGateThresholds(min_observations=200, min_clv_ci_low=0.0),
    )
    assert result.unlocked is False
    assert any("Aucun test de significativite" in r for r in result.reasons_blocked)


def test_gate_blocked_by_missing_human_approval() -> None:
    result = evaluate_kelly_quality_gate(
        n_clv_observations=500,
        clv_bootstrap_result={"mean_diff": 1.0, "ci_low": 0.5, "ci_high": 1.5, "p_value": 0.001},
        manual_human_approval=False,
        thresholds=KellyGateThresholds(min_observations=200, min_clv_ci_low=0.0),
    )
    assert result.unlocked is False
    assert any("Approbation humaine" in r for r in result.reasons_blocked)


def test_gate_reports_all_failing_reasons_simultaneously() -> None:
    result = evaluate_kelly_quality_gate(
        n_clv_observations=1,
        clv_bootstrap_result=None,
        manual_human_approval=False,
        thresholds=KellyGateThresholds(min_observations=200, min_clv_ci_low=0.0),
    )
    assert result.unlocked is False
    assert len(result.reasons_blocked) == 3


# ---------------------------------------------------------------------------
# evaluate_kelly_quality_gate_from_value_log (anti-look-ahead)
# ---------------------------------------------------------------------------


def _make_value_log() -> pd.DataFrame:
    # 250 observations "passees" (avant le cutoff) avec un CLV exactement
    # nul -> IC bootstrap = [0, 0], jamais strictement > 0 : le gate doit
    # rester verrouille en ne voyant que ces lignes.
    past_rows = pd.DataFrame(
        {
            "decision_time": [_T0 + timedelta(hours=i) for i in range(250)],
            "clv_pct": [0.0] * 250,
        }
    )
    # 250 observations "futures" (apres le cutoff) fortement positives : si
    # elles fuitaient dans le calcul, elles feraient basculer l'IC bas
    # au-dessus de 0 et debloqueraient le gate a tort.
    future_rows = pd.DataFrame(
        {
            "decision_time": [_T0 + timedelta(days=365, hours=i) for i in range(250)],
            "clv_pct": [5.0] * 250,
        }
    )
    return pd.concat([past_rows, future_rows], ignore_index=True)


def test_gate_from_value_log_ignores_future_rows() -> None:
    value_log = _make_value_log()

    gate_at_cutoff = evaluate_kelly_quality_gate_from_value_log(
        value_log,
        as_of=_T0 + timedelta(hours=250),
        manual_human_approval=True,
        thresholds=KellyGateThresholds(min_observations=200, min_clv_ci_low=0.0),
    )
    assert gate_at_cutoff.unlocked is False
    assert any("significativement positif" in r for r in gate_at_cutoff.reasons_blocked)


def test_gate_from_value_log_would_unlock_only_with_full_future_data() -> None:
    # Verifie, a titre de contraste, que le meme jeu de donnees COMPLET
    # (cutoff apres les lignes futures) est bien celui qui debloquerait le
    # gate - ce qui confirme que le test precedent isole correctement
    # l'effet du filtrage point-in-time, et n'est pas bloque pour une
    # autre raison (ex: donnees mal construites).
    value_log = _make_value_log()

    gate_full = evaluate_kelly_quality_gate_from_value_log(
        value_log,
        as_of=_T0 + timedelta(days=366),
        manual_human_approval=True,
        thresholds=KellyGateThresholds(min_observations=200, min_clv_ci_low=0.0),
    )
    assert gate_full.unlocked is True


def test_gate_from_value_log_insufficient_observations_before_min_size() -> None:
    value_log = _make_value_log()
    gate = evaluate_kelly_quality_gate_from_value_log(
        value_log,
        as_of=_T0 + timedelta(hours=1),
        manual_human_approval=True,
        thresholds=KellyGateThresholds(min_observations=200, min_clv_ci_low=0.0),
    )
    assert gate.unlocked is False
    assert any("Echantillon" in r for r in gate.reasons_blocked)


# ---------------------------------------------------------------------------
# kelly_stake
# ---------------------------------------------------------------------------


def test_kelly_stake_raises_when_gate_locked() -> None:
    with pytest.raises(KellyGateLockedError):
        kelly_stake(1000.0, model_prob=0.6, odds=2.5, kelly_multiplier=QUARTER_KELLY, gate_result=_LOCKED)


def test_kelly_stake_computes_correctly_when_unlocked() -> None:
    # f* = 1/3, multiplicateur Quarter-Kelly = 0.25 -> mise = 1000 * (1/3) * 0.25
    stake = kelly_stake(1000.0, model_prob=0.6, odds=2.5, kelly_multiplier=QUARTER_KELLY, gate_result=_UNLOCKED)
    assert stake == pytest.approx(1000.0 * (1.0 / 3.0) * 0.25)


def test_kelly_stake_clips_negative_fraction_to_zero() -> None:
    # Pas d'edge -> f* negatif -> mise nulle, jamais negative.
    stake = kelly_stake(1000.0, model_prob=0.3, odds=2.0, kelly_multiplier=HALF_KELLY, gate_result=_UNLOCKED)
    assert stake == 0.0


def test_kelly_stake_rejects_full_kelly_even_when_unlocked() -> None:
    with pytest.raises(ValueError):
        kelly_stake(1000.0, model_prob=0.6, odds=2.5, kelly_multiplier=1.0, gate_result=_UNLOCKED)


def test_kelly_stake_rejects_zero_or_negative_multiplier() -> None:
    with pytest.raises(ValueError):
        kelly_stake(1000.0, model_prob=0.6, odds=2.5, kelly_multiplier=0.0, gate_result=_UNLOCKED)
    with pytest.raises(ValueError):
        kelly_stake(1000.0, model_prob=0.6, odds=2.5, kelly_multiplier=-0.1, gate_result=_UNLOCKED)


def test_kelly_stake_rejects_non_positive_bankroll() -> None:
    with pytest.raises(ValueError):
        kelly_stake(0.0, model_prob=0.6, odds=2.5, kelly_multiplier=QUARTER_KELLY, gate_result=_UNLOCKED)


@given(
    bankroll=st.floats(min_value=1.0, max_value=1_000_000.0, allow_nan=False),
    model_prob=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    odds=st.floats(min_value=1.01, max_value=50.0, allow_nan=False),
    kelly_multiplier=st.floats(min_value=1e-6, max_value=HALF_KELLY, allow_nan=False),
)
@settings(max_examples=150)
def test_kelly_stake_never_exceeds_bankroll_when_unlocked(
    bankroll: float, model_prob: float, odds: float, kelly_multiplier: float
) -> None:
    stake = kelly_stake(bankroll, model_prob, odds, kelly_multiplier, gate_result=_UNLOCKED)
    assert 0.0 <= stake <= bankroll + 1e-6
