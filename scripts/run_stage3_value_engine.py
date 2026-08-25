"""CLI : validation d'architecture du Market/Value Engine (etape 3) sur
donnees synthetiques.

AVERTISSEMENT (a lire avant d'interpreter la moindre sortie de ce
script) : les resultats produits ici demontrent uniquement que la
MECANIQUE de calcul (edge, EV, CLV, retrait de marge) fonctionne
correctement de bout en bout, dans le respect strict du point-in-time.
ILS NE CONSTITUENT EN AUCUN CAS UNE PREUVE D'EDGE REEL SUR UN MARCHE
REEL : le "marche" synthetique de l'etape 2 est construit a partir des
memes probabilites que le modele est cense retrouver, avec un bruit et
une marge controles - toute "value" detectee ici est structurelle au
generateur, pas une decouverte sur un marche financier reel.

Usage:
    python scripts/run_stage3_value_engine.py --config configs/stage2_walk_forward.yaml
    python scripts/run_stage3_value_engine.py --config configs/stage2_walk_forward_drift.yaml
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.backtesting_engine.walk_forward import ModelConfig, run_walk_forward  # noqa: E402
from sys_foot_quant.common.config import load_config  # noqa: E402
from sys_foot_quant.common.logging import get_logger  # noqa: E402
from sys_foot_quant.data_engine.storage.repository import DuckDBRepository  # noqa: E402
from sys_foot_quant.data_engine.storage.writer import write_dataset  # noqa: E402
from sys_foot_quant.data_engine.synthetic.generator import generate_synthetic_dataset  # noqa: E402
from sys_foot_quant.football_model.naive import NaiveModel  # noqa: E402
from sys_foot_quant.football_model.poisson import PoissonModel  # noqa: E402
from sys_foot_quant.market_engine.shin import compare_overround_methods  # noqa: E402
from sys_foot_quant.market_engine.snapshot import latest_odds_as_of  # noqa: E402
from sys_foot_quant.value_engine.pipeline import build_value_log  # noqa: E402
from sys_foot_quant.value_engine.storage import write_value_log  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_BURN_IN_FRACTION = 0.4
# Seuils illustratifs, NON optimises sur ces donnees - voir
# value_engine/selection.py : le choix d'un seuil est une decision
# methodologique a part entiere, ici simplement pre-enregistree pour
# demontrer le mecanisme, jamais validee statistiquement.
_MIN_EDGE = 0.02
_MIN_EV = 0.02


@app.command()
def main(
    config: Path = typer.Option(Path("configs/stage2_walk_forward.yaml")),
    data_dir: Path = typer.Option(Path("data/raw_stage3")),
    value_log_path: Path = typer.Option(Path("data/value_logs/stage3_value_log.parquet")),
) -> None:
    typer.echo(
        "=== AVERTISSEMENT : donnees 100% synthetiques. Aucun resultat "
        "ci-dessous ne constitue une preuve d'edge reel. ===\n"
    )

    cfg = load_config(config)
    dataset = generate_synthetic_dataset(cfg.synthetic_data)
    write_dataset(dataset, data_dir)
    logger.info(
        f"Dataset genere ({config.name}) : {len(dataset.matches)} matchs, "
        f"{cfg.synthetic_data.n_teams} equipes."
    )

    with DuckDBRepository(data_dir) as repo:
        all_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
        n_total = len(all_matches)
        n_burn_in = int(n_total * _BURN_IN_FRACTION)
        eval_ids = all_matches["match_id"].iloc[n_burn_in:].tolist()
        kickoff_by_id = dict(zip(all_matches["match_id"], all_matches["kickoff_time"]))

        model_configs = [
            ModelConfig(name="naive", fit=lambda df, t: NaiveModel().fit(df)),
            ModelConfig(
                name="poisson_simple",
                fit=lambda df, t: PoissonModel(use_team_hfa=False).fit(df),
            ),
        ]
        evaluations = run_walk_forward(
            repository=repo,
            eval_match_ids=eval_ids,
            decision_offset_hours=cfg.decision_offset_hours_before_kickoff,
            model_configs=model_configs,
            include_market_benchmark=True,
        )

        # --- Comparaison des methodes de retrait de marge (proportionnel vs Shin) ---
        typer.echo("=== Comparaison retrait de marge : proportionnel vs Shin ===")
        z_values = []
        max_diffs = []
        holds = []
        n_skipped_shin_domain = 0
        for ev in evaluations:
            odds = latest_odds_as_of(repo, ev.match_id, ev.decision_time)
            if odds is None:
                continue
            try:
                comp = compare_overround_methods(odds)
            except ValueError:
                # Cotes arrondies a 3 decimales : l'arrondi peut, tres
                # rarement, faire passer la marge apparente legerement
                # sous 1 (ou au-dela du domaine numerique retenu pour
                # Shin) - cas attendu et documente, pas une erreur de
                # calcul. On l'exclut de la comparaison plutot que de
                # relacher la validation de shin.py.
                n_skipped_shin_domain += 1
                continue
            z_values.append(comp["shin_z"])
            max_diffs.append(comp["max_abs_diff"])
            holds.append(comp["hold"])
        typer.echo(f"n marches compares       = {len(z_values)} (exclus : {n_skipped_shin_domain})")
        typer.echo(f"hold moyen               = {np.mean(holds):.4f}")
        typer.echo(f"z (Shin) moyen           = {np.mean(z_values):.5f}")
        typer.echo(f"z (Shin) max             = {np.max(z_values):.5f}")
        typer.echo(f"ecart max proportionnel/Shin (moyen)   = {np.mean(max_diffs):.5f}")
        typer.echo(f"ecart max proportionnel/Shin (maximum) = {np.max(max_diffs):.5f}")

        # --- Journal de value candidates + CLV ---
        typer.echo(
            f"\n=== Value log (poisson_simple, seuils illustratifs "
            f"min_edge={_MIN_EDGE}, min_ev={_MIN_EV}) ==="
        )
        log = build_value_log(
            repo, evaluations, "poisson_simple", kickoff_by_id, min_edge=_MIN_EDGE, min_ev=_MIN_EV
        )

    write_value_log(log, value_log_path)
    typer.echo(f"n lignes (match x selection) = {len(log)}")
    typer.echo(f"edge moyen / median          = {log['edge'].mean():+.4f} / {log['edge'].median():+.4f}")
    typer.echo(f"EV moyenne / mediane         = {log['ev'].mean():+.4f} / {log['ev'].median():+.4f}")
    typer.echo(
        "  (moyenne sensible aux valeurs extremes sur marches tres "
        "desequilibres - la mediane est le resume le plus fiable ici)"
    )
    n_passing = int(log["passes_thresholds"].sum())
    typer.echo(
        f"candidats passant les seuils = {n_passing} / {len(log)} "
        f"({100*n_passing/len(log):.1f}%)"
    )

    clv_all = log["clv_pct"].dropna()
    typer.echo(
        f"CLV moyen / median (toutes lignes) = {clv_all.mean():+.3f}% / "
        f"{clv_all.median():+.3f}% (n={len(clv_all)})"
    )

    if n_passing > 0:
        clv_passing = log.loc[log["passes_thresholds"], "clv_pct"].dropna()
        if len(clv_passing) > 0:
            typer.echo(
                f"CLV moyen / median (candidats passant les seuils) = "
                f"{clv_passing.mean():+.3f}% / {clv_passing.median():+.3f}% (n={len(clv_passing)})"
            )
            ev_passing = log.loc[log["passes_thresholds"] & log["clv_pct"].notna(), ["ev", "clv_pct"]]
            if len(ev_passing) > 5:
                corr = ev_passing["ev"].corr(ev_passing["clv_pct"])
                typer.echo(
                    f"Correlation EV / CLV parmi les candidats passant les seuils = {corr:+.3f} "
                    "(proche de 0 ou negative = l'EV du modele ne predit pas la qualite reelle du prix)"
                )
            win_rate = log.loc[log["passes_thresholds"], "selection_won"].mean()
            typer.echo(f"Taux de reussite (candidats passant les seuils) = {win_rate:.1%}")

    typer.echo(
        "\n=== RAPPEL : ce qui precede valide la mecanique du pipeline sur "
        "donnees synthetiques - ce n'est ni une preuve, ni une estimation, "
        "d'un edge exploitable sur un marche reel. ==="
    )


if __name__ == "__main__":
    app()
