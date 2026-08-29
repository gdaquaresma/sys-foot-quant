"""Garde-fous point-in-time et d'integrite pour l'infrastructure de cotes
reelles Football-Data (etape 8, phase economique -
docs/decisions/0006-football-data-point-in-time.md).

Couvre : absence d'utilisation du resultat futur pour determiner une cote,
`knowledge_time` toujours strictement anterieure au coup d'envoi,
provenance correcte, non-regression de la normalisation temporelle et de
l'appariement sur le corpus REEL deja recupere (6 fichiers Football-Data +
6 fichiers Understat, tous commit dans le depot)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.data_engine.market_odds.football_data_loader import (
    load_football_data_csv,
)
from sys_foot_quant.data_engine.market_odds.matching import (
    build_understat_keys,
    match_league_season,
)
from sys_foot_quant.data_engine.market_odds.time_resolution import (
    AmbiguousCollectionWindowError,
    conservative_knowledge_time_utc,
    football_data_kickoff_to_utc,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_FD_DIR = _REPO_ROOT / "research" / "market_odds" / "football_data" / "runs"
_US_DIR = _REPO_ROOT / "research" / "xg_feasibility" / "runs"

_DATASETS = {
    ("premier_league", "2024_25"): ("E0_2024_25.csv", "epl_2024_datesData.json"),
    ("premier_league", "2025_26"): ("E0_2025_26.csv", "epl_2025_datesData.json"),
    ("ligue1", "2024_25"): ("F1_2024_25.csv", "ligue1_2024_datesData.json"),
    ("ligue1", "2025_26"): ("F1_2025_26.csv", "ligue1_2025_datesData.json"),
    ("liga", "2024_25"): ("SP1_2024_25.csv", "liga_2024_datesData.json"),
    ("liga", "2025_26"): ("SP1_2025_26.csv", "liga_2025_datesData.json"),
}

_EXPECTED_MATCHES = {"premier_league": 380, "ligue1": 306, "liga": 380}


def test_football_data_record_odds_are_independent_of_match_result(tmp_path: Path) -> None:
    """Deux matchs avec les memes cotes mais des scores differents doivent
    produire des cotes identiques - la cote n'est jamais derivee du
    resultat (aucune fuite du futur vers la donnee de marche)."""
    header = (
        "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,B365H,B365D,B365A,BWH,BWD,BWA,PSH,PSD,PSA,"
        "B365CH,B365CD,B365CA,BWCH,BWCD,BWCA,PSCH,PSCD,PSCA,"
        "B365>2.5,B365<2.5,P>2.5,P<2.5,B365C>2.5,B365C<2.5,PC>2.5,PC<2.5,HST,AST\n"
    )
    rows = (
        "E0,16/08/2024,20:00,A,B,5,0,H,1.6,4.2,5.25,1.65,4.1,5.3,1.63,4.15,5.2,"
        "1.66,4.15,5.33,1.68,4.1,5.4,1.64,4.2,5.25,1.85,1.95,1.80,1.90,1.88,1.92,1.82,1.87,7,2\n"
        "E0,17/08/2024,15:00,C,D,0,0,D,1.6,4.2,5.25,1.65,4.1,5.3,1.63,4.15,5.2,"
        "1.66,4.15,5.33,1.68,4.1,5.4,1.64,4.2,5.25,1.85,1.95,1.80,1.90,1.88,1.92,1.82,1.87,7,2\n"
    )
    path = tmp_path / "E0.csv"
    path.write_text(header + rows)
    records = load_football_data_csv(path, league="premier_league", season="2024_25")
    assert records[0].b365_home == records[1].b365_home
    assert records[0].b365_draw == records[1].b365_draw
    assert records[0].b365_away == records[1].b365_away
    assert records[0].b365_over_2_5 == records[1].b365_over_2_5
    assert records[0].b365_under_2_5 == records[1].b365_under_2_5
    assert records[0].b365_close_home == records[1].b365_close_home  # la cloture non plus n'est jamais derivee du resultat
    assert records[0].b365_close_over_2_5 == records[1].b365_close_over_2_5
    assert records[0].home_goals != records[1].home_goals  # les scores, eux, different bien


@given(
    year=st.integers(2024, 2026),
    month=st.integers(1, 12),
    day=st.integers(1, 28),
    hour=st.integers(0, 23),
)
@settings(max_examples=100)
def test_conservative_knowledge_time_always_strictly_before_kickoff(year, month, day, hour) -> None:
    kickoff = datetime(year, month, day, hour, 0, tzinfo=timezone.utc)
    try:
        knowledge = conservative_knowledge_time_utc(kickoff)
    except AmbiguousCollectionWindowError:
        return  # vendredi/lundi : correctement refuse, rien a verifier de plus
    assert knowledge < kickoff


def test_provenance_fields_are_always_set_correctly(tmp_path: Path) -> None:
    header = (
        "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,B365H,B365D,B365A,BWH,BWD,BWA,PSH,PSD,PSA,"
        "B365CH,B365CD,B365CA,BWCH,BWCD,BWCA,PSCH,PSCD,PSCA,"
        "B365>2.5,B365<2.5,P>2.5,P<2.5,B365C>2.5,B365C<2.5,PC>2.5,PC<2.5,HST,AST\n"
    )
    path = tmp_path / "E0.csv"
    path.write_text(
        header
        + "E0,16/08/2024,20:00,A,B,1,0,H,1.6,4.2,5.25,1.65,4.1,5.3,1.63,4.15,5.2,"
        + "1.66,4.15,5.33,1.68,4.1,5.4,1.64,4.2,5.25,1.85,1.95,1.80,1.90,1.88,1.92,1.82,1.87,5,3\n"
    )
    records = load_football_data_csv(path, league="premier_league", season="2024_25")
    r = records[0]
    assert r.source == "football_data"
    assert r.bookmaker == "B365"
    assert r.market == "1x2"
    assert r.league == "premier_league"
    assert r.season == "2024_25"


# Residu documente et root-cause (etape 3) : 9 matchs sur 2132 (0.42%) ne
# s'apparient pas via la cle (equipe mappee, date). Verification manuelle :
# dans les 9 cas, l'equipe et le match existent bien des deux cotes, mais
# Understat et Football-Data leur attribuent une DATE differente (ecart
# d'un a deux jours calendaires, pas un simple decalage horaire) - probable
# reprogrammation TV enregistree differemment par les deux sources
# independantes. Ce n'est ni un defaut du mapping d'equipes, ni un bug de
# la cle d'appariement : verifie explicitement en inspectant chaque cas
# individuellement avant d'accepter ce residu (aucune resolution par
# fuzzy-matching sur une fenetre de dates, conformement a la consigne).
_EXPECTED_UNMATCHED_UNDERSTAT = frozenset(
    {
        ("ligue1", "2025_26", "Brest", "Lorient", "2026-02-08"),
        ("ligue1", "2025_26", "Lens", "Rennes", "2026-02-08"),
        ("ligue1", "2025_26", "Metz", "Lille", "2026-02-08"),
        ("ligue1", "2025_26", "Nantes", "Lyon", "2026-02-08"),
        ("ligue1", "2025_26", "Metz", "Monaco", "2026-05-03"),
        ("ligue1", "2025_26", "Nantes", "Marseille", "2026-05-03"),
        ("ligue1", "2025_26", "Nice", "Lens", "2026-05-03"),
        ("ligue1", "2025_26", "Paris Saint Germain", "Lorient", "2026-05-03"),
        ("liga", "2025_26", "Valencia", "Real Oviedo", "2025-09-29"),
    }
)


@pytest.mark.skipif(not _FD_DIR.exists(), reason="Fichiers Football-Data reels non presents.")
def test_real_corpus_integrity_and_matching_non_regression() -> None:
    """Non-regression EXACTE (pas un seuil approximatif) sur le corpus REEL
    deja recupere : le residu non apparie doit rester EXACTEMENT le
    residu deja identifie et explique (ecarts de date entre sources,
    documentes ci-dessus) - toute nouvelle non-correspondance imprevue
    fait echouer ce test plutot que d'etre absorbee silencieusement par
    un seuil."""
    total_matched = 0
    total_understat = 0
    all_unmatched_understat: set[tuple] = set()
    for (league, season), (fd_name, us_name) in _DATASETS.items():
        fd_records = load_football_data_csv(_FD_DIR / fd_name, league=league, season=season)
        assert len(fd_records) == _EXPECTED_MATCHES[league]

        with open(_US_DIR / us_name) as f:
            us_raw = json.load(f)
        us_keys = build_understat_keys(us_raw, league=league, season=season)
        assert len(us_keys) == _EXPECTED_MATCHES[league]

        report = match_league_season(us_keys, fd_records, league, season)
        assert report.n_duplicate_keys_understat == 0
        assert report.n_duplicate_keys_football_data == 0
        all_unmatched_understat.update(report.unmatched_understat)
        total_matched += report.n_matched
        total_understat += report.n_understat

    assert total_understat == 2132
    assert total_matched == 2123
    assert all_unmatched_understat == set(_EXPECTED_UNMATCHED_UNDERSTAT)


@pytest.mark.skipif(not _FD_DIR.exists(), reason="Fichiers Football-Data reels non presents.")
def test_real_corpus_normalized_kickoff_times_agree_after_timezone_correction() -> None:
    """Test de non-regression explicitement demande (etape 2) : apres
    normalisation Europe/London -> UTC, les matchs apparies doivent avoir
    le meme coup d'envoi (a la minute pres) dans l'immense majorite des
    cas - la encore un seuil, pas une egalite parfaite (quelques matchs
    reprogrammes par la TV restent un residu documente, jamais masque)."""
    agree = 0
    total = 0
    for (league, season), (fd_name, us_name) in _DATASETS.items():
        fd_records = load_football_data_csv(_FD_DIR / fd_name, league=league, season=season)
        with open(_US_DIR / us_name) as f:
            us_raw = json.load(f)
        us_keys = build_understat_keys(us_raw, league=league, season=season)
        report = match_league_season(us_keys, fd_records, league, season)

        for m in report.matched:
            fd_kickoff_utc = football_data_kickoff_to_utc(m.football_data.date_str, m.football_data.time_str)
            total += 1
            if fd_kickoff_utc == m.understat.kickoff_utc:
                agree += 1

    assert total > 2000
    agreement_rate = agree / total
    assert agreement_rate >= 0.95, f"Taux d'accord des coups d'envoi normalises : {agreement_rate:.3f}"
