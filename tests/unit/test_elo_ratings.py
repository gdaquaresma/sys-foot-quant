"""Tests de elo_ratings.py (Phase K) - parseur CSV ClubElo et lookup
point-in-time pur `elo_as_of`."""

from __future__ import annotations

from datetime import date

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.data_engine.market_odds.elo_ratings import (
    AmbiguousEloWindowError,
    EloRatingRow,
    elo_as_of,
    parse_clubelo_csv_rows,
)


def _row(club: str, elo: float, frm: str, to: str, country: str = "ESP", level: int = 1) -> dict:
    return {"Rank": "1", "Club": club, "Country": country, "Level": str(level), "Elo": str(elo), "From": frm, "To": to}


def test_parse_clubelo_csv_rows_basic() -> None:
    raw = [_row("Barcelona", 1950.5, "2024-08-01", "2024-08-10")]
    rows = parse_clubelo_csv_rows(raw)
    assert len(rows) == 1
    r = rows[0]
    assert r.club == "Barcelona"
    assert r.country == "ESP"
    assert r.level == 1
    assert r.elo == pytest.approx(1950.5)
    assert r.valid_from == date(2024, 8, 1)
    assert r.valid_to == date(2024, 8, 10)


def test_elo_as_of_selects_window_containing_date() -> None:
    rows = parse_clubelo_csv_rows(
        [
            _row("Barcelona", 1900.0, "2024-08-01", "2024-08-09"),
            _row("Barcelona", 1920.0, "2024-08-10", "2024-08-20"),
        ]
    )
    assert elo_as_of(rows, date(2024, 8, 5)) == pytest.approx(1900.0)
    assert elo_as_of(rows, date(2024, 8, 15)) == pytest.approx(1920.0)


def test_elo_as_of_boundary_dates_are_inclusive() -> None:
    rows = parse_clubelo_csv_rows([_row("Barcelona", 1900.0, "2024-08-01", "2024-08-09")])
    assert elo_as_of(rows, date(2024, 8, 1)) == pytest.approx(1900.0)
    assert elo_as_of(rows, date(2024, 8, 9)) == pytest.approx(1900.0)


def test_elo_as_of_returns_none_for_date_outside_all_windows() -> None:
    rows = parse_clubelo_csv_rows([_row("Barcelona", 1900.0, "2024-08-01", "2024-08-09")])
    assert elo_as_of(rows, date(2024, 7, 1)) is None
    assert elo_as_of(rows, date(2025, 1, 1)) is None


def test_elo_as_of_raises_on_overlapping_windows() -> None:
    rows = parse_clubelo_csv_rows(
        [
            _row("Barcelona", 1900.0, "2024-08-01", "2024-08-15"),
            _row("Barcelona", 1950.0, "2024-08-10", "2024-08-20"),  # chevauche la premiere - anomalie
        ]
    )
    with pytest.raises(AmbiguousEloWindowError):
        elo_as_of(rows, date(2024, 8, 12))


def test_elo_as_of_never_returns_a_window_starting_after_the_lookup_date() -> None:
    """Garde-fou absolu (docs/elo_experiment_specification.md section 2) :
    une fenetre dont `From` est POSTERIEUR a la date interrogee ne doit
    jamais etre selectionnee - injection d'une observation future avec
    une valeur extreme, doit etre exclue (retourne la fenetre anterieure
    ou None, jamais la fenetre future)."""
    rows = parse_clubelo_csv_rows(
        [
            _row("Barcelona", 1900.0, "2024-08-01", "2024-08-09"),
            _row("Barcelona", 9999.0, "2024-08-10", "2024-08-20"),  # future, valeur extreme
        ]
    )
    result = elo_as_of(rows, date(2024, 8, 5))
    assert result == pytest.approx(1900.0)
    assert result != pytest.approx(9999.0)


@given(
    lookup_offset_days=st.integers(-30, 30),
)
@settings(max_examples=100)
def test_property_elo_as_of_only_uses_windows_covering_or_before_lookup_date(lookup_offset_days: int) -> None:
    base = date(2024, 8, 1)
    rows = parse_clubelo_csv_rows(
        [
            _row("Team", 1500.0, "2024-07-01", "2024-07-31"),
            _row("Team", 1600.0, "2024-08-01", "2024-08-31"),
            _row("Team", 1700.0, "2024-09-01", "2024-09-30"),
        ]
    )
    lookup = date(base.year, base.month, base.day)
    import datetime as _dt

    lookup = lookup + _dt.timedelta(days=lookup_offset_days)
    result = elo_as_of(rows, lookup)
    if result is not None:
        matching_row = next(r for r in rows if r.valid_from <= lookup <= r.valid_to)
        assert matching_row.valid_from <= lookup
        assert result == pytest.approx(matching_row.elo)


def test_elo_rating_row_has_no_market_odds_or_closing_field() -> None:
    """Garde-fou structurel (comme Phases F/G/H) : ClubElo est une source
    totalement independante des cotes de marche - aucun champ de cote ni
    de cloture ne doit jamais apparaitre sur ce dataclass."""
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(EloRatingRow)}
    assert not any("odds" in n or "close" in n or "cote" in n for n in field_names)
