"""CLI : E3 - validation hors echantillon de la fiabilite des
probabilites Over/Under CALIBREES (poisson_simple/xg_model, INCHANGES).

Question unique : quand le systeme annonce une probabilite calibree
d'Over, cette probabilite correspond-elle reellement a la frequence
observee sur des matchs futurs, hors echantillon ?

Ce script ne recalcule RIEN de nouveau au niveau statistique : il
REUTILISE EXACTEMENT le pipeline deja teste d'E2
(`run_stage10_over_under_recalibration.build_calibration_and_test_sets`
et `.evaluate_recalibration`, importes tels quels, memes contraintes
point-in-time, meme decoupage 40/30/30, meme courbe isotonique ajustee
uniquement sur la calibration, meme bootstrap appari sur
diff=Brier_apres-Brier_avant) - ce n'est qu'une couche de RAPPORT plus
complete sur les memes resultats deja produits et deja verifies (aucune
fuite : voir tests/leakage/test_over_under_recalibration_point_in_time.py).

Deux ajouts, strictement des mises en forme de donnees DEJA calculees,
pas de nouvelles metriques :
1. Table de calibration COMPLETE (10 tranches fixes, y compris les
   tranches peu peuplees/vides, jamais deplacees ni fusionnees) au lieu
   du seul sous-ensemble "peuple" affiche par E2.
2. Lecture pratique agregee sur les zones 50-60% / 60-70% / 70-80% / 80%+
   (fusion ponderee des tranches [0.8-0.9] et [0.9-1.0] uniquement,
   demandee explicitement) des probabilites CALIBREES (apres
   recalibration) - une simple moyenne ponderee des grandeurs deja
   produites par ``reliability_bins``, pas une nouvelle formule.

Aucune comparaison au bookmaker, aucun ROI, aucune selection de pari,
aucun seuil de cote, aucune optimisation - purement une lecture de
fiabilite probabiliste face au resultat reel.

Usage:
    python scripts/run_stage11_e3_reliability_validation.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.common.logging import get_logger  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_MODELS = ("poisson_simple", "xg_model")
_OU_THRESHOLDS = (1.5, 2.5, 3.5)  # Over 2.5 = priorite, mais les 3 sont rapportes

_STAGE10_PATH = Path(__file__).resolve().parent / "run_stage10_over_under_recalibration.py"


def _load_stage10():
    spec = importlib.util.spec_from_file_location("run_stage10_over_under_recalibration", _STAGE10_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def merge_bins_80_plus(bins_df: pd.DataFrame) -> dict:
    """Fusionne les tranches [0.8-0.9] et [0.9-1.0] de ``reliability_bins``
    en une seule categorie "80%+", moyenne ponderee par effectif des
    memes grandeurs deja calculees - aucune nouvelle formule."""
    sub = bins_df[(bins_df["bin_lo"] >= 0.8) & (bins_df["count"] > 0)]
    count = int(sub["count"].sum())
    if count == 0:
        return {"count": 0, "mean_predicted": float("nan"), "observed_frequency": float("nan")}
    mean_predicted = float((sub["mean_predicted"] * sub["count"]).sum() / count)
    observed_frequency = float((sub["observed_frequency"] * sub["count"]).sum() / count)
    return {"count": count, "mean_predicted": mean_predicted, "observed_frequency": observed_frequency}


def practical_zone_readout(bins_df: pd.DataFrame) -> list[dict]:
    """Zones d'interet explicitement demandees (partie 4) : 50-60%,
    60-70%, 70-80% (tranches directement issues de ``reliability_bins``,
    inchangees) et 80%+ (fusion, voir ``merge_bins_80_plus``)."""
    rows = []
    for lo, label in ((0.5, "50-60%"), (0.6, "60-70%"), (0.7, "70-80%")):
        # np.isclose plutot que "==" : les bornes de tranche de
        # reliability_bins viennent de np.linspace, dont la representation
        # flottante peut differer d'un ULP du litteral Python (ex. 0.6).
        row = bins_df[np.isclose(bins_df["bin_lo"], lo)].iloc[0]
        rows.append(
            {
                "zone": label,
                "count": int(row["count"]),
                "mean_predicted": float(row["mean_predicted"]) if row["count"] > 0 else float("nan"),
                "observed_frequency": float(row["observed_frequency"]) if row["count"] > 0 else float("nan"),
            }
        )
    merged = merge_bins_80_plus(bins_df)
    rows.append({"zone": "80%+", **merged})
    return rows


def _print_full_bin_table(bins_df: pd.DataFrame, label: str) -> None:
    typer.echo(f"  Table complete ({label}) - 10 tranches fixes, aucune fusion/deplacement :")
    for _, row in bins_df.iterrows():
        if row["count"] == 0:
            typer.echo(f"    [{row['bin_lo']:.1f}-{row['bin_hi']:.1f}] n=0 (tranche vide)")
            continue
        biais = row["observed_frequency"] - row["mean_predicted"]  # frequence reelle - probabilite predite
        typer.echo(
            f"    [{row['bin_lo']:.1f}-{row['bin_hi']:.1f}] n={int(row['count']):<5} "
            f"predit_moy={row['mean_predicted']:.3f} observe={row['observed_frequency']:.3f} "
            f"biais={biais:+.3f}"
        )


def _print_zone_readout(rows: list[dict]) -> None:
    typer.echo("  Lecture pratique (probabilites CALIBREES) :")
    for r in rows:
        if r["count"] == 0:
            typer.echo(f"    {r['zone']:<8} n=0 (aucun match dans cette zone)")
            continue
        typer.echo(
            f"    {r['zone']:<8} n={r['count']:<5} annonce_moy={r['mean_predicted']:.3f} "
            f"({r['mean_predicted']*100:.1f}%) -> observe={r['observed_frequency']:.3f} "
            f"({r['observed_frequency']*100:.1f}%)"
        )


@app.command()
def main() -> None:
    typer.echo("=== E3 : fiabilite hors echantillon des probabilites Over/Under CALIBREES ===")
    typer.echo(
        "poisson_simple et xg_model INCHANGES. Reutilise EXACTEMENT le pipeline E2 (meme "
        "decoupage 40/30/30, meme courbe isotonique, meme bootstrap) - aucun recalcul different, "
        "uniquement un rapport de fiabilite plus complet.\n"
    )

    stage10 = _load_stage10()
    stage8 = stage10._load_stage8()
    calibration_df, test_df = stage10.build_calibration_and_test_sets(stage8)
    typer.echo(f"n_calibration={len(calibration_df)}  n_test={len(test_df)}\n")

    for model in _MODELS:
        typer.echo(f"##### {model} #####")
        for t in _OU_THRESHOLDS:
            res = stage10.evaluate_recalibration(calibration_df, test_df, model, t)
            if res is None:
                typer.echo(f"  Over {t} : donnees insuffisantes.")
                continue

            priorite = " (PRIORITE)" if t == 2.5 else ""
            typer.echo(f"--- Over {t}{priorite} (n_test={res['n']}) ---")

            typer.echo("\n  [Section 3] Reliability bins - avant recalibration :")
            _print_full_bin_table(res["reliability_bins_before"], "avant")
            typer.echo("\n  [Section 3] Reliability bins - apres recalibration (calibree) :")
            _print_full_bin_table(res["reliability_bins_after"], "apres")

            typer.echo("\n  [Section 4] Verification de l'idee centrale (probabilites CALIBREES) :")
            zone_rows = practical_zone_readout(res["reliability_bins_after"])
            _print_zone_readout(zone_rows)

            db, da = res["decomposition_before"], res["decomposition_after"]
            typer.echo("\n  [Section 5] Metriques globales (deja definies en E2, aucune nouvelle) :")
            typer.echo(f"    Brier avant={res['brier_before']:.4f}  apres={res['brier_after']:.4f}")
            typer.echo(f"    log loss avant={res['log_loss_before']:.4f}  apres={res['log_loss_after']:.4f}")
            typer.echo(
                f"    biais moyen absolu avant={abs(res['biais_before']):.4f}  "
                f"apres={abs(res['biais_after']):.4f}"
            )
            typer.echo(f"    resolution avant={db['resolution']:.4f}  apres={da['resolution']:.4f}")

            boot = res["bootstrap"]
            verdict = stage10.classify_verdict(boot["ci_low"], boot["ci_high"])
            typer.echo("\n  [Section 6] Incertitude - IC95% bootstrap apparie (diff=Brier_apres-Brier_avant) :")
            typer.echo(
                f"    diff_moy={boot['mean_diff']:+.5f} IC95%=[{boot['ci_low']:+.5f}, {boot['ci_high']:+.5f}] "
                f"p={boot['p_value']:.4f} -> {verdict}"
            )
            typer.echo("")

    typer.echo(
        "RESERVE : aucune comparaison au bookmaker, aucun ROI, aucune selection de pari, aucun "
        "seuil de cote, aucune optimisation. poisson_simple et xg_model restent inchanges - "
        "cette analyse valide uniquement la fiabilite probabiliste de la couche de recalibration "
        "deja testee en E2, sur le MEME segment de test, jamais reutilise pour ajuster quoi que "
        "ce soit."
    )
    typer.echo("\nARRET : rapport termine, conformement au protocole.")


if __name__ == "__main__":
    app()
