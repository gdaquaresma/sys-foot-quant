"""Tests unitaires du parseur OpenFootball (calendrier multi-competitions,
implementation controlee - docs/multi_competition_calendar_open_data_audit.md,
docs/openfootball_calendar.md). Fixtures synthetiques minimales, jamais les
fichiers reels (couverts separement par
tests/integration/test_openfootball_calendar_real_files.py)."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from sys_foot_quant.data_engine.market_odds import openfootball_calendar as ofc

_HEADER = "= Test League 2024/25\n\n# Date       Fri Aug 16 2024 - Sat May 17 2025 (274d)\n# Teams      4\n# Matches    2\n\n\n"


def _write(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(_HEADER + body, encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# 1. Ligne valide
# --------------------------------------------------------------------------


def test_parses_a_valid_match_line(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "valid.txt",
        "▪ Matchday 1\n  Fri Aug 16 2024\n    20:45  Le Havre AC             v Paris Saint-Germain FC   1-4 (0-1)\n",
    )
    report = ofc._parse_file(path, "ligue1", "2024_25")
    assert report.exclusions == ()
    assert len(report.matches) == 1
    m = report.matches[0]
    assert m.home_team == "Le Havre AC"
    assert m.away_team == "Paris Saint-Germain FC"
    assert m.kickoff_local_naive == datetime(2024, 8, 16, 20, 45)
    assert m.home_goals == 1
    assert m.away_goals == 4
    assert m.is_played is True
    assert m.round_label == "Matchday 1"
    assert m.competition == "ligue1"
    assert m.season == "2024_25"


def test_time_is_inherited_from_previous_match_on_same_date(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "inherit.txt",
        "▪ Matchday 1\n  Sun Aug 18\n"
        "    17:00  Montpellier HSC         v RC Strasbourg Alsace     1-1 (0-0)\n"
        "           Toulouse FC             v FC Nantes                0-0\n",
    )
    report = ofc._parse_file(path, "ligue1", "2024_25")
    assert len(report.matches) == 2
    assert report.matches[1].kickoff_local_naive.time() == report.matches[0].kickoff_local_naive.time()


# --------------------------------------------------------------------------
# 2. Ligne invalide / ambigue -> exclusion journalisee, jamais une erreur
#    fatale, jamais un match invente.
# --------------------------------------------------------------------------


def test_match_line_without_any_prior_time_is_preserved_with_no_kickoff_time(tmp_path: Path) -> None:
    """EXTENSION fixtures futures (docs/future_fixture_catalog_2026_27.md) :
    une ligne de match structurellement VALIDE (separateur, equipes, date
    etablie) mais sans heure publiee ne doit plus etre perdue - cas reel
    verifie (Coupe de France 2024/25, "Tours FC v FC Lorient [awarded]") -
    conservee comme ``OpenFootballMatch`` avec ``kickoff_local_naive=None``,
    jamais une heure devinee/heritee a tort, et jamais exclue silencieusement
    (``fixture_date``/equipes/score restent exploitables)."""
    path = _write(
        tmp_path,
        "no_time.txt",
        "▪ Round 1\n  Sat Dec 21\n           Tours FC                v FC Lorient               0-3    [awarded]\n",
    )
    report = ofc._parse_file(path, "coupe_de_france", "2024_25")
    assert report.exclusions == ()
    assert len(report.matches) == 1
    m = report.matches[0]
    assert m.kickoff_local_naive is None
    assert m.fixture_date == date(2024, 12, 21)
    assert m.home_team == "Tours FC"
    assert m.away_team == "FC Lorient"
    # Score "[awarded]" reste traite comme avant (buts None, awarded=True,
    # is_played=True) - ce changement ne touche QUE la gestion de l'heure.
    assert m.is_played is True
    assert m.awarded is True
    assert m.home_goals is None
    assert m.away_goals is None


def test_match_line_with_an_invalid_time_string_remains_a_genuine_exclusion(tmp_path: Path) -> None:
    """Distinction explicite demandee : une heure PRESENTE mais invalide
    (ex. "25:99") est une ligne reellement malformee, jamais convertie en
    match a heure inconnue - contrairement au cas ci-dessus ou l'heure est
    simplement ABSENTE."""
    path = _write(
        tmp_path,
        "bad_time.txt",
        "▪ Round 1\n  Sat Dec 21\n    25:99  Tours FC                v FC Lorient               0-3\n",
    )
    report = ofc._parse_file(path, "coupe_de_france", "2024_25")
    assert report.matches == ()
    assert len(report.exclusions) == 1
    assert "heure invalide" in report.exclusions[0].reason


def test_line_without_v_separator_is_silently_skipped_not_logged(tmp_path: Path) -> None:
    """Une ligne de buteur (ex. detail d'un match) ne contient jamais le
    separateur ' v ' - elle n'est pas une tentative de match et ne doit
    donc PAS polluer la liste d'exclusions."""
    path = _write(
        tmp_path,
        "scorer.txt",
        "▪ Matchday 1\n  Fri Aug 16 2024\n"
        "    20:45  Le Havre AC             v Paris Saint-Germain FC   1-4 (0-1)\n"
        "            (Neymar 71'; Diego 56')\n",
    )
    report = ofc._parse_file(path, "ligue1", "2024_25")
    assert len(report.matches) == 1
    assert report.exclusions == ()


def test_match_line_before_any_date_is_excluded(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "no_date.txt",
        "▪ Matchday 1\n    20:45  Le Havre AC             v Paris Saint-Germain FC   1-4 (0-1)\n",
    )
    report = ofc._parse_file(path, "ligue1", "2024_25")
    assert report.matches == ()
    assert len(report.exclusions) == 1
    assert "date courante" in report.exclusions[0].reason


def test_match_line_with_empty_team_name_after_country_code_split_is_excluded(tmp_path: Path) -> None:
    """Nom d'equipe reduit a vide une fois le code pays entre parentheses
    extrait (``_split_team_country``) - cas degenere jamais observe
    reellement, mais que le parseur doit refuser explicitement plutot que
    de produire un match a equipe vide."""
    path = _write(
        tmp_path,
        "empty_team.txt",
        "▪ League, Matchday 1\n  Tue Sep 17 2024\n    20:45  (SUI)                   v Aston Villa FC (ENG)     0-3 (0-2)\n",
    )
    report = ofc._parse_file(path, "champions_league", "2024_25")
    assert report.matches == ()
    assert len(report.exclusions) == 1
    assert "vide" in report.exclusions[0].reason


# --------------------------------------------------------------------------
# 3. Dates : rollover d'annee (avec restitution explicite ET filet de
#    securite sans restitution), et date hors de la plage declaree.
# --------------------------------------------------------------------------


def test_year_rollover_uses_explicit_year_when_source_restates_it(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "rollover_explicit.txt",
        "▪ Matchday 20\n  Wed Dec 18 2024\n    20:45  Le Havre AC             v Paris Saint-Germain FC   1-4 (0-1)\n"
        "▪ Matchday 21\n  Fri Jan 3 2025\n    20:45  Paris Saint-Germain FC  v Le Havre AC              2-0 (1-0)\n",
    )
    report = ofc._parse_file(path, "ligue1", "2024_25")
    assert report.exclusions == ()
    assert report.matches[1].kickoff_local_naive == datetime(2025, 1, 3, 20, 45)


def test_year_rollover_fallback_without_explicit_restatement(tmp_path: Path) -> None:
    """Filet de securite : si une source ne restituait jamais l'annee au
    changement (jamais observe reellement, mais pas suppose impossible),
    le mois qui redescend declenche quand meme le bon passage d'annee."""
    path = _write(
        tmp_path,
        "rollover_fallback.txt",
        "▪ Matchday 20\n  Wed Dec 18 2024\n    20:45  Le Havre AC             v Paris Saint-Germain FC   1-4 (0-1)\n"
        "▪ Matchday 21\n  Fri Jan 3\n    20:45  Paris Saint-Germain FC  v Le Havre AC              2-0 (1-0)\n",
    )
    report = ofc._parse_file(path, "ligue1", "2024_25")
    assert report.exclusions == ()
    assert report.matches[1].kickoff_local_naive == datetime(2025, 1, 3, 20, 45)


def test_date_outside_declared_header_range_is_excluded(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "out_of_range.txt",
        "▪ Matchday 1\n  Mon Jun 1 2026\n    20:45  Le Havre AC             v Paris Saint-Germain FC   1-4 (0-1)\n",
    )
    report = ofc._parse_file(path, "ligue1", "2024_25")
    assert report.matches == ()
    # Deux exclusions attendues, jamais une seule : la ligne de date
    # hors-plage ET la ligne de match orpheline qui en decoule (plus de
    # date courante valide) sont toutes deux journalisees explicitement -
    # jamais l'une masquant silencieusement l'autre.
    assert len(report.exclusions) == 2
    assert "hors de la plage" in report.exclusions[0].reason
    assert "date courante" in report.exclusions[1].reason


# --------------------------------------------------------------------------
# 4. Equipes (avec/sans code pays)
# --------------------------------------------------------------------------


def test_uefa_country_code_suffix_is_split_from_team_name(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "uefa.txt",
        "▪ League, Matchday 1\n  Tue Sep 17 2024\n"
        "    18:45  BSC Young Boys (SUI)    v Aston Villa FC (ENG)     0-3 (0-2)\n",
    )
    report = ofc._parse_file(path, "champions_league", "2024_25")
    m = report.matches[0]
    assert m.home_team == "BSC Young Boys"
    assert m.home_country_code == "SUI"
    assert m.away_team == "Aston Villa FC"
    assert m.away_country_code == "ENG"


def test_team_without_country_code_has_none_code(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "no_code.txt",
        "▪ Matchday 1\n  Fri Aug 16 2024\n    20:45  Le Havre AC             v Paris Saint-Germain FC   1-4 (0-1)\n",
    )
    report = ofc._parse_file(path, "ligue1", "2024_25")
    assert report.matches[0].home_country_code is None


# --------------------------------------------------------------------------
# 5. Score : simple, avec qualificatif (pen./a.e.t.), [awarded], et
#    match pas encore joue (pas de score du tout).
# --------------------------------------------------------------------------


def test_simple_score_extracts_goals(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "simple_score.txt",
        "▪ Matchday 1\n  Fri Aug 16 2024\n    20:45  Le Havre AC             v Paris Saint-Germain FC   1-4 (0-1)\n",
    )
    m = ofc._parse_file(path, "ligue1", "2024_25").matches[0]
    assert (m.home_goals, m.away_goals) == (1, 4)
    assert m.awarded is False


def test_penalty_shootout_score_never_guesses_goals(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "pen.txt",
        "▪ Round 7\n  Sun Nov 10 2024\n    17:30  Jeunesse Evolution      v CS Moulien               7-6 pen. (0-0)\n",
    )
    m = ofc._parse_file(path, "coupe_de_france", "2024_25").matches[0]
    assert (m.home_goals, m.away_goals) == (None, None)
    assert m.is_played is True
    assert "pen." in m.score_raw


def test_awarded_match_never_guesses_goals_and_is_flagged(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "awarded.txt",
        "▪ Round 7\n  Sun Nov 10 2024\n    17:30  Etoile Maritime         v USSA Vertou              0-3    [awarded]\n",
    )
    m = ofc._parse_file(path, "coupe_de_france", "2024_25").matches[0]
    assert m.awarded is True
    assert (m.home_goals, m.away_goals) == (None, None)


def test_match_without_any_score_is_marked_not_played(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "future.txt",
        "▪ Matchday 1\n  Fri Aug 16 2024\n    20:45  Le Havre AC             v Paris Saint-Germain FC\n",
    )
    m = ofc._parse_file(path, "ligue1", "2024_25").matches[0]
    assert m.is_played is False
    assert (m.home_goals, m.away_goals) == (None, None)


# --------------------------------------------------------------------------
# 6/7. Competition / saison correctement attachees ; fichier absent.
# --------------------------------------------------------------------------


def test_competition_and_season_are_attached_to_every_match(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "attach.txt",
        "▪ Matchday 1\n  Fri Aug 16 2024\n    20:45  Le Havre AC             v Paris Saint-Germain FC   1-4 (0-1)\n",
    )
    m = ofc._parse_file(path, "ligue1", "2024_25").matches[0]
    assert m.competition == "ligue1"
    assert m.season == "2024_25"


def test_missing_file_raises_explicit_error(tmp_path: Path) -> None:
    with pytest.raises(ofc.OpenFootballCalendarError, match="introuvable"):
        ofc._parse_file(tmp_path / "does_not_exist.txt", "ligue1", "2024_25")


def test_unregistered_competition_raises_explicit_error() -> None:
    with pytest.raises(ofc.OpenFootballCalendarError, match="inconnue"):
        ofc.load_competition("2024_25", "not_a_real_competition")


def test_unregistered_season_raises_explicit_error() -> None:
    with pytest.raises(ofc.OpenFootballCalendarError, match="inconnue"):
        ofc.load_competition("2099_00", "ligue1")


# --------------------------------------------------------------------------
# 8. Mapping explicite, AUCUN fuzzy matching.
# --------------------------------------------------------------------------


def test_build_team_calendar_uses_exact_name_match_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "psg.txt",
        "▪ Matchday 1\n  Fri Aug 16 2024\n    20:45  Le Havre AC             v Paris Saint-Germain FC   1-4 (0-1)\n",
    )
    monkeypatch.setitem(ofc._SOURCE_FILES, "2024_25", {**ofc._SOURCE_FILES["2024_25"], "ligue1": path})

    entries, skipped = ofc.build_team_calendar("2024_25", {"ligue1": "Paris Saint-Germain FC"})
    assert len(entries) == 1
    assert entries[0].opponent == "Le Havre AC"
    assert entries[0].is_home is False
    assert skipped == ()


def test_build_team_calendar_finds_nothing_for_a_near_miss_name_no_fuzzy_matching(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Preuve explicite d'absence de fuzzy matching : un nom de club
    legerement different (sans tiret) ne doit JAMAIS etre associe au
    'Paris Saint-Germain FC' reellement present dans le fichier."""
    path = _write(
        tmp_path,
        "psg2.txt",
        "▪ Matchday 1\n  Fri Aug 16 2024\n    20:45  Le Havre AC             v Paris Saint-Germain FC   1-4 (0-1)\n",
    )
    monkeypatch.setitem(ofc._SOURCE_FILES, "2024_25", {**ofc._SOURCE_FILES["2024_25"], "ligue1": path})

    entries, skipped = ofc.build_team_calendar("2024_25", {"ligue1": "Paris Saint Germain"})
    assert entries == ()
    assert skipped == ()  # la competition existe bien ; c'est juste 0 match pour ce nom exact


def test_build_team_calendar_skips_and_logs_unregistered_competition() -> None:
    entries, skipped = ofc.build_team_calendar("2024_25", {"coupe_de_la_lune": "Paris Saint-Germain FC"})
    assert entries == ()
    assert len(skipped) == 1
    assert skipped[0].competition == "coupe_de_la_lune"
    assert "non enregistree" in skipped[0].reason


def test_build_team_calendar_skips_and_logs_missing_file_on_disk(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing = tmp_path / "ghost.txt"
    monkeypatch.setitem(ofc._SOURCE_FILES, "2024_25", {**ofc._SOURCE_FILES["2024_25"], "ligue1": missing})
    entries, skipped = ofc.build_team_calendar("2024_25", {"ligue1": "Paris Saint-Germain FC"})
    assert entries == ()
    assert len(skipped) == 1
    assert "absent sur disque" in skipped[0].reason


# --------------------------------------------------------------------------
# congestion_preview : meme garde-fou PIT que fixture_congestion (jamais
# le match cible lui-meme, jamais un match posterieur).
# --------------------------------------------------------------------------


def test_congestion_preview_ignores_matches_on_or_after_the_target() -> None:
    entries = (
        ofc.TeamCalendarEntry(
            "ligue1", datetime(2024, 8, 16, 20, 45), "Le Havre AC", True, True,
            ofc.OpenFootballMatch("ligue1", "2024_25", None, date(2024, 8, 16), datetime(2024, 8, 16, 20, 45), "PSG", "Le Havre AC",
                                   None, None, True, 4, 1, "4-1", False, "x", 1),
        ),
        ofc.TeamCalendarEntry(
            "ligue1", datetime(2024, 8, 23, 20, 45), "Montpellier HSC", True, True,
            ofc.OpenFootballMatch("ligue1", "2024_25", None, date(2024, 8, 23), datetime(2024, 8, 23, 20, 45), "PSG", "Montpellier HSC",
                                   None, None, True, 6, 0, "6-0", False, "x", 2),
        ),
    )
    preview = ofc.congestion_preview(entries, as_of=datetime(2024, 8, 23, 20, 45))
    assert preview.rest_days == pytest.approx(7.0)
    # Convention assumee et testee : "derniers N jours" = intervalle
    # STRICTEMENT inferieur a N jours (une difference de EXACTEMENT 7.0
    # jours n'entre donc pas dans la fenetre des 7 derniers jours, mais
    # bien dans celle des 14 derniers) - jamais une borne ambigue.
    assert preview.matches_last_7d == 0
    assert preview.matches_last_14d == 1


def test_congestion_preview_7d_window_includes_a_match_six_days_before() -> None:
    entries = (
        ofc.TeamCalendarEntry(
            "ligue1", datetime(2024, 8, 17, 20, 45), "Le Havre AC", True, True,
            ofc.OpenFootballMatch("ligue1", "2024_25", None, date(2024, 8, 17), datetime(2024, 8, 17, 20, 45), "PSG", "Le Havre AC",
                                   None, None, True, 4, 1, "4-1", False, "x", 1),
        ),
    )
    preview = ofc.congestion_preview(entries, as_of=datetime(2024, 8, 23, 20, 45))
    assert preview.matches_last_7d == 1


def test_congestion_preview_is_none_when_no_prior_match() -> None:
    preview = ofc.congestion_preview((), as_of=datetime(2024, 8, 16, 20, 45))
    assert preview.rest_days is None
    assert preview.matches_last_7d == 0


# --------------------------------------------------------------------------
# En-tete : bornes avec/sans annee explicite de chaque cote.
# --------------------------------------------------------------------------


def test_header_range_with_year_only_on_end_side() -> None:
    start, end = ofc._parse_header_range("Tue Jul 9", "Wed Aug 28 2024", "x.txt")
    assert start == date(2024, 7, 9)
    assert end == date(2024, 8, 28)


def test_header_range_without_any_year_raises() -> None:
    with pytest.raises(ofc.OpenFootballCalendarError, match="annee"):
        ofc._parse_header_range("Tue Jul 9", "Wed Aug 28", "x.txt")
