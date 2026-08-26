from __future__ import annotations

from datetime import datetime, timezone

import pytest

from research.xg_feasibility.sampling import select_fixed_sample
from research.xg_feasibility.understat_source import MatchXGRecord

_T0 = datetime(2024, 8, 1, tzinfo=timezone.utc)


def _records(n: int) -> list[MatchXGRecord]:
    return [
        MatchXGRecord(
            match_id=str(i),
            league="EPL",
            season="2024",
            kickoff_utc=_T0,
            home_team=f"Home{i}",
            away_team=f"Away{i}",
            home_goals=1,
            away_goals=1,
            home_xg=1.0,
            away_xg=1.0,
        )
        for i in range(n)
    ]


def test_rejects_non_positive_n() -> None:
    with pytest.raises(ValueError):
        select_fixed_sample(_records(5), n=0, seed=1)


def test_returns_all_records_when_n_exceeds_population() -> None:
    records = _records(5)
    sample = select_fixed_sample(records, n=10, seed=1)
    assert len(sample) == 5


def test_deterministic_for_same_seed_and_population() -> None:
    records = _records(50)
    sample_a = select_fixed_sample(records, n=10, seed=42)
    sample_b = select_fixed_sample(records, n=10, seed=42)
    assert [r.match_id for r in sample_a] == [r.match_id for r in sample_b]


def test_independent_of_input_order() -> None:
    records = _records(50)
    shuffled = list(reversed(records))
    sample_ordered = select_fixed_sample(records, n=10, seed=42)
    sample_shuffled = select_fixed_sample(shuffled, n=10, seed=42)
    assert [r.match_id for r in sample_ordered] == [r.match_id for r in sample_shuffled]


def test_different_seeds_can_give_different_samples() -> None:
    records = _records(50)
    sample_a = select_fixed_sample(records, n=10, seed=1)
    sample_b = select_fixed_sample(records, n=10, seed=2)
    assert [r.match_id for r in sample_a] != [r.match_id for r in sample_b]


def test_sample_result_sorted_by_match_id() -> None:
    records = _records(50)
    sample = select_fixed_sample(records, n=10, seed=7)
    ids = [r.match_id for r in sample]
    assert ids == sorted(ids, key=lambda x: x)
