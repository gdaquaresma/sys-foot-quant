"""Congestion intra-championnat (jours de repos) - apporte-t-elle une
information PREDICTIVE INCREMENTALE sur Over/Under 2.5, au-dela de ce que
le moteur actuel (`poisson_simple` + correction E7/E8) possede deja,
APRES recalibration du modele de base ?

Experience DIAGNOSTIQUE UNIQUE, protocole pre-enregistre AVANT execution :
`docs/fixture_congestion_experiment_specification.md`. PAS une
construction de modele de production. Ne modifie AUCUN modele existant,
AUCUNE correction E7/E8/E14/E15/E16, AUCUN gate du moteur final, N'APPELLE
NI NE MODIFIE `final_engine/`, N'ACTIVE PAS `BET`, NE FIXE PAS
`min_edge_threshold`.

====================================================================
SOURCE DU SIGNAL DE CONGESTION
====================================================================
`src/sys_foot_quant/data_engine/market_odds/fixture_congestion.py`
(INCHANGE, deja teste - 18 tests unitaires + 11 tests leakage) -
`home_rest_days`/`away_rest_days` calcules EXCLUSIVEMENT depuis
`match_catalog.list_matches(competition, season)` (deja catalogue,
aucune acquisition). Variante VOLONTAIREMENT PARTIELLE (intra-
championnat uniquement, coupes/Europe absentes du corpus - voir
docstring du module et section 1 du protocole).

====================================================================
MODELES A/B/C/D/E (figes, docs/fixture_congestion_experiment_specification.md
section 6/6bis)
====================================================================
    A : p_A = calibrate_prediction(poisson_simple)                          - 0 param
    B : p_B = sigmoid(a0 + 1*logit(p_A) + c1*home_rest + c2*away_rest)      - offset, diagnostic uniquement
    C : p_C = sigmoid(a + b*logit(p_A))                                     - 2 param - CONTROLE
    D : p_D = sigmoid(a + b*logit(p_A) + c1*home_rest + c2*away_rest)       - 4 param - TEST PRINCIPAL
    E : p_E = sigmoid(a + b*logit(p_A) + c*rest_days_diff)                  - 3 param - SECONDAIRE, descriptif

Test principal (section 6/7 du protocole) : `paired_bootstrap_test` sur
Brier(D) - Brier(C), population primaire Liga+Ligue1 (discrimination
demontree E4/E11/E15), VALIDATION+TEST (split 40/30/30 REUTILISE de
`run_stage10_over_under_recalibration.split_burn_in_calibration_test`,
INCHANGE). Premiere League analysee separement comme controle, jamais
poolee dans la selection - meme convention que Phase D/K.

Usage :
    python scripts/run_stage31_fixture_congestion_incremental_information.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test  # noqa: E402
from sys_foot_quant.data_engine.market_odds import match_catalog  # noqa: E402
from sys_foot_quant.data_engine.market_odds.fixture_congestion import (  # noqa: E402
    congestion_dataset_for_season,
)
from sys_foot_quant.final_engine.calibration import calibrate_prediction  # noqa: E402
from sys_foot_quant.final_engine.types import ModelPrediction  # noqa: E402

_PRIMARY_MODEL = "poisson_simple"
_MIN_TRAIN_LOGISTIC = 30  # E16, REUTILISE - meme convention que Phases F/G/H/K
_TARGET_THRESHOLD = 2.5  # Over 2.5, DEFAULT_OU_THRESHOLDS - meme cible qu'E11/E14/E16/Phases F/G/H/K
_MIN_GLOBAL_POOL = 30
_PRIMARY_LEAGUES = ("liga", "ligue1")  # discrimination demontree E4/E11/E15 - meme population primaire que Phase D/K

_REPO_ROOT = Path(__file__).resolve().parent.parent
_STAGE10_PATH = _REPO_ROOT / "scripts" / "run_stage10_over_under_recalibration.py"
_STAGE15_PATH = _REPO_ROOT / "scripts" / "run_stage15_e7_total_goals_distribution.py"
_STAGE16_PATH = _REPO_ROOT / "scripts" / "run_stage16_e8_walk_forward_validation.py"
_STAGE25_PATH = _REPO_ROOT / "scripts" / "run_stage25_e16_market_movement_information.py"

_LEAGUES_SEASONS = [
    ("premier_league", "2024_25"),
    ("premier_league", "2025_26"),
    ("ligue1", "2024_25"),
    ("ligue1", "2025_26"),
    ("liga", "2024_25"),
    ("liga", "2025_26"),
]


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


# --------------------------------------------------------------------------
# Regression logistique a offset (meme generalisation MINIMALE que Phase K,
# translitteree sans modification) - le terme `offset` (ici `logit(p_A)`) a
# un coefficient FIXE a 1, jamais reestime - seuls les coefficients de `X`
# sont libres.
# --------------------------------------------------------------------------


def fit_logistic_with_offset(offset: np.ndarray, X: np.ndarray, y: np.ndarray) -> np.ndarray:
    offset = np.asarray(offset, dtype=float)
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)

    def neg_log_lik(beta: np.ndarray) -> float:
        z = offset + X @ beta
        return float(np.mean(np.logaddexp(0.0, -z) * y + np.logaddexp(0.0, z) * (1 - y)))

    beta0 = np.zeros(X.shape[1])
    res = minimize(neg_log_lik, beta0, method="BFGS")
    return res.x


def predict_logistic_with_offset(offset: np.ndarray, beta: np.ndarray, X: np.ndarray) -> np.ndarray:
    offset = np.asarray(offset, dtype=float)
    X = np.asarray(X, dtype=float)
    z = offset + X @ beta
    return 1.0 / (1.0 + np.exp(-z))


def walk_forward_logistic_with_offset(
    offset_all: np.ndarray, X_all: np.ndarray, y_all: np.ndarray, min_train: int = _MIN_TRAIN_LOGISTIC
) -> np.ndarray:
    """Identique en structure a `walk_forward_logistic` (E16, INCHANGEE) :
    pour chaque ligne, ajuste EXCLUSIVEMENT sur les lignes PRECEDENTES
    (deja triees par `decision_time` en amont par l'appelant), jamais la
    ligne elle-meme ni une ligne posterieure."""
    n = len(y_all)
    preds = np.full(n, np.nan)
    for i in range(n):
        if i < min_train:
            continue
        beta = fit_logistic_with_offset(offset_all[:i], X_all[:i], y_all[:i])
        preds[i] = predict_logistic_with_offset(offset_all[i : i + 1], beta, X_all[i : i + 1])[0]
    return preds


def _safe_logit(p: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), eps, 1 - eps)
    return np.log(p / (1 - p))


# --------------------------------------------------------------------------
# Chargement de la congestion (fixture_congestion, INCHANGE) pour les 6
# (competition, saison) deja catalogues - aucune acquisition, aucune
# lecture de fichier au-dela de ce que match_catalog fait deja.
# --------------------------------------------------------------------------


def load_all_congestion_features() -> dict[str, tuple[float | None, float | None]]:
    """match_id -> (home_rest_days, away_rest_days), toutes competitions/
    saisons confondues (les 6 deja catalogues par `match_catalog`)."""
    out: dict[str, tuple[float | None, float | None]] = {}
    for competition, season in _LEAGUES_SEASONS:
        matches = match_catalog.list_matches(competition, season)
        features = congestion_dataset_for_season(competition, matches)
        for f in features:
            out[f.match_id] = (f.home_rest_days, f.away_rest_days)
    return out


# --------------------------------------------------------------------------
# Split 40/30/30 (Phase D, `split_burn_in_calibration_test`, INCHANGEE),
# translittere sans modification de Phase K.
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
# Construction du dataset complet (Modele A + congestion), UNE SEULE PASSE
# walk-forward sur le corpus complet trie par decision_time - le split
# 40/30/30 ne sert qu'a ETIQUETER les lignes pour l'evaluation, jamais a
# limiter l'historique utilise par le walk-forward lui-meme (meme principe
# que Phase K, section 5 du protocole).
# --------------------------------------------------------------------------


def build_full_dataset(
    e7_module, e8_module, stage8_module, congestion_by_match_id: dict
) -> tuple[pd.DataFrame, int]:
    df = e7_module.build_lambda_mu_dataframe(stage8_module)
    decision_time_lookup = e8_module.build_decision_time_lookup(stage8_module)
    df["decision_time"] = df["match_id"].map(decision_time_lookup)
    df["decision_time"] = pd.to_datetime(df["decision_time"], utc=True)

    df = df.dropna(subset=["poisson_simple_lambda", "poisson_simple_mu", "decision_time"]).copy()
    df = df.sort_values("decision_time").reset_index(drop=True)

    calibration_pool = df  # filtre interne par decision_time < as_of_time (fit_scale_correction_as_of)

    p_over_2_5: list[float] = []
    home_rest: list[float] = []
    away_rest: list[float] = []
    has_congestion: list[bool] = []

    for _, row in df.iterrows():
        decision_time = row["decision_time"]
        pred = ModelPrediction(
            model=_PRIMARY_MODEL, lam=float(row["poisson_simple_lambda"]), mu=float(row["poisson_simple_mu"]),
            rho=None, n_train_matches=0,
        )
        calibrated = calibrate_prediction(pred, calibration_pool, as_of_time=decision_time)
        p_over_2_5.append(calibrated.probabilities[_TARGET_THRESHOLD] if calibrated.probabilities is not None else np.nan)

        cong = congestion_by_match_id.get(row["match_id"])
        if cong is not None and cong[0] is not None and cong[1] is not None:
            home_rest.append(cong[0])
            away_rest.append(cong[1])
            has_congestion.append(True)
        else:
            home_rest.append(np.nan)
            away_rest.append(np.nan)
            has_congestion.append(False)

    df["p_over_2_5"] = p_over_2_5
    df["home_rest_days"] = home_rest
    df["away_rest_days"] = away_rest
    df["has_congestion"] = has_congestion
    df["outcome_over_2_5"] = (df["total_goals"] > _TARGET_THRESHOLD).astype(float)

    n_total = len(df)
    df = df.dropna(subset=["p_over_2_5", "home_rest_days", "away_rest_days"]).reset_index(drop=True)
    n_excluded_insufficient_rest_history = n_total - len(df)
    return df, n_excluded_insufficient_rest_history


def compute_model_predictions(df: pd.DataFrame, e16_module) -> pd.DataFrame:
    """Calcule p_B/p_C/p_D/p_E en walk-forward sur TOUT le corpus (deja
    trie par decision_time) - le rodage sert de pool d'historique, jamais
    evalue lui-meme (filtre applique par l'appelant via `split`)."""
    logit_p_a = _safe_logit(df["p_over_2_5"].to_numpy())
    home_rest = df["home_rest_days"].to_numpy()
    away_rest = df["away_rest_days"].to_numpy()
    rest_diff = home_rest - away_rest
    y = df["outcome_over_2_5"].to_numpy()
    ones = np.ones(len(df))

    p_b = walk_forward_logistic_with_offset(logit_p_a, np.column_stack([ones, home_rest, away_rest]), y)
    p_c = e16_module.walk_forward_logistic(df, lambda d: (np.column_stack([ones, logit_p_a]), y))
    p_d = e16_module.walk_forward_logistic(
        df, lambda d: (np.column_stack([ones, logit_p_a, home_rest, away_rest]), y)
    )
    p_e = e16_module.walk_forward_logistic(df, lambda d: (np.column_stack([ones, logit_p_a, rest_diff]), y))

    out = df.copy()
    out["p_B"] = p_b
    out["p_C"] = p_c
    out["p_D"] = p_d
    out["p_E"] = p_e
    return out


def evaluate_brier(df: pd.DataFrame, col: str) -> np.ndarray:
    return (df[col].to_numpy() - df["outcome_over_2_5"].to_numpy()) ** 2


def bootstrap_diff(df: pd.DataFrame, col_a: str, col_b: str, seed: int | None = None) -> dict:
    diffs = evaluate_brier(df, col_a) - evaluate_brier(df, col_b)
    return paired_bootstrap_test(diffs, n_resamples=10000, seed=seed)


# --------------------------------------------------------------------------
# Verdict (docs/fixture_congestion_experiment_specification.md section 10)
# - grille figee, mecanique, 3 valeurs autorisees uniquement.
# --------------------------------------------------------------------------


def classify_verdict(primary_boot: dict, n_primary: int, season_mean_diffs: list[float], season_ns: list[int]) -> str:
    if n_primary < _MIN_GLOBAL_POOL:
        return "DONNEES INSUFFISANTES"

    primary_favorable = primary_boot["ci_high"] < 0.0  # Brier(D) - Brier(C) entierement < 0 -> D meilleur que C
    if not primary_favorable:
        return "SIGNAL NON DEMONTRE"

    powered_seasons = [(d, n) for d, n in zip(season_mean_diffs, season_ns) if n >= _MIN_GLOBAL_POOL]
    if len(powered_seasons) < 2:
        return "DONNEES INSUFFISANTES"  # pas assez de sous-groupes suffisamment peuples pour verifier la replication
    same_direction = all(d < 0.0 for d, _ in powered_seasons)
    if same_direction:
        return "SIGNAL DEMONTRE"
    return "DONNEES INSUFFISANTES"  # direction instable entre sous-groupes temporels


# --------------------------------------------------------------------------
# main() - execution reelle unique.
# --------------------------------------------------------------------------


def main() -> None:
    stage10 = _load_stage10()
    stage8 = stage10._load_stage8()
    e7 = _load_e7()
    e8 = _load_e8()
    e16 = _load_e16()

    print("=== Brique 1 - chargement de la congestion intra-championnat (fixture_congestion) ===")
    congestion_by_match_id = load_all_congestion_features()
    print(f"n matchs catalogues (6 competition x saison) : {len(congestion_by_match_id)}")

    print("=== Construction du dataset complet (Modele A + congestion) ===")
    df, n_excluded_insufficient_rest_history = build_full_dataset(e7, e8, stage8, congestion_by_match_id)
    print(f"n corpus final (avec p_A, home_rest_days, away_rest_days) : {len(df)}")
    print(f"n exclus pour historique de repos insuffisant (1er match de saison d'une equipe) : {n_excluded_insufficient_rest_history}")

    print("=== Distribution des jours de repos (corpus exploitable) ===")
    for col in ("home_rest_days", "away_rest_days"):
        s = df[col]
        print(
            f"  {col}: n={len(s)} moyenne={s.mean():.2f} mediane={s.median():.2f} "
            f"min={s.min():.2f} p25={s.quantile(0.25):.2f} p75={s.quantile(0.75):.2f} max={s.max():.2f}"
        )

    df = tag_burn_in_validation_test(df, stage10, stage8)
    print(df["split"].value_counts().to_dict())

    print("=== Calcul des modeles B/C/D/E (walk-forward) ===")
    df = compute_model_predictions(df, e16)

    eval_pool_all = df[df["split"].isin(["validation", "test"])].dropna(subset=["p_C", "p_D", "p_E"]).reset_index(drop=True)
    eval_pool = eval_pool_all[eval_pool_all["league"].isin(_PRIMARY_LEAGUES)].reset_index(drop=True)
    pl_pool = eval_pool_all[eval_pool_all["league"] == "premier_league"].reset_index(drop=True)

    print(f"\nn evaluable (VALIDATION+TEST, toutes ligues) = {len(eval_pool_all)}")
    print(f"n population primaire (Liga+Ligue1, VALIDATION+TEST) = {len(eval_pool)}")
    print(f"n Premier League (controle, jamais poole) = {len(pl_pool)}")

    print("\n=== Performance baseline vs baseline+congestion (population primaire) ===")
    brier_a = evaluate_brier(eval_pool, "p_over_2_5").mean()
    brier_b = evaluate_brier(eval_pool, "p_B").mean()
    brier_c = evaluate_brier(eval_pool, "p_C").mean()
    brier_d = evaluate_brier(eval_pool, "p_D").mean()
    brier_e = evaluate_brier(eval_pool, "p_E").mean()
    print(f"Brier A (brut)              = {brier_a:.4f}")
    print(f"Brier B (naif+congestion)   = {brier_b:.4f}  (diagnostic, offset)")
    print(f"Brier C (recalibre, CONTROLE) = {brier_c:.4f}")
    print(f"Brier D (recalibre+congestion, TEST PRINCIPAL) = {brier_d:.4f}")
    print(f"Brier E (recalibre+rest_days_diff, SECONDAIRE) = {brier_e:.4f}")
    print(f"Delta Brier (D - C) = {brier_d - brier_c:+.4f}  (negatif = D meilleur que C)")

    print("\n=== CONTROLE DE RECALIBRATION (section 8 du protocole) ===")
    boot_a_c = bootstrap_diff(eval_pool, "p_C", "p_over_2_5", seed=20)
    print(f"  A vs C (recalibration seule, Brier C - Brier A) : {boot_a_c}")
    print("  -> si cet effet est deja grand, toute amelioration D-C doit lui etre comparee, jamais confondue avec lui.")

    print("\n=== TEST PRINCIPAL : Brier(D) - Brier(C), population primaire ===")
    primary_boot = bootstrap_diff(eval_pool, "p_D", "p_C", seed=0)
    print(f"  {primary_boot}")

    print("\n=== Replication par saison (VALIDATION+TEST, population primaire) ===")
    season_mean_diffs: list[float] = []
    season_ns: list[int] = []
    for season in sorted(eval_pool["season"].unique()):
        sub = eval_pool[eval_pool["season"] == season]
        n = len(sub)
        season_ns.append(n)
        if n >= _MIN_GLOBAL_POOL:
            b = bootstrap_diff(sub, "p_D", "p_C", seed=11)
            season_mean_diffs.append(b["mean_diff"])
            print(f"  saison={season} n={n}: {b}")
        else:
            season_mean_diffs.append(float("nan"))
            print(f"  saison={season} n={n}: sous-puissant (< {_MIN_GLOBAL_POOL}), non evalue")

    print("\n=== Robustesse par championnat (population primaire, diagnostic) ===")
    for league in _PRIMARY_LEAGUES:
        sub = eval_pool[eval_pool["league"] == league]
        if len(sub) >= _MIN_GLOBAL_POOL:
            b = bootstrap_diff(sub, "p_D", "p_C", seed=10)
            print(f"  championnat={league} n={len(sub)}: {b}")
        else:
            print(f"  championnat={league} n={len(sub)}: sous-puissant")

    print("\n=== Controle negatif Premier League (jamais poole, section 2 du protocole) ===")
    if len(pl_pool) >= _MIN_GLOBAL_POOL:
        boot_pl = bootstrap_diff(pl_pool, "p_D", "p_C", seed=30)
        print(f"  n={len(pl_pool)}: {boot_pl}")
    else:
        print(f"  n={len(pl_pool)}: sous-puissant, non evalue")

    print("\n=== Effet secondaire descriptif : rest_days_diff (Brier(E) - Brier(C), section 6bis) ===")
    boot_e_c = bootstrap_diff(eval_pool, "p_E", "p_C", seed=40)
    print(f"  {boot_e_c}")
    print("  -> rapporte separement, jamais fusionne avec le verdict primaire (D vs C).")

    print("\n=== Effet separe domicile/exterieur (diagnostic, regression pleine NON walk-forward) ===")
    logit_p_a_eval = _safe_logit(eval_pool["p_over_2_5"].to_numpy())
    home_rest_eval = eval_pool["home_rest_days"].to_numpy()
    away_rest_eval = eval_pool["away_rest_days"].to_numpy()
    beta_full = e16.fit_logistic(
        np.column_stack([np.ones(len(eval_pool)), logit_p_a_eval, home_rest_eval, away_rest_eval]),
        eval_pool["outcome_over_2_5"].to_numpy(),
    )
    print(f"  coefficient home_rest_days (regression pleine, diagnostic uniquement) = {beta_full[2]:.6f}")
    print(f"  coefficient away_rest_days (regression pleine, diagnostic uniquement) = {beta_full[3]:.6f}")
    corr_home_away = float(np.corrcoef(home_rest_eval, away_rest_eval)[0, 1])
    print(f"  correlation(home_rest_days, away_rest_days) sur la population propre = {corr_home_away:.4f}")

    verdict = classify_verdict(primary_boot, len(eval_pool), season_mean_diffs, season_ns)
    print(f"\n=== VERDICT : {verdict} ===")


if __name__ == "__main__":
    main()
