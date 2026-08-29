"""CLI : E13 - la dispersion entre bookmakers contient-elle une
information exploitable sur les probabilites reelles de buts, et
peut-on detecter des incoherences de prix (arbitrage mathematique) entre
bookmakers ? PRIORITE ABSOLUE : Over/Under, en particulier Over 2.5.

`poisson_simple`, `dixon_coles` et `xg_model` restent INCHANGES. Aucun
nouveau modele, aucune nouvelle calibration, aucun tuning, aucun
ROI/Kelly/staking, aucune strategie de pari.

====================================================================
ETAPE 1 - INVENTAIRE PRECIS (avant tout code, "ne rien supposer")
====================================================================
Inspection DIRECTE des six fichiers reels (jamais une hypothese) :
  - 1X2 : B365 (100%), BW (~60-100%), PS (~50-100%), et DEUX colonnes
    jamais lues auparavant - WH (William Hill, UNIQUEMENT fichiers
    2024/25) et LB (Ladbrokes, UNIQUEMENT fichiers 2025/26) - Football-Data
    renomme ce "5e" bookmaker suivi d'une saison a l'autre.
  - Over/Under : CORRECTION IMPORTANTE d'un inventaire incomplet des
    etapes E9-E12 (qui avaient suppose B365 seul sans verifier l'en-tete
    brut) - Pinnacle publie AUSSI une cote Over/Under 2.5, sous le
    prefixe ``P`` (distinct de ``PS`` utilise pour son 1X2 - convention
    de nommage historique de Football-Data). Couverture quasi-complete
    en 2024/25 (~99%), degradee en 2025/26 (~45-50% manquant) - EXACTEMENT
    le meme profil que ``PS`` (1X2), ce qui corrobore qu'il s'agit du
    meme bookmaker. L'Over/Under 2.5 dispose donc REELLEMENT de DEUX
    bookmakers nommes (B365, P) - la dispersion/le consensus/l'arbitrage
    y redeviennent evaluables. `Max`/`Avg` (agregats a composition opaque,
    deja exclus par l'ADR 0006, decision NON revisitee) et `BFE` (nature
    d'exchange non clarifiee) restent explicitement exclus.
  - Extension controlee de `football_data_loader.py` (voir docstring du
    module et ADR 0006) : `_ALLOWED_COLUMNS` etendue a `P>2.5`/`P<2.5` ;
    nouvelle liste `_OPTIONAL_COLUMNS` pour `WHH/D/A`/`LBH/D/A` (lues
    seulement si presentes DANS LE FICHIER, jamais une erreur si
    absentes) ; `BOOKMAKERS_1X2` etendue a `("B365","BW","PS","WH","LB")` ;
    `OVER_UNDER_25_BOOKMAKERS = ("B365","P")`. `multi_bookmaker_odds.py`
    (E9) corrige en consequence : `_odds_over_under_snapshot` inclut
    desormais Pinnacle - les scripts E10/E11/E12 restent NUMERIQUEMENT
    INCHANGES (ils cherchent explicitement la cle "B365", jamais un
    parcours generique des bookmakers presents).

====================================================================
ETAPE 2 - SIX NOTIONS STRICTEMENT DISTINGUEES (jamais confondues, point 9)
====================================================================
1. INFORMATION DESCRIPTIVE : statistiques brutes (couverture, overround,
   dispersion moyenne) - ne prouvent rien en soi.
2. DISCRIMINATION : capacite d'une variable a separer les issues.
3. CALIBRATION : le biais (frequence reelle - probabilite annoncee) et
   son IC95% - coeur des tests de ce script.
4. ANOMALIE DE PRIX : un bookmaker s'ecarte du consensus DE PLUSIEURS
   bookmakers (reutilise `market_engine.anomaly`, deja defini en E9).
5. ARBITRAGE MATHEMATIQUE : detection HISTORIQUE pure
   (`market_engine.arbitrage`, deja defini en E9) - jamais presente comme
   une opportunite actuellement disponible.
6. VALUE POTENTIELLE : NON EVALUEE ICI, quel que soit le resultat.

====================================================================
ETAPE 2bis - TRANCHES FIGEES AVANT EXECUTION REELLE (point 8)
====================================================================
Dispersion (ecart-type des probabilites normalisees entre bookmakers,
en points de probabilite) : <0.5pt / 0.5-1.0pt / 1.0-2.0pt / >=2.0pt.
Ecart meilleure-pire cote (normalise, points de probabilite) :
faible (<5pts) / moderee (5-10pts) / elevee (>=10pts).
Ecart bookmaker individuel vs consensus : grille DEJA pre-enregistree en
E9 (`market_engine.anomaly`, seuils 0.05/0.10), reutilisee sans
modification.
Grille de verdict (hypothese centrale point 3, identique a E12 pour une
terminologie coherente, REUTILISEE sans modification) : demontree
statistiquement / contradictoire / directionnelle mais non demontree /
absence de preuve.

====================================================================
ETAPE 2ter - MARCHE A 2 ISSUES : selection canonique OBLIGATOIRE
====================================================================
Pour l'Over/Under 2.5 (2 issues STRICTEMENT complementaires), P(Under) =
1 - P(Over) pour chaque bookmaker et outcome(Under) = 1 - outcome(Over) :
regrouper les deux lignes dans une meme table agregee est DEGENERE (le
biais agrege est force a EXACTEMENT 0 par construction algebrique, une
comparaison de Brier appariee duplique exactement chaque observation).
Seule la selection canonique "Over" (deja la priorite absolue du
protocole, meme convention que E10/E11/E12) est donc retenue pour toute
table agregee sur ce marche - decision STRUCTURELLE prise avant toute
observation reelle (cf. `restrict_to_canonical_selection`), jamais un
choix de seuil post-hoc. Le 1X2 (3 issues) n'a pas cette degenerescence
(verifie empiriquement : p_moyen et freq_reelle y different legerement
par tranche) et reste pool sur H/D/A sans restriction.

Usage:
    python scripts/run_stage22_e13_multi_bookmaker_dispersion.py
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.calibration_engine.significance import (  # noqa: E402
    paired_bootstrap_test,
    two_sample_bootstrap_test,
)
from sys_foot_quant.common.logging import get_logger  # noqa: E402
from sys_foot_quant.data_engine.market_odds.football_data_loader import (  # noqa: E402
    BOOKMAKERS_1X2,
    OVER_UNDER_25_BOOKMAKERS,
)
from sys_foot_quant.data_engine.market_odds.multi_bookmaker_odds import MultiBookmakerMatchRecord  # noqa: E402
from sys_foot_quant.market_engine.anomaly import (  # noqa: E402
    CLOSE_TO_CONSENSUS,
    MARKED_GAP,
    NOTABLE_GAP,
    classify_gap,
)
from sys_foot_quant.market_engine.arbitrage import detect_mathematical_arbitrage  # noqa: E402
from sys_foot_quant.market_engine.consensus import compute_consensus  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_MIN_N = 30  # identique a E5/E9/E10/E11/E12
_N_RESAMPLES = 10_000
_SEED = 0

# Tranches FIGEES AVANT EXECUTION REELLE (point 8) - jamais recalculees
# a partir des donnees observees.
_DISPERSION_EDGES = [0.0, 0.005, 0.010, 0.020, np.inf]
_DISPERSION_LABELS = ["<0.5pt", "0.5-1.0pt", "1.0-2.0pt", ">=2.0pt"]

_SPREAD_EDGES = [0.0, 0.05, 0.10, np.inf]
_SPREAD_LABELS = ["faible (<5pts)", "moderee (5-10pts)", "elevee (>=10pts)"]

_GAP_LABELS = [CLOSE_TO_CONSENSUS, NOTABLE_GAP, MARKED_GAP]

_STAGE18_PATH = Path(__file__).resolve().parent / "run_stage18_e9_multi_bookmaker_market_layer.py"
_STAGE21_PATH = Path(__file__).resolve().parent / "run_stage21_e12_reliability_price_gap_intersection.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_e9():
    return _load(_STAGE18_PATH, "run_stage18_e9_multi_bookmaker_market_layer")


def _load_e12():
    return _load(_STAGE21_PATH, "run_stage21_e12_reliability_price_gap_intersection")


# --------------------------------------------------------------------------
# ETAPE 1 - inventaire direct des colonnes brutes (jamais une hypothese)
# --------------------------------------------------------------------------


def raw_over_under_column_inventory(csv_path: Path) -> dict:
    """Inspecte l'en-tete BRUT du fichier (jamais les donnees deja
    parsees) pour lister precisement quels bookmakers publient une
    colonne Over/Under non-cloture - ne suppose rien."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        header = next(csv.reader(f))
    header_set = set(header)
    ou_cols = sorted(c for c in header_set if (">2.5" in c or "<2.5" in c) and "C>" not in c and "C<" not in c)
    bookmakers = sorted({c.split(">")[0].split("<")[0] for c in ou_cols})
    return {"ou_columns_non_closing": ou_cols, "bookmakers_with_ou_column": bookmakers}


# --------------------------------------------------------------------------
# ETAPE 3 - construction generique du corpus (match, selection) avec
# dispersion - reutilisable pour le 1X2 ET l'Over/Under 2.5.
# --------------------------------------------------------------------------


def build_result_lookup(stage8_module) -> dict[str, tuple[int, int]]:
    """match_id -> (buts domicile, buts exterieur) - meme convention de
    parcours que `build_decision_time_lookup` (E8), reutilisee ici pour
    le RESULTAT plutot que le decision_time."""
    out: dict[str, tuple[int, int]] = {}
    for season, leagues in stage8_module._SEASONS.items():
        for name in leagues:
            for r in stage8_module._load_records(name, season):
                out[r.match_id] = (r.home_goals, r.away_goals)
    return out


def _outcome_by_selection_1x2(home_goals: int, away_goals: int) -> dict[str, float]:
    return {
        "H": float(home_goals > away_goals),
        "D": float(home_goals == away_goals),
        "A": float(home_goals < away_goals),
    }


def _outcome_by_selection_over_under_25(home_goals: int, away_goals: int) -> dict[str, float]:
    is_over = float(home_goals + away_goals > 2.5)
    return {"Over": is_over, "Under": 1.0 - is_over}


def build_dispersion_dataframe(
    e9_module,
    records: list[MultiBookmakerMatchRecord],
    result_lookup: dict[str, tuple[int, int]],
    odds_attr: str,
    outcome_fn,
) -> pd.DataFrame:
    """Une ligne par (match, selection) disposant d'AU MOINS 2
    bookmakers normalises - jamais une observation individuelle
    inventee. ``odds_attr`` in {"odds_1x2", "odds_over_under_2_5"}.
    `best_book_prob` conservee separement pour la comparaison
    consensus-vs-bookmaker-de-reference-seul (point 7)."""
    reference_bookmaker = "B365"
    rows = []
    for r in records:
        result = result_lookup.get(r.match_id)
        if result is None:
            continue
        outcome_by_sel = outcome_fn(*result)
        normalized = e9_module.normalized_probs_by_selection(getattr(r, odds_attr))
        for sel, probs in normalized.items():
            if len(probs) < 2:
                continue
            consensus = compute_consensus(probs)
            rows.append(
                {
                    "match_id": r.match_id,
                    "league": r.league,
                    "season": r.season,
                    "selection": sel,
                    "n_bookmakers": consensus["n_bookmakers"],
                    "consensus_mean": consensus["mean"],
                    "consensus_median": consensus["median"],
                    "consensus_min": consensus["min"],
                    "consensus_max": consensus["max"],
                    "dispersion_std": consensus["std"],
                    "best_worst_spread": consensus["max"] - consensus["min"],
                    "reference_prob": probs.get(reference_bookmaker, float("nan")),
                    "outcome": outcome_by_sel[sel],
                }
            )
    return pd.DataFrame(rows)


def build_individual_vs_consensus_dataframe(
    e9_module,
    records: list[MultiBookmakerMatchRecord],
    result_lookup: dict[str, tuple[int, int]],
    odds_attr: str,
    outcome_fn,
) -> pd.DataFrame:
    """Une ligne par (match, selection, bookmaker) disposant d'un
    consensus (>=2 bookmakers) - mesure si l'ecart d'UN bookmaker au
    consensus est associe a sa PROPRE fiabilite (point 6)."""
    rows = []
    for r in records:
        result = result_lookup.get(r.match_id)
        if result is None:
            continue
        outcome_by_sel = outcome_fn(*result)
        normalized = e9_module.normalized_probs_by_selection(getattr(r, odds_attr))
        for sel, probs in normalized.items():
            if len(probs) < 2:
                continue
            consensus = compute_consensus(probs)
            for bk, p in probs.items():
                gap = p - consensus["mean"]
                rows.append(
                    {
                        "match_id": r.match_id,
                        "selection": sel,
                        "bookmaker": bk,
                        "p_individual": p,
                        "gap_vs_consensus": gap,
                        "gap_category": classify_gap(gap),
                        "outcome": outcome_by_sel[sel],
                    }
                )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# ETAPE 2bis - classification (PURE, jamais dependante de l'issue)
# --------------------------------------------------------------------------


def restrict_to_canonical_selection(df: pd.DataFrame, selection: str) -> pd.DataFrame:
    """Pour un marche a EXACTEMENT 2 issues strictement complementaires
    (Over/Under 2.5) : pour chaque bookmaker, P(Under) = 1 - P(Over), donc
    dispersion_std et best_worst_spread sont IDENTIQUES pour Over et
    Under (une translation x -> 1-x preserve l'ecart-type et l'etendue),
    et outcome(Under) = 1 - outcome(Over). Regrouper les deux lignes dans
    une meme table agregee est donc DEGENERE, pas neutre : pour toute
    tranche contenant des paires Over/Under completes, le biais agrege
    (freq_reelle - p_moyen) vaut EXACTEMENT 0 par construction algebrique
    (les deux lignes s'annulent), quelle que soit la vraie qualite de
    calibration - un resultat totalement non-informatif plutot qu'une
    absence de preuve reelle. Une comparaison de Brier appariee sur les
    deux lignes duplique aussi exactement chaque observation ((a-b)^2
    est invariant par x -> 1-x), gonflant artificiellement n sans ajouter
    d'information independante. Seule la selection canonique (deja la
    priorite du protocole - identique a la convention E10/E11/E12 qui
    n'a jamais construit qu'une probabilite "Over 2.5") est donc retenue
    pour toute table agregee sur un marche a 2 issues - decision
    structurelle, prise AVANT observation des resultats reels, jamais un
    choix de seuil post-hoc (point 8)."""
    if df.empty:
        return df
    return df[df["selection"] == selection].reset_index(drop=True)


def classify_dispersion(std: float) -> str:
    for lo, hi, label in zip(_DISPERSION_EDGES[:-1], _DISPERSION_EDGES[1:], _DISPERSION_LABELS):
        if lo <= std < hi:
            return label
    raise AssertionError(f"std={std} hors de toute tranche.")


def classify_spread(spread: float) -> str:
    for lo, hi, label in zip(_SPREAD_EDGES[:-1], _SPREAD_EDGES[1:], _SPREAD_LABELS):
        if lo <= spread < hi:
            return label
    raise AssertionError(f"spread={spread} hors de toute tranche.")


# --------------------------------------------------------------------------
# ETAPE 3/4/6 - table de calibration generique par categorie (reutilisee
# pour dispersion, ecart meilleure-pire cote, et ecart individuel-consensus)
# --------------------------------------------------------------------------


def calibration_by_category_table(
    df: pd.DataFrame, bin_col: str, labels: list[str], predicted_col: str, outcome_col: str = "outcome", min_n: int = _MIN_N
) -> pd.DataFrame:
    rows = []
    for label in labels:
        mask = (df[bin_col] == label).to_numpy()
        n = int(mask.sum())
        if n == 0:
            rows.append(
                {
                    "categorie": label, "n": 0, "p_moyen": float("nan"), "freq_reelle": float("nan"),
                    "biais": float("nan"), "biais_ic95_low": float("nan"), "biais_ic95_high": float("nan"),
                    "brier": float("nan"), "log_loss": float("nan"), "insuffisant": True,
                }
            )
            continue
        p = df.loc[mask, predicted_col].to_numpy()
        y = df.loc[mask, outcome_col].to_numpy()
        eps = 1e-12
        logloss = float(np.mean(-(y * np.log(np.clip(p, eps, 1 - eps)) + (1 - y) * np.log(np.clip(1 - p, eps, 1 - eps)))))
        diffs = y - p
        boot = (
            paired_bootstrap_test(diffs, n_resamples=_N_RESAMPLES, seed=_SEED)
            if n >= 2
            else {"ci_low": float("nan"), "ci_high": float("nan")}
        )
        rows.append(
            {
                "categorie": label,
                "n": n,
                "p_moyen": float(p.mean()),
                "freq_reelle": float(y.mean()),
                "biais": float(y.mean() - p.mean()),
                "biais_ic95_low": boot["ci_low"],
                "biais_ic95_high": boot["ci_high"],
                "brier": float(np.mean((p - y) ** 2)),
                "log_loss": logloss,
                "insuffisant": n < min_n,
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# ETAPE 3 - hypothese centrale : la dispersion elevee coincide-t-elle avec
# une pire calibration du consensus ?
# --------------------------------------------------------------------------


def test_high_dispersion_worse_calibrated(df: pd.DataFrame, e12_module) -> dict:
    """`two_sample_bootstrap_test` (REUTILISE) sur le carre de l'erreur du
    consensus entre le groupe HAUTE dispersion (tranches 1.0-2.0pt et
    >=2.0pt POOLEES) et le groupe BASSE dispersion (tranches <0.5pt et
    0.5-1.0pt POOLEES) - regroupement FIGE avant execution, jamais choisi
    apres observation. Verdict reutilise d'E12 (meme grille a 4 niveaux)."""
    low = df[df["dispersion_std"] < _DISPERSION_EDGES[2]]
    high = df[df["dispersion_std"] >= _DISPERSION_EDGES[2]]
    if len(low) < 2 or len(high) < 2:
        return {"n_low": len(low), "n_high": len(high), "boot": None, "verdict": "absence de preuve (donnees insuffisantes)"}
    sq_err_low = (low["consensus_mean"] - low["outcome"]) ** 2
    sq_err_high = (high["consensus_mean"] - high["outcome"]) ** 2
    boot = two_sample_bootstrap_test(sq_err_high.to_numpy(), sq_err_low.to_numpy(), n_resamples=_N_RESAMPLES, seed=_SEED)
    return {"n_low": len(low), "n_high": len(high), "boot": boot, "verdict": e12_module.classify_hypothesis_verdict(boot)}


# --------------------------------------------------------------------------
# ETAPE 7 - le consensus apporte-t-il quelque chose que le bookmaker de
# reference seul n'apporte pas ?
# --------------------------------------------------------------------------


def compare_consensus_vs_reference_alone(df: pd.DataFrame) -> dict | None:
    """`paired_bootstrap_test` (REUTILISE) sur diff = Brier(reference seul) -
    Brier(consensus), memes (match, selection) - jamais un panel different."""
    sub = df.dropna(subset=["reference_prob"])
    if len(sub) < 2:
        return None
    brier_reference = (sub["reference_prob"] - sub["outcome"]) ** 2
    brier_consensus = (sub["consensus_mean"] - sub["outcome"]) ** 2
    diffs = (brier_reference - brier_consensus).to_numpy()
    boot = paired_bootstrap_test(diffs, n_resamples=_N_RESAMPLES, seed=_SEED)
    return {"n": len(sub), "boot": boot}


def compare_model_vs_ou_consensus(ou_over_df: pd.DataFrame, model_probs: dict[str, float]) -> dict | None:
    """`paired_bootstrap_test` (REUTILISE) sur diff = Brier(modele E8
    walk-forward) - Brier(consensus O/U B365+P), memes matchs (selection
    "Over" uniquement, intersection avec le split TEST d'E8)."""
    sub = ou_over_df[ou_over_df["selection"] == "Over"].copy()
    sub["p_model"] = sub["match_id"].map(model_probs)
    sub = sub.dropna(subset=["p_model"])
    if len(sub) < 2:
        return None
    brier_model = (sub["p_model"] - sub["outcome"]) ** 2
    brier_consensus = (sub["consensus_mean"] - sub["outcome"]) ** 2
    diffs = (brier_model - brier_consensus).to_numpy()
    boot = paired_bootstrap_test(diffs, n_resamples=_N_RESAMPLES, seed=_SEED)
    return {"n": len(sub), "boot": boot}


# --------------------------------------------------------------------------
# ETAPE 5 - arbitrage mathematique generique (detection HISTORIQUE pure)
# --------------------------------------------------------------------------


def arbitrage_report(records: list[MultiBookmakerMatchRecord], odds_attr: str) -> dict:
    n_evaluable = 0
    n_positive = 0
    margins = []
    for r in records:
        odds = getattr(r, odds_attr)
        if any(not by_bk for by_bk in odds.values()):
            continue  # au moins une selection sans aucun bookmaker -> non evaluable
        n_evaluable += 1
        result = detect_mathematical_arbitrage(odds)
        margins.append(result["arbitrage_margin"])
        if result["is_mathematical_arbitrage"]:
            n_positive += 1
    return {
        "n_matches": len(records),
        "n_evaluable": n_evaluable,
        "n_arbitrage_positive": n_positive,
        "mean_margin": float(np.mean(margins)) if margins else float("nan"),
    }


def _print_table(label: str, table: pd.DataFrame) -> None:
    typer.echo(f"  -- {label} --")
    for _, r in table.iterrows():
        flag = " [INSUFFISANT n<30]" if r["insuffisant"] else ""
        typer.echo(
            f"    {r['categorie']:<20} n={int(r['n']):<5} p_moyen={r['p_moyen']:.4f} freq_reelle={r['freq_reelle']:.4f} "
            f"biais={r['biais']:+.4f} IC95%=[{r['biais_ic95_low']:+.4f},{r['biais_ic95_high']:+.4f}] "
            f"Brier={r['brier']:.4f} logloss={r['log_loss']:.4f}{flag}"
        )


def _run_dispersion_block(label: str, df: pd.DataFrame, e12_module) -> None:
    typer.echo(f"===== {label} =====")
    typer.echo(f"Instances (match, selection) avec >=2 bookmakers : {len(df)}")
    if df.empty:
        typer.echo("  Aucune instance multi-bookmaker - analyses non evaluables.\n")
        return

    df["dispersion_category"] = df["dispersion_std"].apply(classify_dispersion)
    df["spread_category"] = df["best_worst_spread"].apply(classify_spread)

    typer.echo("--- ETAPE 3/4 : calibration par tranche de DISPERSION (discrimination/calibration) ---")
    _print_table("Dispersion (ecart-type entre bookmakers)", calibration_by_category_table(df, "dispersion_category", _DISPERSION_LABELS, "consensus_mean"))
    result = test_high_dispersion_worse_calibrated(df, e12_module)
    if result["boot"] is None:
        typer.echo(f"  Test central (haute vs basse dispersion) : {result['verdict']}\n")
    else:
        b = result["boot"]
        typer.echo(
            f"  Test central : n_haute={result['n_high']} n_basse={result['n_low']} "
            f"diff_erreur_carree(haute-basse) IC95%=[{b['ci_low']:+.4f},{b['ci_high']:+.4f}] p={b['p_value']:.4f}"
        )
        typer.echo(f"  -> VERDICT : {result['verdict']}\n")

    typer.echo("--- ETAPE 6a : calibration par ECART MEILLEURE-PIRE COTE (price disagreement) ---")
    _print_table("Ecart meilleure-pire cote", calibration_by_category_table(df, "spread_category", _SPREAD_LABELS, "consensus_mean"))
    typer.echo("")

    typer.echo("--- ETAPE 7 : le consensus apporte-t-il quelque chose que le bookmaker de reference seul n'apporte pas ? ---")
    cmp_result = compare_consensus_vs_reference_alone(df)
    if cmp_result is None:
        typer.echo("  Donnees insuffisantes.\n")
    else:
        b = cmp_result["boot"]
        typer.echo(
            f"  n={cmp_result['n']} diff_Brier(reference_seul - consensus) IC95%=[{b['ci_low']:+.4f},{b['ci_high']:+.4f}] p={b['p_value']:.4f}\n"
        )


@app.command()
def main() -> None:
    typer.echo("=== E13 : information de dispersion multi-bookmakers et arbitrage mathematique ===")
    typer.echo(
        "poisson_simple, dixon_coles et xg_model INCHANGES. Aucune nouvelle calibration, aucun "
        "tuning, aucune strategie de pari, aucun ROI/Kelly/staking. PRIORITE ABSOLUE : Over/Under.\n"
    )

    e9 = _load_e9()
    e12 = _load_e12()
    e8 = e9._load_e8()
    e7 = e8._load_e7()
    stage10 = e7._load_stage10()
    stage8 = stage10._load_stage8()

    typer.echo("--- ETAPE 1 : inventaire precis (inspection directe des six fichiers) ---")
    fd_dir = Path("research/market_odds/football_data/runs")
    for csv_path in sorted(fd_dir.glob("*.csv")):
        inv = raw_over_under_column_inventory(csv_path)
        typer.echo(f"  {csv_path.name:20s} bookmakers Over/Under (colonnes non-cloture) : {inv['bookmakers_with_ou_column']}")
    typer.echo(f"  Bookmakers 1X2 lus par le loader (BOOKMAKERS_1X2) : {list(BOOKMAKERS_1X2)}")
    typer.echo(f"  Bookmakers Over/Under 2.5 lus par le loader (OVER_UNDER_25_BOOKMAKERS) : {list(OVER_UNDER_25_BOOKMAKERS)}")
    typer.echo(
        "  CORRECTION : Pinnacle (colonne P) publie aussi l'Over/Under 2.5 - deux bookmakers nommes "
        "existent reellement sur ce marche (B365, P). Dispersion/consensus/arbitrage y sont evaluables.\n"
    )

    records = e9.load_all_multi_bookmaker_records()
    result_lookup = build_result_lookup(stage8)
    typer.echo(f"Corpus multi-bookmaker exploitable (E9) : {len(records)} matchs\n")

    for market_label, odds_attr, outcome_fn, coverage_market, canonical_selection in (
        ("OVER/UNDER 2.5 (priorite)", "odds_over_under_2_5", _outcome_by_selection_over_under_25, "over_under_2_5", "Over"),
        ("1X2 (secondaire)", "odds_1x2", _outcome_by_selection_1x2, "1x2", None),
    ):
        coverage = e9._coverage_report(records, coverage_market)
        typer.echo(f"--- Couverture {market_label} (information descriptive) ---")
        typer.echo(f"  Bookmakers observes : {coverage['bookmakers']}")
        for bk, n in sorted(coverage["coverage_by_bookmaker"].items()):
            typer.echo(f"    {bk:6s} couverture = {n}/{coverage['n_matches']} ({100 * n / coverage['n_matches']:.1f}%)")
        typer.echo("")

        if canonical_selection is not None:
            typer.echo(
                f"  NOTE METHODOLOGIQUE : marche a 2 issues strictement complementaires - seule la "
                f"selection canonique '{canonical_selection}' est retenue pour les tables agregees "
                f"(Under porte EXACTEMENT la meme information ; les regrouper forcerait un biais "
                f"agrege nul par construction algebrique, pas un vrai resultat de calibration).\n"
            )

        df = build_dispersion_dataframe(e9, records, result_lookup, odds_attr, outcome_fn)
        if canonical_selection is not None:
            df = restrict_to_canonical_selection(df, canonical_selection)
        _run_dispersion_block(market_label, df, e12)

        df_indiv = build_individual_vs_consensus_dataframe(e9, records, result_lookup, odds_attr, outcome_fn)
        if canonical_selection is not None:
            df_indiv = restrict_to_canonical_selection(df_indiv, canonical_selection)
        typer.echo(f"--- ETAPE 6b : fiabilite INDIVIDUELLE d'un bookmaker selon son ecart au consensus ({market_label}) ---")
        if df_indiv.empty:
            typer.echo("  Aucune instance multi-bookmaker.\n")
        else:
            _print_table("Ecart bookmaker individuel vs consensus (grille E9)", calibration_by_category_table(df_indiv, "gap_category", _GAP_LABELS, "p_individual"))
            typer.echo("")

        typer.echo(f"--- ETAPE 5 : arbitrage mathematique {market_label} (detection HISTORIQUE, jamais une opportunite reelle) ---")
        arb = arbitrage_report(records, odds_attr)
        typer.echo(
            f"  {arb['n_arbitrage_positive']}/{arb['n_evaluable']} matchs evaluables avec somme des probabilites "
            f"inverses < 1 (marge moyenne = {arb['mean_margin']:+.4f})\n"
        )

    typer.echo("--- ETAPE 7 (suite) : le consensus O/U (B365+P) apporte-t-il quelque chose que la distribution E8 n'apporte pas ? ---")
    ou_df = build_dispersion_dataframe(e9, records, result_lookup, "odds_over_under_2_5", _outcome_by_selection_over_under_25)
    for model in ("poisson_simple", "xg_model"):
        model_probs = e9.model_over25_probs_walk_forward(e8, e7, model)
        cmp_result = compare_model_vs_ou_consensus(ou_df, model_probs)
        if cmp_result is None:
            typer.echo(f"  {model:<16} donnees insuffisantes.")
            continue
        b = cmp_result["boot"]
        typer.echo(
            f"  {model:<16} n={cmp_result['n']:<4} diff_Brier(modele_E8 - consensus_OU) IC95%=[{b['ci_low']:+.4f},{b['ci_high']:+.4f}] p={b['p_value']:.4f}"
        )
    typer.echo("  (dixon_coles reproduit exactement poisson_simple sur Over/Under - deja etabli en K/E7/E8)\n")

    typer.echo(
        "RESERVE : aucune conclusion de rentabilite. Anomalie de prix, arbitrage mathematique et value "
        "potentielle ne sont jamais confondus ni evalues au-dela de ce qui est explicitement mesure ci-dessus. "
        "Aucun ROI, Kelly, staking, seuil optimise sur le resultat. poisson_simple, dixon_coles et xg_model "
        "restent inchanges."
    )
    typer.echo("\nARRET : E13 termine, conformement au protocole. Aucune experience E14 lancee automatiquement.")


if __name__ == "__main__":
    app()
