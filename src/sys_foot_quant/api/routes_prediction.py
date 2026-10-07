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
  inatteignable via cette route, exactement comme via le CLI existant.

EXTENSION (integration produit du catalogue de fixtures futures) : la
resolution de ``match_id`` passe desormais par
``routes_matches._list_catalog_entries`` (catalogue fusionne
Understat + OpenFootball/2026_27, INCHANGE cote logique de fusion) au
lieu de ``match_catalog.list_matches`` seul - une fixture future B/C
(``kickoff_utc`` absent) est donc desormais TROUVEE par cette route,
mais ``KickoffUnavailableError`` (ci-dessous) refuse explicitement de
lancer le moteur dessus plutot que d'inventer une heure. AUCUN autre
changement de comportement pour un match D (``kickoff_utc`` toujours
connu)."""

from __future__ import annotations

import dataclasses

from fastapi import APIRouter, HTTPException, Query

from sys_foot_quant.api.prediction_adapter import run_prediction, validate_market_odds
from sys_foot_quant.api.routes_matches import _list_catalog_entries

router = APIRouter(tags=["prediction"])


class KickoffUnavailableError(ValueError):
    """Refus explicite : la fixture est connue du catalogue fusionne
    (``routes_matches._list_catalog_entries``) mais son ``kickoff_utc``
    n'est pas disponible (etats B/C du modele temporel - voir
    ``future_fixture_catalog.py``) - AUCUNE estimation arbitraire de
    l'heure/du fuseau horaire n'est jamais tentee ici, et
    ``run_prediction``/``final_engine`` ne sont JAMAIS appeles dans ce
    cas (``decision_time = kickoff_utc - 2h`` ne peut pas etre calcule
    sans risque de donnee inventee). Distincte de ``MatchCatalogError``
    (parametre invalide, HTTP 400), d'un 404 (fixture inexistante) et du
    422 de validation FastAPI (parametre de requete manquant) - traduite
    en HTTP 409 par le gestionnaire global de ``app.py``, pour que le
    frontend puisse distinguer precisement ce cas d'une veritable erreur
    serveur ou d'un match inexistant."""


@router.get("/matches/{match_id}/prediction")
def get_match_prediction(
    match_id: str,
    competition: str = Query(..., description="Competition (obligatoire - aucune recherche globale par id seul)."),
    season: str = Query(..., description="Saison (obligatoire - aucune recherche globale par id seul)."),
    over_2_5: float | None = Query(None, description="Cote de marche Over 2.5 (optionnelle, fournir les deux ou aucune)."),
    under_2_5: float | None = Query(None, description="Cote de marche Under 2.5 (optionnelle, fournir les deux ou aucune)."),
) -> dict:
    """``match_id`` -> resolution via le catalogue fusionne (voir
    ``routes_matches._list_catalog_entries``) -> refus explicite si
    ``kickoff_utc`` est absent (``KickoffUnavailableError``, etats B/C) ->
    validation des cotes (INCHANGEE) -> ``run_prediction`` (INCHANGE) ->
    serialisation brute de ``MatchDecisionOutput``. ``MatchCatalogError``/
    ``TeamResolutionError``/``PredictMatchError``/``KickoffUnavailableError``
    sont traduites par les gestionnaires globaux de ``app.py`` - jamais
    absorbees silencieusement ici."""
    match = next((m for m in _list_catalog_entries(competition, season) if m.match_id == match_id), None)
    if match is None:
        raise HTTPException(
            status_code=404,
            detail=f"Match {match_id!r} introuvable pour competition={competition!r}, season={season!r}.",
        )
    if match.kickoff_utc is None:
        raise KickoffUnavailableError(
            f"Match {match_id!r} ({competition!r}, {season!r}) : heure/UTC du coup d'envoi non "
            "disponible (fixture future sans conversion UTC fiable) - analyse impossible tant que "
            "kickoff_utc n'est pas connu. Aucune estimation arbitraire n'est tentee."
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
