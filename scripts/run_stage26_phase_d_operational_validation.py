"""Phase D - validation experimentale du mecanisme BET/NO BET.

**Premiere et seule experience** destinee a determiner si le moteur final
peut produire des `BET` (docs/operational_validation_specification.md).
Suit STRICTEMENT ce protocole. Ne modifie AUCUN modele probabiliste,
AUCUNE correction E7/E8/E14/E15/E16, ne cree AUCUN ensemble, AUCUN
coefficient de championnat. Reutilise SANS MODIFICATION le code reel du
moteur final (`final_engine.calibration.calibrate_prediction`,
`final_engine.market.compare_over_under_to_market`, tous les gates de
`final_engine.gates`, `final_engine.decision.decide`) - ce script ne fait
QUE rejouer ce code sur l'historique reel pour explorer/verrouiller UNE
valeur de `min_edge_threshold`, jamais en reimplementant la logique de
decision lui-meme.

PRE-ENREGISTREMENT (fige AVANT toute lecture d'edge/resultat reel - voir
docs/operational_validation_report.md section "Pre-enregistrement" pour
la justification complete de chaque choix ci-dessous, tous derives
STRUCTURELLEMENT de conventions deja utilisees par E1-E16, jamais
choisis en observant une performance) :

- Separation temporelle : reutilise EXACTEMENT
  ``run_stage10_over_under_recalibration.split_burn_in_calibration_test``
  (40% rodage / 30% VALIDATION / 30% TEST, tri chronologique PAR
  championnat x saison) - la meme fonction pure deja utilisee par
  B1/A2/B2/B3.3/E2/E3/E7/E8/E9/E10 sans modification. Le rodage sert de
  pool de calibration walk-forward pour VALIDATION ; VALIDATION sert de
  pool de calibration walk-forward pour TEST (extension a 3 etages de la
  discipline a 2 etages deja validee par E8).
- Population primaire : Liga + Ligue 1 uniquement (discrimination
  DEMONTREE, E4/E11/E15) - Premier League analysee separement comme
  controle negatif (jamais poolee dans la selection).
- Univers : Over 2.5 uniquement pour l'hypothese primaire (le seul seuil
  publie par une cote de marche B365, E9/E12) ; Under 2.5 en analyse
  secondaire parallele, jamais fusionnee avec Over (lecon E13 - pooler
  Over et Under dans un marche a 2 issues strictement complementaires
  est degenere).
- Grille de seuils (3 candidats primaires, chacun trace a un artefact deja
  fige du projet, aucun n'est invente pour cette occasion) :
    - raw_edge >= 0.05  (E9/E13 : borne "notable" de la grille d'anomalie deja pre-enregistree)
    - raw_edge >= 0.10  (E9/E13 : borne "marquee" de la meme grille)
    - price_edge > 0.0  (E1 : regle EV>0 exacte, seule regle de prix jamais testee dans ce projet)
- Selection : sur VALIDATION uniquement, jamais "meilleur ROI observe" -
  regle de la section 7 de docs/operational_validation_specification.md
  (performance + robustesse + IC95% + effectif + stabilite, TOUTES
  simultanement, sinon aucun seuil n'est retenu).
- TEST : verrouille jusqu'a la selection finale, evalue UNE SEULE FOIS.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from datetime import timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test  # noqa: E402
from sys_foot_quant.data_engine.market_odds.economic_dataset import DECISION_OFFSET_HOURS  # noqa: E402
from sys_foot_quant.final_engine.calibration import calibrate_prediction  # noqa: E402
from sys_foot_quant.final_engine.decision import decide  # noqa: E402
from sys_foot_quant.final_engine.gates import (  # noqa: E402
    OperationalThresholds,
    ambiguous_day_gate,
    calibration_confidence_gate,
    discrimination_confidence_gate,
    distribution_consistency_gate,
    edge_threshold_gate,
    incomplete_market_odds_gate,
    insufficient_calibration_history_gate,
)
from sys_foot_quant.final_engine.market import compare_over_under_to_market  # noqa: E402
from sys_foot_quant.final_engine.reference_tables import discrimination_status  # noqa: E402
from sys_foot_quant.final_engine.types import ModelPrediction  # noqa: E402

_PRIMARY_MODEL = "poisson_simple"
_PRIMARY_LEAGUES = ("liga", "ligue1")  # discrimination DEMONTREE (E4/E11/E15)
_CONTROL_LEAGUE = "premier_league"  # discrimination NON_DEMONTREE - controle negatif uniquement

# --- Grille de seuils PRE-ENREGISTREE (voir docstring module) ---------------
_RAW_EDGE_CANDIDATES: tuple[float, ...] = (0.05, 0.10)  # E9/E13
_PRICE_EDGE_CANDIDATES: tuple[float, ...] = (0.0,)  # E1

_STAGE18_PATH = Path(__file__).resolve().parent / "run_stage18_e9_multi_bookmaker_market_layer.py"


def _load_e9():
    spec = importlib.util.spec_from_file_location("run_stage18_e9_multi_bookmaker_market_layer", _STAGE18_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------
# ETAPE 1 - separation temporelle a 3 etages (rodage / VALIDATION / TEST),
# construite en reutilisant SANS MODIFICATION la fonction pure d'E2/E7/E8.
# --------------------------------------------------------------------------


def split_rodage_validation_test(stage10_module, stage8_module) -> tuple[set[str], set[str], set[str]]:
    """Reutilise ``stage10.split_burn_in_calibration_test`` (40/30/30,
    tri chronologique PAR championnat x saison, DEJA testee et utilisee
    par 8 experiences anterieures) - ce script ne fait qu'agreger le
    complementaire (rodage) que cette fonction ne retournait pas."""
    rodage_ids: set[str] = set()
    validation_ids: set[str] = set()
    test_ids: set[str] = set()
    for season, leagues in stage8_module._SEASONS.items():
        for league in leagues:
            records = stage8_module._load_records(league, season)
            all_ids = {r.match_id for r in records}
            v_ids, t_ids = stage10_module.split_burn_in_calibration_test(records)
            validation_ids |= v_ids
            test_ids |= t_ids
            rodage_ids |= all_ids - v_ids - t_ids
    return rodage_ids, validation_ids, test_ids


# --------------------------------------------------------------------------
# ETAPE 2 - assemblage du dataset : reutilise EXACTEMENT le code reel du
# moteur final (Niveaux B/D/E) pour chaque match, jamais une reimplementation.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class BacktestRow:
    match_id: str
    league: str
    season: str
    decision_time: object
    kickoff_utc: object
    n_calibration_used: int
    p_model_over: float
    market_odds_over: float
    market_odds_under: float
    raw_edge_over: float
    price_edge_over: float
    raw_edge_under: float
    price_edge_under: float
    outcome_over: float  # 1.0 si total_goals > 2.5, sinon 0.0
    base_gates_pass: bool  # tous les gates SAUF edge_threshold_gate (donnees, calibration, discrimination, coherence)
    calibration_status_value: str
    discrimination_status_value: str


def build_backtest_rows(
    segment_ids: set[str],
    historical_pool_df: pd.DataFrame,
    lambda_mu_df: pd.DataFrame,
    records_by_id: dict,
    leagues: tuple[str, ...],
) -> list[BacktestRow]:
    """Pour chaque match de ``segment_ids`` appartenant a ``leagues`` :
    calibration E7/E8 (``calibrate_prediction``, INCHANGEE) contre
    ``historical_pool_df`` uniquement, comparaison de marche
    (``compare_over_under_to_market``, INCHANGEE), puis application de
    TOUS les gates scientifiques/operationnels SAUF ``edge_threshold_gate``
    (dont la valeur est l'objet meme de cette experience - applique a part,
    section 3)."""
    rows: list[BacktestRow] = []
    sub = lambda_mu_df[lambda_mu_df["match_id"].isin(segment_ids) & lambda_mu_df["league"].isin(leagues)]
    for _, row in sub.iterrows():
        if pd.isna(row.get("poisson_simple_lambda")) or pd.isna(row.get("poisson_simple_mu")):
            continue
        rec = records_by_id.get(row["match_id"])
        if rec is None:
            continue
        over_by_bk = rec.odds_over_under_2_5.get("Over", {})
        under_by_bk = rec.odds_over_under_2_5.get("Under", {})
        if "B365" not in over_by_bk or "B365" not in under_by_bk:
            continue

        pred = ModelPrediction(
            model=_PRIMARY_MODEL, lam=float(row["poisson_simple_lambda"]), mu=float(row["poisson_simple_mu"]),
            rho=None, n_train_matches=0,
        )
        calibrated = calibrate_prediction(pred, historical_pool_df, as_of_time=row["decision_time"])
        if calibrated.probabilities is None:
            continue
        p_over = calibrated.probabilities[2.5]

        market_odds = {"Over": float(over_by_bk["B365"]), "Under": float(under_by_bk["B365"])}
        comparison = compare_over_under_to_market(p_over, market_odds["Over"], market_odds["Under"])

        # ``decision_time`` perd son tzinfo UTC en traversant ``Series.map``
        # (particularite de la reconstruction pandas de la colonne, jamais
        # une fuite ni une ambiguite de fuseau reelle - ``build_lambda_mu_dataframe``/
        # ``build_decision_time_lookup`` d'E7/E8, INCHANGES, produisent bien
        # des datetimes UTC a la source). Reattache explicitement UTC avant
        # de reconstruire kickoff_utc, jamais une nouvelle regle temporelle.
        decision_time = row["decision_time"]
        if decision_time.tzinfo is None:
            decision_time = decision_time.tz_localize(timezone.utc) if hasattr(decision_time, "tz_localize") else decision_time.replace(tzinfo=timezone.utc)
        kickoff_utc = decision_time + timedelta(hours=DECISION_OFFSET_HOURS)

        gate_calibration_history = insufficient_calibration_history_gate(calibrated.n_calibration_used)
        gate_ambiguous_day = ambiguous_day_gate(kickoff_utc)
        gate_market_odds = incomplete_market_odds_gate(market_odds)
        gate_distribution = distribution_consistency_gate(calibrated.goal_distribution, calibrated.probabilities)

        discrimination_value = discrimination_status(row["league"])
        thresholds_for_discrimination_check = OperationalThresholds()
        gate_discrimination_conf = discrimination_confidence_gate(discrimination_value, thresholds_for_discrimination_check)

        base_gates_pass = not any(
            g.triggered
            for g in (gate_calibration_history, gate_ambiguous_day, gate_market_odds, gate_distribution, gate_discrimination_conf)
        )

        rows.append(
            BacktestRow(
                match_id=row["match_id"],
                league=row["league"],
                season=row["season"],
                decision_time=row["decision_time"],
                kickoff_utc=kickoff_utc,
                n_calibration_used=calibrated.n_calibration_used,
                p_model_over=p_over,
                market_odds_over=market_odds["Over"],
                market_odds_under=market_odds["Under"],
                raw_edge_over=comparison.raw_edge["Over"],
                price_edge_over=comparison.price_edge["Over"],
                raw_edge_under=comparison.raw_edge["Under"],
                price_edge_under=comparison.price_edge["Under"],
                outcome_over=float(row["total_goals"] > 2.5),
                base_gates_pass=base_gates_pass,
                calibration_status_value="OK",  # calibration_zone_gate delibere hors champ (section 10 - jamais fusionne)
                discrimination_status_value=discrimination_value,
            )
        )
    return rows


# --------------------------------------------------------------------------
# ETAPE 3 - simulation de decision : reutilise litteralement
# ``decision.decide`` avec le VRAI ``edge_threshold_gate`` - jamais une
# reimplementation de la regle BET/NO_BET.
# --------------------------------------------------------------------------


def would_bet(row: BacktestRow, edge_type: str, threshold: float, selection: str = "Over") -> bool:
    """``edge_type`` in {"raw_edge", "price_edge"}. Simule EXACTEMENT ce que
    produirait ``orchestrator.run_match_decision`` si
    ``OperationalThresholds(min_edge_threshold=threshold)`` etait actif -
    reutilise ``decide()`` et tous les gates SANS LES REECRIRE."""
    if not row.base_gates_pass:
        return False
    edge_value = (row.raw_edge_over if edge_type == "raw_edge" else row.price_edge_over) if selection == "Over" else (
        row.raw_edge_under if edge_type == "raw_edge" else row.price_edge_under
    )
    thresholds = OperationalThresholds(min_edge_threshold=threshold)
    gate = edge_threshold_gate(edge_value, thresholds)
    decision_result = decide(scientific_gates=[], operational_gates=[gate])
    return decision_result.decision == "BET"


def profit_for_bet(row: BacktestRow, selection: str = "Over") -> float:
    """Profit par unite misee, cote decimale B365 - flat 1 unite, aucun
    Kelly/staking (identique en esprit a E1, jamais reoptimise ici)."""
    odds = row.market_odds_over if selection == "Over" else row.market_odds_under
    won = row.outcome_over == 1.0 if selection == "Over" else row.outcome_over == 0.0
    return (odds - 1.0) if won else -1.0


# --------------------------------------------------------------------------
# ETAPE 4 - metriques (aucune metrique n'est jamais utilisee seule)
# --------------------------------------------------------------------------


def strategy_metrics(rows: list[BacktestRow], edge_type: str, threshold: float, selection: str = "Over", seed: int = 0) -> dict:
    selected = [r for r in rows if would_bet(r, edge_type, threshold, selection)]
    n = len(selected)
    if n == 0:
        return {"n_bets": 0}
    profits = np.array([profit_for_bet(r, selection) for r in selected])
    boot = paired_bootstrap_test(profits, seed=seed)
    wins = int((profits > 0).sum())
    cumulative = np.cumsum(profits)
    running_max = np.maximum.accumulate(cumulative)
    drawdown = running_max - cumulative
    return {
        "n_bets": n,
        "hit_rate": wins / n,
        "profit_mean": float(profits.mean()),
        "profit_sum": float(profits.sum()),
        "roi": float(profits.mean()),  # flat 1 unite -> ROI par pari = profit moyen
        "yield_pct": float(profits.sum() / n * 100.0),
        "max_drawdown": float(drawdown.max()) if n > 0 else 0.0,
        "volatility": float(profits.std(ddof=1)) if n > 1 else 0.0,
        "ci_low": boot["ci_low"],
        "ci_high": boot["ci_high"],
        "p_value": boot["p_value"],
    }


def baseline_market_only_metrics(rows: list[BacktestRow], selection: str = "Over", seed: int = 0) -> dict:
    """Baseline 1 : parier systematiquement (sans aucun filtre de gate ni
    d'edge) sur TOUS les matchs de la population consideree."""
    profits = np.array([profit_for_bet(r, selection) for r in rows])
    if profits.size == 0:
        return {"n_bets": 0}
    boot = paired_bootstrap_test(profits, seed=seed)
    return {"n_bets": len(rows), "profit_mean": float(profits.mean()), "ci_low": boot["ci_low"], "ci_high": boot["ci_high"], "p_value": boot["p_value"]}


def baseline_model_no_selection_metrics(rows: list[BacktestRow], edge_type: str, selection: str = "Over", seed: int = 0) -> dict:
    """Baseline 2 : parier sur tout match dont l'edge est strictement
    positif (aucun seuil de magnitude), gates de donnees/discrimination
    actifs - reproduit l'esprit de la regle E1 (EV>0 brut) mais restreinte
    a Over 2.5, Liga/Ligue1, avec les gates actuels."""
    return strategy_metrics(rows, edge_type, threshold=1e-9, selection=selection, seed=seed)


# --------------------------------------------------------------------------
# ETAPE 5 - selection du seuil sur VALIDATION uniquement (jamais "meilleur
# ROI observe" - regle de docs/operational_validation_specification.md section 7).
# --------------------------------------------------------------------------


def candidate_grid() -> list[tuple[str, float]]:
    """Grille FIGEE (voir docstring module) - jamais modifiee apres
    observation d'un resultat."""
    candidates = [("raw_edge", t) for t in _RAW_EDGE_CANDIDATES]
    candidates += [("price_edge", t) for t in _PRICE_EDGE_CANDIDATES]
    return candidates


def passes_selection_rule(validation_metrics: dict, market_only_baseline: dict, min_n: int = 30) -> bool:
    """Regle de selection PRE-ENREGISTREE (section 7/11 de
    docs/operational_validation_specification.md) - TOUTES les conditions
    simultanement, jamais une seule :
    1. n_bets >= min_n (effectif suffisant) ;
    2. IC95% du profit entierement > 0 ;
    3. IC95% du profit entierement > IC95_high de la baseline marche seul
       (superieur a la baseline, pas seulement a zero)."""
    if validation_metrics.get("n_bets", 0) < min_n:
        return False
    if validation_metrics["ci_low"] <= 0.0:
        return False
    if validation_metrics["ci_low"] <= market_only_baseline.get("ci_high", 0.0):
        return False
    return True


def main() -> None:
    typer.echo("=== Phase D : validation experimentale du mecanisme BET/NO BET ===")
    typer.echo(
        "Reutilise SANS MODIFICATION calibrate_prediction/compare_over_under_to_market/tous les "
        "gates/decide(). poisson_simple uniquement (modele principal). Liga+Ligue1 = population "
        "primaire (discrimination DEMONTREE) ; Premier League = controle negatif separe.\n"
    )

    e9 = _load_e9()
    e8 = e9._load_e8()
    e7 = e8._load_e7()
    stage10 = e7._load_stage10()
    stage8 = stage10._load_stage8()

    records = e9.load_all_multi_bookmaker_records()
    records_by_id = {r.match_id: r for r in records}

    lambda_mu_df = e7.build_lambda_mu_dataframe(stage8)
    decision_time_lookup = e8.build_decision_time_lookup(stage8)
    lambda_mu_df["decision_time"] = lambda_mu_df["match_id"].map(decision_time_lookup)

    rodage_ids, validation_ids, test_ids = split_rodage_validation_test(stage10, stage8)
    typer.echo(f"n_rodage={len(rodage_ids)}  n_validation={len(validation_ids)}  n_test={len(test_ids)}\n")

    rodage_pool = lambda_mu_df[lambda_mu_df["match_id"].isin(rodage_ids)].copy()
    validation_pool = lambda_mu_df[lambda_mu_df["match_id"].isin(validation_ids)].copy()

    typer.echo("--- Construction VALIDATION (Liga+Ligue1) ---")
    validation_rows = build_backtest_rows(validation_ids, rodage_pool, lambda_mu_df, records_by_id, _PRIMARY_LEAGUES)
    typer.echo(f"n_validation_rows exploitables = {len(validation_rows)}")

    typer.echo("--- Selection du seuil (VALIDATION UNIQUEMENT) ---")
    market_only_validation = baseline_market_only_metrics(validation_rows, "Over")
    typer.echo(f"Baseline marche seul (VALIDATION) : {market_only_validation}")

    selected = None
    for edge_type, threshold in candidate_grid():
        metrics = strategy_metrics(validation_rows, edge_type, threshold, "Over")
        ok = passes_selection_rule(metrics, market_only_validation)
        typer.echo(f"  candidat ({edge_type} >= {threshold}) : {metrics}  -> selection_rule={'OK' if ok else 'REJETE'}")
        if ok and selected is None:
            selected = (edge_type, threshold)

    typer.echo("\n--- Robustesse (VALIDATION uniquement, jamais utilisee pour re-selectionner) ---")
    typer.echo("Par championnat :")
    for league in _PRIMARY_LEAGUES:
        sub = [r for r in validation_rows if r.league == league]
        for edge_type, threshold in candidate_grid():
            m = strategy_metrics(sub, edge_type, threshold, "Over")
            typer.echo(f"  {league} ({edge_type}>={threshold}) : {m}")

    typer.echo("Par saison :")
    for season in sorted({r.season for r in validation_rows}):
        sub = [r for r in validation_rows if r.season == season]
        for edge_type, threshold in candidate_grid():
            m = strategy_metrics(sub, edge_type, threshold, "Over")
            typer.echo(f"  {season} ({edge_type}>={threshold}) : {m}")

    typer.echo("\n--- Controle negatif Premier League (jamais poolee, jamais utilisee pour selectionner) ---")
    pl_validation_rows = build_backtest_rows(validation_ids, rodage_pool, lambda_mu_df, records_by_id, (_CONTROL_LEAGUE,))
    typer.echo(f"n_premier_league_validation_rows = {len(pl_validation_rows)}")
    pl_market_only = baseline_market_only_metrics(pl_validation_rows, "Over")
    typer.echo(f"  Baseline marche seul (PL) : {pl_market_only}")
    for edge_type, threshold in candidate_grid():
        m = strategy_metrics(pl_validation_rows, edge_type, threshold, "Over")
        ok = passes_selection_rule(m, pl_market_only) if m.get("n_bets", 0) else False
        typer.echo(f"  PL ({edge_type}>={threshold}) : {m} -> selection_rule={'OK' if ok else 'REJETE'} (INFORMATIF UNIQUEMENT - jamais active, discrimination_gate bloque BET en PL quel que soit ce resultat)")

    typer.echo("\n--- Secondaire : Under 2.5 (VALIDATION, jamais fusionne avec Over) ---")
    under_market_only = baseline_market_only_metrics(validation_rows, "Under")
    typer.echo(f"  Baseline marche seul (Under, VALIDATION) : {under_market_only}")
    for edge_type, threshold in candidate_grid():
        m = strategy_metrics(validation_rows, edge_type, threshold, "Under")
        ok = passes_selection_rule(m, under_market_only) if m.get("n_bets", 0) else False
        typer.echo(f"  Under ({edge_type}>={threshold}) : {m} -> selection_rule={'OK' if ok else 'REJETE'}")

    typer.echo("\n--- Calibration du sous-ensemble selectionnable (VALIDATION, descriptif) ---")
    for edge_type, threshold in candidate_grid():
        selected_subset = [r for r in validation_rows if would_bet(r, edge_type, threshold, "Over")]
        if selected_subset:
            mean_p = float(np.mean([r.p_model_over for r in selected_subset]))
            mean_outcome = float(np.mean([r.outcome_over for r in selected_subset]))
            typer.echo(f"  ({edge_type}>={threshold}) n={len(selected_subset)} p_model_moyen={mean_p:.4f} freq_reelle={mean_outcome:.4f} ecart={mean_outcome - mean_p:+.4f}")

    if selected is None:
        typer.echo("\nAUCUN candidat ne satisfait la regle de selection sur VALIDATION.")
        typer.echo("VERDICT : NO BET - EDGE NON VALIDE (aucun seuil retenu pour le TEST final).")
        return

    typer.echo(f"\nSeuil retenu (VALIDATION uniquement) : {selected}")
    typer.echo("--- Construction TEST (Liga+Ligue1) - EXECUTION UNIQUE ---")
    test_rows = build_backtest_rows(test_ids, validation_pool, lambda_mu_df, records_by_id, _PRIMARY_LEAGUES)
    typer.echo(f"n_test_rows exploitables = {len(test_rows)}")

    edge_type, threshold = selected
    test_metrics = strategy_metrics(test_rows, edge_type, threshold, "Over")
    market_only_test = baseline_market_only_metrics(test_rows, "Over")
    typer.echo(f"TEST - strategie candidate : {test_metrics}")
    typer.echo(f"TEST - baseline marche seul : {market_only_test}")


if __name__ == "__main__":
    typer.run(main)
