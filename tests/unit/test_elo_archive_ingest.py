"""Tests de elo_archive_ingest.py (Phase K, option b) - reconstruction
de fenetres [From,To] propres a partir du journal brut de scrapes
quotidiens de l'archive GitHub tonyelhabr/club-rankings."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from sys_foot_quant.data_engine.market_odds.elo_archive_ingest import (
    ARCHIVE_NAME_TO_LIVE_NAME,
    ingest_daily_archive,
    load_daily_archive_rows,
)
from sys_foot_quant.data_engine.market_odds.elo_join import build_elo_dataset
from sys_foot_quant.data_engine.market_odds.football_data_loader import FootballDataMatchRecord

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_REAL_ARCHIVE = _REPO_ROOT / "research" / "market_odds" / "clubelo" / "runs" / "clubelo_daily_archive.csv"


def _raw_row(club, country, elo, frm, scrape_date, level="1"):
    return {"Rank": "1", "Club": club, "Country": country, "Level": level, "Elo": str(elo), "From": frm, "To": "9999-01-01", "date": scrape_date, "updated_at": f"{scrape_date} 12:00:00"}


def test_reconstructs_non_overlapping_windows_from_repeated_daily_scrapes() -> None:
    """Trois scrapes consecutifs du MEME From (window encore ouverte),
    puis un nouveau From (nouveau match) - doit produire exactement DEUX
    fenetres, jamais chevauchantes."""
    raw = [
        _raw_row("Barcelona", "ESP", 1900.0, "2024-08-01", "2024-08-01"),
        _raw_row("Barcelona", "ESP", 1900.0, "2024-08-01", "2024-08-02"),
        _raw_row("Barcelona", "ESP", 1900.0, "2024-08-01", "2024-08-03"),
        _raw_row("Barcelona", "ESP", 1920.0, "2024-08-04", "2024-08-04"),
        _raw_row("Barcelona", "ESP", 1920.0, "2024-08-04", "2024-08-05"),
    ]
    report = ingest_daily_archive(raw)
    windows = report.ratings_by_live_name["Barcelona"]
    assert len(windows) == 2
    w1, w2 = sorted(windows, key=lambda w: w.valid_from)
    assert w1.valid_from == date(2024, 8, 1)
    assert w1.valid_to == date(2024, 8, 3)  # jour avant le nouveau From, jamais la colonne To brute
    assert w1.elo == pytest.approx(1900.0)
    assert w2.valid_from == date(2024, 8, 4)
    assert w2.valid_to == date(2024, 8, 5)  # derniere date de scrape observee pour ce club
    assert w2.elo == pytest.approx(1920.0)


def test_uses_first_observed_value_never_a_later_revision() -> None:
    """Si l'archive montre, pour la MEME fenetre (meme From), une valeur
    differente selon le jour de scrape (raffinement retroactif du moteur
    ClubElo, phenomene mesure sur les donnees reelles), la valeur retenue
    doit etre la PREMIERE observee - jamais une revision posterieure."""
    raw = [
        _raw_row("Barcelona", "ESP", 1900.0, "2024-08-01", "2024-08-01"),  # premiere observation
        _raw_row("Barcelona", "ESP", 1915.0, "2024-08-01", "2024-08-10"),  # revision ulterieure, +15 points
    ]
    report = ingest_daily_archive(raw)
    windows = report.ratings_by_live_name["Barcelona"]
    assert len(windows) == 1
    assert windows[0].elo == pytest.approx(1900.0)  # jamais 1915.0


def test_conflict_is_counted_when_revision_exceeds_threshold() -> None:
    raw = [
        _raw_row("Barcelona", "ESP", 1900.0, "2024-08-01", "2024-08-01"),
        _raw_row("Barcelona", "ESP", 1915.0, "2024-08-01", "2024-08-10"),  # +15 points > seuil de 1.0
    ]
    report = ingest_daily_archive(raw)
    assert report.n_windows_with_conflict == 1
    assert report.n_windows_reconstructed == 1


def test_no_conflict_counted_for_negligible_floating_point_drift() -> None:
    raw = [
        _raw_row("Barcelona", "ESP", 1900.000, "2024-08-01", "2024-08-01"),
        _raw_row("Barcelona", "ESP", 1900.002, "2024-08-01", "2024-08-02"),  # bruit flottant negligeable
    ]
    report = ingest_daily_archive(raw)
    assert report.n_windows_with_conflict == 0


def test_archive_name_override_maps_to_live_site_name() -> None:
    """Bilbao/Atletico/Sociedad (noms de l'archive) doivent etre traduits
    vers les noms verifies sur le site en direct (Athletic Club/
    Atlético/Real Sociedad, elo_team_mapping.py) - jamais laisses tels
    quels, ce qui romprait la jointure avec le mapping deja verifie."""
    assert ARCHIVE_NAME_TO_LIVE_NAME == {
        "Bilbao": "Athletic Club",
        "Atletico": "Atlético",
        "Sociedad": "Real Sociedad",
    }
    raw = [_raw_row("Bilbao", "ESP", 1700.0, "2024-08-01", "2024-08-01")]
    report = ingest_daily_archive(raw)
    assert "Athletic Club" in report.ratings_by_live_name
    assert "Bilbao" not in report.ratings_by_live_name


def test_integration_with_elo_join_build_elo_dataset() -> None:
    """L'archive ingeree doit s'integrer SANS AUCUNE MODIFICATION dans
    build_elo_dataset (elo_join.py, deja teste) - verifie l'interface,
    pas une reimplementation."""
    raw = [
        _raw_row("Barcelona", "ESP", 1950.0, "2024-07-01", "2024-08-03"),
        _raw_row("Sevilla", "ESP", 1700.0, "2024-07-01", "2024-08-03"),
    ]
    report = ingest_daily_archive(raw)

    from datetime import datetime

    def _us(match_id, dt, home="Barcelona", away="Sevilla"):
        return {"id": match_id, "isResult": True, "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"), "h": {"id": 1, "title": home}, "a": {"id": 2, "title": away}}

    def _fd(date_dt, home="Barcelona", away="Sevilla", hg=2, ag=1):
        return FootballDataMatchRecord(
            league="liga", season="2024_25", source="football_data", bookmaker="B365", market="1x2",
            date_str=date_dt.strftime("%d/%m/%Y"), time_str=date_dt.strftime("%H:%M"),
            home_team_fd=home, away_team_fd=away, home_goals=hg, away_goals=ag,
            b365_home=1.8, b365_draw=3.6, b365_away=4.5,
        )

    t0 = datetime(2024, 8, 3, 20, 0, 0)  # samedi, dans la fenetre [2024-07-01, 2024-08-03] observee
    join_report = build_elo_dataset("liga", "2024_25", [_us("1", t0)], [_fd(t0)], report.ratings_by_live_name)
    assert join_report.n_exploitable == 1
    assert join_report.records[0].elo_diff == pytest.approx(250.0)


@pytest.mark.skipif(not _REAL_ARCHIVE.exists(), reason="Archive ClubElo reelle non presente.")
def test_real_archive_coverage_is_stable() -> None:
    """Non-regression large sur l'archive REELLE - jamais suppose,
    mesure a chaque execution. Chiffres verifies manuellement lors de
    l'audit (Phase K, option b)."""
    raw = load_daily_archive_rows(str(_REAL_ARCHIVE))
    report = ingest_daily_archive(raw)
    assert report.total_raw_rows == 61394
    assert report.n_clubs == 67
    assert report.earliest_date == date(2023, 3, 27)
    assert report.latest_date == date(2026, 1, 14)
    # aucune equipe manquante parmi les 67 attendues (elo_team_mapping.py)
    from sys_foot_quant.data_engine.market_odds.elo_team_mapping import FOOTBALL_DATA_TO_CLUBELO

    expected_live_names = {name for table in FOOTBALL_DATA_TO_CLUBELO.values() for name in table.values()}
    assert expected_live_names <= set(report.ratings_by_live_name.keys())
