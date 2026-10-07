"""Test d'integration sur les fichiers OpenFootball REELS 2024/25
(research/fixture_calendar/openfootball/runs/) - verifie la couverture
obtenue sur le corpus reel, pas seulement des fixtures synthetiques.
Documente aussi le resultat (docs/openfootball_calendar_validation_report.md).

Si les fichiers venaient a etre deplaces/supprimes du depot, ces tests
echoueraient explicitement (jamais un skip silencieux - meme discipline
que les tests de non-regression football_data_loader)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from sys_foot_quant.data_engine.market_odds import openfootball_calendar as ofc

_RUNS_DIR = Path("research/fixture_calendar/openfootball/runs")


@pytest.mark.parametrize("competition", ofc.available_competitions("2024_25"))
def test_real_file_exists_on_disk(competition: str) -> None:
    assert ofc._SOURCE_FILES["2024_25"][competition].exists(), (
        f"Fichier manquant pour {competition!r} - ce test d'integration exige les fichiers "
        f"reels telecharges dans {_RUNS_DIR} (voir docs/openfootball_calendar.md)."
    )


@pytest.mark.parametrize("competition", ofc.available_competitions("2024_25"))
def test_parsed_match_count_matches_the_source_declared_count_within_tolerance(competition: str) -> None:
    """Le nombre de matchs reellement parses doit etre tres proche du
    nombre declare par l'en-tete '# Matches N' du fichier source - un
    ecart serait le signe d'une regression du parseur (ou d'une anomalie
    documentee du fichier source, comme le match sans heure de la Coupe
    de France - jamais plus d'une poignee d'ecart tolere)."""
    report = ofc.load_competition("2024_25", competition)
    text = report.source_file and Path(report.source_file).read_text(encoding="utf-8")
    declared_match = re.search(r"# Matches\s+(\d+)", text)
    assert declared_match is not None, f"En-tete '# Matches' introuvable dans {report.source_file}"
    declared = int(declared_match.group(1))
    assert len(report.matches) + len(report.exclusions) >= declared - 1
    assert declared - len(report.matches) <= 2, (
        f"{competition}: {declared - len(report.matches)} matchs manquants par rapport a l'en-tete "
        f"(exclusions: {[e.reason for e in report.exclusions]})"
    )


@pytest.mark.parametrize("competition", ofc.available_competitions("2024_25"))
def test_no_duplicate_matches_within_a_competition_file(competition: str) -> None:
    report = ofc.load_competition("2024_25", competition)
    keys = [(m.kickoff_local_naive, m.home_team, m.away_team) for m in report.matches]
    assert len(keys) == len(set(keys)), f"Doublon detecte dans {competition}"


@pytest.mark.parametrize(
    "season,competition",
    [(s, c) for s in ofc.SEASONS for c in ofc.available_competitions(s)],
)
def test_no_date_level_collision_even_without_kickoff_time(season: str, competition: str) -> None:
    """Analyse de risque demandee explicitement (EXTENSION fixtures
    futures) : (home_team, away_team, fixture_date) doit rester unique au
    sein d'un (competition, season), y COMPRIS pour les matchs sans heure
    (desormais conserves, voir OpenFootballMatch) - sinon le patron de
    match_id "competition:season:fixture_date:home_team:away_team" ne
    serait pas sur. Verifie sur TOUS les fichiers reels enregistres
    (2024/25 ET 2026/27), pas seulement un echantillon manuel."""
    report = ofc.load_competition(season, competition)
    keys = [(m.home_team, m.away_team, m.fixture_date) for m in report.matches]
    assert len(keys) == len(set(keys)), f"Collision (equipes, date) detectee dans {season}/{competition}"


@pytest.mark.parametrize("competition", ofc.available_competitions("2024_25"))
def test_all_matches_have_valid_dates_within_declared_header_range(competition: str) -> None:
    """``fixture_date`` (toujours present, EXTENSION fixtures futures) est
    utilise ici plutot que ``kickoff_local_naive.date()`` - ce dernier peut
    desormais etre ``None`` (match sans heure publiee, voir
    OpenFootballMatch). Quand une heure EST connue, les deux doivent
    rester coherents entre eux (verifie ci-dessous)."""
    report = ofc.load_competition("2024_25", competition)
    start, end = report.declared_range
    for m in report.matches:
        assert start <= m.fixture_date <= end
        if m.kickoff_local_naive is not None:
            assert m.kickoff_local_naive.date() == m.fixture_date


@pytest.mark.parametrize("competition", ofc.available_competitions("2024_25"))
def test_no_match_has_an_empty_team_name(competition: str) -> None:
    report = ofc.load_competition("2024_25", competition)
    for m in report.matches:
        assert m.home_team.strip() != ""
        assert m.away_team.strip() != ""
        assert m.home_team != m.away_team


@pytest.mark.parametrize("competition", ofc.available_competitions("2024_25"))
def test_every_match_is_tagged_with_the_requested_competition_and_season(competition: str) -> None:
    report = ofc.load_competition("2024_25", competition)
    for m in report.matches:
        assert m.competition == competition
        assert m.season == "2024_25"


def test_total_real_coverage_is_in_the_expected_order_of_magnitude() -> None:
    """Garde-fou global : ~2500-2600 matchs attendus sur les 13 fichiers
    2024/25 reellement telecharges (verifie manuellement lors de cette
    implementation - voir docs/openfootball_calendar_validation_report.md).
    Un ecart important signalerait un fichier source modifie/corrompu."""
    total = sum(len(ofc.load_competition("2024_25", c).matches) for c in ofc.available_competitions("2024_25"))
    assert 2400 <= total <= 2700


# --------------------------------------------------------------------------
# Reconstruction de calendrier pour quelques clubs francais reels
# (PSG, Marseille, Lyon, Lille, Monaco) - championnat + coupe + UEFA.
# --------------------------------------------------------------------------

# Mapping EXPLICITE, verifie a la main par grep direct sur les fichiers
# reels (jamais devine) - chaque club s'ecrit differemment selon le
# fichier source (meme discipline que team_mapping.py/elo_team_mapping.py).
_CLUB_NAMES_BY_COMPETITION = {
    # NB : le code pays entre parentheses (ex. "(FRA)") est deja retire
    # par le parseur dans un champ separe (``home_country_code``/
    # ``away_country_code``) - le nom a fournir ici est donc TOUJOURS la
    # forme SANS code pays, verifiee reellement via
    # ``{m.home_team for m in report.matches}`` sur le fichier reel,
    # jamais devinee a partir de la ligne brute.
    "Paris Saint-Germain": {
        "ligue1": "Paris Saint-Germain FC",
        "coupe_de_france": "Paris Saint-Germain",
        "champions_league": "Paris Saint-Germain FC",
    },
    "Olympique de Marseille": {
        "ligue1": "Olympique de Marseille",
        "coupe_de_france": "Olympique Marseille",
    },
    "Olympique Lyonnais": {
        "ligue1": "Olympique Lyonnais",
        "coupe_de_france": "Olympique Lyonnais",
        "europa_league": "Olympique Lyonnais",
    },
    "Lille OSC": {
        "ligue1": "Lille OSC",
        "coupe_de_france": "Lille OSC",
        "champions_league": "Lille OSC",
    },
    "AS Monaco": {
        "ligue1": "AS Monaco FC",
        "coupe_de_france": "AS Monaco",
        "champions_league": "AS Monaco FC",
    },
}


# Competitions REELLEMENT trouvees pour chaque club lors de cette
# implementation (voir docs/openfootball_calendar_validation_report.md) -
# assertion stricte (pas seulement ">= 2") pour qu'un mapping de nom
# silencieusement casse (ex. oubli du retrait du code pays) fasse
# immediatement echouer ce test plutot que de passer par accident sur le
# seul fait que championnat+coupe suffisent a depasser un seuil large.
_EXPECTED_COMPETITIONS = {
    "Paris Saint-Germain": {"ligue1", "coupe_de_france", "champions_league"},
    "Olympique de Marseille": {"ligue1", "coupe_de_france"},
    "Olympique Lyonnais": {"ligue1", "coupe_de_france", "europa_league"},
    "Lille OSC": {"ligue1", "coupe_de_france", "champions_league"},
    "AS Monaco": {"ligue1", "coupe_de_france", "champions_league"},
}


@pytest.mark.parametrize("club", sorted(_CLUB_NAMES_BY_COMPETITION))
def test_club_calendar_includes_matches_outside_the_league(club: str) -> None:
    """Verification manuelle demandee : les matchs hors championnat
    (coupe nationale et/ou UEFA) apparaissent bien dans le calendrier
    reconstruit, pas seulement les matchs de Ligue 1."""
    entries, skipped = ofc.build_team_calendar("2024_25", _CLUB_NAMES_BY_COMPETITION[club])
    competitions_seen = {e.competition for e in entries}
    assert competitions_seen == _EXPECTED_COMPETITIONS[club], (
        f"{club}: {competitions_seen} trouvee(s), {_EXPECTED_COMPETITIONS[club]} attendue(s) - "
        "verifier le mapping de noms (code pays residuel ? orthographe ?)."
    )
    # Chronologie strictement croissante (sortie deja triee par build_team_calendar).
    kickoffs = [e.kickoff_local_naive for e in entries]
    assert kickoffs == sorted(kickoffs)


def test_psg_calendar_has_no_unexpected_skips() -> None:
    entries, skipped = ofc.build_team_calendar("2024_25", _CLUB_NAMES_BY_COMPETITION["Paris Saint-Germain"])
    assert skipped == ()
    assert len(entries) > 30  # Ligue 1 (34 journees jouees sans compter les 4 restantes au moment du calcul) + coupe + C1
