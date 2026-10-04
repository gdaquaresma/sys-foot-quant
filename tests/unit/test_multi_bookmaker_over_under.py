"""Tests unitaires de multi_bookmaker_over_under.py (Stage32) -
construction du dataset B365/Max/Avg Over/Under 2.5 d'ouverture apparie."""

from __future__ import annotations

from datetime import datetime

import pytest

from sys_foot_quant.data_engine.market_odds.football_data_loader import FootballDataMatchRecord
from sys_foot_quant.data_engine.market_odds.multi_bookmaker_over_under import (
    build_multi_bookmaker_over_under_dataset,
)

_LEAGUE = "liga"
_SEASON = "2024_25"
_T0 = datetime(2024, 8, 3, 20, 0, 0)  # samedi


def _us(match_id, dt, home="Barcelona", away="Sevilla"):
    return {
        "id": match_id,
        "isResult": True,
        "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "h": {"id": 1, "title": home},
        "a": {"id": 2, "title": away},
    }


def _fd(
    date_dt,
    home="Barcelona",
    away="Sevilla",
    hg=2,
    ag=1,
    b365_ou=(1.85, 1.95),
    max_ou=(1.92, 1.98),
    avg_ou=(1.87, 1.90),
):
    return FootballDataMatchRecord(
        league=_LEAGUE, season=_SEASON, source="football_data", bookmaker="B365", market="1x2",
        date_str=date_dt.strftime("%d/%m/%Y"), time_str=date_dt.strftime("%H:%M"),
        home_team_fd=home, away_team_fd=away, home_goals=hg, away_goals=ag,
        b365_home=1.8, b365_draw=3.6, b365_away=4.5,
        b365_over_2_5=b365_ou[0], b365_under_2_5=b365_ou[1],
        max_over_2_5=max_ou[0], max_under_2_5=max_ou[1],
        avg_over_2_5=avg_ou[0], avg_under_2_5=avg_ou[1],
    )


def test_matched_record_carries_b365_max_avg_odds_correctly() -> None:
    report = build_multi_bookmaker_over_under_dataset(_LEAGUE, _SEASON, [_us("1", _T0)], [_fd(_T0)])
    assert report.n_matched == 1
    rec = report.records[0]
    assert rec.b365_over_2_5 == pytest.approx(1.85)
    assert rec.b365_under_2_5 == pytest.approx(1.95)
    assert rec.max_over_2_5 == pytest.approx(1.92)
    assert rec.max_under_2_5 == pytest.approx(1.98)
    assert rec.avg_over_2_5 == pytest.approx(1.87)
    assert rec.avg_under_2_5 == pytest.approx(1.90)
    assert rec.has_complete_b365 is True
    assert rec.has_complete_max is True
    assert rec.has_complete_avg is True


def test_unmatched_match_is_simply_absent_not_invented() -> None:
    report = build_multi_bookmaker_over_under_dataset(
        _LEAGUE, _SEASON, [_us("1", _T0, "Barcelona", "Sevilla")], [_fd(_T0, "Real Madrid", "Valencia")]
    )
    assert report.n_matched == 0
    assert report.records == ()


def test_incomplete_max_avg_on_a_single_match_is_none_not_imputed() -> None:
    fd = _fd(_T0, max_ou=(None, None))
    report = build_multi_bookmaker_over_under_dataset(_LEAGUE, _SEASON, [_us("1", _T0)], [fd])
    rec = report.records[0]
    assert rec.has_complete_max is False
    assert rec.max_over_2_5 is None
    # B365/Avg restent lisibles independamment de l'absence de Max sur ce match.
    assert rec.has_complete_b365 is True
    assert rec.has_complete_avg is True


def test_never_reads_closing_columns() -> None:
    """Garde-fou structurel : le module n'importe ni n'utilise jamais
    `closing_over_under_2_5_by_bookmaker` ni un champ `*_close_*`."""
    import ast
    import inspect

    from sys_foot_quant.data_engine.market_odds import multi_bookmaker_over_under

    source = inspect.getsource(multi_bookmaker_over_under)
    assert "closing" not in source.lower()
    assert "_close_" not in source
    tree = ast.parse(source)
    attr_names = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert not any("close" in a for a in attr_names)


def test_report_counts_mirror_the_underlying_matching_report() -> None:
    report = build_multi_bookmaker_over_under_dataset(
        _LEAGUE, _SEASON, [_us("1", _T0), _us("2", _T0, "Real Madrid", "Valencia")], [_fd(_T0)]
    )
    assert report.n_understat == 2
    assert report.n_matched == 1
    assert report.n_unmatched_understat == 1
