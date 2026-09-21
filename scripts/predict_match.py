"""CLI de production (MVP / shadow mode) : lance une decision pre-match
complete pour UN match reel (deja joue, pour verification, ou reellement
futur) en assemblant R1 + R2 deja valides et
``final_engine.orchestrator.run_match_decision`` (INCHANGE) :

    R2 (data_engine.market_odds.future_match_dataset) -> goals_train_df/xg_train_df
    R1 (calibration_engine.calibration_dataset)        -> calibration_df_by_model
    + cote(s) de marche fournies EXPLICITEMENT en ligne de commande
        -> final_engine.orchestrator.run_match_decision()

AUCUNE nouvelle logique de modelisation, de calibration ou de gate :
``final_engine/`` n'est pas modifie. AUCUNE nouvelle collecte de donnees -
le corpus historique reste exactement celui deja utilise par
E1-E16/R1/R2 (``research/xg_feasibility/runs/*_datesData.json``). AUCUNE
recuperation automatique de cote : Football-Data.co.uk ne publie que des
cotes de matchs DEJA JOUES (jamais de cote pre-match pour un match
reellement futur), une "recuperation automatique" serait donc soit
inutilisable pour le cas d'usage vise (match futur), soit une nouvelle
couche fragile pour le seul cas d'un match deja joue - la cote est donc
TOUJOURS un parametre CLI explicite (``--market-odds-over-2-5``/
``--market-odds-under-2-5``, ou ``--odds-snapshot-file`` - voir
``snapshot_engine``), jamais une valeur allee chercher seule. Aucun
fournisseur externe : ``--odds-snapshot-file`` encapsule une saisie
MANUELLE structuree (voir ``research/free_historical_odds_sources.md``
pour l'abandon de la recherche d'un fournisseur PIT externe), avec
``decision_time = capture_timestamp`` genere par le systeme au moment
de l'appel - jamais une valeur fournie par l'utilisateur.

Decoupage (competition, saison) -> fichier IDENTIQUE a
``scripts/run_stage8_diagnostic_total_goals_over_under.py`` (``_SEASONS``)
pour ``2024_25``/``2025_26`` - meme choix scientifique deja verrouille par
E7/E8 : chaque flux chronologique reste borne a UNE seule competition,
jamais un tri global qui melangerait des competitions distinctes
(``calibration_engine.calibration_dataset``, docstring - c'est la ou porte
reellement la regle "jamais de melange", pas sur les saisons d'une meme
competition). Duplication minimale et deliberee du mapping, meme
convention que le reste du projet pour les scripts isoles - jamais une
nouvelle source de donnees.

Etape I-2 (saison courante) : ``2026_27`` est la SEULE entree qui agrege
plusieurs fichiers - historique long terme (2024/25+2025/26) + saison
courante deja jouee (2026/27), tous Ligue 1 (meme competition, flux
chronologique unique, coherent avec la regle ci-dessus) - via
``_CURRENT_SEASON_SOURCES``/``build_real_match_records_multi_season``
(INCHANGEE, deja testee par ``multi_season_dataset``). ``2024_25``/
``2025_26`` restent EXACTEMENT mono-fichier, comportement et structure de
``_SEASONS`` inchanges (contrainte imperative de l'audit I-1B : ne jamais
elargir automatiquement l'historique d'une saison deja close).

Resolution d'equipe : accepte directement un nom Understat (recherche
directe dans le corpus charge) ou, a defaut, un nom Football-Data (traduit
via ``data_engine.market_odds.team_mapping.resolve_understat_name``,
INCHANGE) - reutilise integralement
``data_engine.market_odds.future_match_dataset.build_understat_team_id_by_name``
(R2), jamais une nouvelle table de correspondance.

Usage:
    uv run python scripts/predict_match.py \\
        --competition liga --season 2024_25 \\
        --home-team "Real Madrid" --away-team Barcelona \\
        --kickoff-utc 2025-05-11T19:00:00 \\
        --market-odds-over-2-5 1.85 --market-odds-under-2-5 1.95

Sans cote de marche (mode projection seule, Niveaux A-C uniquement) :
    uv run python scripts/predict_match.py \\
        --competition liga --season 2024_25 \\
        --home-team "Real Madrid" --away-team Barcelona \\
        --kickoff-utc 2025-05-11T19:00:00

Avec un snapshot manuel structure (voir snapshot_engine.schema) :
    uv run python scripts/predict_match.py \\
        --competition liga --season 2024_25 \\
        --home-team "Real Madrid" --away-team Barcelona \\
        --kickoff-utc 2025-05-11T19:00:00 \\
        --odds-snapshot-file mon_snapshot.json
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.backtesting_engine.real_data_walk_forward import (  # noqa: E402
    RealMatchRecord,
    build_real_match_records,
)
from sys_foot_quant.calibration_engine.calibration_dataset import (  # noqa: E402
    build_calibration_dataframe,
    split_calibration_df_by_model,
)
from sys_foot_quant.data_engine.market_odds.future_match_dataset import (  # noqa: E402
    build_match_train_dataframes,
    build_understat_team_id_by_name,
)
from sys_foot_quant.data_engine.market_odds.matching import build_understat_keys  # noqa: E402
from sys_foot_quant.data_engine.market_odds.multi_season_dataset import (  # noqa: E402
    build_real_match_records_multi_season,
)
from sys_foot_quant.data_engine.market_odds.team_mapping import resolve_understat_name  # noqa: E402
from sys_foot_quant.final_engine.orchestrator import DECISION_OFFSET_HOURS, run_match_decision  # noqa: E402
from sys_foot_quant.final_engine.types import MatchDecisionOutput  # noqa: E402
from sys_foot_quant.market_engine.overround import validate_odds  # noqa: E402
from sys_foot_quant.shadow_mode.journal import DEFAULT_JOURNAL_PATH as SHADOW_DEFAULT_JOURNAL_PATH  # noqa: E402
from sys_foot_quant.shadow_mode.journal import record_prediction as record_shadow_prediction  # noqa: E402
from sys_foot_quant.snapshot_engine.schema import (  # noqa: E402
    OddsObservation,
    SnapshotValidationError,
    create_snapshot,
    decision_offset_hours_from_snapshot,
    extract_over_under_2_5_with_source,
)

app = typer.Typer(add_completion=False)

# IDENTIQUE au mapping deja utilise par
# scripts/run_stage8_diagnostic_total_goals_over_under.py (``_SEASONS``) -
# duplication volontaire et minimale (meme convention que le reste du
# projet pour les scripts isoles), jamais une nouvelle source de donnees.
_SEASONS: dict[str, dict[str, tuple[str, Path]]] = {
    "2024_25": {
        "ligue1": ("Ligue_1", Path("research/xg_feasibility/runs/ligue1_2024_datesData.json")),
        "premier_league": ("EPL", Path("research/xg_feasibility/runs/epl_2024_datesData.json")),
        "liga": ("La_liga", Path("research/xg_feasibility/runs/liga_2024_datesData.json")),
    },
    "2025_26": {
        "ligue1": ("Ligue_1", Path("research/xg_feasibility/runs/ligue1_2025_datesData.json")),
        "premier_league": ("EPL", Path("research/xg_feasibility/runs/epl_2025_datesData.json")),
        "liga": ("La_liga", Path("research/xg_feasibility/runs/liga_2025_datesData.json")),
    },
}

# Etape I-2 : saison courante, SEULE entree qui agrege plusieurs fichiers -
# historique long terme + saison en cours deja jouee, dans l'ORDRE
# CHRONOLOGIQUE (par construction ci-dessous ; build_real_match_records_multi_season
# re-trie de toute facon par kickoff_utc, jamais un ordre suppose). Forme
# DELIBEREMENT distincte de ``_SEASONS`` (liste de sources, pas un tuple
# unique) : une saison courante n'est jamais un fichier isole. N'ajouter une
# competition ici QUE quand un fichier de saison courante reel existe pour
# elle (jamais une entree vide/anticipee).
_CURRENT_SEASON: str = "2026_27"
_CURRENT_SEASON_SOURCES: dict[str, list[tuple[str, Path]]] = {
    "ligue1": [
        ("Ligue_1", Path("research/xg_feasibility/runs/ligue1_2024_datesData.json")),
        ("Ligue_1", Path("research/xg_feasibility/runs/ligue1_2025_datesData.json")),
        ("Ligue_1", Path("research/xg_feasibility/runs/ligue1_2026_datesData.json")),
    ],
}

COMPETITIONS: tuple[str, ...] = tuple(
    sorted({c for seasons in _SEASONS.values() for c in seasons} | set(_CURRENT_SEASON_SOURCES))
)
SEASONS: tuple[str, ...] = tuple(sorted(set(_SEASONS) | {_CURRENT_SEASON}))


class PredictMatchError(ValueError):
    """Refus explicite d'un parametre CLI manquant/incoherent ou d'une
    equipe/competition/saison non resolue - jamais un defaut silencieux."""


def parse_kickoff_utc(value: str) -> datetime:
    """Coup d'envoi en UTC, NAIF (sans tzinfo) - meme convention que
    ``RealMatchRecord.kickoff_utc`` (``backtesting_engine.
    real_data_walk_forward``, construit via ``datetime.strptime`` sans
    tzinfo). Refuse explicitement une chaine avec fuseau plutot que de
    deviner une conversion."""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise PredictMatchError(
            f"--kickoff-utc invalide : {value!r} (format attendu : AAAA-MM-JJTHH:MM:SS, UTC naif)."
        ) from exc
    if parsed.tzinfo is not None:
        raise PredictMatchError(
            f"--kickoff-utc doit etre naif (deja en UTC, sans fuseau) : {value!r}."
        )
    return parsed


def validate_market_odds(
    market_odds_over_2_5: float | None, market_odds_under_2_5: float | None
) -> dict[str, float] | None:
    """``None`` si aucune cote n'est fournie (mode projection seule, gate
    ``incomplete_market_odds_gate`` produira ``MARKET_DATA_UNAVAILABLE`` en
    aval - comportement deja gere par le moteur, jamais reimplemente ici).
    Refuse explicitement une cote fournie seule (paire incoherente) et
    reutilise ``market_engine.overround.validate_odds`` (INCHANGE) pour la
    validite structurelle (> 1.0, finie)."""
    if market_odds_over_2_5 is None and market_odds_under_2_5 is None:
        return None
    if market_odds_over_2_5 is None or market_odds_under_2_5 is None:
        raise PredictMatchError(
            "--market-odds-over-2-5 et --market-odds-under-2-5 doivent etre fournies ensemble "
            "(ou aucune des deux pour une projection sans marche)."
        )
    odds = {"Over": market_odds_over_2_5, "Under": market_odds_under_2_5}
    try:
        validate_odds(odds)
    except ValueError as exc:
        raise PredictMatchError(str(exc)) from exc
    return odds


@dataclass(frozen=True)
class SnapshotOddsResolution:
    """Resultat complet de la lecture d'un snapshot - cotes exploitables
    par le moteur EXISTANT + metadonnees de tracabilite pure (bookmaker,
    marche, ligne) destinees UNIQUEMENT au journal Shadow Mode, jamais a
    ``run_match_decision``."""

    market_odds: dict[str, float]
    decision_offset_hours: float
    bookmaker: str
    market: str
    line: float


def load_odds_snapshot_from_file(
    path: Path,
    competition: str,
    season: str,
    home_team: str,
    away_team: str,
    kickoff_utc: datetime,
    bookmaker: str | None = None,
) -> SnapshotOddsResolution:
    """Alternative structuree aux deux cotes manuelles
    (``--market-odds-over-2-5``/``--market-odds-under-2-5``) : lit un
    fichier JSON de snapshot (voir ``docs`` du CLI), construit un
    ``snapshot_engine.schema.OddsSnapshot`` (``capture_timestamp`` genere
    par le systeme A CET INSTANT, JAMAIS lu depuis le fichier - voir
    ``create_snapshot``), puis extrait exactement la paire Over/Under 2.5
    deja consommee par ``run_match_decision`` (INCHANGE), le
    ``decision_offset_hours`` correspondant (``decision_time =
    capture_timestamp``, design valide), et la provenance (bookmaker/
    marche/ligne) destinee au journal Shadow Mode.

    ``kickoff_utc`` est ici le meme datetime NAIF deja produit par
    ``parse_kickoff_utc`` (convention R3 existante) - reinterprete
    explicitement comme UTC (jamais un autre fuseau) pour construire le
    snapshot, qui exige lui-meme des datetimes timezone-aware."""
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictMatchError(f"Fichier de snapshot illisible : {path} ({exc}).") from exc

    raw_observations = raw.get("observations")
    if not raw_observations:
        raise PredictMatchError(f"Le fichier de snapshot {path} ne contient aucune 'observations'.")

    try:
        observations = [
            OddsObservation(
                bookmaker=o["bookmaker"], market=o["market"], selection=o["selection"],
                odds=o["odds"], line=o.get("line"),
            )
            for o in raw_observations
        ]
    except (KeyError, SnapshotValidationError) as exc:
        raise PredictMatchError(f"Observation de snapshot invalide dans {path} : {exc}.") from exc

    snapshot_bookmaker = bookmaker or raw.get("bookmaker")
    kickoff_utc_aware = kickoff_utc.replace(tzinfo=timezone.utc)

    try:
        snapshot = create_snapshot(
            competition=competition, season=season, home_team=home_team, away_team=away_team,
            kickoff_utc=kickoff_utc_aware, observations=observations,
        )
        extraction = extract_over_under_2_5_with_source(snapshot, bookmaker=snapshot_bookmaker)
    except SnapshotValidationError as exc:
        raise PredictMatchError(str(exc)) from exc

    return SnapshotOddsResolution(
        market_odds=extraction.market_odds,
        decision_offset_hours=decision_offset_hours_from_snapshot(snapshot),
        bookmaker=extraction.bookmaker,
        market=extraction.market,
        line=extraction.line,
    )


def _load_understat_raw(competition: str, season: str) -> tuple[list[dict], str]:
    if season not in _SEASONS:
        raise PredictMatchError(f"Saison inconnue : {season!r} (saisons disponibles : {SEASONS}).")
    if competition not in _SEASONS[season]:
        raise PredictMatchError(f"Competition inconnue : {competition!r} (competitions disponibles : {COMPETITIONS}).")
    league_id, path = _SEASONS[season][competition]
    if not path.exists():
        raise PredictMatchError(
            f"Fichier Understat introuvable : {path} (ce runner ne collecte jamais de nouvelle donnee)."
        )
    with open(path) as f:
        raw = json.load(f)
    return raw, league_id


def resolve_team_id(name: str, team_id_by_name: dict[str, int], competition: str) -> int:
    """Resout ``name`` vers un ``team_id`` du corpus charge - recherche
    d'abord un nom Understat DIRECT (``team_id_by_name``, construit par R2
    a partir du corpus reellement charge), puis a defaut traduit ``name``
    comme un nom Football-Data via ``team_mapping.resolve_understat_name``
    (INCHANGE). Leve explicitement si aucune des deux resolutions
    n'aboutit - jamais une correspondance approximative."""
    if name in team_id_by_name:
        return team_id_by_name[name]
    try:
        understat_name = resolve_understat_name(competition, name)
    except KeyError:
        raise PredictMatchError(
            f"Equipe inconnue : {name!r} (ni un nom Understat present dans le corpus charge, "
            f"ni un nom Football-Data connu de team_mapping pour {competition!r})."
        ) from None
    try:
        return team_id_by_name[understat_name]
    except KeyError:
        raise PredictMatchError(
            f"Equipe {name!r} resolue vers le nom Understat {understat_name!r}, absent du corpus "
            f"charge ({competition!r}, saisons {SEASONS})."
        ) from None


@dataclass(frozen=True)
class PredictionInputs:
    """Entrees completement assemblees (R1 + R2), pretes pour
    ``run_match_decision`` - separe explicitement de la resolution CLI pour
    rester testable sans argument parsing."""

    league_id: str
    home_team_id: int
    away_team_id: int
    goals_train_df: pd.DataFrame
    xg_train_df: pd.DataFrame
    calibration_df_by_model: dict[str, pd.DataFrame]


def _load_current_season_raw_sources(competition: str) -> list[tuple[list[dict], str]]:
    """Charge, DANS L'ORDRE, les fichiers bruts declares par
    ``_CURRENT_SEASON_SOURCES[competition]`` (historique long terme + saison
    courante) - retourne le format ``(raw_matches, league_id)`` attendu par
    ``build_real_match_records_multi_season`` (INCHANGEE). Refuse
    explicitement une competition ou un fichier absent, meme convention que
    ``_load_understat_raw``."""
    if competition not in _CURRENT_SEASON_SOURCES:
        raise PredictMatchError(
            f"Competition inconnue pour la saison courante {_CURRENT_SEASON!r} : {competition!r} "
            f"(competitions disponibles pour la saison courante : {tuple(sorted(_CURRENT_SEASON_SOURCES))})."
        )
    sources: list[tuple[list[dict], str]] = []
    for league_id, path in _CURRENT_SEASON_SOURCES[competition]:
        if not path.exists():
            raise PredictMatchError(
                f"Fichier Understat introuvable : {path} (ce runner ne collecte jamais de nouvelle donnee)."
            )
        with open(path) as f:
            raw = json.load(f)
        sources.append((raw, league_id))
    return sources


def build_prediction_inputs(
    competition: str,
    season: str,
    home_team: str,
    away_team: str,
    kickoff_utc: datetime,
    decision_offset_hours: float = DECISION_OFFSET_HOURS,
) -> PredictionInputs:
    """Assemble R1 (``calibration_df_by_model``) + R2
    (``goals_train_df``/``xg_train_df``) pour UN match.

    Pour ``season == _CURRENT_SEASON`` (``"2026_27"``), le corpus est
    l'AGREGATION multi-fichiers de ``_CURRENT_SEASON_SOURCES`` (historique
    long terme + saison courante deja jouee), construite EXCLUSIVEMENT via
    ``multi_season_dataset.build_real_match_records_multi_season``
    (INCHANGEE, deja testee - detection de collision de ``match_id``
    comprise). Pour toute autre saison, comportement RIGOUREUSEMENT
    INCHANGE : un seul fichier charge via ``_load_understat_raw``
    (contrainte imperative de l'audit I-1B - jamais d'elargissement
    automatique de l'historique d'une saison deja close).

    AUCUN filtrage point-in-time reimplemente ici dans les deux cas,
    entierement delegue a R1/R2."""
    if home_team == away_team:
        raise PredictMatchError(f"--home-team et --away-team doivent designer deux equipes distinctes ({home_team!r}).")

    if season == _CURRENT_SEASON:
        raw_sources = _load_current_season_raw_sources(competition)
        records: list[RealMatchRecord] = build_real_match_records_multi_season(raw_sources)
        understat_keys = [
            key
            for raw, _source_league_id in raw_sources
            for key in build_understat_keys(raw, league=competition, season=season)
        ]
        # league_id "public" = celui de la saison courante elle-meme (le
        # dernier fichier de la liste, par construction de
        # _CURRENT_SEASON_SOURCES) - coherent avec le sens de ce champ pour
        # les autres saisons (identifiant Understat de LA saison demandee).
        league_id = _CURRENT_SEASON_SOURCES[competition][-1][0]
    else:
        understat_raw, league_id = _load_understat_raw(competition, season)
        records = build_real_match_records(understat_raw, league=league_id)

        # Resolution de nom -> team_id : reutilise integralement les cles deja
        # extraites par matching.build_understat_keys (INCHANGE) et la table
        # construite par future_match_dataset.build_understat_team_id_by_name
        # (R2) - jamais une nouvelle extraction du schema brut Understat.
        understat_keys = build_understat_keys(understat_raw, league=competition, season=season)

    team_id_by_name = build_understat_team_id_by_name(understat_keys)

    home_team_id = resolve_team_id(home_team, team_id_by_name, competition)
    away_team_id = resolve_team_id(away_team, team_id_by_name, competition)

    decision_time = kickoff_utc - timedelta(hours=decision_offset_hours)
    goals_train_df, xg_train_df = build_match_train_dataframes(
        records, home_team_id=home_team_id, away_team_id=away_team_id, decision_time=decision_time
    )

    # R1 : la calibration walk-forward E7/E8 est construite sur le meme
    # flux chronologique (competition, saison) que goals_train_df/
    # xg_train_df - aucun match posterieur a decision_time n'est utilise
    # par construction (fit_scale_correction_as_of filtre lui-meme sur
    # decision_time < as_of_time, INCHANGE).
    calibration_df = build_calibration_dataframe(records)
    calibration_df_by_model = split_calibration_df_by_model(calibration_df)

    return PredictionInputs(
        league_id=league_id,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        goals_train_df=goals_train_df,
        xg_train_df=xg_train_df,
        calibration_df_by_model=calibration_df_by_model,
    )


def run_prediction(
    competition: str,
    season: str,
    home_team: str,
    away_team: str,
    kickoff_utc: datetime,
    market_odds: dict[str, float] | None,
    decision_offset_hours: float = DECISION_OFFSET_HOURS,
) -> MatchDecisionOutput:
    """Assemble les entrees (R1 + R2) puis appelle
    ``final_engine.orchestrator.run_match_decision`` (INCHANGE) - point
    d'entree unique reutilisable directement par les tests, sans passer
    par le parsing CLI."""
    inputs = build_prediction_inputs(
        competition, season, home_team, away_team, kickoff_utc, decision_offset_hours=decision_offset_hours
    )
    match_id = f"{competition}:{season}:{home_team}_vs_{away_team}:{kickoff_utc.isoformat()}"
    return run_match_decision(
        match_id=match_id,
        competition=competition,
        season=season,
        kickoff_utc=kickoff_utc,
        home_team_id=inputs.home_team_id,
        away_team_id=inputs.away_team_id,
        goals_train_df=inputs.goals_train_df,
        xg_train_df=inputs.xg_train_df,
        calibration_df_by_model=inputs.calibration_df_by_model,
        market_odds_over_2_5=market_odds["Over"] if market_odds else None,
        market_odds_under_2_5=market_odds["Under"] if market_odds else None,
        decision_offset_hours=decision_offset_hours,
    )


def format_decision_report(output: MatchDecisionOutput) -> str:
    """Formatte ``MatchDecisionOutput`` pour affichage humain - lecture
    seule, ne recalcule jamais rien (chaque valeur affichee provient
    directement d'un champ deja produit par le moteur)."""
    lines: list[str] = []
    lines.append(f"Match       : {output.match_id}")
    lines.append(f"Competition : {output.competition} ({output.season})")
    lines.append(f"Decision a  : {output.timestamp_decision.isoformat()}")
    lines.append(f"Moteur      : {output.engine_version}")
    lines.append("")
    lines.append(f"Modele principal : {output.primary_model}")
    lines.append("")
    lines.append("--- Niveau A : Prediction (lambda/mu par modele) ---")
    for model_name, pred in output.models.items():
        if pred is None:
            lines.append(f"  {model_name:<14} INSUFFICIENT_HISTORY (aucune prediction)")
            continue
        rho_str = f" rho={pred.rho:.4f}" if pred.rho is not None else ""
        lines.append(
            f"  {model_name:<14} lambda={pred.lam:.4f} mu={pred.mu:.4f}{rho_str} "
            f"(n_train_matches={pred.n_train_matches})"
        )
    lines.append("")
    lines.append("--- Niveau B/C : Calibration E7/E8 + prix juste (Over 2.5) ---")
    for model_name, calib in output.calibration.items():
        if calib.probabilities is None:
            lines.append(f"  {model_name:<14} calibration non estimee (n_calibration_used={calib.n_calibration_used})")
            continue
        p_over_2_5 = calib.probabilities.get(2.5)
        pricing = output.pricing.get(model_name)
        fair_price = pricing.fair_price.get(2.5) if pricing else None
        p_str = f"{p_over_2_5:.4f}" if p_over_2_5 is not None else "n/a"
        price_str = f"{fair_price:.3f}" if fair_price is not None else "n/a"
        lines.append(
            f"  {model_name:<14} scale_c={calib.scale_c:.4f} n_calibration_used={calib.n_calibration_used} "
            f"P(Over 2.5)={p_str} cote_juste={price_str}"
        )
    lines.append("")
    lines.append("--- Niveau D : Comparaison au marche (Over/Under 2.5, cote d'ouverture) ---")
    if output.market is None:
        # ``output.market`` est None soit parce qu'aucune cote valide n'a
        # ete transmise (incomplete_market_odds_gate declenche), soit parce
        # que le Niveau B n'a produit aucune probabilite calibree (cote
        # valide mais Niveau D non atteignable) - distingue les deux sans
        # rien recalculer, a partir du gate deja produit par le moteur.
        odds_gate = next(
            (g for g in output.qualification.scientific_gates if g.name == "incomplete_market_odds_gate"), None
        )
        if odds_gate is not None and odds_gate.triggered:
            lines.append(f"  Aucune cote de marche exploitable (MARKET_DATA_UNAVAILABLE) : {odds_gate.reason}")
        else:
            lines.append(
                "  Cote de marche fournie et valide, mais non exploitable : le Niveau B "
                "(calibration E7/E8) n'a produit aucune probabilite (historique de calibration "
                "insuffisant - voir Niveau B/C ci-dessus)."
            )
    else:
        m = output.market
        lines.append(f"  Cote marche          : Over={m.market_odds['Over']} Under={m.market_odds['Under']}")
        lines.append(
            f"  Prob. implicite (sans marge) : Over={m.market_implied_probability_normalized['Over']:.4f} "
            f"Under={m.market_implied_probability_normalized['Under']:.4f} (overround={m.market_overround:.4f})"
        )
        lines.append(
            f"  Edge (modele - marche, sans marge) : Over={m.raw_edge['Over']:+.4f} Under={m.raw_edge['Under']:+.4f}"
        )
        lines.append(f"  EV (a la cote brute)               : Over={m.price_edge['Over']:+.4f} Under={m.price_edge['Under']:+.4f}")
    lines.append("")
    lines.append("--- Niveau E : Qualification ---")
    lines.append(f"  Statut de calibration (Over 2.5) : {output.qualification.calibration_status.get(2.5, 'n/a')}")
    lines.append(f"  Statut de discrimination          : {output.qualification.discrimination_status}")
    lines.append(f"  Data quality                      : {', '.join(output.qualification.data_quality)}")
    triggered = [g for g in output.qualification.scientific_gates + output.qualification.operational_gates if g.triggered]
    if triggered:
        lines.append("  Gates declenches :")
        for g in triggered:
            lines.append(f"    - {g.name} : {g.reason} (observed={g.observed_value!r}, threshold={g.threshold!r})")
    lines.append("")
    lines.append("=== DECISION FINALE ===")
    lines.append(f"  {output.decision.decision}")
    if output.decision.decision_reason:
        lines.append(f"  Raisons : {', '.join(output.decision.decision_reason)}")
    return "\n".join(lines)


@app.command()
def main(
    competition: str = typer.Option(..., help=f"Championnat ({', '.join(COMPETITIONS)})."),
    season: str = typer.Option(..., help=f"Saison ({', '.join(SEASONS)})."),
    home_team: str = typer.Option(..., "--home-team", help="Equipe a domicile (nom Understat ou Football-Data)."),
    away_team: str = typer.Option(..., "--away-team", help="Equipe a l'exterieur (nom Understat ou Football-Data)."),
    kickoff_utc: str = typer.Option(..., "--kickoff-utc", help="Coup d'envoi, UTC naif : AAAA-MM-JJTHH:MM:SS."),
    market_odds_over_2_5: float | None = typer.Option(None, "--market-odds-over-2-5", help="Cote d'ouverture B365 Over 2.5."),
    market_odds_under_2_5: float | None = typer.Option(None, "--market-odds-under-2-5", help="Cote d'ouverture B365 Under 2.5."),
    odds_snapshot_file: Path | None = typer.Option(
        None,
        "--odds-snapshot-file",
        help="Alternative structuree a --market-odds-over-2-5/--market-odds-under-2-5 : fichier JSON de "
        "snapshot manuel (voir snapshot_engine.schema). Mutuellement exclusif avec les deux options "
        "precedentes. decision_offset_hours est alors TOUJOURS derive du snapshot (capture_timestamp genere "
        "au moment de cet appel) - toute valeur de --decision-offset-hours est ignoree dans ce mode.",
    ),
    odds_snapshot_bookmaker: str | None = typer.Option(
        None,
        "--odds-snapshot-bookmaker",
        help="Filtre le bookmaker a utiliser si le snapshot en contient plusieurs pour Over/Under 2.5 "
        "(--odds-snapshot-file uniquement).",
    ),
    decision_offset_hours: float | None = typer.Option(
        None,
        "--decision-offset-hours",
        help=f"Identique a final_engine.orchestrator.DECISION_OFFSET_HOURS (defaut si omis : {DECISION_OFFSET_HOURS}). "
        "Mutuellement exclusif avec --odds-snapshot-file (qui fixe deja decision_time = capture_timestamp) - "
        "fournir les deux leve une erreur explicite plutot que d'ignorer silencieusement l'un des deux.",
    ),
    record_shadow: bool = typer.Option(
        False,
        "--record-shadow",
        help="Enregistre une copie immuable de cette decision dans le journal Shadow Mode (voir shadow_mode.journal).",
    ),
    shadow_journal_path: Path = typer.Option(
        SHADOW_DEFAULT_JOURNAL_PATH, "--shadow-journal-path", help="Chemin du journal Shadow Mode (--record-shadow uniquement)."
    ),
) -> None:
    odds_bookmaker: str | None = None
    odds_market: str | None = None
    odds_line: float | None = None
    try:
        kickoff = parse_kickoff_utc(kickoff_utc)
        if odds_snapshot_file is not None:
            if market_odds_over_2_5 is not None or market_odds_under_2_5 is not None:
                raise PredictMatchError(
                    "--odds-snapshot-file est mutuellement exclusif avec --market-odds-over-2-5/"
                    "--market-odds-under-2-5 (fournir l'un ou l'autre, jamais les deux)."
                )
            if decision_offset_hours is not None:
                raise PredictMatchError(
                    "--odds-snapshot-file est mutuellement exclusif avec --decision-offset-hours : "
                    "le snapshot fixe deja decision_time = capture_timestamp (design valide) - fournir "
                    "explicitement les deux serait ambigu plutot qu'ignorer l'un d'eux silencieusement."
                )
            resolution = load_odds_snapshot_from_file(
                odds_snapshot_file, competition, season, home_team, away_team, kickoff,
                bookmaker=odds_snapshot_bookmaker,
            )
            market_odds = resolution.market_odds
            decision_offset_hours = resolution.decision_offset_hours
            odds_bookmaker = resolution.bookmaker
            odds_market = resolution.market
            odds_line = resolution.line
        else:
            market_odds = validate_market_odds(market_odds_over_2_5, market_odds_under_2_5)
            if decision_offset_hours is None:
                decision_offset_hours = DECISION_OFFSET_HOURS
        output = run_prediction(
            competition=competition,
            season=season,
            home_team=home_team,
            away_team=away_team,
            kickoff_utc=kickoff,
            market_odds=market_odds,
            decision_offset_hours=decision_offset_hours,
        )
    except PredictMatchError as exc:
        typer.echo(f"ERREUR : {exc}", err=True)
        raise typer.Exit(code=1) from None

    typer.echo(format_decision_report(output))

    if record_shadow:
        # Pipeline R3 DEJA execute ci-dessus (``output``) - ce bloc ne fait
        # que journaliser une copie immuable, jamais un second appel au
        # moteur ni une modification de ``output``.
        record, already_existed = record_shadow_prediction(
            output,
            competition=competition,
            season=season,
            home_team=home_team,
            away_team=away_team,
            kickoff_utc=kickoff,
            decision_offset_hours=decision_offset_hours,
            market_odds_over_2_5=market_odds["Over"] if market_odds else None,
            market_odds_under_2_5=market_odds["Under"] if market_odds else None,
            journal_path=shadow_journal_path,
            odds_bookmaker=odds_bookmaker,
            odds_market=odds_market,
            odds_line=odds_line,
        )
        typer.echo("")
        if already_existed:
            typer.echo(f"Shadow Mode : observation deja enregistree, aucun doublon cree (prediction_id={record['prediction_id']}).")
        else:
            typer.echo(f"Shadow Mode : observation enregistree (prediction_id={record['prediction_id']}, status={record['status']}).")


if __name__ == "__main__":
    app()
