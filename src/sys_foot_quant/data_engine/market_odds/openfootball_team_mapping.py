"""Table de correspondance EXPLICITE Understat <-> OpenFootball, par
championnat et par competition (ligue1/liga/premier_league + leurs coupes
nationales + compétitions UEFA 2024/25) - Brique 2 (congestion
multi-compétitions, docs/fixture_congestion_multi_competition_experiment_specification.md).

Analogue exact de `team_mapping.py` (Football-Data<->Understat) et
`elo_team_mapping.py` (ClubElo<->Understat) : dictionnaire EXPLICITE,
JAMAIS de fuzzy matching au moment de l'usage. Toute équipe absente d'une
compétition donnée dans ce dictionnaire est simplement absente (elle n'a
pas joué cette compétition en 2024/25, ou le fichier source ne la
documente pas) - jamais une erreur, jamais une entrée devinée.

CONSTRUCTION (methode, transparente - meme discipline que les precedents).
Contrairement a `elo_team_mapping.py` (verifie entierement a la main par
l'utilisateur sur le site reel), cette table a ete construite en DEUX
temps au cours de cette session :

1. Proposition automatique par normalisation de chaine (minuscules, accents
   retires, suffixes generiques "FC"/"CF"/"AFC"/"SC"/"AC"/"Club"/"The"
   retires) comparant les ~58 noms Understat deja utilises par le projet
   (`match_catalog.list_teams`) aux noms reels presents dans les 13
   fichiers OpenFootball 2024/25 deja telecharges
   (`research/fixture_calendar/openfootball/runs/`).
2. VERIFICATION MANUELLE de chaque proposition par relecture du resultat
   affiche (jamais acceptee telle quelle) : DEUX erreurs de la
   normalisation automatique ont ete trouvees et corrigees a la main
   avant integration ici -
   - "Manchester City" et "Manchester United" se normalisaient tous deux
     vers "manchester" (suffixes "City"/"United" injustement retires par
     une premiere version trop agressive de la normalisation) - corrige
     en comparant directement aux deux noms reels distincts
     "Manchester City FC"/"Manchester United FC" retrouves dans le
     fichier Premier League ;
   - "Rennes" ne se retrouvait pas automatiquement dans "Stade Rennais FC
     1901" (demonyme "Rennais" differe de la ville "Rennes") - corrige a
     la main apres relecture du fichier reel.
   Sur les 58 autres clubs, aucune collision ni ambiguite n'a ete
   constatee lors de la verification (voir aussi le controle structurel
   `test_openfootball_team_mapping_has_no_accidental_value_collisions`).

Portee : UNIQUEMENT les clubs des 3 championnats deja suivis par le
projet (Liga/Ligue 1/Premier League), saison 2024/25 (seule saison pour
laquelle les fichiers de coupe/UEFA sont disponibles - voir
`openfootball_calendar.SEASONS`). Les centaines de clubs amateurs/de
divisions inferieures qui apparaissent dans les tours preliminaires des
coupes ne sont JAMAIS mappes ici (hors de portee du moteur de
prediction).

EXTENSION 2026/27 (docs/future_fixture_catalog_2026_27.md) : entrees
"league" ajoutees pour des clubs absents du corpus 2024/25 d'origine,
CHACUNE verifiee directement contre le corpus Understat le plus recent
REELLEMENT present dans ce depot pour ce championnat - jamais devinee :

- ligue1 (4 clubs, verifies contre `ligue1_2026_datesData.json` -
  corpus 2026/27 reel, seul championnat a en avoir un) : Le Mans,
  Lorient, Paris FC, Troyes.
- premier_league (2 clubs, verifies contre `epl_2025_datesData.json` -
  aucun corpus 2026/27 n'existe pour ce championnat, 2025/26 est le plus
  recent disponible) : Leeds, Sunderland.
- liga (2 clubs, verifies contre `liga_2025_datesData.json` - meme
  situation) : Elche, Levante.

Restent VOLONTAIREMENT NON mappes (aucun corpus Understat, meme 2025/26,
ne les contient - les mapper serait deviner, interdit explicitement) :
premier_league (Coventry City, Hull City) et liga (Malaga, RC Deportivo
La Coruna, Real Racing Club de Santander), tous deux promus/de retour
directement en 2026/27 sans etape 2025/26 visible dans ce depot.
`future_fixture_catalog.py` leve une erreur explicite pour ces clubs
plutot que d'inventer une correspondance - voir
`validate_team_coverage` dans ce module pour un diagnostic exhaustif.

AUDIT DE RE-VERIFICATION (tour dedie - resolution des mappings 2026/27
bloquants) - avant de conclure a l'absence de preuve, les 5 clubs
ci-dessus ont ete recherches explicitement, par nom, dans TOUS les
corpus Understat reellement presents dans ce depot
(`epl_2024_datesData.json`, `epl_2025_datesData.json`,
`liga_2024_datesData.json`, `liga_2025_datesData.json` - aucun corpus
Understat 2026/27 n'existe pour premier_league/liga, voir ci-dessus) :
AUCUNE occurrence, sous aucune graphie, dans aucun des 4 fichiers.
Resultat identique pour toute autre table de correspondance deja
presente dans ce depot (`team_mapping.py` Football-Data<->Understat,
`elo_team_mapping.py` ClubElo<->Understat) : ces 5 clubs n'y apparaissent
pas non plus. La SEULE source qui les mentionne est OpenFootball
lui-meme (fichiers de coupe 2024/25 - "Coventry City"/"Hull City" dans
`england/2024-25_facup.txt`/`eflcup.txt`, et le fichier championnat
2026/27 lui-meme) - une source OpenFootball ne peut jamais, par
construction, servir de preuve de la graphie Understat correspondante
(c'est precisement la correspondance a etablir, pas une donnee qui la
prouve). Conclusion inchangee : categorie C (absence de preuve
suffisante) pour les 5 clubs - AUCUN mapping ajoute, AUCUNE similarite
de nom utilisee comme preuve de substitution."""

from __future__ import annotations

# dict[league Understat] -> dict[nom Understat] -> dict[cle competition OpenFootball] -> nom OpenFootball
# La cle "league" correspond toujours au fichier championnat lui-meme
# (ligue1/liga/premier_league) - toujours presente. Les autres cles ne
# sont presentes que si le club a reellement joue cette competition en
# 2024/25 (verifie par appartenance reelle au fichier, section ci-dessus).

OPENFOOTBALL_TEAM_MAPPING: dict[str, dict[str, dict[str, str]]] = {
    "ligue1": {
        "Angers": {"league": "Angers SCO", "coupe_de_france": "Angers SCO"},
        "Auxerre": {"league": "AJ Auxerre", "coupe_de_france": "AJ Auxerre"},
        "Brest": {
            "league": "Stade Brestois 29",
            "coupe_de_france": "Stade Brestois 29",
            "champions_league": "Stade Brestois 29",
        },
        "Le Havre": {"league": "Le Havre AC"},
        # Promu 2026/27 (absent du corpus 2024/25 d'origine) - verifie
        # directement contre ligue1_2026_datesData.json (Understat), jamais
        # devine - voir EXTENSION 2026/27 en tete de ce module.
        "Le Mans": {"league": "Le Mans FC"},
        "Lens": {"league": "Racing Club de Lens"},
        "Lille": {
            "league": "Lille OSC",
            "coupe_de_france": "Lille OSC",
            "champions_league": "Lille OSC",
            "champions_league_qualifying": "Lille OSC",
        },
        # Promu 2026/27 - meme verification que "Le Mans" ci-dessus.
        "Lorient": {"league": "FC Lorient"},
        "Lyon": {
            "league": "Olympique Lyonnais",
            "coupe_de_france": "Olympique Lyonnais",
            "europa_league": "Olympique Lyonnais",
        },
        "Marseille": {"league": "Olympique de Marseille", "coupe_de_france": "Olympique Marseille"},
        "Monaco": {
            "league": "AS Monaco FC",
            "coupe_de_france": "AS Monaco",
            "champions_league": "AS Monaco FC",
        },
        "Montpellier": {"league": "Montpellier HSC", "coupe_de_france": "Montpellier HSC"},
        "Nantes": {"league": "FC Nantes", "coupe_de_france": "FC Nantes"},
        "Nice": {"league": "OGC Nice", "coupe_de_france": "OGC Nice", "europa_league": "OGC Nice"},
        # Promu 2026/27 - meme verification que "Le Mans" ci-dessus. Nom
        # OpenFootball identique au nom Understat (aucun suffixe a retirer).
        "Paris FC": {"league": "Paris FC"},
        "Paris Saint Germain": {
            "league": "Paris Saint-Germain FC",
            "coupe_de_france": "Paris Saint-Germain",
            "champions_league": "Paris Saint-Germain FC",
        },
        "Reims": {"league": "Stade de Reims", "coupe_de_france": "Stade de Reims"},
        "Rennes": {"league": "Stade Rennais FC 1901"},
        "Saint-Etienne": {"league": "AS Saint-Étienne", "coupe_de_france": "AS Saint-Étienne"},
        "Strasbourg": {"league": "RC Strasbourg Alsace"},
        "Toulouse": {"league": "Toulouse FC", "coupe_de_france": "Toulouse FC"},
        # Promu 2026/27 - meme verification que "Le Mans" ci-dessus.
        "Troyes": {"league": "ES Troyes AC"},
    },
    "liga": {
        "Alaves": {"league": "Deportivo Alavés"},
        "Athletic Club": {
            "league": "Athletic Club",
            "copa_del_rey": "Athletic Club",
            "europa_league": "Athletic Club",
        },
        "Atletico Madrid": {"league": "Club Atlético de Madrid", "champions_league": "Club Atlético de Madrid"},
        "Barcelona": {"league": "FC Barcelona", "copa_del_rey": "FC Barcelona", "champions_league": "FC Barcelona"},
        "Celta Vigo": {"league": "RC Celta de Vigo"},
        # Promu/de retour en 2025/26 (absent du corpus 2024/25 d'origine) -
        # verifie directement contre liga_2025_datesData.json (Understat,
        # seul corpus disponible pour liga au-dela de 2024/25 dans ce
        # depot - aucun corpus 2026/27 n'existe pour liga, voir EXTENSION
        # 2026/27 en tete de ce module) - toujours present en 2026/27
        # d'apres le fichier OpenFootball reellement telecharge.
        "Elche": {"league": "Elche CF"},
        "Espanyol": {"league": "RCD Espanyol de Barcelona"},
        "Getafe": {"league": "Getafe CF", "copa_del_rey": "Getafe CF"},
        "Girona": {"league": "Girona FC", "copa_del_rey": "Girona FC", "champions_league": "Girona FC"},
        "Las Palmas": {"league": "UD Las Palmas", "copa_del_rey": "UD Las Palmas"},
        "Leganes": {"league": "CD Leganés", "copa_del_rey": "CD Leganés"},
        # Meme situation que "Elche" ci-dessus.
        "Levante": {"league": "Levante UD"},
        "Mallorca": {"league": "RCD Mallorca", "copa_del_rey": "RCD Mallorca"},
        "Osasuna": {"league": "CA Osasuna", "copa_del_rey": "CA Osasuna"},
        "Rayo Vallecano": {"league": "Rayo Vallecano de Madrid"},
        "Real Betis": {"league": "Real Betis Balompié"},
        "Real Madrid": {
            "league": "Real Madrid CF",
            "copa_del_rey": "Real Madrid",
            "champions_league": "Real Madrid CF",
        },
        "Real Sociedad": {"league": "Real Sociedad de Fútbol"},
        "Real Valladolid": {"league": "Real Valladolid CF", "copa_del_rey": "Real Valladolid"},
        "Sevilla": {"league": "Sevilla FC", "copa_del_rey": "Sevilla FC"},
        "Valencia": {"league": "Valencia CF", "copa_del_rey": "Valencia CF"},
        "Villarreal": {"league": "Villarreal CF", "copa_del_rey": "Villarreal CF"},
    },
    "premier_league": {
        "Arsenal": {
            "league": "Arsenal FC",
            "fa_cup": "Arsenal FC",
            "efl_cup": "Arsenal FC",
            "champions_league": "Arsenal FC",
        },
        "Aston Villa": {
            "league": "Aston Villa FC",
            "fa_cup": "Aston Villa",
            "efl_cup": "Aston Villa",
            "champions_league": "Aston Villa FC",
        },
        "Bournemouth": {"league": "AFC Bournemouth", "fa_cup": "AFC Bournemouth", "efl_cup": "AFC Bournemouth"},
        "Brentford": {"league": "Brentford FC", "fa_cup": "Brentford FC", "efl_cup": "Brentford FC"},
        "Brighton": {
            "league": "Brighton & Hove Albion FC",
            "fa_cup": "Brighton & Hove Albion",
            "efl_cup": "Brighton & Hove Albion",
        },
        "Chelsea": {
            "league": "Chelsea FC",
            "fa_cup": "Chelsea FC",
            "efl_cup": "Chelsea FC",
            "conference_league": "Chelsea FC",
            "conference_league_qualifying": "Chelsea FC",
        },
        "Crystal Palace": {"league": "Crystal Palace FC", "fa_cup": "Crystal Palace", "efl_cup": "Crystal Palace"},
        "Everton": {"league": "Everton FC", "fa_cup": "Everton FC", "efl_cup": "Everton FC"},
        "Fulham": {"league": "Fulham FC", "fa_cup": "Fulham FC", "efl_cup": "Fulham FC"},
        "Ipswich": {"league": "Ipswich Town FC", "fa_cup": "Ipswich Town", "efl_cup": "Ipswich Town"},
        # Promu/de retour en 2025/26 (absent du corpus 2024/25 d'origine) -
        # verifie directement contre epl_2025_datesData.json (Understat,
        # seul corpus disponible pour premier_league au-dela de 2024/25
        # dans ce depot - aucun corpus 2026/27 n'existe, voir EXTENSION
        # 2026/27 en tete de ce module) - toujours present en 2026/27
        # d'apres le fichier OpenFootball reellement telecharge.
        "Leeds": {"league": "Leeds United FC"},
        "Leicester": {"league": "Leicester City FC", "fa_cup": "Leicester City", "efl_cup": "Leicester City"},
        "Liverpool": {
            "league": "Liverpool FC",
            "fa_cup": "Liverpool FC",
            "efl_cup": "Liverpool FC",
            "champions_league": "Liverpool FC",
        },
        "Manchester City": {
            "league": "Manchester City FC",
            "fa_cup": "Manchester City",
            "efl_cup": "Manchester City",
            "champions_league": "Manchester City FC",
        },
        "Manchester United": {
            "league": "Manchester United FC",
            "fa_cup": "Manchester United",
            "efl_cup": "Manchester United",
            "europa_league": "Manchester United",
        },
        "Newcastle United": {
            "league": "Newcastle United FC",
            "fa_cup": "Newcastle United",
            "efl_cup": "Newcastle United",
        },
        "Nottingham Forest": {
            "league": "Nottingham Forest FC",
            "fa_cup": "Nottingham Forest",
            "efl_cup": "Nottingham Forest",
        },
        "Southampton": {"league": "Southampton FC", "fa_cup": "Southampton FC", "efl_cup": "Southampton FC"},
        # Meme situation que "Leeds" ci-dessus.
        "Sunderland": {"league": "Sunderland AFC"},
        "Tottenham": {
            "league": "Tottenham Hotspur FC",
            "fa_cup": "Tottenham Hotspur",
            "efl_cup": "Tottenham Hotspur",
            "europa_league": "Tottenham Hotspur",
        },
        "West Ham": {"league": "West Ham United FC", "fa_cup": "West Ham United", "efl_cup": "West Ham United"},
        "Wolverhampton Wanderers": {
            "league": "Wolverhampton Wanderers FC",
            "fa_cup": "Wolverhampton Wanderers",
            "efl_cup": "Wolverhampton Wanderers",
        },
    },
}

# Competition OpenFootball du fichier championnat lui-meme, par championnat
# Understat - necessaire pour resoudre la cle "league" ci-dessus vers le
# bon fichier `openfootball_calendar` (ligue1/liga/premier_league).
LEAGUE_COMPETITION_KEY: dict[str, str] = {
    "ligue1": "ligue1",
    "liga": "liga",
    "premier_league": "premier_league",
}


def team_name_by_competition(league: str, understat_team: str) -> dict[str, str]:
    """Mapping ``competition_openfootball -> nom_openfootball`` pour
    ``understat_team`` dans ``league`` - la cle ``"league"`` du dictionnaire
    source est substituee par la vraie cle de competition OpenFootball
    (``LEAGUE_COMPETITION_KEY``). Leve ``KeyError`` explicitement si le
    championnat ou l'equipe est inconnu - jamais un mapping partiel
    silencieux ni une approximation."""
    teams = OPENFOOTBALL_TEAM_MAPPING[league]
    entry = teams[understat_team]
    out = dict(entry)
    out[LEAGUE_COMPETITION_KEY[league]] = out.pop("league")
    return out
