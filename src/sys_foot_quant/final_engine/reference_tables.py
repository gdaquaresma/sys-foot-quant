"""Tables de reference FIGEES issues d'E4/E11/E15 - jamais recalculees en
ligne (docs/final_engine_specification.md sections 8, 9, 12). Etendre une
de ces tables a un nouveau championnat ou un nouveau seuil necessite la
repetition du diagnostic dedie (E15-like), jamais une ligne ajoutee sans
experience.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Discrimination (E4, E11, E15) - VALIDE SCIENTIFIQUEMENT pour les valeurs
# listees, jamais un recalcul en direct d'un score de discrimination.
# ---------------------------------------------------------------------------

DISCRIMINATION_DEMONTREE = "DEMONTREE"
DISCRIMINATION_NON_DEMONTREE = "NON_DEMONTREE"
DISCRIMINATION_NON_EVALUEE = "NON_EVALUEE"

# Correlation esperance de buts / total reel demontree en Liga et Ligue 1
# (E4 tranches fixes + quintiles, E11 stabilite par championnat) ; absente
# en Premier League, confirmee 3 fois independamment (E4, E11, E15 -
# diagnostic dedie, verdict "ABSENCE DE SIGNAL CONFIRMEE MAIS INEXPLIQUEE").
#
# Les deux variantes "ligue_1" (nom lisible normalise, ex. "Ligue 1") et
# "ligue1" (identifiant interne EXACT utilise par tout le pipeline de
# donnees reelles depuis E1 - _SEASONS/_EXPECTED_MATCHES de
# scripts/run_stage8_diagnostic_total_goals_over_under.py, jamais "ligue_1")
# sont toutes deux presentes - un appel avec la cle interne brute ne doit
# jamais retomber silencieusement sur NON_EVALUEE par un simple defaut
# d'orthographe (bug detecte et corrige en Phase D, avant toute execution
# reelle - voir docs/operational_validation_report.md).
_DISCRIMINATION_TABLE: dict[str, str] = {
    "liga": DISCRIMINATION_DEMONTREE,
    "ligue_1": DISCRIMINATION_DEMONTREE,
    "ligue1": DISCRIMINATION_DEMONTREE,
    "premier_league": DISCRIMINATION_NON_DEMONTREE,
}


def _normalize_competition(competition: str) -> str:
    return competition.strip().lower().replace(" ", "_").replace("-", "_")


def discrimination_status(competition: str) -> str:
    """Statut de discrimination FIGE pour ``competition``. Tout championnat
    absent de la table (jamais audite par un diagnostic E15-like) recoit
    ``NON_EVALUEE`` - position par defaut prudente, jamais optimiste par
    defaut (docs/final_engine_specification.md section 9, "regle
    d'extension explicite")."""
    return _DISCRIMINATION_TABLE.get(_normalize_competition(competition), DISCRIMINATION_NON_EVALUEE)


# ---------------------------------------------------------------------------
# Calibration par seuil O/U (E11, E14) - VALIDE SCIENTIFIQUEMENT.
# ---------------------------------------------------------------------------

CALIBRATION_OK = "OK"
CALIBRATION_ZONE_BIASED = "ZONE_BIAISEE_NON_CORRIGEE"
CALIBRATION_INSUFFICIENT_VALIDATION = "INSUFFICIENT_VALIDATION"

# Seuils dont la calibration a ete testee et confirmee globalement fiable
# hors zone biaisee (E2/E3/E7/E8/E11/E14).
VALIDATED_THRESHOLDS: tuple[float, ...] = (1.5, 2.5, 3.5)

# Seuils calculables (memes proprietes structurelles, section 6) mais dont
# la calibration n'a jamais ete validee avec la meme robustesse (E11 : masse
# concentree sur 2-3 tranches extremes, pentes de Cox peu fiables).
UNVALIDATED_THRESHOLDS: tuple[float, ...] = (0.5, 4.5)

# Zone de sur-confiance demontree sur les trois modeles pour Over 2.5
# (E11 section 2, biais IC95% entierement <0) - E14 a tente une correction
# ciblee et a ete REJETEE (gate de coherence viole substantiellement) :
# cette zone reste NON CORRIGEE, uniquement flaguee.
BIASED_ZONE_THRESHOLD = 2.5
BIASED_ZONE_LOW = 0.6
BIASED_ZONE_HIGH = 0.7  # borne haute exclusive, identique a la tranche E11


def calibration_status_for(threshold: float, probability: float) -> str:
    """Statut de calibration FIGE pour ``threshold`` a la valeur de
    probabilite ``probability``. Leve ``ValueError`` pour tout seuil hors
    des 5 seuils officiels du moteur (0.5/1.5/2.5/3.5/4.5) - jamais un
    statut invente pour un seuil non prevu par la specification."""
    if threshold in UNVALIDATED_THRESHOLDS:
        return CALIBRATION_INSUFFICIENT_VALIDATION
    if threshold not in VALIDATED_THRESHOLDS:
        raise ValueError(
            f"Seuil non supporte par le moteur final : {threshold} "
            f"(seuils officiels : {sorted(VALIDATED_THRESHOLDS + UNVALIDATED_THRESHOLDS)})."
        )
    if threshold == BIASED_ZONE_THRESHOLD and BIASED_ZONE_LOW <= probability < BIASED_ZONE_HIGH:
        return CALIBRATION_ZONE_BIASED
    return CALIBRATION_OK
