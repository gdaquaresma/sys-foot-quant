from __future__ import annotations

from datetime import timedelta

import pytest

from sys_foot_quant.backtesting_engine.engine import (
    ChronologicalBacktestEngine,
    DecisionSnapshot,
)
from sys_foot_quant.data_engine.storage.repository import DuckDBRepository


def _diagnostic_stub(snapshot: DecisionSnapshot) -> dict[str, int]:
    return {entity: len(df) for entity, df in snapshot.visible.items()}


def test_engine_runs_over_all_decision_points_in_order(repo: DuckDBRepository) -> None:
    matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
    decision_times = [kt - timedelta(hours=1) for kt in matches["kickoff_time"]]

    engine = ChronologicalBacktestEngine(
        repository=repo, entities=("matches", "match_results", "odds_snapshots")
    )
    trace = engine.run(decision_times, on_decision=_diagnostic_stub)

    assert len(trace) == len(decision_times)
    # Le nombre de resultats visibles ne peut jamais decroitre au fil du
    # temps (des resultats deviennent visibles, ils ne disparaissent pas).
    result_counts = [step["match_results"] for step in trace]
    assert result_counts == sorted(result_counts)


def test_engine_rejects_unsorted_decision_times(repo: DuckDBRepository) -> None:
    matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
    decision_times = list(matches["kickoff_time"])
    decision_times[0], decision_times[-1] = decision_times[-1], decision_times[0]

    engine = ChronologicalBacktestEngine(repository=repo, entities=("matches",))
    with pytest.raises(ValueError, match="chronologique"):
        engine.run(decision_times, on_decision=_diagnostic_stub)


def test_at_each_decision_no_result_exists_yet_for_the_upcoming_match(
    repo: DuckDBRepository,
) -> None:
    """Le test central de l'etape 1.

    Pour chaque match, au moment de la decision (T-1h avant son propre
    coup d'envoi), le resultat DE CE MATCH ne doit jamais etre visible -
    par construction (knowledge_time du resultat > kickoff_time > T-1h),
    verifie ici bout en bout a travers le moteur de backtest complet.
    """
    matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
    decision_times = [kt - timedelta(hours=1) for kt in matches["kickoff_time"]]
    match_ids = list(matches["match_id"])

    engine = ChronologicalBacktestEngine(repository=repo, entities=("match_results",))

    captured: list[tuple[int, set[int]]] = []

    def capture(snapshot: DecisionSnapshot) -> None:
        visible_ids = set(snapshot.visible["match_results"]["match_id"])
        captured.append(visible_ids)

    engine.run(decision_times, on_decision=capture)

    for match_id, visible_ids in zip(match_ids, captured):
        assert match_id not in visible_ids
