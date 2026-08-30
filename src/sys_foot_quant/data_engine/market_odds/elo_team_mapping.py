"""Table de correspondance Football-Data.co.uk <-> ClubElo (Phase K -
docs/elo_experiment_specification.md section 4). Analogue exact de
``team_mapping.py`` (Understat) : un dictionnaire EXPLICITE par
championnat, jamais de fuzzy matching, echec explicite si une equipe est
absente.

MAPPING VERIFIE A LA MAIN CONTRE LES DONNEES REELLES (Phase K, option b
de l'audit ClubElo) : cet environnement d'execution ne peut toujours pas
atteindre ``clubelo.com``/``api.clubelo.com`` directement (bloque par la
politique de sortie reseau de la session), mais l'utilisateur a consulte
directement les pages reelles ``clubelo.com/ENG``, ``clubelo.com/ESP`` et
``clubelo.com/FRA`` et en a transcrit le contenu integralement (captures
d'ecran et texte copie-colle, dates 2026-08-29/30) - chacune des 66
entrees ci-dessous a ete confrontee individuellement a cette liste reelle,
jamais devinee ni approximee. Trois corrections notables par rapport a
l'ebauche initiale (fondee sur des conventions de wrappers tiers, jamais
verifiee) : ``Man City`` -> ``Man City`` (pas ``Manchester City``),
``Man United`` -> ``Man United`` (pas ``Manchester United``),
``Nott'm Forest`` -> ``Forest`` (pas ``Nottingham``), ``St Etienne`` ->
``Saint-Etienne`` (pas ``St Etienne``), ``Ath Bilbao`` -> ``Athletic
Club`` (pas ``Athletic``), ``Ath Madrid`` -> ``Atlético`` (accent
present, pas ``Atletico``), ``Sociedad`` -> ``Real Sociedad`` (pas
``Sociedad`` seul). Les trois clubs initialement absents de la capture
Espagne (``Leganes``, ``Oviedo``, ``Valladolid``) ont ete retrouves via
une recherche Ctrl+F dediee sur la page reelle et confirmes presents,
sans aucune ambiguite silencieuse.

``MAPPING_VERIFIED_AGAINST_REAL_DATA`` est desormais ``True``. La donnee
ainsi confirmee est le rating ACTUEL (jour de consultation) et le nom
exact du club - elle ne constitue PAS, a elle seule, une preuve de la
couverture historique (fenetres ``[From,To]`` 2024-2026) necessaire a
l'experience : celle-ci reste a obtenir (fichiers CSV d'historique par
club, section 0bis/3 du protocole) avant toute execution reelle."""

from __future__ import annotations

MAPPING_VERIFIED_AGAINST_REAL_DATA = True

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
        "Man City": "Man City",
        "Man United": "Man United",
        "Newcastle": "Newcastle",
        "Nott'm Forest": "Forest",
        "Southampton": "Southampton",
        "Sunderland": "Sunderland",
        "Tottenham": "Tottenham",
        "West Ham": "West Ham",
        "Wolves": "Wolves",
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
        "St Etienne": "Saint-Etienne",
        "Strasbourg": "Strasbourg",
        "Toulouse": "Toulouse",
    },
    "liga": {
        "Alaves": "Alaves",
        "Ath Bilbao": "Athletic Club",
        "Ath Madrid": "Atlético",
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
        "Sociedad": "Real Sociedad",
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
