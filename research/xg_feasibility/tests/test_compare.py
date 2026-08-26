from __future__ import annotations

from datetime import datetime, timezone

import pytest

from research.xg_feasibility.compare import compare_extractions
from research.xg_feasibility.storage import ExtractionFile
from research.xg_feasibility.understat_source import MatchXGRecord

_T0 = datetime(2024, 8, 1, tzinfo=timezone.utc)
_FIRST_COLLECTED = datetime(2026, 8, 1, tzinfo=timezone.utc)
_SECOND_COLLECTED = datetime(2026, 9, 15, tzinfo=timezone.utc)


def _record(match_id: str, home_xg: float, away_xg: float) -> MatchXGRecord:
    return MatchXGRecord(
        match_id=match_id,
        league="EPL",
        season="2024",
        kickoff_utc=_T0,
        home_team="A",
        away_team="B",
        home_goals=1,
        away_goals=1,
        home_xg=home_xg,
        away_xg=away_xg,
    )


def test_identical_extractions_show_zero_change() -> None:
    records = [_record("1", 1.5, 0.9), _record("2", 0.4, 2.1)]
    first = ExtractionFile(_FIRST_COLLECTED, "EPL", "2024", records)
    second = ExtractionFile(_SECOND_COLLECTED, "EPL", "2024", records)

    report = compare_extractions(first, second)

    assert report.home_xg.n_common == 2
    assert report.home_xg.n_changed == 0
    assert report.home_xg.proportion_changed == 0.0
    assert report.home_xg.mean_abs_diff == 0.0
    assert report.away_xg.n_changed == 0


def test_detects_revised_values_above_epsilon() -> None:
    first = ExtractionFile(
        _FIRST_COLLECTED, "EPL", "2024", [_record("1", 1.50, 1.00), _record("2", 0.50, 0.50)]
    )
    second = ExtractionFile(
        _SECOND_COLLECTED, "EPL", "2024", [_record("1", 1.70, 1.00), _record("2", 0.50, 0.50)]
    )

    report = compare_extractions(first, second, epsilon=0.005)

    assert report.home_xg.n_common == 2
    assert report.home_xg.n_changed == 1
    assert report.home_xg.proportion_changed == 0.5
    assert report.home_xg.mean_abs_diff == pytest.approx((0.20 + 0.0) / 2)
    assert report.home_xg.max_abs_diff == pytest.approx(0.20)
    assert report.away_xg.n_changed == 0


def test_tiny_rounding_noise_below_epsilon_not_counted_as_changed() -> None:
    first = ExtractionFile(_FIRST_COLLECTED, "EPL", "2024", [_record("1", 1.500, 1.000)])
    second = ExtractionFile(_SECOND_COLLECTED, "EPL", "2024", [_record("1", 1.501, 1.000)])

    report = compare_extractions(first, second, epsilon=0.005)

    assert report.home_xg.n_changed == 0


def test_matches_only_in_one_extraction_are_counted_but_excluded_from_diff_stats() -> None:
    first = ExtractionFile(
        _FIRST_COLLECTED, "EPL", "2024", [_record("1", 1.0, 1.0), _record("2", 2.0, 2.0)]
    )
    second = ExtractionFile(_SECOND_COLLECTED, "EPL", "2024", [_record("1", 1.0, 1.0), _record("3", 3.0, 3.0)])

    report = compare_extractions(first, second)

    assert report.n_only_in_first == 1
    assert report.n_only_in_second == 1
    assert report.home_xg.n_common == 1


def test_collected_at_timestamps_are_preserved_in_report() -> None:
    first = ExtractionFile(_FIRST_COLLECTED, "EPL", "2024", [_record("1", 1.0, 1.0)])
    second = ExtractionFile(_SECOND_COLLECTED, "EPL", "2024", [_record("1", 1.0, 1.0)])

    report = compare_extractions(first, second)

    assert report.first_collected_at == _FIRST_COLLECTED.isoformat()
    assert report.second_collected_at == _SECOND_COLLECTED.isoformat()
