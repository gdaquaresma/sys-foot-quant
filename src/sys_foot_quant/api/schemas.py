"""Schemas de reponse Pydantic pour l'API - Phase UI-2-B.

Utilise UNIQUEMENT la ou un schema explicite apporte une valeur reelle
(``match_catalog.MatchSummary`` a une forme fixe, petite, entierement
connue : un schema Pydantic la documente sans risque de perte
d'information). Les vues du journal Shadow Mode
(``shadow_mode.journal.load_journal``/``find_prediction``/
``evaluate_shadow``) ont une forme imbriquee et potentiellement evolutive
(``models``, ``market_comparison``, ``settlement``, ``calibration_bins``,
...) - DELIBEREMENT NON modelisees ici en Pydantic strict, pour ne jamais
risquer de supprimer silencieusement un champ non anticipe par ce schema
(comportement par defaut de Pydantic : les champs non declares sont
ignores). Ces routes retournent donc le ``dict``/``list[dict]`` produit
par le module Shadow Mode TEL QUEL (FastAPI le serialise nativement, ces
dicts etant deja entierement JSON-compatibles - construits par un
round-trip ``json.dumps``/``json.loads`` dans ``journal.py``)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from sys_foot_quant.data_engine.market_odds.match_catalog import MatchSummary


class MatchResponse(BaseModel):
    """Reflete exactement ``match_catalog.MatchSummary`` - aucun champ
    ajoute, aucun champ supprime, aucune valeur recalculee."""

    match_id: str
    competition: str
    season: str
    kickoff_utc: datetime
    home_team: str
    away_team: str
    is_played: bool

    @classmethod
    def from_match_summary(cls, match: MatchSummary) -> "MatchResponse":
        return cls(
            match_id=match.match_id,
            competition=match.competition,
            season=match.season,
            kickoff_utc=match.kickoff_utc,
            home_team=match.home_team,
            away_team=match.away_team,
            is_played=match.is_played,
        )
