"""CLI : EXPERIENCE de recalibration isotonique des probabilites
Over/Under DEJA PRODUITES par `poisson_simple` et `xg_model` (aucun
modele predictif modifie, une seule methode testee, walk-forward strict
rodage/calibration/test).

Question unique testee : une recalibration isotonique, apprise
UNIQUEMENT sur le passe (segment calibration), ameliore-t-elle les
probabilites Over/Under sur des matchs FUTURS, hors echantillon (segment
test), sans fuite ?

PROTOCOLE (fige avant execution, aucune variante) :
1. `poisson_simple` et `xg_model` restent INCHANGES - ce script ne lit
   que leurs probabilites deja produites par
   `run_stage8_diagnostic_total_goals_over_under.build_total_goals_dataframe()`
   (import direct, aucun recalcul different, memes contraintes
   point-in-time).
2. Inspection prealable des mecanismes de calibration deja presents
   (documentee dans `calibration_engine/isotonic_calibration.py`) :
   `calibration_engine.reliability.reliability_bins` et
   `calibration_engine.decomposition.brier_decomposition` REUTILISES SANS
   MODIFICATION ; `football_model.elo.EloModel` (calibration empirique
   par tranches) etudie mais non reutilise (assimilable a un nouveau
   modele s'il etait applique ici).
3. UNE SEULE methode de recalibration : regression isotonique
   (`scipy.optimize.isotonic_regression`, PAVA, deja une dependance du
   projet) - choisie et justifiee AVANT implementation (voir docstring de
   `isotonic_calibration.py`) car monotone par construction (ne peut pas
   degrader la resolution), sans forme parametrique supposee (le
   diagnostic prealable a documente un biais en "S", pas une sigmoide),
   et sans hyperparametre a ajuster. Aucune variante, aucune comparaison
   a d'autres methodes, aucune selection fondee sur le resultat.
4. Walk-forward strict, MEME DECOUPAGE que B1/A2/B2/B3.3 : 40% rodage
   (jete), 30% calibration (sert UNIQUEMENT a ajuster la courbe
   isotonique), 30% test (sert UNIQUEMENT a evaluer, jamais vu par la
   courbe). Meme corpus : 3 championnats x 2 saisons.
5. Une courbe de calibration SEPAREE par (modele, seuil) - Over 1.5, 2.5,
   3.5 - jamais une courbe partagee entre seuils.
6. Evaluation sur le TEST uniquement : Brier avant/apres, log loss
   avant/apres, table de calibration complete (reliability bins)
   avant/apres, decomposition de Brier (resolution/fiabilite) avant/apres,
   biais moyen avant/apres, et IC95% bootstrap apparie
   (`paired_bootstrap_test`, REUTILISE SANS MODIFICATION) sur
   diff = Brier_apres - Brier_avant, par match.
7. Verdict PAR (modele, seuil), formulation imposee :
   - IC95% entierement < 0 -> AMELIORATION STATISTIQUEMENT DEMONTREE
   - IC95% contenant 0     -> ABSENCE DE PREUVE D'AMELIORATION
   - IC95% entierement > 0 -> RECALIBRATION SIGNIFICATIVEMENT MOINS BONNE
   Aucun critere agrege au-dela de ces six verdicts individuels.

Usage:
    python scripts/run_stage10_over_under_recalibration.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.calibration_engine.decomposition import brier_decomposition  # noqa: E402
from sys_foot_quant.calibration_engine.isotonic_calibration import fit_isotonic_calibration  # noqa: E402
from sys_foot_quant.calibration_engine.reliability import reliability_bins  # noqa: E402
from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test  # noqa: E402
from sys_foot_quant.common.logging import get_logger  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_MODELS = ("poisson_simple", "xg_model")
_OU_THRESHOLDS = (1.5, 2.5, 3.5)
_N_BINS = 10
_N_RESAMPLES = 10_000
_SEED = 0

# Meme convention que B1/A2/B2/B3.3 (voir scripts/run_stage5_b3_3_gate_disagreement.py)
_BURN_IN_FRACTION = 0.4
_CALIBRATION_FRACTION_OF_REMAINDER = 0.5  # -> ~40/30/30 rodage/calibration/test

_STAGE8_PATH = Path(__file__).resolve().parent / "run_stage8_diagnostic_total_goals_over_under.py"


def _load_stage8():
    spec = importlib.util.spec_from_file_location("run_stage8_diagnostic_total_goals_over_under", _STAGE8_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def split_burn_in_calibration_test(records: list) -> tuple[set[str], set[str]]:
    """Meme regle EXACTE que ``_split_eval_ids`` de
    ``run_stage5_b3_3_gate_disagreement.py`` (40% rodage jete, 30%
    calibration, 30% test, tri chronologique) - dupliquee ici (fonction
    pure, testable isolement) plutot qu'importee d'un script frere."""
    ordered = sorted(records, key=lambda r: r.kickoff_utc)
    n_total = len(ordered)
    n_burn_in = int(n_total * _BURN_IN_FRACTION)
    n_remaining = n_total - n_burn_in
    n_calibration = int(n_remaining * _CALIBRATION_FRACTION_OF_REMAINDER)
    calibration_ids = {r.match_id for r in ordered[n_burn_in : n_burn_in + n_calibration]}
    test_ids = {r.match_id for r in ordered[n_burn_in + n_calibration :]}
    return calibration_ids, test_ids


def build_calibration_and_test_sets(stage8_module) -> tuple:
    """Reconstruit, PAR CHAMPIONNAT ET PAR SAISON, le decoupage
    rodage/calibration/test a partir des memes ``RealMatchRecord`` que
    ``build_total_goals_dataframe`` (``stage8_module._load_records``,
    reutilise sans modification), puis filtre le dataframe DEJA PRODUIT
    (aucun recalcul de prediction) par appartenance des ``match_id``."""
    df = stage8_module.build_total_goals_dataframe()

    calibration_ids: set[str] = set()
    test_ids: set[str] = set()
    for season, leagues in stage8_module._SEASONS.items():
        for league in leagues:
            records = stage8_module._load_records(league, season)
            c_ids, t_ids = split_burn_in_calibration_test(records)
            calibration_ids |= c_ids
            test_ids |= t_ids

    calibration_df = df[df["match_id"].isin(calibration_ids)].reset_index(drop=True)
    test_df = df[df["match_id"].isin(test_ids)].reset_index(drop=True)
    return calibration_df, test_df


def evaluate_recalibration(calibration_df, test_df, model: str, threshold: float) -> dict | None:
    """Ajuste UNE courbe isotonique sur ``calibration_df`` uniquement,
    l'applique a ``test_df``, et calcule toutes les metriques du
    protocole SUR LE TEST UNIQUEMENT - fonction pure, testable avec des
    DataFrames synthetiques."""
    col = f"{model}_p_over_{threshold}"
    calib = calibration_df.dropna(subset=[col])
    test = test_df.dropna(subset=[col])
    if calib.empty or test.empty:
        return None

    p_calib = calib[col].to_numpy()
    y_calib = (calib["total_goals"] > threshold).astype(float).to_numpy()
    curve = fit_isotonic_calibration(p_calib, y_calib)

    p_test_before = test[col].to_numpy()
    y_test = (test["total_goals"] > threshold).astype(float).to_numpy()
    p_test_after = curve.predict(p_test_before)

    brier_before_row = (p_test_before - y_test) ** 2
    brier_after_row = (p_test_after - y_test) ** 2
    eps = 1e-12
    logloss_before_row = -(
        y_test * np.log(np.clip(p_test_before, eps, 1 - eps))
        + (1 - y_test) * np.log(np.clip(1 - p_test_before, eps, 1 - eps))
    )
    logloss_after_row = -(
        y_test * np.log(np.clip(p_test_after, eps, 1 - eps))
        + (1 - y_test) * np.log(np.clip(1 - p_test_after, eps, 1 - eps))
    )

    diffs = brier_after_row - brier_before_row
    boot = paired_bootstrap_test(diffs, n_resamples=_N_RESAMPLES, seed=_SEED)

    decomp_before = brier_decomposition(p_test_before, y_test, n_bins=_N_BINS)
    decomp_after = brier_decomposition(p_test_after, y_test, n_bins=_N_BINS)

    return {
        "n": len(test),
        "brier_before": float(brier_before_row.mean()),
        "brier_after": float(brier_after_row.mean()),
        "log_loss_before": float(logloss_before_row.mean()),
        "log_loss_after": float(logloss_after_row.mean()),
        "biais_before": float((p_test_before - y_test).mean()),
        "biais_after": float((p_test_after - y_test).mean()),
        "reliability_bins_before": reliability_bins(p_test_before, y_test, n_bins=_N_BINS),
        "reliability_bins_after": reliability_bins(p_test_after, y_test, n_bins=_N_BINS),
        "decomposition_before": decomp_before,
        "decomposition_after": decomp_after,
        "bootstrap": boot,
        "n_calibration": len(calib),
    }


def classify_verdict(ci_low: float, ci_high: float) -> str:
    if ci_high < 0.0:
        return "AMELIORATION STATISTIQUEMENT DEMONTREE"
    if ci_low > 0.0:
        return "RECALIBRATION SIGNIFICATIVEMENT MOINS BONNE"
    return "ABSENCE DE PREUVE D'AMELIORATION"


@app.command()
def main() -> None:
    typer.echo("=== EXPERIENCE : recalibration isotonique des probabilites Over/Under ===")
    typer.echo(
        "poisson_simple et xg_model INCHANGES. Une seule methode (regression isotonique, PAVA), "
        "aucun hyperparametre, walk-forward strict 40/30/30 (rodage/calibration/test).\n"
    )

    stage8 = _load_stage8()
    calibration_df, test_df = build_calibration_and_test_sets(stage8)
    typer.echo(f"n_calibration (pooled, 3 championnats x 2 saisons) : {len(calibration_df)}")
    typer.echo(f"n_test (pooled, 3 championnats x 2 saisons)        : {len(test_df)}\n")

    results = {}
    for model in _MODELS:
        typer.echo(f"##### {model} #####")
        for t in _OU_THRESHOLDS:
            res = evaluate_recalibration(calibration_df, test_df, model, t)
            if res is None:
                typer.echo(f"  Over {t} : donnees insuffisantes.")
                continue
            boot = res["bootstrap"]
            verdict = classify_verdict(boot["ci_low"], boot["ci_high"])
            results[(model, t)] = (res, verdict)

            typer.echo(f"--- Over {t} (n_calibration={res['n_calibration']}, n_test={res['n']}) ---")
            typer.echo(
                f"  Brier     avant={res['brier_before']:.4f}  apres={res['brier_after']:.4f}  "
                f"diff={res['brier_after'] - res['brier_before']:+.4f}"
            )
            typer.echo(
                f"  log loss  avant={res['log_loss_before']:.4f}  apres={res['log_loss_after']:.4f}"
            )
            typer.echo(
                f"  biais moyen avant={res['biais_before']:+.4f}  apres={res['biais_after']:+.4f}"
            )
            db, da = res["decomposition_before"], res["decomposition_after"]
            typer.echo(
                f"  fiabilite   avant={db['reliability']:.4f}  apres={da['reliability']:.4f}"
            )
            typer.echo(
                f"  resolution  avant={db['resolution']:.4f}  apres={da['resolution']:.4f}"
            )
            typer.echo(
                f"  IC95% bootstrap (diff=Brier_apres-Brier_avant) : "
                f"diff_moy={boot['mean_diff']:+.5f} IC95%=[{boot['ci_low']:+.5f}, {boot['ci_high']:+.5f}] "
                f"p={boot['p_value']:.4f}"
            )
            typer.echo(f"  -> {verdict}")

            typer.echo("  Table de calibration AVANT (tranches peuplees uniquement) :")
            bins_b = res["reliability_bins_before"]
            for _, row in bins_b[bins_b["count"] > 0].iterrows():
                typer.echo(
                    f"    [{row['bin_lo']:.1f}-{row['bin_hi']:.1f}] n={int(row['count']):<5} "
                    f"predit={row['mean_predicted']:.3f} observe={row['observed_frequency']:.3f}"
                )
            typer.echo("  Table de calibration APRES (tranches peuplees uniquement) :")
            bins_a = res["reliability_bins_after"]
            for _, row in bins_a[bins_a["count"] > 0].iterrows():
                typer.echo(
                    f"    [{row['bin_lo']:.1f}-{row['bin_hi']:.1f}] n={int(row['count']):<5} "
                    f"predit={row['mean_predicted']:.3f} observe={row['observed_frequency']:.3f}"
                )
            typer.echo("")

    typer.echo("=== VERDICTS (formulation imposee, aucun critere agrege au-dela de ceux-ci) ===")
    for (model, t), (res, verdict) in results.items():
        typer.echo(f"  {model:<16} Over {t:<4} -> {verdict}")

    typer.echo(
        "\nRESERVE : la courbe isotonique est ajustee sur la CALIBRATION et evaluee sur le TEST, "
        "jamais l'inverse - aucune fuite. Une seule methode testee, aucune recherche "
        "d'hyperparametre, aucune comparaison a d'autres methodes. Aucune conclusion de "
        "rentabilite - poisson_simple et xg_model restent inchanges."
    )
    typer.echo("\nARRET : experience terminee, conformement au protocole.")


if __name__ == "__main__":
    app()
