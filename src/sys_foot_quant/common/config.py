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
    team_attack_drift_log_std_per_day: float = Field(
        0.0,
        ge=0,
        description=(
            "Ecart-type (echelle log, par jour) du taux de derive de la force "
            "d'attaque par equipe. 0 = force constante dans le temps (scenario "
            "de controle). >0 = derive lineaire (en log) connue et reproductible, "
            "propre a chaque equipe, utilisee pour tester l'hypothese A1."
        ),
    )
    team_defense_drift_log_std_per_day: float = Field(
        0.0,
        ge=0,
        description="Idem team_attack_drift_log_std_per_day, pour la defense.",
    )
    market_margin: float = Field(
        0.05,
        ge=0,
        description=(
            "Marge (overround) appliquee au marche synthetique, en plus des "
            "vraies probabilites du match. 0.05 = 5%."
        ),
    )
    market_noise_concentration: float = Field(
        40.0,
        gt=0,
        description=(
            "Concentration de la loi de Dirichlet centree sur les vraies "
            "probabilites du match (avant marge) : plus la valeur est elevee, "
            "plus le marche synthetique est proche de la verite (marche "
            "'informe'). Valeur fixee une fois, non optimisee."
        ),
    )
    dixon_coles_rho: float = Field(
        0.0,
        description=(
            "Parametre de correlation basse-score rho (Dixon & Coles, 1997), "
            "applique a la loi JOINTE des buts (les lois marginales restent "
            "Poisson(lambda)/Poisson(mu)) - voir "
            "docs/decisions/0005-protocole-generateur-dixon-coles.md pour le "
            "protocole complet. 0.0 (defaut) = comportement RIGOUREUSEMENT "
            "IDENTIQUE aux etapes 1-5 deja validees (deux tirages rng.poisson() "
            "independants, aucune branche nouvelle du code n'est empruntee). "
            "Une valeur non nulle bascule sur un tirage joint via la matrice de "
            "score corrigee par tau(x,y;rho) - voir "
            "data_engine/synthetic/generator.py. Aucune borne de validite n'est "
            "imposee ici : elle depend de (lambda, mu) par match et est "
            "verifiee explicitement a la generation (echec bruyant, jamais un "
            "ecretage silencieux)."
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
