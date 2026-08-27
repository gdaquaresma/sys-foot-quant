from __future__ import annotations

from pathlib import Path

import pytest

from sys_foot_quant.data_engine.market_odds.football_data_loader import (
    BOOKMAKER,
    MARKET,
    SOURCE,
    load_football_data_csv,
)

_HEADER = (
    "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,B365H,B365D,B365A,"
    "B365CH,B365CD,B365CA,MaxH,MaxD,MaxA,AvgH,AvgD,AvgA\n"
)


def _write_csv(path: Path, rows: list[str]) -> Path:
    path.write_text(_HEADER + "\n".join(rows) + "\n")
    return path


def test_load_basic_rows(tmp_path: Path) -> None:
    rows = [
        "E0,16/08/2024,20:00,Man United,Fulham,1,0,H,1.6,4.2,5.25,1.66,4.15,5.33,1.68,4.5,5.6,1.62,4.36,5.15",
        "E0,17/08/2024,12:30,Ipswich,Liverpool,0,2,A,8.5,5.5,1.33,8,5.5,1.35,9,6.1,1.37,8.28,5.76,1.34",
    ]
    path = _write_csv(tmp_path / "E0.csv", rows)
    records = load_football_data_csv(path, league="premier_league", season="2024_25")
    assert len(records) == 2
    r0 = records[0]
    assert r0.home_team_fd == "Man United"
    assert r0.away_team_fd == "Fulham"
    assert r0.home_goals == 1 and r0.away_goals == 0
    assert r0.b365_home == pytest.approx(1.6)
    assert r0.b365_draw == pytest.approx(4.2)
    assert r0.b365_away == pytest.approx(5.25)
    assert r0.source == SOURCE == "football_data"
    assert r0.bookmaker == BOOKMAKER == "B365"
    assert r0.market == MARKET == "1x2"
    assert r0.has_complete_odds is True


def test_missing_b365_values_are_flagged_not_dropped(tmp_path: Path) -> None:
    rows = ["E0,16/08/2024,20:00,Man United,Fulham,1,0,H,,,,"
            "1.66,4.15,5.33,1.68,4.5,5.6,1.62,4.36,5.15"]
    path = _write_csv(tmp_path / "E0.csv", rows)
    records = load_football_data_csv(path, league="premier_league", season="2024_25")
    assert len(records) == 1
    assert records[0].b365_home is None
    assert records[0].has_complete_odds is False


def test_missing_expected_column_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR\nE0,16/08/2024,20:00,A,B,1,0,H\n")
    with pytest.raises(ValueError, match="colonnes attendues absentes"):
        load_football_data_csv(path, league="premier_league", season="2024_25")


def test_closing_odds_columns_are_never_read_even_when_present(tmp_path: Path) -> None:
    """Meme si le fichier contient des colonnes de cloture avec des
    valeurs manifestement differentes des cotes pre-match, le loader ne
    doit produire QUE B365H/D/A - jamais B365CH/CD/CA."""
    rows = [
        "E0,16/08/2024,20:00,Man United,Fulham,1,0,H,1.6,4.2,5.25,"
        "99.9,99.9,99.9,1.68,4.5,5.6,1.62,4.36,5.15"
    ]
    path = _write_csv(tmp_path / "E0.csv", rows)
    records = load_football_data_csv(path, league="premier_league", season="2024_25")
    assert records[0].b365_home == pytest.approx(1.6)  # jamais 99.9 (valeur de cloture)
    assert not hasattr(records[0], "b365_close_home")


def test_allowed_columns_never_contain_a_closing_suffix() -> None:
    from sys_foot_quant.data_engine.market_odds.football_data_loader import _ALLOWED_COLUMNS

    for col in _ALLOWED_COLUMNS:
        assert not col.endswith("CH") and not col.endswith("CD") and not col.endswith("CA"), (
            f"Colonne de cloture detectee dans _ALLOWED_COLUMNS : {col}"
        )
