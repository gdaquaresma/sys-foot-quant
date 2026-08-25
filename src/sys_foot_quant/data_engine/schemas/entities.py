"""Contrats de donnees des tables de faits.

Regle structurelle du projet : toute table de faits susceptible d'etre
lue par un modele ou un backtest herite de ``PointInTimeFact`` et porte
donc un ``knowledge_time`` explicite, distinct de l'``event_time``
eventuel (ex: ``kickoff_time``). C'est ce champ, et lui seul, que le
Repository utilise pour decider si une ligne est visible a un instant T.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from sys_foot_quant.common.time_utils import to_utc


class PointInTimeFact(BaseModel):
    """Base commune a toute donnee soumise au controle point-in-time."""

    knowledge_time: datetime

    @field_validator("knowledge_time")
    @classmethod
    def _normalize_knowledge_time(cls, value: datetime) -> datetime:
        return to_utc(value)


class Team(BaseModel):
    team_id: int
    name: str


class Match(PointInTimeFact):
    """Une rencontre programmee (fixture).

    ``knowledge_time`` represente ici la publication du calendrier, qui
    doit necessairement precede (ou coincider avec) le coup d'envoi.
    """

    match_id: int
    competition_id: str = "synthetic-league"
    season: str = "synthetic"
    home_team_id: int
    away_team_id: int
    kickoff_time: datetime

    @field_validator("kickoff_time")
    @classmethod
    def _normalize_kickoff_time(cls, value: datetime) -> datetime:
        return to_utc(value)

    @model_validator(mode="after")
    def _validate_consistency(self) -> "Match":
        if self.home_team_id == self.away_team_id:
            raise ValueError("home_team_id et away_team_id doivent differer.")
        if self.knowledge_time > self.kickoff_time:
            raise ValueError(
                "Une fixture ne peut pas etre connue apres son coup d'envoi "
                f"(match_id={self.match_id})."
            )
        return self


class MatchResult(PointInTimeFact):
    """Score final d'un match.

    ``knowledge_time`` est l'instant ou le resultat devient connaissable
    (typiquement apres le coup de sifflet final), jamais le kickoff_time
    lui-meme.
    """

    match_id: int
    home_goals: int = Field(..., ge=0)
    away_goals: int = Field(..., ge=0)


class OddsSnapshot(PointInTimeFact):
    """Une cote observee a un instant donne (append-only).

    ``knowledge_time`` correspond ici directement a l'instant
    d'observation (``snapshot_time``) : une cote n'existe, par
    definition, qu'a partir du moment ou elle est publiee.
    """

    match_id: int
    bookmaker: str
    market_type: str = "1x2"
    selection: str
    odds_value: float = Field(..., gt=1.0)
