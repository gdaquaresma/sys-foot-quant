"""CLI : E11 - cartographie de la fiabilite ABSOLUE des probabilites de
buts (Over/Under 0.5 a 4.5) produites par le moteur officiel E8, puis
(seulement dans un second temps) comparaison des ecarts de prix B365
parmi les probabilites reconnues fiables.

Question centrale (H1, coeur d'E11) : quand le modele annonce X%, X% des
matchs realisent-ils vraiment l'evenement ? Question secondaire et
EXPLORATOIRE (H2) : parmi les probabilites bien calibrees, les prix B365
s'en ecartent-ils parfois de facon notable ? H2 ne debouche sur AUCUNE
strategie.

`poisson_simple`, `dixon_coles` et `xg_model` restent INCHANGES. Aucune
nouvelle calibration, aucune nouvelle correction, aucun tuning. Aucun
arbitrage (hors perimetre - un seul bookmaker O/U dans Football-Data).

====================================================================
ETAPE 1 - INSPECTION E8/E9/E10 (avant tout code)
====================================================================
- E8 (`run_stage16_e8_walk_forward_validation.py`) : `build_decision_time_lookup`,
  `attach_walk_forward_scale` (facteur c(m) walk-forward, jamais ajuste
  sur le futur) - REUTILISES SANS MODIFICATION.
- E7 (`run_stage15_e7_total_goals_distribution.py`) : `build_lambda_mu_dataframe`,
  `matrix_for_row`, `over_under_probs` (deja generique sur un TUPLE de
  seuils - LA MEME matrice produit les 5 seuils demandes ici, propriete
  structurelle deja garantie, jamais recalculee par seuil) - REUTILISES
  SANS MODIFICATION.
- E9 (`run_stage18_e9_multi_bookmaker_market_layer.py`) : `load_all_multi_bookmaker_records`
  - REUTILISE SANS MODIFICATION pour les cotes B365 O/U 2.5 (seul
    bookmaker disponible sur ce marche - AUCUN arbitrage ici, hors
    perimetre explicite du protocole).
- E10 (`run_stage19_e10_disagreement_reliability.py`) : inspecte pour
  continuite methodologique (memes conventions de seuil d'incertitude
  n<30) - mais E11 classe par PROBABILITE ANNONCEE, jamais par gap modele
  /marche (changement de perspective explicite du protocole) : aucune
  fonction d'E10 n'est reutilisee, la logique de binning est differente.
- `calibration_engine.reliability.reliability_bins` (10 tranches de
  probabilite EQUI-LARGES [0,10%),[10%,20%),...,[90%,100%] - EXACTEMENT
  la grille demandee) et `.decomposition.brier_decomposition` REUTILISES
  SANS MODIFICATION.
- `calibration_engine.significance.paired_bootstrap_test` REUTILISE SANS
  MODIFICATION pour les IC95% et les comparaisons inter-modeles (memes
  matchs, panels apparies).
- `market_engine.overround.hold_percentage`/`remove_overround_proportional`
  REUTILISES SANS MODIFICATION.

====================================================================
ETAPE 2 - PROTOCOLE (fige avant execution reelle)
====================================================================
- Seuils Over/Under, TOUS derives de LA MEME distribution de score par
  match (jamais une calibration independante par seuil) :
  0.5 / 1.5 / 2.5 / 3.5 / 4.5.
- Tranches de PROBABILITE ANNONCEE (H1, fixees ex ante, 10 tranches de 10
  points - identiques a `reliability_bins(n_bins=10)`, deja utilise dans
  tout le projet) : [0-10%) ... [90-100%].
- Seuil d'incertitude elevee : n<30 par tranche (identique a E5/E10).
- Grille de difference de prix (H2, EXPLORATOIRE, fixee ex ante, jamais
  modifiee apres observation) : <2% / 2-5% / 5-10% / >=10% (difference
  RELATIVE entre la cote B365 Over 2.5 et la cote juste du modele
  `fair_odds = 1/p_model`).
- H2 restreinte aux matchs dont p_model(Over 2.5) tombe dans une tranche
  de probabilite jugee FIABLE au sens H1 (IC95% du biais contenant 0 sur
  la table de calibration globale) - critere MECANIQUE, decide AVANT
  d'examiner les prix, jamais choisi pour faire apparaitre un ecart.
- Comparaison inter-modeles : `paired_bootstrap_test` sur la difference
  de Brier (memes matchs, intersection des trois modeles), jamais de
  selection d'un "gagnant".

Usage:
    python scripts/run_stage20_e11_probability_reliability_mapping.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import typer
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.calibration_engine.decomposition import brier_decomposition  # noqa: E402
from sys_foot_quant.calibration_engine.reliability import reliability_bins  # noqa: E402
from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test  # noqa: E402
from sys_foot_quant.common.logging import get_logger  # noqa: E402
from sys_foot_quant.data_engine.market_odds.multi_bookmaker_odds import MultiBookmakerMatchRecord  # noqa: E402
from sys_foot_quant.market_engine.overround import hold_percentage, remove_overround_proportional  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_MODELS = ("poisson_simple", "dixon_coles", "xg_model")
_THRESHOLDS = (0.5, 1.5, 2.5, 3.5, 4.5)
_N_BINS = 10  # tranches de probabilite de 10 points - grille H1 fixee ex ante
_MIN_N = 30  # identique a E5/E10 - seuil documente, pas un fait universel
_N_RESAMPLES = 10_000
_SEED = 0

# Grille de difference de prix (H2, EXPLORATOIRE) - FIGEE AVANT EXECUTION.
_PRICE_DIFF_EDGES = [0.0, 2.0, 5.0, 10.0, np.inf]
_PRICE_DIFF_LABELS = ["<2%", "2-5%", "5-10%", ">=10%"]

_STAGE18_PATH = Path(__file__).resolve().parent / "run_stage18_e9_multi_bookmaker_market_layer.py"


def _load_e9():
    spec = importlib.util.spec_from_file_location("run_stage18_e9_multi_bookmaker_market_layer", _STAGE18_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------
# ETAPE 2 - construction du jeu de donnees (walk-forward, jamais in-sample)
# --------------------------------------------------------------------------


def build_threshold_dataframe(e8_module, e7_module, model: str) -> pd.DataFrame:
    """Une ligne par match du split TEST walk-forward d'E8 (jamais le
    rodage/calibration). Pour chaque seuil, `p_over_<t>` provient de LA
    MEME matrice de score corrigee (scale=c(m) walk-forward, jamais
    recalculee par seuil) - `over_under_probs` (E7, REUTILISE) recoit le
    TUPLE complet de seuils en un seul appel par match."""
    stage10 = e7_module._load_stage10()
    stage8 = stage10._load_stage8()
    df = e7_module.build_lambda_mu_dataframe(stage8)
    decision_time = e8_module.build_decision_time_lookup(stage8)
    df["decision_time"] = df["match_id"].map(decision_time)

    calibration_df_stage8, test_df_stage8 = stage10.build_calibration_and_test_sets(stage8)
    calibration_ids = set(calibration_df_stage8["match_id"])
    test_ids = set(test_df_stage8["match_id"])
    calibration_df = df[df["match_id"].isin(calibration_ids)].copy()
    test_df = df[df["match_id"].isin(test_ids)].copy()

    with_scale = e8_module.attach_walk_forward_scale(calibration_df, test_df, model)

    rows = []
    for _, row in with_scale.iterrows():
        if pd.isna(row["scale_c"]):
            continue
        matrix = e7_module.matrix_for_row(row, model, scale=float(row["scale_c"]))
        ou = e7_module.over_under_probs(matrix, thresholds=_THRESHOLDS)
        record = {
            "match_id": row["match_id"],
            "league": row["league"],
            "season": row["season"],
            "model": model,
            "total_goals": row["total_goals"],
        }
        for t in _THRESHOLDS:
            record[f"p_over_{t}"] = ou[t]
            record[f"outcome_over_{t}"] = float(row["total_goals"] > t)
        rows.append(record)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# ETAPE 4 - mesures de calibration ABSOLUE (H1) - PURES fonctions de mesure,
# aucune ne modifie ni ne recalibre p.
# --------------------------------------------------------------------------


def bin_index_for_prob(p: np.ndarray, n_bins: int = _N_BINS) -> np.ndarray:
    """Index de tranche (0..n_bins-1) pour chaque probabilite - REPRODUIT
    EXACTEMENT la regle interne de `reliability_bins` (meme appel
    `np.digitize`), jamais une convention differente, pour que la
    correspondance bin_lo/bin_hi <-> sous-ensemble de matchs soit toujours
    exacte."""
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    return np.clip(np.digitize(p, edges[1:-1], right=True), 0, n_bins - 1)


def calibration_table(p: np.ndarray, y: np.ndarray, n_bins: int = _N_BINS, min_n: int = _MIN_N) -> pd.DataFrame:
    """Augmente `reliability_bins` (E2, REUTILISE SANS MODIFICATION - meme
    grille de tranches equi-larges) avec biais + IC95% bootstrap
    (`paired_bootstrap_test`, REUTILISE), Brier, log loss, par tranche."""
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=float)
    base = reliability_bins(p, y, n_bins=n_bins)
    bin_idx = bin_index_for_prob(p, n_bins=n_bins)

    rows = []
    for b in range(n_bins):
        base_row = base.iloc[b]
        mask = bin_idx == b
        n = int(mask.sum())
        if n == 0:
            rows.append(
                {
                    "bin_lo": base_row["bin_lo"], "bin_hi": base_row["bin_hi"], "n": 0,
                    "p_moyen": float("nan"), "freq_observee": float("nan"), "biais": float("nan"),
                    "biais_ic95_low": float("nan"), "biais_ic95_high": float("nan"),
                    "brier": float("nan"), "log_loss": float("nan"), "incertitude_elevee": True,
                }
            )
            continue
        pi, yi = p[mask], y[mask]
        eps = 1e-12
        logloss = float(np.mean(-(yi * np.log(np.clip(pi, eps, 1 - eps)) + (1 - yi) * np.log(np.clip(1 - pi, eps, 1 - eps)))))
        diffs = yi - pi
        boot = (
            paired_bootstrap_test(diffs, n_resamples=_N_RESAMPLES, seed=_SEED)
            if n >= 2
            else {"ci_low": float("nan"), "ci_high": float("nan")}
        )
        rows.append(
            {
                "bin_lo": base_row["bin_lo"],
                "bin_hi": base_row["bin_hi"],
                "n": n,
                "p_moyen": float(base_row["mean_predicted"]),
                "freq_observee": float(base_row["observed_frequency"]),
                "biais": float(base_row["observed_frequency"] - base_row["mean_predicted"]),
                "biais_ic95_low": boot["ci_low"],
                "biais_ic95_high": boot["ci_high"],
                "brier": float(np.mean((pi - yi) ** 2)),
                "log_loss": logloss,
                "incertitude_elevee": n < min_n,
            }
        )
    return pd.DataFrame(rows)


def calibration_slope_intercept(p: np.ndarray, y: np.ndarray) -> dict:
    """Regression de calibration de Cox (1958) : y ~ sigmoid(a + b*logit(p)).
    Pente=1 et intercept=0 -> calibration parfaite. PURE MESURE - ``p``
    n'est jamais modifie ni reutilise pour corriger une prediction future."""
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=float)
    if p.size < 2 or len(set(y.tolist())) < 2:
        return {"intercept": float("nan"), "slope": float("nan"), "converged": False}
    eps = 1e-6
    p_clipped = np.clip(p, eps, 1 - eps)
    logit_p = np.log(p_clipped / (1 - p_clipped))

    def neg_log_lik(params: np.ndarray) -> float:
        a, b = params
        z = a + b * logit_p
        return float(np.mean(np.logaddexp(0.0, -z) * y + np.logaddexp(0.0, z) * (1 - y)))

    res = minimize(neg_log_lik, x0=np.array([0.0, 1.0]), method="Nelder-Mead")
    return {"intercept": float(res.x[0]), "slope": float(res.x[1]), "converged": bool(res.success)}


def point_biserial_correlation(p: np.ndarray, y: np.ndarray) -> float:
    """Correlation de Pearson entre la probabilite predite (continue) et
    l'issue (binaire) - mesure de discrimination brute."""
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=float)
    if p.size < 2 or np.std(p) == 0 or np.std(y) == 0:
        return float("nan")
    return float(np.corrcoef(p, y)[0, 1])


def summarize_reliability(p: np.ndarray, y: np.ndarray) -> dict:
    """Resume compact (utilise pour les sous-groupes championnat/saison -
    la table complete a 10 tranches n'est imprimee qu'au niveau GLOBAL)."""
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=float)
    n = p.size
    if n == 0:
        return {"n": 0, "insuffisant": True}
    slope_intercept = calibration_slope_intercept(p, y)
    corr = point_biserial_correlation(p, y)
    decomp = brier_decomposition(p, y, n_bins=_N_BINS) if n >= 2 else None
    return {
        "n": n,
        "insuffisant": n < _MIN_N,
        "brier": float(np.mean((p - y) ** 2)),
        "biais": float(y.mean() - p.mean()),
        "slope": slope_intercept["slope"],
        "intercept": slope_intercept["intercept"],
        "correlation": corr,
        "resolution": decomp["resolution"] if decomp else float("nan"),
        "reliability": decomp["reliability"] if decomp else float("nan"),
    }


# --------------------------------------------------------------------------
# ETAPE 6 - comparaison inter-modeles (Brier, paires appariees, memes matchs)
# --------------------------------------------------------------------------


def compare_models_paired_brier(df_a: pd.DataFrame, df_b: pd.DataFrame, threshold: float) -> dict | None:
    """`paired_bootstrap_test` sur diff = Brier_a - Brier_b, restreint a
    l'INTERSECTION des match_id des deux modeles (jamais un a-plat non
    apparie)."""
    common = set(df_a["match_id"]) & set(df_b["match_id"])
    if len(common) < 2:
        return None
    a = df_a[df_a["match_id"].isin(common)].sort_values("match_id")
    b = df_b[df_b["match_id"].isin(common)].sort_values("match_id")
    col_p, col_y = f"p_over_{threshold}", f"outcome_over_{threshold}"
    brier_a = (a[col_p].to_numpy() - a[col_y].to_numpy()) ** 2
    brier_b = (b[col_p].to_numpy() - b[col_y].to_numpy()) ** 2
    diffs = brier_a - brier_b
    boot = paired_bootstrap_test(diffs, n_resamples=_N_RESAMPLES, seed=_SEED)
    return {"n": len(common), "boot": boot}


# --------------------------------------------------------------------------
# ETAPE 8-10 - comparaison au marche (H2, EXPLORATOIRE), Over 2.5 uniquement
# --------------------------------------------------------------------------


def reliable_bin_indices(cal_table: pd.DataFrame) -> set[int]:
    """Index des tranches de probabilite jugees FIABLES au sens H1 :
    n>=min_n ET IC95% du biais contenant 0. Decide MECANIQUEMENT a partir
    de la table de calibration deja calculee (meme ordre que
    `bin_index_for_prob`) - jamais choisi en regardant les prix."""
    reliable = cal_table[
        (~cal_table["incertitude_elevee"]) & (cal_table["biais_ic95_low"] <= 0) & (cal_table["biais_ic95_high"] >= 0)
    ]
    return set(reliable.index)


def build_market_comparison_dataframe(
    threshold_df: pd.DataFrame, records_by_id: dict[str, MultiBookmakerMatchRecord]
) -> pd.DataFrame:
    """Fusionne le DataFrame Over 2.5 (walk-forward) avec les cotes B365 -
    calcule fair_odds du modele, cote/probabilite B365 brute ET
    normalisee (jamais confondues), et l'ecart de prix RELATIF (%)."""
    rows = []
    for _, row in threshold_df.iterrows():
        rec = records_by_id.get(row["match_id"])
        if rec is None:
            continue
        over_by_bk = rec.odds_over_under_2_5.get("Over", {})
        under_by_bk = rec.odds_over_under_2_5.get("Under", {})
        if "B365" not in over_by_bk or "B365" not in under_by_bk:
            continue
        b365_odds = {"Over": over_by_bk["B365"], "Under": under_by_bk["B365"]}
        p_model = row["p_over_2.5"]
        fair_odds_model = 1.0 / p_model
        p_market_raw = 1.0 / b365_odds["Over"]
        overround = hold_percentage(b365_odds)
        p_market_normalized = remove_overround_proportional(b365_odds)["Over"]
        price_diff_pct = abs(b365_odds["Over"] - fair_odds_model) / fair_odds_model * 100.0

        rows.append(
            {
                "match_id": row["match_id"],
                "p_model": p_model,
                "fair_odds_model": fair_odds_model,
                "b365_odds_over": b365_odds["Over"],
                "p_market_raw": p_market_raw,
                "overround": overround,
                "p_market_normalized": p_market_normalized,
                "price_diff_pct": price_diff_pct,
                "outcome": row["outcome_over_2.5"],
            }
        )
    out = pd.DataFrame(rows)
    if not out.empty:
        out["bin_idx"] = bin_index_for_prob(out["p_model"].to_numpy())
    return out


def classify_price_diff(pct: float) -> str:
    for lo, hi, label in zip(_PRICE_DIFF_EDGES[:-1], _PRICE_DIFF_EDGES[1:], _PRICE_DIFF_LABELS):
        if lo <= pct < hi:
            return label
    raise AssertionError(f"pct={pct} hors de toute categorie - ne devrait jamais arriver (borne infinie).")


def price_diff_table(df: pd.DataFrame, min_n: int = _MIN_N) -> pd.DataFrame:
    """Table de la grille de prix (H2, EXPLORATOIRE) - IC95% bootstrap sur
    le biais (`paired_bootstrap_test`, REUTILISE), meme construction que
    `calibration_table` (protocole point 10 : n, p_model moyen, frequence
    reelle, biais, IC95%)."""
    cats = df["price_diff_pct"].apply(classify_price_diff)
    rows = []
    for label in _PRICE_DIFF_LABELS:
        mask = (cats == label).to_numpy()
        n = int(mask.sum())
        if n == 0:
            rows.append(
                {
                    "categorie": label, "n": 0, "p_model_moyen": float("nan"), "freq_reelle": float("nan"),
                    "biais": float("nan"), "biais_ic95_low": float("nan"), "biais_ic95_high": float("nan"),
                    "insuffisant": True,
                }
            )
            continue
        p = df.loc[mask, "p_model"].to_numpy()
        y = df.loc[mask, "outcome"].to_numpy()
        diffs = y - p
        boot = (
            paired_bootstrap_test(diffs, n_resamples=_N_RESAMPLES, seed=_SEED)
            if n >= 2
            else {"ci_low": float("nan"), "ci_high": float("nan")}
        )
        rows.append(
            {
                "categorie": label,
                "n": n,
                "p_model_moyen": float(p.mean()),
                "freq_reelle": float(y.mean()),
                "biais": float(y.mean() - p.mean()),
                "biais_ic95_low": boot["ci_low"],
                "biais_ic95_high": boot["ci_high"],
                "insuffisant": n < min_n,
            }
        )
    return pd.DataFrame(rows)


def _print_calibration_table(label: str, table: pd.DataFrame) -> None:
    typer.echo(f"  -- {label} --")
    for _, r in table.iterrows():
        flag = " [INCERTITUDE ELEVEE - n<30]" if r["incertitude_elevee"] else ""
        typer.echo(
            f"    [{r['bin_lo']:.1f}-{r['bin_hi']:.1f}) n={int(r['n']):<4} p_moyen={r['p_moyen']:.4f} "
            f"freq_obs={r['freq_observee']:.4f} biais={r['biais']:+.4f} "
            f"IC95%=[{r['biais_ic95_low']:+.4f},{r['biais_ic95_high']:+.4f}] "
            f"Brier={r['brier']:.4f} logloss={r['log_loss']:.4f}{flag}"
        )


@app.command()
def main() -> None:
    typer.echo("=== E11 : cartographie de la fiabilite des probabilites de buts (E8) vs B365 ===")
    typer.echo(
        "poisson_simple, dixon_coles et xg_model INCHANGES. Aucune nouvelle calibration/correction, "
        "aucun tuning, aucun arbitrage (hors perimetre - un seul bookmaker O/U).\n"
    )

    e9 = _load_e9()
    e8 = e9._load_e8()
    e7 = e8._load_e7()
    records = e9.load_all_multi_bookmaker_records()
    records_by_id = {r.match_id: r for r in records}
    typer.echo(f"Corpus multi-bookmaker exploitable (E9) : {len(records)} matchs\n")

    dfs_by_model: dict[str, pd.DataFrame] = {}
    for model in _MODELS:
        typer.echo(f"##### {model} #####")
        df = build_threshold_dataframe(e8, e7, model)
        dfs_by_model[model] = df
        typer.echo(f"  n (test walk-forward) = {len(df)}")

        for t in _THRESHOLDS:
            typer.echo(f"--- H1 : calibration absolue Over {t} (GLOBAL) ---")
            p = df[f"p_over_{t}"].to_numpy()
            y = df[f"outcome_over_{t}"].to_numpy()
            cal = calibration_table(p, y)
            _print_calibration_table(f"Over {t}", cal)
            si = calibration_slope_intercept(p, y)
            corr = point_biserial_correlation(p, y)
            decomp = brier_decomposition(p, y, n_bins=_N_BINS)
            typer.echo(
                f"    slope={si['slope']:.4f} intercept={si['intercept']:+.4f} correlation={corr:.4f} "
                f"resolution={decomp['resolution']:.4f} reliability={decomp['reliability']:.4f}"
            )

            typer.echo(f"  -- Sous-groupes Over {t} (resume, pas de table complete) --")
            for league in sorted(df["league"].unique()):
                sub = df[df["league"] == league]
                s = summarize_reliability(sub[f"p_over_{t}"].to_numpy(), sub[f"outcome_over_{t}"].to_numpy())
                flag = " [INSUFFISANT n<30]" if s.get("insuffisant") else ""
                typer.echo(
                    f"    {league:<16} n={s['n']:<4} Brier={s.get('brier', float('nan')):.4f} "
                    f"biais={s.get('biais', float('nan')):+.4f} slope={s.get('slope', float('nan')):.4f} "
                    f"corr={s.get('correlation', float('nan')):.4f}{flag}"
                )
            for season in sorted(df["season"].unique()):
                sub = df[df["season"] == season]
                s = summarize_reliability(sub[f"p_over_{t}"].to_numpy(), sub[f"outcome_over_{t}"].to_numpy())
                flag = " [INSUFFISANT n<30]" if s.get("insuffisant") else ""
                typer.echo(
                    f"    {season:<16} n={s['n']:<4} Brier={s.get('brier', float('nan')):.4f} "
                    f"biais={s.get('biais', float('nan')):+.4f} slope={s.get('slope', float('nan')):.4f} "
                    f"corr={s.get('correlation', float('nan')):.4f}{flag}"
                )
            typer.echo("")

    typer.echo("--- Comparaison inter-modeles (Brier, paires appariees, memes matchs) ---")
    for t in _THRESHOLDS:
        result = compare_models_paired_brier(dfs_by_model["poisson_simple"], dfs_by_model["xg_model"], t)
        if result is None:
            typer.echo(f"  Over {t} : donnees insuffisantes.")
            continue
        b = result["boot"]
        typer.echo(
            f"  Over {t} : poisson_simple vs xg_model (n={result['n']}) diff_Brier(IC95%)=[{b['ci_low']:+.4f},{b['ci_high']:+.4f}] p={b['p_value']:.4f}"
        )
    typer.echo("  (dixon_coles reproduit exactement poisson_simple sur Over/Under - deja etabli en K/E7/E8)\n")

    typer.echo("=== H2 (EXPLORATOIRE) : ecarts de prix B365 parmi les probabilites JUGEES FIABLES (Over 2.5) ===")
    for model in ("poisson_simple", "xg_model"):
        typer.echo(f"##### {model} #####")
        df = dfs_by_model[model]
        p = df["p_over_2.5"].to_numpy()
        y = df["outcome_over_2.5"].to_numpy()
        cal = calibration_table(p, y)
        reliable_idx = reliable_bin_indices(cal)
        reliable_ranges = [(cal.loc[i, "bin_lo"], cal.loc[i, "bin_hi"]) for i in sorted(reliable_idx)]
        typer.echo(f"  Tranches jugees fiables (n>=30, IC95% du biais contenant 0) : {reliable_ranges}")

        market_df = build_market_comparison_dataframe(df, records_by_id)
        if market_df.empty:
            typer.echo("    donnees insuffisantes pour la table de prix.\n")
            continue
        restricted = market_df[market_df["bin_idx"].isin(reliable_idx)]
        typer.echo(f"  n total marche = {len(market_df)} | n restreint aux tranches fiables = {len(restricted)}")
        if len(restricted) >= 2:
            table = price_diff_table(restricted)
            for _, r in table.iterrows():
                flag = " [INSUFFISANT n<30]" if r["insuffisant"] else ""
                typer.echo(
                    f"    {r['categorie']:<8} n={int(r['n']):<4} p_model_moyen={r['p_model_moyen']:.4f} "
                    f"freq_reelle={r['freq_reelle']:.4f} biais={r['biais']:+.4f} "
                    f"IC95%=[{r['biais_ic95_low']:+.4f},{r['biais_ic95_high']:+.4f}]{flag}"
                )
        else:
            typer.echo("    donnees insuffisantes pour la table de prix.")
        typer.echo("")

    typer.echo(
        "RESERVE : H2 est EXPLORATOIRE - aucun ecart de prix ci-dessus ne constitue une 'value' demontree "
        "ni une strategie. Aucun arbitrage (hors perimetre). Aucune conclusion de rentabilite. Aucun ROI, "
        "yield, Kelly, staking. poisson_simple, dixon_coles et xg_model restent inchanges."
    )
    typer.echo("\nARRET : E11 termine, conformement au protocole. Aucune experience E12 lancee automatiquement.")


if __name__ == "__main__":
    app()
