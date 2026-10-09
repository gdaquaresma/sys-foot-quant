"""Conversion CET/CEST MANUELLE et ISOLEE de l'heure locale OpenFootball
en UTC - perimetre STRICTEMENT LIMITE a la Ligue 1 (PHASE SHADOW -
EXTENSION CONTROLEE, autorisation explicite).

NE MODIFIE NI N'ETEND `future_fixture_catalog.py`/`openfootball_calendar.py` -
leur champ `kickoff_utc` reste `None` par design pour toute autre
competition/usage (decision deja actee, non rouverte ici). Cette fonction
est un outil MANUEL, appele explicitement par l'operateur pour UN match a
la fois, JAMAIS une conversion automatique generalisee a toute une
competition, a d'autres competitions, ni une ecriture dans le catalogue
existant.

REGLE DE CONVERSION : heure d'ete europeenne, fixee par le droit de
l'Union Europeenne (directive 2000/84/CE, transposee identiquement par
chaque Etat membre, dont la France) - CET (UTC+1) sauf durant l'heure
d'ete europeenne CEST (UTC+2), du dernier dimanche de mars (2h00 CET ->
3h00 CEST) au dernier dimanche d'octobre (3h00 CEST -> 2h00 CET). Dates de
transition CALCULEES ET FIGEES EXPLICITEMENT ci-dessous pour les annees
couvertes par le calendrier Ligue 1 pertinent - jamais une formule
generale non verifiee a l'infini.

REFUS EXPLICITE (jamais une conversion silencieuse) :
- kickoff_local_naive deja timezone-aware (ne doit jamais etre reinterprete) ;
- annee hors de la table de transitions explicite ci-dessous ;
- date tombant le jour meme du changement d'heure (heure locale ambigue
  ou inexistante ce jour-la) ;
- `fixture_date` et la date de `kickoff_local_naive` qui divergent
  (incoherence de donnees, jamais corrigee silencieusement).

VERIFICATION CROISEE OBLIGATOIRE : `build_cross_checked_kickoff` exige
explicitement une seconde heure locale (d'une source independante,
fournie par l'operateur - jamais recuperee automatiquement par ce
module) ; le resultat n'est marque `verified=True` que si les deux
heures locales concordent EXACTEMENT. Une concordance entre deux sources
non officielles reste signalee comme telle (`officially_confirmed=False`)
- jamais presentee comme une confirmation officielle.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone


class AmbiguousOrInvalidKickoffError(ValueError):
    """Levee quand la conversion ne peut pas etre realisee de maniere sure."""


# Dates de transition DST europeennes (dernier dimanche de mars / octobre),
# calculees et figees explicitement - jamais une formule generale non
# verifiee. Couvre les saisons Ligue 1 pertinentes pour ce perimetre.
_DST_TRANSITIONS: dict[int, tuple[date, date]] = {
    2025: (date(2025, 3, 30), date(2025, 10, 26)),
    2026: (date(2026, 3, 29), date(2026, 10, 25)),
    2027: (date(2027, 3, 28), date(2027, 10, 31)),
}


def convert_ligue1_local_kickoff_to_utc(fixture_date: date, kickoff_local_naive: datetime) -> datetime:
    """Convertit UN horaire local Ligue 1 (France metropolitaine, heure
    naive) en UTC. Leve `AmbiguousOrInvalidKickoffError` plutot que de
    deviner dans tout cas non couvert explicitement (voir docstring du
    module)."""
    if kickoff_local_naive.tzinfo is not None:
        raise AmbiguousOrInvalidKickoffError(
            "kickoff_local_naive doit etre naif (sans fuseau) - une valeur deja timezone-aware ne doit jamais etre reinterpretee."
        )
    if kickoff_local_naive.date() != fixture_date:
        raise AmbiguousOrInvalidKickoffError(
            f"fixture_date ({fixture_date}) et la date de kickoff_local_naive ({kickoff_local_naive.date()}) divergent - refus plutot que correction silencieuse."
        )
    if fixture_date.year not in _DST_TRANSITIONS:
        raise AmbiguousOrInvalidKickoffError(
            f"Annee {fixture_date.year} non couverte par la table de transitions DST explicite - refus plutot que calcul non verifie."
        )

    spring, autumn = _DST_TRANSITIONS[fixture_date.year]
    if fixture_date in (spring, autumn):
        raise AmbiguousOrInvalidKickoffError(
            f"{fixture_date} est le jour du changement d'heure europeen - heure locale ambigue ou inexistante, refus explicite."
        )

    is_cest = spring < fixture_date < autumn
    offset_hours = 2 if is_cest else 1
    return (kickoff_local_naive - timedelta(hours=offset_hours)).replace(tzinfo=timezone.utc)


def timezone_label_for(fixture_date: date) -> str:
    """Retourne 'CEST' ou 'CET' pour une date deja validee par
    `convert_ligue1_local_kickoff_to_utc` (meme table de transitions)."""
    spring, autumn = _DST_TRANSITIONS[fixture_date.year]
    return "CEST" if spring < fixture_date < autumn else "CET"


@dataclass(frozen=True)
class CrossCheckedKickoff:
    """Resultat trace d'une conversion + verification croisee - conserve
    la source, l'horaire initial, le fuseau, l'heure UTC calculee et le
    resultat de la verification, conformement a l'exigence de
    tracabilite."""

    fixture_date: date
    kickoff_local_naive: datetime
    timezone_label: str
    kickoff_utc: datetime
    source_local_time: str
    cross_check_source: str
    cross_check_local_time: datetime
    cross_check_kickoff_matches: bool
    verified: bool
    officially_confirmed: bool


def build_cross_checked_kickoff(
    fixture_date: date,
    kickoff_local_naive: datetime,
    source_local_time: str,
    cross_check_source: str,
    cross_check_local_time: datetime,
    officially_confirmed: bool = False,
) -> CrossCheckedKickoff:
    """Construit un `CrossCheckedKickoff` tracable. `verified` n'est
    `True` que si `cross_check_local_time == kickoff_local_naive` -
    toute divergence doit empecher tout usage ulterieur (a l'appelant de
    refuser l'enregistrement d'une prediction shadow si `verified` est
    `False`). `officially_confirmed` doit etre laisse a `False` sauf si
    une source officiellement accessible a ete verifiee directement -
    jamais deduit d'une simple convergence de sources non officielles."""
    kickoff_utc = convert_ligue1_local_kickoff_to_utc(fixture_date, kickoff_local_naive)
    timezone_label = timezone_label_for(fixture_date)
    matches = cross_check_local_time == kickoff_local_naive

    return CrossCheckedKickoff(
        fixture_date=fixture_date,
        kickoff_local_naive=kickoff_local_naive,
        timezone_label=timezone_label,
        kickoff_utc=kickoff_utc,
        source_local_time=source_local_time,
        cross_check_source=cross_check_source,
        cross_check_local_time=cross_check_local_time,
        cross_check_kickoff_matches=matches,
        verified=matches,
        officially_confirmed=officially_confirmed,
    )
