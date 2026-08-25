"""Chargement de configuration typee (YAML -> pydantic).

Un run (generation de donnees ou backtest) doit toujours pouvoir etre
retrace a une configuration explicite et versionnee dans ``configs/``,
plutot qu'a des parametres passes en dur dans le code.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class SyntheticDataConfig(BaseModel):
    """Parametres deterministes du generateur de donnees synthetiques."""

    seed: int = Field(..., description="Graine du generateur pseudo-aleatoire.")
    n_teams: int = Field(..., gt=1)
    n_matches: int = Field(..., gt=0)
    start_date: str = Field(..., description="Date ISO du premier match (UTC).")
    days_between_matches: float = Field(1.0, gt=0)
    result_confirmation_delay_hours: float = Field(
        2.0,
        gt=0,
        description=(
            "Delai apres le coup d'envoi avant que le resultat ne soit "
            "considere comme connu (knowledge_time du resultat)."
        ),
    )
    fixture_announcement_days_before: float = Field(
        14.0,
        gt=0,
        description="Anticipation de publication du calendrier avant le coup d'envoi.",
    )
    odds_snapshot_offsets_hours: list[float] = Field(
        default_factory=lambda: [72.0, 24.0, 1.0],
        description="Heures avant le coup d'envoi auxquelles une cote est publiee.",
    )
    team_attack_log_std: float = Field(
        0.0,
        ge=0,
        description=(
            "Ecart-type (echelle log) de la force d'attaque simulee par equipe. "
            "0 = toutes les equipes identiques (comportement etape 1, inchange)."
        ),
    )
    team_defense_log_std: float = Field(
        0.0,
        ge=0,
        description=(
            "Ecart-type (echelle log) de la force defensive simulee par equipe. "
            "0 = toutes les equipes identiques (comportement etape 1, inchange)."
        ),
    )


class BacktestStageOneConfig(BaseModel):
    """Configuration d'un run d'infrastructure (etape 1, sans modele)."""

    synthetic_data: SyntheticDataConfig
    decision_offset_hours_before_kickoff: float = Field(
        1.0,
        ge=0,
        description="A quelle avance du coup d'envoi la decision est evaluee.",
    )


def load_config(path: str | Path) -> BacktestStageOneConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return BacktestStageOneConfig.model_validate(raw)
