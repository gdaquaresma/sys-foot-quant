"""CLI : E16 - le mouvement du marche entre l'OUVERTURE et la CLOTURE
contient-il une information sur le resultat reel qui n'etait pas deja
contenue dans la cote d'OUVERTURE ? Teste separement pour le 1X2 et
l'Over/Under 2.5. Experience RETROSPECTIVE : la cloture n'est JAMAIS
utilisee comme feature d'une decision prise a l'ouverture.

`poisson_simple`, `dixon_coles` et `xg_model` ne sont PAS utilises ici
(protocole explicite : etudier le marche INDEPENDAMMENT du modele).
E7/E8/E14/E15 ne sont ni lus ni modifies. Aucune strategie de pari, aucun
ROI/Kelly/staking, aucune conclusion de rentabilite.

====================================================================
ETAPE 1 - INSPECTION PREALABLE ET AUDIT DES DONNEES (avant tout code)
====================================================================
- `football_data_loader.py` : etendu (voir ADR 0006, section "Extension
  realisee E16") pour lire les cotes de CLOTURE deja presentes dans les
  six fichiers sources (B365/BW/PS 1X2, B365/P Over/Under 2.5, WH/LB 1X2
  optionnelles) - AUCUNE colonne inventee, verifie colonne par colonne
  avant extension. Couverture constatee (jamais supposee) : B365
  OUVERTURE ET CLOTURE 100% completes sur les 2132 matchs (seul
  bookmaker dans ce cas) ; BW/PS/P cloture 75-81% completes (legerement
  inferieure a leur ouverture respective, jamais superieure). B365 est
  donc le candidat PRIMAIRE (couverture totale des deux cotes) ; PS sert
  UNIQUEMENT de verification secondaire (etape 9), jamais de conclusion
  principale.
- `data_engine/market_odds/matching.py` (`build_understat_keys`,
  `match_league_season`) et `time_resolution.py`
  (`conservative_knowledge_time_utc`, `AmbiguousCollectionWindowError`) -
  REUTILISES SANS MODIFICATION, EXACTEMENT le meme mecanisme
  d'appariement et de point-in-time que `multi_bookmaker_odds.py` (E9) -
  jamais reimplemente differemment. `multi_bookmaker_odds.py` lui-meme
  n'expose PAS les cotes de cloture (perimetre volontairement limite a
  l'ouverture, jamais modifie ici) - une nouvelle fonction locale a CE
  script (`build_movement_dataset`) mirrors EXACTEMENT sa logique
  d'exclusion (B365 1X2 ouverture complet, jour non ambigu, PIT valide)
  en y ajoutant simplement la capture des cotes de cloture.
- `market_engine.overround.remove_overround_proportional` - REUTILISE
  SANS MODIFICATION pour retirer la marge par cote (ouverture ET
  cloture, jamais une moyenne des deux).
- `calibration_engine.significance.paired_bootstrap_test` - REUTILISE
  SANS MODIFICATION pour tous les IC95%.
- E11 (`calibration_slope_intercept`) etudiee mais NON reutilisee
  directement : sa forme (sigmoid(a+b*logit(p))) est generalisee ICI a un
  nombre arbitraire de covariables (logit(p_ouverture), mouvement,
  logit(p_cloture)) - une nouvelle fonction generique est ecrite dans CE
  script plutot que d'etendre E11.

====================================================================
ETAPE 2bis - DEFINITION EXACTE DU MOUVEMENT (figee avant execution)
====================================================================
Pour chaque selection d'un marche (H/D/A pour le 1X2, Over pour l'O/U -
Under exclu, degenerescence complementaire deja demontree en E13) :
    movement_abs  = cote_cloture - cote_ouverture
    movement_rel  = movement_abs / cote_ouverture
    prob_*_raw    = 1/cote (implicite BRUTE, PAS ajustee de la marge)
    prob_*_norm   = probabilite normalisee (marge retiree PAR COTE,
                    `remove_overround_proportional`, jamais une moyenne)
    movement_prob = prob_cloture_norm - prob_ouverture_norm (mesure
                    PRIMAIRE utilisee pour tous les tests statistiques -
                    la version BRUTE, moins rigoureuse car elle inclut la
                    marge, est rapportee separement a titre descriptif
                    uniquement, jamais utilisee pour un test)

====================================================================
ETAPE 2ter - MODELES COMPARES (figes avant execution, jamais choisis
apres observation des resultats)
====================================================================
    O   (ouverture seule)      : p = prob_ouverture_norm - ZERO parametre
    C   (cloture seule)        : p = prob_cloture_norm - ZERO parametre -
                                  RETROSPECTIF UNIQUEMENT
    M   (mouvement seul)       : p = sigmoid(a + b*movement_prob) -
                                  regression logistique a 2 parametres,
                                  walk-forward
    O+M (ouverture+mouvement)  : p = sigmoid(a + b*logit(p_O) +
                                  c*movement_prob) - 3 parametres,
                                  walk-forward - TEST CENTRAL (point 6)
    O+C (ouverture+cloture)    : p = sigmoid(a + b*logit(p_O) +
                                  c*logit(p_C)) - 3 parametres,
                                  walk-forward - RETROSPECTIF UNIQUEMENT
Tous les modeles a parametres (M, O+M, O+C) sont ajustes en FENETRE
GLISSANTE EXPANSIVE : pour chaque match evalue m (trie par
`decision_time`, PUIS uniquement), les parametres sont ajustes
EXCLUSIVEMENT sur les matchs dont `decision_time` est strictement
anterieur - jamais le match evalue, jamais un match posterieur - meme
principe que `attach_walk_forward_scale` (E8) et
`walk_forward_recalibrate` (E14), applique ici a une regression
logistique generique. Regle d'exclusion PRE-ENREGISTREE (identique en
esprit a E8/E14) : un match est exclu si moins de `_MIN_TRAIN=30` matchs
anterieurs disposent des covariables necessaires.

====================================================================
ETAPE 5 - TRANCHES D'AMPLITUDE (FIGEES avant execution, sur
|movement_prob| normalise, jamais choisies pour produire un resultat)
====================================================================
    quasi nul : <1pt (0.01)
    petit     : 1-3pt (0.01-0.03)
    moyen     : 3-6pt (0.03-0.06)
    gros      : >=6pt (0.06)

====================================================================
ETAPE 11 - HYPOTHESES PRIMAIRES ET CORRECTION MULTIPLE (figees avant
execution)
====================================================================
4 hypotheses PRIMAIRES, seules soumises a une correction de Holm-Bonferroni
conjointe (alpha=0.05) : le test central O+M vs O (point 6), pour les 4
cibles Home / Draw / Away / Over 2.5. Toute autre comparaison (M seul,
O+C retrospectif, decoupes par championnat/saison/tranche/bookmaker) est
EXPLORATOIRE - rapportee mais jamais utilisee seule pour declarer un
signal "demontre".

Usage:
    python scripts/run_stage25_e16_market_movement_information.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import typer
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test  # noqa: E402
from sys_foot_quant.common.logging import get_logger  # noqa: E402
from sys_foot_quant.data_engine.market_odds.economic_dataset import DECISION_OFFSET_HOURS  # noqa: E402
from sys_foot_quant.data_engine.market_odds.football_data_loader import FootballDataMatchRecord, load_football_data_csv  # noqa: E402
from sys_foot_quant.data_engine.market_odds.matching import build_understat_keys, match_league_season  # noqa: E402
from sys_foot_quant.data_engine.market_odds.time_resolution import (  # noqa: E402
    AmbiguousCollectionWindowError,
    conservative_knowledge_time_utc,
)
from sys_foot_quant.market_engine.overround import remove_overround_proportional  # noqa: E402

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

_MIN_TRAIN = 30  # regle d'exclusion PRE-ENREGISTREE, meme convention que E8/E14
_N_RESAMPLES = 10_000
_SEED = 0

_AMPLITUDE_EDGES = [0.0, 0.01, 0.03, 0.06, np.inf]
_AMPLITUDE_LABELS = ["quasi nul (<1pt)", "petit (1-3pt)", "moyen (3-6pt)", "gros (>=6pt)"]


# --------------------------------------------------------------------------
# ETAPE 1 - construction du jeu de donnees ouverture+cloture (mirror EXACT
# de multi_bookmaker_odds.build_multi_bookmaker_dataset, cloture en plus).
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class MovementMatchRecord:
    match_id: str
    league: str
    season: str
    kickoff_utc: datetime
    decision_time_utc: datetime
    home_goals: int
    away_goals: int
    b365_open_1x2: dict[str, float]
    b365_close_1x2: dict[str, float] | None
    b365_open_ou: dict[str, float] | None
    b365_close_ou: dict[str, float] | None
    ps_open_1x2: dict[str, float] | None
    ps_close_1x2: dict[str, float] | None


def build_movement_dataset(
    league: str, season: str, understat_raw: list[dict], football_data_records: list[FootballDataMatchRecord]
) -> tuple[list[MovementMatchRecord], dict]:
    """Mirror EXACT de `multi_bookmaker_odds.build_multi_bookmaker_dataset`
    (memes exclusions : B365 1X2 ouverture complet, jour non ambigu, PIT
    valide) - capture EN PLUS les cotes de CLOTURE (jamais utilisees pour
    filtrer l'inclusion d'un match, exactement comme BW/PS/P a l'ouverture
    en E9/E13)."""
    understat_keys = build_understat_keys(understat_raw, league, season)
    matching_report = match_league_season(understat_keys, football_data_records, league, season)

    n_excluded_ambiguous_weekday = 0
    n_excluded_incomplete_b365 = 0
    n_excluded_pit_violation = 0
    records: list[MovementMatchRecord] = []
    for m in matching_report.matched:
        fd = m.football_data
        if not fd.has_complete_odds:
            n_excluded_incomplete_b365 += 1
            continue
        try:
            knowledge_time = conservative_knowledge_time_utc(m.understat.kickoff_utc)
        except AmbiguousCollectionWindowError:
            n_excluded_ambiguous_weekday += 1
            continue
        decision_time = m.understat.kickoff_utc - timedelta(hours=DECISION_OFFSET_HOURS)
        if not (knowledge_time <= decision_time):
            n_excluded_pit_violation += 1
            continue

        records.append(
            MovementMatchRecord(
                match_id=m.understat.match_id,
                league=league,
                season=season,
                kickoff_utc=m.understat.kickoff_utc,
                decision_time_utc=decision_time,
                home_goals=fd.home_goals,
                away_goals=fd.away_goals,
                b365_open_1x2={"H": fd.b365_home, "D": fd.b365_draw, "A": fd.b365_away},
                b365_close_1x2=(
                    {"H": fd.b365_close_home, "D": fd.b365_close_draw, "A": fd.b365_close_away}
                    if fd.has_complete_close_odds
                    else None
                ),
                b365_open_ou=(
                    {"Over": fd.b365_over_2_5, "Under": fd.b365_under_2_5} if fd.has_complete_over_under_2_5_odds else None
                ),
                b365_close_ou=(
                    {"Over": fd.b365_close_over_2_5, "Under": fd.b365_close_under_2_5}
                    if fd.has_complete_close_over_under_2_5_odds
                    else None
                ),
                ps_open_1x2=({"H": fd.ps_home, "D": fd.ps_draw, "A": fd.ps_away} if fd.has_complete_ps_odds else None),
                ps_close_1x2=(
                    {"H": fd.ps_close_home, "D": fd.ps_close_draw, "A": fd.ps_close_away}
                    if fd.has_complete_ps_close_odds
                    else None
                ),
            )
        )

    counts = {
        "n_understat": matching_report.n_understat,
        "n_matched": matching_report.n_matched,
        "n_excluded_ambiguous_weekday": n_excluded_ambiguous_weekday,
        "n_excluded_incomplete_b365": n_excluded_incomplete_b365,
        "n_excluded_pit_violation": n_excluded_pit_violation,
        "n_exploitable": len(records),
    }
    return records, counts


def load_all_movement_records() -> tuple[list[MovementMatchRecord], dict]:
    all_records: list[MovementMatchRecord] = []
    total_counts: dict[str, int] = {}
    for (league, season), (fd_name, us_name) in _DATASETS.items():
        fd_records = load_football_data_csv(_FD_DIR / fd_name, league=league, season=season)
        with open(_US_DIR / us_name) as f:
            us_raw = json.load(f)
        records, counts = build_movement_dataset(league, season, us_raw, fd_records)
        all_records.extend(records)
        for k, v in counts.items():
            total_counts[k] = total_counts.get(k, 0) + v
    return all_records, total_counts


# --------------------------------------------------------------------------
# ETAPE 1 - audit de couverture ouverture/cloture (purement descriptif).
# --------------------------------------------------------------------------


def coverage_audit(records: list[MovementMatchRecord]) -> dict:
    n = len(records)
    return {
        "n_matches": n,
        "b365_1x2_open": sum(1 for r in records if r.b365_open_1x2 is not None) / n,
        "b365_1x2_close": sum(1 for r in records if r.b365_close_1x2 is not None) / n,
        "b365_ou_open": sum(1 for r in records if r.b365_open_ou is not None) / n,
        "b365_ou_close": sum(1 for r in records if r.b365_close_ou is not None) / n,
        "ps_1x2_open": sum(1 for r in records if r.ps_open_1x2 is not None) / n,
        "ps_1x2_close": sum(1 for r in records if r.ps_close_1x2 is not None) / n,
    }


# --------------------------------------------------------------------------
# ETAPE 2 - construction du signal de mouvement (fonction PURE).
# --------------------------------------------------------------------------


def compute_market_movement(odds_open: dict[str, float], odds_close: dict[str, float]) -> dict[str, dict[str, float]]:
    """Pour chaque selection commune a `odds_open`/`odds_close` : cote,
    mouvement absolu/relatif, probabilite implicite BRUTE (1/cote,
    descriptif uniquement) et NORMALISEE (marge retiree PAR COTE,
    `remove_overround_proportional`, REUTILISE - mesure PRIMAIRE des tests
    statistiques) et leur mouvement respectif."""
    norm_open = remove_overround_proportional(odds_open)
    norm_close = remove_overround_proportional(odds_close)
    out: dict[str, dict[str, float]] = {}
    for sel in odds_open:
        o, c = odds_open[sel], odds_close[sel]
        out[sel] = {
            "odds_open": o,
            "odds_close": c,
            "movement_abs": c - o,
            "movement_rel": (c - o) / o,
            "prob_open_raw": 1.0 / o,
            "prob_close_raw": 1.0 / c,
            "movement_prob_raw": 1.0 / c - 1.0 / o,
            "prob_open_norm": norm_open[sel],
            "prob_close_norm": norm_close[sel],
            "movement_prob_norm": norm_close[sel] - norm_open[sel],
        }
    return out


# --------------------------------------------------------------------------
# ETAPE 2ter - regression logistique generique (fit walk-forward par
# fenetre expansive) - PURE, jamais un nouveau "modele de buts".
# --------------------------------------------------------------------------


def fit_logistic(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Ajuste beta par maximum de vraisemblance (regression logistique
    generique, X DEJA muni d'une colonne de biais si necessaire par
    l'appelant) - convexe et lisse, `BFGS` (gradient numerique) plutot que
    Nelder-Mead pour une convergence fiable au-dela de 2 parametres."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)

    def neg_log_lik(beta: np.ndarray) -> float:
        z = X @ beta
        return float(np.mean(np.logaddexp(0.0, -z) * y + np.logaddexp(0.0, z) * (1 - y)))

    beta0 = np.zeros(X.shape[1])
    res = minimize(neg_log_lik, beta0, method="BFGS")
    return res.x


def predict_logistic(beta: np.ndarray, X: np.ndarray) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    z = X @ beta
    return 1.0 / (1.0 + np.exp(-z))


def _safe_logit(p: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), eps, 1 - eps)
    return np.log(p / (1 - p))


def walk_forward_logistic(
    df: pd.DataFrame, build_covariates, min_train: int = _MIN_TRAIN
) -> np.ndarray:
    """Pour chaque ligne de `df` (deja triee par `decision_time`), ajuste
    la regression EXCLUSIVEMENT sur les lignes PRECEDENTES (index < i dans
    le tri chronologique - jamais la ligne elle-meme, jamais une ligne
    posterieure), puis predit sur la ligne courante. `build_covariates(df)
    -> (X, y)` construit les covariables ET la cible pour tout le
    DataFrame en une fois (jamais une fuite : seule la portion PASSEE de X
    est utilisee a chaque etape). Retourne un vecteur de predictions,
    `nan` pour les lignes avec moins de `min_train` antecedents."""
    X_all, y_all = build_covariates(df)
    n = len(df)
    preds = np.full(n, np.nan)
    for i in range(n):
        if i < min_train:
            continue
        beta = fit_logistic(X_all[:i], y_all[:i])
        preds[i] = predict_logistic(beta, X_all[i : i + 1])[0]
    return preds


# --------------------------------------------------------------------------
# ETAPE 3/4/6 - construction des 5 series de probabilite (O, C, M, O+M, O+C)
# pour UNE cible (selection) donnee, sur un DataFrame deja trie.
# --------------------------------------------------------------------------


def build_prediction_series(df: pd.DataFrame) -> dict[str, np.ndarray]:
    """`df` doit contenir les colonnes ``prob_open_norm``,
    ``prob_close_norm``, ``movement_prob_norm``, ``outcome`` - deja triees
    par `decision_time`. Retourne les 5 series de probabilite (memes
    lignes, `nan` la ou walk-forward est insuffisant)."""
    p_open = df["prob_open_norm"].to_numpy()
    p_close = df["prob_close_norm"].to_numpy()
    y = df["outcome"].to_numpy()

    def _cov_m(d: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        mv = d["movement_prob_norm"].to_numpy()
        X = np.column_stack([np.ones(len(d)), mv])
        return X, d["outcome"].to_numpy()

    def _cov_om(d: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        logit_o = _safe_logit(d["prob_open_norm"].to_numpy())
        mv = d["movement_prob_norm"].to_numpy()
        X = np.column_stack([np.ones(len(d)), logit_o, mv])
        return X, d["outcome"].to_numpy()

    def _cov_oc(d: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        logit_o = _safe_logit(d["prob_open_norm"].to_numpy())
        logit_c = _safe_logit(d["prob_close_norm"].to_numpy())
        X = np.column_stack([np.ones(len(d)), logit_o, logit_c])
        return X, d["outcome"].to_numpy()

    return {
        "O": p_open,
        "C": p_close,
        "M": walk_forward_logistic(df, _cov_m),
        "O+M": walk_forward_logistic(df, _cov_om),
        "O+C": walk_forward_logistic(df, _cov_oc),
        "y": y,
    }


# --------------------------------------------------------------------------
# ETAPE 3/4 - metriques (Brier, log loss, biais/calibration, IC95%).
# --------------------------------------------------------------------------


def evaluate_predictions(p: np.ndarray, y: np.ndarray) -> dict:
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = ~np.isnan(p)
    p, y = p[mask], y[mask]
    n = p.size
    if n == 0:
        return {"n": 0, "brier": float("nan"), "log_loss": float("nan"), "biais": float("nan")}
    eps = 1e-12
    logloss = float(np.mean(-(y * np.log(np.clip(p, eps, 1 - eps)) + (1 - y) * np.log(np.clip(1 - p, eps, 1 - eps)))))
    return {
        "n": n,
        "brier": float(np.mean((p - y) ** 2)),
        "log_loss": logloss,
        "p_moyen": float(p.mean()),
        "freq_reelle": float(y.mean()),
        "biais": float(y.mean() - p.mean()),
    }


def compare_brier_paired(p_a: np.ndarray, p_b: np.ndarray, y: np.ndarray) -> dict | None:
    """`paired_bootstrap_test` (REUTILISE) sur diff = Brier(a) - Brier(b),
    restreint aux lignes ou LES DEUX series sont non-nan (meme n, meme
    panel, jamais un a-plat)."""
    p_a = np.asarray(p_a, dtype=float)
    p_b = np.asarray(p_b, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = ~np.isnan(p_a) & ~np.isnan(p_b)
    if mask.sum() < 2:
        return None
    diffs = (p_a[mask] - y[mask]) ** 2 - (p_b[mask] - y[mask]) ** 2
    boot = paired_bootstrap_test(diffs, n_resamples=_N_RESAMPLES, seed=_SEED)
    return {"n": int(mask.sum()), "boot": boot}


# --------------------------------------------------------------------------
# ETAPE 5 - tranches d'amplitude (FIGEES, jamais choisies apres observation)
# --------------------------------------------------------------------------


def classify_amplitude(movement_prob_norm: float) -> str:
    abs_m = abs(movement_prob_norm)
    for lo, hi, label in zip(_AMPLITUDE_EDGES[:-1], _AMPLITUDE_EDGES[1:], _AMPLITUDE_LABELS):
        if lo <= abs_m < hi:
            return label
    raise AssertionError(f"movement={movement_prob_norm} hors de toute tranche.")


def amplitude_table(df: pd.DataFrame, min_n: int = _MIN_TRAIN) -> pd.DataFrame:
    cats = df["movement_prob_norm"].apply(classify_amplitude)
    rows = []
    for label in _AMPLITUDE_LABELS:
        mask = (cats == label).to_numpy()
        n = int(mask.sum())
        if n == 0:
            rows.append(
                {
                    "categorie": label, "n": 0, "brier_open": float("nan"), "brier_close": float("nan"),
                    "biais_open": float("nan"), "biais_close": float("nan"), "taux_reussite": float("nan"),
                    "diff_ic95_low": float("nan"), "diff_ic95_high": float("nan"), "insuffisant": True,
                }
            )
            continue
        p_o = df.loc[mask, "prob_open_norm"].to_numpy()
        p_c = df.loc[mask, "prob_close_norm"].to_numpy()
        y = df.loc[mask, "outcome"].to_numpy()
        diffs = (p_c - y) ** 2 - (p_o - y) ** 2
        boot = paired_bootstrap_test(diffs, n_resamples=_N_RESAMPLES, seed=_SEED) if n >= 2 else {"ci_low": float("nan"), "ci_high": float("nan")}
        rows.append(
            {
                "categorie": label,
                "n": n,
                "brier_open": float(np.mean((p_o - y) ** 2)),
                "brier_close": float(np.mean((p_c - y) ** 2)),
                "biais_open": float(y.mean() - p_o.mean()),
                "biais_close": float(y.mean() - p_c.mean()),
                "taux_reussite": float(y.mean()),
                "diff_ic95_low": boot["ci_low"],
                "diff_ic95_high": boot["ci_high"],
                "insuffisant": n < min_n,
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# ETAPE 10 - price discovery (jamais un "CLV" - aucune decision definie).
# --------------------------------------------------------------------------


def price_discovery_summary(df: pd.DataFrame) -> dict:
    mv = df["movement_prob_norm"].to_numpy()
    y = df["outcome"].to_numpy()
    moved_up = mv > 0
    moved_down = mv < 0
    significant = np.abs(mv) >= _AMPLITUDE_EDGES[1]  # >= 1pt, seuil FIGE (etape 5)
    directional_agreement = float(np.mean(y[moved_up])) if moved_up.any() else float("nan")
    directional_disagreement = float(np.mean(y[moved_down])) if moved_down.any() else float("nan")
    return {
        "n": len(df),
        "mean_abs_movement": float(np.mean(np.abs(mv))),
        "frac_significant_movement": float(np.mean(significant)),
        "frac_moved_toward_selection": float(np.mean(moved_up)),
        "freq_outcome_when_moved_toward": directional_agreement,
        "freq_outcome_when_moved_away": directional_disagreement,
    }


# --------------------------------------------------------------------------
# ETAPE 11 - correction de comparaisons multiples (Holm-Bonferroni, PURE).
# --------------------------------------------------------------------------


def holm_bonferroni(p_values: list[float], alpha: float = 0.05) -> list[bool]:
    """Retourne, pour chaque hypothese (MEME ORDRE que `p_values`), si elle
    est rejetee (True) sous la procedure sequentielle de Holm-Bonferroni -
    controle du taux d'erreur familial, moins conservateur qu'un Bonferroni
    simple mais toujours valide sans hypothese d'independance."""
    n = len(p_values)
    order = sorted(range(n), key=lambda i: p_values[i])
    rejected = [False] * n
    for rank, idx in enumerate(order):
        threshold = alpha / (n - rank)
        if p_values[idx] <= threshold:
            rejected[idx] = True
        else:
            break  # sequentiel : des que le seuil n'est plus franchi, on s'arrete
    return rejected


# --------------------------------------------------------------------------
# Construction du DataFrame par (marche, selection) - trie par decision_time.
# --------------------------------------------------------------------------


def build_selection_dataframe(records: list[MovementMatchRecord], market: str, selection: str) -> pd.DataFrame:
    """`market` in {"1x2", "ou25"}. Une ligne par match disposant de
    l'ouverture ET de la cloture COMPLETES pour B365 sur ce marche - jamais
    un match ou seule l'ouverture (ou seule la cloture) est disponible."""
    rows = []
    for r in records:
        if market == "1x2":
            odds_open, odds_close = r.b365_open_1x2, r.b365_close_1x2
            outcome = float((r.home_goals > r.away_goals) if selection == "H" else (r.home_goals == r.away_goals) if selection == "D" else (r.home_goals < r.away_goals))
        else:
            odds_open, odds_close = r.b365_open_ou, r.b365_close_ou
            outcome = float((r.home_goals + r.away_goals) > 2.5)  # selection == "Over" uniquement
        if odds_open is None or odds_close is None:
            continue
        mv = compute_market_movement(odds_open, odds_close)[selection]
        rows.append(
            {
                "match_id": r.match_id,
                "league": r.league,
                "season": r.season,
                "decision_time": r.decision_time_utc,
                **mv,
                "outcome": outcome,
            }
        )
    if not rows:
        return pd.DataFrame(columns=["match_id", "league", "season", "decision_time", "outcome"])
    df = pd.DataFrame(rows).sort_values("decision_time").reset_index(drop=True)
    return df


def build_ps_selection_dataframe(records: list[MovementMatchRecord], selection: str) -> pd.DataFrame:
    """Etape 9 - meme construction que `build_selection_dataframe` mais
    pour Pinnacle (1X2 uniquement, seul marche PS disponible)."""
    rows = []
    for r in records:
        if r.ps_open_1x2 is None or r.ps_close_1x2 is None:
            continue
        outcome = float((r.home_goals > r.away_goals) if selection == "H" else (r.home_goals == r.away_goals) if selection == "D" else (r.home_goals < r.away_goals))
        mv = compute_market_movement(r.ps_open_1x2, r.ps_close_1x2)[selection]
        rows.append({"match_id": r.match_id, "league": r.league, "season": r.season, "decision_time": r.decision_time_utc, **mv, "outcome": outcome})
    if not rows:
        return pd.DataFrame(columns=["match_id", "league", "season", "decision_time", "outcome"])
    return pd.DataFrame(rows).sort_values("decision_time").reset_index(drop=True)


def _print_zone(label: str, res: dict) -> None:
    typer.echo(f"    {label:<6} n={res['n']:<5} Brier={res['brier']:.4f} logloss={res['log_loss']:.4f} biais={res.get('biais', float('nan')):+.4f}")


@app.command()
def main() -> None:
    typer.echo("=== E16 : information contenue dans le mouvement de marche (ouverture -> cloture) ===")
    typer.echo(
        "poisson_simple, dixon_coles, xg_model NON UTILISES (marche etudie independamment du modele). "
        "E7/E8/E14/E15 non lus, non modifies. RETROSPECTIF - la cloture n'est jamais un feature "
        "d'ouverture. Aucun ROI/Kelly/staking, aucune strategie de pari.\n"
    )

    records, counts = load_all_movement_records()
    typer.echo("--- ETAPE 1 : construction et audit du corpus ---")
    for k, v in counts.items():
        typer.echo(f"  {k}: {v}")
    coverage = coverage_audit(records)
    typer.echo(f"  Couverture (sur {coverage['n_matches']} matchs exploitables B365 1X2 ouverture) :")
    for k, v in coverage.items():
        if k == "n_matches":
            continue
        typer.echo(f"    {k:<16} {100*v:.1f}%")
    typer.echo("")

    primary_p_values: list[tuple[str, float]] = []

    for market_label, market_key, selections in (("1X2", "1x2", ("H", "D", "A")), ("Over/Under 2.5", "ou25", ("Over",))):
        typer.echo(f"===== {market_label} =====")
        for selection in selections:
            typer.echo(f"--- Selection {selection} ---")
            df = build_selection_dataframe(records, market_key, selection)
            typer.echo(f"  n (ouverture ET cloture B365 completes) = {len(df)}")
            series = build_prediction_series(df)
            y = series["y"]

            typer.echo("  -- ETAPE 3/4 : Modeles O / C / M / O+M / O+C --")
            for name in ("O", "C", "M", "O+M", "O+C"):
                res = evaluate_predictions(series[name], y)
                _print_zone(name, res)

            typer.echo("  -- ETAPE 6 (coeur) : O+M apporte-t-il une info incrementale a O ? --")
            central = compare_brier_paired(series["O+M"], series["O"], y)
            if central:
                b = central["boot"]
                typer.echo(f"    n={central['n']} diff_Brier(O+M - O) IC95%=[{b['ci_low']:+.4f},{b['ci_high']:+.4f}] p={b['p_value']:.4f}")
                primary_p_values.append((f"{market_label}/{selection}", b["p_value"]))
            else:
                typer.echo("    donnees insuffisantes.")
                primary_p_values.append((f"{market_label}/{selection}", 1.0))

            typer.echo("  -- (descriptif) M apporte-t-il une info incrementale a O ? --")
            m_vs_o = compare_brier_paired(series["M"], series["O"], y)
            if m_vs_o:
                b = m_vs_o["boot"]
                typer.echo(f"    n={m_vs_o['n']} diff_Brier(M - O) IC95%=[{b['ci_low']:+.4f},{b['ci_high']:+.4f}] p={b['p_value']:.4f}")

            typer.echo("  -- RETROSPECTIF : O+C apporte-t-il une info incrementale a O ? (jamais decision-usable) --")
            oc_vs_o = compare_brier_paired(series["O+C"], series["O"], y)
            if oc_vs_o:
                b = oc_vs_o["boot"]
                typer.echo(f"    n={oc_vs_o['n']} diff_Brier(O+C - O) IC95%=[{b['ci_low']:+.4f},{b['ci_high']:+.4f}] p={b['p_value']:.4f}")

            typer.echo("  -- ETAPE 5 : tranches d'amplitude (FIGEES) --")
            at = amplitude_table(df)
            for _, r in at.iterrows():
                flag = " [INSUFFISANT n<30]" if r["insuffisant"] else ""
                typer.echo(
                    f"    {r['categorie']:<18} n={int(r['n']):<5} Brier_O={r['brier_open']:.4f} Brier_C={r['brier_close']:.4f} "
                    f"biais_O={r['biais_open']:+.4f} biais_C={r['biais_close']:+.4f} taux_reussite={r['taux_reussite']:.4f} "
                    f"diff_IC95%=[{r['diff_ic95_low']:+.4f},{r['diff_ic95_high']:+.4f}]{flag}"
                )

            typer.echo("  -- ETAPE 10 : price discovery (jamais un CLV, aucune decision definie) --")
            pd_summary = price_discovery_summary(df)
            typer.echo(
                f"    mouvement absolu moyen={pd_summary['mean_abs_movement']:.4f} "
                f"frac_mouvement_significatif(>=1pt)={pd_summary['frac_significant_movement']:.4f} "
                f"frac_mouvement_vers_selection={pd_summary['frac_moved_toward_selection']:.4f} "
                f"freq_reelle_si_mouvement_vers={pd_summary['freq_outcome_when_moved_toward']:.4f} "
                f"freq_reelle_si_mouvement_contre={pd_summary['freq_outcome_when_moved_away']:.4f}"
            )

            typer.echo("  -- ETAPE 8 (exploratoire) : robustesse par championnat --")
            for league in sorted(df["league"].unique()):
                sub = df[df["league"] == league].reset_index(drop=True)
                if len(sub) < _MIN_TRAIN + 10:
                    typer.echo(f"    {league:<16} n={len(sub)} insuffisant.")
                    continue
                sub_series = build_prediction_series(sub)
                cmp_league = compare_brier_paired(sub_series["O+M"], sub_series["O"], sub_series["y"])
                if cmp_league:
                    b = cmp_league["boot"]
                    typer.echo(f"    {league:<16} n={cmp_league['n']:<4} diff_Brier(O+M-O) IC95%=[{b['ci_low']:+.4f},{b['ci_high']:+.4f}]")

            typer.echo("  -- ETAPE 8 (exploratoire) : robustesse par saison --")
            for season in sorted(df["season"].unique()):
                sub = df[df["season"] == season].reset_index(drop=True)
                if len(sub) < _MIN_TRAIN + 10:
                    typer.echo(f"    {season:<10} n={len(sub)} insuffisant.")
                    continue
                sub_series = build_prediction_series(sub)
                cmp_season = compare_brier_paired(sub_series["O+M"], sub_series["O"], sub_series["y"])
                if cmp_season:
                    b = cmp_season["boot"]
                    typer.echo(f"    {season:<10} n={cmp_season['n']:<4} diff_Brier(O+M-O) IC95%=[{b['ci_low']:+.4f},{b['ci_high']:+.4f}]")

            if market_key == "1x2":
                typer.echo("  -- ETAPE 9 (exploratoire, secondaire) : meme test central avec Pinnacle (PS) --")
                df_ps = build_ps_selection_dataframe(records, selection)
                if len(df_ps) >= _MIN_TRAIN + 10:
                    series_ps = build_prediction_series(df_ps)
                    cmp_ps = compare_brier_paired(series_ps["O+M"], series_ps["O"], series_ps["y"])
                    if cmp_ps:
                        b = cmp_ps["boot"]
                        typer.echo(f"    PS n={cmp_ps['n']:<4} diff_Brier(O+M-O) IC95%=[{b['ci_low']:+.4f},{b['ci_high']:+.4f}] p={b['p_value']:.4f}")
                else:
                    typer.echo(f"    PS n={len(df_ps)} insuffisant.")
            typer.echo("")

    typer.echo("=== ETAPE 11 : correction de Holm-Bonferroni sur les 4 hypotheses PRIMAIRES (O+M vs O) ===")
    labels = [lbl for lbl, _ in primary_p_values]
    pvals = [p for _, p in primary_p_values]
    rejected = holm_bonferroni(pvals, alpha=0.05)
    for lbl, p, rej in zip(labels, pvals, rejected):
        typer.echo(f"  {lbl:<20} p={p:.4f} -> {'REJETEE (H0 rejetee, signal retenu)' if rej else 'NON REJETEE'}")

    typer.echo(
        "\nRESERVE : aucune conclusion de rentabilite. La cloture n'est jamais utilisee comme feature "
        "d'une decision a l'ouverture. E7/E8/E14/E15 et poisson_simple/dixon_coles/xg_model non "
        "modifies. Les decoupes par championnat/saison/bookmaker sont EXPLORATOIRES, jamais corrigees "
        "pour comparaisons multiples - seules les 4 hypotheses primaires ci-dessus le sont."
    )
    typer.echo("\nARRET : E16 termine, conformement au protocole. Aucune experience E17 lancee automatiquement.")


if __name__ == "__main__":
    app()
