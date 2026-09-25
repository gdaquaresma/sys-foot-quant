"""Routes Shadow Mode en LECTURE SEULE (Phase UI-2-B) - delegue
integralement a ``shadow_mode.journal`` (INCHANGE). N'importe et n'expose
JAMAIS ``record_prediction``/``settle_prediction`` (ecriture) - aucune
route POST/PUT/PATCH/DELETE dans ce module, par construction (seul
``APIRouter.get`` est utilise ci-dessous).

``DEFAULT_JOURNAL_PATH`` est TOUJOURS passe explicitement aux 3 appels
ci-dessous (jamais un appel sans argument reposant sur le defaut interne
de ``load_journal``/``evaluate_shadow``, qui est lie a la definition de
ces fonctions et donc invisible a un monkeypatch du module) - meme valeur
reelle en production, mais rend le chemin du journal substituable pour les
tests d'integration (fixture isolee, jamais le journal canonique)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from sys_foot_quant.shadow_mode.journal import DEFAULT_JOURNAL_PATH, evaluate_shadow, find_prediction, load_journal

router = APIRouter(tags=["shadow"])


@router.get("/shadow")
def get_shadow_journal() -> list[dict]:
    """Vue fusionnee complete du journal (``load_journal``, INCHANGEE).
    Si le fichier ``research/shadow_mode/predictions.jsonl`` n'existe pas,
    ``load_journal`` retourne deja nativement ``[]`` - propage cet etat
    tel quel (succes, liste vide), ne cree jamais le fichier, ne fabrique
    jamais d'observation."""
    return load_journal(DEFAULT_JOURNAL_PATH)


@router.get("/shadow/{prediction_id}")
def get_shadow_prediction(prediction_id: str) -> dict:
    """Une observation precise (``find_prediction``, INCHANGEE - exige
    ``journal_path`` explicitement, sans valeur par defaut cote fonction).
    Identifiant absent (y compris si le journal lui-meme est absent,
    ``find_prediction`` retournant ``None`` dans les deux cas) -> HTTP 404
    explicite, jamais un objet vide silencieux."""
    record = find_prediction(DEFAULT_JOURNAL_PATH, prediction_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Observation Shadow Mode introuvable : prediction_id={prediction_id!r}."
        )
    return record


@router.get("/performance")
def get_performance() -> dict:
    """Evaluation globale (``evaluate_shadow``, INCHANGEE) - structure et
    valeurs preservees telles quelles (compteurs a zero et messages
    explicites inclus si le journal est vide/insuffisant). Aucun filtre
    temporel ni metrique recalculee ici - ``evaluate_shadow`` n'accepte
    d'ailleurs aucun parametre de ce type."""
    return evaluate_shadow(DEFAULT_JOURNAL_PATH)
