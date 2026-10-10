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
(``kickoff_utc`` absent) est donc desormais TROUVEE par cette route.
Pour l'etat C (aucune heure publiee du tout, ``kickoff_local_naive``
absent) : ``KickoffUnavailableError`` (ci-dessous) refuse toujours
explicitement de lancer le moteur, aucune donnee a convertir. AUCUN
autre changement de comportement pour un match D (``kickoff_utc``
toujours connu).

EXTENSION (demande produit explicite - ne jamais laisser une fixture
Ligue 1 a l'heure locale connue bloquer l'analyse) : pour l'etat B
(``kickoff_local_naive`` connu, ``kickoff_utc`` absent) d'une fixture
``ligue1``, cette route derive desormais une heure UTC ESTIMEE via
``ligue1_kickoff_cet_conversion.convert_ligue1_local_kickoff_to_utc``
(INCHANGE, deja construit et teste pour PHASE SHADOW - meme regle
CET/CEST deterministe fixee par le droit de l'UE, jamais une nouvelle
regle de conversion). Cette estimation N'EST PAS un recoupement
independant (``build_cross_checked_kickoff`` reste la seule fonction
qui produit un horaire ``verified``) - elle est explicitement signalee
comme telle via le champ ``kickoff_utc_estimated`` ajoute a la reponse
(jamais un champ silencieux : le frontend doit l'afficher). Hors Ligue 1
(``premier_league``/``liga``, qui n'ont de toute facon pas de fichier
Understat saison courante 2026/27 - voir docs/next_brique_decision.md)
ou si la conversion elle-meme est refusee (jour de changement d'heure,
annee hors table) : ``KickoffUnavailableError`` inchangee."""

from __future__ import annotations

import dataclasses

from fastapi import APIRouter, HTTPException, Query

from sys_foot_quant.api.prediction_adapter import run_prediction, validate_market_odds
from sys_foot_quant.api.routes_matches import _list_catalog_entries
from sys_foot_quant.data_engine.market_odds.ligue1_kickoff_cet_conversion import (
    AmbiguousOrInvalidKickoffError,
    convert_ligue1_local_kickoff_to_utc,
)

router = APIRouter(tags=["prediction"])

# Seule competition pour laquelle une estimation UTC derivee de l'heure
# locale est tentee (meme perimetre que ligue1_kickoff_cet_conversion.py,
# jamais elargi silencieusement ici).
_ESTIMATABLE_COMPETITIONS = frozenset({"ligue1"})


class KickoffUnavailableError(ValueError):
    """Refus explicite : la fixture est connue du catalogue fusionne
    (``routes_matches._list_catalog_entries``) mais aucune heure UTC
    (confirmee ou estimee) n'a pu etre obtenue - soit aucune heure
    publiee du tout (etat C), soit une competition hors du perimetre de
    l'estimation CET/CEST (etat B hors Ligue 1), soit une conversion
    refusee explicitement (jour de changement d'heure, annee non
    couverte - voir ``ligue1_kickoff_cet_conversion.py``).
    ``run_prediction``/``final_engine`` ne sont JAMAIS appeles dans ce
    cas (``decision_time`` ne peut pas etre calcule sans risque de
    donnee inventee). Distincte de ``MatchCatalogError`` (parametre
    invalide, HTTP 400), d'un 404 (fixture inexistante) et du 422 de
    validation FastAPI (parametre de requete manquant) - traduite en
    HTTP 409 par le gestionnaire global de ``app.py``, pour que le
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

    kickoff_utc, kickoff_utc_estimated = _resolve_kickoff_utc(match_id, competition, season, match)

    market_odds = validate_market_odds(over_2_5, under_2_5)

    output = run_prediction(
        competition=competition,
        season=season,
        home_team=match.home_team,
        away_team=match.away_team,
        kickoff_utc=kickoff_utc,
        market_odds=market_odds,
    )
    return _serialize_match_decision_output(output, kickoff_utc_estimated=kickoff_utc_estimated)


def _resolve_kickoff_utc(match_id: str, competition: str, season: str, match) -> tuple:
    """Resout l'heure UTC a utiliser pour ``run_prediction`` - CONFIRMEE
    (``match.kickoff_utc``, etat D/A) en priorite, jamais recalculee dans
    ce cas ; sinon ESTIMEE (etat B, Ligue 1 uniquement) via la conversion
    CET/CEST deja validee ; sinon refus explicite (``KickoffUnavailableError``).
    Retourne ``(kickoff_utc_naif, estimee: bool)``."""
    if match.kickoff_utc is not None:
        return match.kickoff_utc.replace(tzinfo=None), False

    if match.kickoff_local_naive is not None and competition in _ESTIMATABLE_COMPETITIONS:
        try:
            estimated = convert_ligue1_local_kickoff_to_utc(match.fixture_date, match.kickoff_local_naive)
        except AmbiguousOrInvalidKickoffError as exc:
            raise KickoffUnavailableError(
                f"Match {match_id!r} ({competition!r}, {season!r}) : heure locale connue mais conversion UTC "
                f"refusee ({exc}) - analyse impossible."
            ) from None
        return estimated.replace(tzinfo=None), True

    raise KickoffUnavailableError(
        f"Match {match_id!r} ({competition!r}, {season!r}) : aucune heure UTC confirmee ni estimable "
        "(heure locale non publiee, ou competition hors du perimetre de l'estimation CET/CEST) - "
        "analyse impossible. Aucune estimation arbitraire n'est tentee."
    )


def _serialize_match_decision_output(output: object, *, kickoff_utc_estimated: bool) -> dict:
    """Serialisation directe et fidele de ``MatchDecisionOutput`` (dataclass
    imbriquee, ``final_engine.types``, INCHANGEE) - aucune transformation,
    aucun champ du moteur ajoute/supprime/recalcule. ``kickoff_utc_estimated``
    est le SEUL champ ajoute ici (hors moteur) - signale explicitement au
    frontend que l'heure utilisee est une estimation CET/CEST depuis l'heure
    locale publiee, jamais un recoupement independant confirme (voir
    ``_resolve_kickoff_utc``) - ne doit jamais etre masque silencieusement."""
    return {**dataclasses.asdict(output), "kickoff_utc_estimated": kickoff_utc_estimated}
