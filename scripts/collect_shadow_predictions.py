"""PHASE SHADOW-AUTO-1 : collecte groupee et securisee de predictions
shadow-mode, pour plusieurs fixtures Ligue 1 DEJA VERIFIEES, en une seule
invocation.

REUTILISE INTEGRALEMENT, SANS MODIFICATION :
- ``predict_match.run_prediction`` (R1+R2 + ``final_engine.orchestrator.
  run_match_decision``, INCHANGE) - charge via le meme mecanisme
  ``importlib`` que ``tests/unit/test_predict_match_shadow_cli.py``,
  jamais une reimplementation du pipeline de prediction ;
- ``shadow_mode.journal.record_prediction`` - la deduplication
  deterministe (``compute_prediction_id``) existe DEJA dans ce module et
  N'EST PAS reimplementee ici : ce script delegue entierement la
  detection de doublon a ``record_prediction`` (qui retourne
  ``already_existed=True`` plutot que d'ecrire une seconde fois) ;
- ``ligue1_kickoff_cet_conversion.CrossCheckedKickoff`` (PHASE SHADOW -
  EXTENSION CONTROLEE) - la verification croisee des horaires reste
  entierement en amont de ce script, jamais recalculee ici.

CE SCRIPT NE RECUPERE AUCUNE DONNEE DE CALENDRIER AUTOMATIQUEMENT - aucun
acces reseau, aucune nouvelle dependance. Chaque ``FixtureToCollect``
porte deja sa propre verification croisee, construite par l'appelant
(operateur humain, ou recherche web ponctuelle comme dans les phases
precedentes) via ``ligue1_kickoff_cet_conversion.build_cross_checked_kickoff``
- jamais devinee ou recalculee par ce module.

TRAITEMENT FIXTURE PAR FIXTURE : une erreur sur UNE fixture (equipe
inconnue, historique insuffisant, etc.) ne doit JAMAIS interrompre le
traitement des fixtures suivantes - chaque resultat est capture
individuellement, jamais une exception qui remonterait et annulerait le
reste de la collecte.

AUCUNE PREDICTION DE DEMONSTRATION N'EST JAMAIS ECRITE DANS LE JOURNAL
REEL PAR LES TESTS DE CE MODULE - tous les tests utilisent un
``journal_path`` temporaire explicite, jamais
``shadow_mode.journal.DEFAULT_JOURNAL_PATH``."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from sys_foot_quant.data_engine.market_odds.ligue1_kickoff_cet_conversion import (  # noqa: E402
    CrossCheckedKickoff,
)
from sys_foot_quant.final_engine.orchestrator import DECISION_OFFSET_HOURS  # noqa: E402
from sys_foot_quant.shadow_mode.journal import DEFAULT_JOURNAL_PATH, record_prediction  # noqa: E402

_PREDICT_MATCH_PATH = _REPO_ROOT / "scripts" / "predict_match.py"


def _load_predict_match():
    """Charge ``scripts/predict_match.py`` comme module - MEME mecanisme
    que ``tests/unit/test_predict_match_shadow_cli.py`` (deja existant,
    deja valide), jamais une reimplementation de son contenu."""
    spec = importlib.util.spec_from_file_location("predict_match_for_shadow_collection", _PREDICT_MATCH_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_STATUS_RECORDED = "recorded"
_STATUS_DUPLICATE = "duplicate"
_STATUS_UNVERIFIED = "unverified"
_STATUS_DEADLINE_PASSED = "deadline_passed"
_STATUS_ERROR = "error"


@dataclass(frozen=True)
class FixtureToCollect:
    """Une fixture DEJA VERIFIEE (verification croisee deja effectuee par
    l'appelant, jamais par ce module) a soumettre a la collecte.
    ``cross_checked_kickoff`` doit provenir de
    ``ligue1_kickoff_cet_conversion.build_cross_checked_kickoff`` - jamais
    une heure UTC construite a la main sans verification. Les cotes
    absentes doivent rester ``None`` (jamais inventees)."""

    competition: str
    season: str
    home_team: str
    away_team: str
    cross_checked_kickoff: CrossCheckedKickoff
    market_odds_over_2_5: float | None = None
    market_odds_under_2_5: float | None = None


@dataclass(frozen=True)
class CollectionResult:
    """Resultat trace pour UNE fixture - jamais une exception non
    capturee qui interromprait le traitement des autres fixtures."""

    home_team: str
    away_team: str
    status: str
    detail: str
    prediction_id: str | None = None


def collect_one(
    fixture: FixtureToCollect,
    now: datetime,
    decision_offset_hours: float = DECISION_OFFSET_HOURS,
    journal_path: Path = DEFAULT_JOURNAL_PATH,
    predict_match_module=None,
) -> CollectionResult:
    """Traite UNE fixture - ne leve JAMAIS, toute erreur est capturee et
    retournee comme ``CollectionResult(status="error", ...)``.

    Ordre des verifications (chacune peut arreter le traitement de CETTE
    fixture, jamais des autres) : (1) verification croisee concordante,
    (2) delai de decision non depasse, (3) resolution + construction de
    la prediction (deleguee a ``predict_match.run_prediction``, INCHANGE),
    (4) enregistrement + deduplication (deleguee a
    ``journal.record_prediction``, INCHANGE)."""
    predict_match = predict_match_module or _load_predict_match()
    home, away = fixture.home_team, fixture.away_team
    ck = fixture.cross_checked_kickoff

    if not ck.verified:
        return CollectionResult(home, away, _STATUS_UNVERIFIED, "Verification croisee des horaires non concordante (verified=False) - fixture exclue.")

    # run_prediction/record_prediction attendent un kickoff_utc NAIF (meme
    # convention que predict_match.parse_kickoff_utc) - CrossCheckedKickoff
    # le porte timezone-aware (UTC) ; conversion explicite, jamais une
    # reinterpretation silencieuse d'un autre fuseau.
    kickoff_utc_naive = ck.kickoff_utc.astimezone(timezone.utc).replace(tzinfo=None)
    decision_time = ck.kickoff_utc - timedelta(hours=decision_offset_hours)
    if decision_time <= now:
        return CollectionResult(
            home, away, _STATUS_DEADLINE_PASSED,
            f"decision_time ({decision_time.isoformat()}) deja depasse (now={now.isoformat()}).",
        )

    try:
        output = predict_match.run_prediction(
            fixture.competition, fixture.season, home, away, kickoff_utc_naive,
            market_odds=None, decision_offset_hours=decision_offset_hours,
        )
    except predict_match.PredictMatchError as exc:
        return CollectionResult(home, away, _STATUS_ERROR, f"PredictMatchError: {exc}")
    except Exception as exc:  # garde-fou large EXPLICITE - jamais une exception qui remonte silencieusement
        return CollectionResult(home, away, _STATUS_ERROR, f"{type(exc).__name__}: {exc}")

    view, already_existed = record_prediction(
        output, fixture.competition, fixture.season, home, away, kickoff_utc_naive, decision_offset_hours,
        fixture.market_odds_over_2_5, fixture.market_odds_under_2_5, journal_path,
    )
    if already_existed:
        return CollectionResult(home, away, _STATUS_DUPLICATE, "Observation identique deja presente (prediction_id deterministe) - non reecrite.", view["prediction_id"])
    return CollectionResult(home, away, _STATUS_RECORDED, "Observation enregistree.", view["prediction_id"])


def collect_many(
    fixtures: list[FixtureToCollect],
    now: datetime | None = None,
    decision_offset_hours: float = DECISION_OFFSET_HOURS,
    journal_path: Path = DEFAULT_JOURNAL_PATH,
) -> list[CollectionResult]:
    """Traite CHAQUE fixture independamment - une erreur sur l'une
    n'interrompt jamais le traitement des suivantes. Charge
    ``predict_match`` UNE SEULE FOIS pour tout le lot (performance),
    jamais une nouvelle logique de prediction."""
    now = now or datetime.now(timezone.utc)
    predict_match = _load_predict_match()
    return [collect_one(f, now, decision_offset_hours, journal_path, predict_match) for f in fixtures]


def format_collection_report(results: list[CollectionResult]) -> str:
    """Rapport humain, lecture seule - ne recalcule jamais rien, affiche
    uniquement les champs deja presents dans chaque ``CollectionResult``."""
    lines = [f"Collecte shadow : {len(results)} fixture(s) traitee(s)."]
    for r in results:
        pid = f" prediction_id={r.prediction_id}" if r.prediction_id else ""
        lines.append(f"  [{r.status:16s}] {r.home_team} - {r.away_team} :: {r.detail}{pid}")
    counts: dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    lines.append("Resume : " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    return "\n".join(lines)
