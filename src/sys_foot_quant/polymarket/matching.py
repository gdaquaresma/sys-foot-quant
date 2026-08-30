"""Rattachement Polymarket -> Football-Data (Phase L, etape 6).

Polymarket market -> home_team/away_team (deja extraits par l'appelant,
cf. reserve ci-dessous) -> mapping canonique explicite -> match_id
Football-Data, ou rejet explicite (``reason_codes``).

RESERVE IMPORTANTE : ce module ne cherche PAS lui-meme les noms
``home_team``/``away_team`` dans un titre de marche libre (ex. "Will Real
Madrid beat Barcelona?") - aucun exemple reel de titre Polymarket n'a pu
etre inspecte dans cet environnement (acces reseau bloque, voir
docs/polymarket_pomet_data_audit.md), et un parseur de titre construit
sans exemple reel serait une hypothese non verifiee sur un format non
confirme. ``Market.home_team``/``away_team`` doivent donc deja etre
renseignes (par une extraction ulterieure, une fois des titres reels
disponibles) avant d'appeler ce module - sinon le marche est rejete
``POLYMARKET_MATCH_UNMATCHED`` (aucune tentative de deviner un nom
d'equipe depuis un champ libre).

``CANONICAL_TEAM_ALIASES`` est INTENTIONNELLEMENT VIDE pour l'instant -
suit exactement la convention deja etablie par
``team_mapping.py``/``elo_team_mapping.py`` (dictionnaire explicite par
championnat, jamais de fuzzy matching), mais aucune entree ne peut y etre
ajoutee tant qu'aucun nom d'equipe Polymarket reel n'a ete observe et
verifie individuellement (meme methode que la Phase K pour ClubElo)."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta

from sys_foot_quant.polymarket import reason_codes
from sys_foot_quant.polymarket.schemas import Market, MarketMatchResult

# Dictionnaire explicite par championnat, structure identique a
# ``team_mapping.FOOTBALL_DATA_TO_UNDERSTAT`` - VIDE tant qu'aucune donnee
# reelle Polymarket n'a ete verifiee (voir docstring module).
CANONICAL_TEAM_ALIASES: dict[str, dict[str, str]] = {}

# Tolerance de date pour associer un marche a un match (etape 6 : utiliser
# aussi la date/heure, pas seulement les noms d'equipe) - un match de
# championnat ne dure jamais plus de quelques heures ; une fenetre large
# absorbe une eventuelle imprecision de ``start_time`` cote marche sans
# jamais s'etendre a un autre jour de championnat.
_DATE_TOLERANCE = timedelta(hours=12)


@dataclass(frozen=True)
class FootballDataMatchCandidate:
    """Projection minimale d'un match Football-Data utile au matching -
    decouplee de ``FootballDataMatchRecord`` (donnees de cotes) pour
    garder ce module independant et testable sans charger de CSV reel."""

    match_id: str
    competition: str
    season: str
    kickoff_utc: datetime
    home_team: str
    away_team: str


def normalize_team_name(name: str) -> str:
    """Normalisation generique (minuscule, sans accents, sans
    ponctuation) - utilisee uniquement pour COMPARER deux noms deja
    presents dans ``CANONICAL_TEAM_ALIASES``, jamais pour deviner une
    correspondance par similarite floue (fuzzy matching explicitement
    exclu, comme pour toutes les autres sources de ce projet)."""
    decomposed = unicodedata.normalize("NFKD", name)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return "".join(c.lower() for c in without_accents if c.isalnum())


def resolve_canonical_team_name(competition: str, raw_name: str) -> str | None:
    """Retourne le nom canonique d'une equipe pour ``competition``, ou
    ``None`` si le championnat ou l'equipe est absent du mapping explicite
    - jamais une correspondance approximative silencieuse."""
    table = CANONICAL_TEAM_ALIASES.get(competition)
    if table is None:
        return None
    normalized_raw = normalize_team_name(raw_name)
    for known_raw, canonical in table.items():
        if normalize_team_name(known_raw) == normalized_raw:
            return canonical
    return None


def match_market_to_football_data(
    market: Market, candidates: list[FootballDataMatchCandidate]
) -> MarketMatchResult:
    """Rattache un ``Market`` a un ``match_id`` Football-Data unique, ou
    rejette explicitement (etape 6) :

    - equipes non renseignees sur le marche, ou absentes du mapping
      canonique -> ``POLYMARKET_MATCH_UNMATCHED`` ;
    - aucun candidat ne correspond (equipes + fenetre de date) ->
      ``POLYMARKET_MATCH_UNMATCHED`` ;
    - plusieurs candidats correspondent -> ``POLYMARKET_MATCH_AMBIGUOUS``
      (jamais un choix arbitraire du premier)."""
    if market.home_team is None or market.away_team is None:
        return MarketMatchResult(
            polymarket_market_id=market.market_id,
            match_id=None,
            reason_code=reason_codes.POLYMARKET_MATCH_UNMATCHED,
        )

    competition = market.league or ""
    canonical_home = resolve_canonical_team_name(competition, market.home_team)
    canonical_away = resolve_canonical_team_name(competition, market.away_team)
    if canonical_home is None or canonical_away is None:
        return MarketMatchResult(
            polymarket_market_id=market.market_id,
            match_id=None,
            reason_code=reason_codes.POLYMARKET_MATCH_UNMATCHED,
        )

    matched: list[FootballDataMatchCandidate] = []
    for c in candidates:
        if c.competition != competition:
            continue
        if c.home_team != canonical_home or c.away_team != canonical_away:
            continue
        if market.start_time is not None and abs(c.kickoff_utc - market.start_time) > _DATE_TOLERANCE:
            continue
        matched.append(c)

    if len(matched) == 0:
        return MarketMatchResult(
            polymarket_market_id=market.market_id,
            match_id=None,
            reason_code=reason_codes.POLYMARKET_MATCH_UNMATCHED,
        )
    if len(matched) > 1:
        return MarketMatchResult(
            polymarket_market_id=market.market_id,
            match_id=None,
            reason_code=reason_codes.POLYMARKET_MATCH_AMBIGUOUS,
            candidates=tuple(c.match_id for c in matched),
        )

    return MarketMatchResult(
        polymarket_market_id=market.market_id,
        match_id=matched[0].match_id,
        reason_code=None,
    )
