"""Routes du catalogue de matchs (Phase UI-2-B) - delegue integralement a
``data_engine.market_odds.match_catalog`` (UI-2-A, INCHANGE). Ne construit
JAMAIS de DataFrame d'entrainement, ne lance JAMAIS de prediction - lecture
seule pure, meme perimetre que le module sous-jacent."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from sys_foot_quant.api.schemas import MatchResponse
from sys_foot_quant.data_engine.market_odds import match_catalog

router = APIRouter(tags=["matches"])


@router.get("/matches", response_model=list[MatchResponse])
def get_matches(
    competition: str = Query(..., description="Competition (voir match_catalog.list_competitions())."),
    season: str = Query(..., description="Saison (voir match_catalog.list_seasons())."),
) -> list[MatchResponse]:
    """Catalogue existant tel quel - ``competition``/``season`` inconnues
    levent ``match_catalog.MatchCatalogError``, traduite en HTTP 400 par le
    gestionnaire d'erreurs global (``app.py``), jamais une liste vide
    silencieuse."""
    matches = match_catalog.list_matches(competition, season)
    return [MatchResponse.from_match_summary(m) for m in matches]


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
    matches = match_catalog.list_matches(competition, season)
    for m in matches:
        if m.match_id == match_id:
            return MatchResponse.from_match_summary(m)
    raise HTTPException(
        status_code=404,
        detail=f"Match {match_id!r} introuvable pour competition={competition!r}, season={season!r}.",
    )
