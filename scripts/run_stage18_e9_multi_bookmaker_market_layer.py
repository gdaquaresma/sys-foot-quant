"""CLI : E9 - construction de la couche multi-bookmakers et detection
d'anomalies/arbitrage MATHEMATIQUE (purement descriptif, aucune conclusion
de rentabilite, aucune strategie de pari).

`poisson_simple`, `dixon_coles` et `xg_model` restent INCHANGES. Aucun
nouveau modele predictif. La probabilite modele utilisee ici pour Over 2.5
est EXACTEMENT celle validee en E8 (correction scalaire walk-forward,
verdict A) - jamais recalculee differemment.

====================================================================
ETAPE 1 - INSPECTION PREALABLE (avant tout code)
====================================================================
- `football_data_loader.py` : ne lisait que B365 (1X2 + O/U 2.5). Etendu
  ICI a BW/PS pour le 1X2 uniquement (`BOOKMAKERS_1X2 = ("B365","BW","PS")`)
  - AUCUNE colonne O/U BW/PS n'existe dans les six fichiers sources
    (verifie par inspection directe des en-tetes), perimetre volontairement
    limite a B365 pour l'Over/Under. `BFE` n'est PAS lu - nature d'exchange
    non clarifiee (protocole E9, point 2).
- `market_engine/overround.py` : `remove_overround_proportional`/
  `hold_percentage` REUTILISES SANS MODIFICATION, appliques ICI par
  bookmaker (jamais sur une moyenne de cotes brutes).
- `market_engine/model_vs_market.py` : interface generique deja existante
  pour UN bookmaker ; E9 ajoute les briques manquantes pour PLUSIEURS
  bookmakers (`market_engine/consensus.py`, `.anomaly.py`, `.arbitrage.py`)
  sans modifier `model_vs_market.py`.
- `over_under_odds.py`/`economic_dataset.py` (E1/E5) : mecanisme
  point-in-time (matching, time_resolution, DECISION_OFFSET_HOURS)
  REUTILISE A L'IDENTIQUE par le nouveau module `multi_bookmaker_odds.py`
  - aucun nouveau timestamp, aucune nouvelle regle temporelle.
- ADR 0006 : couvre deja le principe d'extension controlee de
  `_ALLOWED_COLUMNS` - suivi ici pour BW/PS (1X2 uniquement).
- E5/E6/E8 : le pipeline modele Over 2.5 walk-forward valide (E8, verdict
  A) est reutilise TEL QUEL (dynamique, comme toutes les etapes
  precedentes) pour la comparaison modele/marche (point 6 du protocole) -
  jamais recalcule.

====================================================================
ETAPE 2 - PROTOCOLE (fige avant execution reelle)
====================================================================
- Perimetre marche : 1X2 (B365/BW/PS, cotes pre-match uniquement) et
  Over/Under 2.5 (B365 uniquement). Aucune cote de cloture.
- Overround retire PAR BOOKMAKER (`remove_overround_proportional`, un
  bookmaker doit avoir toutes les selections du marche pour etre
  normalise - jamais un marche partiel normalise).
- Consensus = moyenne/mediane/min/max/ecart-type des probabilites
  normalisees entre bookmakers disponibles pour un match/marche/selection
  donnes - AUCUN poids optimise, chaque bookmaker reste identifiable.
- Anomalie (book vs consensus, ou modele vs consensus) : grille
  PRE-ENREGISTREE `market_engine.anomaly` (seuils 0.05/0.10 point de
  probabilite, deja justifies par la granularite utilisee en E5) - jamais
  qualifiee de "value".
- Arbitrage : `market_engine.arbitrage.detect_mathematical_arbitrage`,
  purement mathematique (somme des probabilites inverses des MEILLEURS
  prix < 1) - jamais presente comme une opportunite reelle (aucune prise
  en compte des limites de mise, disponibilite simultanee, regles
  bookmaker, void, delais, variation des prix).
- Comparaison modele/marche restreinte a Over 2.5, sur l'INTERSECTION du
  split TEST walk-forward valide en E8 (n=640, hors echantillon) et du
  corpus multi-bookmaker exploitable - jamais une probabilite modele
  in-sample ou du rodage/calibration.
- Distinction stricte (protocole point 12) : A - modele vs marche (ne
  prouve rien seul) ; B - bookmaker vs marche (anomalie potentielle) ;
  C - arbitrage (phenomene mathematique different, jamais confondu avec A/B).
- Aucun ROI, yield, Kelly, staking, profit, strategie de pari.

Usage:
    python scripts/run_stage18_e9_multi_bookmaker_market_layer.py
"""

from __future__ import annotations

import importlib.util
import json
import statistics
import sys
from pathlib import Path

import pandas as pd
import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.common.logging import get_logger  # noqa: E402
from sys_foot_quant.data_engine.market_odds.football_data_loader import load_football_data_csv  # noqa: E402
from sys_foot_quant.data_engine.market_odds.multi_bookmaker_odds import (  # noqa: E402
    MultiBookmakerMatchRecord,
    build_multi_bookmaker_dataset,
)
from sys_foot_quant.market_engine.anomaly import book_vs_consensus, model_vs_consensus  # noqa: E402
from sys_foot_quant.market_engine.arbitrage import detect_mathematical_arbitrage  # noqa: E402
from sys_foot_quant.market_engine.consensus import compute_consensus  # noqa: E402
from sys_foot_quant.market_engine.overround import hold_percentage, remove_overround_proportional  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_FD_DIR = _REPO_ROOT / "research" / "market_odds" / "football_data" / "runs"
_US_DIR = _REPO_ROOT / "research" / "xg_feasibility" / "runs"

_DATASETS = {
    ("premier_league", "2024_25"): ("E0_2024_25.csv", "epl_2024_datesData.json"),
    ("premier_league", "2025_26"): ("E0_2025_26.csv", "epl_2025_datesData.json"),
    ("ligue1", "2024_25"): ("F1_2024_25.csv", "ligue1_2024_datesData.json"),
    ("ligue1", "2025_26"): ("F1_2025_26.csv", "ligue1_2025_datesData.json"),
    ("liga", "2024_25"): ("SP1_2024_25.csv", "liga_2024_datesData.json"),
    ("liga", "2025_26"): ("SP1_2025_26.csv", "liga_2025_datesData.json"),
}

_MODELS_FOR_OU = ("poisson_simple", "xg_model")
_STAGE16_PATH = Path(__file__).resolve().parent / "run_stage16_e8_walk_forward_validation.py"


def _load_e8():
    spec = importlib.util.spec_from_file_location("run_stage16_e8_walk_forward_validation", _STAGE16_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------
# ETAPE 4/5 - overround par bookmaker, consensus (fonctions pures)
# --------------------------------------------------------------------------


def bookmaker_odds_by_bookmaker(odds_by_selection_bookmaker: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    """Transpose selection->bookmaker->cote en bookmaker->selection->cote.
    Ne retient un bookmaker QUE s'il cote TOUTES les selections du marche
    (condition necessaire pour un retrait d'overround coherent - jamais un
    marche partiel normalise)."""
    selections = list(odds_by_selection_bookmaker)
    bookmakers: set[str] = set()
    for sel in selections:
        bookmakers |= set(odds_by_selection_bookmaker[sel])
    out: dict[str, dict[str, float]] = {}
    for bk in bookmakers:
        if all(bk in odds_by_selection_bookmaker[sel] for sel in selections):
            out[bk] = {sel: odds_by_selection_bookmaker[sel][bk] for sel in selections}
    return out


def normalized_probs_by_selection(odds_by_selection_bookmaker: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    """selection -> {bookmaker: probabilite normalisee} - overround retire
    PAR BOOKMAKER (`remove_overround_proportional`, REUTILISE SANS
    MODIFICATION) avant toute comparaison entre bookmakers."""
    by_bk = bookmaker_odds_by_bookmaker(odds_by_selection_bookmaker)
    normalized_by_bk = {bk: remove_overround_proportional(o) for bk, o in by_bk.items()}
    selections = list(odds_by_selection_bookmaker)
    out: dict[str, dict[str, float]] = {sel: {} for sel in selections}
    for bk, probs in normalized_by_bk.items():
        for sel, p in probs.items():
            out[sel][bk] = p
    return out


def overrounds_by_bookmaker(odds_by_selection_bookmaker: dict[str, dict[str, float]]) -> dict[str, float]:
    by_bk = bookmaker_odds_by_bookmaker(odds_by_selection_bookmaker)
    return {bk: hold_percentage(o) for bk, o in by_bk.items()}


# --------------------------------------------------------------------------
# ETAPE 7 - anomalies book vs consensus (agregation sur un marche)
# --------------------------------------------------------------------------


def book_anomalies_for_market(odds_by_selection_bookmaker: dict[str, dict[str, float]]) -> dict[str, dict[str, dict]]:
    """selection -> bookmaker -> resultat de `book_vs_consensus` - calcule
    UNIQUEMENT sur les selections ayant au moins un bookmaker."""
    normalized = normalized_probs_by_selection(odds_by_selection_bookmaker)
    out: dict[str, dict[str, dict]] = {}
    for sel, probs in normalized.items():
        if not probs:
            continue
        consensus = compute_consensus(probs)
        out[sel] = {bk: book_vs_consensus(bk, p, consensus) for bk, p in probs.items()}
    return out


# --------------------------------------------------------------------------
# ETAPE 8 - arbitrage (delegue a market_engine.arbitrage, sur cotes BRUTES)
# --------------------------------------------------------------------------


def arbitrage_for_market(odds_by_selection_bookmaker: dict[str, dict[str, float]]) -> dict | None:
    """None si au moins une selection du marche n'a AUCUN bookmaker
    (arbitrage non evaluable), sinon le resultat de
    `detect_mathematical_arbitrage` (REUTILISE SANS MODIFICATION)."""
    if any(not by_bk for by_bk in odds_by_selection_bookmaker.values()):
        return None
    return detect_mathematical_arbitrage(odds_by_selection_bookmaker)


# --------------------------------------------------------------------------
# Chargement des donnees reelles (6 fichiers, INCHANGE - meme convention
# que E1/E5/E6/E7/E8)
# --------------------------------------------------------------------------


def load_all_multi_bookmaker_records() -> list[MultiBookmakerMatchRecord]:
    records: list[MultiBookmakerMatchRecord] = []
    for (league, season), (fd_name, us_name) in _DATASETS.items():
        fd_records = load_football_data_csv(_FD_DIR / fd_name, league=league, season=season)
        with open(_US_DIR / us_name) as f:
            us_raw = json.load(f)
        report = build_multi_bookmaker_dataset(league, season, us_raw, fd_records)
        records.extend(report.records)
    return records


# --------------------------------------------------------------------------
# ETAPE 11 - rapport descriptif agrege (structure du marche uniquement)
# --------------------------------------------------------------------------


def _coverage_report(records: list[MultiBookmakerMatchRecord], market: str) -> dict:
    bookmakers_seen: set[str] = set()
    counts: dict[str, int] = {}
    n_matches_with_market = 0
    for r in records:
        odds = r.odds_1x2 if market == "1x2" else r.odds_over_under_2_5
        bks = {bk for by_bk in odds.values() for bk in by_bk}
        if bks:
            n_matches_with_market += 1
        bookmakers_seen |= bks
        for bk in bks:
            counts[bk] = counts.get(bk, 0) + 1
    return {
        "n_matches": len(records),
        "n_matches_with_market": n_matches_with_market,
        "bookmakers": sorted(bookmakers_seen),
        "coverage_by_bookmaker": counts,
    }


def _overround_dispersion_anomaly_arbitrage_report(records: list[MultiBookmakerMatchRecord], market: str) -> dict:
    overrounds: dict[str, list[float]] = {}
    dispersions: list[float] = []
    n_multi_bookmaker = 0
    anomaly_counts: dict[str, int] = {}
    n_arbitrage_evaluable = 0
    n_arbitrage_positive = 0

    for r in records:
        odds = r.odds_1x2 if market == "1x2" else r.odds_over_under_2_5
        for bk, oround in overrounds_by_bookmaker(odds).items():
            overrounds.setdefault(bk, []).append(oround)

        normalized = normalized_probs_by_selection(odds)
        for sel, probs in normalized.items():
            if not probs:
                continue
            consensus = compute_consensus(probs)
            if consensus["n_bookmakers"] >= 2:
                n_multi_bookmaker += 1
                dispersions.append(consensus["std"])
            for bk, p in probs.items():
                result = book_vs_consensus(bk, p, consensus)
                anomaly_counts[result["classification"]] = anomaly_counts.get(result["classification"], 0) + 1

        arb = arbitrage_for_market(odds)
        if arb is not None:
            n_arbitrage_evaluable += 1
            if arb["is_mathematical_arbitrage"]:
                n_arbitrage_positive += 1

    return {
        "mean_overround_by_bookmaker": {bk: statistics.fmean(v) for bk, v in overrounds.items()},
        "median_overround_by_bookmaker": {bk: statistics.median(v) for bk, v in overrounds.items()},
        "n_selection_instances_multi_bookmaker": n_multi_bookmaker,
        "mean_dispersion_std_when_multi_bookmaker": statistics.fmean(dispersions) if dispersions else float("nan"),
        "anomaly_classification_counts": anomaly_counts,
        "n_arbitrage_evaluable": n_arbitrage_evaluable,
        "n_arbitrage_mathematical_positive": n_arbitrage_positive,
    }


# --------------------------------------------------------------------------
# ETAPE 6 - modele vs marche, Over 2.5 uniquement, sur le split TEST
# walk-forward VALIDE en E8 (jamais in-sample)
# --------------------------------------------------------------------------


def model_over25_probs_walk_forward(e8_module, e7_module, model: str) -> dict[str, float]:
    """match_id -> P_model(Over 2.5), EXACTEMENT le pipeline valide en E8
    (correction scalaire walk-forward, verdict A) - jamais recalcule
    differemment. Restreint, par construction, au split TEST (out-of-sample)."""
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
    out: dict[str, float] = {}
    for _, row in with_scale.iterrows():
        if pd.isna(row["scale_c"]):
            continue
        matrix = e7_module.matrix_for_row(row, model, scale=float(row["scale_c"]))
        out[row["match_id"]] = e7_module.over_under_probs(matrix, thresholds=(2.5,))[2.5]
    return out


def model_vs_market_report(records_by_id: dict[str, MultiBookmakerMatchRecord], model_probs: dict[str, float]) -> dict:
    """Compare P_model (walk-forward, Over 2.5) au consensus de marche et
    a chaque bookmaker, UNIQUEMENT sur les matchs presents a la fois dans
    le split TEST modele et le corpus multi-bookmaker exploitable."""
    gaps: list[float] = []
    classifications: dict[str, int] = {}
    n = 0
    for match_id, p_model in model_probs.items():
        rec = records_by_id.get(match_id)
        if rec is None:
            continue
        normalized = normalized_probs_by_selection(rec.odds_over_under_2_5)
        over_probs = normalized.get("Over", {})
        if not over_probs:
            continue
        consensus = compute_consensus(over_probs)
        result = model_vs_consensus(p_model, consensus)
        gaps.append(result["gap"])
        classifications[result["classification"]] = classifications.get(result["classification"], 0) + 1
        n += 1
    return {
        "n": n,
        "mean_gap": statistics.fmean(gaps) if gaps else float("nan"),
        "median_gap": statistics.median(gaps) if gaps else float("nan"),
        "classification_counts": classifications,
    }


@app.command()
def main() -> None:
    typer.echo("=== E9 : couche multi-bookmakers et detection d'anomalies/arbitrage ===")
    typer.echo(
        "poisson_simple, dixon_coles et xg_model INCHANGES. Aucune conclusion de rentabilite, "
        "aucune strategie de pari - structure du marche uniquement.\n"
    )

    records = load_all_multi_bookmaker_records()
    typer.echo(f"Matchs multi-bookmaker exploitables (B365 1X2 complet, PIT verifie) : {len(records)}\n")

    for market, label in (("1x2", "1X2"), ("over_under_2_5", "Over/Under 2.5")):
        typer.echo(f"--- Marche {label} ---")
        coverage = _coverage_report(records, market)
        typer.echo(f"  Bookmakers observes : {coverage['bookmakers']}")
        typer.echo(f"  Matchs avec au moins un bookmaker sur ce marche : {coverage['n_matches_with_market']}/{coverage['n_matches']}")
        for bk, n in sorted(coverage["coverage_by_bookmaker"].items()):
            typer.echo(f"    {bk:6s} couverture = {n}/{coverage['n_matches']} ({100 * n / coverage['n_matches']:.1f}%)")

        stats = _overround_dispersion_anomaly_arbitrage_report(records, market)
        typer.echo("  Overround moyen (marge) par bookmaker :")
        for bk, v in sorted(stats["mean_overround_by_bookmaker"].items()):
            typer.echo(f"    {bk:6s} moyenne={v:.4f} mediane={stats['median_overround_by_bookmaker'][bk]:.4f}")
        typer.echo(
            f"  Instances selection x match avec >=2 bookmakers : {stats['n_selection_instances_multi_bookmaker']} "
            f"(ecart-type moyen entre bookmakers = {stats['mean_dispersion_std_when_multi_bookmaker']:.4f})"
        )
        typer.echo(f"  Frequence des classifications d'ecart (bookmaker vs consensus) : {stats['anomaly_classification_counts']}")
        typer.echo(
            f"  Arbitrage mathematique (B - detection historique, PAS une opportunite reelle) : "
            f"{stats['n_arbitrage_mathematical_positive']}/{stats['n_arbitrage_evaluable']} matchs evaluables"
        )
        typer.echo("")

    typer.echo("--- Modele vs marche (A), Over 2.5 uniquement, split TEST walk-forward valide (E8) ---")
    e8 = _load_e8()
    e7 = e8._load_e7()
    records_by_id = {r.match_id: r for r in records}
    for model in _MODELS_FOR_OU:
        model_probs = model_over25_probs_walk_forward(e8, e7, model)
        report = model_vs_market_report(records_by_id, model_probs)
        typer.echo(
            f"  {model:<16} n={report['n']:<4} ecart moyen (modele-consensus)={report['mean_gap']:+.4f} "
            f"mediane={report['median_gap']:+.4f} classifications={report['classification_counts']}"
        )
    typer.echo(
        "  RAPPEL : un ecart modele/marche (A) ne prouve rien seul - jamais qualifie de 'value'. "
        "Distinct d'une anomalie bookmaker/marche (B) et d'un arbitrage mathematique (C)."
    )

    typer.echo(
        "\nRESERVE : aucune conclusion de rentabilite. Aucun ROI, yield, Kelly, staking, profit, "
        "strategie de pari. poisson_simple, dixon_coles et xg_model restent inchanges."
    )
    typer.echo("\nARRET : E9 termine, conformement au protocole. Aucune experience E10 lancee automatiquement.")


if __name__ == "__main__":
    app()
