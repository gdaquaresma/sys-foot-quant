"""Adaptateur d'import pour ``scripts/predict_match.py`` (Phase de
cadrage/implementation "moteur -> API").

``scripts/predict_match.py`` est un SCRIPT (hors du paquet installe
``sys_foot_quant``), pas un module de bibliotheque - il est deja charge
ainsi par les tests existants
(``tests/leakage/test_predict_match_current_season.py`` et autres, voir
``importlib.util.spec_from_file_location``). Ce module reprend EXACTEMENT
le meme mecanisme, UNE SEULE FOIS a l'import (module mis en cache par
``sys.modules``), pour exposer a l'API les objets deja definis la-bas :

- ``run_prediction`` (point d'entree canonique, INCHANGE) ;
- ``PredictMatchError`` (refus explicite, INCHANGE) ;
- ``validate_market_odds`` (validation des cotes, INCHANGE).

AUCUNE logique n'est copiee ou reimplementee ici - ce module ne fait que
charger et re-exporter. ``scripts/predict_match.py`` n'est jamais modifie."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent.parent / "scripts" / "predict_match.py"


def _load_predict_match_module():
    spec = importlib.util.spec_from_file_location("sys_foot_quant_api_predict_match", _SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Impossible de charger scripts/predict_match.py depuis {_SCRIPT_PATH}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_predict_match = _load_predict_match_module()

run_prediction = _predict_match.run_prediction
PredictMatchError = _predict_match.PredictMatchError
validate_market_odds = _predict_match.validate_market_odds
