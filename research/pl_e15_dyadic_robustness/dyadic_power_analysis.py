"""PL-E15-DYADIC-POWER : analyse de puissance statistique PARALLELE (hors
chaine de production), reprenant la question de PL-E15-POWER mais a partir
de l'incertitude dyadique-robuste deja validee et commitee
(`dyadic_correlation_ci.py`), au lieu du Fisher-z naif i.i.d. utilise dans
PL-E15-POWER.

NE REMPLACE PAS, NE MODIFIE PAS `dyadic_correlation_ci.py` ni ses tests -
ce module les IMPORTE en lecture (reutilisation, pas une copie), et ne
touche a aucune donnee canonique, aucun fichier du moteur, aucun script E15
canonique.

====================================================================
POURQUOI CE N'EST PAS UN SIMPLE COPIER-COLLER DE FISHER-Z (voir le rapport
PL-E15-DYADIC-POWER pour la discussion complete)
====================================================================

1. QUANTITE TESTEE : H0: r=0 contre H1: r!=0, test de Wald DIRECT sur r
   (`r_hat / se_r` compare a `t(df)`), PAS une reconstruction via Fisher-z
   (atanh). `dyadic_correlation_ci.py` construit deja son IC comme
   `r +/- t_crit * se_r` directement sur r - jamais sur atanh(r). Reprendre
   Fisher-z ici introduirait une double transformation incoherente avec la
   methode deja validee et commitee.

2. UNITE EFFECTIVE D'INFORMATION : pas le match. PL-E15-CLUSTER/DYADIC ont
   etabli que l'information effective vient de ~23 clusters (equipes), pas
   de 228 observations independantes. Une saison PL supplementaire ajoute
   ~114 matchs mais seulement ~3 NOUVEAUX clusters (17-20 equipes
   recoupees d'une saison a l'autre, deja confirme empiriquement) - donc
   majoritairement de l'information INTRA-cluster, pas inter-cluster.

3. AUCUNE FORMULE se_r(n) VALIDEE POUR LE CAS DYADIQUE : contrairement au
   cas i.i.d. (SE = 1/sqrt(n-3), formule fermee de Fisher), il n'existe
   PAS de formule analytique validee donnant se_r en fonction de n pour
   l'estimateur sandwich dyadique. On dispose seulement d'UN point
   empirique : se_r a n=228 (23 clusters). Toute projection vers un n plus
   grand necessite une HYPOTHESE D'EXTRAPOLATION explicite.

4. APPROXIMATION RETENUE (documentee, pas cachee) : facteur d'inflation
   empirique kappa = se_r_dyadique / se_r_naif(n=228), ou
   se_r_naif(n=228) = 1/sqrt(228-3) est la formule Fisher i.i.d. classique
   appliquee au MEME n. On observe kappa_poisson > 1 (SE gonflee) et
   kappa_xg < 1 (SE reduite) - cohrent avec le resultat deja observe en
   PL-E15-DYADIC-CI (IC plus large pour poisson, plus etroit pour xg).
   L'extrapolation `n_necessaire_dyadique ~= (n_necessaire_fisher_z - 3) *
   kappa**2 + 3` est utilisee SOUS L'HYPOTHESE EXPLICITE que kappa reste
   constant quand n augmente.

5. HYPOTHESE OPTIMISTE SIGNALEE EXPLICITEMENT : kappa constant avec n est
   une hypothese OPTIMISTE, pas neutre - puisque les nouveaux clusters
   croissent plus lentement (promotion/relegation, ~3/saison) que les
   nouvelles observations (~114/saison), la theorie des variances
   clusterisees suggere que kappa devrait plutot AUGMENTER (pas rester
   constant) a mesure qu'on ajoute des saisons qui reutilisent
   majoritairement les memes clusters. Les resultats bases sur cette
   hypothese doivent donc etre lus comme un ORDRE DE GRANDEUR OPTIMISTE,
   jamais une puissance exacte.

6. APPROXIMATION DE PUISSANCE : approximation normale standard (pas de
   distribution t non centrale exacte), avec seuil critique t(df) (pas
   z) pour rester coherent avec la convention deja adoptee par
   `dyadic_correlation_ci` pour construire son IC.

   CONSEQUENCE DOCUMENTEE (decouverte en testant ce module) : ce choix
   (seuil t(df) + approximation normale de la puissance) ne preserve PAS
   exactement alpha=5% sous H0 - le taux de faux positifs reel est
   `2*Phi(-t_crit(df))`, legerement INFERIEUR a alpha pour un df modeste
   (ex. ~3.8% pour df=22, pas 5%). C'est un effet secondaire mineur et
   legerement CONSERVATEUR de la coherence avec `dyadic_correlation_ci`,
   pas une erreur - signale explicitement plutot que suppose neutre.

Aucune nouvelle donnee, aucune nouvelle saison, aucune modification des
228 observations historiques - ce module est purement parametrique (il ne
charge aucune donnee de match, il prend r/se_r/n/df en entree).
"""

from __future__ import annotations

import math

from scipy.stats import norm, t as student_t

# Valeurs de reference deja validees et commitees (PL-E15-DYADIC-CI /
# PL-E15-DYADIC-METHOD-CORRECTION), reproduites ici UNIQUEMENT comme
# constantes documentaires - ne sont jamais recalculees par ce module.
REFERENCE_RESULTS = {
    "poisson_simple": {"r": -0.0056, "se_b": 0.378961, "se_r": 0.071158, "df": 22},
    "xg_model": {"r": 0.0367, "se_r": 0.051121, "se_b": 0.316312, "df": 22},
}
CURRENT_N = 228
PER_SEASON = 114  # confirme empiriquement (PL-E15-POWER) : 30% d'une saison de 380 matchs
ALPHA_DEFAULT = 0.05


def _validate_se(se: float) -> None:
    if not math.isfinite(se) or se <= 0:
        raise ValueError(f"se doit etre fini et strictement positif, recu {se!r}.")


def _validate_power_target(power: float) -> None:
    if not (0.0 < power < 1.0):
        raise ValueError(f"power_cible doit etre dans (0,1), recu {power!r}.")


def _validate_effect(r_ref: float) -> None:
    if not math.isfinite(r_ref):
        raise ValueError(f"r_ref doit etre fini, recu {r_ref!r}.")


def _validate_n(n: int) -> None:
    if not isinstance(n, int) or n < 4:
        raise ValueError(f"n doit etre un entier >= 4, recu {n!r}.")


def current_power_direct_wald(r_ref: float, se_r: float, df: int, alpha: float = ALPHA_DEFAULT) -> float:
    """Puissance ACTUELLE (n=228, se_r deja estime) pour detecter un effet
    de reference r_ref, via un test de Wald DIRECT sur r (pas Fisher-z).

    Approximation normale standard, seuil critique t(df) (coherent avec la
    convention de `dyadic_correlation_ci`).
    """
    _validate_se(se_r)
    _validate_effect(r_ref)
    if not isinstance(df, int) or df < 1:
        raise ValueError(f"df doit etre un entier >= 1, recu {df!r}.")
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha doit etre dans (0,1), recu {alpha!r}.")

    t_crit = float(student_t.ppf(1 - alpha / 2, df))
    z = r_ref / se_r
    power = float(norm.cdf(z - t_crit) + norm.cdf(-z - t_crit))
    return power


def naive_fisher_z_se(n: int) -> float:
    """SE Fisher-z i.i.d. classique (PL-E15-POWER), 1/sqrt(n-3). Fournie
    uniquement pour calculer le facteur d'inflation kappa (comparaison),
    jamais utilisee seule pour un resultat final de cette phase."""
    _validate_n(n)
    return 1.0 / math.sqrt(n - 3)


def inflation_factor(se_r_dyadic: float, n: int = CURRENT_N) -> float:
    """kappa = se_r dyadique observe / SE Fisher-z naif au MEME n.
    kappa > 1 : l'incertitude dyadique est plus grande que l'hypothese
    i.i.d. (cas poisson_simple). kappa < 1 : plus petite (cas xg_model)."""
    _validate_se(se_r_dyadic)
    se_naive = naive_fisher_z_se(n)
    return se_r_dyadic / se_naive


def n_needed_naive_fisher_z(r_ref: float, power_target: float, alpha: float = ALPHA_DEFAULT) -> float:
    """Reproduit exactement la formule de PL-E15-POWER (Cohen 1988) :
    n = ((z_alpha/2 + z_power) / atanh(r_ref))**2 + 3. Fournie uniquement
    comme terme de comparaison explicite (section 'comparaison obligatoire
    avec Fisher-z'), jamais presentee seule comme un resultat de cette
    phase dyadique."""
    _validate_effect(r_ref)
    _validate_power_target(power_target)
    if r_ref == 0:
        raise ValueError("r_ref=0 : effet non detectable, n necessaire infini (non defini).")
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha doit etre dans (0,1), recu {alpha!r}.")
    z_crit = float(norm.ppf(1 - alpha / 2))
    z_power = float(norm.ppf(power_target))
    z_r = math.atanh(abs(r_ref))
    return ((z_crit + z_power) / z_r) ** 2 + 3


def n_needed_dyadic_extrapolated(
    r_ref: float,
    power_target: float,
    se_r_dyadic: float,
    current_n: int = CURRENT_N,
    alpha: float = ALPHA_DEFAULT,
) -> dict:
    """Extrapolation du n necessaire sous l'hypothese EXPLICITE (section 5
    du docstring du module) que le facteur d'inflation kappa reste
    constant quand n augmente - hypothese OPTIMISTE, signalee comme telle
    dans le resultat retourne (`hypothesis_optimistic`).

    Retourne un dict avec le n Fisher-z naif (comparaison), kappa, et le n
    dyadique extrapole - jamais un seul chiffre presente sans ces
    elements de tracabilite.
    """
    _validate_effect(r_ref)
    _validate_power_target(power_target)
    _validate_se(se_r_dyadic)
    _validate_n(current_n)

    n_naive = n_needed_naive_fisher_z(r_ref, power_target, alpha=alpha)
    kappa = inflation_factor(se_r_dyadic, n=current_n)
    n_dyadic = (n_naive - 3) * (kappa**2) + 3

    return {
        "r_ref": r_ref,
        "power_target": power_target,
        "n_naive_fisher_z": n_naive,
        "kappa": kappa,
        "n_dyadic_extrapolated": n_dyadic,
        "hypothesis_optimistic": True,
        "hypothesis_description": (
            "kappa suppose constant quand n augmente - hypothese optimiste : "
            "les nouveaux clusters (equipes) croissent plus lentement que les "
            "nouvelles observations (promotion/relegation ~3/saison vs ~114 "
            "matchs/saison), ce qui tend structurellement a FAIRE AUGMENTER "
            "kappa plutot qu'a le maintenir constant."
        ),
    }


def seasons_needed(n_target: float, current_n: int = CURRENT_N, per_season: int = PER_SEASON) -> int:
    """Traduit un n cible en nombre de saisons PL supplementaires
    necessaires (arrondi superieur), reutilisant exactement la cadence
    deja confirmee empiriquement par PL-E15-POWER (114 matchs TEST par
    saison)."""
    _validate_n(current_n)
    if not isinstance(per_season, int) or per_season < 1:
        raise ValueError(f"per_season doit etre un entier >= 1, recu {per_season!r}.")
    if not math.isfinite(n_target):
        raise ValueError(f"n_target doit etre fini, recu {n_target!r}.")
    extra = max(0.0, n_target - current_n)
    return int(math.ceil(extra / per_season))
