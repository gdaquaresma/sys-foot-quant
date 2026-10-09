"""PHASE SHADOW-AUTO-2 : decouverte automatique de candidats de fixtures
Ligue 1 a partir du catalogue OpenFootball DEJA INTEGRE
(``future_fixture_catalog.build_future_fixtures``, INCHANGE) - reduit la
saisie manuelle a UNE seule chose restante : confirmer l'horaire par
recoupement independant, JAMAIS une automatisation complete.

DISTINCTION STRICTE, JAMAIS MELANGEE (demande explicite SHADOW-AUTO-2) :

1. HORAIRE DECOUVERT : ``kickoff_local_naive`` tel que publie par
   OpenFootball (GitHub, deja integre) - AUCUNE garantie de fiabilite en
   soi. C'est pourquoi ``DraftFixtureCandidate`` n'est PAS un
   ``CrossCheckedKickoff`` et NE PEUT JAMAIS etre transmis directement a
   ``collect_shadow_predictions`` sans etape intermediaire explicite.
2. HORAIRE RECOUPE : obtenu UNIQUEMENT en appelant explicitement
   ``ligue1_kickoff_cet_conversion.build_cross_checked_kickoff`` avec une
   SECONDE source independante (recherche web ou autre) - toujours une
   etape manuelle separee, APRES ce module, jamais automatisee ici.
3. HORAIRE OFFICIELLEMENT CONFIRME : jamais produit automatiquement, ni
   ici ni dans ``build_cross_checked_kickoff`` (``officially_confirmed``
   reste ``False`` par defaut partout dans ce projet).

CE MODULE NE FAIT AUCUN APPEL RESEAU EXTERNE - ``build_future_fixtures``
lit uniquement les fichiers OpenFootball DEJA PRESENTS dans le depot
(obtenus via GitHub, deja integre avant cette phase). Aucune nouvelle
dependance, aucune modification de ``future_fixture_catalog.py`` ni de
``final_engine/``.

COUVERTURE REELLE CONSTATEE (audit read-only prealable a cette
implementation, Ligue 1, catalogue actuel) : 261 fixtures non jouees,
toutes resolues (noms d'equipe connus), mais SEULEMENT 69 portent deja
une heure locale (``kickoff_local_naive``) - les 192 autres sont en etat
C (date seule, aucune heure publiee) et ne peuvent structurellement pas
etre traitees par ce module (ni par aucun autre, faute d'heure a
convertir)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from sys_foot_quant.data_engine.market_odds.future_fixture_catalog import build_future_fixtures  # noqa: E402
from sys_foot_quant.shadow_mode.journal import DEFAULT_JOURNAL_PATH, load_journal  # noqa: E402


@dataclass(frozen=True)
class DraftFixtureCandidate:
    """HORAIRE DECOUVERT uniquement - PAS un horaire recoupe ni confirme.
    Volontairement SANS champ ``verified``/``officially_confirmed`` (a la
    difference de ``CrossCheckedKickoff``) pour qu'il soit structurellement
    impossible de le confondre avec un horaire deja verifie."""

    competition: str
    season: str
    home_team: str
    away_team: str
    fixture_date: date
    kickoff_local_naive: datetime
    source: str = "OpenFootball (GitHub, deja integre)"


def _already_in_journal(home: str, away: str, fixture_date: date, journal_path: Path) -> bool:
    """Pre-filtre heuristique UNIQUEMENT (reduit le travail de
    recoupement a refaire) - PAS le dedup final/autoritaire, qui reste
    entierement ``journal.record_prediction`` via ``prediction_id``
    (deterministe, deja existant, jamais reimplemente ici)."""
    for entry in load_journal(journal_path):
        if entry["home_team"] != home or entry["away_team"] != away:
            continue
        try:
            entry_date = datetime.fromisoformat(entry["kickoff_utc"]).date()
        except (KeyError, ValueError):
            continue
        if abs((entry_date - fixture_date).days) <= 1:
            return True
    return False


def draft_candidates(
    now: date,
    horizon_days: int = 21,
    competition: str = "ligue1",
    season: str = "2026_27",
    journal_path: Path = DEFAULT_JOURNAL_PATH,
) -> list[DraftFixtureCandidate]:
    """Decouvre les fixtures ``competition`` non jouees, resolues, avec
    une heure locale deja publiee par OpenFootball, dans la fenetre
    [``now``, ``now + horizon_days``], en excluant celles deja presentes
    dans le journal (pre-filtre heuristique, voir ``_already_in_journal``).

    NE RETOURNE JAMAIS un horaire recoupe ou confirme (voir docstring du
    module) - uniquement decouvert, a recouper explicitement ensuite."""
    horizon_end = now + timedelta(days=horizon_days)
    fixtures = build_future_fixtures(competition)

    candidates: list[DraftFixtureCandidate] = []
    for f in fixtures:
        if f.is_played:
            continue
        if f.resolution_status != "resolved":
            continue
        if f.kickoff_local_naive is None:
            continue
        if not (now <= f.fixture_date <= horizon_end):
            continue
        if _already_in_journal(f.home_team, f.away_team, f.fixture_date, journal_path):
            continue
        candidates.append(
            DraftFixtureCandidate(
                competition=competition,
                season=season,
                home_team=f.home_team,
                away_team=f.away_team,
                fixture_date=f.fixture_date,
                kickoff_local_naive=f.kickoff_local_naive,
            )
        )
    return candidates


def format_draft_report(candidates: list[DraftFixtureCandidate]) -> str:
    """Rapport lecture seule - rappelle explicitement que ce sont des
    horaires DECOUVERTS, jamais recoupes ni confirmes."""
    lines = [
        f"{len(candidates)} candidat(s) decouvert(s) (OpenFootball) - "
        "HORAIRE NON RECOUPE, recoupement independant requis avant toute collecte :"
    ]
    for c in candidates:
        lines.append(f"  {c.home_team} - {c.away_team} :: {c.fixture_date} {c.kickoff_local_naive.time()} (local, source={c.source})")
    return "\n".join(lines)
