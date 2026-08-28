"""CLI : E7 - construction et validation d'une distribution COHERENTE du
total de buts (P(Total=0..5), P(Total>=6)), dont TOUS les marches
Over/Under derives (1.5/2.5/3.5) proviennent de la MEME distribution -
jamais de modeles/calibrations separes par seuil.

`poisson_simple`, `dixon_coles` et `xg_model` restent INCHANGES. Aucun
nouveau modele predictif. Aucune conclusion de rentabilite - purement la
construction et la validation d'une representation probabiliste du total
de buts.

====================================================================
ETAPE 1 - INSPECTION PREALABLE DES MODULES EXISTANTS (avant tout code)
====================================================================
- `football_model.scoring.score_matrix(lam, mu, max_goals)` : matrice
  P(X=x, Y=y) Poisson independants - DEJA la brique de base.
- `football_model.dixon_coles.apply_dixon_coles_correction(matrix, lam,
  mu, rho)` : correction bas-score DEJA implementee, DEJA appliquee par
  `DixonColesModel.predict_score_matrix` - reutilisee ici TELLE QUELLE
  (fonction pure, jamais modifiee) pour reconstruire une matrice a partir
  de (lam, mu) EVENTUELLEMENT corriges, avec le meme rho deja estime par
  le modele fige.
- `run_stage8_diagnostic_total_goals_over_under.total_goals_distribution(matrix)`
  et `.over_under_probs(matrix, thresholds)` : DEJA calculees a partir de
  la MEME matrice de score - la propriete demandee par le protocole
  ("Over/Under derives de la meme distribution, jamais de modeles
  separes") est DEJA l'architecture existante depuis l'etape 8. E7 ne
  change donc PAS ce principe, il ameliore la matrice sous-jacente.
- `calibration_engine.metrics.brier_score`/`log_loss` : DEJA generiques
  multi-categories (`probs` de forme (N, K) quelconque, pas restreintes a
  K=3) - reutilisables SANS MODIFICATION pour les 7 categories de la
  distribution du total de buts.
- `calibration_engine.reliability.reliability_bins` et
  `calibration_engine.decomposition.brier_decomposition` : reutilisables
  sans modification sur les probabilites Over/Under DERIVEES (evenements
  binaires).
- `calibration_engine.isotonic_calibration.fit_isotonic_calibration` (E2)
  et `calibration_engine.significance.paired_bootstrap_test` : reutilises
  sans modification.

====================================================================
ETAPE 2 - POURQUOI LES MODELES SURESTIMENT LA QUEUE HAUTE (diagnostic)
====================================================================
Hypothese testee explicitement : la queue haute (6+ buts) est-elle
surestimee parce que (a) la FORME Poisson est mauvaise (le vrai total de
buts est intrinsequement moins disperse qu'un Poisson), ou (b) parce que
la MOYENNE predite (lambda+mu) est biaisee vers le haut (deja etabli aux
sections K/L/E4), ce qui gonfle mecaniquement la queue d'un Poisson (dont
la masse de queue croit avec le taux) sans que la FORME elle-meme soit en
cause ? Verifie en comparant la distribution observee reelle a UNE
distribution de reference Poisson(moyenne empirique reelle) - si cette
reference reproduit deja fidelement la queue observee, le probleme est
la MOYENNE, pas la forme.

====================================================================
ETAPE 3 - CALIBRATION : CE QUI EST DEJA DISPONIBLE, POURQUOI L'ISOTONE
PAR SEUIL NE SUFFIT PAS, QUELLES PROPRIETES CONSERVER, METHODE PROPOSEE
====================================================================
Deja disponible : la regression isotonique par seuil (E2/E3),
INDEPENDANTE pour chaque seuil (Over 1.5, 2.5, 3.5 sont CALIBRES SEPAREMENT,
sur des cibles binaires distinctes). Rien ne garantit mathematiquement
que P_calibree(Over 1.5) >= P_calibree(Over 2.5) >= P_calibree(Over 3.5)
apres coup - DEMONTRE EMPIRIQUEMENT ci-dessous (comptage de violations sur
les probabilites deja calibrees en E2/E3).

Proprietes a conserver : (1) toutes les probabilites de la distribution
sont >= 0 ; (2) leur somme = 1 ; (3) les probabilites Over/Under DERIVEES
de cette distribution sont AUTOMATIQUEMENT coherentes entre seuils (pas
une contrainte ajoutee apres coup, mais une CONSEQUENCE STRUCTURELLE de
ne jamais calibrer un seuil independamment).

METHODE PROPOSEE (UNE SEULE, choisie et justifiee AVANT implementation) :
une **correction scalaire de l'esperance** - facteur unique
`c = E[total reel] / E[lambda+mu predit]`, estime UNIQUEMENT sur la
CALIBRATION, applique multiplicativement a (lambda, mu) -> (c*lambda,
c*mu) (preserve le ratio domicile/exterieur implicite du modele), puis la
matrice de score COMPLETE est reconstruite a partir de ces valeurs
corrigees (`score_matrix`, et pour Dixon-Coles `apply_dixon_coles_correction`
avec le rho DEJA estime par le modele, inchange). Choisie plutot qu'une
isotonique par seuil car : (1) UN SEUL degre de liberte (pas de risque de
surajustement sur 640 matchs de calibration, contrairement a plusieurs
courbes isotoniques independantes) ; (2) cible directement la cause
racine identifiee a l'etape 2 (biais de la moyenne) plutot que de
reformer la queue de facon non parametrique sans comprendre pourquoi ;
(3) garantit la coherence entre seuils PAR CONSTRUCTION (une seule
distribution corrigee, jamais une correction par seuil) - la propriete
centrale demandee par le protocole. Aucune autre methode testee, aucune
comparaison de plusieurs variantes, aucune selection fondee sur le
resultat.

Usage:
    python scripts/run_stage15_e7_total_goals_distribution.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import typer
from scipy.stats import poisson as scipy_poisson

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.calibration_engine.decomposition import brier_decomposition  # noqa: E402
from sys_foot_quant.calibration_engine.metrics import brier_score, log_loss  # noqa: E402
from sys_foot_quant.calibration_engine.reliability import reliability_bins  # noqa: E402
from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test  # noqa: E402
from sys_foot_quant.common.logging import get_logger  # noqa: E402
from sys_foot_quant.data_engine.market_odds.economic_dataset import (  # noqa: E402
    DECISION_OFFSET_HOURS,
    MIN_TRAIN_MATCHES,
)
from sys_foot_quant.football_model.dixon_coles import DixonColesModel, apply_dixon_coles_correction  # noqa: E402
from sys_foot_quant.football_model.poisson import PoissonModel  # noqa: E402
from sys_foot_quant.football_model.scoring import score_matrix  # noqa: E402
from sys_foot_quant.football_model.xg_model import XGModel  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_MODELS = ("poisson_simple", "dixon_coles", "xg_model")
_MAX_GOALS = 20
_MAX_BUCKET = 6  # 0..5 + "6+"
_OU_THRESHOLDS = (1.5, 2.5, 3.5)
_N_RESAMPLES = 10_000
_SEED = 0

_STAGE10_PATH = Path(__file__).resolve().parent / "run_stage10_over_under_recalibration.py"


def _load_stage10():
    spec = importlib.util.spec_from_file_location("run_stage10_over_under_recalibration", _STAGE10_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------
# Briques reutilisees SANS MODIFICATION : total_goals_distribution/
# over_under_probs sont deja definies dans le stage8 - importees via le
# module charge dynamiquement (meme convention que E4/E5/E6).
# --------------------------------------------------------------------------


def independent_matrix(lam: float, mu: float, max_goals: int = _MAX_GOALS) -> np.ndarray:
    """Matrice Poisson independante normalisee - reutilise `score_matrix`
    (INCHANGEE) - base commune a poisson_simple et xg_model."""
    m = score_matrix(lam, mu, max_goals=max_goals)
    return m / m.sum()


def dixon_coles_matrix(lam: float, mu: float, rho: float, max_goals: int = _MAX_GOALS) -> np.ndarray:
    """Matrice Dixon-Coles - reutilise `score_matrix` ET
    `apply_dixon_coles_correction` (INCHANGEES), avec le rho DEJA estime
    par le modele fige (jamais recalcule ici)."""
    return apply_dixon_coles_correction(independent_matrix(lam, mu, max_goals=max_goals), lam, mu, rho)


# --------------------------------------------------------------------------
# Assemblage du jeu de donnees (lambda/mu SEPARES par modele - necessaires
# pour une correction scalaire qui preserve le ratio domicile/exterieur ;
# stage8 n'expose que leur somme).
# --------------------------------------------------------------------------


def build_lambda_mu_dataframe(stage8_module) -> pd.DataFrame:
    """Reproduit EXACTEMENT le mecanisme point-in-time de stage8 (memes
    fonctions privees reutilisees via le module charge dynamiquement :
    `_load_records`, `_goals_train_df`, `_xg_train_df`), mais expose
    (lambda, mu) SEPAREMENT par modele plutot que leur seule somme."""
    from datetime import timedelta

    rows = []
    for season, leagues in stage8_module._SEASONS.items():
        for name in leagues:
            records = stage8_module._load_records(name, season)
            ordered = sorted(records, key=lambda r: r.kickoff_utc)
            for r in ordered:
                decision_time = r.kickoff_utc - timedelta(hours=DECISION_OFFSET_HOURS)
                goals_df = stage8_module._goals_train_df(records, decision_time, exclude_match_id=r.match_id)
                xg_df = stage8_module._xg_train_df(records, decision_time, exclude_match_id=r.match_id)

                row = {
                    "match_id": r.match_id,
                    "league": name,
                    "season": season,
                    "home_goals": r.home_goals,
                    "away_goals": r.away_goals,
                    "total_goals": r.home_goals + r.away_goals,
                }

                if len(goals_df) >= MIN_TRAIN_MATCHES:
                    poisson = PoissonModel(use_team_hfa=False).fit(goals_df)
                    lam, mu = poisson.predict_lambda_mu(r.home_team_id, r.away_team_id)
                    row["poisson_simple_lambda"], row["poisson_simple_mu"] = lam, mu

                    dc = DixonColesModel(use_team_hfa=False).fit(goals_df)
                    dc_lam, dc_mu = dc.predict_lambda_mu(r.home_team_id, r.away_team_id)
                    row["dixon_coles_lambda"], row["dixon_coles_mu"], row["dixon_coles_rho"] = dc_lam, dc_mu, dc.rho_
                else:
                    row["poisson_simple_lambda"] = row["poisson_simple_mu"] = float("nan")
                    row["dixon_coles_lambda"] = row["dixon_coles_mu"] = row["dixon_coles_rho"] = float("nan")

                if len(xg_df) >= MIN_TRAIN_MATCHES:
                    xg = XGModel(max_goals=_MAX_GOALS).fit(xg_df)
                    xg_lam, xg_mu = xg.predict_lambda_mu(r.home_team_id, r.away_team_id)
                    row["xg_model_lambda"], row["xg_model_mu"] = xg_lam, xg_mu
                else:
                    row["xg_model_lambda"] = row["xg_model_mu"] = float("nan")

                rows.append(row)
    return pd.DataFrame(rows)


def matrix_for_row(row: pd.Series, model: str, scale: float = 1.0) -> np.ndarray | None:
    """Construit la matrice de score (RAW si scale=1.0, CORRIGEE sinon)
    pour une ligne donnee - None si l'historique etait insuffisant."""
    lam, mu = row.get(f"{model}_lambda"), row.get(f"{model}_mu")
    if pd.isna(lam) or pd.isna(mu):
        return None
    lam, mu = scale * lam, scale * mu
    if model == "dixon_coles":
        rho = row["dixon_coles_rho"]
        return dixon_coles_matrix(lam, mu, rho)
    return independent_matrix(lam, mu)


# --------------------------------------------------------------------------
# ETAPE 4 - Coherence automatique (fonctions pures, testees isolement)
# --------------------------------------------------------------------------


def total_goals_distribution(matrix: np.ndarray, max_bucket: int = _MAX_BUCKET) -> np.ndarray:
    """Identique a celle de stage8 (dupliquee ici pour ne pas dependre de
    l'import dynamique dans les fonctions pures testables isolement) -
    P(total=0..max_bucket-1), P(total>=max_bucket)."""
    n = matrix.shape[0]
    totals = np.add.outer(np.arange(n), np.arange(n))
    out = np.zeros(max_bucket + 1)
    for k in range(max_bucket):
        out[k] = matrix[totals == k].sum()
    out[max_bucket] = matrix[totals >= max_bucket].sum()
    return out


def over_under_probs(matrix: np.ndarray, thresholds: tuple[float, ...] = _OU_THRESHOLDS) -> dict[float, float]:
    """Identique a celle de stage8 - P(total > seuil) pour chaque seuil,
    DERIVEE DE LA MEME MATRICE que la distribution complete (jamais un
    calcul separe)."""
    n = matrix.shape[0]
    totals = np.add.outer(np.arange(n), np.arange(n))
    return {t: float(matrix[totals > t].sum()) for t in thresholds}


def check_distribution_validity(dist: np.ndarray, atol: float = 1e-9) -> dict:
    return {
        "all_non_negative": bool(np.all(dist >= -atol)),
        "sums_to_one": bool(abs(float(dist.sum()) - 1.0) < 1e-6),
    }


def check_over_under_monotonic(ou: dict[float, float]) -> bool:
    """P(Over 1.5) >= P(Over 2.5) >= P(Over 3.5) - doit toujours etre vrai
    par construction quand ou provient d'une seule matrice."""
    sorted_thresholds = sorted(ou)
    values = [ou[t] for t in sorted_thresholds]
    return all(values[i] >= values[i + 1] - 1e-9 for i in range(len(values) - 1))


def check_over_under_matches_distribution(dist: np.ndarray, ou: dict[float, float], atol: float = 1e-6) -> bool:
    """P(Over 2.5) doit exactement egaler sum(P(total>=3)) issu de la MEME
    distribution - verifie la reproduction exacte demandee (etape 6)."""
    ok = True
    for t, p in ou.items():
        k_min = int(np.floor(t)) + 1  # ex: Over 2.5 -> total >= 3
        expected = float(dist[k_min:].sum())  # P(total >= k_min), toujours valide (k_min <= _MAX_BUCKET ici)
        ok = ok and abs(expected - p) < atol
    return ok


# --------------------------------------------------------------------------
# ETAPE 3 - correction scalaire
# --------------------------------------------------------------------------


def fit_scale_correction(calibration_df: pd.DataFrame, model: str) -> float:
    """c = E[total reel] / E[lambda+mu predit], estime UNIQUEMENT sur la
    CALIBRATION - un seul degre de liberte, jamais ajuste sur le test."""
    lam_col, mu_col = f"{model}_lambda", f"{model}_mu"
    sub = calibration_df.dropna(subset=[lam_col, mu_col])
    predicted_mean = float((sub[lam_col] + sub[mu_col]).mean())
    actual_mean = float(sub["total_goals"].mean())
    return actual_mean / predicted_mean


# --------------------------------------------------------------------------
# ETAPE 2 - diagnostic de la queue haute
# --------------------------------------------------------------------------


def poisson_reference_distribution(empirical_mean: float, max_bucket: int = _MAX_BUCKET) -> np.ndarray:
    """Distribution Poisson(empirical_mean) de reference - AUCUN lien avec
    les modeles, sert uniquement a tester si la FORME Poisson, a la bonne
    moyenne, reproduit deja la queue observee."""
    k = np.arange(max_bucket)
    probs = scipy_poisson.pmf(k, empirical_mean)
    tail = 1.0 - probs.sum()
    return np.concatenate([probs, [tail]])


def dispersion_index(total_goals: np.ndarray) -> float:
    """Indice de dispersion = Variance / Moyenne (=1 pour un Poisson exact)."""
    return float(np.var(total_goals, ddof=1) / np.mean(total_goals))


# --------------------------------------------------------------------------
# ETAPE 3 (demonstration empirique) - incoherence de l'isotonique par seuil
# --------------------------------------------------------------------------


def count_isotonic_incoherences(stage10_module, calibration_df_stage8, test_df_stage8, model: str) -> dict:
    """Sur les MEMES probabilites deja calibrees par E2/E3 (une courbe
    isotonique INDEPENDANTE par seuil), compte les matchs du TEST ou
    P_calibree(Over 1.5) < P_calibree(Over 2.5) ou P_calibree(Over 2.5) <
    P_calibree(Over 3.5) - demonstration empirique, pas seulement
    theorique, que la calibration par seuil ne garantit pas la
    coherence."""
    probs_by_threshold = {}
    for t in _OU_THRESHOLDS:
        col = f"{model}_p_over_{t}"
        calib = calibration_df_stage8.dropna(subset=[col])
        curve_p_calib = calib[col].to_numpy()
        y_calib = (calib["total_goals"] > t).astype(float).to_numpy()
        from sys_foot_quant.calibration_engine.isotonic_calibration import fit_isotonic_calibration

        curve = fit_isotonic_calibration(curve_p_calib, y_calib)
        test = test_df_stage8.dropna(subset=[col]).set_index("match_id")
        probs_by_threshold[t] = pd.Series(curve.predict(test[col].to_numpy()), index=test.index)

    common_index = probs_by_threshold[1.5].index
    for t in _OU_THRESHOLDS[1:]:
        common_index = common_index.intersection(probs_by_threshold[t].index)

    p15 = probs_by_threshold[1.5].loc[common_index]
    p25 = probs_by_threshold[2.5].loc[common_index]
    p35 = probs_by_threshold[3.5].loc[common_index]

    violation_15_25 = (p15 < p25 - 1e-9).sum()
    violation_25_35 = (p25 < p35 - 1e-9).sum()
    return {
        "n": len(common_index),
        "violations_over15_lt_over25": int(violation_15_25),
        "violations_over25_lt_over35": int(violation_25_35),
        "any_violation": int(((p15 < p25 - 1e-9) | (p25 < p35 - 1e-9)).sum()),
    }


# --------------------------------------------------------------------------
# ETAPE 5 - evaluation
# --------------------------------------------------------------------------


def _calibration_weighted_error(p: np.ndarray, y: np.ndarray, n_bins: int = 10) -> float:
    bins = reliability_bins(p, y, n_bins=n_bins)
    non_empty = bins[bins["count"] > 0]
    if non_empty.empty:
        return float("nan")
    abs_err = (non_empty["mean_predicted"] - non_empty["observed_frequency"]).abs()
    return float((abs_err * non_empty["count"]).sum() / non_empty["count"].sum())


def evaluate_distributions(df: pd.DataFrame, model: str, scale: float) -> dict:
    """Evalue la distribution RAW (scale=1.0) et CORRIGEE (scale=c) sur
    exactement le meme sous-ensemble - Brier/log loss multi-categorie
    (REUTILISES sans modification, deja generiques), erreur sur E[Total],
    erreur de queue, calibration Over/Under derivee (par
    `brier_decomposition`, REUTILISE)."""
    lam_col, mu_col = f"{model}_lambda", f"{model}_mu"
    sub = df.dropna(subset=[lam_col, mu_col]).copy()

    raw_dists, corr_dists = [], []
    raw_ou = {t: [] for t in _OU_THRESHOLDS}
    corr_ou = {t: [] for t in _OU_THRESHOLDS}
    for _, row in sub.iterrows():
        m_raw = matrix_for_row(row, model, scale=1.0)
        m_corr = matrix_for_row(row, model, scale=scale)
        raw_dists.append(total_goals_distribution(m_raw))
        corr_dists.append(total_goals_distribution(m_corr))
        ou_raw = over_under_probs(m_raw)
        ou_corr = over_under_probs(m_corr)
        for t in _OU_THRESHOLDS:
            raw_ou[t].append(ou_raw[t])
            corr_ou[t].append(ou_corr[t])

    raw_dists = np.array(raw_dists)
    corr_dists = np.array(corr_dists)
    outcomes = np.clip(sub["total_goals"].to_numpy(), 0, _MAX_BUCKET)

    brier_raw = brier_score(raw_dists, outcomes)
    brier_corr = brier_score(corr_dists, outcomes)
    logloss_raw = log_loss(raw_dists, outcomes)
    logloss_corr = log_loss(corr_dists, outcomes)

    expected_total_raw = raw_dists @ np.arange(raw_dists.shape[1])  # approx (bucket 6 traite comme "6")
    expected_total_corr = corr_dists @ np.arange(corr_dists.shape[1])
    actual_total = sub["total_goals"].to_numpy()

    bias_raw = float((expected_total_raw - actual_total).mean())
    bias_corr = float((expected_total_corr - actual_total).mean())
    mae_raw = float(np.abs(expected_total_raw - actual_total).mean())
    mae_corr = float(np.abs(expected_total_corr - actual_total).mean())

    tail_predicted_raw = float(raw_dists[:, _MAX_BUCKET].mean())
    tail_predicted_corr = float(corr_dists[:, _MAX_BUCKET].mean())
    tail_observed = float((actual_total >= _MAX_BUCKET).mean())

    diffs_brier = np.sum((corr_dists - np.eye(_MAX_BUCKET + 1)[outcomes.astype(int)]) ** 2, axis=1) - np.sum(
        (raw_dists - np.eye(_MAX_BUCKET + 1)[outcomes.astype(int)]) ** 2, axis=1
    )
    boot_brier = paired_bootstrap_test(diffs_brier, n_resamples=_N_RESAMPLES, seed=_SEED)

    ou_calibration = {}
    for t in _OU_THRESHOLDS:
        y_bin = (actual_total > t).astype(float)
        p_raw = np.array(raw_ou[t])
        p_corr = np.array(corr_ou[t])
        ou_calibration[t] = {
            "cal_error_raw": _calibration_weighted_error(p_raw, y_bin),
            "cal_error_corr": _calibration_weighted_error(p_corr, y_bin),
            "resolution_raw": brier_decomposition(p_raw, y_bin)["resolution"],
            "resolution_corr": brier_decomposition(p_corr, y_bin)["resolution"],
        }

    return {
        "n": len(sub),
        "brier_raw": brier_raw,
        "brier_corr": brier_corr,
        "logloss_raw": logloss_raw,
        "logloss_corr": logloss_corr,
        "bias_raw": bias_raw,
        "bias_corr": bias_corr,
        "mae_raw": mae_raw,
        "mae_corr": mae_corr,
        "tail_predicted_raw": tail_predicted_raw,
        "tail_predicted_corr": tail_predicted_corr,
        "tail_observed": tail_observed,
        "boot_brier_corr_minus_raw": boot_brier,
        "ou_calibration": ou_calibration,
    }


def _print_scope_evaluation(label: str, res: dict) -> None:
    typer.echo(f"  -- {label} (n={res['n']}) --")
    typer.echo(
        f"    Brier(7cat)   raw={res['brier_raw']:.4f}  corrige={res['brier_corr']:.4f}  "
        f"diff(IC95%)=[{res['boot_brier_corr_minus_raw']['ci_low']:+.4f}, "
        f"{res['boot_brier_corr_minus_raw']['ci_high']:+.4f}] p={res['boot_brier_corr_minus_raw']['p_value']:.4f}"
    )
    typer.echo(f"    log loss(7cat) raw={res['logloss_raw']:.4f}  corrige={res['logloss_corr']:.4f}")
    typer.echo(f"    biais E[Total] raw={res['bias_raw']:+.4f}  corrige={res['bias_corr']:+.4f}")
    typer.echo(f"    MAE E[Total]   raw={res['mae_raw']:.4f}  corrige={res['mae_corr']:.4f}")
    typer.echo(
        f"    queue P(>=6) predite raw={res['tail_predicted_raw']:.4f}  corrigee={res['tail_predicted_corr']:.4f}  "
        f"observee={res['tail_observed']:.4f}"
    )
    for t, c in res["ou_calibration"].items():
        typer.echo(
            f"    Over {t} : calibration raw={c['cal_error_raw']:.4f} corrigee={c['cal_error_corr']:.4f}  "
            f"resolution raw={c['resolution_raw']:.4f} corrigee={c['resolution_corr']:.4f}"
        )


@app.command()
def main() -> None:
    typer.echo("=== E7 : distribution coherente du total de buts ===")
    typer.echo(
        "poisson_simple, dixon_coles et xg_model INCHANGES. Aucun nouveau modele. Aucune "
        "conclusion de rentabilite.\n"
    )

    stage10 = _load_stage10()
    stage8 = stage10._load_stage8()

    typer.echo("--- ETAPE 2 : pourquoi la queue haute est-elle surestimee ? ---")
    df = build_lambda_mu_dataframe(stage8)
    actual_total = df["total_goals"].to_numpy()
    empirical_mean = float(actual_total.mean())
    observed_dist = np.array([float((np.clip(actual_total, 0, _MAX_BUCKET) == k).mean()) for k in range(_MAX_BUCKET + 1)])
    reference_dist = poisson_reference_distribution(empirical_mean)
    typer.echo(f"  Moyenne reelle observee (corpus complet) : {empirical_mean:.4f}")
    typer.echo(f"  Indice de dispersion (Var/Moyenne, =1 pour Poisson exact) : {dispersion_index(actual_total):.4f}")
    typer.echo("  Distribution observee vs reference Poisson(moyenne empirique) :")
    for k in range(_MAX_BUCKET + 1):
        label = str(k) if k < _MAX_BUCKET else f"{_MAX_BUCKET}+"
        typer.echo(f"    total={label:<3} observe={observed_dist[k]:.4f}  Poisson(moyenne_reelle)={reference_dist[k]:.4f}")
    typer.echo(
        "  -> Si la reference Poisson(moyenne_reelle) reproduit deja fidelement la queue observee, "
        "le probleme identifie aux etapes K/L/E4 est la MOYENNE surestimee, pas la forme Poisson "
        "elle-meme.\n"
    )

    typer.echo("--- ETAPE 3 (demonstration empirique) : incoherence de l'isotonique par seuil (E2/E3) ---")
    calibration_df_stage8, test_df_stage8 = stage10.build_calibration_and_test_sets(stage8)
    for model in ("poisson_simple", "xg_model"):  # seuls modeles calibres en E2/E3
        result = count_isotonic_incoherences(stage10, calibration_df_stage8, test_df_stage8, model)
        typer.echo(
            f"  {model:<16} n={result['n']:<5} violations Over1.5<Over2.5={result['violations_over15_lt_over25']:<4} "
            f"violations Over2.5<Over3.5={result['violations_over25_lt_over35']:<4} "
            f"au moins une violation={result['any_violation']}"
        )
    typer.echo("")

    typer.echo("--- ETAPE 4 : coherence automatique de la distribution corrigee (echantillon de verification) ---")
    sample = df.dropna(subset=["poisson_simple_lambda", "poisson_simple_mu"]).head(50)
    all_valid = True
    for _, row in sample.iterrows():
        m = matrix_for_row(row, "poisson_simple", scale=1.15)
        dist = total_goals_distribution(m)
        ou = over_under_probs(m)
        validity = check_distribution_validity(dist)
        all_valid = all_valid and validity["all_non_negative"] and validity["sums_to_one"]
        all_valid = all_valid and check_over_under_monotonic(ou)
        all_valid = all_valid and check_over_under_matches_distribution(dist, ou)
    typer.echo(f"  Coherence verifiee sur {len(sample)} matchs (non-negativite, somme=1, monotonicite, reproduction exacte) : {all_valid}\n")

    typer.echo("--- ETAPES 3+5+7 : correction scalaire, ajustee sur CALIBRATION uniquement, evaluee sur TEST ---")
    calibration_ids = set(calibration_df_stage8["match_id"])
    test_ids = set(test_df_stage8["match_id"])
    calibration_df = df[df["match_id"].isin(calibration_ids)]
    test_df = df[df["match_id"].isin(test_ids)]

    scales = {}
    for model in _MODELS:
        c = fit_scale_correction(calibration_df, model)
        scales[model] = c
        typer.echo(f"  {model:<16} facteur de correction c (ajuste sur calibration) = {c:.4f}")
    typer.echo("")

    for model in _MODELS:
        typer.echo(f"##### {model} #####")
        c = scales[model]
        typer.echo("=== GLOBAL (TEST) ===")
        _print_scope_evaluation("GLOBAL", evaluate_distributions(test_df, model, c))

        typer.echo("=== Stabilite par championnat (TEST) ===")
        for league in sorted(test_df["league"].unique()):
            _print_scope_evaluation(league, evaluate_distributions(test_df[test_df["league"] == league], model, c))

        typer.echo("=== Stabilite par saison (TEST) ===")
        for season in sorted(test_df["season"].unique()):
            _print_scope_evaluation(season, evaluate_distributions(test_df[test_df["season"] == season], model, c))
        typer.echo("")

    typer.echo(
        "RESERVE : aucune conclusion de rentabilite. Aucune regle de pari, ROI, yield, Kelly, "
        "staking, seuil de cote, optimisation de value, selection de bookmaker, arbitrage. "
        "poisson_simple, dixon_coles et xg_model restent inchanges."
    )
    typer.echo("\nARRET : E7 termine, conformement au protocole. Aucune experience suivante lancee automatiquement.")


if __name__ == "__main__":
    app()
