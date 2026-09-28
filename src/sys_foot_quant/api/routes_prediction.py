"""Route de prediction (lecture seule cote moteur) - Phase "integration du
moteur dans le site". Orchestre STRICTEMENT des fonctions deja existantes
(``match_catalog.list_matches`` + ``prediction_adapter.run_prediction``/
``validate_market_odds``) - AUCUNE logique scientifique ici : ni calcul de
probabilite, ni calcul d'edge, ni regle de decision. Le moteur
(``final_engine``, INCHANGE) reste l'unique source de verite.

Garanties de conception (jamais a assouplir depuis cette route) :

- ``kickoff_utc`` n'est JAMAIS un parametre client - toujours derive du
  catalogue reel (``match_catalog.MatchSummary.kickoff_utc``), converti en
  naif UTC pour respecter la convention deja etablie par
  ``scripts/predict_match.py`` (``parse_kickoff_utc`` - "Coup d'envoi en
  UTC, NAIF (sans tzinfo)") - une simple adaptation de representation,
  jamais un recalcul.
- ``decision_offset_hours``/``min_edge_threshold``/``operational_thresholds``
  ne sont JAMAIS exposes : ``run_prediction()`` ne les accepte meme pas
  tous dans sa signature publique (``decision_offset_hours`` a une valeur
  par defaut jamais surchargee ici), rendant BET structurellement
  inatteignable via cette route, exactement comme via le CLI existant."""

from __future__ import annotations

import dataclasses

from fastapi import APIRouter, HTTPException, Query

from sys_foot_quant.api.prediction_adapter import run_prediction, validate_market_odds
from sys_foot_quant.data_engine.market_odds import match_catalog

router = APIRouter(tags=["prediction"])


@router.get("/matches/{match_id}/prediction")
def get_match_prediction(
    match_id: str,
    competition: str = Query(..., description="Competition (obligatoire - aucune recherche globale par id seul)."),
    season: str = Query(..., description="Saison (obligatoire - aucune recherche globale par id seul)."),
    over_2_5: float | None = Query(None, description="Cote de marche Over 2.5 (optionnelle, fournir les deux ou aucune)."),
    under_2_5: float | None = Query(None, description="Cote de marche Under 2.5 (optionnelle, fournir les deux ou aucune)."),
) -> dict:
    """``match_id`` -> resolution via le catalogue (INCHANGE) -> validation
    des cotes (INCHANGEE) -> ``run_prediction`` (INCHANGE) -> serialisation
    brute de ``MatchDecisionOutput``. ``MatchCatalogError``/
    ``PredictMatchError`` sont traduites en HTTP 400 par les gestionnaires
    globaux de ``app.py`` - jamais absorbees silencieusement ici."""
    matches = match_catalog.list_matches(competition, season)
    match = next((m for m in matches if m.match_id == match_id), None)
    if match is None:
        raise HTTPException(
            status_code=404,
            detail=f"Match {match_id!r} introuvable pour competition={competition!r}, season={season!r}.",
        )

    market_odds = validate_market_odds(over_2_5, under_2_5)

    output = run_prediction(
        competition=competition,
        season=season,
        home_team=match.home_team,
        away_team=match.away_team,
        # Toujours le kickoff REEL du catalogue, jamais une valeur client -
        # convention naive-UTC deja etablie par predict_match.py (simple
        # adaptation de representation, aucun recalcul de la valeur).
        kickoff_utc=match.kickoff_utc.replace(tzinfo=None),
        market_odds=market_odds,
    )
    return _serialize_match_decision_output(output)


def _serialize_match_decision_output(output: object) -> dict:
    """Serialisation directe et fidele de ``MatchDecisionOutput`` (dataclass
    imbriquee, ``final_engine.types``, INCHANGEE) - aucune transformation,
    aucun champ ajoute/supprime/recalcule. Les ``datetime`` restants sont
    convertis par l'encodeur JSON de FastAPI (deja utilise ailleurs dans
    cette API pour ``MatchResponse``), jamais une conversion manuelle
    supplementaire."""
    return dataclasses.asdict(output)
