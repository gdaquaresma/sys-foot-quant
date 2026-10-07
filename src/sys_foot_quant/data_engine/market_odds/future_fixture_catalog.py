"""Couche de normalisation ISOLEE des fixtures futures (saison 2026/27) -
docs/future_fixture_catalog_2026_27.md. Construit des objets ``FutureFixture``
a partir d'``openfootball_calendar.py`` (parsing, INCHANGE) +
``openfootball_team_mapping.py`` (resolution de noms, etendue pour cette
saison - voir ce module) - AUCUNE nouvelle logique de parsing, AUCUN fuzzy
matching.

PORTEE STRICTE DE CE MODULE - lire avant toute modification. Ce module ne
modifie, n'importe ni n'appelle JAMAIS :

- ``final_engine/`` (aucun module de ce package) ;
- ``scripts/predict_match.py`` / ``run_prediction`` ;
- ``match_catalog.py`` (le catalogue PRINCIPAL reste exclusivement
  Understat - ce module produit des objets SEPARES, jamais injectes dans
  ``match_catalog.list_matches``) ;
- la decision BET/NO_BET, ``min_edge_threshold``, une calibration ;
- une route API, un endpoint, le frontend.

``FutureFixture`` n'est PAS un ``match_catalog.MatchSummary`` : son champ
``kickoff_utc`` reste TOUJOURS ``None`` en pratique aujourd'hui (voir
section fuseau horaire ci-dessous) - toute integration future au
catalogue principal devra d'abord lever cette limitation, pas la
contourner silencieusement.

MODELE A 4 ETATS (audit temporel dedie, voir conversation) - deduit des
champs, JAMAIS un champ ``status`` separe qui risquerait de se
desynchroniser des donnees reelles :

- **A** - ``fixture_date`` presente, ``kickoff_local_naive`` presente,
  ``kickoff_utc`` presente (fiable). N'arrive JAMAIS aujourd'hui (aucune
  regle de conversion n'est assez fiable, voir DECOUVERTE 2).
- **B** - ``fixture_date`` presente, ``kickoff_local_naive`` presente,
  ``kickoff_utc`` absente (``None``). Heure locale connue, UTC non fiable.
- **C** - ``fixture_date`` presente, ``kickoff_local_naive`` ABSENTE
  (``None``), ``kickoff_utc`` absente. Date connue, heure non encore
  publiee par la source - EXTENSION ajoutee ici (voir ci-dessous) :
  avant cette extension, ces fixtures etaient entierement invisibles.
- **D** - match deja joue (``is_played=True``), independamment de la
  presence ou non d'une heure (un match deja joue PEUT manquer d'heure
  publiee - cas reel verifie : Coupe de France 2024/25, "Tours FC v FC
  Lorient [awarded]").

« Match connu » (A, B ou C) est une condition STRICTEMENT PLUS FAIBLE que
« match suffisamment renseigne pour lancer le moteur » (A seul,
aujourd'hui toujours vide) - ne jamais confondre les deux. B et C restent
dans ce catalogue, jamais supprimes faute d'heure (voir EXTENSION
ETAT C ci-dessous) ; ils ne sont simplement PAS analysables par le
moteur tant que A n'est pas atteint pour eux.

---

EXTENSION ETAT C (ce tour) - ``openfootball_calendar.py`` transformait
auparavant TOUTE ligne de match sans heure en ``ParseExclusion`` (texte
brut non structure, equipes/date perdues) - comportement herite du cas
2024/25 (ou une ligne sans heure etait une anomalie RARE, 1 cas sur 2565
matchs) mais structurellement inadapte au cas 2026/27 (une ligne sans
heure y est la situation NORMALE et majoritaire pour les journees
eloignees - 192/306 Ligue 1, 290/380 Liga). ``OpenFootballMatch`` expose
desormais ``fixture_date`` (toujours present) et ``kickoff_local_naive:
datetime | None`` ; une ligne structurellement valide (separateur,
equipes, date etablie) mais sans heure devient un ``OpenFootballMatch``
avec ``kickoff_local_naive=None``, JAMAIS une heure devinee/heritee a
tort. Une ligne REELLEMENT invalide (separateur absent, nom d'equipe
vide, aucune date courante, heure PRESENTE mais malformee) reste exclue
exactement comme avant - cette distinction est testee explicitement
(``tests/unit/test_openfootball_calendar.py``).

---

DECOUVERTE 1 - LE FORMAT SOURCE N'EST PAS STABLE DANS LE TEMPS. Les
fichiers 2025/26 England/Spain utilisent un format different (en-tete
"Regular Season - N", pas de separateur " v ") incompatible avec
``openfootball_calendar._parse_match_line``. Les fichiers 2026/27
reellement utilises ici sont revenus au format compatible - VERIFIE
directement en executant ``_parse_file`` dessus (voir
docs/future_fixture_catalog_2026_27.md section 2), jamais suppose. Toute
extension a une autre saison DOIT revalider ce point avant de faire
confiance a ce module.

DECOUVERTE 2 - LE FUSEAU HORAIRE N'EST PAS FIABLE UNIFORMEMENT. En
croisant des matchs REELS deja presents dans le catalogue existant
(``GET /matches`` sur un backend reel lance pour ce test) avec leur ligne
OpenFootball correspondante :

- Ligue 1 (2026/27, 2 matchs verifies) et Liga (2025/26, 2 matchs
  verifies) : ecart constant de +2h, cohérent avec "heure locale civile
  du pays, regle DST standard UE" (CEST en aout/septembre).
- Premier League (2025/26, 5 matchs verifies) : 3 matchs cohérents avec
  +1h (BST), MAIS 2 matchs (Liverpool-Bournemouth, Sunderland-West Ham)
  montrent un ecart de +0h - INCOHÉRENT, probablement une
  reprogrammation TV entre les deux instantanés de donnees (phenomene
  connu en Premier League), cause exacte non confirmee.

DECISION PRISE : AUCUNE conversion automatique vers UTC n'est
implementee ici, pour AUCUNE des 3 competitions - y compris Ligue 1/Liga,
dont l'echantillon verifie (n=4 chacune) reste trop petit pour etre
qualifie de "fiable" selon la discipline deja en vigueur dans ce depot.
``FutureFixture.kickoff_local_naive`` est le SEUL champ temporel expose -
jamais un ``kickoff_utc`` fabrique a partir d'une regle non verifiee a
l'echelle necessaire. Toute tentative d'alimenter
``decision_time = kickoff_utc - 2h`` (moteur, INCHANGE) a partir de ce
module devra d'abord lever cette limitation, explicitement, jamais en la
contournant.

---

RESOLUTION DES EQUIPES - AUCUN FUZZY MATCHING, AUCUN FALLBACK
APPROXIMATIF. Pour Ligue 1 (2026/27), les 18 equipes du fichier source
sont TOUTES resolues (100%, verifiees contre le corpus Understat 2026/27
reel). Pour Premier League et Liga, 2 clubs par championnat (promus/de
retour directement en 2026/27, sans etape 2025/26 visible) N'ONT AUCUN
corpus Understat dans ce depot pour verifier leur orthographe exacte
(Premier League : Coventry City, Hull City ; Liga : Malaga, RC Deportivo
La Coruna, Real Racing Club de Santander - 3 pour liga) - les mapper
serait deviner, interdit explicitement (voir le detail complet dans
``openfootball_team_mapping.py``, section EXTENSION 2026/27, re-audite
une seconde fois lors de la RESOLUTION PARTIELLE ci-dessous : toujours
aucune preuve Understat locale pour ces 5 clubs).
``resolve_openfootball_team`` (variante levante, pour un appelant qui
veut un refus immediat) leve ``TeamResolutionError`` pour ces clubs
plutot que d'inventer une correspondance ; ``validate_team_coverage``
les enumere explicitement sans jamais s'arreter au premier echec, pour
un diagnostic complet.

RESOLUTION PARTIELLE DU CATALOGUE (EXTENSION - demande produit
explicite, distincte de la resolution d'equipe elle-meme ci-dessus) :
``build_future_fixtures`` NE leve PLUS ``TeamResolutionError`` - une
seule equipe non resolue (ex. Coventry City) ne bloque plus la
construction de TOUTE la competition (ex. Premier League). Chaque
``FutureFixture`` porte desormais un ``resolution_status`` ("resolved"
ou "unresolved", INDEPENDANT de l'etat temporel A/B/C/D) ; une fixture
``"unresolved"`` garde ``home_team``/``away_team`` a ``None`` du cote
non resolu - jamais le nom OpenFootball substitue a la place. C'est a
l'appelant (``routes_matches.py``) de ne jamais exposer/analyser une
fixture ``"unresolved"`` - ce module continue, lui, a la representer
fidelement plutot que de la faire disparaitre silencieusement."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from sys_foot_quant.data_engine.market_odds import openfootball_calendar as ofc
from sys_foot_quant.data_engine.market_odds.openfootball_calendar import OpenFootballMatch
from sys_foot_quant.data_engine.market_odds.openfootball_team_mapping import OPENFOOTBALL_TEAM_MAPPING

ResolutionStatus = Literal["resolved", "unresolved"]

# Registre EXPLICITE de ce que cette couche sait normaliser - jamais une
# saison/competition non enregistree ici traitee silencieusement. Ligue 1
# UNIQUEMENT a un corpus Understat "2026_27" dans ce depot
# (``match_catalog._SEASON_FILES``) - Premier League/Liga sont tout de
# meme incluses ici (le calendrier OpenFootball existe pour elles) car la
# resolution d'equipe reste possible pour les clubs NON promus ; seuls les
# clubs promus sans corpus Understat 2026/27 echoueront explicitement.
FUTURE_FIXTURE_SEASON = "2026_27"
FUTURE_FIXTURE_COMPETITIONS: tuple[str, ...] = ("ligue1", "premier_league", "liga")


class TeamResolutionError(ValueError):
    """Un nom d'equipe OpenFootball n'a pas de correspondance Understat
    enregistree - refus explicite, jamais un fuzzy matching ni un
    fallback vers le nom brut OpenFootball (voir docstring du module)."""


@dataclass(frozen=True)
class FutureFixture:
    """Un match (joue ou non) normalise pour ``(competition, season)`` -
    voir le MODELE A 4 ETATS (A/B/C/D) dans la docstring du module.
    ``fixture_date`` est TOUJOURS present. ``kickoff_local_naive`` est
    ``None`` tant que la source ne publie pas d'heure (etat C).
    ``kickoff_utc`` reste TOUJOURS ``None`` aujourd'hui (DECOUVERTE 2 -
    aucune regle de conversion suffisamment fiable) ; le champ existe pour
    que l'etat A soit un jour representable sans reecrire ce modele,
    jamais pour laisser croire qu'une conversion a eu lieu.
    ``home_team_openfootball``/``away_team_openfootball`` conservent
    TOUJOURS les noms bruts de la source, resolus ou non, pour tracabilite
    complete, jamais masques.

    RESOLUTION PARTIELLE (EXTENSION - une seule equipe non resolue ne doit
    plus faire echouer la construction de TOUTE la competition, demande
    produit explicite) : ``resolution_status`` est un axe INDEPENDANT de
    l'etat temporel A/B/C/D ci-dessus - une fixture peut etre B/C/D ET
    ``"unresolved"`` en meme temps. Quand ``resolution_status ==
    "unresolved"``, ``home_team``/``away_team`` (noms Understat) sont
    ``None`` pour le ou les cotes non resolus - JAMAIS le nom OpenFootball
    brut substitue a la place (ce serait presenter une equipe non resolue
    comme si elle avait ete verifiee contre le corpus Understat, exactement
    l'erreur que ce module interdit depuis l'origine). Une fixture
    ``"unresolved"`` ne doit JAMAIS atteindre ``run_prediction`` - c'est a
    l'appelant (``routes_matches.py``) de la filtrer avant toute analyse,
    jamais a ce module de la supprimer silencieusement (elle reste
    presente ici, identifiable, pour que ``validate_team_coverage``/un
    futur diagnostic produit puisse toujours la retrouver)."""

    match_id: str
    competition: str
    season: str
    fixture_date: date
    kickoff_local_naive: datetime | None
    kickoff_utc: datetime | None
    home_team: str | None
    away_team: str | None
    home_team_openfootball: str
    away_team_openfootball: str
    is_played: bool
    resolution_status: ResolutionStatus
    source_match: OpenFootballMatch


@dataclass(frozen=True)
class TeamCoverageReport:
    """Resultat complet d'une tentative de resolution de TOUTES les
    equipes d'un fichier - jamais un arret au premier echec (contrairement
    a ``build_future_fixtures``, qui refuse vite). ``resolved``/
    ``unresolved`` sont des noms OpenFootball bruts (tels qu'ils
    apparaissent dans le fichier source)."""

    competition: str
    season: str
    resolved: tuple[str, ...]
    unresolved: tuple[str, ...]

    @property
    def is_fully_resolved(self) -> bool:
        return len(self.unresolved) == 0


def _reverse_mapping_for(competition: str) -> dict[str, str]:
    """``{nom_openfootball: nom_understat}`` pour ``competition`` -
    derive de ``OPENFOOTBALL_TEAM_MAPPING[competition][*]["league"]``,
    jamais une seconde table independante. Leve ``KeyError`` si
    ``competition`` est absente de la table (ne devrait jamais arriver
    pour les 3 competitions enregistrees dans ``FUTURE_FIXTURE_COMPETITIONS``)."""
    teams = OPENFOOTBALL_TEAM_MAPPING[competition]
    return {entry["league"]: understat_name for understat_name, entry in teams.items()}


def resolve_openfootball_team(competition: str, openfootball_name: str) -> str:
    """Nom Understat correspondant a ``openfootball_name`` pour
    ``competition`` - recherche EXACTE uniquement dans
    ``OPENFOOTBALL_TEAM_MAPPING`` (jamais de normalisation/fuzzy matching
    a ce stade, contrairement a la METHODE DE CONSTRUCTION ponctuelle
    documentee dans ``openfootball_team_mapping.py``, qui ne s'applique
    qu'a la construction initiale verifiee a la main). Leve
    ``TeamResolutionError`` explicitement si absente - variante LEVANTE,
    pour un appelant qui veut un refus immediat (ex. les tests directs de
    ce module). ``build_future_fixtures`` utilise desormais
    ``_try_resolve_openfootball_team`` (NON levante) pour permettre une
    resolution partielle du catalogue - voir cette fonction."""
    reverse = _reverse_mapping_for(competition)
    try:
        return reverse[openfootball_name]
    except KeyError:
        raise TeamResolutionError(
            f"Aucune correspondance Understat enregistree pour l'equipe OpenFootball "
            f"{openfootball_name!r} ({competition!r}) - voir openfootball_team_mapping.py "
            f"(EXTENSION 2026/27) : ce club est probablement promu/de retour sans corpus "
            f"Understat 2026/27 disponible dans ce depot pour verifier son orthographe."
        ) from None


def _try_resolve_openfootball_team(competition: str, openfootball_name: str) -> str | None:
    """Variante NON LEVANTE de ``resolve_openfootball_team`` - retourne
    ``None``, jamais une approximation, quand ``openfootball_name`` est
    absente de la table. Utilisee UNIQUEMENT par ``build_future_fixtures``
    pour permettre une resolution PARTIELLE du catalogue (demande produit
    explicite : une seule equipe non resolue, ex. Coventry City, ne doit
    plus faire echouer la construction de TOUTE la competition, ex.
    Premier League) - jamais pour masquer une absence reelle de
    correspondance, qui reste identifiable via ``resolution_status`` sur
    la fixture produite."""
    return _reverse_mapping_for(competition).get(openfootball_name)


def build_match_id(
    competition: str,
    season: str,
    home_team: str,
    away_team: str,
    fixture_date: date,
    kickoff_local_naive: datetime | None,
) -> str:
    """Identifiant composite DETERMINISTE - PAS un identifiant fourni par
    OpenFootball (qui n'en expose aucun, voir docstring du module).
    Stable entre deux telechargements identiques (ne depend que des
    donnees du match lui-meme, jamais de l'ordre de lecture du fichier) -
    meme patron que ``scripts/predict_match.py::run_prediction`` (jamais
    importe d'ici, seulement le meme esprit de construction, pour ne
    jamais faire dependre ce module isole de ``scripts/``).

    Utilise l'heure COMPLETE (``kickoff_local_naive.isoformat()``) quand
    elle est connue (etats A/B/D) pour la precision maximale ; retombe sur
    ``fixture_date.isoformat()`` SEUL quand elle est absente (etat C) -
    jamais une heure fabriquee pour completer l'identifiant. L'unicite de
    (competition, season, home_team, away_team, fixture_date) a ete
    verifiee empiriquement sur les 16 fichiers reels enregistres (2024/25
    + 2026/27, aucune collision - voir
    tests/integration/test_openfootball_calendar_real_files.py::test_no_date_level_collision_even_without_kickoff_time) :
    deux equipes ne se rencontrent jamais deux fois le meme jour dans un
    championnat a une seule manche par journee."""
    time_component = kickoff_local_naive.isoformat() if kickoff_local_naive is not None else fixture_date.isoformat()
    return f"{competition}:{season}:{home_team}_vs_{away_team}:{time_component}"


def validate_team_coverage(competition: str, season: str = FUTURE_FIXTURE_SEASON) -> TeamCoverageReport:
    """Tente de resoudre TOUTES les equipes reellement presentes dans le
    fichier ``(competition, season)`` - jamais un arret au premier echec
    (contrairement a ``build_future_fixtures``) : c'est le diagnostic
    EXHAUSTIF demande, pas une simple construction de catalogue."""
    report = ofc.load_competition(season, competition)
    names = sorted({m.home_team for m in report.matches} | {m.away_team for m in report.matches})
    reverse = _reverse_mapping_for(competition)
    resolved = tuple(n for n in names if n in reverse)
    unresolved = tuple(n for n in names if n not in reverse)
    return TeamCoverageReport(competition=competition, season=season, resolved=resolved, unresolved=unresolved)


def build_future_fixtures(competition: str, season: str = FUTURE_FIXTURE_SEASON) -> tuple[FutureFixture, ...]:
    """Construit TOUS les ``FutureFixture`` (joues ET non joues, AVEC et
    SANS heure publiee, RESOLUS ET non resolus - jamais filtre ici, voir
    MODELE A 4 ETATS dans la docstring du module) pour
    ``(competition, season)``, tries chronologiquement (``fixture_date``
    puis heure quand connue) puis par ``match_id`` (meme convention que
    ``match_catalog.list_matches``).

    RESOLUTION PARTIELLE (EXTENSION - demande produit explicite) : NE leve
    PLUS ``TeamResolutionError`` quand une equipe est non resolue - une
    fixture dont au moins une equipe (domicile et/ou exterieur) n'a pas de
    correspondance Understat enregistree est desormais INCLUSE avec
    ``resolution_status="unresolved"`` et le(s) cote(s) concerne(s) a
    ``None`` (jamais le nom OpenFootball brut substitue, voir docstring de
    ``FutureFixture``), plutot que de faire echouer la construction de
    TOUTE la competition pour une seule equipe bloquante (cas reel :
    Coventry City/Hull City bloquaient integralement Premier League,
    Malaga/Deportivo/Racing Santander bloquaient integralement Liga).
    ``validate_team_coverage`` reste l'outil de diagnostic EXHAUSTIF pour
    enumerer precisement ces equipes. ``kickoff_utc`` reste toujours
    ``None`` (DECOUVERTE 2) - aucun lien avec la resolution d'equipe."""
    if competition not in FUTURE_FIXTURE_COMPETITIONS:
        raise ValueError(
            f"Competition non enregistree pour les fixtures futures : {competition!r} "
            f"(disponibles : {FUTURE_FIXTURE_COMPETITIONS})."
        )
    report = ofc.load_competition(season, competition)
    fixtures: list[FutureFixture] = []
    for m in report.matches:
        home_team = _try_resolve_openfootball_team(competition, m.home_team)
        away_team = _try_resolve_openfootball_team(competition, m.away_team)
        resolution_status: ResolutionStatus = "resolved" if home_team is not None and away_team is not None else "unresolved"
        # L'identifiant reste construit avec le nom Understat des que
        # possible (comportement INCHANGE pour toute fixture entierement
        # resolue, donc aucune regression sur les match_id deja testes) ;
        # retombe sur le nom OpenFootball brut UNIQUEMENT pour construire
        # un identifiant stable du cote non resolu - jamais pour le
        # presenter comme un nom Understat (voir FutureFixture.home_team).
        id_home = home_team if home_team is not None else m.home_team
        id_away = away_team if away_team is not None else m.away_team
        fixtures.append(
            FutureFixture(
                match_id=build_match_id(competition, season, id_home, id_away, m.fixture_date, m.kickoff_local_naive),
                competition=competition,
                season=season,
                fixture_date=m.fixture_date,
                kickoff_local_naive=m.kickoff_local_naive,
                kickoff_utc=None,
                home_team=home_team,
                away_team=away_team,
                home_team_openfootball=m.home_team,
                away_team_openfootball=m.away_team,
                is_played=m.is_played,
                resolution_status=resolution_status,
                source_match=m,
            )
        )
    # Cle de tri robuste a kickoff_local_naive=None (Python ne compare pas
    # None a un datetime) : groupe par date, puis les fixtures A HEURE
    # CONNUE avant celles sans heure au sein d'un meme jour (ordre stable,
    # jamais une comparaison directe impliquant None), puis match_id en
    # repli deterministe final.
    return tuple(
        sorted(
            fixtures,
            key=lambda f: (f.fixture_date, f.kickoff_local_naive is None, f.kickoff_local_naive or datetime.min, f.match_id),
        )
    )
