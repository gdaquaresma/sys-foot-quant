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

from datetime import date, datetime

from pydantic import BaseModel

from sys_foot_quant.data_engine.market_odds.future_fixture_catalog import FutureFixture
from sys_foot_quant.data_engine.market_odds.match_catalog import MatchSummary


class MatchResponse(BaseModel):
    """Reflete ``match_catalog.MatchSummary`` (matchs joues, ``kickoff_utc``
    toujours connu) ET ``future_fixture_catalog.FutureFixture`` (fixtures
    futures 2026/27, OpenFootball - ``kickoff_utc`` encore toujours
    ``None`` aujourd'hui, DECOUVERTE 2 de ce module) - EXTENSION
    integration produit du catalogue de fixtures futures. Aucun champ
    ``status`` separe : l'etat A/B/C/D (voir future_fixture_catalog.py)
    se deduit TOUJOURS de la presence/absence de ``kickoff_local_naive``/
    ``kickoff_utc``, jamais d'un champ redondant qui pourrait se
    desynchroniser."""

    match_id: str
    competition: str
    season: str
    fixture_date: date
    kickoff_local_naive: datetime | None
    kickoff_utc: datetime | None
    home_team: str
    away_team: str
    is_played: bool

    @classmethod
    def from_match_summary(cls, match: MatchSummary) -> "MatchResponse":
        """``match_catalog`` (Understat) n'expose aucune notion d'heure
        locale distincte de l'UTC deja connu - ``kickoff_local_naive``
        reste ``None`` ici (pas une donnee manquante : simplement un
        concept propre a la source OpenFootball, jamais fabrique a partir
        de ``kickoff_utc``)."""
        return cls(
            match_id=match.match_id,
            competition=match.competition,
            season=match.season,
            fixture_date=match.kickoff_utc.date(),
            kickoff_local_naive=None,
            kickoff_utc=match.kickoff_utc,
            home_team=match.home_team,
            away_team=match.away_team,
            is_played=match.is_played,
        )

    @classmethod
    def from_future_fixture(cls, fixture: FutureFixture) -> "MatchResponse":
        """``kickoff_utc`` reste ``None`` tant que ``fixture.kickoff_utc``
        l'est (etats B/C) - jamais recalcule ici a partir de
        ``kickoff_local_naive`` (aucune regle de conversion suffisamment
        fiable, voir future_fixture_catalog.py)."""
        return cls(
            match_id=fixture.match_id,
            competition=fixture.competition,
            season=fixture.season,
            fixture_date=fixture.fixture_date,
            kickoff_local_naive=fixture.kickoff_local_naive,
            kickoff_utc=fixture.kickoff_utc,
            home_team=fixture.home_team,
            away_team=fixture.away_team,
            is_played=fixture.is_played,
        )
