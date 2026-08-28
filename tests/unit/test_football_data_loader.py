from __future__ import annotations

from pathlib import Path

import pytest

from sys_foot_quant.data_engine.market_odds.football_data_loader import (
    BOOKMAKER,
    BOOKMAKERS_1X2,
    MARKET,
    SOURCE,
    load_football_data_csv,
)

_HEADER = (
    "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,B365H,B365D,B365A,"
    "BWH,BWD,BWA,PSH,PSD,PSA,"
    "B365CH,B365CD,B365CA,BWCH,BWCD,BWCA,PSCH,PSCD,PSCA,MaxH,MaxD,MaxA,AvgH,AvgD,AvgA,"
    "B365>2.5,B365<2.5,B365C>2.5,B365C<2.5\n"
)


def _write_csv(path: Path, rows: list[str]) -> Path:
    path.write_text(_HEADER + "\n".join(rows) + "\n")
    return path


def test_load_basic_rows(tmp_path: Path) -> None:
    rows = [
        "E0,16/08/2024,20:00,Man United,Fulham,1,0,H,1.6,4.2,5.25,"
        "1.65,4.1,5.3,1.63,4.15,5.2,"
        "1.66,4.15,5.33,1.68,4.1,5.4,1.64,4.2,5.25,1.68,4.5,5.6,1.62,4.36,5.15,1.85,1.95,1.88,1.92",
        "E0,17/08/2024,12:30,Ipswich,Liverpool,0,2,A,8.5,5.5,1.33,"
        "8.4,5.4,1.35,8.3,5.6,1.32,"
        "8,5.5,1.35,8.1,5.4,1.36,7.9,5.6,1.33,9,6.1,1.37,8.28,5.76,1.34,1.5,2.5,1.52,2.45",
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
    assert r0.b365_over_2_5 == pytest.approx(1.85)
    assert r0.b365_under_2_5 == pytest.approx(1.95)
    assert r0.bw_home == pytest.approx(1.65)
    assert r0.bw_draw == pytest.approx(4.1)
    assert r0.bw_away == pytest.approx(5.3)
    assert r0.ps_home == pytest.approx(1.63)
    assert r0.ps_draw == pytest.approx(4.15)
    assert r0.ps_away == pytest.approx(5.2)
    assert r0.source == SOURCE == "football_data"
    assert r0.bookmaker == BOOKMAKER == "B365"
    assert r0.market == MARKET == "1x2"
    assert BOOKMAKERS_1X2 == ("B365", "BW", "PS")
    assert r0.has_complete_odds is True
    assert r0.has_complete_over_under_2_5_odds is True
    assert r0.has_complete_bw_odds is True
    assert r0.has_complete_ps_odds is True
    assert r0.odds_1x2_by_bookmaker() == {
        "B365": {"H": pytest.approx(1.6), "D": pytest.approx(4.2), "A": pytest.approx(5.25)},
        "BW": {"H": pytest.approx(1.65), "D": pytest.approx(4.1), "A": pytest.approx(5.3)},
        "PS": {"H": pytest.approx(1.63), "D": pytest.approx(4.15), "A": pytest.approx(5.2)},
    }


def test_missing_b365_values_are_flagged_not_dropped(tmp_path: Path) -> None:
    rows = [
        "E0,16/08/2024,20:00,Man United,Fulham,1,0,H,,,,"
        "1.65,4.1,5.3,,,,"
        "1.66,4.15,5.33,1.68,4.1,5.4,1.64,4.2,5.25,1.68,4.5,5.6,1.62,4.36,5.15,,,1.88,1.92"
    ]
    path = _write_csv(tmp_path / "E0.csv", rows)
    records = load_football_data_csv(path, league="premier_league", season="2024_25")
    assert len(records) == 1
    assert records[0].b365_home is None
    assert records[0].has_complete_odds is False
    assert records[0].b365_over_2_5 is None
    assert records[0].has_complete_over_under_2_5_odds is False
    assert records[0].bw_home == pytest.approx(1.65)
    assert records[0].has_complete_bw_odds is True
    assert records[0].ps_home is None
    assert records[0].has_complete_ps_odds is False
    # bookmaker absent/partiel -> simplement absent du dict, jamais invente
    assert set(records[0].odds_1x2_by_bookmaker()) == {"BW"}


def test_missing_expected_column_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR\nE0,16/08/2024,20:00,A,B,1,0,H\n")
    with pytest.raises(ValueError, match="colonnes attendues absentes"):
        load_football_data_csv(path, league="premier_league", season="2024_25")


def test_closing_odds_columns_are_never_read_even_when_present(tmp_path: Path) -> None:
    """Meme si le fichier contient des colonnes de cloture avec des
    valeurs manifestement differentes des cotes pre-match, le loader ne
    doit produire QUE les cotes pre-match (B365/BW/PS H/D/A et
    B365>2.5/B365<2.5) - jamais une colonne suffixee C."""
    rows = [
        "E0,16/08/2024,20:00,Man United,Fulham,1,0,H,1.6,4.2,5.25,"
        "1.65,4.1,5.3,1.63,4.15,5.2,"
        "99.9,99.9,99.9,99.9,99.9,99.9,99.9,99.9,99.9,1.68,4.5,5.6,1.62,4.36,5.15,1.85,1.95,99.9,99.9"
    ]
    path = _write_csv(tmp_path / "E0.csv", rows)
    records = load_football_data_csv(path, league="premier_league", season="2024_25")
    assert records[0].b365_home == pytest.approx(1.6)  # jamais 99.9 (valeur de cloture)
    assert records[0].bw_home == pytest.approx(1.65)  # jamais 99.9 (valeur de cloture BW)
    assert records[0].ps_home == pytest.approx(1.63)  # jamais 99.9 (valeur de cloture PS)
    assert records[0].b365_over_2_5 == pytest.approx(1.85)  # jamais 99.9 (valeur de cloture)
    assert not hasattr(records[0], "b365_close_home")
    assert not hasattr(records[0], "b365_close_over_2_5")


def test_allowed_columns_never_contain_a_closing_over_under_column() -> None:
    from sys_foot_quant.data_engine.market_odds.football_data_loader import _ALLOWED_COLUMNS

    assert "B365C>2.5" not in _ALLOWED_COLUMNS
    assert "B365C<2.5" not in _ALLOWED_COLUMNS


def test_allowed_columns_never_contain_a_closing_suffix() -> None:
    from sys_foot_quant.data_engine.market_odds.football_data_loader import _ALLOWED_COLUMNS

    for col in _ALLOWED_COLUMNS:
        if col in ("B365>2.5", "B365<2.5"):
            continue  # pas un suffixe CH/CD/CA - couvert par le test dedie ci-dessus
        assert not col.endswith("CH") and not col.endswith("CD") and not col.endswith("CA"), (
            f"Colonne de cloture detectee dans _ALLOWED_COLUMNS : {col}"
        )


def test_allowed_columns_never_contain_bfe() -> None:
    """BFE (Betfair Exchange) n'est jamais lu - nature d'exchange non
    clarifiee (protocole E9), volontairement exclu du perimetre."""
    from sys_foot_quant.data_engine.market_odds.football_data_loader import _ALLOWED_COLUMNS

    assert not any("BFE" in col for col in _ALLOWED_COLUMNS)
