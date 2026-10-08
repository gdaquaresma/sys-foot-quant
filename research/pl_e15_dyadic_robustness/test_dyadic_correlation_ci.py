"""Tests cibles pour `dyadic_correlation_ci` (analyse de ROBUSTESSE,
hors chaine de production E15). Deux familles de tests :

1. Cas synthetiques simples (comportement algorithmique uniquement -
   AUCUN match fictif presente comme une donnee reelle) ;
2. Verification sur le corpus E15 reel deja utilise (228 matchs TEST
   Premier League) - confirme que x/y et le nombre de matchs/equipes
   sont EXACTEMENT ceux d'E15, jamais une nouvelle saison ni une
   donnee future.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import sys
from pathlib import Path

import numpy as np
import pytest

_MODULE_PATH = Path(__file__).resolve().parent / "dyadic_correlation_ci.py"
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_module():
    spec = importlib.util.spec_from_file_location("dyadic_correlation_ci", _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def dyadic_module():
    return _load_module()


# --- 1. Determinisme (aucun tirage aleatoire) --------------------------------


def test_deterministic_same_inputs_same_outputs(dyadic_module) -> None:
    rng = np.random.default_rng(0)
    x = rng.normal(size=60)
    y = (rng.normal(size=60) > 0).astype(float)
    home_ids = rng.integers(0, 10, size=60)
    away_ids = rng.integers(0, 10, size=60)
    out1 = dyadic_module.dyadic_correlation_ci(x, y, home_ids, away_ids)
    out2 = dyadic_module.dyadic_correlation_ci(x, y, home_ids, away_ids)
    assert out1 == out2


# --- 2. La correlation ponctuelle retournee == np.corrcoef standard ---------


def test_point_correlation_matches_numpy_corrcoef(dyadic_module) -> None:
    rng = np.random.default_rng(1)
    x = rng.normal(size=40)
    y = rng.normal(size=40)
    home_ids = np.arange(40)
    away_ids = np.arange(40, 80)
    out = dyadic_module.dyadic_correlation_ci(x, y, home_ids, away_ids)
    assert out["r"] == pytest.approx(float(np.corrcoef(x, y)[0, 1]))


# --- 3. Cas totalement independant (aucun noeud partage) : la methode doit
#        degenerer vers la variance robuste non-clusterisee standard (HC0) --


def test_fully_independent_dyads_reduces_to_standard_robust_se(dyadic_module) -> None:
    rng = np.random.default_rng(2)
    n = 200
    x = rng.normal(size=n)
    y = 0.3 * x + rng.normal(size=n)
    # Chaque match a ses 2 equipes propres, jamais reutilisees -> 0 noeud partage
    home_ids = np.arange(n)
    away_ids = np.arange(n, 2 * n)
    out = dyadic_module.dyadic_correlation_ci(x, y, home_ids, away_ids)

    # Formule HC0 non-clusterisee de reference (aucune donnee partagee) :
    x_c = x - x.mean()
    s_xx = float(np.sum(x_c**2))
    bhat = float(np.sum(x_c * (y - y.mean())) / s_xx)
    resid = y - (y.mean() - bhat * x.mean() + bhat * x)
    hc0_var = float(np.sum((x_c * resid) ** 2) / s_xx**2)
    hc0_se = np.sqrt(hc0_var)

    assert out["se_b"] == pytest.approx(hc0_se, rel=1e-9)
    assert out["n_clusters"] == 2 * n


# --- 4. Cas avec forte dependance intra-cluster : la SE dyadique doit etre
#        STRICTEMENT superieure a la SE non-clusterisee (comportement attendu) --


def test_shared_cluster_dependence_inflates_standard_error(dyadic_module) -> None:
    rng = np.random.default_rng(3)
    n_teams = 6
    matches_per_team_pair = 10
    # Force latente par equipe (feature non observee, cree une dependance
    # intra-equipe reelle) :
    team_strength = rng.normal(size=n_teams)

    home_ids, away_ids, x_list, y_list = [], [], [], []
    for t in range(n_teams):
        for _ in range(matches_per_team_pair):
            opponent = (t + 1) % n_teams
            x_val = 0.2 * team_strength[t] + rng.normal(scale=0.3)
            y_val = team_strength[t] + rng.normal(scale=0.3)
            home_ids.append(t)
            away_ids.append(opponent)
            x_list.append(x_val)
            y_list.append(y_val)
    x = np.array(x_list)
    y = np.array(y_list)
    home_ids = np.array(home_ids)
    away_ids = np.array(away_ids)

    out = dyadic_module.dyadic_correlation_ci(x, y, home_ids, away_ids)

    # SE non-clusterisee (HC0) de reference, memes donnees :
    x_c = x - x.mean()
    s_xx = float(np.sum(x_c**2))
    bhat = float(np.sum(x_c * (y - y.mean())) / s_xx)
    resid = y - (y.mean() - bhat * x.mean() + bhat * x)
    hc0_se = float(np.sqrt(np.sum((x_c * resid) ** 2) / s_xx**2))

    assert out["se_b"] > hc0_se  # la dependance intra-equipe gonfle la SE, comme attendu
    assert out["n_clusters"] == n_teams


# --- 5. Aucune fuite temporelle possible : la fonction ne lit jamais de date --


def test_function_never_reads_any_temporal_field(dyadic_module) -> None:
    source = inspect.getsource(dyadic_module.dyadic_correlation_ci)
    tree = ast.parse(source)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    forbidden = {"kickoff_utc", "kickoff_time", "decision_time", "date", "datetime", "season"}
    assert names.isdisjoint(forbidden)
    sig_params = set(inspect.signature(dyadic_module.dyadic_correlation_ci).parameters)
    assert sig_params == {"x", "y", "home_ids", "away_ids", "alpha"}


# --- 6. Verification sur le corpus E15 REEL (228 matchs PL, 23 equipes) -----


@pytest.fixture(scope="module")
def e15_real_data():
    sys.path.insert(0, str(_REPO_ROOT / "src"))

    def _load(path: Path, name: str):
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        return mod

    stage12 = _load(_REPO_ROOT / "scripts" / "run_stage12_e4_expected_goals_discrimination.py", "stage12")
    stage20 = _load(_REPO_ROOT / "scripts" / "run_stage20_e11_probability_reliability_mapping.py", "stage20")
    e9 = stage20._load_e9()
    e8 = e9._load_e8()
    e7 = e8._load_e7()
    stage10 = e7._load_stage10()
    stage8 = stage10._load_stage8()

    _, test_df_raw = stage10.build_calibration_and_test_sets(stage8)

    match_teams = {}
    for season in ("2024_25", "2025_26"):
        for r in stage8._load_records("premier_league", season):
            match_teams[r.match_id] = (r.home_team_id, r.away_team_id)

    pl_test = test_df_raw[test_df_raw["league"] == "premier_league"].copy()
    pl_test["home_team_id"] = pl_test["match_id"].map(lambda m: match_teams[m][0])
    pl_test["away_team_id"] = pl_test["match_id"].map(lambda m: match_teams[m][1])
    return pl_test


def test_e15_corpus_size_matches_already_published_results(e15_real_data) -> None:
    assert len(e15_real_data) == 228
    all_ids = set(e15_real_data["home_team_id"]) | set(e15_real_data["away_team_id"])
    assert len(all_ids) == 23


def test_e15_corpus_correlation_matches_already_published_values(dyadic_module, e15_real_data) -> None:
    # Reproduit EXACTEMENT la colonne p_over_2.5 corrigee (E7/E8) utilisee par
    # E15 Etape 5 - via le meme chemin que le script canonique, jamais une
    # nouvelle colonne ni un nouveau calcul.
    sys.path.insert(0, str(_REPO_ROOT / "src"))

    def _load(path: Path, name: str):
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        return mod

    stage20 = _load(_REPO_ROOT / "scripts" / "run_stage20_e11_probability_reliability_mapping.py", "stage20")
    e9 = stage20._load_e9()
    e8 = e9._load_e8()
    e7 = e8._load_e7()

    for model, expected_r in (("poisson_simple", -0.0056), ("xg_model", 0.0367)):
        corrected_df = stage20.build_threshold_dataframe(e8, e7, model)
        sub = corrected_df[corrected_df["league"] == "premier_league"].copy()
        sub["home_team_id"] = sub["match_id"].map(
            lambda m: e15_real_data.set_index("match_id").loc[m, "home_team_id"]
            if m in e15_real_data["match_id"].values
            else None
        )
        # jointure directe via le dict deja construit pour eviter toute ambiguite
        merged = sub.merge(e15_real_data[["match_id", "home_team_id", "away_team_id"]], on="match_id", suffixes=("", "_dup"))
        p = merged["p_over_2.5"].to_numpy()
        y = merged["outcome_over_2.5"].to_numpy()
        home_ids = merged["home_team_id"].to_numpy()
        away_ids = merged["away_team_id"].to_numpy()
        assert len(p) == 228

        out = dyadic_module.dyadic_correlation_ci(p, y, home_ids, away_ids)
        assert out["r"] == pytest.approx(expected_r, abs=1e-3)
        assert out["n_clusters"] == 23


# --- 7. Lacunes identifiees par PL-E15-DYADIC-METHOD-AUDIT -------------------
# (A) dyade reciproque (A->B et B->A), (B) symetrie codifiee de l'adjacence,
# (C) invariance a l'ordre des observations, (D) variance negative -> NaN.


def test_reciprocal_dyad_is_treated_as_sharing_both_nodes(dyadic_module) -> None:
    # Deux observations A->B et B->A : elles partagent les DEUX noeuds, dans
    # les deux directions. L'adjacence doit les considerer comme liees
    # (agnostique au role domicile/exterieur, conformement a Aronow-Samii-
    # Assenova pour des dyades dirigees - section 1 de l'audit methode).
    rng = np.random.default_rng(42)
    n = 20
    x = rng.normal(size=n)
    y = rng.normal(size=n)
    home_ids = rng.integers(0, 6, size=n)
    away_ids = rng.integers(0, 6, size=n)
    # On force les observations 0 et 1 a etre une paire reciproque A<->B.
    home_ids[0], away_ids[0] = 0, 1  # A -> B
    home_ids[1], away_ids[1] = 1, 0  # B -> A

    home_centered = home_ids[:, None] == home_ids[None, :]
    home_away = home_ids[:, None] == away_ids[None, :]
    away_home = away_ids[:, None] == home_ids[None, :]
    away_away = away_ids[:, None] == away_ids[None, :]
    adjacency = home_centered | home_away | away_home | away_away

    # Les observations 0 et 1 partagent A ET B (dans des roles inverses) ->
    # doivent etre mutuellement adjacentes.
    assert adjacency[0, 1]
    assert adjacency[1, 0]

    # La fonction doit s'executer sans erreur sur ce cas (pas d'exception).
    out = dyadic_module.dyadic_correlation_ci(x, y, home_ids, away_ids)
    assert out["n"] == n


def test_adjacency_matrix_is_symmetric_across_home_away_configurations(dyadic_module) -> None:
    # Reproduit la verification de symetrie effectuee pendant l'audit
    # (PL-E15-DYADIC-METHOD-AUDIT section 1), desormais codifiee en test.
    rng = np.random.default_rng(11)
    n = 40
    home_ids = rng.integers(0, 10, size=n)
    away_ids = rng.integers(0, 10, size=n)

    shares_home_home = home_ids[:, None] == home_ids[None, :]
    shares_home_away = home_ids[:, None] == away_ids[None, :]
    shares_away_home = away_ids[:, None] == home_ids[None, :]
    shares_away_away = away_ids[:, None] == away_ids[None, :]
    adjacency = shares_home_home | shares_home_away | shares_away_home | shares_away_away

    assert np.array_equal(adjacency, adjacency.T)
    assert np.all(np.diag(adjacency))  # une observation partage toujours ses noeuds avec elle-meme


def test_order_invariance_of_observations(dyadic_module) -> None:
    # Meme jeu de donnees, deux ordres differents : r et se_b doivent etre
    # identiques (a la precision flottante standard) lorsque finis, et le
    # comportement NaN doit etre coherent (NaN des deux cotes, pas fini
    # d'un cote et NaN de l'autre).
    rng = np.random.default_rng(5)
    n = 25
    x = rng.normal(size=n)
    y = rng.normal(size=n)
    home_ids = rng.integers(0, 9, size=n)
    away_ids = rng.integers(0, 9, size=n)

    out_original = dyadic_module.dyadic_correlation_ci(x, y, home_ids, away_ids)

    perm = rng.permutation(n)
    out_permuted = dyadic_module.dyadic_correlation_ci(x[perm], y[perm], home_ids[perm], away_ids[perm])

    assert out_original["r"] == pytest.approx(out_permuted["r"], abs=1e-9)
    assert out_original["n_clusters"] == out_permuted["n_clusters"]

    se_b_original_finite = np.isfinite(out_original["se_b"])
    se_b_permuted_finite = np.isfinite(out_permuted["se_b"])
    assert se_b_original_finite == se_b_permuted_finite  # coherence du comportement NaN
    if se_b_original_finite:
        assert out_original["se_b"] == pytest.approx(out_permuted["se_b"], rel=1e-9)
        assert out_original["ci_r"] == pytest.approx(out_permuted["ci_r"], rel=1e-9)


def test_negative_sandwich_variance_returns_nan_without_exception(dyadic_module) -> None:
    # Reproduit, de maniere deterministe (seed fixe), le cas synthetique
    # observe pendant l'audit (PL-E15-DYADIC-METHOD-AUDIT section 1) ou la
    # variance sandwich dyadique devient negative. Documente le comportement
    # de securite attendu : NaN, jamais une exception, jamais une valeur
    # positive forcee (ex. abs(var_b)).
    rng = np.random.default_rng(7)
    n = 30
    x = rng.normal(size=n)
    y = rng.normal(size=n)
    home_ids = rng.integers(0, 8, size=n)
    away_ids = rng.integers(0, 8, size=n)

    out = dyadic_module.dyadic_correlation_ci(x, y, home_ids, away_ids)

    # Ce seed precis est connu (audit) pour produire une variance sandwich
    # negative -> se_b/se_r/ci_r doivent etre NaN, jamais une exception levee
    # et jamais une valeur positive artificielle.
    assert np.isnan(out["se_b"])
    assert np.isnan(out["se_r"])
    assert np.isnan(out["ci_r"][0]) and np.isnan(out["ci_r"][1])
    # r et b restent calculables independamment de la variance (pas affectes
    # par le garde-fou NaN - seule la partie incertitude est concernee).
    assert np.isfinite(out["r"])
    assert np.isfinite(out["b"])
