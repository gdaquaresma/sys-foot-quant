"""CLI : E4 - validation de la discrimination de l'esperance totale de
buts predite (poisson_simple, xg_model - INCHANGES, AUCUNE calibration
isotone utilisee ici).

Question exacte : lorsque le modele predit un total attendu de buts plus
eleve, les matchs produisent-ils effectivement davantage de buts ?
Objectif : demontrer une DISCRIMINATION reelle du niveau de buts - PAS
une calibration parfaite (une surestimation globale de l'esperance
n'annule pas cette propriete).

Variable etudiee, strictement point-in-time, AUCUNE information du
futur : ``expected_total_goals = lambda_home + lambda_away``, DEJA
calculee et exposee par
``run_stage8_diagnostic_total_goals_over_under.build_total_goals_dataframe()``
(colonnes ``{model}_lambda_plus_mu``) - reutilisee ici SANS RECALCUL.

Aucun nouveau modele, aucune modification de poisson_simple/xg_model,
aucune calibration isotone (la calibration isotone d'E2/E3 n'est PAS
utilisee ici - on etudie l'esperance BRUTE, la variable structurelle).

Protocole temporel : meme decoupage 40% rodage / 30% calibration / 30%
test que B1/A2/B2/B3.3/E2/E3, reutilise sans modification
(``run_stage10_over_under_recalibration.build_calibration_and_test_sets``)
- la partie "calibration" du decoupage n'est ici utilisee pour RIEN
(aucun ajustement necessaire pour cette analyse), seul le TEST sert a
l'evaluation finale, conformement au protocole.

Analyses (aucun seuil de cote, aucun ROI, aucune selection de pari,
aucune optimisation de bin) :
1. Tranches FIXES, definies avant toute execution : <1.5, 1.5-2.0,
   2.0-2.5, 2.5-3.0, 3.0-3.5, 3.5+ - n, moyenne predite, moyenne
   observee, biais = observe - predit.
2. Quintiles de l'esperance predite (bornes determinees UNIQUEMENT a
   partir des valeurs predites, jamais du resultat reel) - verification
   de monotonicite (prediction croissante -> realite croissante).
3. Correlation de Pearson, MAE, biais moyen - IC95% bootstrap
   (``paired_bootstrap_test``, REUTILISE SANS MODIFICATION) sur le biais
   moyen ET sur la MAE (deux applications directes du meme outil
   generique deja utilise pour "profit par pari" en E1 - aucun nouvel
   outil statistique). Aucun bootstrap n'est construit pour la
   correlation elle-meme (aucun outil generique de ce type deja present
   dans le depot - non ajoute ici, conformement a "ne pas ajouter de
   tests statistiques multiples").
4. Stabilite : globalement, par championnat, par saison - aucun
   sous-groupe choisi apres observation.
5. Lecture descriptive P(Over 2.5 observe) par tranche fixe de
   l'esperance predite - PAS une calibration, uniquement descriptif.

Usage:
    python scripts/run_stage12_e4_expected_goals_discrimination.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test  # noqa: E402
from sys_foot_quant.common.logging import get_logger  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_MODELS = ("poisson_simple", "xg_model")
_N_RESAMPLES = 10_000
_SEED = 0

# Tranches FIXEES AVANT TOUTE EXECUTION (partie 4 du protocole) - jamais
# modifiees apres observation des resultats.
_FIXED_BIN_EDGES = [-np.inf, 1.5, 2.0, 2.5, 3.0, 3.5, np.inf]
_FIXED_BIN_LABELS = ["<1.5", "1.5-2.0", "2.0-2.5", "2.5-3.0", "3.0-3.5", "3.5+"]
_N_QUINTILES = 5

_STAGE10_PATH = Path(__file__).resolve().parent / "run_stage10_over_under_recalibration.py"


def _load_stage10():
    spec = importlib.util.spec_from_file_location("run_stage10_over_under_recalibration", _STAGE10_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def fixed_bin_table(expected: np.ndarray, actual: np.ndarray) -> pd.DataFrame:
    """Tranches fixes (partie 4) - n, moyenne predite, moyenne observee,
    biais = observe - predit. Tranches peu peuplees CONSERVEES (jamais
    fusionnees ni deplacees)."""
    cats = pd.cut(expected, bins=_FIXED_BIN_EDGES, labels=_FIXED_BIN_LABELS, right=False)
    rows = []
    for label in _FIXED_BIN_LABELS:
        mask = cats == label
        n = int(mask.sum())
        if n == 0:
            rows.append({"tranche": label, "n": 0, "predit_moy": float("nan"), "observe_moy": float("nan"), "biais": float("nan")})
            continue
        predit_moy = float(expected[mask].mean())
        observe_moy = float(actual[mask].mean())
        rows.append({"tranche": label, "n": n, "predit_moy": predit_moy, "observe_moy": observe_moy, "biais": observe_moy - predit_moy})
    return pd.DataFrame(rows)


def quintile_table(expected: np.ndarray, actual: np.ndarray, n_quintiles: int = _N_QUINTILES) -> pd.DataFrame:
    """Quintiles de l'esperance PREDITE uniquement (partie 5) - les
    frontieres ne dependent JAMAIS du resultat reel."""
    quintile = pd.qcut(expected, n_quintiles, labels=[f"Q{i+1}" for i in range(n_quintiles)], duplicates="drop")
    rows = []
    for label in quintile.categories:
        mask = quintile == label
        n = int(mask.sum())
        rows.append(
            {
                "quintile": str(label),
                "n": n,
                "predit_moy": float(expected[mask].mean()) if n else float("nan"),
                "observe_moy": float(actual[mask].mean()) if n else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def is_monotonic_non_decreasing(values: np.ndarray, tol: float = 1e-9) -> bool:
    values = np.asarray(values, dtype=float)
    if len(values) < 2:
        return True
    return bool(np.all(np.diff(values) >= -tol))


def regression_diagnostics(expected: np.ndarray, actual: np.ndarray) -> dict:
    """Partie 6 : correlation, MAE, biais moyen - metriques minimales
    demandees, aucune metrique sophistiquee ajoutee. La decomposition de
    Brier (fiabilite/resolution, E2/E3) n'est PAS applicable ici : elle
    suppose une probabilite dans [0,1] et un resultat binaire, alors que
    ``expected_total_goals`` est une estimation ponctuelle continue - la
    correlation joue ici le role de mesure de discrimination pour une
    variable continue."""
    expected = np.asarray(expected, dtype=float)
    actual = np.asarray(actual, dtype=float)
    n = len(expected)
    if n < 2:
        return {"n": n, "correlation": float("nan"), "mae": float("nan"), "biais_moyen": float("nan")}
    correlation = float(np.corrcoef(expected, actual)[0, 1])
    mae = float(np.mean(np.abs(actual - expected)))
    biais_moyen = float(np.mean(actual - expected))
    return {"n": n, "correlation": correlation, "mae": mae, "biais_moyen": biais_moyen}


def bootstrap_bias_and_mae(expected: np.ndarray, actual: np.ndarray) -> dict:
    """IC95% bootstrap (``paired_bootstrap_test``, REUTILISE SANS
    MODIFICATION - meme outil qu'E1/E2/E3, applique ici a un vecteur
    d'ecarts par match, exactement son usage generique documente) sur le
    biais moyen ET sur la MAE."""
    diffs_bias = np.asarray(actual, dtype=float) - np.asarray(expected, dtype=float)
    diffs_mae = np.abs(diffs_bias)
    return {
        "biais": paired_bootstrap_test(diffs_bias, n_resamples=_N_RESAMPLES, seed=_SEED),
        "mae": paired_bootstrap_test(diffs_mae, n_resamples=_N_RESAMPLES, seed=_SEED),
    }


def over_25_rate_by_fixed_bin(expected: np.ndarray, total_goals: np.ndarray) -> pd.DataFrame:
    """Partie 9 : P(Over 2.5 observe) par tranche fixe d'esperance
    predite - purement descriptif, AUCUNE calibration de cette relation."""
    cats = pd.cut(expected, bins=_FIXED_BIN_EDGES, labels=_FIXED_BIN_LABELS, right=False)
    over = (np.asarray(total_goals, dtype=float) > 2.5).astype(float)
    rows = []
    for label in _FIXED_BIN_LABELS:
        mask = cats == label
        n = int(mask.sum())
        rows.append(
            {
                "tranche": label,
                "n": n,
                "p_over_2_5_observe": float(over[mask].mean()) if n else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def _print_scope_report(label: str, expected: np.ndarray, actual: np.ndarray, total_goals: np.ndarray) -> None:
    n = len(expected)
    typer.echo(f"  -- {label} (n={n}) --")
    if n < 2:
        typer.echo("    donnees insuffisantes.")
        return

    typer.echo("    Tranches fixes :")
    fb = fixed_bin_table(expected, actual)
    for _, row in fb.iterrows():
        if row["n"] == 0:
            typer.echo(f"      {row['tranche']:<10} n=0 (tranche vide)")
            continue
        typer.echo(
            f"      {row['tranche']:<10} n={int(row['n']):<5} predit={row['predit_moy']:.3f} "
            f"observe={row['observe_moy']:.3f} biais={row['biais']:+.3f}"
        )

    typer.echo("    Quintiles (esperance predite) :")
    qt = quintile_table(expected, actual)
    monotone = is_monotonic_non_decreasing(qt["observe_moy"].to_numpy())
    for _, row in qt.iterrows():
        typer.echo(
            f"      {row['quintile']:<4} n={int(row['n']):<5} predit={row['predit_moy']:.3f} "
            f"observe={row['observe_moy']:.3f}"
        )
    typer.echo(f"      -> relation monotone (predit croissant => observe croissant) : {monotone}")

    diag = regression_diagnostics(expected, actual)
    boot = bootstrap_bias_and_mae(expected, actual)
    typer.echo(
        f"    correlation={diag['correlation']:+.4f}  MAE={diag['mae']:.4f} "
        f"IC95%=[{boot['mae']['ci_low']:.4f}, {boot['mae']['ci_high']:.4f}]  "
        f"biais_moyen={diag['biais_moyen']:+.4f} "
        f"IC95%=[{boot['biais']['ci_low']:+.4f}, {boot['biais']['ci_high']:+.4f}]"
    )

    typer.echo("    P(Over 2.5 observe) par tranche fixe d'esperance predite (descriptif) :")
    ov = over_25_rate_by_fixed_bin(expected, total_goals)
    for _, row in ov.iterrows():
        if row["n"] == 0:
            typer.echo(f"      {row['tranche']:<10} n=0")
            continue
        typer.echo(f"      {row['tranche']:<10} n={int(row['n']):<5} P(Over2.5)={row['p_over_2_5_observe']:.3f}")


@app.command()
def main() -> None:
    typer.echo("=== E4 : discrimination de l'esperance totale de buts (E[total buts] = lambda_home+lambda_away) ===")
    typer.echo(
        "poisson_simple et xg_model INCHANGES. Aucune calibration isotone utilisee ici (variable "
        "brute). Question : prediction croissante => realite croissante (discrimination), pas "
        "necessairement calibration parfaite.\n"
    )

    stage10 = _load_stage10()
    stage8 = stage10._load_stage8()
    _, test_df = stage10.build_calibration_and_test_sets(stage8)
    typer.echo(f"n_test (pooled, 3 championnats x 2 saisons) : {len(test_df)}\n")

    for model in _MODELS:
        typer.echo(f"##### {model} #####")
        col = f"{model}_lambda_plus_mu"
        sub = test_df.dropna(subset=[col])
        expected_all = sub[col].to_numpy()
        actual_all = sub["total_goals"].to_numpy()

        typer.echo("- Global -")
        _print_scope_report("GLOBAL", expected_all, actual_all, actual_all)
        typer.echo("- Par championnat -")
        for league in sorted(sub["league"].unique()):
            m = sub["league"] == league
            _print_scope_report(league, sub.loc[m, col].to_numpy(), sub.loc[m, "total_goals"].to_numpy(), sub.loc[m, "total_goals"].to_numpy())
        typer.echo("- Par saison -")
        for season in sorted(sub["season"].unique()):
            m = sub["season"] == season
            _print_scope_report(season, sub.loc[m, col].to_numpy(), sub.loc[m, "total_goals"].to_numpy(), sub.loc[m, "total_goals"].to_numpy())
        typer.echo("")

    typer.echo(
        "RESERVE : aucune cote bookmaker, aucun ROI/yield/CLV, aucune selection de pari, aucun "
        "seuil de cote, aucune optimisation de bin. poisson_simple et xg_model restent inchanges. "
        "Aucune calibration nouvelle n'a ete creee ici."
    )
    typer.echo("\nARRET : E4 termine, conformement au protocole. Aucune experience suivante lancee automatiquement.")


if __name__ == "__main__":
    app()
