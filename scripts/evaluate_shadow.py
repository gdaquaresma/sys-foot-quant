"""CLI minimal, LECTURE SEULE : evalue les observations REGLEES du journal
Shadow Mode (``research/shadow_mode/predictions.jsonl`` par defaut). Ne
modifie jamais le journal ni le moteur. N'invente JAMAIS un BET : tant
qu'aucune observation reglee n'a ``decision == "BET"`` (attendu tant que
``min_edge_threshold`` reste ``None``, voir
``docs/final_engine_user_guide.md``), la section pari le signale
explicitement plutot que de fabriquer un echantillon.

Usage:
    uv run python scripts/evaluate_shadow.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.shadow_mode.journal import DEFAULT_JOURNAL_PATH, evaluate_shadow  # noqa: E402

app = typer.Typer(add_completion=False)


def format_evaluation_report(report: dict) -> str:
    lines: list[str] = []
    lines.append(
        f"Observations : {report['n_total']} total "
        f"(PENDING={report['n_pending']}, SETTLED={report['n_settled']})"
    )
    lines.append(f"Distribution des decisions (toutes observations) : {report['decision_distribution']}")
    lines.append("")
    lines.append("--- Par modele (observations REGLEES uniquement, probabilite Over 2.5) ---")
    for model, m in report["models"].items():
        if m["n"] == 0:
            lines.append(f"  {model:<14} n=0 (aucune observation reglee avec probabilite disponible)")
            continue
        lines.append(f"  {model:<14} n={m['n']:<4} Brier={m['brier']:.4f} log_loss={m['log_loss']:.4f}")
        if m["calibration_bins"] is not None:
            lines.append(f"    calibration (n >= {report['calibration_min_observations']}) :")
            for b in m["calibration_bins"]:
                if b["count"] == 0:
                    continue
                lines.append(
                    f"      [{b['bin_lo']:.2f},{b['bin_hi']:.2f}] predit={b['mean_predicted']:.3f} "
                    f"observe={b['observed_frequency']:.3f} n={b['count']}"
                )
        else:
            lines.append(f"    calibration : echantillon insuffisant pour l'afficher (< {report['calibration_min_observations']} observations).")
    lines.append("")
    lines.append("--- Marche / pari theorique ---")
    betting = report["betting"]
    if betting["n_bet"] == 0:
        lines.append(f"  {betting['message']}")
    else:
        lines.append(
            f"  n_bet={betting['n_bet']} win_rate={betting['win_rate']:.3f} "
            f"PnL_total={betting['total_pnl_theoretical']:+.4f} ROI={betting['roi_theoretical']:+.4f}"
        )
        lines.append(f"  CLV : non disponible ({betting['clv_unavailable_reason']})")
    return "\n".join(lines)


@app.command()
def main(
    journal_path: Path = typer.Option(DEFAULT_JOURNAL_PATH, "--journal-path", help="Chemin du journal Shadow Mode."),
) -> None:
    report = evaluate_shadow(journal_path)
    typer.echo(format_evaluation_report(report))


if __name__ == "__main__":
    app()
