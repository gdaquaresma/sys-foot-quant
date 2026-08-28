"""CLI : E6 - le marche Over/Under 2.5 apporte-t-il une information
incrementale sur le total de buts par rapport a notre modele ?

Question centrale : a esperance de buts du modele comparable, le marche
distingue-t-il encore des differences de total reel ? Et inversement, a
probabilite marche comparable, l'esperance du modele distingue-t-elle
encore des differences ? PAS "peut-on gagner de l'argent avec cette
information" - une question de contenu informationnel, pas de
rentabilite.

`poisson_simple` et `xg_model` restent INCHANGES. Aucun nouveau modele
predictif, aucune nouvelle calibration (reutilise SANS RECALCUL la
calibration isotonique deja ajustee en E2/E3, via
`run_stage13_e5_model_market_agreement_over25.compute_calibrated_probs`,
et les cotes marche point-in-time deja construites en E5, via
`build_pooled_over_under_odds`). Meme perimetre de donnees et memes
regles temporelles que E5 - aucune nouvelle hypothese.

INSPECTION PREALABLE DES OUTILS EXISTANTS (avant toute implementation) :
- `calibration_engine.decomposition.brier_decomposition` (E2/E3) :
  directement applicable ici, REUTILISEE SANS MODIFICATION, pour comparer
  le pouvoir de discrimination de la probabilite modele calibree et de la
  probabilite marche normalisee sur le MEME evenement binaire (Over 2.5).
- `calibration_engine.significance.two_sample_bootstrap_test` (deja
  utilise en diagnostic post-E1, section 4) : l'outil EXACT pour la
  question centrale d'E6 - comparer deux groupes NON apparies (definis
  par une variable) sur la frequence reelle d'un evenement, en
  controlant (par stratification, pas par regression) une autre
  variable. REUTILISEE SANS MODIFICATION.
- `market_engine.overround.remove_overround_proportional` (E1/E5) :
  formule de marche INCHANGEE.
- Aucun nouveau modele predictif, aucune nouvelle metrique statistique
  sophistiquee : uniquement des tranches fixes, des moyennes, des
  correlations et les deux outils bootstrap deja presents.

Seuils d'analyse conditionnelle : 50% pour la probabilite de marche (le
seuil naturel du marche Over/Under lui-meme - pas une recherche), 2.5 buts
pour l'esperance du modele (la ligne du marche lui-meme, deja fixee par
construction du produit Over/Under 2.5 - pas une recherche non plus).
Aucun seuil optimise apres observation des resultats.

INTERDIT (verifie explicitement dans le rapport, jamais depasse) : ROI,
yield, simulation de paris, seuil de cote, regle BET, formule de value,
Kelly, autres bookmakers, autres marches, recherche de combinaison
optimale apres coup.

Usage:
    python scripts/run_stage14_e6_market_incremental_information.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.calibration_engine.decomposition import brier_decomposition  # noqa: E402
from sys_foot_quant.calibration_engine.significance import two_sample_bootstrap_test  # noqa: E402
from sys_foot_quant.common.logging import get_logger  # noqa: E402
from sys_foot_quant.market_engine.overround import remove_overround_proportional  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_MODELS = ("poisson_simple", "xg_model")
_N_RESAMPLES = 10_000
_SEED = 0
_MIN_N_FOR_LOW_UNCERTAINTY = 30  # meme seuil documente que E5

# Tranches FIXEES AVANT EXECUTION - jamais modifiees apres observation.
_EXPECTED_GOALS_EDGES = [-np.inf, 2.0, 2.5, 3.0, 3.5, np.inf]
_EXPECTED_GOALS_LABELS = ["<2.0", "2.0-2.5", "2.5-3.0", "3.0-3.5", ">=3.5"]

_MARKET_PROB_EDGES = [-np.inf, 0.45, 0.50, 0.55, 0.60, np.inf]
_MARKET_PROB_LABELS = ["<45%", "45-50%", "50-55%", "55-60%", ">=60%"]

# Seuils NATURELS (pas recherches) pour les deux tests d'information
# incrementale : la ligne du marche elle-meme (2.5 buts) et le seuil de
# decision naturel d'une probabilite Over/Under (50%).
_MARKET_NATURAL_SPLIT = 0.50
_MODEL_NATURAL_SPLIT = 2.5

_STAGE13_PATH = Path(__file__).resolve().parent / "run_stage13_e5_model_market_agreement_over25.py"


def _load_stage13():
    spec = importlib.util.spec_from_file_location("run_stage13_e5_model_market_agreement_over25", _STAGE13_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def build_e6_dataframe(
    model: str,
    calibration_df: pd.DataFrame,
    test_df: pd.DataFrame,
    odds_by_match_id: dict[str, tuple[float, float]],
    stage13_module,
) -> pd.DataFrame:
    """Assemble, pour UN modele, les quatre grandeurs necessaires a E6 :
    esperance de buts BRUTE (E4), probabilite Over 2.5 CALIBREE (E2/E3,
    reutilisee via `compute_calibrated_probs`), probabilite de marche
    normalisee (overround retire, INCHANGE) et resultat reel. Un match
    sans cote marche point-in-time valide, ou sans historique suffisant
    pour l'un ou l'autre modele, est exclu (jamais silencieusement)."""
    exp_col = f"{model}_lambda_plus_mu"
    p_col = f"{model}_p_over_2.5"
    test = test_df.dropna(subset=[exp_col, p_col]).set_index("match_id")

    p_model_calibrated = stage13_module.compute_calibrated_probs(calibration_df, test_df, model)

    rows = []
    for match_id, p_model in p_model_calibrated.items():
        if match_id not in odds_by_match_id or match_id not in test.index:
            continue
        b365_over, b365_under = odds_by_match_id[match_id]
        p_market = remove_overround_proportional({"over": b365_over, "under": b365_under})["over"]
        row = test.loc[match_id]
        total_goals = float(row["total_goals"])
        rows.append(
            {
                "match_id": match_id,
                "league": row["league"],
                "season": row["season"],
                "expected_goals": float(row[exp_col]),
                "p_model_over25": float(p_model),
                "p_market_over25": float(p_market),
                "total_goals": total_goals,
                "outcome_over25": float(total_goals > 2.5),
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Section 2 : redondance vs complementarite (descriptif, pas de conclusion
# a partir de la seule correlation)
# --------------------------------------------------------------------------


def correlation_matrix(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["expected_goals", "p_model_over25", "p_market_over25"]
    return df[cols].corr()


# --------------------------------------------------------------------------
# Section 3 : tranches fixes d'esperance de buts
# --------------------------------------------------------------------------


def expected_goals_bin_table(df: pd.DataFrame) -> pd.DataFrame:
    cats = pd.cut(df["expected_goals"], bins=_EXPECTED_GOALS_EDGES, labels=_EXPECTED_GOALS_LABELS, right=False)
    rows = []
    for label in _EXPECTED_GOALS_LABELS:
        mask = cats == label
        n = int(mask.sum())
        if n == 0:
            rows.append(
                {
                    "tranche": label, "n": 0, "expected_moy": float("nan"), "total_reel_moy": float("nan"),
                    "freq_over25_reelle": float("nan"), "p_model_moy": float("nan"), "p_market_moy": float("nan"),
                }
            )
            continue
        rows.append(
            {
                "tranche": label,
                "n": n,
                "expected_moy": float(df.loc[mask, "expected_goals"].mean()),
                "total_reel_moy": float(df.loc[mask, "total_goals"].mean()),
                "freq_over25_reelle": float(df.loc[mask, "outcome_over25"].mean()),
                "p_model_moy": float(df.loc[mask, "p_model_over25"].mean()),
                "p_market_moy": float(df.loc[mask, "p_market_over25"].mean()),
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Section 5 : grille conditionnelle (esperance x probabilite marche)
# --------------------------------------------------------------------------


def conditional_grid(df: pd.DataFrame) -> pd.DataFrame:
    exp_cats = pd.cut(df["expected_goals"], bins=_EXPECTED_GOALS_EDGES, labels=_EXPECTED_GOALS_LABELS, right=False)
    mkt_cats = pd.cut(df["p_market_over25"], bins=_MARKET_PROB_EDGES, labels=_MARKET_PROB_LABELS, right=False)
    rows = []
    for e_label in _EXPECTED_GOALS_LABELS:
        for m_label in _MARKET_PROB_LABELS:
            mask = (exp_cats == e_label) & (mkt_cats == m_label)
            n = int(mask.sum())
            if n == 0:
                rows.append(
                    {
                        "expected_tranche": e_label, "market_tranche": m_label, "n": 0,
                        "expected_moy": float("nan"), "p_market_moy": float("nan"),
                        "freq_over25_reelle": float("nan"), "total_reel_moy": float("nan"),
                    }
                )
                continue
            rows.append(
                {
                    "expected_tranche": e_label,
                    "market_tranche": m_label,
                    "n": n,
                    "expected_moy": float(df.loc[mask, "expected_goals"].mean()),
                    "p_market_moy": float(df.loc[mask, "p_market_over25"].mean()),
                    "freq_over25_reelle": float(df.loc[mask, "outcome_over25"].mean()),
                    "total_reel_moy": float(df.loc[mask, "total_goals"].mean()),
                }
            )
    return pd.DataFrame(rows)


def market_incremental_info_test(df: pd.DataFrame) -> pd.DataFrame:
    """Section 5, test central : a esperance de buts comparable (a
    l'interieur de chaque tranche fixe), le marche (seuil naturel 50%)
    distingue-t-il encore une frequence reelle d'Over 2.5 differente ?
    ``two_sample_bootstrap_test`` REUTILISE SANS MODIFICATION."""
    exp_cats = pd.cut(df["expected_goals"], bins=_EXPECTED_GOALS_EDGES, labels=_EXPECTED_GOALS_LABELS, right=False)
    rows = []
    for e_label in _EXPECTED_GOALS_LABELS:
        sub = df[exp_cats == e_label]
        low = sub.loc[sub["p_market_over25"] < _MARKET_NATURAL_SPLIT, "outcome_over25"].to_numpy()
        high = sub.loc[sub["p_market_over25"] >= _MARKET_NATURAL_SPLIT, "outcome_over25"].to_numpy()
        if len(low) == 0 or len(high) == 0:
            rows.append(
                {"tranche": e_label, "n_marche_bas": len(low), "n_marche_haut": len(high), "diff": float("nan"), "ci_low": float("nan"), "ci_high": float("nan"), "p_value": float("nan"), "incertitude_elevee": True}
            )
            continue
        boot = two_sample_bootstrap_test(high, low, n_resamples=_N_RESAMPLES, seed=_SEED)
        rows.append(
            {
                "tranche": e_label,
                "n_marche_bas": len(low),
                "n_marche_haut": len(high),
                "diff": boot["mean_diff"],
                "ci_low": boot["ci_low"],
                "ci_high": boot["ci_high"],
                "p_value": boot["p_value"],
                "incertitude_elevee": min(len(low), len(high)) < _MIN_N_FOR_LOW_UNCERTAINTY,
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Section 6 : analyse inverse
# --------------------------------------------------------------------------


def model_incremental_info_test(df: pd.DataFrame) -> pd.DataFrame:
    """A probabilite marche comparable (tranche fixe), l'esperance du
    modele (seuil naturel 2.5 buts, la ligne elle-meme) distingue-t-elle
    encore une frequence reelle d'Over 2.5 differente ?"""
    mkt_cats = pd.cut(df["p_market_over25"], bins=_MARKET_PROB_EDGES, labels=_MARKET_PROB_LABELS, right=False)
    rows = []
    for m_label in _MARKET_PROB_LABELS:
        sub = df[mkt_cats == m_label]
        low = sub.loc[sub["expected_goals"] < _MODEL_NATURAL_SPLIT, "outcome_over25"].to_numpy()
        high = sub.loc[sub["expected_goals"] >= _MODEL_NATURAL_SPLIT, "outcome_over25"].to_numpy()
        if len(low) == 0 or len(high) == 0:
            rows.append(
                {"tranche": m_label, "n_modele_bas": len(low), "n_modele_haut": len(high), "diff": float("nan"), "ci_low": float("nan"), "ci_high": float("nan"), "p_value": float("nan"), "incertitude_elevee": True}
            )
            continue
        boot = two_sample_bootstrap_test(high, low, n_resamples=_N_RESAMPLES, seed=_SEED)
        rows.append(
            {
                "tranche": m_label,
                "n_modele_bas": len(low),
                "n_modele_haut": len(high),
                "diff": boot["mean_diff"],
                "ci_low": boot["ci_low"],
                "ci_high": boot["ci_high"],
                "p_value": boot["p_value"],
                "incertitude_elevee": min(len(low), len(high)) < _MIN_N_FOR_LOW_UNCERTAINTY,
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Section 7 : discrimination (reutilisation directe)
# --------------------------------------------------------------------------


def discrimination_summary(df: pd.DataFrame) -> dict:
    decomp_model = brier_decomposition(df["p_model_over25"].to_numpy(), df["outcome_over25"].to_numpy())
    decomp_market = brier_decomposition(df["p_market_over25"].to_numpy(), df["outcome_over25"].to_numpy())
    corr_expected_total = float(np.corrcoef(df["expected_goals"], df["total_goals"])[0, 1])
    return {"decomp_model": decomp_model, "decomp_market": decomp_market, "corr_expected_total": corr_expected_total}


def _print_bin_table(df: pd.DataFrame, title: str) -> None:
    typer.echo(f"  {title}")
    for _, row in df.iterrows():
        if row["n"] == 0:
            typer.echo(f"    {row['tranche']:<10} n=0")
            continue
        typer.echo(
            f"    {row['tranche']:<10} n={int(row['n']):<5} esperance_moy={row['expected_moy']:.3f} "
            f"total_reel_moy={row['total_reel_moy']:.3f} freq_over25_reelle={row['freq_over25_reelle']:.3f} "
            f"p_model_moy={row['p_model_moy']:.3f} p_market_moy={row['p_market_moy']:.3f}"
        )


def _print_incremental_test(df: pd.DataFrame, group_a: str, group_b: str) -> None:
    for _, row in df.iterrows():
        flag = " [INCERTITUDE ELEVEE]" if row.get("incertitude_elevee") else ""
        na = row.get("n_marche_bas", row.get("n_modele_bas"))
        nb = row.get("n_marche_haut", row.get("n_modele_haut"))
        typer.echo(
            f"    {row['tranche']:<10} n_{group_a}={int(na):<5} n_{group_b}={int(nb):<5} "
            f"diff({group_b}-{group_a})={row['diff']:+.4f} IC95%=[{row['ci_low']:+.4f}, {row['ci_high']:+.4f}] "
            f"p={row['p_value']:.4f}{flag}"
        )


def _run_scope(label: str, df: pd.DataFrame) -> None:
    typer.echo(f"-- {label} (n={len(df)}) --")
    if len(df) < 10:
        typer.echo("   donnees insuffisantes.")
        return
    _print_bin_table(expected_goals_bin_table(df), "Tranches fixes d'esperance de buts :")
    typer.echo("  Test d'information incrementale - MARCHE a esperance comparable (seuil naturel 50%) :")
    _print_incremental_test(market_incremental_info_test(df), "marche_bas", "marche_haut")
    typer.echo("  Test d'information incrementale INVERSE - MODELE a probabilite marche comparable (seuil naturel 2.5 buts) :")
    _print_incremental_test(model_incremental_info_test(df), "modele_bas", "modele_haut")
    disc = discrimination_summary(df)
    typer.echo(
        f"  Discrimination : resolution_modele={disc['decomp_model']['resolution']:.4f} "
        f"resolution_marche={disc['decomp_market']['resolution']:.4f} "
        f"fiabilite_modele={disc['decomp_model']['reliability']:.4f} "
        f"fiabilite_marche={disc['decomp_market']['reliability']:.4f} "
        f"corr(esperance,total_reel)={disc['corr_expected_total']:+.4f}"
    )


@app.command()
def main() -> None:
    typer.echo("=== E6 : le marche Over/Under 2.5 apporte-t-il une information incrementale sur le total de buts ? ===")
    typer.echo(
        "poisson_simple et xg_model INCHANGES. Aucun nouveau modele, aucune nouvelle calibration. "
        "Question de contenu informationnel, PAS de rentabilite.\n"
    )

    stage13 = _load_stage13()
    stage10 = stage13._load_stage10()
    stage8 = stage10._load_stage8()
    calibration_df, test_df = stage10.build_calibration_and_test_sets(stage8)
    odds_by_match_id, market_totals = stage13.build_pooled_over_under_odds()
    typer.echo(
        f"n_calibration={len(calibration_df)}  n_test={len(test_df)}  "
        f"cotes O/U point-in-time exploitables={market_totals['n_exploitable']}/{market_totals['n_understat']}\n"
    )

    for model in _MODELS:
        typer.echo(f"##### {model} (calibre) #####")
        df = build_e6_dataframe(model, calibration_df, test_df, odds_by_match_id, stage13)
        typer.echo(f"n matchs exploitables (modele + marche joints) : {len(df)}\n")

        corr = correlation_matrix(df)
        typer.echo("-- Section 2 : matrice de correlation (descriptif, pas de conclusion isolee) --")
        typer.echo(f"{corr.round(4)}\n")

        typer.echo("=== GLOBAL ===")
        _run_scope("GLOBAL", df)

        typer.echo("\n=== Stabilite par championnat ===")
        for league in sorted(df["league"].unique()):
            _run_scope(league, df[df["league"] == league])

        typer.echo("\n=== Stabilite par saison ===")
        for season in sorted(df["season"].unique()):
            _run_scope(season, df[df["season"] == season])
        typer.echo("")

    typer.echo(
        "RESERVE : aucune conclusion de rentabilite. Aucun ROI, yield, seuil de cote, regle BET, "
        "formule de value, Kelly, autre bookmaker/marche, ni combinaison recherchee apres coup. "
        "poisson_simple et xg_model restent inchanges, aucune nouvelle calibration creee."
    )
    typer.echo("\nARRET : E6 termine, conformement au protocole. Aucune experience suivante lancee automatiquement.")


if __name__ == "__main__":
    app()
