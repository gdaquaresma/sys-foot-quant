from __future__ import annotations

from sys_foot_quant.final_engine.decision import decide
from sys_foot_quant.final_engine.types import GateResult


def _gate(name: str, triggered: bool, failure_code: str | None = None) -> GateResult:
    return GateResult(
        name=name, triggered=triggered, reason="r", metric="m", observed_value=None, threshold=None, failure_code=failure_code
    )


def test_no_gate_triggered_yields_bet_with_empty_reason() -> None:
    result = decide([_gate("a", False)], [_gate("b", False)])
    assert result.decision == "BET"
    assert result.decision_reason == []


def test_single_triggered_scientific_gate_yields_no_bet_with_its_code() -> None:
    result = decide([_gate("a", True, "CODE_A")], [])
    assert result.decision == "NO_BET"
    assert result.decision_reason == ["CODE_A"]


def test_multiple_triggered_gates_yield_sorted_unique_codes() -> None:
    result = decide(
        [_gate("a", True, "CODE_B"), _gate("b", True, "CODE_A")],
        [_gate("c", True, "CODE_A")],  # doublon volontaire
    )
    assert result.decision == "NO_BET"
    assert result.decision_reason == ["CODE_A", "CODE_B"]


def test_triggered_gate_without_failure_code_never_crashes_and_is_ignored_in_codes() -> None:
    result = decide([_gate("a", True, None)], [])
    assert result.decision == "NO_BET"
    assert result.decision_reason == []


def test_never_modifies_gate_inputs() -> None:
    gates = [_gate("a", True, "CODE_A")]
    before = list(gates)
    decide(gates, [])
    assert gates == before
