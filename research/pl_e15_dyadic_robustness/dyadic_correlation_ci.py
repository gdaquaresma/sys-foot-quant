"""Analyse de ROBUSTESSE (hors chaine de production E15) de l'IC95% de la
correlation point-biserielle p_over_2.5 / outcome_over_2.5.

NE REMPLACE PAS et NE MODIFIE PAS `bootstrap_correlation_ci`
(scripts/run_stage24_e15_premier_league_discrimination_diagnostic.py),
`paired_bootstrap_test` (calibration_engine/significance.py) ni
`classify_calibration_discrimination`. Les resultats E15 historiques
(classification A/B/C/D, split, modeles) restent inchanges - ce module
calcule uniquement un IC alternatif, cluster-robuste, pour QUANTIFIER le
risque deja identifie (PL-E15-CLUSTER, PL-E15-DYADIC) que le bootstrap
par match ignore la dependance intra-equipe.

METHODE (analytique, deterministe, aucun tirage aleatoire) :

1. La correlation de Pearson/point-biserielle r entre x et y est reliee
   de facon EXACTE (identite algebrique OLS, pas une approximation) a la
   pente b de la regression lineaire simple y = a + b*x + e par
   r = b * SD(x) / SD(y). Puisque SD(x), SD(y) > 0, r=0 <=> b=0 : tester
   b=0 avec une variance robuste dyadique equivaut EXACTEMENT a tester
   r=0 (aucune approximation pour le test d'hypothese lui-meme). Seule
   la conversion SE(b) -> SE(r) (pour construire un IC sur r, pas pour
   le test) utilise la methode delta standard (SD(x)/SD(y) traites
   comme approximativement fixes) - approximation signalee, pas cachee.

2. Variance "sandwich" dyadique-robuste de b (Aronow, Samii & Assenova
   2015, "Cluster-Robust Variance Estimation for Dyadic Data") :
   generalise le cluster-robuste standard (qui somme les produits
   croises de score UNIQUEMENT pour des observations du MEME cluster)
   a une structure de graphe - on somme pour TOUTE PAIRE d'observations
   partageant AU MOINS UN noeud (equipe domicile OU exterieure, dans
   n'importe quel role). C'est precisement la structure confirmee par
   PL-E15-DYADIC (chaque match appartient simultanement a 2 clusters),
   et c'est EXPLICITEMENT DIFFERENT d'un bootstrap naif ou domicile et
   exterieur seraient tires separement sans lien entre les deux roles.

3. Degres de liberte - AVERTISSEMENT METHODOLOGIQUE EXPLICITE (audit
   PL-E15-DYADIC-METHOD-AUDIT, section 2) :

   Le choix `df = n_clusters - 1` (quantile de Student plutot que normal)
   est une HEURISTIQUE IMPORTEE de la pratique cluster-robuste A UNE
   DIMENSION (Cameron, Gelbach & Miller 2008 ; Cameron & Miller 2015,
   "A Practitioner's Guide to Cluster-Robust Inference"), ou les clusters
   forment une PARTITION disjointe des donnees. Elle n'est PAS une
   correction theoriquement etablie SPECIFIQUEMENT pour l'estimateur
   dyadique d'Aronow, Samii & Assenova (2015) - leur article ne prescrit
   aucune correction de degres de liberte en petit echantillon pour leur
   estimateur ; leur traitement est principalement asymptotique (normalite
   approchee quand le nombre de noeuds croit). Ici, les "clusters"
   (equipes) ne forment PAS une partition - domicile et exterieur sont
   tires du MEME ensemble de noeuds et se recoupent integralement, ce qui
   est structurellement different du cas pour lequel `G-1` a ete concu.

   CE QUE CELA SIGNIFIE CONCRETEMENT :
   - La METHODE DE VARIANCE utilisee (le sandwich dyadique lui-meme,
     `var_b`/`se_b`) est l'estimateur valide - rien n'est remis en cause
     a ce niveau.
   - La TRANSFORMATION de cette variance en intervalle via un quantile
     t(df=n_clusters-1) est une approximation/heuristique, pas une
     correction de petit echantillon theoriquement justifiee pour ce cas
     precis.
   - L'intervalle retourne (`ci_b`, `ci_r`) doit donc etre lu comme
     INDICATIF/APPROXIMATIF, et non comme un IC95% rigoureusement
     calibre par une theorie de petit echantillon specifique a la
     structure dyadique. Le choix de df n'est PAS modifie ici (le
     resultat numerique existant est preserve a l'identique) - seule
     cette documentation est ajoutee, conformement a la decision B de
     l'audit (corriger la documentation, pas l'estimateur).

4. Transformation b -> r : AVERTISSEMENT METHODOLOGIQUE EXPLICITE (audit
   PL-E15-DYADIC-METHOD-AUDIT, section 3) :

   `SE(r) ~= SE(b) * SD(x) / SD(y)` est une PROPAGATION DELTA DE PREMIER
   ORDRE, pas une methode delta complete. `SD(x)` et `SD(y)` sont traites
   comme des CONSTANTES FIXES dans cette approximation - la covariance
   jointe complete de `(b_hat, SD(x)_hat, SD(y)_hat)` (trois quantites
   conjointement echantillonnees) sous le meme cadre dyadique-robuste
   n'est PAS calculee ici. Consequence : le TEST d'hypothese `r=0`
   (equivalent exact a `b=0`, section 1 du module) reste valide sans
   aucune approximation, mais la LARGEUR EXACTE de l'intervalle sur `r`
   herite de cette approximation de premier ordre. Cette methode n'est
   PAS remplacee par une autre ici (decision B : documenter, pas
   reconstruire).

5. Variance negative -> NaN : COMPORTEMENT INTENTIONNEL, documente
   explicitement (audit PL-E15-DYADIC-METHOD-AUDIT, section 1) :

   L'estimateur sandwich dyadique-robuste, comme tout estimateur de
   variance clusterisee/reseau de ce type, N'EST PAS GARANTI SEMI-DEFINI
   POSITIF EN ECHANTILLON FINI - un phenomene connu et documente dans la
   litterature des variances sandwich clusterisees (pas une anomalie de
   cette implementation). Si `var_b` est calcule negatif ou nul, la
   fonction retourne `NaN` pour `se_b`/`se_r`/les bornes d'IC associees,
   PLUTOT QUE de lever une exception ou de produire une valeur fausse.
   Ce garde-fou ne doit JAMAIS etre modifie pour forcer une valeur
   positive artificielle (ex. `abs(var_b)`) - cela masquerait une
   situation ou la variance estimee n'est structurellement pas
   exploitable, ce qui serait plus trompeur qu'un `NaN` explicite. Sur le
   corpus reel Premier League (228 matchs, 23 equipes) utilise par cette
   analyse, ce cas ne s'est PAS produit (`var_b > 0` pour les deux
   modeles, poisson_simple et xg_model) - mais il a ete observe sur un
   cas synthetique distinct lors de l'audit, d'ou ce garde-fou.

Aucune donnee fabriquee, aucune nouvelle saison, aucun bootstrap sur les
resultats historiques deja actes.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import t as student_t


def dyadic_correlation_ci(
    x: np.ndarray,
    y: np.ndarray,
    home_ids: np.ndarray,
    away_ids: np.ndarray,
    alpha: float = 0.05,
) -> dict:
    """IC robuste (dyadique) pour la correlation entre x (continu) et y
    (binaire ou continu). home_ids/away_ids identifient les deux noeuds
    (equipes) de chaque observation (meme ordre que x/y).

    Retourne un dict avec la correlation ponctuelle (identique a
    np.corrcoef), l'IC robuste, le nombre de clusters distincts, et les
    quantites intermediaires (b, se_b, se_r) pour audit.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    home_ids = np.asarray(home_ids)
    away_ids = np.asarray(away_ids)
    n = x.size
    if not (y.size == n and home_ids.size == n and away_ids.size == n):
        raise ValueError("x, y, home_ids, away_ids doivent avoir la meme longueur.")
    if n < 4:
        raise ValueError("n trop petit pour une regression/correlation.")

    r = float(np.corrcoef(x, y)[0, 1])

    # --- regression lineaire simple y = a + b*x + e (OLS, forme fermee) ---
    x_centered = x - x.mean()
    y_centered = y - y.mean()
    s_xx = float(np.sum(x_centered**2))
    b = float(np.sum(x_centered * y_centered) / s_xx)
    a = float(y.mean() - b * x.mean())
    resid = y - (a + b * x)

    # --- variance sandwich dyadique-robuste de b (Aronow-Samii-Assenova) ---
    g = x_centered * resid  # contribution ("score") de chaque observation
    all_ids = np.concatenate([home_ids, away_ids])
    n_clusters = int(np.unique(all_ids).size)

    # matrice d'adjacence dyadique : partagent-ils au moins un noeud ?
    shares_home_home = home_ids[:, None] == home_ids[None, :]
    shares_home_away = home_ids[:, None] == away_ids[None, :]
    shares_away_home = away_ids[:, None] == home_ids[None, :]
    shares_away_away = away_ids[:, None] == away_ids[None, :]
    adjacency = shares_home_home | shares_home_away | shares_away_home | shares_away_away

    meat = float(np.sum((g[:, None] * g[None, :]) * adjacency))
    var_b = meat / (s_xx**2)
    # Garde-fou INTENTIONNEL, ne jamais forcer une valeur positive (voir
    # section 5 du docstring du module) : var_b n'est pas garanti >= 0 en
    # echantillon fini pour un estimateur sandwich de ce type.
    se_b = float(np.sqrt(var_b)) if var_b > 0 else float("nan")

    # --- propagation delta SE(b) -> SE(r) - approximation de premier ordre,
    # SD(x)/SD(y) traites comme fixes (voir section 4 du docstring du module) ---
    sd_x = float(x.std(ddof=1))
    sd_y = float(y.std(ddof=1))
    se_r = se_b * sd_x / sd_y if sd_y > 0 else float("nan")

    # --- quantile de Student, df = n_clusters - 1 : HEURISTIQUE importee du
    # cluster-robuste a une dimension, non validee specifiquement pour cet
    # estimateur dyadique - IC resultant a lire comme INDICATIF, pas comme
    # un IC95% rigoureusement calibre (voir section 3 du docstring du module) ---
    df = max(n_clusters - 1, 1)
    t_crit = float(student_t.ppf(1 - alpha / 2, df))

    ci_low_b, ci_high_b = b - t_crit * se_b, b + t_crit * se_b
    ci_low_r, ci_high_r = r - t_crit * se_r, r + t_crit * se_r

    return {
        "n": n,
        "n_clusters": n_clusters,
        "df": df,
        "r": r,
        "b": b,
        "se_b": se_b,
        "se_r": se_r,
        "t_crit": t_crit,
        "ci_b": (ci_low_b, ci_high_b),
        "ci_r": (ci_low_r, ci_high_r),
        "contains_zero": ci_low_r <= 0.0 <= ci_high_r,
    }
