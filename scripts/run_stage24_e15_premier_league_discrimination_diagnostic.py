"""CLI : E15 - diagnostic STRUCTUREL de l'absence de discrimination de
l'esperance de buts predite en Premier League, deja constatee 3 fois
(E4, E11, implicitement E10) sur une correlation quasi nulle/negative
espérance predite <-> total reel.

E15 est un DIAGNOSTIC PUR : aucun modele modifie, aucun hyperparametre
touche, aucune correction E7/E8 modifiee, aucune regle de production
creee. Aucune conclusion causale n'est tiree d'une simple correlation -
seulement un faisceau d'indices pour distinguer 5 explications possibles
(donnee/mapping, puissance, caracteristique distributionnelle reelle,
difference de calibration, absence reelle de signal).

====================================================================
ETAPE 0 - INSPECTION PREALABLE (avant tout code)
====================================================================
- stage8 (`run_stage8_diagnostic_total_goals_over_under.py`) : `_load_records`,
  `_SEASONS`, `_EXPECTED_MATCHES`, `_EXPECTED_TEAMS`, `build_total_goals_dataframe`
  - REUTILISES SANS MODIFICATION (`_load_records` execute deja
  `_verify_integrity`, qui echoue explicitement si le nombre de matchs/
  equipes/scores/xG attendu n'est pas respecte - deja un premier niveau
  d'audit, reconfirme ici avec des controles complementaires).
- stage10 (`run_stage10_over_under_recalibration.py`) :
  `build_calibration_and_test_sets` - REUTILISE SANS MODIFICATION, MEME
  perimetre de donnees que E4/E11 (point 9 de la consigne generale du
  projet : comparaison directe possible).
- E4 (`run_stage12_e4_expected_goals_discrimination.py`) :
  `regression_diagnostics`, `bootstrap_bias_and_mae`, `fixed_bin_table`,
  `quintile_table` - REUTILISES SANS MODIFICATION pour reproduire
  EXACTEMENT les chiffres deja publies avant toute nouvelle analyse
  (etape 2 du protocole).
- E11 (`run_stage20_e11_probability_reliability_mapping.py`) :
  `build_threshold_dataframe`, `calibration_table`,
  `calibration_slope_intercept`, `point_biserial_correlation`,
  `summarize_reliability` - REUTILISES SANS MODIFICATION pour reproduire
  la calibration/discrimination de la distribution CORRIGEE E7/E8 par
  championnat.
- `calibration_engine.decomposition.brier_decomposition` et
  `.significance.paired_bootstrap_test`/`two_sample_bootstrap_test` -
  REUTILISES SANS MODIFICATION.
- `run_stage15_e7_total_goals_distribution.dispersion_index` - REUTILISE
  SANS MODIFICATION (deja utilise en E7 section 2 sur le corpus complet).
Aucun de ces outils ne permettait de DECOMPOSER la difference par
championnat au niveau demande ici (audit de donnees, spread des
predictions, bootstrap/permutation de la DIFFERENCE entre championnats) -
de nouvelles fonctions PURES, minimales, sont ajoutees ci-dessous dans CE
script, sans modifier aucun script anterieur.

====================================================================
ETAPE 0bis - REGLE DE CLASSIFICATION (figee AVANT observation des
resultats, etape 5 du protocole)
====================================================================
Pour chaque championnat (Over 2.5, distribution corrigee E7/E8) :
    calibree  := IC95% du biais de calibration contient 0
    discrimination_demontree := IC95% (bootstrap) de la correlation
        point-bisseriale n'inclut PAS 0
    magnitude_comparable := la correlation ponctuelle du championnat
        atteint au moins celle du championnat le moins discriminant parmi
        Liga/Ligue1 (jamais un seuil invente ad hoc - toujours relatif aux
        deux autres championnats du meme corpus)
Classification mecanique :
    A - mal calibree et peu discriminante  : NON calibree ET discrimination
        NON demontree
    B - bien calibree mais peu discriminante : calibree ET discrimination
        NON demontree ET magnitude NON comparable
    C - discrimination potentiellement sous-puissante : calibree ET
        discrimination NON demontree ET magnitude COMPARABLE aux autres
        championnats (le signal pourrait exister mais rester invisible a
        cette taille d'echantillon)
    D - autre (discrimination demontree, ou mal calibree ET discriminante)

====================================================================
ETAPE 0ter - CE QUE CE SCRIPT NE FAIT JAMAIS (point 9 du protocole)
====================================================================
Aucune selection d'hypothese a posteriori parmi celles testees. Le
rapport final presente les 9 etapes dans l'ordre, avec leur resultat
individuel, et le verdict est obtenu MECANIQUEMENT a partir de la grille
"Verdict obligatoire" du protocole - jamais en choisissant l'explication
"la plus satisfaisante" apres coup. "Aucune cause identifiable" est un
resultat valide et explicitement accepte.

Usage:
    python scripts/run_stage24_e15_premier_league_discrimination_diagnostic.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.stats as scipy_stats
import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.calibration_engine.decomposition import brier_decomposition  # noqa: E402
from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test  # noqa: E402
from sys_foot_quant.common.logging import get_logger  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_MODELS = ("poisson_simple", "xg_model")  # dixon_coles reproduit poisson_simple sur O2.5 (K/E7/E8/E11)
_LEAGUES = ("liga", "ligue1", "premier_league")
_SEASONS_LIST = ("2024_25", "2025_26")
_N_RESAMPLES = 10_000
_N_PERMUTATIONS = 2_000
_SEED = 0
_MIN_N = 30  # meme convention que partout ailleurs dans le projet

_STAGE12_PATH = Path(__file__).resolve().parent / "run_stage12_e4_expected_goals_discrimination.py"
_STAGE20_PATH = Path(__file__).resolve().parent / "run_stage20_e11_probability_reliability_mapping.py"
_STAGE15_PATH = Path(__file__).resolve().parent / "run_stage15_e7_total_goals_distribution.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_e4():
    return _load(_STAGE12_PATH, "run_stage12_e4_expected_goals_discrimination")


def _load_e11():
    return _load(_STAGE20_PATH, "run_stage20_e11_probability_reliability_mapping")


def _load_e7():
    return _load(_STAGE15_PATH, "run_stage15_e7_total_goals_distribution")


# ==========================================================================
# ETAPE 1 - AUDIT DES DONNEES (fonctions pures, jamais dependantes du
# resultat d'un modele)
# ==========================================================================


def audit_league_season(league: str, season: str, stage8_module) -> dict:
    """Audit direct du fichier BRUT (jamais les objets deja transformes) -
    complete `_verify_integrity` (deja execute par `_load_records`, qui
    leve une exception explicite si le nombre de matchs/equipes/scores/xG
    attendu n'est pas respecte) avec des controles supplementaires :
    equilibre domicile/exterieur, coherence id<->nom d'equipe, doublons de
    coup d'envoi, plausibilite des scores/xG, repartition temporelle."""
    league_id, path = stage8_module._SEASONS[season][league]
    with open(path) as f:
        raw = json.load(f)
    records = stage8_module._load_records(league, season)  # leve deja une exception si integrite violee

    ids = [m["id"] for m in raw]
    n_duplicate_match_ids = len(ids) - len(set(ids))

    team_name_by_id: dict[str, str] = {}
    name_conflicts: list[tuple[str, str, str]] = []
    for m in raw:
        for side in ("h", "a"):
            tid, title = m[side]["id"], m[side]["title"]
            if tid in team_name_by_id and team_name_by_id[tid] != title:
                name_conflicts.append((tid, team_name_by_id[tid], title))
            team_name_by_id[tid] = title
    n_teams = len(team_name_by_id)

    home_counts = Counter(m["h"]["id"] for m in raw)
    away_counts = Counter(m["a"]["id"] for m in raw)
    all_team_ids = set(home_counts) | set(away_counts)
    home_away_imbalance = {
        tid: (home_counts.get(tid, 0), away_counts.get(tid, 0))
        for tid in all_team_ids
        if home_counts.get(tid, 0) != away_counts.get(tid, 0)
    }

    scores = [(int(m["goals"]["h"]), int(m["goals"]["a"])) for m in raw]
    invalid_scores = [s for s in scores if s[0] < 0 or s[1] < 0 or s[0] > 15 or s[1] > 15]

    xgs = [(float(m["xG"]["h"]), float(m["xG"]["a"])) for m in raw]
    invalid_xg = [x for x in xgs if x[0] < 0 or x[1] < 0 or x[0] > 10 or x[1] > 10]

    kickoffs = sorted(r.kickoff_utc for r in records)
    n_duplicate_kickoffs = len(raw) - len(set(kickoffs))
    by_month = Counter((k.year, k.month) for k in kickoffs)

    expected_round_robin = n_teams * (n_teams - 1)

    return {
        "league": league,
        "season": season,
        "n_matches": len(raw),
        "n_teams": n_teams,
        "expected_round_robin_matches": expected_round_robin,
        "matches_equal_round_robin": len(raw) == expected_round_robin,
        "n_duplicate_match_ids": n_duplicate_match_ids,
        "n_team_name_conflicts": len(name_conflicts),
        "team_name_conflicts": name_conflicts,
        "n_home_away_imbalance": len(home_away_imbalance),
        "n_invalid_scores": len(invalid_scores),
        "n_invalid_xg": len(invalid_xg),
        "n_duplicate_kickoffs": n_duplicate_kickoffs,
        "date_min": kickoffs[0],
        "date_max": kickoffs[-1],
        "matches_by_month": dict(sorted(by_month.items())),
    }


def cross_season_team_consistency(league: str, stage8_module) -> dict:
    """Verifie qu'un ID d'equipe DEJA VU une saison n'est jamais reattribue
    a un nom d'equipe DIFFERENT la saison suivante (anomalie de mapping) -
    le turnover normal (promotion/relegation) n'est PAS une anomalie et
    n'est jamais signale comme tel ici."""
    teams_by_season: dict[str, dict[str, str]] = {}
    for season in stage8_module._SEASONS:
        league_id, path = stage8_module._SEASONS[season][league]
        with open(path) as f:
            raw = json.load(f)
        teams: dict[str, str] = {}
        for m in raw:
            for side in ("h", "a"):
                teams[m[side]["id"]] = m[side]["title"]
        teams_by_season[season] = teams

    s1, s2 = _SEASONS_LIST
    common_ids = set(teams_by_season[s1]) & set(teams_by_season[s2])
    conflicts = [
        (tid, teams_by_season[s1][tid], teams_by_season[s2][tid])
        for tid in common_ids
        if teams_by_season[s1][tid] != teams_by_season[s2][tid]
    ]
    return {
        "league": league,
        "n_teams_season1": len(teams_by_season[s1]),
        "n_teams_season2": len(teams_by_season[s2]),
        "n_common_teams": len(common_ids),
        "n_id_name_conflicts_across_seasons": len(conflicts),
        "id_name_conflicts": conflicts,
    }


# ==========================================================================
# ETAPE 3 - DISTRIBUTION REELLE DES BUTS (nouvelles fonctions PURES)
# ==========================================================================


def frequency_table(total_goals: np.ndarray, max_bucket: int = 6) -> dict[str, float]:
    total_goals = np.asarray(total_goals)
    out = {str(k): float(np.mean(total_goals == k)) for k in range(max_bucket)}
    out[f"{max_bucket}+"] = float(np.mean(total_goals >= max_bucket))
    return out


def distribution_moments(total_goals: np.ndarray) -> dict:
    total_goals = np.asarray(total_goals, dtype=float)
    return {
        "n": int(total_goals.size),
        "mean": float(np.mean(total_goals)),
        "var": float(np.var(total_goals, ddof=1)),
        "dispersion_index": float(np.var(total_goals, ddof=1) / np.mean(total_goals)),
        "skewness": float(scipy_stats.skew(total_goals)),
        "excess_kurtosis": float(scipy_stats.kurtosis(total_goals)),
    }


def bootstrap_statistic_diff(sample_a: np.ndarray, sample_b: np.ndarray, stat_fn, n_resamples: int = _N_RESAMPLES, seed: int = _SEED) -> dict:
    """Bootstrap NON apparie generique sur la difference stat_fn(a)-stat_fn(b)
    - generalise `two_sample_bootstrap_test` (qui suppose implicitement
    stat_fn=mean) a une statistique QUELCONQUE (ex. indice de dispersion)."""
    a = np.asarray(sample_a, dtype=float)
    b = np.asarray(sample_b, dtype=float)
    rng = np.random.default_rng(seed)
    stat_a_obs, stat_b_obs = stat_fn(a), stat_fn(b)
    mean_diff = float(stat_a_obs - stat_b_obs)
    idx_a = rng.integers(0, a.size, size=(n_resamples, a.size))
    idx_b = rng.integers(0, b.size, size=(n_resamples, b.size))
    diffs = np.array([stat_fn(a[idx_a[i]]) - stat_fn(b[idx_b[i]]) for i in range(n_resamples)])
    ci_low, ci_high = np.percentile(diffs, [2.5, 97.5])
    p_value = 2.0 * float(np.mean(diffs <= 0)) if mean_diff >= 0 else 2.0 * float(np.mean(diffs >= 0))
    return {"stat_a": float(stat_a_obs), "stat_b": float(stat_b_obs), "mean_diff": mean_diff, "ci_low": float(ci_low), "ci_high": float(ci_high), "p_value": min(p_value, 1.0)}


# ==========================================================================
# ETAPE 4 - DISTRIBUTION DES PREDICTIONS (nouvelle fonction PURE)
# ==========================================================================


def prediction_spread_summary(expected: np.ndarray) -> dict:
    expected = np.asarray(expected, dtype=float)
    q25, q50, q75 = np.percentile(expected, [25, 50, 75])
    return {
        "n": int(expected.size),
        "mean": float(np.mean(expected)),
        "std": float(np.std(expected, ddof=1)),
        "cv": float(np.std(expected, ddof=1) / np.mean(expected)),
        "q25": float(q25),
        "median": float(q50),
        "q75": float(q75),
        "iqr": float(q75 - q25),
    }


# ==========================================================================
# ETAPE 5/6 - CORRELATION : bootstrap (CI simple + difference), permutation
# ==========================================================================


def _pearson_batch(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Correlation de Pearson VECTORISEE sur des lignes (n_resamples, n)."""
    xm = x - x.mean(axis=1, keepdims=True)
    ym = y - y.mean(axis=1, keepdims=True)
    num = (xm * ym).sum(axis=1)
    den = np.sqrt((xm**2).sum(axis=1) * (ym**2).sum(axis=1))
    return num / den


def bootstrap_correlation_ci(x: np.ndarray, y: np.ndarray, n_resamples: int = _N_RESAMPLES, seed: int = _SEED) -> dict:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, x.size, size=(n_resamples, x.size))
    resampled = _pearson_batch(x[idx], y[idx])
    ci_low, ci_high = np.percentile(resampled, [2.5, 97.5])
    return {"corr": float(np.corrcoef(x, y)[0, 1]), "ci_low": float(ci_low), "ci_high": float(ci_high)}


def bootstrap_correlation_diff(x_a: np.ndarray, y_a: np.ndarray, x_b: np.ndarray, y_b: np.ndarray, n_resamples: int = _N_RESAMPLES, seed: int = _SEED) -> dict:
    """Bootstrap NON apparie de la difference de correlation entre deux
    groupes INDEPENDANTS (ex. Premier League vs Liga) - chaque groupe est
    reechantillonne separement, la paire (x,y) est toujours preservee a
    l'interieur d'un meme reechantillonnage (jamais x et y melanges)."""
    x_a, y_a = np.asarray(x_a, dtype=float), np.asarray(y_a, dtype=float)
    x_b, y_b = np.asarray(x_b, dtype=float), np.asarray(y_b, dtype=float)
    rng = np.random.default_rng(seed)
    corr_a_obs = float(np.corrcoef(x_a, y_a)[0, 1])
    corr_b_obs = float(np.corrcoef(x_b, y_b)[0, 1])
    mean_diff = corr_a_obs - corr_b_obs
    idx_a = rng.integers(0, x_a.size, size=(n_resamples, x_a.size))
    idx_b = rng.integers(0, x_b.size, size=(n_resamples, x_b.size))
    corr_a_resampled = _pearson_batch(x_a[idx_a], y_a[idx_a])
    corr_b_resampled = _pearson_batch(x_b[idx_b], y_b[idx_b])
    diffs = corr_a_resampled - corr_b_resampled
    ci_low, ci_high = np.percentile(diffs, [2.5, 97.5])
    p_value = 2.0 * float(np.mean(diffs <= 0)) if mean_diff >= 0 else 2.0 * float(np.mean(diffs >= 0))
    return {"corr_a": corr_a_obs, "corr_b": corr_b_obs, "mean_diff": float(mean_diff), "ci_low": float(ci_low), "ci_high": float(ci_high), "p_value": min(p_value, 1.0)}


def permutation_test_correlation_diff(x: np.ndarray, y: np.ndarray, group_mask: np.ndarray, n_permutations: int = _N_PERMUTATIONS, seed: int = _SEED) -> dict:
    """Sous H0 (aucune difference structurelle liee au groupe), permuter
    l'appartenance au groupe ne doit pas systematiquement reproduire la
    difference de correlation observee. `group_mask` : True = groupe A."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    group_mask = np.asarray(group_mask, dtype=bool)
    n = x.size
    n_a = int(group_mask.sum())
    corr_a_obs = float(np.corrcoef(x[group_mask], y[group_mask])[0, 1])
    corr_b_obs = float(np.corrcoef(x[~group_mask], y[~group_mask])[0, 1])
    observed_diff = corr_a_obs - corr_b_obs

    rng = np.random.default_rng(seed)
    null_diffs = np.empty(n_permutations)
    for i in range(n_permutations):
        perm = rng.permutation(n)
        idx_a, idx_b = perm[:n_a], perm[n_a:]
        ca = np.corrcoef(x[idx_a], y[idx_a])[0, 1]
        cb = np.corrcoef(x[idx_b], y[idx_b])[0, 1]
        null_diffs[i] = ca - cb
    p_value = float(np.mean(np.abs(null_diffs) >= abs(observed_diff)))
    return {"corr_a": corr_a_obs, "corr_b": corr_b_obs, "observed_diff": observed_diff, "p_value": p_value, "n_permutations": n_permutations}


# ==========================================================================
# ETAPE 5 - classification calibration/discrimination (regle FIGEE, etape 0bis)
# ==========================================================================


def classify_calibration_discrimination(calibration_ci: tuple[float, float], correlation_point: float, correlation_ci: tuple[float, float], reference_corr_values: list[float]) -> str:
    calibree = calibration_ci[0] <= 0.0 <= calibration_ci[1]
    discrimination_demontree = not (correlation_ci[0] <= 0.0 <= correlation_ci[1])
    magnitude_comparable = len(reference_corr_values) > 0 and correlation_point >= min(reference_corr_values)

    if not calibree and not discrimination_demontree:
        return "A - mal calibree et peu discriminante"
    if calibree and not discrimination_demontree and magnitude_comparable:
        return "C - discrimination potentiellement sous-puissante (magnitude comparable, non demontree)"
    if calibree and not discrimination_demontree:
        return "B - bien calibree mais peu discriminante"
    return "D - autre (discrimination demontree, ou mal calibree ET discriminante)"


# ==========================================================================
# IMPRESSION - fonctions d'affichage (aucun calcul, purement presentation)
# ==========================================================================


def _print_audit(a: dict) -> None:
    typer.echo(
        f"  {a['league']:<16} {a['season']:<8} n={a['n_matches']:<4} equipes={a['n_teams']:<3} "
        f"round_robin_ok={a['matches_equal_round_robin']!s:<5} doublons_id={a['n_duplicate_match_ids']} "
        f"conflits_nom={a['n_team_name_conflicts']} desequilibre_dom_ext={a['n_home_away_imbalance']} "
        f"scores_invalides={a['n_invalid_scores']} xg_invalides={a['n_invalid_xg']} "
        f"coups_envoi_dupliques={a['n_duplicate_kickoffs']}"
    )
    typer.echo(f"      periode : {a['date_min'].date()} -> {a['date_max'].date()}")


@app.command()
def main() -> None:
    typer.echo("=== E15 : diagnostic structurel de l'absence de discrimination en Premier League ===")
    typer.echo(
        "DIAGNOSTIC PUR. poisson_simple, dixon_coles et xg_model INCHANGES. Aucune modification "
        "d'E1-E14. Aucune conclusion causale tiree d'une simple correlation.\n"
    )

    e11 = _load_e11()
    e9 = e11._load_e9()
    e8 = e9._load_e8()
    e7 = e8._load_e7()
    stage10 = e7._load_stage10()
    stage8 = stage10._load_stage8()
    e4 = _load_e4()

    # ---------------------------------------------------------------- ETAPE 1
    typer.echo("--- ETAPE 1 : audit des donnees (Liga / Ligue 1 / Premier League) ---")
    for league in _LEAGUES:
        for season in _SEASONS_LIST:
            audit = audit_league_season(league, season, stage8)
            _print_audit(audit)
            if audit["team_name_conflicts"]:
                typer.echo(f"      CONFLITS DE NOM (meme id, saison en cours) : {audit['team_name_conflicts']}")
        cross = cross_season_team_consistency(league, stage8)
        typer.echo(
            f"      continuite inter-saisons {league:<16} : {cross['n_common_teams']} equipes communes "
            f"sur {cross['n_teams_season1']}/{cross['n_teams_season2']} - conflits id<->nom : "
            f"{cross['n_id_name_conflicts_across_seasons']}"
        )
        if cross["id_name_conflicts"]:
            typer.echo(f"      CONFLITS INTER-SAISONS : {cross['id_name_conflicts']}")
    typer.echo("")

    # ---------------------------------------------------------------- ETAPE 2
    typer.echo("--- ETAPE 2 : replication d'E4 (espérance BRUTE, RAW, aucune calibration) ---")
    _, test_df_raw = stage10.build_calibration_and_test_sets(stage8)

    corrected_by_model_league: dict[str, dict[str, pd.DataFrame]] = {}
    for model in _MODELS:
        typer.echo(f"##### {model} #####")
        col = f"{model}_lambda_plus_mu"
        sub = test_df_raw.dropna(subset=[col])
        for league in _LEAGUES:
            m = sub["league"] == league
            expected = sub.loc[m, col].to_numpy()
            actual = sub.loc[m, "total_goals"].to_numpy()
            diag = e4.regression_diagnostics(expected, actual)
            boot = e4.bootstrap_bias_and_mae(expected, actual)
            typer.echo(
                f"  {league:<16} n={diag['n']:<4} correlation={diag['correlation']:+.4f} "
                f"MAE={diag['mae']:.4f} biais={diag['biais_moyen']:+.4f} "
                f"IC95%(biais)=[{boot['biais']['ci_low']:+.4f},{boot['biais']['ci_high']:+.4f}]"
            )

        typer.echo(f"  -- {model} : distribution CORRIGEE E7/E8, Over 2.5 (reproduction E11) --")
        corrected_df = e11.build_threshold_dataframe(e8, e7, model)
        corrected_by_model_league[model] = {}
        for league in _LEAGUES:
            sub_c = corrected_df[corrected_df["league"] == league]
            corrected_by_model_league[model][league] = sub_c
            s = e11.summarize_reliability(sub_c["p_over_2.5"].to_numpy(), sub_c["outcome_over_2.5"].to_numpy())
            flag = " [INSUFFISANT n<30]" if s.get("insuffisant") else ""
            typer.echo(
                f"    {league:<16} n={s['n']:<4} Brier={s.get('brier', float('nan')):.4f} "
                f"biais={s.get('biais', float('nan')):+.4f} corr={s.get('correlation', float('nan')):+.4f} "
                f"resolution={s.get('resolution', float('nan')):.4f}{flag}"
            )
        typer.echo("")

    # ---------------------------------------------------------------- ETAPE 3
    typer.echo("--- ETAPE 3 : distribution REELLE du total de buts (corpus complet, 2 saisons) ---")
    total_goals_by_league: dict[str, np.ndarray] = {}
    for league in _LEAGUES:
        all_goals = []
        for season in _SEASONS_LIST:
            for r in stage8._load_records(league, season):
                all_goals.append(r.home_goals + r.away_goals)
        total_goals_by_league[league] = np.array(all_goals, dtype=float)
        moments = distribution_moments(total_goals_by_league[league])
        freq = frequency_table(total_goals_by_league[league])
        typer.echo(
            f"  {league:<16} n={moments['n']:<4} moyenne={moments['mean']:.4f} var={moments['var']:.4f} "
            f"dispersion={moments['dispersion_index']:.4f} skew={moments['skewness']:+.4f} "
            f"kurtosis_exces={moments['excess_kurtosis']:+.4f}"
        )
        typer.echo(f"      frequences : {', '.join(f'{k}={v:.4f}' for k, v in freq.items())}")

    typer.echo("  -- Test de difference d'indice de dispersion (bootstrap, PL vs les deux autres) --")
    for other in ("liga", "ligue1"):
        diff = bootstrap_statistic_diff(total_goals_by_league["premier_league"], total_goals_by_league[other], lambda x: np.var(x, ddof=1) / np.mean(x))
        typer.echo(
            f"    PL vs {other:<8} : dispersion PL={diff['stat_a']:.4f} {other}={diff['stat_b']:.4f} "
            f"diff IC95%=[{diff['ci_low']:+.4f},{diff['ci_high']:+.4f}] p={diff['p_value']:.4f}"
        )
    typer.echo("")

    # ---------------------------------------------------------------- ETAPE 4
    typer.echo("--- ETAPE 4 : distribution des PREDICTIONS (esperance brute) par championnat ---")
    for model in _MODELS:
        typer.echo(f"##### {model} #####")
        col = f"{model}_lambda_plus_mu"
        sub = test_df_raw.dropna(subset=[col])
        for league in _LEAGUES:
            expected = sub.loc[sub["league"] == league, col].to_numpy()
            s = prediction_spread_summary(expected)
            typer.echo(
                f"  {league:<16} n={s['n']:<4} moyenne={s['mean']:.4f} ecart_type={s['std']:.4f} "
                f"CV={s['cv']:.4f} Q25={s['q25']:.4f} mediane={s['median']:.4f} Q75={s['q75']:.4f} IQR={s['iqr']:.4f}"
            )
    typer.echo("")

    # ---------------------------------------------------------------- ETAPE 5
    typer.echo("--- ETAPE 5 : calibration vs discrimination (Over 2.5, distribution corrigee), classification A/B/C/D ---")
    for model in _MODELS:
        typer.echo(f"##### {model} #####")
        corr_by_league: dict[str, float] = {}
        for league in _LEAGUES:
            sub_c = corrected_by_model_league[model][league]
            p, y = sub_c["p_over_2.5"].to_numpy(), sub_c["outcome_over_2.5"].to_numpy()
            corr_by_league[league] = e11.point_biserial_correlation(p, y)

        for league in _LEAGUES:
            sub_c = corrected_by_model_league[model][league]
            p, y = sub_c["p_over_2.5"].to_numpy(), sub_c["outcome_over_2.5"].to_numpy()
            n = len(p)
            if n < _MIN_N:
                typer.echo(f"  {league:<16} n={n} [INSUFFISANT n<30] - non classifie.")
                continue
            diffs = y - p
            boot_bias = paired_bootstrap_test(diffs, n_resamples=_N_RESAMPLES, seed=_SEED)
            corr_ci = bootstrap_correlation_ci(p, y)
            reference = [v for lg, v in corr_by_league.items() if lg != league]
            classification = classify_calibration_discrimination(
                (boot_bias["ci_low"], boot_bias["ci_high"]), corr_ci["corr"], (corr_ci["ci_low"], corr_ci["ci_high"]), reference
            )
            typer.echo(
                f"  {league:<16} n={n:<4} biais_IC95%=[{boot_bias['ci_low']:+.4f},{boot_bias['ci_high']:+.4f}] "
                f"corr={corr_ci['corr']:+.4f} corr_IC95%=[{corr_ci['ci_low']:+.4f},{corr_ci['ci_high']:+.4f}]"
            )
            typer.echo(f"      -> classification : {classification}")
    typer.echo("")

    # ---------------------------------------------------------------- ETAPE 6
    typer.echo("--- ETAPE 6 : puissance/incertitude - la difference PL vs Liga/Ligue1 est-elle demontree ? ---")
    for model in _MODELS:
        typer.echo(f"##### {model} #####")
        col = f"{model}_lambda_plus_mu"
        sub = test_df_raw.dropna(subset=[col])
        pl = sub[sub["league"] == "premier_league"]
        for other in ("liga", "ligue1"):
            oth = sub[sub["league"] == other]
            diff = bootstrap_correlation_diff(pl[col].to_numpy(), pl["total_goals"].to_numpy(), oth[col].to_numpy(), oth["total_goals"].to_numpy())
            typer.echo(
                f"  PL (corr={diff['corr_a']:+.4f}) vs {other:<8} (corr={diff['corr_b']:+.4f}) : "
                f"diff IC95%=[{diff['ci_low']:+.4f},{diff['ci_high']:+.4f}] p={diff['p_value']:.4f}"
            )

        rest_mask = (sub["league"] != "premier_league").to_numpy()
        perm = permutation_test_correlation_diff(sub[col].to_numpy(), sub["total_goals"].to_numpy(), sub["league"].eq("premier_league").to_numpy())
        typer.echo(
            f"  Permutation (PL vs reste poole, {perm['n_permutations']} permutations) : "
            f"corr_PL={perm['corr_a']:+.4f} corr_reste={perm['corr_b']:+.4f} diff_observee={perm['observed_diff']:+.4f} "
            f"p={perm['p_value']:.4f}"
        )
    typer.echo("")

    # ---------------------------------------------------------------- ETAPE 7
    typer.echo("--- ETAPE 7 : analyse temporelle (par saison, puis par moitie chronologique du test) ---")
    decision_time = e8.build_decision_time_lookup(stage8)
    test_df_raw_dt = test_df_raw.copy()
    test_df_raw_dt["decision_time"] = test_df_raw_dt["match_id"].map(decision_time)
    for model in _MODELS:
        typer.echo(f"##### {model} #####")
        col = f"{model}_lambda_plus_mu"
        sub = test_df_raw_dt.dropna(subset=[col])
        for league in _LEAGUES:
            sub_l = sub[sub["league"] == league]
            typer.echo(f"  {league} :")
            for season in _SEASONS_LIST:
                s_l = sub_l[sub_l["season"] == season]
                if len(s_l) >= _MIN_N:
                    diag = e4.regression_diagnostics(s_l[col].to_numpy(), s_l["total_goals"].to_numpy())
                    typer.echo(f"      saison {season} : n={diag['n']:<4} correlation={diag['correlation']:+.4f}")
                else:
                    typer.echo(f"      saison {season} : n={len(s_l)} [INSUFFISANT n<30]")

            median_time = sub_l["decision_time"].median()
            for label, mask in (("premiere moitie", sub_l["decision_time"] < median_time), ("seconde moitie", sub_l["decision_time"] >= median_time)):
                s_l = sub_l[mask]
                if len(s_l) >= _MIN_N:
                    diag = e4.regression_diagnostics(s_l[col].to_numpy(), s_l["total_goals"].to_numpy())
                    typer.echo(f"      {label:<16} : n={diag['n']:<4} correlation={diag['correlation']:+.4f}")
                else:
                    typer.echo(f"      {label:<16} : n={len(s_l)} [INSUFFISANT n<30]")
    typer.echo("")

    # ---------------------------------------------------------------- ETAPE 8
    typer.echo("--- ETAPE 8 : synthese par modele (le phenomene est-il commun aux deux modeles ?) ---")
    for league in _LEAGUES:
        corrs = {}
        for model in _MODELS:
            col = f"{model}_lambda_plus_mu"
            sub = test_df_raw.dropna(subset=[col])
            m = sub["league"] == league
            corrs[model] = e4.regression_diagnostics(sub.loc[m, col].to_numpy(), sub.loc[m, "total_goals"].to_numpy())["correlation"]
        typer.echo(f"  {league:<16} " + " | ".join(f"{model}={c:+.4f}" for model, c in corrs.items()))
    typer.echo("  (dixon_coles reproduit exactement poisson_simple sur Over 2.5 - deja etabli en K/E7/E8/E11)\n")

    typer.echo(
        "RESERVE : diagnostic pur, aucune conclusion causale tiree d'une simple correlation. Aucun "
        "modele modifie, aucun hyperparametre touche, aucune correction E7/E8 modifiee, aucune regle "
        "de production creee. poisson_simple, dixon_coles et xg_model restent inchanges."
    )
    typer.echo("\nARRET : E15 termine, conformement au protocole. Aucune experience E16 lancee automatiquement.")


if __name__ == "__main__":
    app()
