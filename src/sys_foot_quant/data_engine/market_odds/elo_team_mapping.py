"""Table de correspondance Football-Data.co.uk <-> ClubElo (Phase K -
docs/elo_experiment_specification.md section 4). Analogue exact de
``team_mapping.py`` (Understat) : un dictionnaire EXPLICITE par
championnat, jamais de fuzzy matching, echec explicite si une equipe est
absente.

AVERTISSEMENT NON NEGOCIABLE (docs/elo_experiment_specification.md
section 0bis/4) : cet environnement d'execution ne peut pas atteindre
``clubelo.com``/``api.clubelo.com`` (bloque par la politique de sortie
reseau de la session). Le mapping ci-dessous est donc une EBAUCHE fondee
sur des conventions de nommage observees dans des wrappers communautaires
tiers (``soccerdata``, archives GitHub citees en Phase J/K) - il n'a PAS
ete verifie a la main contre la liste reelle des clubs presents dans des
fichiers ClubElo reellement obtenus, contrairement a l'exigence explicite
de la Phase K (« matching... verifie manuellement pour les cas
ambigus »). ``MAPPING_VERIFIED_AGAINST_REAL_DATA`` reste ``False`` tant
que cette verification manuelle n'a pas ete faite - ``resolve_clubelo_name``
refuse toute resolution non explicitement marquee comme test/audit tant
que ce drapeau n'est pas passe a ``True``."""

from __future__ import annotations

MAPPING_VERIFIED_AGAINST_REAL_DATA = False

FOOTBALL_DATA_TO_CLUBELO: dict[str, dict[str, str]] = {
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
        "Newcastle": "Newcastle",
        "Nott'm Forest": "Nottingham",
        "Southampton": "Southampton",
        "Sunderland": "Sunderland",
        "Tottenham": "Tottenham",
        "West Ham": "West Ham",
        "Wolves": "Wolverhampton",
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
        "Paris SG": "Paris SG",
        "Reims": "Reims",
        "Rennes": "Rennes",
        "St Etienne": "St Etienne",
        "Strasbourg": "Strasbourg",
        "Toulouse": "Toulouse",
    },
    "liga": {
        "Alaves": "Alaves",
        "Ath Bilbao": "Athletic",
        "Ath Madrid": "Atletico",
        "Barcelona": "Barcelona",
        "Betis": "Betis",
        "Celta": "Celta",
        "Elche": "Elche",
        "Espanol": "Espanyol",
        "Getafe": "Getafe",
        "Girona": "Girona",
        "Las Palmas": "Las Palmas",
        "Leganes": "Leganes",
        "Levante": "Levante",
        "Mallorca": "Mallorca",
        "Osasuna": "Osasuna",
        "Oviedo": "Oviedo",
        "Real Madrid": "Real Madrid",
        "Sevilla": "Sevilla",
        "Sociedad": "Sociedad",
        "Valencia": "Valencia",
        "Valladolid": "Valladolid",
        "Vallecano": "Rayo Vallecano",
        "Villarreal": "Villarreal",
    },
}


class EloMappingUnverifiedError(Exception):
    """Levee si une resolution est tentee sans que le mapping ait ete
    verifie a la main contre des donnees ClubElo reelles, et sans que
    l'appelant ne le demande explicitement (tests/audit uniquement,
    ``allow_unverified=True``)."""


def resolve_clubelo_name(league: str, football_data_name: str, *, allow_unverified: bool = False) -> str:
    """Traduit un nom d'equipe Football-Data vers son equivalent
    ClubElo. Leve ``EloMappingUnverifiedError`` si le mapping n'a jamais
    ete verifie contre des donnees reelles et que l'appelant ne l'a pas
    explicitement autorise (tests avec des donnees synthetiques
    uniquement) - bloque ainsi toute execution reelle par construction,
    pas seulement par consigne documentaire. Leve ``KeyError`` (jamais de
    correspondance approximative) si le championnat ou l'equipe est
    inconnu du mapping."""
    if not allow_unverified and not MAPPING_VERIFIED_AGAINST_REAL_DATA:
        raise EloMappingUnverifiedError(
            "Le mapping Football-Data -> ClubElo n'a jamais ete verifie a la main contre "
            "des donnees ClubElo reelles (docs/elo_experiment_specification.md section 4) - "
            "execution reelle bloquee tant que MAPPING_VERIFIED_AGAINST_REAL_DATA n'est pas "
            "mis a True apres verification manuelle contre les fichiers ClubElo reellement obtenus."
        )
    try:
        table = FOOTBALL_DATA_TO_CLUBELO[league]
    except KeyError:
        raise KeyError(f"Championnat inconnu du mapping ClubElo : {league!r}.") from None
    try:
        return table[football_data_name]
    except KeyError:
        raise KeyError(
            f"Equipe Football-Data non resolue vers ClubElo pour {league!r} : {football_data_name!r}. "
            "Aucun fuzzy matching - ajouter l'entree explicitement au mapping, apres verification manuelle."
        ) from None
