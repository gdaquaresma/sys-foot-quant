"""Phase K - l'ecart de rating Elo pre-match (ClubElo) apporte-t-il une
information PREDICTIVE INCREMENTALE sur Over/Under 2.5, au-dela de ce que
le moteur actuel (`poisson_simple` + correction E7/E8) possede deja,
APRES recalibration du modele de base ?

Experience DIAGNOSTIQUE UNIQUE (docs/elo_experiment_specification.md) -
PAS une construction de modele de production. Ne modifie AUCUN modele
existant, AUCUNE correction E7/E8/E14/E15/E16, AUCUN gate du moteur
final, N'ACTIVE PAS `BET`, NE FIXE PAS `min_edge_threshold`.

====================================================================
SOURCE DES DONNEES ELO (option (b) - docs/elo_experiment_specification.md
section 0bis/annexe archive)
====================================================================
`clubelo.com`/`api.clubelo.com` etaient inaccessibles (timeout constate
independamment par l'utilisateur et par cet environnement) au moment de
cette phase. Utilise a la place l'archive quotidienne publique
(depot GitHub `tonyelhabr/club-rankings`), filtree aux 67 clubs des 3
championnats deja couverts
(`research/market_odds/clubelo/runs/clubelo_daily_archive.csv`), ingeree
via `elo_archive_ingest.ingest_daily_archive` (reconstruction de fenetres
[From,To] propres a partir du journal brut de scrapes quotidiens, valeur
retenue = PREMIERE observation par fenetre - jamais une revision
ulterieure, cf. docstring du module). Mapping d'equipes verifie a la
main par l'utilisateur contre le site clubelo.com en direct
(`elo_team_mapping.py`, `MAPPING_VERIFIED_AGAINST_REAL_DATA=True`), avec
traduction des 3 noms specifiques a cette archive
(`elo_archive_ingest.ARCHIVE_NAME_TO_LIVE_NAME`).

**Restriction de corpus, decidee explicitement par l'utilisateur** :
l'archive s'arrete au 2026-01-14 - tout match dont `decision_time` tombe
apres cette date est EXCLU (compte explicitement, jamais impute). Ceci
retire ~45-50% de la saison 2025/26 (mais aucune saison 2024/25).

====================================================================
MODELES A/B/C/D (figes, docs/elo_experiment_specification.md section 6)
====================================================================
    A : p_A = calibrate_prediction(poisson_simple)              - 0 param
    B : p_B = sigmoid(a0 + 1*logit(p_A) + c*elo_diff)           - offset, 2 param (a0, c)
    C : p_C = sigmoid(a + b*logit(p_A))                         - 2 param (a, b) - CONTROLE
    D : p_D = sigmoid(a + b*logit(p_A) + c*elo_diff)            - 3 param (a, b, c) - TEST

Test principal (docs/elo_experiment_specification.md section 9) :
`paired_bootstrap_test` sur Brier(D) - Brier(C), population VALIDATION+TEST
(split 40/30/30 REUTILISE de `run_stage10_over_under_recalibration.
split_burn_in_calibration_test`, INCHANGE), avec VALIDATION et TEST
rapportes separement comme controle de robustesse temporelle obligatoire.

Usage :
    python scripts/run_stage30_phase_k_elo_incremental_information.py
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test  # noqa: E402
from sys_foot_quant.data_engine.market_odds.elo_archive_ingest import (  # noqa: E402
    ingest_daily_archive,
    load_daily_archive_rows,
)
from sys_foot_quant.data_engine.market_odds.elo_join import build_elo_dataset  # noqa: E402
from sys_foot_quant.data_engine.market_odds.football_data_loader import load_football_data_csv  # noqa: E402
from sys_foot_quant.final_engine.calibration import calibrate_prediction  # noqa: E402
from sys_foot_quant.final_engine.types import ModelPrediction  # noqa: E402

_PRIMARY_MODEL = "poisson_simple"
_MIN_TRAIN_LOGISTIC = 30  # E16, REUTILISE - meme convention que Phases F/G/H
_TARGET_THRESHOLD = 2.5  # Over 2.5, DEFAULT_OU_THRESHOLDS - meme cible qu'E11/E14/E16/Phases F/G/H
_MIN_GLOBAL_POOL = 30

# Derniere date couverte par l'archive ClubElo (docs/elo_experiment_specification.md
# annexe archive) - LOCKED avant execution, jamais ajustee apres observation.
_CORPUS_CUTOFF_DATE = date(2026, 1, 14)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_FD_DIR = _REPO_ROOT / "research" / "market_odds" / "football_data" / "runs"
_US_DIR = _REPO_ROOT / "research" / "xg_feasibility" / "runs"
_ELO_ARCHIVE_PATH = _REPO_ROOT / "research" / "market_odds" / "clubelo" / "runs" / "clubelo_daily_archive.csv"

_DATASETS = {
    ("premier_league", "2024_25"): ("E0_2024_25.csv", "epl_2024_datesData.json"),
    ("premier_league", "2025_26"): ("E0_2025_26.csv", "epl_2025_datesData.json"),
    ("ligue1", "2024_25"): ("F1_2024_25.csv", "ligue1_2024_datesData.json"),
    ("ligue1", "2025_26"): ("F1_2025_26.csv", "ligue1_2025_datesData.json"),
    ("liga", "2024_25"): ("SP1_2024_25.csv", "liga_2024_datesData.json"),
    ("liga", "2025_26"): ("SP1_2025_26.csv", "liga_2025_datesData.json"),
}

_STAGE10_PATH = Path(__file__).resolve().parent / "run_stage10_over_under_recalibration.py"
_STAGE15_PATH = Path(__file__).resolve().parent / "run_stage15_e7_total_goals_distribution.py"
_STAGE16_PATH = Path(__file__).resolve().parent / "run_stage16_e8_walk_forward_validation.py"
_STAGE25_PATH = Path(__file__).resolve().parent / "run_stage25_e16_market_movement_information.py"


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
# Regression logistique a offset (docs/elo_experiment_specification.md
# section 6) - generalisation MINIMALE de `fit_logistic`/`predict_logistic`
# (E16, INCHANGEES) : le terme `offset` (ici `logit(p_A)`) a un coefficient
# FIXE a 1, jamais reestime - seuls les coefficients de `X` sont libres.
# Si `offset` est un vecteur de zeros, `fit_logistic_with_offset` reproduit
# EXACTEMENT `fit_logistic` (verifie par un test dedie).
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


# --------------------------------------------------------------------------
# Chargement des donnees Elo reelles (archive, option b)
# --------------------------------------------------------------------------


def load_elo_ratings_by_club() -> dict[str, list]:
    if not _ELO_ARCHIVE_PATH.exists():
        raise FileNotFoundError(
            f"{_ELO_ARCHIVE_PATH} n'existe pas - archive ClubElo non presente dans ce depot."
        )
    raw_rows = load_daily_archive_rows(str(_ELO_ARCHIVE_PATH))
    report = ingest_daily_archive(raw_rows)
    return report.ratings_by_live_name


def load_all_elo_records(elo_ratings_by_club: dict[str, list]) -> tuple[dict[str, object], dict]:
    """match_id -> EloMatchRecord, tous championnats/saisons confondus,
    plus les rapports de jointure par championnat x saison (couverture,
    exclusions - docs/elo_experiment_specification.md section 3)."""
    out: dict[str, object] = {}
    reports: dict[tuple[str, str], object] = {}
    for (league, season), (fd_name, us_name) in _DATASETS.items():
        fd_records = load_football_data_csv(_FD_DIR / fd_name, league=league, season=season)
        import json

        with open(_US_DIR / us_name) as f:
            us_raw = json.load(f)
        report = build_elo_dataset(league, season, us_raw, fd_records, elo_ratings_by_club)
        reports[(league, season)] = report
        for r in report.records:
            out[r.match_id] = r
    return out, reports


# --------------------------------------------------------------------------
# Split 40/30/30 (Phase D, `split_burn_in_calibration_test`, INCHANGEE) -
# applique par championnat x saison, docs/elo_experiment_specification.md
# section 5.
# --------------------------------------------------------------------------


def tag_burn_in_validation_test(df: pd.DataFrame, stage10_module, stage8_module) -> pd.DataFrame:
    """Ajoute une colonne `split` (`burn_in`/`validation`/`test`) a `df`,
    calculee PAR CHAMPIONNAT x SAISON via `split_burn_in_calibration_test`
    (INCHANGEE). `df` doit deja porter `match_id`/`league`/`season`."""
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
# Construction du dataset complet (Modele A + Elo), UNE SEULE PASSE
# walk-forward sur le corpus complet trie par decision_time (le split
# 40/30/30 ne sert qu'a ETIQUETER les lignes pour l'evaluation, jamais a
# limiter l'historique utilise par le walk-forward lui-meme - section 5
# du protocole).
# --------------------------------------------------------------------------


def build_full_dataset(e7_module, e8_module, stage8_module, elo_by_match_id: dict) -> tuple[pd.DataFrame, int]:
    df = e7_module.build_lambda_mu_dataframe(stage8_module)
    decision_time_lookup = e8_module.build_decision_time_lookup(stage8_module)
    df["decision_time"] = df["match_id"].map(decision_time_lookup)
    df["decision_time"] = pd.to_datetime(df["decision_time"], utc=True)

    df = df.dropna(subset=["poisson_simple_lambda", "poisson_simple_mu", "decision_time"]).copy()
    df = df.sort_values("decision_time").reset_index(drop=True)

    calibration_pool = df  # filtre interne par decision_time < as_of_time (fit_scale_correction_as_of)

    p_over_2_5: list[float] = []
    elo_diff: list[float] = []
    elo_home: list[float] = []
    elo_away: list[float] = []
    has_elo: list[bool] = []

    for _, row in df.iterrows():
        decision_time = row["decision_time"]
        pred = ModelPrediction(
            model=_PRIMARY_MODEL, lam=float(row["poisson_simple_lambda"]), mu=float(row["poisson_simple_mu"]),
            rho=None, n_train_matches=0,
        )
        calibrated = calibrate_prediction(pred, calibration_pool, as_of_time=decision_time)
        p_over_2_5.append(calibrated.probabilities[_TARGET_THRESHOLD] if calibrated.probabilities is not None else np.nan)

        elo_rec = elo_by_match_id.get(row["match_id"])
        if elo_rec is not None:
            elo_diff.append(elo_rec.elo_diff)
            elo_home.append(elo_rec.elo_home)
            elo_away.append(elo_rec.elo_away)
            has_elo.append(True)
        else:
            elo_diff.append(np.nan)
            elo_home.append(np.nan)
            elo_away.append(np.nan)
            has_elo.append(False)

    df["p_over_2_5"] = p_over_2_5
    df["elo_diff"] = elo_diff
    df["elo_home"] = elo_home
    df["elo_away"] = elo_away
    df["has_elo"] = has_elo
    df["outcome_over_2_5"] = (df["total_goals"] > _TARGET_THRESHOLD).astype(float)

    n_before_cutoff_filter = len(df)
    df = df[df["decision_time"].dt.date <= _CORPUS_CUTOFF_DATE].reset_index(drop=True)
    n_excluded_after_cutoff = n_before_cutoff_filter - len(df)

    df = df.dropna(subset=["p_over_2_5", "elo_diff"]).reset_index(drop=True)
    return df, n_excluded_after_cutoff


def _safe_logit(p: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), eps, 1 - eps)
    return np.log(p / (1 - p))


def compute_model_predictions(df: pd.DataFrame, e16_module) -> pd.DataFrame:
    """Calcule p_B/p_C/p_D en walk-forward sur TOUT le corpus (deja
    trie par decision_time) - le rodage sert de pool d'historique,
    jamais evalue lui-meme (filtre applique par l'appelant via `split`)."""
    logit_p_a = _safe_logit(df["p_over_2_5"].to_numpy())
    elo = df["elo_diff"].to_numpy()
    y = df["outcome_over_2_5"].to_numpy()
    ones = np.ones(len(df))

    p_b = walk_forward_logistic_with_offset(logit_p_a, np.column_stack([ones, elo]), y)
    p_c = e16_module.walk_forward_logistic(df.assign(**{"_X": 0}), lambda d: (np.column_stack([ones, logit_p_a]), y))
    p_d = e16_module.walk_forward_logistic(df.assign(**{"_X": 0}), lambda d: (np.column_stack([ones, logit_p_a, elo]), y))

    out = df.copy()
    out["p_B"] = p_b
    out["p_C"] = p_c
    out["p_D"] = p_d
    return out


def evaluate_brier(df: pd.DataFrame, col: str) -> np.ndarray:
    return (df[col].to_numpy() - df["outcome_over_2_5"].to_numpy()) ** 2


def bootstrap_diff(df: pd.DataFrame, col_a: str, col_b: str, seed: int | None = None) -> dict:
    diffs = evaluate_brier(df, col_a) - evaluate_brier(df, col_b)
    return paired_bootstrap_test(diffs, n_resamples=10000, seed=seed)


# --------------------------------------------------------------------------
# Verdict (docs/elo_experiment_specification.md section 13) - grille
# figee, mecanique, 5 valeurs autorisees uniquement.
# --------------------------------------------------------------------------


def classify_verdict(
    primary_boot: dict, validation_boot: dict, test_boot: dict, scope_boots: list[dict], n_global_pool: int
) -> str:
    if n_global_pool < _MIN_GLOBAL_POOL:
        return "DONNEES INSUFFISANTES"

    validation_favorable = validation_boot["ci_high"] < 0.0
    validation_unfavorable = validation_boot["ci_low"] > 0.0
    test_favorable = test_boot["ci_high"] < 0.0
    test_unfavorable = test_boot["ci_low"] > 0.0
    contradiction = (validation_favorable and test_unfavorable) or (validation_unfavorable and test_favorable)

    primary_favorable = primary_boot["ci_high"] < 0.0
    primary_width = primary_boot["ci_high"] - primary_boot["ci_low"]

    if contradiction:
        return "ABSENCE DE PREUVE" if not any(b["ci_low"] > 0.0 for b in scope_boots) else "NON VALIDE"

    if primary_favorable:
        any_scope_inversion = any(b["ci_low"] > 0.0 for b in scope_boots)
        if any_scope_inversion:
            return "NON VALIDE"
        return "VALIDE"

    if primary_width > 0.05:
        return "ABSENCE DE PREUVE"
    return "NON VALIDE"


# --------------------------------------------------------------------------
# main() - execution reelle unique.
# --------------------------------------------------------------------------


def main() -> None:
    stage10 = _load_stage10()
    stage8 = stage10._load_stage8()
    e7 = _load_e7()
    e8 = _load_e8()
    e16 = _load_e16()

    print("=== Phase K - chargement des donnees Elo (archive) ===")
    elo_by_club = load_elo_ratings_by_club()
    elo_by_match_id, join_reports = load_all_elo_records(elo_by_club)
    print(f"n clubs Elo charges: {len(elo_by_club)}")
    for (league, season), r in join_reports.items():
        print(
            f"  {league}/{season}: matched={r.n_matched} exploitable={r.n_exploitable} "
            f"excl_weekday={r.n_excluded_ambiguous_weekday} excl_pit={r.n_excluded_pit_violation} "
            f"excl_not_mapped={r.n_excluded_team_not_mapped} excl_no_rating={r.n_excluded_no_elo_rating} "
            f"excl_ambiguous_window={r.n_excluded_ambiguous_elo_window}"
        )

    print("=== Construction du dataset complet (Modele A + Elo) ===")
    df, n_excluded_after_cutoff = build_full_dataset(e7, e8, stage8, elo_by_match_id)
    print(f"n corpus final (post-cutoff, avec p_A et elo_diff): {len(df)}")
    print(f"n exclus par la restriction de corpus (> {_CORPUS_CUTOFF_DATE}): {n_excluded_after_cutoff}")

    df = tag_burn_in_validation_test(df, stage10, stage8)
    print(df["split"].value_counts().to_dict())

    print("=== Calcul des modeles B/C/D (walk-forward) ===")
    df = compute_model_predictions(df, e16)

    eval_pool = df[df["split"].isin(["validation", "test"])].dropna(subset=["p_C", "p_D"]).reset_index(drop=True)
    validation_pool = eval_pool[eval_pool["split"] == "validation"]
    test_pool = eval_pool[eval_pool["split"] == "test"]

    brier_a = evaluate_brier(eval_pool, "p_over_2_5").mean()
    brier_b = evaluate_brier(eval_pool, "p_B").mean()
    brier_c = evaluate_brier(eval_pool, "p_C").mean()
    brier_d = evaluate_brier(eval_pool, "p_D").mean()
    print(f"Brier A={brier_a:.4f} B={brier_b:.4f} C={brier_c:.4f} D={brier_d:.4f} (n={len(eval_pool)})")

    primary_boot = bootstrap_diff(eval_pool, "p_D", "p_C", seed=0)
    validation_boot = bootstrap_diff(validation_pool, "p_D", "p_C", seed=1) if len(validation_pool) >= 30 else {"ci_low": np.nan, "ci_high": np.nan}
    test_boot = bootstrap_diff(test_pool, "p_D", "p_C", seed=2) if len(test_pool) >= 30 else {"ci_low": np.nan, "ci_high": np.nan}

    print(f"Primaire (D-C, VALIDATION+TEST): {primary_boot}")
    print(f"VALIDATION seule (D-C): {validation_boot}")
    print(f"TEST seul (D-C): {test_boot}")

    print("=== Robustesse (diagnostics secondaires, section 10 du protocole) ===")
    scope_boots = []
    for league in sorted(eval_pool["league"].unique()):
        sub = eval_pool[eval_pool["league"] == league]
        if len(sub) >= 30:
            b = bootstrap_diff(sub, "p_D", "p_C", seed=10)
            scope_boots.append(b)
            print(f"  championnat={league} n={len(sub)}: {b}")
    for season in sorted(eval_pool["season"].unique()):
        sub = eval_pool[eval_pool["season"] == season]
        if len(sub) >= 30:
            b = bootstrap_diff(sub, "p_D", "p_C", seed=11)
            scope_boots.append(b)
            print(f"  saison={season} n={len(sub)}: {b}")

    print("=== Comparaisons secondaires (section 9 du protocole) ===")
    boot_a_c = bootstrap_diff(eval_pool, "p_C", "p_over_2_5", seed=20)
    boot_b_a = bootstrap_diff(eval_pool, "p_B", "p_over_2_5", seed=21)
    boot_b_d = bootstrap_diff(eval_pool, "p_B", "p_D", seed=22)
    print(f"  A vs C (recalibration seule, Brier C - Brier A): {boot_a_c}")
    print(f"  A vs B (naif, Brier B - Brier A): {boot_b_a}")
    print(f"  B vs D (Brier B - Brier D): {boot_b_d}")

    print("=== Test de redondance (section 11 du protocole) ===")
    logit_p_a_eval = _safe_logit(eval_pool["p_over_2_5"].to_numpy())
    elo_eval = eval_pool["elo_diff"].to_numpy()
    corr = float(np.corrcoef(logit_p_a_eval, elo_eval)[0, 1])
    print(f"  correlation(logit(p_A), elo_diff) sur la population propre = {corr:.4f}")
    beta_full = e16.fit_logistic(
        np.column_stack([np.ones(len(eval_pool)), logit_p_a_eval, elo_eval]), eval_pool["outcome_over_2_5"].to_numpy()
    )
    print(f"  coefficient elo_diff (regression pleine, non walk-forward, diagnostic uniquement) = {beta_full[2]:.6f}")

    print("=== Question A : calibration du modele sur la population complete ===")
    print(f"  p_A moyen (eval_pool) = {eval_pool['p_over_2_5'].mean():.4f}, frequence reelle observee = {eval_pool['outcome_over_2_5'].mean():.4f}")

    verdict = classify_verdict(primary_boot, validation_boot, test_boot, scope_boots, len(eval_pool))
    print(f"=== VERDICT: {verdict} ===")


if __name__ == "__main__":
    main()
