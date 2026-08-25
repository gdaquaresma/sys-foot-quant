"""Generateur de donnees synthetiques deterministe.

Aucune source de donnees reelle n'est encore configuree pour ce projet.
Ce generateur produit un jeu de matchs/resultats/cotes purement
synthetique, mais avec une structure temporelle realiste :

- une fixture (``Match``) est "connue" (``knowledge_time``) bien avant le
  coup d'envoi (publication du calendrier) ;
- un resultat (``MatchResult``) n'est "connu" qu'apres le coup d'envoi
  (delai de confirmation) ;
- une cote (``OddsSnapshot``) n'est connue qu'a l'instant ou elle est
  observee, generalement a plusieurs echeances avant le coup d'envoi.

Cette asymetrie structurelle du ``knowledge_time`` est precisement ce que
les tests anti-look-ahead (``tests/leakage``) verifient via le
Repository : interroger le systeme avant le coup d'envoi ne doit jamais
exposer un resultat.

Determinisme : pour un ``seed`` donne, la sortie est entierement
reproductible (meme table logique), independamment de l'environnement
d'execution. Voir docs/decisions/0004-reproductibilite-deterministe.md
pour la distinction avec une reproductibilite "bit-a-bit".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from sys_foot_quant.common.config import SyntheticDataConfig
from sys_foot_quant.common.time_utils import to_utc
from sys_foot_quant.data_engine.schemas.entities import (
    Match,
    MatchResult,
    OddsSnapshot,
    Team,
)

_SELECTIONS = ("home", "draw", "away")


@dataclass(frozen=True)
class SyntheticDataset:
    teams: pd.DataFrame
    matches: pd.DataFrame
    match_results: pd.DataFrame
    odds_snapshots: pd.DataFrame
    # Force reellement utilisee pour generer les resultats (attack/defense
    # multiplicatifs par equipe, base 1.0 = force moyenne). N'est PAS une
    # table de faits point-in-time et n'est jamais ecrite en Parquet : c'est
    # un artefact de validation, utilise uniquement pour verifier qu'un
    # estimateur retrouve un signal connu (voir tests/integration). Un
    # modele de prediction ne doit jamais y avoir acces.
    true_team_strength: pd.DataFrame


_BASE_HOME_LAMBDA = 1.35
_BASE_AWAY_LAMBDA = 1.10


def generate_synthetic_dataset(config: SyntheticDataConfig) -> SyntheticDataset:
    rng = np.random.default_rng(config.seed)
    start = to_utc(datetime.fromisoformat(config.start_date))

    teams = [
        Team(team_id=i, name=f"Team_{i:02d}") for i in range(config.n_teams)
    ]

    # Force d'attaque/defense simulee par equipe (echelle log-normale,
    # centree sur 1.0). std=0 => toutes les equipes a 1.0, comportement
    # strictement identique a l'etape 1 (aucun signal d'equipe).
    team_attack = np.exp(rng.normal(0.0, config.team_attack_log_std, size=config.n_teams))
    team_defense = np.exp(rng.normal(0.0, config.team_defense_log_std, size=config.n_teams))
    true_team_strength = pd.DataFrame(
        {
            "team_id": list(range(config.n_teams)),
            "true_attack": team_attack,
            "true_defense": team_defense,
        }
    )

    matches: list[Match] = []
    results: list[MatchResult] = []
    odds: list[OddsSnapshot] = []

    for i in range(config.n_matches):
        home_id, away_id = rng.choice(config.n_teams, size=2, replace=False)
        home_id, away_id = int(home_id), int(away_id)
        kickoff = start + timedelta(days=config.days_between_matches * i)
        fixture_known = kickoff - timedelta(
            days=config.fixture_announcement_days_before
        )

        match = Match(
            match_id=i + 1,
            home_team_id=home_id,
            away_team_id=away_id,
            kickoff_time=kickoff,
            knowledge_time=fixture_known,
        )
        matches.append(match)

        lam_home = _BASE_HOME_LAMBDA * team_attack[home_id] * team_defense[away_id]
        lam_away = _BASE_AWAY_LAMBDA * team_attack[away_id] * team_defense[home_id]
        home_goals = int(rng.poisson(lam=lam_home))
        away_goals = int(rng.poisson(lam=lam_away))
        confirmation_delay = config.result_confirmation_delay_hours + float(
            rng.uniform(0.0, 0.5)
        )
        results.append(
            MatchResult(
                match_id=match.match_id,
                home_goals=home_goals,
                away_goals=away_goals,
                knowledge_time=kickoff + timedelta(hours=confirmation_delay),
            )
        )

        true_home_strength = rng.uniform(0.30, 0.55)
        true_away_strength = rng.uniform(0.20, 0.35)
        true_draw = 1.0 - true_home_strength - true_away_strength
        base_probs = np.array([true_home_strength, true_draw, true_away_strength])
        base_probs = base_probs / base_probs.sum()

        for offset_hours in config.odds_snapshot_offsets_hours:
            snapshot_time = kickoff - timedelta(hours=offset_hours)
            noise = rng.dirichlet(alpha=base_probs * 40.0)
            overround = 1.05
            implied = noise * overround
            for selection, prob in zip(_SELECTIONS, implied):
                odds.append(
                    OddsSnapshot(
                        match_id=match.match_id,
                        bookmaker="synthetic_book",
                        market_type="1x2",
                        selection=selection,
                        odds_value=round(1.0 / prob, 3),
                        knowledge_time=snapshot_time,
                    )
                )

    return SyntheticDataset(
        teams=pd.DataFrame([t.model_dump() for t in teams]),
        matches=pd.DataFrame([m.model_dump() for m in matches]),
        match_results=pd.DataFrame([r.model_dump() for r in results]),
        odds_snapshots=pd.DataFrame([o.model_dump() for o in odds]),
        true_team_strength=true_team_strength,
    )
