"""CLI : DIAGNOSTIC de calibration des probabilites Over/Under DEJA
PRODUITES par ``poisson_simple`` et ``xg_model`` (aucun nouveau modele
predictif, aucune modification de modele, aucune nouvelle donnee, aucune
comparaison au marche, aucune optimisation de seuil).

Contexte : le diagnostic precedent
(``run_stage8_diagnostic_total_goals_over_under.py``) a mesure une erreur
de calibration ponderee globale par seuil Over/Under, sur poisson_simple,
dixon_coles et xg_model. Ce script va plus loin, UNIQUEMENT sur
poisson_simple et xg_model (comme demande), sur les seuils 1.5/2.5/3.5 :

1. **Inspection prealable des outils de calibration deja presents**
   (documentee ci-dessous, PAS un nouveau developpement avant d'avoir
   verifie l'existant) :
   - ``calibration_engine.reliability.reliability_bins`` : deja utilisee
     par le stage8 pour un resume pondere unique ; REUTILISEE ICI SANS
     MODIFICATION pour produire la table COMPLETE par tranche (le
     "biais par tranche de probabilite" demande).
   - ``football_model.elo.EloModel`` contient deja une forme de
     "calibration isotonique par tranches" (bins empiriques appliques en
     lookup) - PRECEDENT ETUDIE mais PAS reutilise ici : l'appliquer
     reviendrait a CONSTRUIRE un nouveau modele recalibre, explicitement
     exclu par la consigne. Ce diagnostic reste purement analytique.
   - Aucune decomposition de Brier (fiabilite/resolution/incertitude) et
     aucune metrique de discrimination (AUC, monotonicite) n'existaient
     dans le depot - AJOUTEES ici comme outils de MESURE purs
     (``calibration_engine/decomposition.py``, meme statut que
     ``goodness_of_fit.py``/``low_score_metrics.py`` deja presents :
     analyse d'un ensemble (probabilite, resultat) deja produit, ne
     genere et ne modifie aucune prediction).
2. Reutilise **SANS RECALCUL** les probabilites Over/Under deja produites
   par ``run_stage8_diagnostic_total_goals_over_under.build_total_goals_dataframe()``
   (import direct de cette fonction, memes contraintes point-in-time,
   memes 2132 matchs, memes modeles geles).
3. Pour poisson_simple et xg_model, aux seuils 1.5/2.5/3.5 : table
   complete de calibration par tranche (10 tranches), decomposition de
   Brier (fiabilite/resolution/incertitude), taux de violation de
   monotonicite, et lecture de la STABILITE du biais par championnat et
   saison (le meme biais, dans le meme sens, partout, ou un artefact
   localise ?).
4. Discussion, PUREMENT ANALYTIQUE (aucun ajustement effectivement
   applique) : la resolution est-elle substantielle par rapport a
   l'incertitude (skill au-dela de la base rate) ? La fiabilite
   represente-t-elle une part importante du Brier total ? La relation
   tranche -> frequence observee est-elle monotone (condition necessaire
   pour qu'une recalibration monotone ne puisse, par construction
   mathematique, que preserver ou ameliorer la resolution) ?

Usage:
    python scripts/run_stage9_over_under_calibration_diagnostic.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.calibration_engine.decomposition import (  # noqa: E402
    bin_monotonicity_violations,
    brier_decomposition,
)
from sys_foot_quant.calibration_engine.reliability import reliability_bins  # noqa: E402
from sys_foot_quant.common.logging import get_logger  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_MODELS = ("poisson_simple", "xg_model")
_OU_THRESHOLDS = (1.5, 2.5, 3.5)
_N_BINS = 10

_STAGE8_PATH = Path(__file__).resolve().parent / "run_stage8_diagnostic_total_goals_over_under.py"


def _load_stage8():
    spec = importlib.util.spec_from_file_location("run_stage8_diagnostic_total_goals_over_under", _STAGE8_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def analyze_over_under(df, model: str, threshold: float, n_bins: int = _N_BINS) -> dict:
    """Rassemble, pour un (modele, seuil) donne, la table de calibration
    complete, la decomposition de Brier et le taux de violation de
    monotonicite - toutes fonctions PURES reutilisees sans modification."""
    sub = df.dropna(subset=[f"{model}_p_over_{threshold}"])
    p = sub[f"{model}_p_over_{threshold}"].to_numpy()
    y = (sub["total_goals"] > threshold).astype(float).to_numpy()

    bins = reliability_bins(p, y, n_bins=n_bins)
    bins = bins.copy()
    bins["biais"] = bins["mean_predicted"] - bins["observed_frequency"]

    decomp = brier_decomposition(p, y, n_bins=n_bins)
    mono = bin_monotonicity_violations(p, y, n_bins=n_bins)

    return {"n": len(sub), "bins": bins, "decomposition": decomp, "monotonicity": mono}


def stability_by_group(df, model: str, threshold: float, group_col: str) -> dict:
    """Biais global (moyenne predite - frequence observee) par valeur de
    ``group_col`` (championnat ou saison) - lecture de stabilite du biais,
    pas une nouvelle metrique."""
    sub = df.dropna(subset=[f"{model}_p_over_{threshold}"])
    out = {}
    for value, g in sub.groupby(group_col):
        p = g[f"{model}_p_over_{threshold}"].to_numpy()
        y = (g["total_goals"] > threshold).astype(float).to_numpy()
        out[value] = {"n": len(g), "biais": float(p.mean() - y.mean())}
    return out


@app.command()
def main() -> None:
    typer.echo("=== DIAGNOSTIC : calibration Over/Under de poisson_simple et xg_model (par tranche) ===")
    typer.echo(
        "Aucun nouveau modele predictif, aucune modification de modele, aucune donnee nouvelle, "
        "aucune comparaison au marche, aucune optimisation de seuil. Reutilise directement les "
        "probabilites deja produites par run_stage8_diagnostic_total_goals_over_under.py.\n"
    )

    stage8 = _load_stage8()
    df = stage8.build_total_goals_dataframe()
    typer.echo(f"Matchs totaux (memes contraintes point-in-time que stage8) : {len(df)}\n")

    for model in _MODELS:
        typer.echo(f"##### {model} #####")
        for t in _OU_THRESHOLDS:
            res = analyze_over_under(df, model, t)
            d = res["decomposition"]
            m = res["monotonicity"]
            typer.echo(f"--- Over {t} (n={res['n']}) ---")
            typer.echo("  Table de calibration complete (tranche de probabilite predite) :")
            for _, row in res["bins"].iterrows():
                if row["count"] == 0:
                    continue
                typer.echo(
                    f"    [{row['bin_lo']:.1f}-{row['bin_hi']:.1f}] n={int(row['count']):<5} "
                    f"predit_moy={row['mean_predicted']:.3f} observe={row['observed_frequency']:.3f} "
                    f"biais={row['biais']:+.3f}"
                )
            typer.echo(
                f"  Decomposition de Brier : fiabilite={d['reliability']:.4f} "
                f"resolution={d['resolution']:.4f} incertitude={d['uncertainty']:.4f} "
                f"(brier_groupe={d['brier_grouped']:.4f} vs brier_brut={d['brier_raw']:.4f}, "
                f"ecart_groupement={d['grouping_error']:+.5f})"
            )
            typer.echo(f"  Skill vs climatologie (resolution-fiabilite)/incertitude : {d['skill_score_vs_climatology']:+.4f}")
            typer.echo(
                f"  Monotonicite : {m['n_violations']}/{m['n_transitions']} transitions en violation "
                f"(taux={m['violation_rate']:.3f})" if m["n_transitions"] else "  Monotonicite : non evaluable (trop peu de tranches peuplees)."
            )

            typer.echo("  Stabilite du biais par championnat :")
            for league, s in stability_by_group(df, model, t, "league").items():
                typer.echo(f"    {league:<16} n={s['n']:<5} biais={s['biais']:+.4f}")
            typer.echo("  Stabilite du biais par saison :")
            for season, s in stability_by_group(df, model, t, "season").items():
                typer.echo(f"    {season:<8} n={s['n']:<5} biais={s['biais']:+.4f}")
            typer.echo("")

    typer.echo(
        "RESERVE : analyse purement diagnostique - aucune recalibration n'a ete effectivement "
        "ajustee ni appliquee (cela constituerait un nouveau modele, explicitement exclu). Les "
        "indicateurs de resolution/monotonicite renseignent uniquement sur la PLAUSIBILITE "
        "qu'une recalibration monotone future puisse reduire le biais sans degrader la "
        "discrimination - ce n'est pas une demonstration que cela fonctionnerait effectivement "
        "hors echantillon."
    )
    typer.echo(
        "\nARRET : aucun ROI, aucune comparaison aux cotes, aucune optimisation de seuil, aucune "
        "nouvelle variante. Diagnostic termine."
    )


if __name__ == "__main__":
    app()
