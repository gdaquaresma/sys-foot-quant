"""CLI : E10 - fiabilite des zones de desaccord modele/marche sur Over/Under
2.5 (question centrale : certaines categories de desaccord modele/marche
correspondent-elles a une estimation historiquement fiable, distincte
d'une simple recherche de "value" ?).

`poisson_simple`, `dixon_coles` et `xg_model` restent INCHANGES. Aucun
nouveau modele, aucune nouvelle calibration. La probabilite modele est
EXACTEMENT celle validee en E8 (correction scalaire walk-forward, verdict
A) - jamais recalculee differemment. Aucune conclusion de rentabilite,
aucune regle de pari, aucune optimisation de seuil.

====================================================================
ETAPE 1 - INSPECTION DU PIPELINE E8/E9 (avant tout code)
====================================================================
- E8 (`run_stage16_e8_walk_forward_validation.py`) expose
  `build_decision_time_lookup`, `attach_walk_forward_scale` (facteur c(m)
  walk-forward, jamais ajuste sur le futur) - REUTILISES SANS MODIFICATION.
- E7 (`run_stage15_e7_total_goals_distribution.py`) expose
  `build_lambda_mu_dataframe`, `matrix_for_row`, `over_under_probs` -
  REUTILISES SANS MODIFICATION pour reconstruire P_model(Over 2.5) a
  partir de la matrice CORRIGEE (scale=c(m) walk-forward).
- E9 (`run_stage18_e9_multi_bookmaker_market_layer.py`) expose
  `load_all_multi_bookmaker_records` (couche multi-bookmaker point-in-time
  deja testee) - REUTILISE SANS MODIFICATION pour les cotes B365 O/U 2.5
  (seul bookmaker disponible sur ce marche - limitation documentee, jamais
  contournee).
- `market_engine.overround.hold_percentage`/`remove_overround_proportional`
  REUTILISES SANS MODIFICATION pour separer probabilite brute, overround,
  probabilite normalisee (jamais une comparaison silencieuse a une
  probabilite brute).
- `calibration_engine.decomposition.brier_decomposition`,
  `.significance.paired_bootstrap_test`/`.two_sample_bootstrap_test`
  REUTILISES SANS MODIFICATION.
- `football_model.scoring.outcome_probabilities` REUTILISE SANS
  MODIFICATION pour le diagnostic secondaire 1X2 (point 13 du protocole).

====================================================================
ETAPE 2 - CATEGORIES DE DESACCORD (FIGEES AVANT EXECUTION REELLE)
====================================================================
gap = P_model(Over 2.5, walk-forward corrige) - P_market(Over 2.5,
normalise, B365 uniquement). Tranches IDENTIQUES a celles deja
pre-enregistrees en E5 (meme granularite de 5 points, continuite
methodologique explicite, jamais choisies apres observation) :

    <=-15 / -15 a -10 / -10 a -5 / -5 a +5 / +5 a +10 / +10 a +15 / >=+15

Zones d'accord/desaccord (point 8, memes seuils 5/10/15) :
    accord (|gap|<5) / desaccord modere (5-10) / desaccord important
    (10-15) / desaccord extreme (>=15)

Seuil d'incertitude elevee (n insuffisant pour conclure) : n < 30 -
IDENTIQUE au seuil deja documente en E5 (`_MIN_N_FOR_LOW_UNCERTAINTY`),
pas une nouvelle valeur choisie ad hoc.

Usage:
    python scripts/run_stage19_e10_disagreement_reliability.py
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
from sys_foot_quant.calibration_engine.significance import (  # noqa: E402
    paired_bootstrap_test,
    two_sample_bootstrap_test,
)
from sys_foot_quant.common.logging import get_logger  # noqa: E402
from sys_foot_quant.data_engine.market_odds.multi_bookmaker_odds import MultiBookmakerMatchRecord  # noqa: E402
from sys_foot_quant.football_model.scoring import outcome_probabilities  # noqa: E402
from sys_foot_quant.market_engine.overround import hold_percentage, remove_overround_proportional  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_MODELS = ("poisson_simple", "dixon_coles", "xg_model")
_N_RESAMPLES = 10_000
_SEED = 0
_MIN_N_FOR_LOW_UNCERTAINTY = 30  # identique a E5 - regle documentee, pas un fait statistique universel

# Tranches de desaccord FIGEES AVANT EXECUTION REELLE - identiques a E5.
_GAP_EDGES = [-np.inf, -0.15, -0.10, -0.05, 0.05, 0.10, 0.15, np.inf]
_GAP_LABELS = ["<=-15pts", "-15/-10", "-10/-5", "-5/+5", "+5/+10", "+10/+15", ">=+15pts"]

_ZONE_LABELS = ["accord (|gap|<5)", "desaccord modere (5-10)", "desaccord important (10-15)", "desaccord extreme (>=15)"]

_STAGE18_PATH = Path(__file__).resolve().parent / "run_stage18_e9_multi_bookmaker_market_layer.py"


def _load_e9():
    spec = importlib.util.spec_from_file_location("run_stage18_e9_multi_bookmaker_market_layer", _STAGE18_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------
# ETAPE 2 - classification (fonctions PURES, jamais dependantes de l'issue)
# --------------------------------------------------------------------------


def classify_gap_bin(gap: float) -> str:
    """Classe UN gap (deja calcule, jamais l'issue du match) selon la
    grille figee ci-dessus."""
    for lo, hi, label in zip(_GAP_EDGES[:-1], _GAP_EDGES[1:], _GAP_LABELS):
        if lo <= gap < hi:
            return label
    raise AssertionError(f"gap={gap} hors de toute tranche - ne devrait jamais arriver (bornes infinies).")


def classify_agreement_zone(gap: float) -> str:
    """Classe UN gap selon son AMPLEUR (valeur absolue) en 4 zones
    accord/desaccord (point 8) - jamais dependant de l'issue du match."""
    abs_gap = abs(gap)
    if abs_gap < 0.05:
        return _ZONE_LABELS[0]
    if abs_gap < 0.10:
        return _ZONE_LABELS[1]
    if abs_gap < 0.15:
        return _ZONE_LABELS[2]
    return _ZONE_LABELS[3]


# --------------------------------------------------------------------------
# ETAPE 3/9 - construction du jeu de donnees (walk-forward, jamais in-sample)
# --------------------------------------------------------------------------


def build_disagreement_dataframe(
    e8_module, e7_module, model: str, records_by_id: dict[str, MultiBookmakerMatchRecord]
) -> pd.DataFrame:
    """Une ligne par match du split TEST walk-forward d'E8 (jamais le
    rodage/calibration) PRESENT dans le corpus multi-bookmaker exploitable
    d'E9 ET disposant d'une cote B365 Over/Under 2.5 complete. P_model
    provient EXACTEMENT du pipeline E8 (`attach_walk_forward_scale` +
    `matrix_for_row`/`over_under_probs` d'E7, scale=c(m) walk-forward,
    jamais recalcule). P_market = B365 uniquement, brut ET normalise
    conserves separement (`overround.py`, REUTILISE SANS MODIFICATION)."""
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
        rec = records_by_id.get(row["match_id"])
        if rec is None:
            continue
        over_by_bk = rec.odds_over_under_2_5.get("Over", {})
        under_by_bk = rec.odds_over_under_2_5.get("Under", {})
        if "B365" not in over_by_bk or "B365" not in under_by_bk:
            continue

        matrix = e7_module.matrix_for_row(row, model, scale=float(row["scale_c"]))
        p_model = e7_module.over_under_probs(matrix, thresholds=(2.5,))[2.5]

        b365_odds = {"Over": over_by_bk["B365"], "Under": under_by_bk["B365"]}
        p_market_raw = 1.0 / b365_odds["Over"]
        overround = hold_percentage(b365_odds)
        p_market_normalized = remove_overround_proportional(b365_odds)["Over"]

        rows.append(
            {
                "match_id": row["match_id"],
                "league": row["league"],
                "season": row["season"],
                "model": model,
                "p_model": p_model,
                "p_market_raw": p_market_raw,
                "overround": overround,
                "p_market_normalized": p_market_normalized,
                "gap": p_model - p_market_normalized,
                "total_goals": row["total_goals"],
                "outcome": float(row["total_goals"] > 2.5),
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# ETAPE 6/7 - table de fiabilite generique (reutilisee pour tranches ET zones)
# --------------------------------------------------------------------------


def reliability_table(df: pd.DataFrame, bin_col: str, labels: list[str]) -> pd.DataFrame:
    """Pour chaque categorie deja assignee (colonne ``bin_col``, jamais
    recalculee ici a partir de l'issue) : n, probabilite moyenne annoncee,
    frequence reelle, biais (reel-annonce) + IC95% bootstrap
    (`paired_bootstrap_test`, REUTILISE), Brier, log loss, resolution
    (`brier_decomposition`, REUTILISE)."""
    rows = []
    for label in labels:
        mask = (df[bin_col] == label).to_numpy()
        n = int(mask.sum())
        if n == 0:
            rows.append(
                {
                    "categorie": label, "n": 0, "p_model_moyen": float("nan"), "frequence_observee": float("nan"),
                    "biais": float("nan"), "biais_ic95_low": float("nan"), "biais_ic95_high": float("nan"),
                    "brier": float("nan"), "log_loss": float("nan"), "resolution": float("nan"),
                    "incertitude_elevee": True,
                }
            )
            continue
        p = df.loc[mask, "p_model"].to_numpy()
        y = df.loc[mask, "outcome"].to_numpy()
        mean_predicted = float(p.mean())
        observed_freq = float(y.mean())
        eps = 1e-12
        logloss = float(np.mean(-(y * np.log(np.clip(p, eps, 1 - eps)) + (1 - y) * np.log(np.clip(1 - p, eps, 1 - eps)))))
        resolution = brier_decomposition(p, y)["resolution"] if n >= 2 else float("nan")
        diffs = y - p
        boot = (
            paired_bootstrap_test(diffs, n_resamples=_N_RESAMPLES, seed=_SEED)
            if n >= 2
            else {"mean_diff": float(diffs.mean()), "ci_low": float("nan"), "ci_high": float("nan")}
        )
        rows.append(
            {
                "categorie": label,
                "n": n,
                "p_model_moyen": mean_predicted,
                "frequence_observee": observed_freq,
                "biais": observed_freq - mean_predicted,
                "biais_ic95_low": boot["ci_low"],
                "biais_ic95_high": boot["ci_high"],
                "brier": float(np.mean((p - y) ** 2)),
                "log_loss": logloss,
                "resolution": resolution,
                "incertitude_elevee": n < _MIN_N_FOR_LOW_UNCERTAINTY,
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# ETAPE 10 - test d'asymetrie (modele > marche vs modele < marche)
# --------------------------------------------------------------------------


def asymmetry_test(df: pd.DataFrame) -> dict:
    """Compare la fiabilite (biais = issue - p_model) entre les matchs ou
    le modele est plus optimiste que le marche (gap>0) et ceux ou il est
    plus pessimiste (gap<0) - `two_sample_bootstrap_test` REUTILISE (les
    deux groupes portent sur des matchs DIFFERENTS, jamais apparies)."""
    above = df[df["gap"] > 0]
    below = df[df["gap"] < 0]
    if len(above) < 2 or len(below) < 2:
        return {
            "n_model_above_market": len(above),
            "n_model_below_market": len(below),
            "bias_above": float("nan"),
            "bias_below": float("nan"),
            "boot": None,
        }
    diffs_above = (above["outcome"] - above["p_model"]).to_numpy()
    diffs_below = (below["outcome"] - below["p_model"]).to_numpy()
    boot = two_sample_bootstrap_test(diffs_above, diffs_below, n_resamples=_N_RESAMPLES, seed=_SEED)
    return {
        "n_model_above_market": len(above),
        "n_model_below_market": len(below),
        "bias_above": float(diffs_above.mean()),
        "bias_below": float(diffs_below.mean()),
        "boot": boot,
    }


def brier_diff_vs_agreement_zone(df: pd.DataFrame, disagreement_zone: str) -> dict | None:
    """Compare le Brier (par match) de la zone d'ACCORD a celui d'une zone
    de DESACCORD donnee - `two_sample_bootstrap_test` REUTILISE (groupes
    non apparies). None si l'une des deux zones a moins de 2 matchs."""
    accord = df[df["zone"] == _ZONE_LABELS[0]]
    disaccord = df[df["zone"] == disagreement_zone]
    if len(accord) < 2 or len(disaccord) < 2:
        return None
    brier_accord = ((accord["p_model"] - accord["outcome"]) ** 2).to_numpy()
    brier_disaccord = ((disaccord["p_model"] - disaccord["outcome"]) ** 2).to_numpy()
    boot = two_sample_bootstrap_test(brier_disaccord, brier_accord, n_resamples=_N_RESAMPLES, seed=_SEED)
    return {"n_accord": len(accord), "n_desaccord": len(disaccord), "boot": boot}


# --------------------------------------------------------------------------
# Diagnostic secondaire 1X2 (point 13 - NE DOIT PAS detourner l'objectif
# principal : traitement volontairement plus leger, global uniquement).
# --------------------------------------------------------------------------


def build_1x2_home_win_dataframe(e7_module, e8_module, records_by_id: dict[str, MultiBookmakerMatchRecord]) -> pd.DataFrame:
    """Meme principe que ``build_disagreement_dataframe`` mais pour la
    selection "victoire domicile" du marche 1X2, `poisson_simple`
    UNIQUEMENT (raw, jamais corrige - la correction E7/E8 est specifique
    au total de buts), sur le MEME split TEST walk-forward."""
    stage10 = e7_module._load_stage10()
    stage8 = stage10._load_stage8()
    df = e7_module.build_lambda_mu_dataframe(stage8)
    _, test_df_stage8 = stage10.build_calibration_and_test_sets(stage8)
    test_ids = set(test_df_stage8["match_id"])
    test_df = df[df["match_id"].isin(test_ids)].copy()

    rows = []
    for _, row in test_df.iterrows():
        if pd.isna(row["poisson_simple_lambda"]) or pd.isna(row["poisson_simple_mu"]):
            continue
        rec = records_by_id.get(row["match_id"])
        if rec is None:
            continue
        h_by_bk = rec.odds_1x2.get("H", {})
        d_by_bk = rec.odds_1x2.get("D", {})
        a_by_bk = rec.odds_1x2.get("A", {})
        if "B365" not in h_by_bk or "B365" not in d_by_bk or "B365" not in a_by_bk:
            continue

        matrix = e7_module.independent_matrix(row["poisson_simple_lambda"], row["poisson_simple_mu"])
        p_model_home, _, _ = outcome_probabilities(matrix)

        b365_odds = {"H": h_by_bk["B365"], "D": d_by_bk["B365"], "A": a_by_bk["B365"]}
        p_market_normalized = remove_overround_proportional(b365_odds)["H"]

        rows.append(
            {
                "match_id": row["match_id"],
                "p_model": p_model_home,
                "p_market_normalized": p_market_normalized,
                "gap": p_model_home - p_market_normalized,
                "outcome": float(row["home_goals"] > row["away_goals"]),
            }
        )
    return pd.DataFrame(rows)


def _print_reliability_table(label: str, table: pd.DataFrame) -> None:
    typer.echo(f"  -- {label} --")
    for _, r in table.iterrows():
        flag = " [INCERTITUDE ELEVEE - n<30]" if r["incertitude_elevee"] else ""
        typer.echo(
            f"    {r['categorie']:<24} n={int(r['n']):<4} p_model={r['p_model_moyen']:.4f} "
            f"freq_obs={r['frequence_observee']:.4f} biais={r['biais']:+.4f} "
            f"IC95%=[{r['biais_ic95_low']:+.4f},{r['biais_ic95_high']:+.4f}] "
            f"Brier={r['brier']:.4f} logloss={r['log_loss']:.4f} resolution={r['resolution']:.4f}{flag}"
        )


@app.command()
def main() -> None:
    typer.echo("=== E10 : fiabilite des zones de desaccord modele/marche (Over/Under 2.5) ===")
    typer.echo(
        "poisson_simple, dixon_coles et xg_model INCHANGES. Aucune nouvelle calibration, aucune "
        "conclusion de rentabilite, aucune regle de pari, aucune optimisation de seuil.\n"
    )
    typer.echo(
        "LIMITATION DOCUMENTEE : B365 est actuellement le SEUL bookmaker Over/Under 2.5 disponible "
        "dans Football-Data - aucune analyse inter-bookmakers O/U, aucun arbitrage O/U, aucune "
        "dispersion multi-bookmakers O/U ne peut etre produite ici.\n"
    )

    e9 = _load_e9()
    e8 = e9._load_e8()
    e7 = e8._load_e7()
    records = e9.load_all_multi_bookmaker_records()
    records_by_id = {r.match_id: r for r in records}
    typer.echo(f"Corpus multi-bookmaker exploitable (E9) : {len(records)} matchs\n")

    for model in _MODELS:
        typer.echo(f"##### {model} #####")
        df = build_disagreement_dataframe(e8, e7, model, records_by_id)
        df["gap_bin"] = df["gap"].apply(classify_gap_bin)
        df["zone"] = df["gap"].apply(classify_agreement_zone)
        typer.echo(f"  n total (test walk-forward x corpus multi-bookmaker x B365 O/U complet) = {len(df)}")

        typer.echo("--- Fiabilite par tranche de gap (GLOBAL) ---")
        _print_reliability_table("GLOBAL", reliability_table(df, "gap_bin", _GAP_LABELS))

        typer.echo("--- Fiabilite par championnat ---")
        for league in sorted(df["league"].unique()):
            _print_reliability_table(league, reliability_table(df[df["league"] == league], "gap_bin", _GAP_LABELS))

        typer.echo("--- Fiabilite par saison ---")
        for season in sorted(df["season"].unique()):
            _print_reliability_table(season, reliability_table(df[df["season"] == season], "gap_bin", _GAP_LABELS))

        typer.echo("--- Zones accord/desaccord (point 8) ---")
        zone_table = reliability_table(df, "zone", _ZONE_LABELS)
        _print_reliability_table("ZONES", zone_table)

        typer.echo("--- Brier : zones de desaccord vs zone d'accord ---")
        for zone in _ZONE_LABELS[1:]:
            result = brier_diff_vs_agreement_zone(df, zone)
            if result is None:
                typer.echo(f"    {zone:<28} donnees insuffisantes (n<2 dans au moins une des deux zones)")
                continue
            b = result["boot"]
            typer.echo(
                f"    {zone:<28} n_desaccord={result['n_desaccord']:<4} n_accord={result['n_accord']:<4} "
                f"diff_Brier(IC95%)=[{b['ci_low']:+.4f},{b['ci_high']:+.4f}] p={b['p_value']:.4f}"
            )

        typer.echo("--- Test d'asymetrie : modele > marche vs modele < marche ---")
        asym = asymmetry_test(df)
        if asym["boot"] is None:
            typer.echo("    donnees insuffisantes")
        else:
            b = asym["boot"]
            typer.echo(
                f"    n(modele>marche)={asym['n_model_above_market']:<4} biais={asym['bias_above']:+.4f} | "
                f"n(modele<marche)={asym['n_model_below_market']:<4} biais={asym['bias_below']:+.4f} | "
                f"diff(IC95%)=[{b['ci_low']:+.4f},{b['ci_high']:+.4f}] p={b['p_value']:.4f}"
            )
        typer.echo("")

    typer.echo("--- Diagnostic SECONDAIRE 1X2 (victoire domicile, poisson_simple RAW, priorite = Over/Under 2.5) ---")
    df_1x2 = build_1x2_home_win_dataframe(e7, e8, records_by_id)
    df_1x2["gap_bin"] = df_1x2["gap"].apply(classify_gap_bin)
    _print_reliability_table("1X2 (H) GLOBAL", reliability_table(df_1x2, "gap_bin", _GAP_LABELS))

    typer.echo(
        "\nRESERVE : aucune conclusion de rentabilite. Aucune regle de pari, ROI, yield, Kelly, "
        "staking, optimisation de seuil, selection de modele/championnat/saison apres observation. "
        "poisson_simple, dixon_coles et xg_model restent inchanges."
    )
    typer.echo("\nARRET : E10 termine, conformement au protocole. Aucune experience E11 lancee automatiquement.")


if __name__ == "__main__":
    app()
