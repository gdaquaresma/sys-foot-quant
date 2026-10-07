"""Routes du catalogue de matchs (Phase UI-2-B) - delegue integralement a
``data_engine.market_odds.match_catalog`` (UI-2-A, INCHANGE) pour les
matchs joues. Ne construit JAMAIS de DataFrame d'entrainement, ne lance
JAMAIS de prediction - lecture seule pure.

EXTENSION (integration produit du catalogue de fixtures futures) :
``_list_catalog_entries`` fusionne ce catalogue PRINCIPAL avec
``future_fixture_catalog`` (OpenFootball, fixtures 2026/27 B/C) -
UNIQUEMENT pour ``season == FUTURE_FIXTURE_SEASON`` et une competition
enregistree dans ``FUTURE_FIXTURE_COMPETITIONS``, jamais pour une autre
saison. ``match_catalog`` reste la seule source pour les matchs joues
(D) ; seules les fixtures FUTURES (``is_played=False``) de
``future_fixture_catalog`` sont ajoutees, pour ne jamais dupliquer un
match deja present cote Understat (partition stricte sur ``is_played`` -
aucune logique de correspondance fragile entre les deux sources,
analyse de risque documentee dans future_fixture_catalog.py).

EXTENSION (resolution partielle du catalogue de fixtures futures) :
``future_fixture_catalog.build_future_fixtures`` ne leve plus
``TeamResolutionError`` - il retourne desormais AUSSI les fixtures dont
une equipe n'est pas resolue (``resolution_status == "unresolved"``,
``home_team``/``away_team`` a ``None`` cote non resolu). Cette route ne
les expose PAS encore via l'API (voir ``_list_catalog_entries``) : le
contrat ``MatchResponse`` actuel declare ``home_team``/``away_team``
comme des noms toujours significatifs (meme typage que ``kickoff_utc``
avant son extension B/C, mais jamais etendu de la meme facon ici) ; les
exposer avec une valeur ``None`` reviendrait soit a fabriquer un nom
Understat pour un club non verifie (interdit explicitement), soit a
changer le contrat ``MatchResponse`` (hors perimetre de cette etape, qui
ne doit toucher ni le frontend ni l'API au-dela du filtrage ci-dessous).
LIMITE DOCUMENTEE (plutot que bricolee) : une fixture "unresolved" (ex.
tout match impliquant Coventry City) n'apparait donc PAS dans
``GET /matches``/``GET /matches/{id}`` aujourd'hui - elle reste
neanmoins visible et diagnosticable directement via
``future_fixture_catalog.build_future_fixtures``/``validate_team_coverage``
(voir tests d'integration dedies). Le gain produit de cette etape est
que les AUTRES fixtures de la meme competition (desormais majoritaires,
ex. 330/380 pour Premier League) ne sont plus bloquees avec elle."""

from __future__ import annotations

from datetime import datetime, time

from fastapi import APIRouter, HTTPException, Query

from sys_foot_quant.api.schemas import MatchResponse
from sys_foot_quant.data_engine.market_odds import future_fixture_catalog, match_catalog
from sys_foot_quant.data_engine.market_odds.future_fixture_catalog import (
    FUTURE_FIXTURE_COMPETITIONS,
    FUTURE_FIXTURE_SEASON,
)
from sys_foot_quant.data_engine.market_odds.match_catalog import MatchCatalogError

router = APIRouter(tags=["matches"])


def _sort_instant(m: MatchResponse) -> datetime:
    """Meilleur instant connu pour trier ``m``, par ordre de preference
    ``kickoff_utc`` (D, naif pour rester comparable - un ``datetime``
    conscient du fuseau horaire et un naif ne se comparent jamais
    directement en Python) > ``kickoff_local_naive`` (B) >
    ``fixture_date`` seule a minuit (C, aucune heure publiee). Pour les
    matchs D/B (``match_catalog`` seul, pas de fusion), cette cle
    reproduit EXACTEMENT l'ordre de tri deja garanti par
    ``match_catalog.list_matches`` (``kickoff_utc`` puis ``match_id``) -
    aucune regression d'ordre pour les saisons non fusionnees."""
    if m.kickoff_utc is not None:
        return m.kickoff_utc.replace(tzinfo=None)
    if m.kickoff_local_naive is not None:
        return m.kickoff_local_naive
    return datetime.combine(m.fixture_date, time.min)


def _list_catalog_entries(competition: str, season: str) -> list[MatchResponse]:
    """Catalogue fusionne pour ``(competition, season)``, trie de facon
    deterministe par meilleur instant connu (``_sort_instant``) puis
    ``match_id``.

    Pour toute saison AUTRE que ``FUTURE_FIXTURE_SEASON``, ou toute
    competition absente de ``FUTURE_FIXTURE_COMPETITIONS``, comportement
    STRICTEMENT inchange : ``match_catalog.MatchCatalogError`` (competition/
    saison inconnue, fichier absent/corrompu) propage tel quel, jamais
    absorbe. Pour ``FUTURE_FIXTURE_SEASON`` + une competition enregistree,
    une ``MatchCatalogError`` levee par ``match_catalog`` (ex. Premier
    League/Liga, qui n'ont pas de fichier Understat 2026_27) est
    suppose signifier "aucun match deja joue connu", pas un refus
    - les fixtures futures restent alors proposees seules.

    Seules les fixtures futures ``resolution_status == "resolved"`` sont
    ajoutees ici (voir docstring du module, section RESOLUTION PARTIELLE) -
    une fixture "unresolved" n'atteint donc JAMAIS cette liste, donc
    jamais ``GET /matches/{id}/prediction``/``run_prediction`` via cette
    route. ``future_fixture_catalog.build_future_fixtures`` ne leve plus
    ``TeamResolutionError`` pour ce motif (EXTENSION resolution partielle) -
    seul un ``ValueError`` generique pour une competition non enregistree
    (jamais atteint ici, ``competition`` est deja filtre ci-dessus) reste
    possible."""
    entries: list[MatchResponse] = []
    try:
        matches = match_catalog.list_matches(competition, season)
        entries.extend(MatchResponse.from_match_summary(m) for m in matches)
    except MatchCatalogError:
        if not (season == FUTURE_FIXTURE_SEASON and competition in FUTURE_FIXTURE_COMPETITIONS):
            raise

    if season == FUTURE_FIXTURE_SEASON and competition in FUTURE_FIXTURE_COMPETITIONS:
        future_fixtures = future_fixture_catalog.build_future_fixtures(competition, season)
        entries.extend(
            MatchResponse.from_future_fixture(f)
            for f in future_fixtures
            if not f.is_played and f.resolution_status == "resolved"
        )

    return sorted(entries, key=lambda m: (_sort_instant(m), m.match_id))


@router.get("/matches", response_model=list[MatchResponse])
def get_matches(
    competition: str = Query(..., description="Competition (voir match_catalog.list_competitions())."),
    season: str = Query(..., description="Saison (voir match_catalog.list_seasons())."),
) -> list[MatchResponse]:
    """Catalogue fusionne (voir ``_list_catalog_entries``) - ``competition``/
    ``season`` inconnues levent ``MatchCatalogError``, traduite en HTTP 400
    par le gestionnaire d'erreurs global (``app.py``), jamais une liste
    vide silencieuse."""
    return _list_catalog_entries(competition, season)


@router.get("/matches/{match_id}", response_model=MatchResponse)
def get_match(
    match_id: str,
    competition: str = Query(..., description="Competition (obligatoire - aucune recherche globale par id seul)."),
    season: str = Query(..., description="Saison (obligatoire - aucune recherche globale par id seul)."),
) -> MatchResponse:
    """Recherche ``match_id`` STRICTEMENT dans le perimetre
    (``competition``, ``season``) fourni - jamais une recherche implicite
    sur l'ensemble du catalogue (decision de conception validee, Phase
    UI-2-B section 2)."""
    for m in _list_catalog_entries(competition, season):
        if m.match_id == match_id:
            return m
    raise HTTPException(
        status_code=404,
        detail=f"Match {match_id!r} introuvable pour competition={competition!r}, season={season!r}.",
    )
