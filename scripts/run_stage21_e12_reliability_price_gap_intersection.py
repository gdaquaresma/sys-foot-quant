"""CLI : E12 - intersection entre fiabilite historique de la probabilite
modele et amplitude de l'ecart de prix avec B365.

Question centrale (fixee AVANT execution) : les tranches de probabilite
ou notre modele est historiquement bien calibre sont-elles AUSSI les
tranches ou l'ecart de prix avec B365 est le plus grand ? Il ne s'agit
JAMAIS de chercher a battre le marche globalement, ni de construire une
strategie de pari - uniquement de mesurer si ces deux proprietes
(fiabilite, amplitude de desaccord) coincident ou non.

`poisson_simple`, `dixon_coles` et `xg_model` restent INCHANGES. Aucun
nouveau modele, aucune nouvelle calibration, aucun tuning. Aucun ROI,
Kelly, staking, seuil optimise sur le resultat.

====================================================================
ETAPE 1 - INSPECTION E8/E9/E11 (avant tout code) - REUTILISATION STRICTE
====================================================================
- E11 (`run_stage20_e11_probability_reliability_mapping.py`) expose deja
  TOUT ce dont E12 a besoin, REUTILISE SANS MODIFICATION :
  `build_threshold_dataframe` (P_model walk-forward E8, 5 seuils derives
  de la MEME matrice), `calibration_table` (tranches de probabilite
  FIXEES ex ante, biais + IC95% bootstrap), `bin_index_for_prob`,
  `build_market_comparison_dataframe` (cotes B365 O/U 2.5, probabilite
  brute ET normalisee conservees separement, fair_odds du modele).
- E9 (`run_stage18_e9_multi_bookmaker_market_layer.py`) :
  `load_all_multi_bookmaker_records` - REUTILISE SANS MODIFICATION.
- `calibration_engine.significance.two_sample_bootstrap_test` REUTILISE
  SANS MODIFICATION pour le test central (point 5 du protocole).
- LIMITATION DE DONNEES CONFIRMEE (deja documentee en E9/E10/E11, jamais
  contournee) : B365 est le seul bookmaker Over/Under dans Football-Data,
  et Football-Data ne publie QUE la ligne 2.5 pour l'Over/Under (aucune
  cote marche pour 0.5/1.5/3.5/4.5). L'intersection fiabilite x ecart de
  prix n'est donc TESTABLE QUE sur Over 2.5 - les autres seuils ne
  peuvent recevoir qu'un diagnostic de fiabilite seul (deja etabli en
  E11), jamais une comparaison au marche.

====================================================================
ETAPE 2 - QUATRE NOTIONS STRICTEMENT DISTINCTES (jamais confondues)
====================================================================
1. PROBABILITE FIABLE : tranche de probabilite ou le biais (frequence
   reelle - probabilite annoncee) a un IC95% bootstrap contenant 0, avec
   n>=30 (`classify_bin_reliability`).
2. DESACCORD AVEC LE MARCHE : simple difference numerique
   gap = P_model - P_market_normalisee. Une difference n'est PAS en soi
   une preuve de quoi que ce soit (deja demontre en E10 - le desaccord
   seul n'est pas fiable).
3. ANOMALIE DE PRIX : notion reservee a E9 (un bookmaker s'ecarte du
   CONSENSUS DE PLUSIEURS bookmakers) - STRUCTURELLEMENT NON EVALUABLE
   ici, un seul bookmaker (B365) existe sur l'Over/Under. E12 ne mesure
   JAMAIS d'anomalie de prix au sens E9 - seulement un ecart modele/marche.
4. VALUE POTENTIELLE : NON EVALUEE ICI, quel que soit le resultat. Meme
   si l'hypothese du point 5 est confirmee, cela ne demontre AUCUNE
   rentabilite (aucun ROI, Kelly, staking, cout de transaction reel pris
   en compte).

====================================================================
ETAPE 2bis - GRILLE DE VERDICT (fixee AVANT execution reelle, point 9)
====================================================================
Test : `two_sample_bootstrap_test` sur |gap| entre les matchs des
tranches FIABLES et les matchs des tranches NON FIABLES (tranches
"insuffisant" exclues des deux groupes) :
    IC95% entierement > 0  -> "demontree statistiquement"
    IC95% entierement < 0  -> "contradictoire"
    IC95% contient 0, diff moyen > 0 -> "directionnelle mais non demontree"
    IC95% contient 0, diff moyen <= 0 -> "absence de preuve"

Usage:
    python scripts/run_stage21_e12_reliability_price_gap_intersection.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.calibration_engine.significance import two_sample_bootstrap_test  # noqa: E402
from sys_foot_quant.common.logging import get_logger  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_MODELS = ("poisson_simple", "dixon_coles", "xg_model")
_OTHER_THRESHOLDS = (0.5, 1.5, 3.5, 4.5)  # aucune donnee de marche disponible - diagnostic de fiabilite seul
_MIN_N = 30  # identique a E5/E10/E11
_N_RESAMPLES = 10_000
_SEED = 0

_STAGE20_PATH = Path(__file__).resolve().parent / "run_stage20_e11_probability_reliability_mapping.py"


def _load_e11():
    spec = importlib.util.spec_from_file_location("run_stage20_e11_probability_reliability_mapping", _STAGE20_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------
# ETAPE 2 - classification de fiabilite (PURE, opere sur des statistiques
# DEJA agregees - jamais sur une donnee individuelle future)
# --------------------------------------------------------------------------

FIABLE = "fiable"
NON_FIABLE = "non fiable - biais significatif"
INSUFFISANT = "insuffisant"


def classify_bin_reliability(n: int, ci_low: float, ci_high: float, min_n: int = _MIN_N) -> str:
    """Classe UNE tranche de probabilite deja resumee (n, bornes IC95% du
    biais) - jamais une observation individuelle, jamais l'issue future."""
    if n < min_n or np.isnan(ci_low) or np.isnan(ci_high):
        return INSUFFISANT
    if ci_low <= 0.0 <= ci_high:
        return FIABLE
    return NON_FIABLE


# --------------------------------------------------------------------------
# ETAPE 2bis - grille de verdict (PURE, fixee avant execution)
# --------------------------------------------------------------------------

VERDICT_DEMONTREE = "demontree statistiquement"
VERDICT_CONTRADICTOIRE = "contradictoire"
VERDICT_DIRECTIONNELLE = "directionnelle mais non demontree"
VERDICT_ABSENCE_PREUVE = "absence de preuve"


def classify_hypothesis_verdict(boot: dict) -> str:
    if boot["ci_low"] > 0.0:
        return VERDICT_DEMONTREE
    if boot["ci_high"] < 0.0:
        return VERDICT_CONTRADICTOIRE
    if boot["mean_diff"] > 0.0:
        return VERDICT_DIRECTIONNELLE
    return VERDICT_ABSENCE_PREUVE


# --------------------------------------------------------------------------
# ETAPE 3-4 - table jointe fiabilite x ecart de prix (Over 2.5 uniquement -
# seul seuil disposant d'une cote de marche reelle)
# --------------------------------------------------------------------------


def joint_bin_table(cal_table: pd.DataFrame, market_df: pd.DataFrame, min_n: int = _MIN_N) -> pd.DataFrame:
    """Une ligne par tranche de probabilite (memes tranches que
    `calibration_table`, index = bin_idx) - fusionne la fiabilite (H1,
    calculee sur TOUT le split test) et les statistiques de marche
    (calculees sur le sous-ensemble AVEC cote B365, necessairement plus
    restreint - `n_marche` reporte separement de `n` pour ne jamais les
    confondre)."""
    rows = []
    for bin_idx, cal_row in cal_table.iterrows():
        classification = classify_bin_reliability(cal_row["n"], cal_row["biais_ic95_low"], cal_row["biais_ic95_high"], min_n)
        sub = market_df[market_df["bin_idx"] == bin_idx]
        n_marche = len(sub)
        row = {
            "bin_lo": cal_row["bin_lo"],
            "bin_hi": cal_row["bin_hi"],
            "n": int(cal_row["n"]),
            "p_model_moyen": cal_row["p_moyen"],
            "freq_observee": cal_row["freq_observee"],
            "biais": cal_row["biais"],
            "biais_ic95_low": cal_row["biais_ic95_low"],
            "biais_ic95_high": cal_row["biais_ic95_high"],
            "classification_fiabilite": classification,
            "n_marche": n_marche,
        }
        if n_marche == 0:
            row.update(
                {
                    "p_market_brute_moyenne": float("nan"),
                    "p_market_normalisee_moyenne": float("nan"),
                    "gap_moyen": float("nan"),
                    "gap_abs_moyen": float("nan"),
                    "fair_odds_model_moyenne": float("nan"),
                    "b365_odds_moyenne": float("nan"),
                }
            )
        else:
            gap = sub["p_model"] - sub["p_market_normalized"]
            row.update(
                {
                    "p_market_brute_moyenne": float(sub["p_market_raw"].mean()),
                    "p_market_normalisee_moyenne": float(sub["p_market_normalized"].mean()),
                    "gap_moyen": float(gap.mean()),
                    "gap_abs_moyen": float(gap.abs().mean()),
                    "fair_odds_model_moyenne": float(sub["fair_odds_model"].mean()),
                    "b365_odds_moyenne": float(sub["b365_odds_over"].mean()),
                }
            )
        rows.append(row)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# ETAPE 5 - test central : les tranches fiables ont-elles un ecart de prix
# plus grand que les tranches non fiables ?
# --------------------------------------------------------------------------


def test_reliable_bins_have_larger_gaps(cal_table: pd.DataFrame, market_df: pd.DataFrame, min_n: int = _MIN_N) -> dict:
    """`two_sample_bootstrap_test` (REUTILISE) sur |gap| entre les matchs
    des tranches FIABLES et ceux des tranches NON FIABLES (tranches
    "insuffisant" exclues des deux groupes, jamais comptees comme
    fiables ni non fiables)."""
    reliable_idx: set[int] = set()
    non_reliable_idx: set[int] = set()
    for bin_idx, cal_row in cal_table.iterrows():
        classification = classify_bin_reliability(cal_row["n"], cal_row["biais_ic95_low"], cal_row["biais_ic95_high"], min_n)
        if classification == FIABLE:
            reliable_idx.add(bin_idx)
        elif classification == NON_FIABLE:
            non_reliable_idx.add(bin_idx)

    reliable_matches = market_df[market_df["bin_idx"].isin(reliable_idx)]
    non_reliable_matches = market_df[market_df["bin_idx"].isin(non_reliable_idx)]
    n_fiable, n_non_fiable = len(reliable_matches), len(non_reliable_matches)
    if n_fiable < 2 or n_non_fiable < 2:
        return {
            "n_fiable": n_fiable, "n_non_fiable": n_non_fiable, "boot": None,
            "verdict": f"{VERDICT_ABSENCE_PREUVE} (donnees insuffisantes)",
        }

    gap_abs_reliable = (reliable_matches["p_model"] - reliable_matches["p_market_normalized"]).abs().to_numpy()
    gap_abs_non_reliable = (non_reliable_matches["p_model"] - non_reliable_matches["p_market_normalized"]).abs().to_numpy()
    boot = two_sample_bootstrap_test(gap_abs_reliable, gap_abs_non_reliable, n_resamples=_N_RESAMPLES, seed=_SEED)
    return {"n_fiable": n_fiable, "n_non_fiable": n_non_fiable, "boot": boot, "verdict": classify_hypothesis_verdict(boot)}


def _print_joint_table(table: pd.DataFrame) -> None:
    for _, r in table.iterrows():
        typer.echo(
            f"    [{r['bin_lo']:.1f}-{r['bin_hi']:.1f}) n={r['n']:<4} n_marche={r['n_marche']:<4} "
            f"p_model={r['p_model_moyen']:.4f} freq_obs={r['freq_observee']:.4f} "
            f"biais={r['biais']:+.4f} IC95%=[{r['biais_ic95_low']:+.4f},{r['biais_ic95_high']:+.4f}] "
            f"[{r['classification_fiabilite']}] | p_marche_brute={r['p_market_brute_moyenne']:.4f} "
            f"p_marche_norm={r['p_market_normalisee_moyenne']:.4f} gap_moy={r['gap_moyen']:+.4f} "
            f"|gap|_moy={r['gap_abs_moyen']:.4f} cote_juste_modele={r['fair_odds_model_moyenne']:.3f} "
            f"cote_b365={r['b365_odds_moyenne']:.3f}"
        )


@app.command()
def main() -> None:
    typer.echo("=== E12 : intersection fiabilite / ecart de prix (Over 2.5 prioritaire) ===")
    typer.echo(
        "poisson_simple, dixon_coles et xg_model INCHANGES. Aucune nouvelle calibration, aucun "
        "tuning, aucune strategie de pari. Objectif : mesurer si les tranches fiables coincident "
        "avec les tranches a fort ecart de prix - jamais battre le marche.\n"
    )
    typer.echo(
        "LIMITATION DOCUMENTEE : B365 est le seul bookmaker Over/Under, et Football-Data ne "
        "publie que la ligne 2.5 - l'intersection fiabilite/ecart de prix n'est testable QUE sur "
        "Over 2.5. Les autres seuils (0.5/1.5/3.5/4.5) ne recoivent qu'un diagnostic de fiabilite "
        "seul, deja documente en detail en E11.\n"
    )

    e11 = _load_e11()
    e9 = e11._load_e9()
    e8 = e9._load_e8()
    e7 = e8._load_e7()
    records = e9.load_all_multi_bookmaker_records()
    records_by_id = {r.match_id: r for r in records}
    typer.echo(f"Corpus multi-bookmaker exploitable (E9) : {len(records)} matchs\n")

    for model in _MODELS:
        typer.echo(f"##### {model} #####")
        df = e11.build_threshold_dataframe(e8, e7, model)
        p, y = df["p_over_2.5"].to_numpy(), df["outcome_over_2.5"].to_numpy()
        cal_table = e11.calibration_table(p, y)
        market_df = e11.build_market_comparison_dataframe(df, records_by_id)

        typer.echo("--- Table jointe : fiabilite (H1) x ecart de prix B365 (Over 2.5) ---")
        joint = joint_bin_table(cal_table, market_df)
        _print_joint_table(joint)

        typer.echo("--- Test central (point 5) : tranches fiables vs non fiables, |gap| ---")
        result = test_reliable_bins_have_larger_gaps(cal_table, market_df)
        if result["boot"] is None:
            typer.echo(f"    n_fiable={result['n_fiable']} n_non_fiable={result['n_non_fiable']} -> {result['verdict']}")
        else:
            b = result["boot"]
            typer.echo(
                f"    n_fiable={result['n_fiable']} n_non_fiable={result['n_non_fiable']} "
                f"diff_|gap|(fiable-non_fiable) IC95%=[{b['ci_low']:+.4f},{b['ci_high']:+.4f}] p={b['p_value']:.4f}"
            )
            typer.echo(f"    -> VERDICT : {result['verdict']}")
        typer.echo("")

    typer.echo("--- Diagnostic de fiabilite seul sur les autres seuils (AUCUNE donnee de marche disponible) ---")
    for model in _MODELS:
        typer.echo(f"  {model} :")
        df = e11.build_threshold_dataframe(e8, e7, model)
        for t in _OTHER_THRESHOLDS:
            p, y = df[f"p_over_{t}"].to_numpy(), df[f"outcome_over_{t}"].to_numpy()
            cal_table = e11.calibration_table(p, y)
            n_fiable = int((cal_table.apply(lambda r: classify_bin_reliability(r["n"], r["biais_ic95_low"], r["biais_ic95_high"]), axis=1) == FIABLE).sum())
            n_non_fiable = int((cal_table.apply(lambda r: classify_bin_reliability(r["n"], r["biais_ic95_low"], r["biais_ic95_high"]), axis=1) == NON_FIABLE).sum())
            typer.echo(f"    Over {t} : {n_fiable} tranche(s) fiable(s), {n_non_fiable} tranche(s) non fiable(s) - aucune comparaison au marche possible.")
    typer.echo("  (detail complet de la calibration par tranche pour ces seuils : voir docs/research_framework.md section V, E11)\n")

    typer.echo(
        "RESERVE : aucune conclusion de rentabilite. 'fiable', 'desaccord', 'anomalie de prix' et "
        "'value potentielle' ne sont JAMAIS confondus - E12 ne mesure ni anomalie de prix (reservee "
        "a E9, plusieurs bookmakers) ni value potentielle (jamais evaluee ici). Aucun ROI, Kelly, "
        "staking, seuil optimise sur le resultat. poisson_simple, dixon_coles et xg_model restent "
        "inchanges."
    )
    typer.echo("\nARRET : E12 termine, conformement au protocole. Aucune experience E13 lancee automatiquement.")


if __name__ == "__main__":
    app()
