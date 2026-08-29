"""CLI : E14 - recalibration CIBLEE de la zone de sur-confiance [0.6,0.7)
d'Over 2.5, identifiee et reproduite trois fois (E11, section V) sur les
trois modeles (biais -0.11 a -0.12, IC95% entierement <0).

Question exacte (jamais simplifiee en "peut-on ameliorer la calibration
dans cette tranche ?") : peut-on ameliorer DEMONTRABLEMENT la calibration
de [0.6,0.7) en walk-forward/hors-echantillon, TOUT EN CONSERVANT une
distribution de buts coherente et les proprietes deja validees en
E7/E8/E11 ?

`poisson_simple`, `dixon_coles` et `xg_model` restent INCHANGES. Aucune
modification d'E1-E13. Aucune donnee historique modifiee. Aucun look-ahead.
Aucune strategie de pari, aucun ROI/Kelly/staking, aucune recherche de
value.

====================================================================
ETAPE 1 - INSPECTION PREALABLE (avant tout code)
====================================================================
- E7 (`run_stage15_e7_total_goals_distribution.py`) : `matrix_for_row`,
  `over_under_probs` (UNE SEULE matrice produit les 5 seuils - propriete
  structurelle deja garantie) - REUTILISES SANS MODIFICATION.
- E8 (`run_stage16_e8_walk_forward_validation.py`) : `build_decision_time_lookup`,
  `attach_walk_forward_scale` (facteur d'echelle c(m), reestime PAR MATCH
  de test a partir des seuls matchs de calibration strictement anterieurs,
  jamais ajuste sur le futur) - REUTILISES SANS MODIFICATION. E14 applique
  EXACTEMENT le meme principe de reestimation walk-forward PAR MATCH
  (jamais un ajustement poole une seule fois) a une SECONDE couche de
  calibration, appliquee APRES la distribution deja corrigee par E7/E8 -
  jamais a la place.
- E11 (`run_stage20_e11_probability_reliability_mapping.py`) :
  `calibration_slope_intercept` (regression de calibration de Cox,
  utilisee ici comme MECANISME D'AJUSTEMENT de la methode B, pas
  seulement comme mesure - reutilisee SANS MODIFICATION, seul l'USAGE
  change) - REUTILISE. `build_threshold_dataframe` n'est PAS reutilisee
  directement (elle ne calcule que le split calibration/test fixe,
  jamais le calibration-interne walk-forward necessaire ici) - une
  fonction generalisee equivalente est ecrite ci-dessous dans CE script,
  sans modifier E11.
- `calibration_engine.isotonic_calibration.fit_isotonic_calibration` (E2) :
  REUTILISEE SANS MODIFICATION comme methode A.
- `calibration_engine.significance.paired_bootstrap_test` : REUTILISE SANS
  MODIFICATION pour tous les IC95%.
- stage10 (`run_stage10_over_under_recalibration.py`) :
  `build_calibration_and_test_sets` - REUTILISE SANS MODIFICATION, MEME
  perimetre de donnees et MEMES championnats que toutes les experiences
  precedentes (point 9 du protocole).

====================================================================
ETAPE 2 - POINT METHODOLOGIQUE CRITIQUE : couche specifique au marche
O2.5, jamais une modification de la distribution de buts
====================================================================
E7/E8 ont valide qu'UNE SEULE distribution de buts coherente doit
permettre de deriver tous les seuils O/U. Une recalibration qui ne
toucherait QUE P(Over 2.5), en laissant P(Over 1.5)/P(Over 3.5) inchanges,
romprait ce principe si elle n'est jamais verifiee : elle pourrait produire
P(Over 2.5)_recalibree > P(Over 1.5) ou < P(Over 3.5) pour un match donne
(violation de la monotonicite empilee), ce qui n'existerait PLUS dans une
distribution de score unique. Une recalibration JOINTE des 5 seuils (en
conservant leur monotonicite empilee par construction) exigerait de
corriger la MATRICE de score elle-meme de facon conditionnelle a la
tranche de probabilite predite - un mecanisme de correction ENTIEREMENT
NOUVEAU, aussi complexe qu'une nouvelle couche de modele, et donc hors du
perimetre "simple, parcimonieuse, pre-specifiee" impose par ce protocole
(et hors du principe "ne pas modifier E1-E13"). E14 teste donc
EXCLUSIVEMENT l'option 1 du protocole : une recalibration de P(Over 2.5)
SEULE, traitee comme une couche de calibration SPECIFIQUE AU MARCHE Over
2.5, jamais integree a la distribution de buts elle-meme, et soumise a un
GATE OBLIGATOIRE de coherence inter-seuils (etape 6) contre les seuils
1.5/3.5 INCHANGES de la MEME distribution E7/E8. Une methode qui viole ce
gate de facon substantielle est rejetee, quelle que soit sa performance
sur Over 2.5 seul.

====================================================================
ETAPE 3 - DEUX METHODES CONCEPTUELLEMENT DIFFERENTES, PRE-SPECIFIEES
====================================================================
Methode A - Isotonic locale : regression isotonique (PAVA,
`fit_isotonic_calibration`, REUTILISEE, zero parametre libre), ajustee
SUR TOUT LE DOMAINE de probabilite [0,1] (jamais restreinte a [0.6,0.7)
seul) precisement pour EVITER toute rupture artificielle aux frontieres
de la zone (une courbe ajustee uniquement sur [0.6,0.7) creerait une
discontinuite avec les zones voisines non traitees) - son EFFET est
ensuite mesure specifiquement dans [0.6,0.7).
Methode B - Correction parametrique locale : recalibration logistique a
DEUX parametres (a, b), p_recalibree = sigmoid(a + b*logit(p)) - EXACTEMENT
la meme forme fonctionnelle que la regression de calibration de Cox deja
utilisee comme MESURE en E11 (`calibration_slope_intercept`, REUTILISEE
SANS MODIFICATION comme MECANISME D'AJUSTEMENT ici). Deux parametres
seulement, ajustee sur TOUT LE DOMAINE (meme raison qu'A), aucune
flexibilite locale supplementaire - choisie precisement parce qu'elle est
la correction la plus PARCIMONIEUSE et deja mesuree comme pertinente
(pentes de Cox <1 systematiquement observees en E11) plutot qu'une
nouvelle forme fonctionnelle inventee pour l'occasion.
Les deux methodes sont des experiences DISTINCTES : chacune est evaluee
selon EXACTEMENT la meme grille de verdict (etape 8), independamment de
la performance de l'autre - AUCUNE selection "la meilleure des deux" n'est
faite apres observation des resultats OOS (point 6/7 du protocole).

====================================================================
ETAPE 4 - PROTOCOLE WALK-FORWARD (jamais un ajustement poole une fois)
====================================================================
Pour chaque match de test m (trie par `decision_time`), la courbe/le
parametre de recalibration (A ou B) est ajuste EXCLUSIVEMENT sur les
matchs du jeu de CALIBRATION (jamais le test, jamais un autre jeu) dont
`decision_time < decision_time(m)` - EXACTEMENT le meme principe de
reestimation walk-forward strictement anterieure qu'E8, applique ici a
une seconde couche de calibration plutot qu'a l'echelle (lambda, mu). Les probabilites baseline
utilisees comme donnees d'ENTRAINEMENT de la recalibration (pour les
matchs de calibration eux-memes) sont ELLES-MEMES des probabilites
walk-forward (calculees en utilisant UNIQUEMENT les matchs de calibration
anterieurs, jamais un match de calibration utilise contre lui-meme) -
zero fuite a n'importe quel niveau de la chaine. Regle d'exclusion
(definie AVANT observation des resultats reels, identique en esprit a
E8) : un match est exclu si moins de `_MIN_N_RECAL=30` matchs de
calibration anterieurs disposent d'une probabilite baseline valide.

Usage:
    python scripts/run_stage23_e14_local_recalibration_over25.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.calibration_engine.isotonic_calibration import (  # noqa: E402
    IsotonicCalibrationCurve,
    fit_isotonic_calibration,
)
from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test  # noqa: E402
from sys_foot_quant.common.logging import get_logger  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_MODELS = ("poisson_simple", "xg_model")  # dixon_coles reproduit poisson_simple sur Over 2.5/3.5/4.5 (K/E7/E8/E11)
_THRESHOLDS = (0.5, 1.5, 2.5, 3.5, 4.5)
_TARGET_LOW, _TARGET_HIGH = 0.6, 0.7  # zone ciblee, IDENTIQUE a E11
_ADJACENT_LOW, _ADJACENT_HIGH = 0.4, 0.6  # zone de comparaison, IDENTIQUE a E11 (bien calibree)
_MIN_N_RECAL = 30  # regle d'exclusion PRE-ENREGISTREE, meme convention que E8 (_MIN_CALIBRATION_MATCHES_FOR_SCALE)
_N_RESAMPLES = 10_000
_SEED = 0
_COHERENCE_EPS = 1e-9

_STAGE20_PATH = Path(__file__).resolve().parent / "run_stage20_e11_probability_reliability_mapping.py"


def _load_e11():
    spec = importlib.util.spec_from_file_location("run_stage20_e11_probability_reliability_mapping", _STAGE20_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------
# ETAPE 4 - construction du jeu de donnees (walk-forward, generalisation de
# `build_threshold_dataframe` d'E11 a un couple (source, cible) arbitraire -
# n'importe rien dans E11 elle-meme).
# --------------------------------------------------------------------------


def build_walk_forward_probs(
    e7_module, e8_module, source_df: pd.DataFrame, target_df: pd.DataFrame, model: str,
    thresholds: tuple[float, ...] = _THRESHOLDS,
) -> pd.DataFrame:
    """Une ligne par match de `target_df` (trie par `decision_time`) - pour
    chaque seuil, `p_over_<t>` provient de LA MEME matrice de score
    corrigee par un facteur d'echelle walk-forward `c(m)`
    (`attach_walk_forward_scale`, E8, REUTILISE SANS MODIFICATION), estime
    EXCLUSIVEMENT sur les matchs de `source_df` dont `decision_time` est
    strictement anterieur. Appeler avec `source_df=target_df=calibration_df`
    donne les probabilites baseline walk-forward DES matchs de calibration
    eux-memes (jamais un match utilise contre lui-meme, car le filtre est
    strictement `<`)."""
    with_scale = e8_module.attach_walk_forward_scale(source_df, target_df, model)
    rows = []
    for _, row in with_scale.iterrows():
        if pd.isna(row["scale_c"]):
            continue
        matrix = e7_module.matrix_for_row(row, model, scale=float(row["scale_c"]))
        ou = e7_module.over_under_probs(matrix, thresholds=thresholds)
        record = {
            "match_id": row["match_id"],
            "league": row["league"],
            "season": row["season"],
            "decision_time": row["decision_time"],
            "total_goals": row["total_goals"],
        }
        for t in thresholds:
            record[f"p_over_{t}"] = ou[t]
            record[f"outcome_over_{t}"] = float(row["total_goals"] > t)
        rows.append(record)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# ETAPE 3 - methodes de recalibration, PURES fonctions fit/predict.
# --------------------------------------------------------------------------


def fit_logistic_recalibration(p: np.ndarray, y: np.ndarray, e11_module) -> dict:
    """Methode B : ajuste (a, b) par la MEME regression de calibration de
    Cox qu'E11 (`calibration_slope_intercept`, REUTILISEE SANS
    MODIFICATION comme mecanisme d'ajustement plutot que comme seule
    mesure). Deux parametres, aucune flexibilite supplementaire."""
    return e11_module.calibration_slope_intercept(p, y)


def apply_logistic_recalibration(params: dict, p: np.ndarray) -> np.ndarray:
    a, b = params["intercept"], params["slope"]
    eps = 1e-6
    p = np.clip(np.asarray(p, dtype=float), eps, 1 - eps)
    logit_p = np.log(p / (1 - p))
    z = a + b * logit_p
    return 1.0 / (1.0 + np.exp(-z))


def apply_isotonic_recalibration(curve: IsotonicCalibrationCurve, p: np.ndarray) -> np.ndarray:
    return curve.predict(p)


def walk_forward_recalibrate(
    calib_baseline_df: pd.DataFrame,
    test_baseline_df: pd.DataFrame,
    fit_fn,
    predict_fn,
    min_matches: int = _MIN_N_RECAL,
    p_col: str = "p_over_2.5",
    y_col: str = "outcome_over_2.5",
) -> pd.DataFrame:
    """Pour chaque match de `test_baseline_df` (deja trie par
    `decision_time`), ajuste la methode de recalibration EXCLUSIVEMENT sur
    les matchs de `calib_baseline_df` dont `decision_time` est strictement
    anterieur (jamais le test, jamais un match posterieur), puis l'applique
    au match evalue. `fit_fn(p_train, y_train) -> params_or_curve`,
    `predict_fn(params_or_curve, p_array) -> p_array_recalibree`."""
    calib_sorted = calib_baseline_df.dropna(subset=[p_col]).sort_values("decision_time").reset_index(drop=True)
    test_sorted = test_baseline_df.dropna(subset=[p_col]).sort_values("decision_time").reset_index(drop=True)

    calib_times = calib_sorted["decision_time"].to_numpy()
    calib_p = calib_sorted[p_col].to_numpy()
    calib_y = calib_sorted[y_col].to_numpy()

    rows = []
    for _, row in test_sorted.iterrows():
        as_of = row["decision_time"]
        mask = calib_times < as_of
        n = int(mask.sum())
        if n < min_matches:
            rows.append({"match_id": row["match_id"], "p_recalibrated": float("nan"), "n_calibration_used": n})
            continue
        fitted = fit_fn(calib_p[mask], calib_y[mask])
        p_new = predict_fn(fitted, np.array([row[p_col]]))[0]
        rows.append({"match_id": row["match_id"], "p_recalibrated": float(p_new), "n_calibration_used": n})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# ETAPE 7 - mesures de zone (Brier, biais, IC95%) - PURES, jamais utilisees
# pour ajuster une methode.
# --------------------------------------------------------------------------


def zone_mask(p_baseline: np.ndarray, lo: float, hi: float) -> np.ndarray:
    p_baseline = np.asarray(p_baseline, dtype=float)
    return (p_baseline >= lo) & (p_baseline < hi)


def zone_summary(p: np.ndarray, y: np.ndarray, min_n: int = _MIN_N_RECAL) -> dict:
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=float)
    n = p.size
    if n == 0:
        return {
            "n": 0, "p_moyen": float("nan"), "freq_reelle": float("nan"), "biais": float("nan"),
            "biais_ic95_low": float("nan"), "biais_ic95_high": float("nan"), "brier": float("nan"),
            "insuffisant": True,
        }
    diffs = y - p
    boot = paired_bootstrap_test(diffs, n_resamples=_N_RESAMPLES, seed=_SEED) if n >= 2 else {"ci_low": float("nan"), "ci_high": float("nan")}
    return {
        "n": n,
        "p_moyen": float(p.mean()),
        "freq_reelle": float(y.mean()),
        "biais": float(y.mean() - p.mean()),
        "biais_ic95_low": boot["ci_low"],
        "biais_ic95_high": boot["ci_high"],
        "brier": float(np.mean((p - y) ** 2)),
        "insuffisant": n < min_n,
    }


def compare_brier_paired(p_baseline: np.ndarray, p_candidate: np.ndarray, y: np.ndarray) -> dict | None:
    """`paired_bootstrap_test` (REUTILISE) sur diff = Brier(candidate) -
    Brier(baseline), memes matchs, jamais un panel different."""
    p_baseline = np.asarray(p_baseline, dtype=float)
    p_candidate = np.asarray(p_candidate, dtype=float)
    y = np.asarray(y, dtype=float)
    if p_baseline.size < 2:
        return None
    diffs = (p_candidate - y) ** 2 - (p_baseline - y) ** 2
    boot = paired_bootstrap_test(diffs, n_resamples=_N_RESAMPLES, seed=_SEED)
    return {"n": p_baseline.size, "boot": boot}


# --------------------------------------------------------------------------
# ETAPE 6 - GATE OBLIGATOIRE : coherence inter-seuils.
# --------------------------------------------------------------------------


def coherence_gate(
    baseline_test_df: pd.DataFrame, recalibrated_df: pd.DataFrame, eps: float = _COHERENCE_EPS
) -> dict:
    """Verifie, pour chaque match ou P(Over 2.5) a ete recalibree, que
    P(Over 1.5) >= P(Over 2.5)_recalibree >= P(Over 3.5) - les seuils
    1.5/3.5 restent EXACTEMENT ceux de la distribution E7/E8 baseline,
    JAMAIS touches par la recalibration (qui ne porte que sur Over 2.5)."""
    merged = baseline_test_df.merge(recalibrated_df, on="match_id", how="inner")
    merged = merged.dropna(subset=["p_recalibrated"])
    n = len(merged)
    if n == 0:
        return {"n": 0, "n_violations": 0, "rate": float("nan"), "max_amplitude": 0.0}
    upper_gap = merged["p_recalibrated"] - merged["p_over_1.5"]
    lower_gap = merged["p_over_3.5"] - merged["p_recalibrated"]
    viol_upper = upper_gap > eps
    viol_lower = lower_gap > eps
    n_violations = int((viol_upper | viol_lower).sum())
    amplitudes = pd.concat([upper_gap[viol_upper], lower_gap[viol_lower]])
    max_amplitude = float(amplitudes.max()) if len(amplitudes) > 0 else 0.0
    return {"n": n, "n_violations": n_violations, "rate": n_violations / n, "max_amplitude": max_amplitude}


# --------------------------------------------------------------------------
# ETAPE 8 - grille de verdict (definie AVANT observation des resultats).
# --------------------------------------------------------------------------

VERDICT_VALIDEE = "E14 - RECALIBRATION VALIDEE"
VERDICT_NON_VALIDEE = "E14 - RECALIBRATION NON VALIDEE"


def classify_e14_verdict(
    target_zone_boot: dict | None,
    global_boot: dict | None,
    adjacent_zone_boot: dict | None,
    coherence: dict,
    n_target: int,
    min_n: int = _MIN_N_RECAL,
) -> tuple[str, list[str]]:
    """Applique MECANIQUEMENT les criteres du protocole (definis avant
    observation des resultats). Retourne le verdict et la liste des
    raisons (pour un rejet, ou des confirmations pour une validation)."""
    reasons: list[str] = []
    if n_target < min_n:
        reasons.append(f"echantillon insuffisant dans [0.6,0.7) (n={n_target} < {min_n}).")
        return VERDICT_NON_VALIDEE, reasons
    if target_zone_boot is None:
        reasons.append("comparaison Brier [0.6,0.7) non calculable.")
        return VERDICT_NON_VALIDEE, reasons

    target_improved = target_zone_boot["ci_high"] <= 0.0
    if not target_improved:
        reasons.append(
            f"amelioration OOS non demontree dans [0.6,0.7) (IC95%=[{target_zone_boot['ci_low']:+.4f},"
            f"{target_zone_boot['ci_high']:+.4f}])."
        )
        return VERDICT_NON_VALIDEE, reasons
    reasons.append(
        f"amelioration OOS demontree dans [0.6,0.7) (IC95%=[{target_zone_boot['ci_low']:+.4f},"
        f"{target_zone_boot['ci_high']:+.4f}])."
    )

    if global_boot is not None and global_boot["ci_low"] > 0.0:
        reasons.append(f"degradation significative du Brier global (IC95%=[{global_boot['ci_low']:+.4f},{global_boot['ci_high']:+.4f}]).")
        return VERDICT_NON_VALIDEE, reasons
    reasons.append("pas de degradation significative du Brier global.")

    if adjacent_zone_boot is not None and adjacent_zone_boot["ci_low"] > 0.0:
        reasons.append(
            f"degradation significative de la zone adjacente [0.4,0.6) (IC95%=[{adjacent_zone_boot['ci_low']:+.4f},"
            f"{adjacent_zone_boot['ci_high']:+.4f}])."
        )
        return VERDICT_NON_VALIDEE, reasons
    reasons.append("pas de degradation significative de la zone adjacente [0.4,0.6).")

    if coherence["n_violations"] > 0:
        reasons.append(
            f"violation(s) de coherence inter-seuils detectee(s) (n={coherence['n_violations']}/{coherence['n']}, "
            f"amplitude max={coherence['max_amplitude']:.4f})."
        )
        return VERDICT_NON_VALIDEE, reasons
    reasons.append("aucune violation de coherence inter-seuils.")

    return VERDICT_VALIDEE, reasons


def _print_zone(label: str, s: dict) -> None:
    flag = " [INSUFFISANT n<30]" if s.get("insuffisant") else ""
    typer.echo(
        f"    {label:<28} n={s['n']:<5} p_moyen={s['p_moyen']:.4f} freq_reelle={s['freq_reelle']:.4f} "
        f"biais={s['biais']:+.4f} IC95%=[{s['biais_ic95_low']:+.4f},{s['biais_ic95_high']:+.4f}] "
        f"Brier={s['brier']:.4f}{flag}"
    )


@app.command()
def main() -> None:
    typer.echo("=== E14 : recalibration ciblee de la zone [0.6,0.7) d'Over 2.5 ===")
    typer.echo(
        "poisson_simple, dixon_coles et xg_model INCHANGES. Aucune modification d'E1-E13. "
        "Aucun ROI/Kelly/staking, aucune strategie de pari, aucune recherche de value.\n"
    )

    e11 = _load_e11()
    e9 = e11._load_e9()
    e8 = e9._load_e8()
    e7 = e8._load_e7()
    stage10 = e7._load_stage10()
    stage8 = stage10._load_stage8()

    df = e7.build_lambda_mu_dataframe(stage8)
    decision_time = e8.build_decision_time_lookup(stage8)
    df["decision_time"] = df["match_id"].map(decision_time)

    calibration_ids_df, test_ids_df = stage10.build_calibration_and_test_sets(stage8)
    calibration_ids = set(calibration_ids_df["match_id"])
    test_ids = set(test_ids_df["match_id"])
    calibration_df = df[df["match_id"].isin(calibration_ids)].copy()
    test_df = df[df["match_id"].isin(test_ids)].copy()
    typer.echo(f"n_calibration (meme perimetre que E7/E8/E11) : {len(calibration_df)}")
    typer.echo(f"n_test (meme perimetre que E7/E8/E11)        : {len(test_df)}\n")

    verdicts: dict[str, dict[str, str]] = {}

    for model in _MODELS:
        typer.echo(f"##### {model} #####")

        baseline_test = build_walk_forward_probs(e7, e8, calibration_df, test_df, model)
        baseline_calib = build_walk_forward_probs(e7, e8, calibration_df, calibration_df, model)
        typer.echo(f"  n baseline test (walk-forward, non-regression E11) = {len(baseline_test)}")
        typer.echo(f"  n baseline calibration (walk-forward interne)      = {len(baseline_calib)}\n")

        p_base = baseline_test["p_over_2.5"].to_numpy()
        y = baseline_test["outcome_over_2.5"].to_numpy()
        mask_target = zone_mask(p_base, _TARGET_LOW, _TARGET_HIGH)
        mask_adjacent = zone_mask(p_base, _ADJACENT_LOW, _ADJACENT_HIGH)
        typer.echo(f"  n zone cible [0.6,0.7)    = {int(mask_target.sum())}")
        typer.echo(f"  n zone adjacente [0.4,0.6) = {int(mask_adjacent.sum())}\n")

        typer.echo("--- BASELINE (E7/E8, sans recalibration) ---")
        _print_zone("GLOBAL", zone_summary(p_base, y))
        _print_zone("[0.6,0.7)", zone_summary(p_base[mask_target], y[mask_target]))
        _print_zone("[0.4,0.6)", zone_summary(p_base[mask_adjacent], y[mask_adjacent]))

        methods = {
            "A - Isotonic": (fit_isotonic_calibration, apply_isotonic_recalibration),
            "B - Logistic (Cox, 2 param.)": (
                lambda p, y_: fit_logistic_recalibration(p, y_, e11),
                apply_logistic_recalibration,
            ),
        }
        verdicts[model] = {}

        for method_label, (fit_fn, predict_fn) in methods.items():
            typer.echo(f"\n--- Methode {method_label} ---")
            recal = walk_forward_recalibrate(baseline_calib, baseline_test, fit_fn, predict_fn)
            merged = baseline_test.merge(recal, on="match_id", how="inner")
            n_excluded = int(merged["p_recalibrated"].isna().sum())
            merged_valid = merged.dropna(subset=["p_recalibrated"])
            typer.echo(f"  n exclus (moins de {_MIN_N_RECAL} matchs de calibration anterieurs) : {n_excluded}")

            p_cand_full = merged_valid["p_recalibrated"].to_numpy()
            p_base_full = merged_valid["p_over_2.5"].to_numpy()
            y_full = merged_valid["outcome_over_2.5"].to_numpy()
            mask_t = zone_mask(p_base_full, _TARGET_LOW, _TARGET_HIGH)
            mask_a = zone_mask(p_base_full, _ADJACENT_LOW, _ADJACENT_HIGH)
            mask_outside = ~mask_t

            typer.echo("  -- Candidat --")
            _print_zone("GLOBAL", zone_summary(p_cand_full, y_full))
            _print_zone("[0.6,0.7)", zone_summary(p_cand_full[mask_t], y_full[mask_t]))
            _print_zone("[0.4,0.6)", zone_summary(p_cand_full[mask_a], y_full[mask_a]))
            _print_zone("hors [0.6,0.7)", zone_summary(p_cand_full[mask_outside], y_full[mask_outside]))

            boot_global = compare_brier_paired(p_base_full, p_cand_full, y_full)
            boot_target = compare_brier_paired(p_base_full[mask_t], p_cand_full[mask_t], y_full[mask_t]) if mask_t.sum() >= 2 else None
            boot_adjacent = compare_brier_paired(p_base_full[mask_a], p_cand_full[mask_a], y_full[mask_a]) if mask_a.sum() >= 2 else None

            typer.echo("  -- Diff Brier (candidat - baseline), memes matchs --")
            if boot_global:
                b = boot_global["boot"]
                typer.echo(f"    GLOBAL      n={boot_global['n']:<4} IC95%=[{b['ci_low']:+.4f},{b['ci_high']:+.4f}] p={b['p_value']:.4f}")
            if boot_target:
                b = boot_target["boot"]
                typer.echo(f"    [0.6,0.7)   n={boot_target['n']:<4} IC95%=[{b['ci_low']:+.4f},{b['ci_high']:+.4f}] p={b['p_value']:.4f}")
            if boot_adjacent:
                b = boot_adjacent["boot"]
                typer.echo(f"    [0.4,0.6)   n={boot_adjacent['n']:<4} IC95%=[{b['ci_low']:+.4f},{b['ci_high']:+.4f}] p={b['p_value']:.4f}")

            typer.echo("  -- GATE : coherence inter-seuils (P(O1.5) >= P(O2.5)_recal >= P(O3.5)) --")
            coherence = coherence_gate(baseline_test, recal)
            typer.echo(
                f"    n={coherence['n']} violations={coherence['n_violations']} "
                f"taux={coherence['rate']:.4f} amplitude_max={coherence['max_amplitude']:.6f}"
            )

            typer.echo("  -- Robustesse : par sous-periode (mediane chronologique du test) --")
            median_time = baseline_test["decision_time"].median()
            for label, sub_mask in (
                ("premiere moitie", merged_valid["decision_time"] < median_time),
                ("seconde moitie", merged_valid["decision_time"] >= median_time),
            ):
                sub = merged_valid[sub_mask.to_numpy() & mask_t]
                if len(sub) >= 2:
                    b = compare_brier_paired(sub["p_over_2.5"].to_numpy(), sub["p_recalibrated"].to_numpy(), sub["outcome_over_2.5"].to_numpy())["boot"]
                    typer.echo(f"    {label:<16} [0.6,0.7) n={len(sub):<4} diff_Brier IC95%=[{b['ci_low']:+.4f},{b['ci_high']:+.4f}]")
                else:
                    typer.echo(f"    {label:<16} [0.6,0.7) n={len(sub)} insuffisant.")

            typer.echo("  -- Robustesse : par championnat --")
            for league in sorted(merged_valid["league"].unique()):
                sub = merged_valid[(merged_valid["league"] == league) & mask_t]
                if len(sub) >= 2:
                    b = compare_brier_paired(sub["p_over_2.5"].to_numpy(), sub["p_recalibrated"].to_numpy(), sub["outcome_over_2.5"].to_numpy())["boot"]
                    typer.echo(f"    {league:<16} [0.6,0.7) n={len(sub):<4} diff_Brier IC95%=[{b['ci_low']:+.4f},{b['ci_high']:+.4f}]")
                else:
                    typer.echo(f"    {league:<16} [0.6,0.7) n={len(sub)} insuffisant.")

            typer.echo("  -- Robustesse : sensibilite a l'observation extreme (zone cible) --")
            zone_df = merged_valid[mask_t].copy()
            if len(zone_df) >= 3:
                resid = zone_df["outcome_over_2.5"] - zone_df["p_over_2.5"]
                idx_extreme = resid.abs().idxmax()
                zone_df_trimmed = zone_df.drop(index=idx_extreme)
                s_full = zone_summary(zone_df["p_over_2.5"].to_numpy(), zone_df["outcome_over_2.5"].to_numpy())
                s_trim = zone_summary(zone_df_trimmed["p_over_2.5"].to_numpy(), zone_df_trimmed["outcome_over_2.5"].to_numpy())
                typer.echo(f"    biais baseline avec l'observation extreme    : {s_full['biais']:+.4f} (n={s_full['n']})")
                typer.echo(f"    biais baseline sans cette observation        : {s_trim['biais']:+.4f} (n={s_trim['n']})")

            verdict, reasons = classify_e14_verdict(
                target_zone_boot=boot_target["boot"] if boot_target else None,
                global_boot=boot_global["boot"] if boot_global else None,
                adjacent_zone_boot=boot_adjacent["boot"] if boot_adjacent else None,
                coherence=coherence,
                n_target=int(mask_t.sum()),
            )
            verdicts[model][method_label] = verdict
            typer.echo(f"\n  -> VERDICT {model} / {method_label} : {verdict}")
            for r in reasons:
                typer.echo(f"     - {r}")
            typer.echo("")

    typer.echo("=== VERDICTS (grille definie avant observation des resultats) ===")
    for model, by_method in verdicts.items():
        for method_label, v in by_method.items():
            typer.echo(f"  {model:<14} / {method_label:<30} -> {v}")

    typer.echo(
        "\nRESERVE : aucune conclusion de rentabilite. Aucun ROI, Kelly, staking, seuil de cote, "
        "recherche de value. Aucune donnee de marche utilisee pour calibrer cette zone. "
        "poisson_simple, dixon_coles et xg_model restent inchanges. Aucune modification d'E1-E13."
    )
    typer.echo("\nARRET : E14 termine, conformement au protocole. Aucune experience E15 lancee automatiquement.")


if __name__ == "__main__":
    app()
