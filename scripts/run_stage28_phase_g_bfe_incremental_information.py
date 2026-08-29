"""Phase G - les prix Betfair Exchange (BFE) apportent-ils une
information de marche INCREMENTALE par rapport a B365, deja exploite
depuis E1 ?

Experience DIAGNOSTIQUE UNIQUE (docs/bfe_incremental_information_experiment.md).
Ne modifie AUCUN modele (`poisson_simple`/`dixon_coles`/`xg_model`),
AUCUNE correction E7/E8/E14/E15/E16, AUCUN gate. N'ACTIVE PAS `BET`, NE
FIXE PAS `min_edge_threshold`. Question posee : BFE apporte-t-il une
information au-dela de B365 - PAS "BFE est-il meilleur que B365", PAS
"peut-on gagner de l'argent avec BFE".

====================================================================
ETAPE 1 - AUDIT DES COLONNES BETFAIR (avant tout code, inspection
directe des six fichiers reels, jamais suppose)
====================================================================
Deux instruments Betfair DISTINCTS, jamais un seul :
- ``BF``/``BFD`` (renomme entre saisons, EXACTEMENT comme WH->LB, E13) :
  overround moyen 1.045-1.060, IDENTIQUE au profil B365 (1.055-1.056) -
  signature d'un bookmaker a marge classique ("Betfair Sportsbook"). 1X2
  UNIQUEMENT. **NON LU** - redondant par construction avec BW/PS/WH/LB
  deja exclus comme non-informatifs (E9/E13), hors perimetre (une seule
  variable nouvelle : BFE).
- ``BFEH/D/A``, ``BFE>2.5/<2.5`` (constant sur les six fichiers) :
  overround moyen 1.006-1.013 - PRES DE 1.0, signature attendue d'un prix
  d'echange ("best back price", sans marge de bookmaker centralisee).
  Couverture par ligne : 100% (2024/25), 92-95% (2025/26). **SEUL
  INSTRUMENT LU** (voir `football_data_loader.py` pour le detail complet
  de cet audit, avec les deux preuves structurelles independantes).
``BFEAHH/AHA`` (handicap asiatique) et toute colonne de cloture (``BFC*``,
``BFEC*``) : colonnes existantes mais **NON LUES**, hors perimetre
explicite (etape 12).

====================================================================
ETAPE 2 - POINT-IN-TIME
====================================================================
BFE provient de la MEME ligne source que B365 (meme moment de collecte
suppose) - AUCUNE nouvelle regle temporelle. Reutilise EXACTEMENT
`matching.py`/`time_resolution.conservative_knowledge_time_utc`/
`DECISION_OFFSET_HOURS` (`betfair_exchange_odds.py`, INCHANGES depuis
E5/E9). Colonnes d'OUVERTURE uniquement (``BFEH``/``BFED``/``BFEA``/
``BFE>2.5``/``BFE<2.5``) - jamais la cloture, jamais melangees.

====================================================================
ETAPE 3/4 - MARCHES ET MODELES COMPARES (figes avant execution)
====================================================================
1X2 (H, D, A separement) PUIS Over/Under 2.5 (Over uniquement - Under
exclu, degenerescence complementaire deja demontree en E13). Pour
chaque selection :
    B365            : p = normalise(cote B365) - ZERO parametre.
    B365-recalibre  : p = sigmoid(a + b*logit(p_B365)) - 2 parametres,
                      walk-forward - CONTROLE OBLIGATOIRE (lecon Phase F :
                      isole tout effet de re-calibration generique d'un
                      effet specifique a BFE, jamais teste directement
                      B365+BFE contre B365 brut).
    B365+BFE        : p = sigmoid(a + b*logit(p_B365) + c*logit(p_BFE)) -
                      3 parametres, walk-forward - TEST CENTRAL.
Tous les modeles a parametres reutilisent SANS MODIFICATION
`fit_logistic`/`predict_logistic`/`_safe_logit`/`walk_forward_logistic`
(E16, `run_stage25...py`), meme `_MIN_TRAIN=30`. Une seule passe
walk-forward sur le corpus complet (meme justification que Phase F,
etape 3bis - pas de threshold a proteger, effectif maximise).

====================================================================
ETAPE 9 - NORMALISATION (figee avant execution)
====================================================================
`remove_overround_proportional` (REUTILISE SANS MODIFICATION,
`market_engine.overround`) - fonction AGNOSTIQUE a la taille de la marge
(p_i = (1/cote_i) / somme_j(1/cote_j)), valide pour n'importe quel
ensemble de cotes decimales completes, QUELLE QUE SOIT la marge integree
- jamais une correction differente appliquee a BFE sous pretexte que son
overround est plus proche de 1.0 (ce serait supposer une propriete non
verifiee ; la meme formule marche identiquement dans les deux cas).

====================================================================
ETAPE 11 - GRILLE DE VERDICT (definie AVANT observation des resultats)
====================================================================
    VALIDE   : IC95% de la difference de Brier (B365+BFE vs
               B365-recalibre, PAS vs B365 brut) ENTIEREMENT < 0 AU
               NIVEAU GLOBAL, ET stable par championnat/saison (pas
               d'inversion), ET aucune degradation majeure de calibration,
               ET aucune fuite detectee.
    NON VALIDE : IC95% chevauchant 0, OU instable (inversion dans une
               decoupe), OU redondant (coefficient BFE non distinguable
               de 0 dans la regression walk-forward).
    REJETE   : fuite temporelle, mauvaise interpretation de colonne,
               protocole invalide, couverture insuffisante.
Applique mecaniquement, PAR MARCHE/SELECTION, sans ajustement apres
observation.

====================================================================
INTERDIT (etape 12)
====================================================================
Pas de modification du moteur, pas d'activation de BET, pas de
`min_edge_threshold`, pas de dizaines de transformations BFE testees,
pas d'AH simultane, pas de SOT simultane, pas de nouvelles lignes O/U,
pas de compositions/blessures, pas d'analyse de rentabilite.

Usage:
    python scripts/run_stage28_phase_g_bfe_incremental_information.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.calibration_engine.decomposition import brier_decomposition  # noqa: E402
from sys_foot_quant.calibration_engine.reliability import reliability_bins  # noqa: E402
from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test  # noqa: E402
from sys_foot_quant.data_engine.market_odds.betfair_exchange_odds import build_betfair_exchange_dataset  # noqa: E402
from sys_foot_quant.data_engine.market_odds.football_data_loader import load_football_data_csv  # noqa: E402
from sys_foot_quant.market_engine.overround import remove_overround_proportional  # noqa: E402

app = typer.Typer(add_completion=False)

_MIN_TRAIN_LOGISTIC = 30  # E16, REUTILISE - meme convention
_SELECTIONS_1X2 = ("H", "D", "A")

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

_STAGE25_PATH = Path(__file__).resolve().parent / "run_stage25_e16_market_movement_information.py"


def _load_e16():
    spec = importlib.util.spec_from_file_location("run_stage25_e16_market_movement_information", _STAGE25_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------
# ETAPE 1 - construction du corpus B365+BFE (toutes ligues x saisons).
# --------------------------------------------------------------------------


def load_all_betfair_exchange_records() -> list:
    records = []
    for (league, season), (fd_name, us_name) in _DATASETS.items():
        fd_records = load_football_data_csv(_FD_DIR / fd_name, league=league, season=season)
        with open(_US_DIR / us_name) as f:
            us_raw = json.load(f)
        report = build_betfair_exchange_dataset(league, season, us_raw, fd_records)
        records.extend(report.records)
    return records


def _actual_1x2_selection(r) -> str:
    if r.home_goals > r.away_goals:
        return "H"
    if r.home_goals < r.away_goals:
        return "A"
    return "D"


def build_market_dataframe(records: list, selection: str) -> pd.DataFrame:
    """Construit, pour UNE selection (H/D/A du 1X2, ou "Over" de l'O/U
    2.5), le DataFrame trie par decision_time avec p_b365/p_bfe
    (probabilites NORMALISEES, `remove_overround_proportional`,
    REUTILISE) et l'issue binaire reelle - `p_bfe` vaut NaN si BFE est
    absent sur ce match pour ce marche (jamais invente)."""
    is_1x2 = selection in _SELECTIONS_1X2
    rows = []
    for r in records:
        b365_odds = r.b365_1x2 if is_1x2 else r.b365_over_under_2_5
        if not b365_odds:
            continue
        p_b365 = remove_overround_proportional(b365_odds)[selection]

        bfe_odds = r.bfe_1x2 if is_1x2 else r.bfe_over_under_2_5
        p_bfe = remove_overround_proportional(bfe_odds)[selection] if bfe_odds else np.nan

        outcome = float(_actual_1x2_selection(r) == selection) if is_1x2 else float(r.total_goals > 2.5)
        rows.append(
            {
                "match_id": r.match_id,
                "league": r.league,
                "season": r.season,
                "decision_time": r.decision_time_utc,
                "p_b365": p_b365,
                "p_bfe": p_bfe,
                "outcome": outcome,
            }
        )
    df = pd.DataFrame(rows)
    return df.sort_values("decision_time").reset_index(drop=True)


# --------------------------------------------------------------------------
# ETAPE 3/4 - eligibilite (B365 ET BFE tous deux disponibles) et
# construction des 3 series (B365, B365-recalibre CONTROLE, B365+BFE).
# --------------------------------------------------------------------------


def eligible_dataset(df: pd.DataFrame) -> pd.DataFrame:
    elig = df.dropna(subset=["p_b365", "p_bfe"]).copy()
    return elig.sort_values("decision_time").reset_index(drop=True)


def build_b365_vs_bfe(elig: pd.DataFrame, e16_module) -> pd.DataFrame:
    """Mirroir exact de `run_stage27...build_o_vs_osot` (Phase F) -
    memes primitives E16, meme controle obligatoire (lecon Phase F)."""

    def _cov_b365_recal(d: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        logit_b365 = e16_module._safe_logit(d["p_b365"].to_numpy())
        X = np.column_stack([np.ones(len(d)), logit_b365])
        return X, d["outcome"].to_numpy()

    def _cov_b365_bfe(d: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        logit_b365 = e16_module._safe_logit(d["p_b365"].to_numpy())
        logit_bfe = e16_module._safe_logit(d["p_bfe"].to_numpy())
        X = np.column_stack([np.ones(len(d)), logit_b365, logit_bfe])
        return X, d["outcome"].to_numpy()

    p_b365_recal = e16_module.walk_forward_logistic(elig, _cov_b365_recal, min_train=_MIN_TRAIN_LOGISTIC)
    p_b365_bfe = e16_module.walk_forward_logistic(elig, _cov_b365_bfe, min_train=_MIN_TRAIN_LOGISTIC)
    out = elig.copy()
    out["p_b365_recal"] = p_b365_recal
    out["p_b365_bfe"] = p_b365_bfe
    return out.dropna(subset=["p_b365_recal", "p_b365_bfe"]).reset_index(drop=True)


# --------------------------------------------------------------------------
# ETAPE 7/10 - metriques et tests statistiques.
# --------------------------------------------------------------------------


def _brier_logloss(p: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    eps = 1e-12
    brier = (p - y) ** 2
    logloss = -(y * np.log(np.clip(p, eps, 1 - eps)) + (1 - y) * np.log(np.clip(1 - p, eps, 1 - eps)))
    return brier, logloss


def _calibration_weighted_error(p: np.ndarray, y: np.ndarray, n_bins: int = 10) -> float:
    bins = reliability_bins(p, y, n_bins=n_bins)
    non_empty = bins[bins["count"] > 0]
    if non_empty.empty:
        return float("nan")
    abs_err = (non_empty["mean_predicted"] - non_empty["observed_frequency"]).abs()
    return float((abs_err * non_empty["count"]).sum() / non_empty["count"].sum())


def evaluate_b365_vs_bfe(compared: pd.DataFrame) -> dict:
    """Test PRINCIPAL : B365+BFE vs le CONTROLE B365-recalibre (jamais vs
    B365 brut - meme lecon que Phase F)."""
    p_b365 = compared["p_b365"].to_numpy()
    p_recal = compared["p_b365_recal"].to_numpy()
    p_bfe_combo = compared["p_b365_bfe"].to_numpy()
    y = compared["outcome"].to_numpy()
    n = len(compared)

    brier_b365, logloss_b365 = _brier_logloss(p_b365, y)
    brier_recal, logloss_recal = _brier_logloss(p_recal, y)
    brier_combo, logloss_combo = _brier_logloss(p_bfe_combo, y)

    boot_brier_combo_minus_b365 = paired_bootstrap_test(brier_combo - brier_b365, seed=0)
    boot_brier_combo_minus_recal = paired_bootstrap_test(brier_combo - brier_recal, seed=0)
    boot_logloss_combo_minus_recal = paired_bootstrap_test(logloss_combo - logloss_recal, seed=0)

    return {
        "n": n,
        "brier_b365": float(brier_b365.mean()),
        "brier_recal": float(brier_recal.mean()),
        "brier_combo": float(brier_combo.mean()),
        "logloss_b365": float(logloss_b365.mean()),
        "logloss_recal": float(logloss_recal.mean()),
        "logloss_combo": float(logloss_combo.mean()),
        "boot_brier_combo_minus_b365": boot_brier_combo_minus_b365,
        "boot_brier_combo_minus_recal": boot_brier_combo_minus_recal,
        "boot_logloss_combo_minus_recal": boot_logloss_combo_minus_recal,
        "calibration_b365": _calibration_weighted_error(p_b365, y),
        "calibration_recal": _calibration_weighted_error(p_recal, y),
        "calibration_combo": _calibration_weighted_error(p_bfe_combo, y),
        "resolution_b365": brier_decomposition(p_b365, y)["resolution"],
        "resolution_recal": brier_decomposition(p_recal, y)["resolution"],
        "resolution_combo": brier_decomposition(p_bfe_combo, y)["resolution"],
    }


def classify_verdict(global_res: dict, scope_boots: list[dict]) -> str:
    """Grille FIGEE (etape 11) - le critere de significativite porte sur
    B365+BFE vs le CONTROLE B365-recalibre, jamais vs B365 brut."""
    ci_high = global_res["boot_brier_combo_minus_recal"]["ci_high"]
    globally_improved = ci_high < 0.0
    any_scope_inversion = any(s["ci_low"] > 0.0 for s in scope_boots)
    calibration_degraded = global_res["calibration_combo"] > global_res["calibration_recal"] * 1.5

    if not globally_improved:
        return "NON VALIDE"
    if any_scope_inversion or calibration_degraded:
        return "NON VALIDE"
    return "VALIDE"


def _print_metrics(label: str, res: dict) -> None:
    typer.echo(f"  -- {label} (n={res['n']}) --")
    typer.echo(f"    Brier B365={res['brier_b365']:.4f}  B365-recalibre={res['brier_recal']:.4f}  B365+BFE={res['brier_combo']:.4f}")
    typer.echo(f"      B365+BFE vs B365 brut       diff(IC95%)=[{res['boot_brier_combo_minus_b365']['ci_low']:+.4f}, {res['boot_brier_combo_minus_b365']['ci_high']:+.4f}] "
               f"p={res['boot_brier_combo_minus_b365']['p_value']:.4f}")
    typer.echo(f"      B365+BFE vs B365-recalibre  diff(IC95%)=[{res['boot_brier_combo_minus_recal']['ci_low']:+.4f}, {res['boot_brier_combo_minus_recal']['ci_high']:+.4f}] "
               f"p={res['boot_brier_combo_minus_recal']['p_value']:.4f}  <- TEST PRINCIPAL (information incrementale)")
    typer.echo(f"    LogLoss B365={res['logloss_b365']:.4f}  B365-recalibre={res['logloss_recal']:.4f}  B365+BFE={res['logloss_combo']:.4f}")
    typer.echo(f"      B365+BFE vs B365-recalibre  diff(IC95%)=[{res['boot_logloss_combo_minus_recal']['ci_low']:+.4f}, {res['boot_logloss_combo_minus_recal']['ci_high']:+.4f}]")
    typer.echo(f"    Calibration B365={res['calibration_b365']:.4f}  B365-recalibre={res['calibration_recal']:.4f}  B365+BFE={res['calibration_combo']:.4f}")
    typer.echo(f"    Resolution  B365={res['resolution_b365']:.4f}  B365-recalibre={res['resolution_recal']:.4f}  B365+BFE={res['resolution_combo']:.4f}")


def run_for_selection(selection: str, records: list, e16_module) -> tuple[dict, str]:
    typer.echo(f"\n########## Selection : {selection} ##########")
    df = build_market_dataframe(records, selection)
    typer.echo(f"n_corpus (B365 disponible) = {len(df)}")

    elig = eligible_dataset(df)
    typer.echo(f"n_eligible (B365 ET BFE tous deux disponibles) = {len(elig)}")

    compared = build_b365_vs_bfe(elig, e16_module)
    typer.echo(f"n_compare (apres warm-up walk-forward, min_train={_MIN_TRAIN_LOGISTIC}) = {len(compared)}")

    global_res = evaluate_b365_vs_bfe(compared)
    _print_metrics("GLOBAL", global_res)

    scope_boots = []
    typer.echo("  -- Robustesse par championnat (descriptif) --")
    for league in sorted(compared["league"].unique()):
        sub = compared[compared["league"] == league]
        if len(sub) < 10:
            typer.echo(f"    {league} : n={len(sub)} (trop peu, non exploite)")
            continue
        res = evaluate_b365_vs_bfe(sub)
        _print_metrics(f"    {league}", res)
        scope_boots.append(res["boot_brier_combo_minus_recal"])

    typer.echo("  -- Robustesse par saison (descriptif) --")
    for season in sorted(compared["season"].unique()):
        sub = compared[compared["season"] == season]
        if len(sub) < 10:
            typer.echo(f"    {season} : n={len(sub)} (trop peu, non exploite)")
            continue
        res = evaluate_b365_vs_bfe(sub)
        _print_metrics(f"    {season}", res)
        scope_boots.append(res["boot_brier_combo_minus_recal"])

    verdict = classify_verdict(global_res, scope_boots)
    typer.echo(f"  -> VERDICT {selection} : {verdict}")
    return global_res, verdict


@app.command()
def main() -> None:
    typer.echo("=== Phase G : information incrementale de Betfair Exchange (BFE) sur B365 ===")
    typer.echo("B365 = benchmark deja valide (E1-E16, INCHANGE). BFE = SEUL nouvel instrument (Betfair Sportsbook BF/BFD explicitement NON lu).\n")

    e16 = _load_e16()
    records = load_all_betfair_exchange_records()
    typer.echo(f"n_matches_exploitables (tous marches confondus, avant filtre par marche) = {len(records)}")
    n_with_bfe_1x2 = sum(1 for r in records if r.bfe_1x2 is not None)
    n_with_bfe_ou = sum(1 for r in records if r.bfe_over_under_2_5 is not None)
    typer.echo(f"  dont BFE 1X2 disponible : {n_with_bfe_1x2} ({n_with_bfe_1x2/len(records):.1%})")
    typer.echo(f"  dont BFE O/U 2.5 disponible : {n_with_bfe_ou} ({n_with_bfe_ou/len(records):.1%})")

    verdicts: dict[str, str] = {}
    for selection in (*_SELECTIONS_1X2, "Over"):
        _, verdict = run_for_selection(selection, records, e16)
        verdicts[selection] = verdict

    typer.echo("\n=== VERDICTS (grille figee avant observation, par selection) ===")
    for selection, v in verdicts.items():
        typer.echo(f"  {selection:<6} -> {v}")

    typer.echo(
        "\nRESERVE : aucune conclusion de rentabilite, aucune strategie de pari, aucun seuil "
        "d'edge/ROI. Aucun modele/gate modifie. `BET` non active, `min_edge_threshold` non fixe."
    )
    typer.echo("\nARRET : Phase G terminee, conformement au protocole. Aucune experience suivante lancee automatiquement.")


if __name__ == "__main__":
    app()
