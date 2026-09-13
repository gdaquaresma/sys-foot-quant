"""Structure formelle du snapshot manuel de cotes (design valide, voir
``snapshot_engine/__init__.py``).

Garantie centrale, exigee explicitement et implementee ICI (pas
seulement documentee) : ``capture_timestamp`` ne peut JAMAIS etre une
valeur fournie par l'appelant. La seule facon de construire un
``OddsSnapshot`` en production est ``create_snapshot()``, qui n'accepte
aucun parametre ``capture_timestamp`` et appelle systematiquement
l'horloge systeme (``datetime.now(timezone.utc)``). La validation
``capture_timestamp < kickoff_utc`` vit dans ``OddsSnapshot.__post_init__``
- donc meme une construction directe du dataclass (utile en test pour
verifier le refus d'un cas limite) ne peut jamais produire un snapshot
dont l'invariant temporel est viole : l'invariant est une propriete du
TYPE, pas d'une seule fonction d'entree.

``decision_time`` n'est PAS un champ separe stocke : c'est une propriete
qui renvoie toujours ``capture_timestamp`` - une divergence entre les
deux est donc structurellement impossible, pas seulement validee."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

_TARGET_LINE_OVER_UNDER_2_5 = 2.5
_OVER = "OVER"
_UNDER = "UNDER"


class SnapshotValidationError(ValueError):
    """Refus explicite d'un snapshot ou d'une observation incoherente -
    jamais un defaut silencieux ni une correction automatique."""


def _require_utc_aware(value: datetime, field_name: str) -> None:
    """Meme garde-fou que partout ailleurs dans ce projet
    (``polymarket/trades.py::_parse_timestamp``,
    ``validate_thestatsapi.py::_require_aware``) : un timestamp naif ou
    dans un fuseau autre qu'UTC est un risque de fuite/decalage PIT,
    jamais suppose UTC silencieusement."""
    if value.tzinfo is None:
        raise SnapshotValidationError(f"{field_name} doit etre timezone-aware (recu un datetime naif : {value!r}).")
    if value.utcoffset().total_seconds() != 0:
        raise SnapshotValidationError(f"{field_name} doit etre en UTC (offset non nul recu : {value!r}).")


@dataclass(frozen=True)
class OddsObservation:
    """Une observation unique : un bookmaker, un marche, une selection,
    une cote - jamais une moyenne, jamais une valeur interpolee."""

    bookmaker: str
    market: str
    selection: str
    odds: float
    line: float | None = None

    def __post_init__(self) -> None:
        if not self.bookmaker or not self.bookmaker.strip():
            raise SnapshotValidationError("bookmaker ne peut pas etre vide.")
        if not self.market or not self.market.strip():
            raise SnapshotValidationError("market ne peut pas etre vide.")
        if not self.selection or not self.selection.strip():
            raise SnapshotValidationError("selection ne peut pas etre vide.")
        # Meme garde que market_engine.overround.validate_odds (reutilisee
        # telle quelle par le pont vers R3, voir extract_over_under_2_5) -
        # dupliquee ici uniquement pour refuser une observation invalide
        # DES sa creation, avant meme d'atteindre R3.
        if not (self.odds > 1.0) or self.odds != self.odds or self.odds in (float("inf"), float("-inf")):
            raise SnapshotValidationError(f"odds invalide pour '{self.bookmaker}/{self.market}/{self.selection}' : {self.odds!r} (doit etre > 1.0 et finie).")


@dataclass(frozen=True)
class OddsSnapshot:
    """Snapshot immuable de cotes observees pour UN match, a UN instant
    unique (``capture_timestamp``, genere par le systeme - voir
    ``create_snapshot``). ``decision_time`` est TOUJOURS
    ``capture_timestamp`` (propriete, jamais un champ separe pouvant
    diverger)."""

    competition: str
    season: str
    home_team: str
    away_team: str
    kickoff_utc: datetime
    capture_timestamp: datetime
    observations: tuple[OddsObservation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.home_team == self.away_team:
            raise SnapshotValidationError(f"home_team et away_team doivent etre distincts ({self.home_team!r}).")
        _require_utc_aware(self.kickoff_utc, "kickoff_utc")
        _require_utc_aware(self.capture_timestamp, "capture_timestamp")
        if not self.observations:
            raise SnapshotValidationError("Un snapshot doit contenir au moins une observation.")
        # LE garde-fou temporel central du design valide : refuse
        # explicitement capture_timestamp >= kickoff_utc (jamais une
        # cote "capturee" pendant ou apres le match).
        if self.capture_timestamp >= self.kickoff_utc:
            raise SnapshotValidationError(
                f"capture_timestamp ({self.capture_timestamp.isoformat()}) doit etre strictement "
                f"anterieur a kickoff_utc ({self.kickoff_utc.isoformat()}) - "
                f"{'egal au' if self.capture_timestamp == self.kickoff_utc else 'posterieur au'} coup d'envoi refuse."
            )

    @property
    def decision_time(self) -> datetime:
        """Toujours egal a ``capture_timestamp`` (design valide) - une
        propriete, jamais un champ stocke separement, pour rendre toute
        divergence structurellement impossible plutot que seulement
        validee."""
        return self.capture_timestamp


def create_snapshot(
    competition: str,
    season: str,
    home_team: str,
    away_team: str,
    kickoff_utc: datetime,
    observations: list[OddsObservation],
    *,
    _now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> OddsSnapshot:
    """SEUL point d'entree destine a la production. N'accepte JAMAIS de
    parametre ``capture_timestamp`` : il est TOUJOURS lu depuis l'horloge
    systeme au moment de l'appel. ``_now_fn`` n'existe que pour permettre
    aux tests d'injecter une horloge deterministe - jamais expose comme
    une option CLI ou un parametre public destine a un appelant reel (le
    prefixe ``_`` le marque explicitement comme interne)."""
    return OddsSnapshot(
        competition=competition,
        season=season,
        home_team=home_team,
        away_team=away_team,
        kickoff_utc=kickoff_utc,
        capture_timestamp=_now_fn(),
        observations=tuple(observations),
    )


def decision_offset_hours_from_snapshot(snapshot: OddsSnapshot) -> float:
    """Convertit le ``decision_time`` du snapshot (= capture_timestamp)
    dans le parametre ``decision_offset_hours`` DEJA accepte par
    ``final_engine.orchestrator.run_match_decision`` et
    ``scripts/predict_match.py`` (jamais un nouveau parametre du moteur) :
    ``decision_time = kickoff_utc - decision_offset_hours``, donc
    ``decision_offset_hours = (kickoff_utc - decision_time) en heures``.
    Toujours strictement positif : garanti par la validation de
    ``OddsSnapshot.__post_init__`` (capture_timestamp < kickoff_utc)."""
    delta = snapshot.kickoff_utc - snapshot.decision_time
    return delta.total_seconds() / 3600.0


def kickoff_utc_naive_for_r3(snapshot: OddsSnapshot) -> datetime:
    """Pont explicite vers la convention EXISTANTE de
    ``scripts/predict_match.py`` (``parse_kickoff_utc`` : naif, deja en
    UTC - jamais une nouvelle convention). La conversion est sans perte
    car ``OddsSnapshot.__post_init__`` a deja garanti que ``kickoff_utc``
    est explicitement UTC avant que ce module ne retire l'information de
    fuseau - jamais une reinterpretation silencieuse d'un fuseau non
    verifie."""
    return snapshot.kickoff_utc.replace(tzinfo=None)


@dataclass(frozen=True)
class OverUnderExtraction:
    """Paire Over/Under 2.5 ACCOMPAGNEE de sa provenance exacte - pour la
    tracabilite du journal Shadow Mode (bookmaker/marche/ligne), jamais
    pour un nouveau calcul. ``market``/``line`` sont ici la
    representation EXPLICITE demandee (``"OU"``/``2.5``), distincte du
    libelle interne libre (``over_under``/``over_under_2_5``/...) accepte
    en entree par ``OddsObservation.market``."""

    market_odds: dict[str, float]
    bookmaker: str
    market: str
    line: float


def extract_over_under_2_5_with_source(snapshot: OddsSnapshot, bookmaker: str | None = None) -> OverUnderExtraction:
    """Meme extraction/memes refus que ``extract_over_under_2_5`` (qui
    delegue desormais ICI) - ajoute uniquement la provenance (bookmaker
    resolu, marche/ligne explicites) necessaire a la tracabilite, jamais
    un nouveau calcul ni une nouvelle regle de selection."""
    candidates = [
        obs
        for obs in snapshot.observations
        if obs.market.strip().lower() in ("over_under", "over_under_2_5", "ou25", "o/u")
        and obs.line is not None
        and obs.line == _TARGET_LINE_OVER_UNDER_2_5
    ]
    if bookmaker is not None:
        candidates = [obs for obs in candidates if obs.bookmaker == bookmaker]

    if not candidates:
        raise SnapshotValidationError(
            "Aucune observation Over/Under 2.5 exploitable dans ce snapshot"
            + (f" pour le bookmaker {bookmaker!r}." if bookmaker else ".")
        )

    distinct_bookmakers = sorted({obs.bookmaker for obs in candidates})
    if len(distinct_bookmakers) > 1:
        raise SnapshotValidationError(
            f"Plusieurs bookmakers offrent Over/Under 2.5 dans ce snapshot ({distinct_bookmakers}) - "
            "precisez lequel utiliser (parametre bookmaker) plutot que d'en choisir un implicitement."
        )

    over_obs = [obs for obs in candidates if obs.selection.strip().upper() == _OVER]
    under_obs = [obs for obs in candidates if obs.selection.strip().upper() == _UNDER]
    if len(over_obs) != 1 or len(under_obs) != 1:
        raise SnapshotValidationError(
            f"Attendu exactement une observation OVER et une UNDER pour Over/Under 2.5 "
            f"(trouve {len(over_obs)} OVER, {len(under_obs)} UNDER)."
        )
    return OverUnderExtraction(
        market_odds={"Over": over_obs[0].odds, "Under": under_obs[0].odds},
        bookmaker=distinct_bookmakers[0],
        market="OU",
        line=_TARGET_LINE_OVER_UNDER_2_5,
    )


def extract_over_under_2_5(snapshot: OddsSnapshot, bookmaker: str | None = None) -> dict[str, float]:
    """Extrait la paire Over/Under 2.5 exploitable par le moteur EXISTANT
    (``run_match_decision(market_odds_over_2_5=..., market_odds_under_2_5=...)``,
    INCHANGE) - jamais un nouveau calcul, uniquement une lecture filtree
    du snapshot. INCHANGE (signature et comportement identiques) - delegue
    desormais a ``extract_over_under_2_5_with_source`` pour eviter toute
    duplication de la logique de filtrage/refus d'ambiguite."""
    return extract_over_under_2_5_with_source(snapshot, bookmaker=bookmaker).market_odds
