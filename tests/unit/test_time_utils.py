from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sys_foot_quant.common.time_utils import assert_strictly_sorted, to_utc


def test_to_utc_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="naif"):
        to_utc(datetime(2024, 1, 1))


def test_to_utc_converts_non_utc_timezone() -> None:
    tz_minus_5 = timezone(timedelta(hours=-5))
    local = datetime(2024, 1, 1, 10, 0, tzinfo=tz_minus_5)
    converted = to_utc(local)
    assert converted.tzinfo == timezone.utc
    assert converted.hour == 15


def test_assert_strictly_sorted_accepts_non_decreasing_sequence() -> None:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    sequence = [base, base + timedelta(hours=1), base + timedelta(hours=1), base + timedelta(days=1)]
    assert_strictly_sorted(sequence)  # ne doit pas lever


def test_assert_strictly_sorted_rejects_decreasing_sequence() -> None:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    sequence = [base + timedelta(days=1), base]
    with pytest.raises(ValueError, match="chronologique"):
        assert_strictly_sorted(sequence)
