"""Evaluation historique point-in-time d'un match REEL deja joue -
AJOUT PUR, pure orchestration : n'introduit AUCUNE nouvelle logique de
prediction, de calibration, de gate, de pricing ni de parsing de donnees.
Reutilise EXCLUSIVEMENT des briques deja existantes et validees :

    historique (match_catalog)
    -> prediction point-in-time (api.prediction_adapter.run_prediction,
       INCHANGE - meme chemin que le CLI de production)
    -> cotes d'ouverture reelles (data_engine.market_odds.matching,
       deja valide - jamais une cote inventee)
    -> enregistrement immuable pre-match (shadow_mode.journal.
       record_prediction, INCHANGE)
    -> resultat reel lu APRES (shadow_mode.journal.settle_prediction,
       INCHANGE)

Separation temporelle stricte (meme principe non negociable que
``shadow_mode/journal.py``, deja garanti par ses propres tests - voir
``tests/leakage/test_shadow_mode_temporal_separation.py`` - jamais
redemontre ici) : le score reel n'est lu qu'APRES que la prediction et son
enregistrement immuable aient deja ete produits, par construction de
l'ordre des appels dans ``evaluate_historical_match`` - jamais utilise
pour construire ``goals_train_df``/``xg_train_df`` ni pour influencer
``run_prediction``.

Les cotes utilisees sont EXCLUSIVEMENT des cotes d'OUVERTURE B365/Pinnacle
Over/Under 2.5 (``data_engine.market_odds.matching.
opening_over_under_2_5_by_match_id``, deja valide) - jamais une cote de
cloture, jamais une cote inventee quand elle est absente (l'observation
reste alors non evaluable pour la partie marche, exactement comme le
chemin de production existant : ``MARKET_DATA_UNAVAILABLE``, deja gere
par les gates existants, INCHANGES)."""

from __future__ import annotations

from pathlib import Path

from sys_foot_quant.api.prediction_adapter import run_prediction
from sys_foot_quant.data_engine.market_odds import match_catalog
from sys_foot_quant.data_engine.market_odds.football_data_loader import FootballDataMatchRecord
from sys_foot_quant.data_engine.market_odds.matching import (
    build_understat_keys,
    match_league_season,
    opening_over_under_2_5_by_match_id,
)
from sys_foot_quant.final_engine.orchestrator import DECISION_OFFSET_HOURS
from sys_foot_quant.shadow_mode.journal import record_prediction, settle_prediction


class HistoricalEvaluationError(ValueError):
    """Refus explicite (match introuvable dans le catalogue, ou dans le
    corpus Understat fourni) - jamais un resultat partiel ou invente."""


def _historical_result(understat_raw: list[dict], match_id: str) -> tuple[int, int]:
    """Score reel (buts domicile/exterieur) du match ``match_id``, lu
    directement dans le corpus canonique Understat BRUT deja fourni par
    l'appelant - memes deux champs (``goals.h``/``goals.a``) que
    ``backtesting_engine.real_data_walk_forward.build_real_match_records``/
    ``data_engine.market_odds.match_catalog`` lisent deja ailleurs, jamais
    une nouvelle source de verite ni un nouveau parsing. N'est appele
    qu'APRES que la prediction et son enregistrement immuable aient deja
    ete produits (voir ``evaluate_historical_match``) - jamais avant."""
    for raw in understat_raw:
        if str(raw.get("id")) == match_id:
            return int(raw["goals"]["h"]), int(raw["goals"]["a"])
    raise HistoricalEvaluationError(
        f"match_id {match_id!r} introuvable dans le corpus Understat fourni - "
        "aucun resultat invente."
    )


def evaluate_historical_match(
    understat_raw: list[dict],
    football_data_records: list[FootballDataMatchRecord] | None,
    competition: str,
    season: str,
    match_id: str,
    journal_path: Path,
    bookmaker: str = "B365",
    decision_offset_hours: float = DECISION_OFFSET_HOURS,
) -> dict:
    """Reconstruit une observation historique complete pour ``match_id`` :
    identifie le match dans le catalogue existant (``match_catalog``,
    INCHANGE), appelle le moteur de production (``run_prediction``,
    INCHANGE) avec la cote Over/Under 2.5 d'OUVERTURE reelle si elle est
    disponible (``opening_over_under_2_5_by_match_id``, deja valide,
    jamais inventee), journalise la decision de facon immuable
    (``shadow_mode.journal.record_prediction``, INCHANGE), puis regle
    l'observation avec le score reel du match (``settle_prediction``,
    INCHANGE) - LU EN DERNIER, apres que tout ce qui precede ait deja ete
    produit.

    ``football_data_records`` vaut ``None`` quand aucun fichier
    Football-Data reel n'existe pour (``competition``, ``season``) (ex.
    ligue1/2026_27 a ce jour) - l'observation reste alors produite, avec
    des cotes de marche absentes (``MARKET_DATA_UNAVAILABLE``, deja gere
    par les gates existants) plutot que jamais inventees.

    Retourne la vue resolue de ``shadow_mode.journal.find_prediction``
    (deja reglee), avec en plus la cle ``match_id`` (identifiant Understat
    du catalogue - distinct du ``prediction_id`` interne au journal,
    lequel reste un hash deterministe des parametres d'entree) : contient
    au minimum competition/season/kickoff_utc/home_team/away_team, les
    cotes de marche utilisees, les sorties par modele (lambda/mu/rho/
    probabilites/calibration), l'edge de marche, la decision et ses
    raisons/gates declenches, et - apres reglement - le score reel, le
    resultat Over/Under 2.5, et le profit theorique si la decision etait
    BET.

    Leve ``HistoricalEvaluationError`` si ``match_id`` n'existe pas dans
    le catalogue (``competition``, ``season``) ou dans ``understat_raw`` -
    jamais un resultat partiel ou invente."""
    matches = match_catalog.list_matches(competition, season)
    match = next((m for m in matches if m.match_id == match_id), None)
    if match is None:
        raise HistoricalEvaluationError(
            f"match_id {match_id!r} introuvable dans le catalogue ({competition!r}, {season!r})."
        )
    kickoff_naive = match.kickoff_utc.replace(tzinfo=None)

    # Cotes d'ouverture - EXCLUSIVEMENT via le bridge deja valide
    # (data_engine.market_odds.matching), jamais une seconde logique
    # d'appariement ni une cote inventee si absente.
    market_odds: dict[str, float] | None = None
    if football_data_records is not None:
        understat_keys = build_understat_keys(understat_raw, league=competition, season=season)
        report = match_league_season(understat_keys, football_data_records, competition, season)
        market_odds = opening_over_under_2_5_by_match_id(report, match_id, bookmaker=bookmaker)

    # Prediction point-in-time - chemin de production INCHANGE (meme
    # fonction que le CLI/l'API), jamais un second calcul.
    output = run_prediction(
        competition=competition,
        season=season,
        home_team=match.home_team,
        away_team=match.away_team,
        kickoff_utc=kickoff_naive,
        market_odds=market_odds,
        decision_offset_hours=decision_offset_hours,
    )

    # Enregistrement immuable pre-match - shadow_mode.journal, INCHANGE.
    prediction_view, _ = record_prediction(
        output,
        competition=competition,
        season=season,
        home_team=match.home_team,
        away_team=match.away_team,
        kickoff_utc=kickoff_naive,
        decision_offset_hours=decision_offset_hours,
        market_odds_over_2_5=market_odds["Over"] if market_odds else None,
        market_odds_under_2_5=market_odds["Under"] if market_odds else None,
        journal_path=journal_path,
        odds_bookmaker=bookmaker if market_odds else None,
        odds_market="OU" if market_odds else None,
        odds_line=2.5 if market_odds else None,
    )

    # Resultat reel - lu EN DERNIER, strictement apres que la prediction
    # et son enregistrement immuable ci-dessus aient deja ete produits.
    home_goals, away_goals = _historical_result(understat_raw, match_id)
    settled_view = settle_prediction(
        prediction_view["prediction_id"],
        home_goals=home_goals,
        away_goals=away_goals,
        journal_path=journal_path,
    )

    return {"match_id": match_id, **settled_view}
