"""Table de correspondance EXPLICITE et DETERMINISTE des noms d'equipe
Football-Data.co.uk <-> Understat (etape 1, phase economique -
docs/decisions/0006-football-data-point-in-time.md).

Construite A LA MAIN par verification directe des listes completes
d'equipes des deux sources (union des saisons 2024/25 et 2025/26, trois
championnats), PAS par fuzzy matching : chaque entree ci-dessous a ete
verifiee individuellement contre les fichiers reels
(research/market_odds/football_data/runs/, research/xg_feasibility/runs/).
Toute equipe absente de ces tables leve une erreur explicite plutot que
d'etre associee de facon approximative.
"""

from __future__ import annotations

FOOTBALL_DATA_TO_UNDERSTAT: dict[str, dict[str, str]] = {
    "premier_league": {
        "Arsenal": "Arsenal",
        "Aston Villa": "Aston Villa",
        "Bournemouth": "Bournemouth",
        "Brentford": "Brentford",
        "Brighton": "Brighton",
        "Burnley": "Burnley",
        "Chelsea": "Chelsea",
        "Crystal Palace": "Crystal Palace",
        "Everton": "Everton",
        "Fulham": "Fulham",
        "Ipswich": "Ipswich",
        "Leeds": "Leeds",
        "Leicester": "Leicester",
        "Liverpool": "Liverpool",
        "Man City": "Manchester City",
        "Man United": "Manchester United",
        "Newcastle": "Newcastle United",
        "Nott'm Forest": "Nottingham Forest",
        "Southampton": "Southampton",
        "Sunderland": "Sunderland",
        "Tottenham": "Tottenham",
        "West Ham": "West Ham",
        "Wolves": "Wolverhampton Wanderers",
    },
    "ligue1": {
        "Angers": "Angers",
        "Auxerre": "Auxerre",
        "Brest": "Brest",
        "Le Havre": "Le Havre",
        "Lens": "Lens",
        "Lille": "Lille",
        "Lorient": "Lorient",
        "Lyon": "Lyon",
        "Marseille": "Marseille",
        "Metz": "Metz",
        "Monaco": "Monaco",
        "Montpellier": "Montpellier",
        "Nantes": "Nantes",
        "Nice": "Nice",
        "Paris FC": "Paris FC",
        "Paris SG": "Paris Saint Germain",
        "Reims": "Reims",
        "Rennes": "Rennes",
        "St Etienne": "Saint-Etienne",
        "Strasbourg": "Strasbourg",
        "Toulouse": "Toulouse",
    },
    "liga": {
        "Alaves": "Alaves",
        "Ath Bilbao": "Athletic Club",
        "Ath Madrid": "Atletico Madrid",
        "Barcelona": "Barcelona",
        "Betis": "Real Betis",
        "Celta": "Celta Vigo",
        "Elche": "Elche",
        "Espanol": "Espanyol",
        "Getafe": "Getafe",
        "Girona": "Girona",
        "Las Palmas": "Las Palmas",
        "Leganes": "Leganes",
        "Levante": "Levante",
        "Mallorca": "Mallorca",
        "Osasuna": "Osasuna",
        "Oviedo": "Real Oviedo",
        "Real Madrid": "Real Madrid",
        "Sevilla": "Sevilla",
        "Sociedad": "Real Sociedad",
        "Valencia": "Valencia",
        "Valladolid": "Real Valladolid",
        "Vallecano": "Rayo Vallecano",
        "Villarreal": "Villarreal",
    },
}


def resolve_understat_name(league: str, football_data_name: str) -> str:
    """Traduit un nom d'equipe Football-Data vers son equivalent Understat.
    Leve explicitement si le championnat ou l'equipe est inconnu du
    mapping - jamais de correspondance approximative silencieuse."""
    try:
        table = FOOTBALL_DATA_TO_UNDERSTAT[league]
    except KeyError:
        raise KeyError(f"Championnat inconnu du mapping d'equipes : {league!r}.") from None
    try:
        return table[football_data_name]
    except KeyError:
        raise KeyError(
            f"Equipe Football-Data non resolue pour {league!r} : {football_data_name!r}. "
            "Aucun fuzzy matching - ajouter l'entree explicitement au mapping."
        ) from None


def validate_mapping_bijective(league: str, expected_understat_teams: set[str]) -> None:
    """Verifie qu'un mapping est bijectif par rapport a un ensemble
    d'equipes Understat attendu : aucune collision (deux entrees
    Football-Data associees a la meme equipe Understat), aucune equipe
    Understat pertinente non couverte, aucune equipe surnumeraire visee."""
    try:
        table = FOOTBALL_DATA_TO_UNDERSTAT[league]
    except KeyError:
        raise KeyError(f"Championnat inconnu du mapping d'equipes : {league!r}.") from None

    targets = list(table.values())
    if len(set(targets)) != len(targets):
        seen: set[str] = set()
        dupes: set[str] = set()
        for t in targets:
            if t in seen:
                dupes.add(t)
            seen.add(t)
        raise ValueError(f"Collision(s) dans le mapping {league!r} : cible(s) dupliquee(s) {sorted(dupes)}.")

    missing = expected_understat_teams - set(targets)
    if missing:
        raise ValueError(f"Equipes Understat non couvertes par le mapping {league!r} : {sorted(missing)}.")

    extra = set(targets) - expected_understat_teams
    if extra:
        raise ValueError(f"Le mapping {league!r} cible des equipes Understat inattendues : {sorted(extra)}.")
