"""Consensus multi-bookmaker Max/Avg Over/Under 2.5 - apporte-t-il une
information PREDICTIVE INCREMENTALE sur Over/Under 2.5, au-dela de ce que
le moteur actuel (`poisson_simple` + correction E7/E8) possede deja,
APRES recalibration du modele de base - et au-dela de ce que B365 seul
apporte deja ?

Experience DIAGNOSTIQUE UNIQUE, protocole pre-enregistre AVANT execution :
`docs/multi_bookmaker_consensus_experiment_specification.md`. Ferme la
derniere piste non evaluee de la categorie Football-Data
(docs/final_data_strategy.md). PAS une construction de modele de
production. Ne modifie AUCUN modele existant, AUCUNE correction
E7/E8/E14/E15/E16, AUCUN gate du moteur final, N'APPELLE NI NE MODIFIE
`final_engine/`, N'ACTIVE PAS `BET`, NE FIXE PAS `min_edge_threshold`.

====================================================================
SOURCE DU SIGNAL
====================================================================
`src/sys_foot_quant/data_engine/market_odds/multi_bookmaker_over_under.py`
(INCHANGE, deja teste) - cotes Max/Avg Over/Under 2.5 D'OUVERTURE
UNIQUEMENT, extraites via `football_data_loader.FootballDataMatchRecord.
max_avg_over_under_2_5()` (deja teste, couverture 100% sur le corpus
reel - voir docstring de `football_data_loader`).

====================================================================
MODELES (figes, docs/multi_bookmaker_consensus_experiment_specification.md
section 6)
====================================================================
    A   : p_A = calibrate_prediction(poisson_simple)                         - 0 param
    C   : p_C = sigmoid(a + b*logit(p_A))                                    - 2 param - CONTROLE
    B365: p_test_B365 = sigmoid(a + b*logit(p_A) + c*logit(p_market_B365))   - 3 param - comparaison equitable
    Avg : p_test_Avg  = sigmoid(a + b*logit(p_A) + c*logit(p_market_Avg))    - 3 param - TEST PRINCIPAL
    Max : p_test_Max  = sigmoid(a + b*logit(p_A) + c*logit(p_market_Max))    - 3 param - SECONDAIRE, descriptif

Test principal : `paired_bootstrap_test` sur Brier(test_Avg) - Brier(C),
population primaire Liga+Ligue1, VALIDATION+TEST (split 40/30/30,
`run_stage10_over_under_recalibration.split_burn_in_calibration_test`,
INCHANGE).

Usage :
    python scripts/run_stage32_multi_bookmaker_consensus_incremental_information.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test  # noqa: E402
from sys_foot_quant.data_engine.market_odds.football_data_loader import load_football_data_csv  # noqa: E402
from sys_foot_quant.data_engine.market_odds.multi_bookmaker_over_under import (  # noqa: E402
    build_multi_bookmaker_over_under_dataset,
)
from sys_foot_quant.final_engine.calibration import calibrate_prediction  # noqa: E402
from sys_foot_quant.final_engine.types import ModelPrediction  # noqa: E402
from sys_foot_quant.market_engine.overround import remove_overround_proportional  # noqa: E402

_PRIMARY_MODEL = "poisson_simple"
_MIN_TRAIN_LOGISTIC = 30
_TARGET_THRESHOLD = 2.5
_MIN_GLOBAL_POOL = 30
_PRIMARY_LEAGUES = ("liga", "ligue1")

_REPO_ROOT = Path(__file__).resolve().parent.parent
_STAGE10_PATH = _REPO_ROOT / "scripts" / "run_stage10_over_under_recalibration.py"
_STAGE15_PATH = _REPO_ROOT / "scripts" / "run_stage15_e7_total_goals_distribution.py"
_STAGE16_PATH = _REPO_ROOT / "scripts" / "run_stage16_e8_walk_forward_validation.py"
_STAGE25_PATH = _REPO_ROOT / "scripts" / "run_stage25_e16_market_movement_information.py"

_FD_DIR = _REPO_ROOT / "research" / "market_odds" / "football_data" / "runs"
_US_DIR = _REPO_ROOT / "research" / "xg_feasibility" / "runs"

_DATASETS = {
    ("premier_league", "2024_25"): ("E0_2024_25.csv", "epl_2024_datesData.json"),
    ("premier_league", "2025_26"): ("E0_2025_26.csv", "epl_2025_datesData.json"),
    ("ligue1", "2024_25"): ("F1_2024_25.csv", "ligue1_2024_datesData.json"),
    ("ligue1", "2025_26"): ("F1_2025_26.csv", "ligue1_2025_datesData.json"),
    ("liga", "2024_25"): ("SP1_2024_25.csv", "liga_2024_datesData.json"),
    ("liga", "2025_26"): ("SP1_2025_26.csv", "liga_2025_datesData.json"),
}


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_stage10():
    return _load_module("run_stage10_over_under_recalibration", _STAGE10_PATH)


def _load_e7():
    return _load_module("run_stage15_e7_total_goals_distribution", _STAGE15_PATH)


def _load_e8():
    return _load_module("run_stage16_e8_walk_forward_validation", _STAGE16_PATH)


def _load_e16():
    return _load_module("run_stage25_e16_market_movement_information", _STAGE25_PATH)


def _safe_logit(p: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), eps, 1 - eps)
    return np.log(p / (1 - p))


# --------------------------------------------------------------------------
# Chargement des cotes B365/Max/Avg (multi_bookmaker_over_under, INCHANGE)
# pour les 6 (competition, saison) deja catalogues.
# --------------------------------------------------------------------------


def load_all_multi_bookmaker_records() -> dict[str, object]:
    """match_id -> MultiBookmakerOverUnderRecord, toutes competitions/
    saisons confondues."""
    out: dict[str, object] = {}
    for (league, season), (fd_name, us_name) in _DATASETS.items():
        fd_records = load_football_data_csv(_FD_DIR / fd_name, league=league, season=season)
        with open(_US_DIR / us_name) as f:
            us_raw = json.load(f)
        report = build_multi_bookmaker_over_under_dataset(league, season, us_raw, fd_records)
        for r in report.records:
            out[r.match_id] = r
    return out


def _normalized_over_prob(over_odds: float | None, under_odds: float | None) -> float | None:
    """Probabilite implicite NORMALISEE (marge retiree,
    `remove_overround_proportional`, INCHANGE) du cote "Over" - `None` si
    l'une des deux cotes est absente (jamais imputee)."""
    if over_odds is None or under_odds is None:
        return None
    normalized = remove_overround_proportional({"Over": over_odds, "Under": under_odds})
    return normalized["Over"]


# --------------------------------------------------------------------------
# Split 40/30/30 (Phase D, INCHANGEE), translittere sans modification.
# --------------------------------------------------------------------------


def tag_burn_in_validation_test(df: pd.DataFrame, stage10_module, stage8_module) -> pd.DataFrame:
    validation_ids: set[str] = set()
    test_ids: set[str] = set()
    for season, leagues in stage8_module._SEASONS.items():
        for league in leagues:
            records = stage8_module._load_records(league, season)
            v_ids, t_ids = stage10_module.split_burn_in_calibration_test(records)
            validation_ids |= v_ids
            test_ids |= t_ids

    def _tag(match_id: str) -> str:
        if match_id in validation_ids:
            return "validation"
        if match_id in test_ids:
            return "test"
        return "burn_in"

    out = df.copy()
    out["split"] = out["match_id"].map(_tag)
    return out


# --------------------------------------------------------------------------
# Construction du dataset complet (Modele A + B365/Max/Avg normalises).
# --------------------------------------------------------------------------


def build_full_dataset(e7_module, e8_module, stage8_module, multi_bk_by_match_id: dict) -> tuple[pd.DataFrame, dict[str, int]]:
    df = e7_module.build_lambda_mu_dataframe(stage8_module)
    decision_time_lookup = e8_module.build_decision_time_lookup(stage8_module)
    df["decision_time"] = df["match_id"].map(decision_time_lookup)
    df["decision_time"] = pd.to_datetime(df["decision_time"], utc=True)

    df = df.dropna(subset=["poisson_simple_lambda", "poisson_simple_mu", "decision_time"]).copy()
    df = df.sort_values("decision_time").reset_index(drop=True)

    calibration_pool = df

    p_over_2_5: list[float] = []
    p_market_b365: list[float] = []
    p_market_avg: list[float] = []
    p_market_max: list[float] = []

    for _, row in df.iterrows():
        decision_time = row["decision_time"]
        pred = ModelPrediction(
            model=_PRIMARY_MODEL, lam=float(row["poisson_simple_lambda"]), mu=float(row["poisson_simple_mu"]),
            rho=None, n_train_matches=0,
        )
        calibrated = calibrate_prediction(pred, calibration_pool, as_of_time=decision_time)
        p_over_2_5.append(calibrated.probabilities[_TARGET_THRESHOLD] if calibrated.probabilities is not None else np.nan)

        rec = multi_bk_by_match_id.get(row["match_id"])
        if rec is None:
            p_market_b365.append(np.nan)
            p_market_avg.append(np.nan)
            p_market_max.append(np.nan)
        else:
            p_market_b365.append(_normalized_over_prob(rec.b365_over_2_5, rec.b365_under_2_5) or np.nan)
            p_market_avg.append(_normalized_over_prob(rec.avg_over_2_5, rec.avg_under_2_5) or np.nan)
            p_market_max.append(_normalized_over_prob(rec.max_over_2_5, rec.max_under_2_5) or np.nan)

    df["p_over_2_5"] = p_over_2_5
    df["p_market_b365"] = p_market_b365
    df["p_market_avg"] = p_market_avg
    df["p_market_max"] = p_market_max
    df["outcome_over_2_5"] = (df["total_goals"] > _TARGET_THRESHOLD).astype(float)

    n_total = len(df)
    n_excluded = {
        "no_b365": int(df["p_market_b365"].isna().sum()),
        "no_avg": int(df["p_market_avg"].isna().sum()),
        "no_max": int(df["p_market_max"].isna().sum()),
    }
    df = df.dropna(subset=["p_over_2_5", "p_market_b365", "p_market_avg", "p_market_max"]).reset_index(drop=True)
    n_excluded["total_excluded"] = n_total - len(df)
    return df, n_excluded


def compute_model_predictions(df: pd.DataFrame, e16_module) -> pd.DataFrame:
    logit_p_a = _safe_logit(df["p_over_2_5"].to_numpy())
    logit_market_b365 = _safe_logit(df["p_market_b365"].to_numpy())
    logit_market_avg = _safe_logit(df["p_market_avg"].to_numpy())
    logit_market_max = _safe_logit(df["p_market_max"].to_numpy())
    y = df["outcome_over_2_5"].to_numpy()
    ones = np.ones(len(df))

    p_c = e16_module.walk_forward_logistic(df, lambda d: (np.column_stack([ones, logit_p_a]), y))
    p_b365 = e16_module.walk_forward_logistic(df, lambda d: (np.column_stack([ones, logit_p_a, logit_market_b365]), y))
    p_avg = e16_module.walk_forward_logistic(df, lambda d: (np.column_stack([ones, logit_p_a, logit_market_avg]), y))
    p_max = e16_module.walk_forward_logistic(df, lambda d: (np.column_stack([ones, logit_p_a, logit_market_max]), y))

    out = df.copy()
    out["p_C"] = p_c
    out["p_test_B365"] = p_b365
    out["p_test_Avg"] = p_avg
    out["p_test_Max"] = p_max
    return out


def evaluate_brier(df: pd.DataFrame, col: str) -> np.ndarray:
    return (df[col].to_numpy() - df["outcome_over_2_5"].to_numpy()) ** 2


def bootstrap_diff(df: pd.DataFrame, col_a: str, col_b: str, seed: int | None = None) -> dict:
    diffs = evaluate_brier(df, col_a) - evaluate_brier(df, col_b)
    return paired_bootstrap_test(diffs, n_resamples=10000, seed=seed)


def classify_verdict(primary_boot: dict, n_primary: int, season_mean_diffs: list[float], season_ns: list[int]) -> str:
    if n_primary < _MIN_GLOBAL_POOL:
        return "DONNEES INSUFFISANTES"
    primary_favorable = primary_boot["ci_high"] < 0.0
    if not primary_favorable:
        return "SIGNAL NON DEMONTRE"
    powered_seasons = [(d, n) for d, n in zip(season_mean_diffs, season_ns) if n >= _MIN_GLOBAL_POOL]
    if len(powered_seasons) < 2:
        return "DONNEES INSUFFISANTES"
    same_direction = all(d < 0.0 for d, _ in powered_seasons)
    return "SIGNAL DEMONTRE" if same_direction else "DONNEES INSUFFISANTES"


def main() -> None:
    stage10 = _load_stage10()
    stage8 = stage10._load_stage8()
    e7 = _load_e7()
    e8 = _load_e8()
    e16 = _load_e16()

    print("=== Consensus multi-bookmaker Max/Avg O/U 2.5 - chargement ===")
    multi_bk_by_match_id = load_all_multi_bookmaker_records()
    print(f"n matchs avec B365/Max/Avg apparies (6 competition x saison) : {len(multi_bk_by_match_id)}")

    print("=== Construction du dataset complet (Modele A + marches normalises) ===")
    df, n_excluded = build_full_dataset(e7, e8, stage8, multi_bk_by_match_id)
    print(f"n corpus final (avec p_A, p_market_b365/avg/max) : {len(df)}")
    print(f"exclusions avant filtrage final : {n_excluded}")

    print("\n=== Couverture par championnat x saison ===")
    for (league, season) in _DATASETS:
        n = sum(1 for r in multi_bk_by_match_id.values() if r.league == league and r.season == season)
        print(f"  {league:<16} {season}: n_apparies={n}")

    df = tag_burn_in_validation_test(df, stage10, stage8)
    print(f"\nsplit: {df['split'].value_counts().to_dict()}")

    print("=== Calcul des modeles (walk-forward) ===")
    df = compute_model_predictions(df, e16)

    eval_pool_all = df[df["split"].isin(["validation", "test"])].dropna(
        subset=["p_C", "p_test_B365", "p_test_Avg", "p_test_Max"]
    ).reset_index(drop=True)
    eval_pool = eval_pool_all[eval_pool_all["league"].isin(_PRIMARY_LEAGUES)].reset_index(drop=True)
    pl_pool = eval_pool_all[eval_pool_all["league"] == "premier_league"].reset_index(drop=True)

    print(f"\nn evaluable (VALIDATION+TEST, toutes ligues) = {len(eval_pool_all)}")
    print(f"n population primaire (Liga+Ligue1, VALIDATION+TEST) = {len(eval_pool)}")
    print(f"n Premier League (controle, jamais poole) = {len(pl_pool)}")

    print("\n=== Brier (population primaire) ===")
    brier_a = evaluate_brier(eval_pool, "p_over_2_5").mean()
    brier_c = evaluate_brier(eval_pool, "p_C").mean()
    brier_b365 = evaluate_brier(eval_pool, "p_test_B365").mean()
    brier_avg = evaluate_brier(eval_pool, "p_test_Avg").mean()
    brier_max = evaluate_brier(eval_pool, "p_test_Max").mean()
    print(f"Brier A (brut)                       = {brier_a:.4f}")
    print(f"Brier C (recalibre, CONTROLE)         = {brier_c:.4f}")
    print(f"Brier test_B365 (comparaison equitable) = {brier_b365:.4f}")
    print(f"Brier test_Avg (TEST PRINCIPAL)       = {brier_avg:.4f}")
    print(f"Brier test_Max (SECONDAIRE)           = {brier_max:.4f}")
    print(f"Delta Brier (test_Avg - C)  = {brier_avg - brier_c:+.4f}  (negatif = Avg meilleur que C)")
    print(f"Delta Brier (test_B365 - C) = {brier_b365 - brier_c:+.4f}  (negatif = B365 meilleur que C)")

    print("\n=== CONTROLE DE RECALIBRATION (A vs C) ===")
    boot_a_c = bootstrap_diff(eval_pool, "p_C", "p_over_2_5", seed=20)
    print(f"  {boot_a_c}")

    print("\n=== Comparaison equitable : B365 vs C (le marche deja utilise en production aide-t-il) ===")
    boot_b365_c = bootstrap_diff(eval_pool, "p_test_B365", "p_C", seed=21)
    print(f"  {boot_b365_c}")

    print("\n=== TEST PRINCIPAL : Avg vs C ===")
    primary_boot = bootstrap_diff(eval_pool, "p_test_Avg", "p_C", seed=0)
    print(f"  {primary_boot}")

    print("\n=== Avg vs B365 (le consensus elargi fait-il mieux que B365 seul) ===")
    boot_avg_b365 = bootstrap_diff(eval_pool, "p_test_Avg", "p_test_B365", seed=22)
    print(f"  {boot_avg_b365}")

    print("\n=== Replication par saison (Avg vs C, population primaire) ===")
    season_mean_diffs: list[float] = []
    season_ns: list[int] = []
    for season in sorted(eval_pool["season"].unique()):
        sub = eval_pool[eval_pool["season"] == season]
        n = len(sub)
        season_ns.append(n)
        if n >= _MIN_GLOBAL_POOL:
            b = bootstrap_diff(sub, "p_test_Avg", "p_C", seed=11)
            season_mean_diffs.append(b["mean_diff"])
            print(f"  saison={season} n={n}: {b}")
        else:
            season_mean_diffs.append(float("nan"))
            print(f"  saison={season} n={n}: sous-puissant")

    print("\n=== Robustesse par championnat (Avg vs C) ===")
    for league in _PRIMARY_LEAGUES:
        sub = eval_pool[eval_pool["league"] == league]
        if len(sub) >= _MIN_GLOBAL_POOL:
            b = bootstrap_diff(sub, "p_test_Avg", "p_C", seed=10)
            print(f"  championnat={league} n={len(sub)}: {b}")
        else:
            print(f"  championnat={league} n={len(sub)}: sous-puissant")

    print("\n=== Controle negatif Premier League (Avg vs C, jamais poole) ===")
    if len(pl_pool) >= _MIN_GLOBAL_POOL:
        boot_pl = bootstrap_diff(pl_pool, "p_test_Avg", "p_C", seed=30)
        print(f"  n={len(pl_pool)}: {boot_pl}")
    else:
        print(f"  n={len(pl_pool)}: sous-puissant")

    print("\n=== Effet secondaire descriptif : Max vs C (reserve d'overround, jamais fusionne au verdict) ===")
    boot_max_c = bootstrap_diff(eval_pool, "p_test_Max", "p_C", seed=40)
    print(f"  {boot_max_c}")

    print("\n=== Marge/dispersion (descriptif, jamais confondu avec un signal predictif) ===")
    overround_b365 = [1.0 / r.b365_over_2_5 + 1.0 / r.b365_under_2_5 for r in multi_bk_by_match_id.values() if r.has_complete_b365]
    overround_avg = [1.0 / r.avg_over_2_5 + 1.0 / r.avg_under_2_5 for r in multi_bk_by_match_id.values() if r.has_complete_avg]
    overround_max = [1.0 / r.max_over_2_5 + 1.0 / r.max_under_2_5 for r in multi_bk_by_match_id.values() if r.has_complete_max]
    print(f"  overround B365 : moyenne={np.mean(overround_b365):.4f}")
    print(f"  overround Avg  : moyenne={np.mean(overround_avg):.4f}")
    print(f"  overround Max  : moyenne={np.mean(overround_max):.4f} (min={np.min(overround_max):.4f})")

    verdict = classify_verdict(primary_boot, len(eval_pool), season_mean_diffs, season_ns)
    print(f"\n=== VERDICT (test_Avg vs C) : {verdict} ===")


if __name__ == "__main__":
    main()
