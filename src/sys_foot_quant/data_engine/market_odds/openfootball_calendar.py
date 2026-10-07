"""Calendrier multi-competitions OpenFootball (championnat + coupe
nationale + UEFA) - implementation controlee, perimetre 2024/25
uniquement (docs/multi_competition_calendar_open_data_audit.md,
verdict GO PARTIEL).

PORTEE DE CE MODULE - lire avant toute modification. Ce module construit
UNIQUEMENT une couche de donnees en lecture : parsing de fichiers texte
"football.txt" (domaine public, CC0, `github.com/openfootball/*`) deja
telecharges dans `research/fixture_calendar/openfootball/runs/` (meme
convention que `research/market_odds/football_data/runs/`). Il ne modifie,
n'importe ni n'appelle JAMAIS :

- `final_engine/` (aucun module de ce package) ;
- `scripts/predict_match.py` / `run_prediction` ;
- la decision BET/NO_BET, un seuil `min_edge_threshold`, une calibration ;
- `poisson_simple`/`dixon_coles`/`xg_model` ;
- `fixture_congestion.py` (Brique 1, intra-championnat, INCHANGE) - ce
  nouveau module est un corpus de donnees SEPARE, jamais fusionne.

Aucune experience, aucun test statistique, aucune activation en
production ne decoule de ce module a ce stade.

PLACEMENT ARCHITECTURAL : `data_engine/market_odds/`, pas un nouveau
sous-package `data_engine/fixture_calendar/`, par coherence avec le choix
deja documente et justifie dans `fixture_congestion.py` ("Aucun nouveau
sous-package data_engine/schedule/ n'est cree") et avec les precedents
`elo_ratings.py`/`shots_on_target.py`/`football_data_loader.py` (fournisseurs
de donnees externes non-cote, deja installes ici pour la meme raison).

SOURCE ET PROVENANCE (docs/multi_competition_calendar_open_data_audit.md
section 2) : fichiers texte au format "football.txt" du projet
`openfootball`/`football.db` (domaine public CC0), recuperes par appel
HTTP reel (`raw.githubusercontent.com`, verifie accessible depuis cette
session) et committes tels quels dans `research/fixture_calendar/
openfootball/runs/<pays_ou_uefa>/<saison>_<competition>.txt`. Aucun
telechargement automatise n'est effectue par ce module lui-meme (meme
discipline que `football_data_loader.py`, qui lit des CSV deja presents
sans jamais les telecharger lui-meme) : si un fichier venait a manquer,
ce module leve une erreur explicite plutot que de tenter un acces reseau.

PERIMETRE 2024/25 (championnat + coupe + UEFA, 13 fichiers) - la saison
2025/26 n'est PAS enregistree ici pour ces competitions etendues, car les
fichiers de coupe nationale et des phases principales Europa/Conference
League 2025/26 etaient absents (HTTP 404 reel, verifie) au moment de cet
audit - conformement a la consigne "ne jamais supposer qu'un fichier
existe", aucune entree 2025/26 n'est creee tant que son fichier n'a pas
ete verifie present.

EXTENSION 2026/27 (championnat SEUL - ligue1/premier_league/liga,
docs/future_fixture_catalog_2026_27.md) : ajoutee pour alimenter
``future_fixture_catalog.py`` en fixtures FUTURES reelles (saison en
cours, non terminee) - cas DIFFERENT de l'hypothese PIT ci-dessous (qui ne
vaut que pour 2024/25, saison deja close). Pas de coupe/UEFA 2026/27 ici
(hors perimetre demande). Decouverte lors de cette extension : le format
source n'est PAS stable dans le temps - les fichiers 2025/26
England/Spain utilisent un format different (pas de separateur " v ")
incompatible avec ce parseur, alors que les fichiers 2026/27 utilises ici
sont revenus au format compatible (verifie reellement, voir le document
cite ci-dessus) - toute extension future doit revalider le format avant
de faire confiance a ce module.

HYPOTHESE PIT EXPLICITE POUR 2024/25 (ne pas la presenter comme davantage
que ce qu'elle est - NE S'APPLIQUE PAS a l'extension 2026/27 ci-dessus,
dont le but est justement d'exposer des matchs non joues) : les fichiers
2024/25 sont des instantanes historiques d'une saison DEJA TERMINEE, mis
a jour par le projet source de facon hebdomadaire pendant la saison
(historique de commits reel verifie dans l'audit precedent : messages
"auto-update week N"). Par construction de ce mode de production, un
match ne peut apparaitre avec un score que s'il a deja ete joue au moment
du commit - il n'existe donc, dans l'etat du depot tel que recupere ici
pour 2024/25, aucune ligne representant une date "programmee mais pas
encore jouee" presentee comme definitive. **Ceci ne constitue PAS une
preuve que la source traite correctement un report de match en
particulier** (aucun cas reel de report n'a ete observe dans les fichiers
utilises) - seulement un argument structurel sur le mode de production.
Aucune information de marche future n'est utilisee ici, et aucune
pretention de garantie PIT absolue n'est faite.

LIMITE DE FUSEAU HORAIRE, DOCUMENTEE PLUTOT QUE MASQUEE : l'heure indiquee
dans les fichiers source (ex. "20:45") n'est PAS confirmee comme etant en
UTC - elle correspond vraisemblablement a l'heure locale du lieu de
match, convention non documentee par la source elle-meme. Ce module
expose donc deliberement un champ ``kickoff_local_naive`` (``datetime``
SANS fuseau horaire), jamais un ``kickoff_utc`` qui pretendrait a une
precision non verifiee. Toute comparaison inter-fuseaux (ex. repos entre
un match en Russie et un match en Espagne) resterait donc approximative
tant que ce point n'est pas leve - limite assumee, jamais masquee."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

_MONTHS: dict[str, int] = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}
# Saison "2024_25" uniquement (voir docstring du module) - chemins verifies
# HTTP 200 au moment du telechargement reel dans cette session.
_SOURCE_FILES: dict[str, dict[str, Path]] = {
    "2024_25": {
        "ligue1": Path("research/fixture_calendar/openfootball/runs/france/2024-25_fr1.txt"),
        "coupe_de_france": Path("research/fixture_calendar/openfootball/runs/france/2024-25_frcup.txt"),
        "premier_league": Path(
            "research/fixture_calendar/openfootball/runs/england/2024-25_1-premierleague.txt"
        ),
        "fa_cup": Path("research/fixture_calendar/openfootball/runs/england/2024-25_facup.txt"),
        "efl_cup": Path("research/fixture_calendar/openfootball/runs/england/2024-25_eflcup.txt"),
        "liga": Path("research/fixture_calendar/openfootball/runs/espana/2024-25_1-liga.txt"),
        "copa_del_rey": Path("research/fixture_calendar/openfootball/runs/espana/2024-25_cup.txt"),
        "champions_league": Path("research/fixture_calendar/openfootball/runs/uefa/2024-25_cl.txt"),
        "champions_league_qualifying": Path("research/fixture_calendar/openfootball/runs/uefa/2024-25_clq.txt"),
        "europa_league": Path("research/fixture_calendar/openfootball/runs/uefa/2024-25_el.txt"),
        "europa_league_qualifying": Path("research/fixture_calendar/openfootball/runs/uefa/2024-25_elq.txt"),
        "conference_league": Path("research/fixture_calendar/openfootball/runs/uefa/2024-25_conf.txt"),
        "conference_league_qualifying": Path(
            "research/fixture_calendar/openfootball/runs/uefa/2024-25_confq.txt"
        ),
    },
    # Extension 2026/27 - championnat seul (voir docstring du module,
    # section EXTENSION 2026/27) - chemins verifies HTTP 200 au moment du
    # telechargement reel (2026-10-05T19:18:49Z,
    # docs/future_fixture_catalog_2026_27.md).
    "2026_27": {
        "ligue1": Path("research/fixture_calendar/openfootball/runs/france/2026-27_fr1.txt"),
        "premier_league": Path(
            "research/fixture_calendar/openfootball/runs/england/2026-27_1-premierleague.txt"
        ),
        "liga": Path("research/fixture_calendar/openfootball/runs/espana/2026-27_1-liga.txt"),
    },
}

SEASONS: tuple[str, ...] = tuple(sorted(_SOURCE_FILES))


class OpenFootballCalendarError(ValueError):
    """Refus explicite (saison/competition non enregistree, fichier
    absent, en-tete illisible) - jamais un calendrier partiel ou un
    defaut silencieux (meme discipline que ``MatchCatalogError``)."""


@dataclass(frozen=True)
class OpenFootballMatch:
    """UN match, tel que parse depuis un fichier football.txt - jamais une
    structure d'entrainement (pas de buts totaux agreges, pas de xG).

    ``fixture_date`` est TOUJOURS present (la ligne de date d'en-tete de
    journee, ex. "Sun May 16", est requise pour meme tenter de parser une
    ligne de match - voir ``_parse_file``). ``kickoff_local_naive`` est
    ``None`` quand la source ne publie PAS ENCORE d'heure de coup d'envoi
    pour ce match (EXTENSION fixtures futures, docs/future_fixture_catalog_2026_27.md) -
    JAMAIS une heure devinee/heritee a tort. Un match avec
    ``kickoff_local_naive is None`` peut etre deja joue (``is_played=True``
    reste possible - cas reel verifie : Coupe de France 2024/25, "Tours FC
    v FC Lorient [awarded]", resultat connu mais heure jamais publiee par
    la source) ou pas encore joue (``is_played=False``, cas des journees
    eloignees non encore programmees par les diffuseurs). Distinct d'une
    ligne reellement INVALIDE (separateur absent, nom d'equipe vide, aucune
    date courante etablie) : CES lignes restent des ``ParseExclusion``,
    jamais transformees en ``OpenFootballMatch`` (voir ``_parse_file``)."""

    competition: str
    season: str
    round_label: str | None
    fixture_date: date
    kickoff_local_naive: datetime | None
    home_team: str
    away_team: str
    home_country_code: str | None
    away_country_code: str | None
    is_played: bool
    home_goals: int | None
    away_goals: int | None
    score_raw: str
    awarded: bool
    source_file: str
    source_line_number: int


@dataclass(frozen=True)
class ParseExclusion:
    """UNE ligne candidate-match rejetee explicitement - jamais une
    omission silencieuse. ``reason`` est un texte stable, teste."""

    source_file: str
    source_line_number: int
    raw_line: str
    reason: str


@dataclass(frozen=True)
class ParseReport:
    """Resultat complet et deterministe d'un parsing de fichier -
    matches ET exclusions, jamais l'un sans l'autre."""

    competition: str
    season: str
    source_file: str
    declared_range: tuple[date, date]
    matches: tuple[OpenFootballMatch, ...]
    exclusions: tuple[ParseExclusion, ...]


_HEADER_TITLE_RE = re.compile(r"^=\s*(.+)$")
_HEADER_DATE_RE = re.compile(r"^#\s*Date\s+(?P<start>.+?)\s*-\s*(?P<end>.+?)\s*\(\d+d\)\s*$")
_ROUND_RE = re.compile(r"^▪\s*(.+)$")
_DATE_LINE_RE = re.compile(
    r"^\s*(?P<dow>Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(?P<month>[A-Za-z]{3})\s+(?P<day>\d{1,2})"
    r"(?:\s+(?P<year>\d{4}))?\s*$"
)
_COUNTRY_CODE_RE = re.compile(r"^(?P<name>.*?)\s*\((?P<code>[A-Z]{3})\)\s*$")
_SCORE_RE = re.compile(r"\d+\s*-\s*\d+")
_SIMPLE_SCORE_RE = re.compile(r"^(?P<home>\d+)\s*-\s*(?P<away>\d+)$")


def _parse_bare_date(text: str) -> tuple[str, int, int | None]:
    """``"Tue Jul 9"`` ou ``"Wed Aug 28 2024"`` -> (mois, jour, annee|None).
    Le jour de semaine est optionnel (absent sur certaines bornes
    d'en-tete, ex. ``"Jul 9"``). Leve ``OpenFootballCalendarError`` si le
    format ne correspond pas - jamais une interpretation approximative."""
    direct = re.match(r"^(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+)?(?P<month>[A-Za-z]{3})\s+(?P<day>\d{1,2})"
                       r"(?:\s+(?P<year>\d{4}))?$", text.strip())
    if not direct:
        raise OpenFootballCalendarError(f"Borne d'en-tete illisible : {text!r}.")
    month = direct.group("month")
    if month not in _MONTHS:
        raise OpenFootballCalendarError(f"Mois inconnu dans l'en-tete : {text!r}.")
    year = int(direct.group("year")) if direct.group("year") else None
    return month, int(direct.group("day")), year


def _parse_header_range(start_text: str, end_text: str, source_file: str) -> tuple[date, date]:
    """``# Date <debut> - <fin> (Nd)``. L'un des deux cotes peut ne pas
    porter d'annee explicite (observe reellement sur les fichiers de
    qualifications UEFA, ex. ``"Tue Jul 9 - Wed Aug 28 2024 (50d)"``) :
    dans ce cas l'annee manquante est celle de l'autre borne (les fenetres
    de qualification ne traversent jamais un changement d'annee dans les
    fichiers observes) - jamais une annee devinee hors de cette regle
    explicite et testee."""
    start_month, start_day, start_year = _parse_bare_date(start_text)
    end_month, end_day, end_year = _parse_bare_date(end_text)
    if start_year is None and end_year is None:
        raise OpenFootballCalendarError(
            f"En-tete sans aucune annee exploitable dans {source_file} : {start_text!r} - {end_text!r}."
        )
    if start_year is None:
        start_year = end_year
    if end_year is None:
        end_year = start_year
    try:
        start = date(start_year, _MONTHS[start_month], start_day)
        end = date(end_year, _MONTHS[end_month], end_day)
    except ValueError as exc:
        raise OpenFootballCalendarError(f"Date d'en-tete invalide dans {source_file} : {exc}.") from exc
    if end < start:
        raise OpenFootballCalendarError(
            f"En-tete incoherente dans {source_file} : fin ({end}) anterieure au debut ({start})."
        )
    return start, end


def _split_team_country(raw: str) -> tuple[str, str | None]:
    m = _COUNTRY_CODE_RE.match(raw.strip())
    if m:
        return m.group("name").strip(), m.group("code")
    return raw.strip(), None


def _extract_goals(score_text: str) -> tuple[int | None, int | None]:
    """``home_goals``/``away_goals`` UNIQUEMENT pour un score simple sans
    qualificatif (``"1-4"``) - ``None`` des qu'un ``pen.``/``a.e.t.``/
    ``[awarded]`` est present (nombre ambigu, jamais devine - voir
    docstring du module)."""
    m = _SIMPLE_SCORE_RE.match(score_text.strip())
    if not m:
        return None, None
    return int(m.group("home")), int(m.group("away"))


def _parse_match_line(
    line: str, line_number: int, source_file: str, current_date: date | None, current_round: str | None
) -> tuple[OpenFootballMatch | None, ParseExclusion | None]:
    """Une seule ligne candidate-match. Retourne soit un match, soit une
    exclusion journalisee - jamais les deux, jamais ni l'un ni l'autre
    pour une ligne reconnue comme candidate."""
    time_match = re.match(r"^\s*(?P<time>\d{1,2}:\d{2})\s+(?P<body>.+)$", line)
    body = time_match.group("body") if time_match else line.strip()
    time_text = time_match.group("time") if time_match else None

    parts = re.split(r"\s+v\s+", body, maxsplit=1)
    if len(parts) != 2:
        return None, ParseExclusion(source_file, line_number, line.rstrip("\n"), "separateur ' v ' absent")

    home_raw, away_and_result = parts
    score_match = _SCORE_RE.search(away_and_result)
    if score_match is None:
        away_raw = away_and_result.strip()
        score_raw = ""
        is_played = False
    else:
        away_raw = away_and_result[: score_match.start()].strip()
        score_raw = away_and_result[score_match.start() :].strip()
        is_played = True

    home_name, home_code = _split_team_country(home_raw)
    away_name, away_code = _split_team_country(away_raw)

    if not home_name or not away_name:
        return None, ParseExclusion(
            source_file, line_number, line.rstrip("\n"), "nom d'equipe vide apres extraction"
        )
    if current_date is None:
        return None, ParseExclusion(
            source_file, line_number, line.rstrip("\n"), "aucune date courante etablie avant cette ligne"
        )

    awarded = "[awarded]" in score_raw
    has_qualifier = "pen." in score_raw or "a.e.t." in score_raw
    if awarded or has_qualifier or not score_raw:
        # Score ambigu (tirs au but / prolongations / forfait) ou absent
        # (match pas encore joue) : jamais de nombre de buts devine -
        # voir docstring de ``_extract_goals``.
        home_goals, away_goals = None, None
    else:
        home_goals, away_goals = _extract_goals(score_raw.split("(")[0].strip())

    return (
        _MatchLineResult(
            round_label=current_round,
            date_=current_date,
            time_text=time_text,
            home_name=home_name,
            away_name=away_name,
            home_code=home_code,
            away_code=away_code,
            is_played=is_played,
            home_goals=home_goals,
            away_goals=away_goals,
            score_raw=score_raw,
            awarded=awarded,
        ),
        None,
    )


@dataclass(frozen=True)
class _MatchLineResult:
    round_label: str | None
    date_: date
    time_text: str | None
    home_name: str
    away_name: str
    home_code: str | None
    away_code: str | None
    is_played: bool
    home_goals: int | None
    away_goals: int | None
    score_raw: str
    awarded: bool


def _parse_file(path: Path, competition: str, season: str) -> ParseReport:
    if not path.exists():
        raise OpenFootballCalendarError(
            f"Fichier OpenFootball introuvable : {path} (ce module ne telecharge jamais de donnee lui-meme)."
        )
    source_file = str(path)
    lines = path.read_text(encoding="utf-8").splitlines()

    declared_range: tuple[date, date] | None = None
    current_date: date | None = None
    current_year: int | None = None
    last_month_num: int | None = None
    current_round: str | None = None
    last_time_text: str | None = None

    matches: list[OpenFootballMatch] = []
    exclusions: list[ParseExclusion] = []

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\n")
        stripped = line.strip()

        if not stripped:
            continue

        header_date = _HEADER_DATE_RE.match(stripped)
        if header_date:
            declared_range = _parse_header_range(header_date.group("start"), header_date.group("end"), source_file)
            current_year = declared_range[0].year
            continue

        if _HEADER_TITLE_RE.match(stripped) and stripped.startswith("="):
            continue
        if stripped.startswith("#"):
            continue

        round_match = _ROUND_RE.match(stripped)
        if round_match:
            current_round = round_match.group(1).strip()
            last_time_text = None
            continue

        date_match = _DATE_LINE_RE.match(stripped)
        if date_match:
            if current_year is None:
                exclusions.append(
                    ParseExclusion(source_file, line_number, line, "date rencontree avant tout en-tete '# Date'")
                )
                continue
            month = date_match.group("month")
            if month not in _MONTHS:
                exclusions.append(ParseExclusion(source_file, line_number, line, f"mois inconnu : {month!r}"))
                continue
            month_num = _MONTHS[month]
            if date_match.group("year") is not None:
                # Annee explicite sur cette ligne : verifiee reellement
                # restituee par la source au changement d'annee civile
                # (ex. "Fri Jan 3 2025" dans les fichiers reels
                # telecharges) - toujours prioritaire, et propagee comme
                # nouvelle reference pour les lignes suivantes sans annee.
                year = int(date_match.group("year"))
                current_year = year
            elif last_month_num is not None and month_num < last_month_num:
                # Filet de securite si jamais une source ne restituait pas
                # l'annee au changement : bascule deduite du sens de
                # lecture chronologique du fichier, jamais une autre regle.
                current_year += 1
                year = current_year
            else:
                year = current_year
            try:
                candidate_date = date(year, month_num, int(date_match.group("day")))
            except ValueError:
                exclusions.append(ParseExclusion(source_file, line_number, line, "date calendaire invalide"))
                continue
            if declared_range and not (declared_range[0] <= candidate_date <= declared_range[1]):
                exclusions.append(
                    ParseExclusion(
                        source_file,
                        line_number,
                        line,
                        f"date {candidate_date} hors de la plage declaree en en-tete {declared_range}",
                    )
                )
                current_date = None
                last_month_num = month_num
                continue
            current_date = candidate_date
            last_month_num = month_num
            last_time_text = None
            continue

        # Ligne candidate-match uniquement si le separateur ' v ' est present ;
        # sinon ligne benigne (buteurs, note, separateur visuel) - jamais
        # journalisee comme exclusion (ce n'est pas une tentative de match).
        if not re.search(r"\sv\s", stripped):
            continue

        result, exclusion = _parse_match_line(line, line_number, source_file, current_date, current_round)
        if exclusion is not None:
            exclusions.append(exclusion)
            continue
        assert result is not None  # pour mypy : l'un des deux est toujours non-None

        # Une ligne candidate-match ARRIVEE ICI est deja structurellement
        # valide (separateur " v " trouve, noms d'equipe non vides, date
        # courante etablie - sinon ``_parse_match_line``/la boucle
        # ci-dessus l'auraient deja rejetee en ``ParseExclusion``, inchange
        # ci-dessous). L'absence d'heure n'est donc PAS une raison de
        # rejeter le match lui-meme - seulement de laisser
        # ``kickoff_local_naive`` honnetement ``None`` (EXTENSION fixtures
        # futures, voir docstring de ``OpenFootballMatch``) - jamais une
        # heure devinee ni heritee a tort d'une autre journee.
        time_text = result.time_text or last_time_text
        if result.time_text:
            last_time_text = result.time_text
        kickoff: datetime | None
        if time_text is None:
            kickoff = None
        else:
            try:
                hour, minute = (int(x) for x in time_text.split(":"))
                kickoff = datetime(result.date_.year, result.date_.month, result.date_.day, hour, minute)
            except ValueError:
                # Heure PRESENTE mais structurellement invalide (ex.
                # "25:99") - ceci reste une ligne reellement malformee,
                # jamais convertie en match a heure inconnue.
                exclusions.append(ParseExclusion(source_file, line_number, line, f"heure invalide : {time_text!r}"))
                continue

        matches.append(
            OpenFootballMatch(
                competition=competition,
                season=season,
                round_label=result.round_label,
                fixture_date=result.date_,
                kickoff_local_naive=kickoff,
                home_team=result.home_name,
                away_team=result.away_name,
                home_country_code=result.home_code,
                away_country_code=result.away_code,
                is_played=result.is_played,
                home_goals=result.home_goals,
                away_goals=result.away_goals,
                score_raw=result.score_raw,
                awarded=result.awarded,
                source_file=source_file,
                source_line_number=line_number,
            )
        )

    if declared_range is None:
        raise OpenFootballCalendarError(f"Aucun en-tete '# Date ... - ...' trouve dans {path}.")

    return ParseReport(
        competition=competition,
        season=season,
        source_file=source_file,
        declared_range=declared_range,
        matches=tuple(matches),
        exclusions=tuple(exclusions),
    )


def available_competitions(season: str) -> tuple[str, ...]:
    """Competitions ENREGISTREES pour ``season`` - ne garantit pas que le
    fichier existe encore sur disque (verifie par ``load_competition``),
    seulement qu'il etait present au moment de cet audit."""
    if season not in _SOURCE_FILES:
        raise OpenFootballCalendarError(f"Saison inconnue : {season!r} (saisons disponibles : {SEASONS}).")
    return tuple(sorted(_SOURCE_FILES[season]))


def load_competition(season: str, competition: str) -> ParseReport:
    """Parse le fichier de ``(season, competition)``. Leve
    ``OpenFootballCalendarError`` explicitement si la cle n'est pas
    enregistree ou si le fichier est absent du disque - jamais un
    resultat vide silencieux (meme discipline que
    ``match_catalog.list_matches``)."""
    if season not in _SOURCE_FILES:
        raise OpenFootballCalendarError(f"Saison inconnue : {season!r} (saisons disponibles : {SEASONS}).")
    if competition not in _SOURCE_FILES[season]:
        raise OpenFootballCalendarError(
            f"Competition inconnue pour {season!r} : {competition!r} "
            f"(disponibles : {available_competitions(season)})."
        )
    return _parse_file(_SOURCE_FILES[season][competition], competition, season)


@dataclass(frozen=True)
class TeamCalendarEntry:
    """Une ligne du calendrier reconstruit d'UN club, toutes competitions
    confondues - ``is_home`` distingue domicile/exterieur, jamais fusionne."""

    competition: str
    kickoff_local_naive: datetime
    opponent: str
    is_home: bool
    is_played: bool
    source_match: OpenFootballMatch


@dataclass(frozen=True)
class SkippedCompetition:
    """UNE competition demandee mais non disponible pour cette saison -
    journalisee explicitement, jamais simulee (``fichier absent =
    competition non disponible``)."""

    competition: str
    reason: str


def build_team_calendar(
    season: str,
    team_name_by_competition: Mapping[str, str],
) -> tuple[tuple[TeamCalendarEntry, ...], tuple[SkippedCompetition, ...]]:
    """Calendrier chronologique d'UN club sur ``season``, en combinant
    toutes les competitions listees dans ``team_name_by_competition``
    (cle = competition, valeur = nom EXACT du club tel qu'il apparait
    dans CE fichier de competition - mapping explicite fourni par
    l'appelant, JAMAIS de fuzzy matching ici).

    Une competition absente du registre ``_SOURCE_FILES`` pour cette
    saison est explicitement ignoree et journalisee dans la seconde
    valeur retournee (``SkippedCompetition``) - jamais une erreur fatale
    qui empecherait de construire le reste du calendrier, et jamais une
    simulation du contenu manquant."""
    entries: list[TeamCalendarEntry] = []
    skipped: list[SkippedCompetition] = []

    for competition, team_name in team_name_by_competition.items():
        if season not in _SOURCE_FILES or competition not in _SOURCE_FILES[season]:
            skipped.append(SkippedCompetition(competition, "competition non enregistree pour cette saison"))
            continue
        path = _SOURCE_FILES[season][competition]
        if not path.exists():
            skipped.append(SkippedCompetition(competition, f"fichier absent sur disque : {path}"))
            continue
        report = load_competition(season, competition)
        for m in report.matches:
            # Un match sans heure publiee (``kickoff_local_naive is None`` -
            # EXTENSION fixtures futures) ne peut structurellement pas
            # entrer dans un calcul de repos/congestion (``congestion_preview``
            # compare des instants precis) - exclu ICI, au niveau de ce
            # calendrier de club, jamais au niveau du parseur (qui le
            # preserve honnetement comme match CONNU, voir ``OpenFootballMatch``).
            if m.kickoff_local_naive is None:
                continue
            if m.home_team == team_name:
                entries.append(TeamCalendarEntry(competition, m.kickoff_local_naive, m.away_team, True, m.is_played, m))
            elif m.away_team == team_name:
                entries.append(TeamCalendarEntry(competition, m.kickoff_local_naive, m.home_team, False, m.is_played, m))

    entries.sort(key=lambda e: (e.kickoff_local_naive, e.competition))
    return tuple(entries), tuple(skipped)


@dataclass(frozen=True)
class CongestionPreview:
    """Donnee PREPARATOIRE uniquement (jamais injectee dans un modele a ce
    stade) - repos et frequence de matchs avant une date cible, toutes
    competitions confondues."""

    as_of: datetime
    rest_days: float | None
    matches_last_7d: int
    matches_last_14d: int
    matches_last_21d: int


def congestion_preview(calendar: Sequence[TeamCalendarEntry], as_of: datetime) -> CongestionPreview:
    """``calendar`` doit deja etre trie chronologiquement (sortie de
    ``build_team_calendar``). Seuls les matchs STRICTEMENT anterieurs a
    ``as_of`` sont consideres (meme garde-fou PIT que
    ``fixture_congestion.rest_days_before_match`` : jamais le match cible
    lui-meme, jamais un match posterieur)."""
    prior = [e for e in calendar if e.kickoff_local_naive < as_of]
    rest_days: float | None = None
    if prior:
        last = max(prior, key=lambda e: e.kickoff_local_naive)
        rest_days = (as_of - last.kickoff_local_naive).total_seconds() / 86400.0
    matches_7 = sum(1 for e in prior if (as_of - e.kickoff_local_naive).days < 7)
    matches_14 = sum(1 for e in prior if (as_of - e.kickoff_local_naive).days < 14)
    matches_21 = sum(1 for e in prior if (as_of - e.kickoff_local_naive).days < 21)
    return CongestionPreview(as_of, rest_days, matches_7, matches_14, matches_21)
