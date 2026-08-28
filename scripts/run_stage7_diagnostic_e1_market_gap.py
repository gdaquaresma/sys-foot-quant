"""CLI : DIAGNOSTIC post-E1 (aucune nouvelle experience economique, aucune
strategie, aucune optimisation - purement descriptif).

Contexte : l'experience E1 (`scripts/run_stage6_economic_b365_ev.py`) a
conclu a un SIGNAL NEGATIF (`poisson_simple` moins bien calibre que le
marche B365, strategie EV>0 deficitaire, IC95% entierement negatif). Ce
script repond a la question de suivi, strictement diagnostique :
"Pourquoi poisson_simple est-il inferieur a B365, et existe-t-il malgre
tout une information independante du marche que xG pourrait apporter ?"

INTERDICTIONS EXPLICITES (protocole valide avant execution) : aucune
nouvelle strategie de paris, aucun nouveau seuil EV, aucun Kelly/staking,
aucun bookmaker/marche supplementaire, `poisson_simple` INCHANGE, aucun
meta-modele/stacking/gate/poids optimal (B3.4 exclu), aucune nouvelle
donnee. Ce script ne fait que lire/agreger le dataset economique DEJA
construit (`economic_dataset.py`, INCHANGE) et y attacher, en parallele et
SANS RIEN MODIFIER, les predictions `xg_model` deja existantes (`B3`).

Structure (parties 1 a 9 du protocole) :
1. Decomposition de l'ecart poisson/marche (biais, dispersion, calibration,
   frequence des ecarts importants, par championnat/saison/issue/decile).
2. Caracterisation des zones ou poisson est mauvais (quintiles de
   probabilite du favori marche) - AUCUNE recherche de sous-groupe
   rentable, uniquement biais/calibration.
3. Comparaison des erreurs par match (Brier ligne par ligne), distribution
   de delta_error.
4. Test de l'information independante : le signe du desaccord
   poisson/marche predit-il encore le resultat une fois la probabilite de
   marche prise en compte (comparaison DEMEANEE par decile, bootstrap non
   apparie REUTILISE sans modification) ?
5-6. xG face au marche : erreurs corrigees, correlations d'erreurs entre
   poisson/xG/marche, differences appariees de Brier (purement
   descriptives, AUCUN meta-modele).
7. Verification explicite que les contraintes point-in-time sont
   IDENTIQUES a celles d'E1 (assertion de non-regression, pas une
   affirmation).
8. Data snooping documente.
9. Arret obligatoire - ce script ne retourne qu'un rapport.

Usage:
    python scripts/run_stage7_diagnostic_e1_market_gap.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.backtesting_engine.real_data_walk_forward import (  # noqa: E402
    RealModelConfig,
    build_real_match_records,
    run_real_data_walk_forward,
)
from sys_foot_quant.calibration_engine.reliability import reliability_bins  # noqa: E402
from sys_foot_quant.calibration_engine.significance import (  # noqa: E402
    paired_bootstrap_test,
    two_sample_bootstrap_test,
)
from sys_foot_quant.common.logging import get_logger  # noqa: E402
from sys_foot_quant.data_engine.market_odds.economic_dataset import (  # noqa: E402
    DECISION_OFFSET_HOURS,
    MIN_TRAIN_MATCHES,
    SELECTIONS,
    EconomicDatasetReport,
    build_economic_dataset,
)
from sys_foot_quant.data_engine.market_odds.football_data_loader import load_football_data_csv  # noqa: E402
from sys_foot_quant.football_model.xg_model import XGModel  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_EXPECTED_MATCHES = {"ligue1": 306, "premier_league": 380, "liga": 380}
_EXPECTED_TEAMS = {"ligue1": 18, "premier_league": 20, "liga": 20}

_UNDERSTAT_DIR = Path("research/xg_feasibility/runs")
_FOOTBALL_DATA_DIR = Path("research/market_odds/football_data/runs")

_DATASETS = {
    ("premier_league", "2024_25"): ("epl_2024_datesData.json", "E0_2024_25.csv"),
    ("premier_league", "2025_26"): ("epl_2025_datesData.json", "E0_2025_26.csv"),
    ("ligue1", "2024_25"): ("ligue1_2024_datesData.json", "F1_2024_25.csv"),
    ("ligue1", "2025_26"): ("ligue1_2025_datesData.json", "F1_2025_26.csv"),
    ("liga", "2024_25"): ("liga_2024_datesData.json", "SP1_2024_25.csv"),
    ("liga", "2025_26"): ("liga_2025_datesData.json", "SP1_2025_26.csv"),
}

# Seuils documentes pour "ecart important" (etape 1) - choix descriptifs,
# jamais utilises pour une regle de decision.
_LARGE_GAP_THRESHOLDS = (0.05, 0.10)
_N_QUANTILE_BINS = 5   # partie 2 : quintiles de probabilite du favori marche
_N_DECILES = 10        # partie 1 et 4 : deciles de probabilite de marche
_N_RESAMPLES = 10_000
_SEED = 0


def _verify_understat_integrity(name: str, raw: list[dict]) -> None:
    n = len(raw)
    if n != _EXPECTED_MATCHES[name]:
        raise ValueError(f"{name}: {n} matchs trouves, {_EXPECTED_MATCHES[name]} attendus.")
    ids = [m["id"] for m in raw]
    if len(set(ids)) != n:
        raise ValueError(f"{name}: doublons de match_id detectes.")
    teams = {m["h"]["title"] for m in raw} | {m["a"]["title"] for m in raw}
    if len(teams) != _EXPECTED_TEAMS[name]:
        raise ValueError(f"{name}: {len(teams)} equipes trouvees, {_EXPECTED_TEAMS[name]} attendues.")


def _fit_xg(goals_df, xg_df, decision_time):
    return XGModel().fit(xg_df)


def _load_e1_report(league: str, season: str) -> tuple[EconomicDatasetReport, list[dict]]:
    us_name, fd_name = _DATASETS[(league, season)]
    with open(_UNDERSTAT_DIR / us_name) as f:
        raw = json.load(f)
    _verify_understat_integrity(league, raw)
    fd_records = load_football_data_csv(_FOOTBALL_DATA_DIR / fd_name, league=league, season=season)
    report = build_economic_dataset(league, season, raw, fd_records)
    return report, raw


def _attach_xg_predictions(report: EconomicDatasetReport, raw: list[dict]) -> dict[str, tuple | None]:
    """Partie 5-6 : calcule p_xg pour EXACTEMENT les matchs deja retenus par
    E1 (`report.records`), en reutilisant `real_data_walk_forward` SANS
    MODIFICATION, avec les memes constantes que `economic_dataset.py`
    (`DECISION_OFFSET_HOURS`, `MIN_TRAIN_MATCHES`) - partie 7 (verification
    temporelle) : le `decision_time` recalcule ici DOIT etre identique,
    match par match, a celui deja stocke dans le dataset E1 - verifie par
    assertion, pas suppose."""
    real_records = build_real_match_records(raw, league=report.league)
    eval_ids = [r.match_id for r in report.records]
    configs = [RealModelConfig(name="xg_model", fit=_fit_xg, min_train_matches=MIN_TRAIN_MATCHES)]
    evaluations = run_real_data_walk_forward(
        real_records, eval_match_ids=eval_ids, decision_offset_hours=DECISION_OFFSET_HOURS, model_configs=configs
    )
    decision_time_e1 = {r.match_id: r.decision_time_utc for r in report.records}
    xg_by_id: dict[str, tuple | None] = {}
    for ev in evaluations:
        assert ev.decision_time == decision_time_e1[ev.match_id], (
            f"Incoherence point-in-time detectee pour {ev.match_id} - ne devrait jamais se produire "
            "(memes constantes, meme mecanisme que economic_dataset.py)."
        )
        xg_by_id[ev.match_id] = ev.predictions.get("xg_model")
    return xg_by_id


def _row_brier(probs: dict[str, float], outcome_selection: str) -> float:
    return float(sum((probs[s] - (1.0 if s == outcome_selection else 0.0)) ** 2 for s in SELECTIONS))


def build_diagnostic_dataframe(reports_and_xg: list[tuple[EconomicDatasetReport, dict]]) -> pd.DataFrame:
    """Une ligne par match du dataset E1 (memes matchs, memes contraintes
    point-in-time), avec p_xg attachee quand disponible (NaN sinon)."""
    rows = []
    for report, xg_by_id in reports_and_xg:
        for r in report.records:
            row = {
                "match_id": r.match_id,
                "league": r.league,
                "season": r.season,
                "outcome_selection": r.outcome_selection,
            }
            for s in SELECTIONS:
                row[f"model_prob_{s}"] = r.model_probs[s]
                row[f"implied_norm_{s}"] = r.implied_prob_normalized[s]
                row[f"edge_norm_{s}"] = r.edge_norm[s]
            row["erreur_poisson"] = _row_brier(r.model_probs, r.outcome_selection)
            row["erreur_marche"] = _row_brier(r.implied_prob_normalized, r.outcome_selection)

            p_xg = xg_by_id.get(r.match_id)
            row["has_xg"] = p_xg is not None
            for i, s in enumerate(SELECTIONS):
                row[f"xg_prob_{s}"] = p_xg[i] if p_xg is not None else np.nan
            row["erreur_xg"] = (
                _row_brier({s: p_xg[i] for i, s in enumerate(SELECTIONS)}, r.outcome_selection)
                if p_xg is not None
                else np.nan
            )
            rows.append(row)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# PARTIE 1 : decomposition de l'ecart
# --------------------------------------------------------------------------


def calibration_summary(df: pd.DataFrame, prefix: str, selection: str, n_bins: int = 10) -> dict:
    probs = df[f"{prefix}_{selection}"].to_numpy()
    outcomes = (df["outcome_selection"] == selection).to_numpy().astype(float)
    bins = reliability_bins(probs, outcomes, n_bins=n_bins)
    non_empty = bins[bins["count"] > 0]
    if non_empty.empty:
        return {"weighted_mean_abs_error": float("nan"), "n_bins_used": 0}
    abs_err = (non_empty["mean_predicted"] - non_empty["observed_frequency"]).abs()
    weighted = float((abs_err * non_empty["count"]).sum() / non_empty["count"].sum())
    return {"weighted_mean_abs_error": weighted, "n_bins_used": int(len(non_empty))}


def gap_decomposition(df: pd.DataFrame, selection: str) -> dict:
    gap = df[f"model_prob_{selection}"] - df[f"implied_norm_{selection}"]
    n = len(df)
    freq_large = {
        f"pct_ecart_abs_ge_{t:.2f}": float((gap.abs() >= t).mean()) for t in _LARGE_GAP_THRESHOLDS
    }
    return {
        "n": n,
        "biais_moyen": float(gap.mean()),
        "biais_median": float(gap.median()),
        "dispersion_std": float(gap.std()),
        "calibration_poisson": calibration_summary(df, "model_prob", selection),
        "calibration_marche": calibration_summary(df, "implied_norm", selection),
        **freq_large,
    }


def decile_table(df: pd.DataFrame, selection: str, n_bins: int = _N_DECILES) -> pd.DataFrame:
    """Performance conditionnelle selon la probabilite implicite du
    marche, par decile, pour UNE issue - sert aux parties 1 et 2 (ne
    selectionne rien, decrit l'ensemble du spectre)."""
    sub = df.copy()
    sub["decile"] = pd.qcut(sub[f"implied_norm_{selection}"], n_bins, labels=False, duplicates="drop")
    outcome_ind = (sub["outcome_selection"] == selection).astype(float)
    grouped = sub.groupby("decile").apply(
        lambda g: pd.Series(
            {
                "n": len(g),
                "market_prob_moy": g[f"implied_norm_{selection}"].mean(),
                "poisson_prob_moy": g[f"model_prob_{selection}"].mean(),
                "freq_observee": (g["outcome_selection"] == selection).mean(),
            }
        ),
        include_groups=False,
    )
    grouped["biais_poisson"] = grouped["poisson_prob_moy"] - grouped["freq_observee"]
    grouped["biais_marche"] = grouped["market_prob_moy"] - grouped["freq_observee"]
    return grouped.reset_index()


# --------------------------------------------------------------------------
# PARTIE 2 : ou poisson perd (quintiles de probabilite du favori marche)
# --------------------------------------------------------------------------


def favorite_quintile_table(df: pd.DataFrame, n_bins: int = _N_QUANTILE_BINS) -> pd.DataFrame:
    sub = df.copy()
    market_probs = sub[[f"implied_norm_{s}" for s in SELECTIONS]].to_numpy()
    fav_idx = market_probs.argmax(axis=1)
    fav_selection = [SELECTIONS[i] for i in fav_idx]
    sub["favorite_selection"] = fav_selection
    sub["favorite_prob_marche"] = market_probs.max(axis=1)
    sub["favorite_prob_poisson"] = [
        sub.iloc[i][f"model_prob_{fav_selection[i]}"] for i in range(len(sub))
    ]
    sub["favorite_won"] = (sub["outcome_selection"] == sub["favorite_selection"]).astype(float)
    sub["quintile"] = pd.qcut(sub["favorite_prob_marche"], n_bins, labels=False, duplicates="drop")

    rows = []
    for q, g in sub.groupby("quintile"):
        brier_poisson = g.apply(
            lambda r: _row_brier({s: r[f"model_prob_{s}"] for s in SELECTIONS}, r["outcome_selection"]), axis=1
        ).mean()
        brier_marche = g.apply(
            lambda r: _row_brier({s: r[f"implied_norm_{s}"] for s in SELECTIONS}, r["outcome_selection"]), axis=1
        ).mean()
        rows.append(
            {
                "quintile": int(q),
                "n": len(g),
                "favorite_prob_marche_moy": g["favorite_prob_marche"].mean(),
                "favorite_prob_poisson_moy": g["favorite_prob_poisson"].mean(),
                "freq_favori_gagne": g["favorite_won"].mean(),
                "biais_poisson": g["favorite_prob_poisson"].mean() - g["favorite_won"].mean(),
                "biais_marche": g["favorite_prob_marche"].mean() - g["favorite_won"].mean(),
                "brier_poisson_moy": brier_poisson,
                "brier_marche_moy": brier_marche,
            }
        )
    return pd.DataFrame(rows).sort_values("quintile").reset_index(drop=True)


# --------------------------------------------------------------------------
# PARTIE 3 : comparaison des erreurs par match
# --------------------------------------------------------------------------


def delta_error_distribution(df: pd.DataFrame) -> dict:
    delta = df["erreur_poisson"] - df["erreur_marche"]
    return {
        "n": len(delta),
        "moyenne": float(delta.mean()),
        "std": float(delta.std()),
        "p10": float(delta.quantile(0.10)),
        "p25": float(delta.quantile(0.25)),
        "p50": float(delta.quantile(0.50)),
        "p75": float(delta.quantile(0.75)),
        "p90": float(delta.quantile(0.90)),
        "pct_poisson_meilleur": float((delta < -0.05).mean()),
        "pct_proche": float((delta.abs() <= 0.05).mean()),
        "pct_marche_meilleur": float((delta > 0.05).mean()),
    }


# --------------------------------------------------------------------------
# PARTIE 4 : information independante (desaccord poisson/marche)
# --------------------------------------------------------------------------


def independent_information_test(df: pd.DataFrame, selection: str, n_bins: int = _N_DECILES) -> dict | None:
    """Le signe du desaccord poisson-marche predit-il encore le resultat
    une fois la probabilite de marche prise en compte ? Demeaning par
    decile de probabilite de marche (variable disponible avant le match),
    puis comparaison NON appariee (groupes de matchs differents) via
    ``two_sample_bootstrap_test`` REUTILISE SANS MODIFICATION - aucun
    nouveau modele, aucune variable construite a partir du resultat (le
    decile utilise uniquement `implied_norm`, connu avant le match ;
    seule la moyenne PAR decile, calculee sur l'echantillon, sert de
    reference descriptive, jamais utilisee pour predire un match
    individuel)."""
    sub = df.copy()
    sub["decile"] = pd.qcut(sub[f"implied_norm_{selection}"], n_bins, labels=False, duplicates="drop")
    outcome_ind = (sub["outcome_selection"] == selection).astype(float)
    decile_mean = outcome_ind.groupby(sub["decile"]).transform("mean")
    demeaned = outcome_ind - decile_mean

    edge = sub[f"edge_norm_{selection}"]
    pos = demeaned[edge > 0].to_numpy()
    neg = demeaned[edge <= 0].to_numpy()
    if len(pos) == 0 or len(neg) == 0:
        return None
    boot = two_sample_bootstrap_test(pos, neg, n_resamples=_N_RESAMPLES, seed=_SEED)
    return {"n_edge_positif": len(pos), "n_edge_negatif_ou_nul": len(neg), **boot}


# --------------------------------------------------------------------------
# PARTIE 5-6 : xG face au marche, information incrementale
# --------------------------------------------------------------------------


def xg_vs_market_summary(df: pd.DataFrame) -> dict:
    sub = df[df["has_xg"]].copy()
    n = len(sub)
    if n == 0:
        return {"n": 0}
    probs_poisson = sub[[f"model_prob_{s}" for s in SELECTIONS]].to_numpy()
    probs_xg = sub[[f"xg_prob_{s}" for s in SELECTIONS]].to_numpy()
    probs_market = sub[[f"implied_norm_{s}" for s in SELECTIONS]].to_numpy()
    outcome_idx = sub["outcome_selection"].map({s: i for i, s in enumerate(SELECTIONS)}).to_numpy()
    one_hot = np.zeros_like(probs_poisson)
    one_hot[np.arange(n), outcome_idx] = 1.0

    brier_poisson = float(np.mean(np.sum((probs_poisson - one_hot) ** 2, axis=1)))
    brier_xg = float(np.mean(np.sum((probs_xg - one_hot) ** 2, axis=1)))
    brier_marche = float(np.mean(np.sum((probs_market - one_hot) ** 2, axis=1)))

    erreur_poisson = sub["erreur_poisson"].to_numpy()
    erreur_xg = sub["erreur_xg"].to_numpy()
    erreur_marche = sub["erreur_marche"].to_numpy()

    corr_poisson_marche = float(np.corrcoef(erreur_poisson, erreur_marche)[0, 1])
    corr_xg_marche = float(np.corrcoef(erreur_xg, erreur_marche)[0, 1])
    corr_poisson_xg = float(np.corrcoef(erreur_poisson, erreur_xg)[0, 1])

    boot_xg_vs_marche = paired_bootstrap_test(erreur_xg - erreur_marche, n_resamples=_N_RESAMPLES, seed=_SEED)
    boot_poisson_vs_marche = paired_bootstrap_test(
        erreur_poisson - erreur_marche, n_resamples=_N_RESAMPLES, seed=_SEED
    )
    boot_xg_vs_poisson = paired_bootstrap_test(erreur_xg - erreur_poisson, n_resamples=_N_RESAMPLES, seed=_SEED)

    return {
        "n": n,
        "brier_poisson": brier_poisson,
        "brier_xg": brier_xg,
        "brier_marche": brier_marche,
        "corr_erreur_poisson_marche": corr_poisson_marche,
        "corr_erreur_xg_marche": corr_xg_marche,
        "corr_erreur_poisson_xg": corr_poisson_xg,
        "diff_xg_moins_marche": boot_xg_vs_marche,
        "diff_poisson_moins_marche": boot_poisson_vs_marche,
        "diff_xg_moins_poisson": boot_xg_vs_poisson,
    }


# --------------------------------------------------------------------------
# Impression du rapport
# --------------------------------------------------------------------------


def _fmt_boot(b: dict) -> str:
    return f"diff_moy={b['mean_diff']:+.5f} IC95%=[{b['ci_low']:+.5f}, {b['ci_high']:+.5f}] p={b['p_value']:.4f}"


@app.command()
def main() -> None:
    typer.echo("=== DIAGNOSTIC POST-E1 : ou poisson_simple perd-il, et le xG apporte-t-il une info independante ? ===\n")

    reports_and_xg = []
    for league, season in _DATASETS:
        report, raw = _load_e1_report(league, season)
        xg_by_id = _attach_xg_predictions(report, raw)
        reports_and_xg.append((report, xg_by_id))

    df = build_diagnostic_dataframe(reports_and_xg)
    typer.echo(f"Matchs E1 (identiques, memes contraintes point-in-time verifiees) : {len(df)}")
    typer.echo(f"...dont avec prediction xG disponible : {int(df['has_xg'].sum())}\n")

    # --- PARTIE 1 --------------------------------------------------------
    typer.echo("=== PARTIE 1 : decomposition de l'ecart poisson/marche ===")
    for s in SELECTIONS:
        d = gap_decomposition(df, s)
        typer.echo(
            f"  [{s:<5}] n={d['n']:<5} biais_moy={d['biais_moyen']:+.4f} biais_med={d['biais_median']:+.4f} "
            f"std={d['dispersion_std']:.4f}  cal_poisson={d['calibration_poisson']['weighted_mean_abs_error']:.4f} "
            f"cal_marche={d['calibration_marche']['weighted_mean_abs_error']:.4f}  "
            f"ecart>=0.05={d['pct_ecart_abs_ge_0.05']:.3f} ecart>=0.10={d['pct_ecart_abs_ge_0.10']:.3f}"
        )
    typer.echo("\n  -- par championnat --")
    for league in sorted(df["league"].unique()):
        sub = df[df["league"] == league]
        for s in SELECTIONS:
            d = gap_decomposition(sub, s)
            typer.echo(
                f"  [{league:<16} {s:<5}] n={d['n']:<5} biais_moy={d['biais_moyen']:+.4f} "
                f"cal_poisson={d['calibration_poisson']['weighted_mean_abs_error']:.4f} "
                f"cal_marche={d['calibration_marche']['weighted_mean_abs_error']:.4f}"
            )
    typer.echo("\n  -- par saison --")
    for season in sorted(df["season"].unique()):
        sub = df[df["season"] == season]
        for s in SELECTIONS:
            d = gap_decomposition(sub, s)
            typer.echo(
                f"  [{season:<8} {s:<5}] n={d['n']:<5} biais_moy={d['biais_moyen']:+.4f} "
                f"cal_poisson={d['calibration_poisson']['weighted_mean_abs_error']:.4f} "
                f"cal_marche={d['calibration_marche']['weighted_mean_abs_error']:.4f}"
            )
    typer.echo("\n  -- deciles de probabilite de marche (global) --")
    for s in SELECTIONS:
        typer.echo(f"  [{s}]")
        table = decile_table(df, s)
        for _, row in table.iterrows():
            typer.echo(
                f"    decile={int(row['decile'])} n={int(row['n']):<4} market={row['market_prob_moy']:.3f} "
                f"poisson={row['poisson_prob_moy']:.3f} freq_obs={row['freq_observee']:.3f} "
                f"biais_poisson={row['biais_poisson']:+.3f} biais_marche={row['biais_marche']:+.3f}"
            )

    # --- PARTIE 2 --------------------------------------------------------
    typer.echo("\n=== PARTIE 2 : quintiles de probabilite du favori marche (caracterisation, pas de selection) ===")
    fav_table = favorite_quintile_table(df)
    for _, row in fav_table.iterrows():
        typer.echo(
            f"  Q{int(row['quintile'])} n={int(row['n']):<4} fav_marche={row['favorite_prob_marche_moy']:.3f} "
            f"fav_poisson={row['favorite_prob_poisson_moy']:.3f} freq_gagne={row['freq_favori_gagne']:.3f} "
            f"biais_poisson={row['biais_poisson']:+.3f} biais_marche={row['biais_marche']:+.3f} "
            f"brier_poisson={row['brier_poisson_moy']:.4f} brier_marche={row['brier_marche_moy']:.4f}"
        )

    # --- PARTIE 3 --------------------------------------------------------
    typer.echo("\n=== PARTIE 3 : distribution de delta_error = erreur_poisson - erreur_marche ===")
    dd = delta_error_distribution(df)
    typer.echo(
        f"  n={dd['n']} moyenne={dd['moyenne']:+.4f} std={dd['std']:.4f} "
        f"p10={dd['p10']:+.4f} p25={dd['p25']:+.4f} p50={dd['p50']:+.4f} p75={dd['p75']:+.4f} p90={dd['p90']:+.4f}"
    )
    typer.echo(
        f"  pct_poisson_meilleur(delta<-0.05)={dd['pct_poisson_meilleur']:.3f}  "
        f"pct_proche(|delta|<=0.05)={dd['pct_proche']:.3f}  pct_marche_meilleur(delta>0.05)={dd['pct_marche_meilleur']:.3f}"
    )

    # --- PARTIE 4 --------------------------------------------------------
    typer.echo("\n=== PARTIE 4 : information independante du desaccord poisson/marche (demeanee par decile) ===")
    for s in SELECTIONS:
        res = independent_information_test(df, s)
        if res is None:
            typer.echo(f"  [{s}] echantillon insuffisant.")
            continue
        typer.echo(
            f"  [{s:<5}] n_edge+={res['n_edge_positif']:<5} n_edge-/0={res['n_edge_negatif_ou_nul']:<5} "
            f"{_fmt_boot(res)}"
        )

    # --- PARTIE 5-6 --------------------------------------------------------
    typer.echo("\n=== PARTIE 5-6 : xG face au marche (sous-ensemble avec prediction xG disponible) ===")
    xgs = xg_vs_market_summary(df)
    if xgs["n"] == 0:
        typer.echo("  Aucun match avec prediction xG disponible sur ce corpus.")
    else:
        typer.echo(
            f"  n={xgs['n']}  Brier poisson={xgs['brier_poisson']:.4f}  Brier xG={xgs['brier_xg']:.4f}  "
            f"Brier marche={xgs['brier_marche']:.4f}"
        )
        typer.echo(
            f"  correlations d'erreurs : (poisson,marche)={xgs['corr_erreur_poisson_marche']:+.4f}  "
            f"(xG,marche)={xgs['corr_erreur_xg_marche']:+.4f}  (poisson,xG)={xgs['corr_erreur_poisson_xg']:+.4f}"
        )
        typer.echo(f"  diff appariee xG - marche      : {_fmt_boot(xgs['diff_xg_moins_marche'])}")
        typer.echo(f"  diff appariee poisson - marche  : {_fmt_boot(xgs['diff_poisson_moins_marche'])}")
        typer.echo(f"  diff appariee xG - poisson       : {_fmt_boot(xgs['diff_xg_moins_poisson'])}")

    # --- PARTIE 7-9 --------------------------------------------------------
    typer.echo("\n=== PARTIE 7 : verification temporelle ===")
    typer.echo(
        "  OK - les predictions xG ont ete calculees sur EXACTEMENT les matchs du dataset E1, avec les "
        "memes constantes (DECISION_OFFSET_HOURS, MIN_TRAIN_MATCHES) et le meme mecanisme "
        "(real_data_walk_forward, inchange) ; assertion decision_time identique verifiee match par match "
        "sans exception (le script se serait arrete sinon)."
    )
    typer.echo(
        "\n=== PARTIE 8 : data snooping ===\n"
        "  Cette analyse est directement motivee par le resultat SIGNAL NEGATIF d'E1 - elle est donc "
        "diagnostique et exploratoire par construction. Aucune conclusion de rentabilite n'est tiree "
        "d'un sous-groupe (quintile, decile, championnat, saison) decouvert pendant cette analyse."
    )
    typer.echo(
        "\n=== PARTIE 9 : arret obligatoire ===\n"
        "  Aucune nouvelle experience economique, aucune strategie, aucun seuil, aucun modele ne suivent "
        "ce script. Ce rapport sert uniquement a decider de la prochaine hypothese scientifique."
    )


if __name__ == "__main__":
    app()
