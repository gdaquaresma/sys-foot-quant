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
    "B365>2.5,B365<2.5,P>2.5,P<2.5,B365C>2.5,B365C<2.5,PC>2.5,PC<2.5,HST,AST,"
    "BFEH,BFED,BFEA,BFE>2.5,BFE<2.5,AHh,B365AHH,B365AHA,PAHH,PAHA\n"
)


def _write_csv(path: Path, rows: list[str]) -> Path:
    # HST,AST (Phase F), BFEH,BFED,BFEA,BFE>2.5,BFE<2.5 (Phase G), puis
    # AHh,B365AHH,B365AHA,PAHH,PAHA (Phase H) ajoutees en fin de _HEADER -
    # valeurs arbitraires non pertinentes pour ces tests, ajoutees en fin
    # de chaque ligne.
    rows = [f"{r},4,3,1.90,3.80,4.20,1.85,1.95,-0.75,1.95,1.95,1.98,1.92" for r in rows]
    path.write_text(_HEADER + "\n".join(rows) + "\n")
    return path


def test_load_basic_rows(tmp_path: Path) -> None:
    rows = [
        "E0,16/08/2024,20:00,Man United,Fulham,1,0,H,1.6,4.2,5.25,"
        "1.65,4.1,5.3,1.63,4.15,5.2,"
        "1.66,4.15,5.33,1.68,4.1,5.4,1.64,4.2,5.25,1.68,4.5,5.6,1.62,4.36,5.15,1.85,1.95,1.80,1.90,1.88,1.92,1.82,1.87",
        "E0,17/08/2024,12:30,Ipswich,Liverpool,0,2,A,8.5,5.5,1.33,"
        "8.4,5.4,1.35,8.3,5.6,1.32,"
        "8,5.5,1.35,8.1,5.4,1.36,7.9,5.6,1.33,9,6.1,1.37,8.28,5.76,1.34,1.5,2.5,1.48,2.55,1.52,2.45,1.50,2.50",
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
    assert r0.p_over_2_5 == pytest.approx(1.80)
    assert r0.p_under_2_5 == pytest.approx(1.90)
    assert r0.bw_home == pytest.approx(1.65)
    assert r0.bw_draw == pytest.approx(4.1)
    assert r0.bw_away == pytest.approx(5.3)
    assert r0.ps_home == pytest.approx(1.63)
    assert r0.ps_draw == pytest.approx(4.15)
    assert r0.ps_away == pytest.approx(5.2)
    assert r0.source == SOURCE == "football_data"
    assert r0.bookmaker == BOOKMAKER == "B365"
    assert r0.market == MARKET == "1x2"
    assert BOOKMAKERS_1X2 == ("B365", "BW", "PS", "WH", "LB")
    assert r0.has_complete_odds is True
    assert r0.has_complete_over_under_2_5_odds is True
    assert r0.has_complete_p_over_under_2_5_odds is True
    assert r0.has_complete_bw_odds is True
    assert r0.has_complete_ps_odds is True
    assert r0.odds_1x2_by_bookmaker() == {
        "B365": {"H": pytest.approx(1.6), "D": pytest.approx(4.2), "A": pytest.approx(5.25)},
        "BW": {"H": pytest.approx(1.65), "D": pytest.approx(4.1), "A": pytest.approx(5.3)},
        "PS": {"H": pytest.approx(1.63), "D": pytest.approx(4.15), "A": pytest.approx(5.2)},
    }
    assert r0.over_under_2_5_by_bookmaker() == {
        "B365": {"Over": pytest.approx(1.85), "Under": pytest.approx(1.95)},
        "P": {"Over": pytest.approx(1.80), "Under": pytest.approx(1.90)},
    }
    # --- cotes de CLOTURE (E16) - RETROSPECTIF uniquement -----------------
    assert r0.b365_close_home == pytest.approx(1.66)
    assert r0.b365_close_draw == pytest.approx(4.15)
    assert r0.b365_close_away == pytest.approx(5.33)
    assert r0.bw_close_home == pytest.approx(1.68)
    assert r0.bw_close_draw == pytest.approx(4.1)
    assert r0.bw_close_away == pytest.approx(5.4)
    assert r0.ps_close_home == pytest.approx(1.64)
    assert r0.ps_close_draw == pytest.approx(4.2)
    assert r0.ps_close_away == pytest.approx(5.25)
    assert r0.b365_close_over_2_5 == pytest.approx(1.88)
    assert r0.b365_close_under_2_5 == pytest.approx(1.92)
    assert r0.p_close_over_2_5 == pytest.approx(1.82)
    assert r0.p_close_under_2_5 == pytest.approx(1.87)
    assert r0.has_complete_close_odds is True
    assert r0.has_complete_close_over_under_2_5_odds is True
    assert r0.has_complete_p_close_over_under_2_5_odds is True
    assert r0.has_complete_bw_close_odds is True
    assert r0.has_complete_ps_close_odds is True
    assert r0.closing_odds_1x2_by_bookmaker() == {
        "B365": {"H": pytest.approx(1.66), "D": pytest.approx(4.15), "A": pytest.approx(5.33)},
        "BW": {"H": pytest.approx(1.68), "D": pytest.approx(4.1), "A": pytest.approx(5.4)},
        "PS": {"H": pytest.approx(1.64), "D": pytest.approx(4.2), "A": pytest.approx(5.25)},
    }
    assert r0.closing_over_under_2_5_by_bookmaker() == {
        "B365": {"Over": pytest.approx(1.88), "Under": pytest.approx(1.92)},
        "P": {"Over": pytest.approx(1.82), "Under": pytest.approx(1.87)},
    }
    # --- tirs cadres (Phase F) - POST-kickoff, jamais une cote -------------
    assert r0.home_shots_on_target == 4
    assert r0.away_shots_on_target == 3
    # --- Betfair Exchange (Phase G) - PAS Betfair Sportsbook ---------------
    assert r0.bfe_home == pytest.approx(1.90)
    assert r0.bfe_draw == pytest.approx(3.80)
    assert r0.bfe_away == pytest.approx(4.20)
    assert r0.bfe_over_2_5 == pytest.approx(1.85)
    assert r0.bfe_under_2_5 == pytest.approx(1.95)
    assert r0.has_complete_bfe_odds is True
    assert r0.has_complete_bfe_over_under_2_5_odds is True
    assert r0.bfe_odds_1x2() == {"H": pytest.approx(1.90), "D": pytest.approx(3.80), "A": pytest.approx(4.20)}
    assert r0.bfe_over_under_2_5() == {"Over": pytest.approx(1.85), "Under": pytest.approx(1.95)}
    # BFE reste ISOLE des methodes/tuple deja utilises par E9/E13 (geles) -
    # jamais un "BFE" qui apparait dans leur sortie ou leur perimetre.
    assert "BFE" not in r0.odds_1x2_by_bookmaker()
    assert "BFE" not in r0.over_under_2_5_by_bookmaker()
    assert "BFE" not in BOOKMAKERS_1X2
    # --- Handicap asiatique (Phase H) - OUVERTURE uniquement ---------------
    assert r0.ah_line == pytest.approx(-0.75)
    assert r0.b365_ah_home == pytest.approx(1.95)
    assert r0.b365_ah_away == pytest.approx(1.95)
    assert r0.p_ah_home == pytest.approx(1.98)
    assert r0.p_ah_away == pytest.approx(1.92)
    assert r0.has_complete_b365_ah_odds is True
    assert r0.has_complete_p_ah_odds is True
    assert r0.b365_asian_handicap() == {"line": pytest.approx(-0.75), "home": pytest.approx(1.95), "away": pytest.approx(1.95)}
    assert r0.p_asian_handicap() == {"line": pytest.approx(-0.75), "home": pytest.approx(1.98), "away": pytest.approx(1.92)}


def test_ah_line_can_be_negative_zero_or_positive(tmp_path: Path) -> None:
    """``AHh`` n'est PAS une cote (jamais bornee a ``> 1.0``, contrairement
    a ``_parse_optional_float``) - verifie explicitement pour une ligne
    negative, nulle, et positive."""
    for line in (-1.5, 0.0, 1.5):
        rows = [
            "E0,16/08/2024,20:00,Man United,Fulham,1,0,H,1.6,4.2,5.25,"
            "1.65,4.1,5.3,1.63,4.15,5.2,"
            f"1.66,4.15,5.33,1.68,4.1,5.4,1.64,4.2,5.25,1.68,4.5,5.6,1.62,4.36,5.15,1.85,1.95,1.80,1.90,1.88,1.92,1.82,1.87,4,3,1.90,3.80,4.20,1.85,1.95,{line},1.95,1.95,1.98,1.92",
        ]
        path = tmp_path / f"E0_{line}.csv"
        path.write_text(_HEADER + "\n".join(rows) + "\n")
        records = load_football_data_csv(path, league="premier_league", season="2024_25")
        assert records[0].ah_line == pytest.approx(line)


def test_ah_column_missing_raises(tmp_path: Path) -> None:
    """``AHh``/``B365AHH``/``B365AHA``/``PAHH``/``PAHA`` font partie de
    ``_ALLOWED_COLUMNS`` (Phase H) - un fichier sans ces colonnes doit
    echouer explicitement."""
    path = tmp_path / "bad.csv"
    path.write_text(
        "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,B365H,B365D,B365A,BWH,BWD,BWA,PSH,PSD,PSA,"
        "B365CH,B365CD,B365CA,BWCH,BWCD,BWCA,PSCH,PSCD,PSCA,"
        "B365>2.5,B365<2.5,P>2.5,P<2.5,B365C>2.5,B365C<2.5,PC>2.5,PC<2.5,HST,AST,BFEH,BFED,BFEA,BFE>2.5,BFE<2.5\n"
        "E0,16/08/2024,20:00,A,B,1,0,H,1.6,4.2,5.25,1.65,4.1,5.3,1.63,4.15,5.2,"
        "1.66,4.15,5.33,1.68,4.1,5.4,1.64,4.2,5.25,1.85,1.95,1.80,1.90,1.88,1.92,1.82,1.87,4,3,1.90,3.80,4.20,1.85,1.95\n"
    )
    with pytest.raises(ValueError, match="colonnes attendues absentes"):
        load_football_data_csv(path, league="premier_league", season="2024_25")


def test_ah_missing_on_a_single_row_is_absent_not_invented(tmp_path: Path) -> None:
    """Pinnacle AH est absent sur ~23% des matchs (couverture constatee,
    voir docstring de module) - un match sans Pinnacle AH reste
    exploitable pour B365 AH, simplement absent de ``p_asian_handicap()``."""
    rows = [
        "E0,16/08/2024,20:00,Man United,Fulham,1,0,H,1.6,4.2,5.25,"
        "1.65,4.1,5.3,1.63,4.15,5.2,"
        "1.66,4.15,5.33,1.68,4.1,5.4,1.64,4.2,5.25,1.68,4.5,5.6,1.62,4.36,5.15,1.85,1.95,1.80,1.90,1.88,1.92,1.82,1.87,4,3,1.90,3.80,4.20,1.85,1.95,-0.75,1.95,1.95,,",
    ]
    path = tmp_path / "E0.csv"
    path.write_text(_HEADER + "\n".join(rows) + "\n")
    records = load_football_data_csv(path, league="premier_league", season="2024_25")
    r = records[0]
    assert r.ah_line == pytest.approx(-0.75)
    assert r.has_complete_b365_ah_odds is True
    assert r.p_ah_home is None
    assert r.has_complete_p_ah_odds is False
    assert r.p_asian_handicap() is None
    assert r.b365_asian_handicap() is not None


def test_bfe_column_missing_raises(tmp_path: Path) -> None:
    """``BFEH``/``BFED``/``BFEA``/``BFE>2.5``/``BFE<2.5`` font partie de
    ``_ALLOWED_COLUMNS`` (Phase G) - un fichier sans ces colonnes doit
    echouer explicitement, jamais silencieusement produire ``None``."""
    path = tmp_path / "bad.csv"
    path.write_text(
        "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,B365H,B365D,B365A,BWH,BWD,BWA,PSH,PSD,PSA,"
        "B365CH,B365CD,B365CA,BWCH,BWCD,BWCA,PSCH,PSCD,PSCA,"
        "B365>2.5,B365<2.5,P>2.5,P<2.5,B365C>2.5,B365C<2.5,PC>2.5,PC<2.5,HST,AST\n"
        "E0,16/08/2024,20:00,A,B,1,0,H,1.6,4.2,5.25,1.65,4.1,5.3,1.63,4.15,5.2,"
        "1.66,4.15,5.33,1.68,4.1,5.4,1.64,4.2,5.25,1.85,1.95,1.80,1.90,1.88,1.92,1.82,1.87,4,3\n"
    )
    with pytest.raises(ValueError, match="colonnes attendues absentes"):
        load_football_data_csv(path, league="premier_league", season="2024_25")


def test_bfe_missing_on_a_single_row_is_absent_not_invented(tmp_path: Path) -> None:
    """BFE est absent sur ~5-8% des matchs 2025/26 (couverture constatee,
    voir docstring de module) - un match sans BFE reste exploitable,
    simplement absent de ``bfe_odds_1x2()``/``bfe_over_under_2_5()``."""
    rows = [
        "E0,16/08/2024,20:00,Man United,Fulham,1,0,H,1.6,4.2,5.25,"
        "1.65,4.1,5.3,1.63,4.15,5.2,"
        "1.66,4.15,5.33,1.68,4.1,5.4,1.64,4.2,5.25,1.68,4.5,5.6,1.62,4.36,5.15,1.85,1.95,1.80,1.90,1.88,1.92,1.82,1.87,4,3,,,,,,-0.75,1.95,1.95,1.98,1.92",
    ]
    path = tmp_path / "E0.csv"
    path.write_text(_HEADER + "\n".join(rows) + "\n")
    records = load_football_data_csv(path, league="premier_league", season="2024_25")
    r = records[0]
    assert r.bfe_home is None
    assert r.has_complete_bfe_odds is False
    assert r.bfe_odds_1x2() is None
    # les cotes 1X2 B365 restent lisibles independamment de l'absence de BFE
    assert r.b365_home == pytest.approx(1.6)


def test_shots_on_target_column_missing_raises(tmp_path: Path) -> None:
    """HST/AST font partie de ``_ALLOWED_COLUMNS`` (Phase F, couverture
    100% verifiee sur les six fichiers reels) - un fichier sans ces
    colonnes doit echouer explicitement, jamais silencieusement produire
    ``None``."""
    path = tmp_path / "bad.csv"
    path.write_text(
        "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,B365H,B365D,B365A,BWH,BWD,BWA,PSH,PSD,PSA,"
        "B365CH,B365CD,B365CA,BWCH,BWCD,BWCA,PSCH,PSCD,PSCA,"
        "B365>2.5,B365<2.5,P>2.5,P<2.5,B365C>2.5,B365C<2.5,PC>2.5,PC<2.5\n"
        "E0,16/08/2024,20:00,A,B,1,0,H,1.6,4.2,5.25,1.65,4.1,5.3,1.63,4.15,5.2,"
        "1.66,4.15,5.33,1.68,4.1,5.4,1.64,4.2,5.25,1.85,1.95,1.80,1.90,1.88,1.92,1.82,1.87\n"
    )
    with pytest.raises(ValueError, match="colonnes attendues absentes"):
        load_football_data_csv(path, league="premier_league", season="2024_25")


def test_shots_on_target_values_are_read_as_integers(tmp_path: Path) -> None:
    rows = [
        "E0,16/08/2024,20:00,Man United,Fulham,1,0,H,1.6,4.2,5.25,"
        "1.65,4.1,5.3,1.63,4.15,5.2,"
        "1.66,4.15,5.33,1.68,4.1,5.4,1.64,4.2,5.25,1.68,4.5,5.6,1.62,4.36,5.15,1.85,1.95,1.80,1.90,1.88,1.92,1.82,1.87,9,0,"
        "1.90,3.80,4.20,1.85,1.95,-0.75,1.95,1.95,1.98,1.92",
    ]
    path = tmp_path / "E0.csv"
    path.write_text(_HEADER + "\n".join(rows) + "\n")  # ecrit directement (pas _write_csv, HST/AST/BFE/AH deja fournis)
    records = load_football_data_csv(path, league="premier_league", season="2024_25")
    assert records[0].home_shots_on_target == 9
    assert records[0].away_shots_on_target == 0


def test_missing_b365_values_are_flagged_not_dropped(tmp_path: Path) -> None:
    rows = [
        "E0,16/08/2024,20:00,Man United,Fulham,1,0,H,,,,"
        "1.65,4.1,5.3,,,,"
        "1.66,4.15,5.33,1.68,4.1,5.4,1.64,4.2,5.25,1.68,4.5,5.6,1.62,4.36,5.15,,,,,1.88,1.92,1.82,1.87"
    ]
    path = _write_csv(tmp_path / "E0.csv", rows)
    records = load_football_data_csv(path, league="premier_league", season="2024_25")
    assert len(records) == 1
    assert records[0].b365_home is None
    assert records[0].has_complete_odds is False
    assert records[0].b365_over_2_5 is None
    assert records[0].has_complete_over_under_2_5_odds is False
    assert records[0].p_over_2_5 is None
    assert records[0].has_complete_p_over_under_2_5_odds is False
    assert records[0].bw_home == pytest.approx(1.65)
    assert records[0].has_complete_bw_odds is True
    assert records[0].ps_home is None
    assert records[0].has_complete_ps_odds is False
    # bookmaker absent/partiel -> simplement absent du dict, jamais invente
    assert set(records[0].odds_1x2_by_bookmaker()) == {"BW"}
    assert records[0].over_under_2_5_by_bookmaker() == {}
    # les cotes de CLOTURE restent lisibles independamment de l'ouverture
    # (constat reel possible - une cote peut manquer a l'ouverture mais
    # etre presente a la cloture, ou l'inverse) - jamais couplees.
    assert records[0].b365_close_home == pytest.approx(1.66)
    assert records[0].has_complete_close_odds is True
    assert records[0].ps_close_home == pytest.approx(1.64)
    assert records[0].has_complete_ps_close_odds is True
    assert records[0].b365_close_over_2_5 == pytest.approx(1.88)
    assert records[0].has_complete_close_over_under_2_5_odds is True
    assert records[0].p_close_over_2_5 == pytest.approx(1.82)
    assert records[0].has_complete_p_close_over_under_2_5_odds is True


def test_missing_expected_column_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR\nE0,16/08/2024,20:00,A,B,1,0,H\n")
    with pytest.raises(ValueError, match="colonnes attendues absentes"):
        load_football_data_csv(path, league="premier_league", season="2024_25")


def test_closing_odds_columns_are_read_and_distinct_from_opening(tmp_path: Path) -> None:
    """Extension E16 : les cotes de cloture SONT desormais lues (colonnes
    deja presentes dans les fichiers sources, jamais inventees) - mais
    restent des champs SEPARES et DISTINCTS des cotes d'ouverture, jamais
    confondus ni substitues l'un a l'autre."""
    rows = [
        "E0,16/08/2024,20:00,Man United,Fulham,1,0,H,1.6,4.2,5.25,"
        "1.65,4.1,5.3,1.63,4.15,5.2,"
        "1.70,4.30,5.10,1.72,4.20,5.15,1.71,4.25,5.05,1.68,4.5,5.6,1.62,4.36,5.15,1.85,1.95,1.80,1.90,1.90,1.90,1.86,1.86"
    ]
    path = _write_csv(tmp_path / "E0.csv", rows)
    records = load_football_data_csv(path, league="premier_league", season="2024_25")
    r = records[0]
    # ouverture et cloture different reellement l'une de l'autre ici
    assert r.b365_home == pytest.approx(1.6)
    assert r.b365_close_home == pytest.approx(1.70)
    assert r.b365_home != r.b365_close_home
    assert r.b365_over_2_5 == pytest.approx(1.85)
    assert r.b365_close_over_2_5 == pytest.approx(1.90)
    assert r.b365_over_2_5 != r.b365_close_over_2_5


def test_allowed_columns_contain_exactly_the_documented_closing_columns() -> None:
    """Perimetre de cloture volontairement limite (E16) : B365/BW/PS 1X2 et
    B365/P Over/Under - jamais Max/Avg/BFE (deja exclus, ADR 0006), jamais
    une colonne de cloture au-dela de celles documentees."""
    from sys_foot_quant.data_engine.market_odds.football_data_loader import _ALLOWED_COLUMNS

    closing_columns = {c for c in _ALLOWED_COLUMNS if c.endswith(("CH", "CD", "CA")) or c.startswith(("B365C", "PC"))}
    assert closing_columns == {
        "B365CH", "B365CD", "B365CA",
        "BWCH", "BWCD", "BWCA",
        "PSCH", "PSCD", "PSCA",
        "B365C>2.5", "B365C<2.5",
        "PC>2.5", "PC<2.5",
    }


def test_allowed_columns_contain_exactly_the_documented_bfe_columns() -> None:
    """Decision E9/E13 ("BFE jamais lu, nature d'exchange non clarifiee")
    REVISITEE en Phase G apres audit empirique dedie (voir docstring de
    module) : exactement les 5 colonnes BFE d'OUVERTURE (1X2 + Over/Under
    2.5), JAMAIS le handicap asiatique (`BFEAHH`/`BFEAHA`) ni la cloture
    (`BFECH`/`BFEC>2.5`/...) ni Betfair Sportsbook (`BFH`/`BFD`/`BFDH`,
    instrument DIFFERENT, non lu - voir docstring de module)."""
    from sys_foot_quant.data_engine.market_odds.football_data_loader import _ALLOWED_COLUMNS

    bfe_columns = {c for c in _ALLOWED_COLUMNS if "BFE" in c}
    assert bfe_columns == {"BFEH", "BFED", "BFEA", "BFE>2.5", "BFE<2.5"}
    assert not any(c.startswith("BF") and "BFE" not in c for c in _ALLOWED_COLUMNS)  # BF/BFD (Sportsbook) jamais lu


def test_bfe_is_never_merged_into_the_frozen_e9_e13_bookmaker_layer() -> None:
    """Garde-fou de non-regression E9/E13 (Phase G) : BFE ne doit JAMAIS
    apparaitre dans ``BOOKMAKERS_1X2`` ni dans les sorties de
    ``odds_1x2_by_bookmaker``/``over_under_2_5_by_bookmaker`` - ces
    methodes sont deja utilisees par des scripts GELES (E9, E13) dont la
    reproductibilite ne doit jamais etre alteree par une extension
    ulterieure."""
    assert "BFE" not in BOOKMAKERS_1X2


def test_allowed_columns_never_contain_max_or_avg_aggregates() -> None:
    """Max*/Avg* sont des agregats de marche a composition opaque -
    exclus par l'ADR 0006, decision non revisitee en E13/E16 (y compris
    leurs variantes de cloture MaxC*/AvgC*)."""
    from sys_foot_quant.data_engine.market_odds.football_data_loader import _ALLOWED_COLUMNS, _OPTIONAL_COLUMNS

    for col in list(_ALLOWED_COLUMNS) + list(_OPTIONAL_COLUMNS):
        assert not col.startswith("Max") and not col.startswith("Avg")


def test_optional_columns_absent_from_file_yield_none_not_error(tmp_path: Path) -> None:
    """Un fichier SANS colonnes WH/LB du tout (comme les six fichiers
    reels a des saisons donnees) ne doit jamais lever d'erreur - les
    champs correspondants valent simplement None."""
    rows = [
        "E0,16/08/2024,20:00,Man United,Fulham,1,0,H,1.6,4.2,5.25,"
        "1.65,4.1,5.3,1.63,4.15,5.2,"
        "1.66,4.15,5.33,1.68,4.1,5.4,1.64,4.2,5.25,1.68,4.5,5.6,1.62,4.36,5.15,1.85,1.95,1.80,1.90,1.88,1.92,1.82,1.87"
    ]
    path = _write_csv(tmp_path / "E0.csv", rows)  # _HEADER n'a pas WHH/LBH/WHCH/LBCH
    records = load_football_data_csv(path, league="premier_league", season="2024_25")
    assert records[0].wh_home is None
    assert records[0].lb_home is None
    assert records[0].has_complete_wh_odds is False
    assert records[0].has_complete_lb_odds is False
    assert "WH" not in records[0].odds_1x2_by_bookmaker()
    assert "LB" not in records[0].odds_1x2_by_bookmaker()
    assert records[0].wh_close_home is None
    assert records[0].lb_close_home is None
    assert records[0].has_complete_wh_close_odds is False
    assert records[0].has_complete_lb_close_odds is False
    assert "WH" not in records[0].closing_odds_1x2_by_bookmaker()
    assert "LB" not in records[0].closing_odds_1x2_by_bookmaker()


_REQUIRED_PREFIX = (
    "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,"
    "B365H,B365D,B365A,BWH,BWD,BWA,PSH,PSD,PSA,"
    "B365CH,B365CD,B365CA,BWCH,BWCD,BWCA,PSCH,PSCD,PSCA"
)
_REQUIRED_ROW_PREFIX = (
    "E0,{date},{time},{home},{away},{hg},{ag},{ftr},"
    "1.6,4.2,5.25,1.65,4.1,5.3,1.63,4.15,5.2,"
    "1.58,4.30,5.40,1.60,4.20,5.35,1.61,4.25,5.15"
)
_OU_SUFFIX = ",B365>2.5,B365<2.5,P>2.5,P<2.5,B365C>2.5,B365C<2.5,PC>2.5,PC<2.5,HST,AST,BFEH,BFED,BFEA,BFE>2.5,BFE<2.5,AHh,B365AHH,B365AHA,PAHH,PAHA"
_OU_ROW_SUFFIX = ",1.85,1.95,1.80,1.90,1.88,1.92,1.86,1.89,4,3,1.90,3.80,4.20,1.85,1.95,-0.75,1.95,1.95,1.98,1.92"


def test_wh_column_present_and_read_when_in_file(tmp_path: Path) -> None:
    header = f"{_REQUIRED_PREFIX},WHH,WHD,WHA{_OU_SUFFIX}\n"
    row = _REQUIRED_ROW_PREFIX.format(date="16/08/2024", time="20:00", home="A", away="B", hg=1, ag=0, ftr="H")
    path = tmp_path / "E0.csv"
    path.write_text(header + f"{row},1.70,4.0,5.4{_OU_ROW_SUFFIX}\n")
    records = load_football_data_csv(path, league="premier_league", season="2024_25")
    r = records[0]
    assert r.wh_home == pytest.approx(1.70)
    assert r.wh_draw == pytest.approx(4.0)
    assert r.wh_away == pytest.approx(5.4)
    assert r.has_complete_wh_odds is True
    assert r.lb_home is None  # LB absent de ce fichier
    assert r.odds_1x2_by_bookmaker()["WH"] == {"H": pytest.approx(1.70), "D": pytest.approx(4.0), "A": pytest.approx(5.4)}


def test_lb_column_present_and_read_when_in_file(tmp_path: Path) -> None:
    header = f"{_REQUIRED_PREFIX},LBH,LBD,LBA{_OU_SUFFIX}\n"
    row = _REQUIRED_ROW_PREFIX.format(date="16/08/2025", time="20:00", home="A", away="B", hg=1, ag=0, ftr="H")
    path = tmp_path / "E0.csv"
    path.write_text(header + f"{row},1.72,4.05,5.35{_OU_ROW_SUFFIX}\n")
    records = load_football_data_csv(path, league="premier_league", season="2025_26")
    r = records[0]
    assert r.lb_home == pytest.approx(1.72)
    assert r.has_complete_lb_odds is True
    assert r.wh_home is None  # WH absent de ce fichier
    assert r.odds_1x2_by_bookmaker()["LB"]["H"] == pytest.approx(1.72)


def test_wh_and_lb_never_both_present_is_not_enforced_but_reads_correctly_if_both_columns_exist(tmp_path: Path) -> None:
    """Cas hypothetique (jamais observe dans les six fichiers reels) : si
    un fichier contenait les deux colonnes, le loader doit simplement les
    lire toutes les deux sans les fusionner - comportement mecanique,
    pas une hypothese sur les donnees reelles."""
    header = f"{_REQUIRED_PREFIX},WHH,WHD,WHA,LBH,LBD,LBA{_OU_SUFFIX}\n"
    row = _REQUIRED_ROW_PREFIX.format(date="16/08/2024", time="20:00", home="A", away="B", hg=1, ag=0, ftr="H")
    path = tmp_path / "E0.csv"
    path.write_text(header + f"{row},1.70,4.0,5.4,1.72,4.05,5.35{_OU_ROW_SUFFIX}\n")
    records = load_football_data_csv(path, league="premier_league", season="2024_25")
    r = records[0]
    assert r.wh_home == pytest.approx(1.70)
    assert r.lb_home == pytest.approx(1.72)
    assert set(r.odds_1x2_by_bookmaker()) >= {"WH", "LB"}


def test_missing_optional_value_on_a_single_row_is_none(tmp_path: Path) -> None:
    header = f"{_REQUIRED_PREFIX},WHH,WHD,WHA{_OU_SUFFIX}\n"
    row = _REQUIRED_ROW_PREFIX.format(date="16/08/2024", time="20:00", home="A", away="B", hg=1, ag=0, ftr="H")
    path = tmp_path / "E0.csv"
    path.write_text(header + f"{row},,,{_OU_ROW_SUFFIX}\n")
    records = load_football_data_csv(path, league="premier_league", season="2024_25")
    assert records[0].wh_home is None
    assert records[0].has_complete_wh_odds is False


def test_literal_zero_odds_value_is_treated_as_missing_not_as_a_real_price(tmp_path: Path) -> None:
    """CONSTAT EMPIRIQUE (E13) : un match reel (Paris SG-Le Havre, F1
    2024/25, 19/04/2025) porte litteralement ``"0"`` dans ``P>2.5``/
    ``P<2.5`` - le sentinelle Football-Data pour "cote non collectee" sur
    ce bookmaker precis, jamais une vraie cote (une cote decimale est
    toujours > 1.0). Doit etre traite comme absent (None), jamais comme
    0.0 (ce qui casserait toute normalisation d'overround en aval) - la
    meme regle s'applique identiquement aux cotes de CLOTURE (E16)."""
    header = f"{_REQUIRED_PREFIX},B365>2.5,B365<2.5,P>2.5,P<2.5,B365C>2.5,B365C<2.5,PC>2.5,PC<2.5,HST,AST,BFEH,BFED,BFEA,BFE>2.5,BFE<2.5,AHh,B365AHH,B365AHA,PAHH,PAHA\n"
    row = _REQUIRED_ROW_PREFIX.format(date="19/04/2025", time="16:00", home="A", away="B", hg=2, ag=1, ftr="H")
    path = tmp_path / "E0.csv"
    path.write_text(header + f"{row},1.25,4.0,0,0,1.30,3.9,0,0,4,3,1.90,3.80,4.20,1.85,1.95,-0.75,1.95,1.95,1.98,1.92\n")
    records = load_football_data_csv(path, league="ligue1", season="2024_25")
    r = records[0]
    assert r.p_over_2_5 is None
    assert r.p_under_2_5 is None
    assert r.has_complete_p_over_under_2_5_odds is False
    assert "P" not in r.over_under_2_5_by_bookmaker()
    assert r.p_close_over_2_5 is None
    assert r.p_close_under_2_5 is None
    assert r.has_complete_p_close_over_under_2_5_odds is False
    assert "P" not in r.closing_over_under_2_5_by_bookmaker()


def test_wh_closing_column_present_and_read_when_in_file(tmp_path: Path) -> None:
    header = f"{_REQUIRED_PREFIX},WHH,WHD,WHA,WHCH,WHCD,WHCA{_OU_SUFFIX}\n"
    row = _REQUIRED_ROW_PREFIX.format(date="16/08/2024", time="20:00", home="A", away="B", hg=1, ag=0, ftr="H")
    path = tmp_path / "E0.csv"
    path.write_text(header + f"{row},1.70,4.0,5.4,1.75,3.95,5.30{_OU_ROW_SUFFIX}\n")
    records = load_football_data_csv(path, league="premier_league", season="2024_25")
    r = records[0]
    assert r.wh_close_home == pytest.approx(1.75)
    assert r.wh_close_draw == pytest.approx(3.95)
    assert r.wh_close_away == pytest.approx(5.30)
    assert r.has_complete_wh_close_odds is True
    assert r.lb_close_home is None
    assert r.closing_odds_1x2_by_bookmaker()["WH"] == {"H": pytest.approx(1.75), "D": pytest.approx(3.95), "A": pytest.approx(5.30)}


def test_lb_closing_column_present_and_read_when_in_file(tmp_path: Path) -> None:
    header = f"{_REQUIRED_PREFIX},LBH,LBD,LBA,LBCH,LBCD,LBCA{_OU_SUFFIX}\n"
    row = _REQUIRED_ROW_PREFIX.format(date="16/08/2025", time="20:00", home="A", away="B", hg=1, ag=0, ftr="H")
    path = tmp_path / "E0.csv"
    path.write_text(header + f"{row},1.72,4.05,5.35,1.78,3.90,5.20{_OU_ROW_SUFFIX}\n")
    records = load_football_data_csv(path, league="premier_league", season="2025_26")
    r = records[0]
    assert r.lb_close_home == pytest.approx(1.78)
    assert r.has_complete_lb_close_odds is True
    assert r.wh_close_home is None
    assert r.closing_odds_1x2_by_bookmaker()["LB"]["H"] == pytest.approx(1.78)
