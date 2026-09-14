"""Instrumentation empirique intermediaire : mesure ce que l'ajout des
matchs deja joues d'une saison courante (ex. 2026/27) change REELLEMENT
dans le moteur actuel a poids egal - decidee explicitement AVANT toute
reouverture de ``football_model/recent_form.py``/A1-bis. Ne modifie
aucune ponderation (``weighting.py``/``recent_form.py`` non importes ici,
INCHANGES).

Compare deux regimes au MEME ``decision_time`` :

- BASELINE : historique long terme seul (ex. 2024/25 + 2025/26) ;
- CURRENT  : historique long terme + saison courante deja jouee, filtree
  point-in-time (ex. 2024/25 + 2025/26 + les matchs 2026/27 dont le coup
  d'envoi precede strictement ``decision_time``).

Reutilise integralement, SANS MODIFICATION : ``future_match_dataset``
(R2) et ``calibration_dataset`` (R1) pour le filtrage point-in-time et la
construction de l'historique de calibration E7/E8,
``final_engine.orchestrator.run_match_decision`` pour la prediction/
calibration/pricing/decision completes (appele deux fois, jamais
modifie), et ``PoissonModel`` directement pour un SEUL besoin
diagnostique que ``final_engine`` n'expose pas dans ses objets de sortie
(``types.ModelPrediction`` ne porte que lambda/mu, pas attack/defense par
equipe) - reproduit exactement l'appel deja fait par
``final_engine/prediction.py`` (``PoissonModel(use_team_hfa=False).fit(goals_train_df)``),
jamais une nouvelle estimation ni un nouveau modele."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd

from sys_foot_quant.backtesting_engine.real_data_walk_forward import RealMatchRecord
from sys_foot_quant.calibration_engine.calibration_dataset import (
    build_calibration_dataframe,
    split_calibration_df_by_model,
)
from sys_foot_quant.data_engine.market_odds.future_match_dataset import build_match_train_dataframes
from sys_foot_quant.final_engine.orchestrator import run_match_decision
from sys_foot_quant.final_engine.types import MatchDecisionOutput
from sys_foot_quant.football_model.poisson import PoissonModel

_THRESHOLD_OVER_2_5 = 2.5


@dataclass(frozen=True)
class SeasonSensitivityMetrics:
    """Un jeu de metriques pour UN regime (BASELINE ou CURRENT), au meme
    ``decision_time`` - aucun nouveau calcul de probabilite : uniquement
    une lecture des sorties deja produites par ``PoissonModel``
    (diagnostic attaque/defense) et par ``run_match_decision``
    (INCHANGE). Un champ ``None`` signifie que le niveau correspondant du
    moteur n'a pas produit de valeur (ex. historique insuffisant) -
    jamais une valeur de repli inventee."""

    n_train_matches: int
    attack_home: float | None
    defense_home: float | None
    attack_away: float | None
    defense_away: float | None
    lambda_home: float | None
    lambda_away: float | None
    total_lambda: float | None
    scale_c: float | None
    n_calibration_used: int
    p_over_2_5: float | None
    fair_odds_over_2_5: float | None
    # Nomme "decision_output" (jamais "decision") pour eviter toute collision
    # avec MatchDecisionOutput.decision (le champ DecisionResult interne) -
    # metrics.decision_output.decision.decision serait sinon ambigu a lire.
    decision_output: MatchDecisionOutput


def _delta(current: float | None, baseline: float | None) -> float | None:
    """``None`` si l'une des deux valeurs est elle-meme ``None`` - jamais
    une soustraction silencieuse avec une valeur de repli (ex. 0.0)."""
    if current is None or baseline is None:
        return None
    return current - baseline


@dataclass(frozen=True)
class SeasonSensitivityComparison:
    """BASELINE vs CURRENT au meme ``decision_time``, plus le delta
    (``CURRENT - BASELINE``) champ par champ pour les metriques
    numeriques demandees (etape 2/3 de la comparaison empirique)."""

    baseline: SeasonSensitivityMetrics
    current: SeasonSensitivityMetrics

    @property
    def delta_attack_home(self) -> float | None:
        return _delta(self.current.attack_home, self.baseline.attack_home)

    @property
    def delta_defense_home(self) -> float | None:
        return _delta(self.current.defense_home, self.baseline.defense_home)

    @property
    def delta_attack_away(self) -> float | None:
        return _delta(self.current.attack_away, self.baseline.attack_away)

    @property
    def delta_defense_away(self) -> float | None:
        return _delta(self.current.defense_away, self.baseline.defense_away)

    @property
    def delta_lambda_home(self) -> float | None:
        return _delta(self.current.lambda_home, self.baseline.lambda_home)

    @property
    def delta_lambda_away(self) -> float | None:
        return _delta(self.current.lambda_away, self.baseline.lambda_away)

    @property
    def delta_total_lambda(self) -> float | None:
        return _delta(self.current.total_lambda, self.baseline.total_lambda)

    @property
    def delta_p_over_2_5(self) -> float | None:
        return _delta(self.current.p_over_2_5, self.baseline.p_over_2_5)

    @property
    def delta_fair_odds_over_2_5(self) -> float | None:
        return _delta(self.current.fair_odds_over_2_5, self.baseline.fair_odds_over_2_5)


def _diagnostic_attack_defense(
    goals_train_df: pd.DataFrame, home_team_id: int, away_team_id: int
) -> tuple[float | None, float | None, float | None, float | None]:
    """Extrait ``attack[home]``/``defense[home]``/``attack[away]``/
    ``defense[away]`` via ``PoissonModel(use_team_hfa=False)`` -
    EXACTEMENT la meme construction que ``final_engine/prediction.py``
    (``PRIMARY_MODEL``), jamais une nouvelle estimation. ``None`` si
    l'historique est vide (``PoissonModel.fit`` refuse un DataFrame vide)
    - jamais une valeur de repli inventee."""
    if len(goals_train_df) == 0:
        return None, None, None, None
    model = PoissonModel(use_team_hfa=False).fit(goals_train_df)
    assert model.attack_ is not None and model.defense_ is not None
    return (
        model.attack_.get(home_team_id),
        model.defense_.get(home_team_id),
        model.attack_.get(away_team_id),
        model.defense_.get(away_team_id),
    )


def _compute_metrics_for_regime(
    records: list[RealMatchRecord],
    match_id: str,
    competition: str,
    season: str,
    home_team_id: int,
    away_team_id: int,
    kickoff_utc: datetime,
    decision_offset_hours: float,
    market_odds_over_2_5: float | None,
    market_odds_under_2_5: float | None,
) -> SeasonSensitivityMetrics:
    decision_time = kickoff_utc - timedelta(hours=decision_offset_hours)
    # exclude_match_id=match_id : garde-fou EXPLICITE (meme discipline que
    # _goals_train_df/_xg_train_df) - le match cible est deja exclu par le
    # filtre point-in-time des lors que decision_offset_hours > 0, mais ceci
    # ne doit jamais etre une simple consequence indirecte : si le fichier
    # "saison courante" contenait par erreur (contamination) une entree dont
    # le match_id est celui du match cible, elle reste exclue explicitement.
    goals_train_df, xg_train_df = build_match_train_dataframes(
        records,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        decision_time=decision_time,
        exclude_match_id=match_id,
    )

    # Meme convention que scripts/predict_match.py::build_prediction_inputs :
    # build_calibration_dataframe est appele avec ses valeurs par defaut
    # (jamais decision_offset_hours reinjecte ici), pour rester strictement
    # coherent avec le chemin de production existant, mono-saison.
    calibration_df = build_calibration_dataframe(records)
    calibration_df_by_model = split_calibration_df_by_model(calibration_df)

    attack_home, defense_home, attack_away, defense_away = _diagnostic_attack_defense(
        goals_train_df, home_team_id, away_team_id
    )

    decision = run_match_decision(
        match_id=match_id,
        competition=competition,
        season=season,
        kickoff_utc=kickoff_utc,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        goals_train_df=goals_train_df,
        xg_train_df=xg_train_df,
        calibration_df_by_model=calibration_df_by_model,
        market_odds_over_2_5=market_odds_over_2_5,
        market_odds_under_2_5=market_odds_under_2_5,
        decision_offset_hours=decision_offset_hours,
    )

    primary = decision.models.get("poisson_simple")
    primary_calibration = decision.calibration.get("poisson_simple")
    primary_pricing = decision.pricing.get("poisson_simple")

    lambda_home = primary.lam if primary is not None else None
    lambda_away = primary.mu if primary is not None else None
    total_lambda = (lambda_home + lambda_away) if primary is not None else None
    p_over_2_5 = (
        primary_calibration.probabilities.get(_THRESHOLD_OVER_2_5)
        if primary_calibration is not None and primary_calibration.probabilities is not None
        else None
    )
    fair_odds_over_2_5 = (
        primary_pricing.fair_price.get(_THRESHOLD_OVER_2_5) if primary_pricing is not None else None
    )

    return SeasonSensitivityMetrics(
        n_train_matches=primary.n_train_matches if primary is not None else len(goals_train_df),
        attack_home=attack_home,
        defense_home=defense_home,
        attack_away=attack_away,
        defense_away=defense_away,
        lambda_home=lambda_home,
        lambda_away=lambda_away,
        total_lambda=total_lambda,
        scale_c=primary_calibration.scale_c if primary_calibration is not None else None,
        n_calibration_used=primary_calibration.n_calibration_used if primary_calibration is not None else 0,
        p_over_2_5=p_over_2_5,
        fair_odds_over_2_5=fair_odds_over_2_5,
        decision_output=decision,
    )


def compute_season_sensitivity(
    baseline_records: list[RealMatchRecord],
    current_records: list[RealMatchRecord],
    match_id: str,
    competition: str,
    season: str,
    home_team_id: int,
    away_team_id: int,
    kickoff_utc: datetime,
    decision_offset_hours: float,
    market_odds_over_2_5: float | None = None,
    market_odds_under_2_5: float | None = None,
) -> SeasonSensitivityComparison:
    """Compare BASELINE (``baseline_records``, ex. 2024/25+2025/26 seules)
    et CURRENT (``current_records``, ex. 2024/25+2025/26 + saison
    courante deja jouee) EXACTEMENT au meme ``decision_time`` (derive du
    meme ``kickoff_utc``/``decision_offset_hours`` pour les deux regimes,
    jamais recalcule differemment). N'exige aucun filtrage prealable par
    l'appelant au-dela de ce que ``build_match_train_dataframes``/
    ``build_calibration_dataframe`` font deja (point-in-time, exclusion
    du match cible s'il est deja present dans ``records`` - meme
    garantie que R1/R2, jamais reimplementee ici).

    ``current_records`` doit deja etre le resultat de
    ``multi_season_dataset.build_real_match_records_multi_season`` (ou
    equivalent) - ce module ne verifie pas lui-meme que ``current_records``
    contient bien ``baseline_records`` en plus de nouveaux matchs, cette
    responsabilite reste a l'appelant."""
    baseline = _compute_metrics_for_regime(
        baseline_records, match_id, competition, season, home_team_id, away_team_id,
        kickoff_utc, decision_offset_hours, market_odds_over_2_5, market_odds_under_2_5,
    )
    current = _compute_metrics_for_regime(
        current_records, match_id, competition, season, home_team_id, away_team_id,
        kickoff_utc, decision_offset_hours, market_odds_over_2_5, market_odds_under_2_5,
    )
    return SeasonSensitivityComparison(baseline=baseline, current=current)
