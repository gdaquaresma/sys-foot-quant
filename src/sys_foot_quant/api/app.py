"""Point d'entree de l'API HTTP sys-foot-quant (Phase UI-2-B + integration
moteur de prediction).

Perimetre : routes GET uniquement (``routes_matches``/``routes_shadow``/
``routes_prediction``) - aucune route d'ecriture Shadow Mode
(``record_prediction``/``settle_prediction`` non importees), aucun
parametre exposant un seuil scientifique (``min_edge_threshold``,
``operational_thresholds``, ``decision_offset_hours`` restent internes a
``final_engine/``/``scripts/predict_match.py``, jamais acceptes en entree
de cette API). ``routes_prediction`` n'importe ``run_prediction`` que via
``prediction_adapter`` (chargement du script existant, INCHANGE) - aucune
logique scientifique n'est dupliquee ici.

Lancement local (Mac de developpement) :

    uv run uvicorn sys_foot_quant.api.app:app --host 127.0.0.1 --port 8000

``DEFAULT_HOST``/``DEFAULT_PORT`` ci-dessous documentent cette convention -
liaison locale UNIQUEMENT (``127.0.0.1``), JAMAIS ``0.0.0.0`` par defaut.
Toute exposition reseau plus large est une decision separee, hors
perimetre de cette phase."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from sys_foot_quant.api import routes_matches, routes_prediction, routes_shadow
from sys_foot_quant.api.prediction_adapter import PredictMatchError
from sys_foot_quant.data_engine.market_odds.match_catalog import MatchCatalogError

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000

app = FastAPI(
    title="sys-foot-quant API",
    description="API locale en lecture seule : catalogue de matchs et journal Shadow Mode. "
    "Ne produit aucune prediction et n'ecrit jamais dans le journal Shadow Mode.",
    version="0.1.0",
)


@app.exception_handler(MatchCatalogError)
async def handle_match_catalog_error(request: Request, exc: MatchCatalogError) -> JSONResponse:
    """Traduit un refus explicite de ``match_catalog`` (competition/saison
    inconnue, fichier absent/corrompu) en reponse HTTP 400 explicite -
    jamais un 200 avec un resultat par defaut, jamais un 500 generique
    masquant la cause reelle."""
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(PredictMatchError)
async def handle_predict_match_error(request: Request, exc: PredictMatchError) -> JSONResponse:
    """Meme traitement que ``MatchCatalogError`` - un refus explicite du
    chemin de prediction (ex. cotes incoherentes) devient un HTTP 400
    explicite, jamais un 500 generique ni un resultat par defaut."""
    return JSONResponse(status_code=400, content={"detail": str(exc)})


app.include_router(routes_matches.router)
app.include_router(routes_shadow.router)
app.include_router(routes_prediction.router)
