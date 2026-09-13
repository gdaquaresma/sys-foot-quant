"""Tests unitaires du CLI de production R3 (``scripts/predict_match.py``) :
parsing/validation des arguments, refus propre des parametres manquants ou
incoherents, et formatage du rapport - AUCUN de ces tests n'appelle
``run_match_decision`` sur donnees reelles (voir
``tests/leakage/test_predict_match_point_in_time.py`` pour l'integration
bout-en-bout).

La section ``--odds-snapshot-file`` (integration du snapshot manuel,
voir ``snapshot_engine.schema``) verifie explicitement la
retrocompatibilite : les arguments ``--market-odds-over-2-5``/
``--market-odds-under-2-5`` existants doivent continuer a fonctionner
EXACTEMENT comme avant (voir la section 1 ci-dessus, executee sans modification pour le
prouver), et le nouveau chemin ne doit jamais faire fuiter une cote de
cloture dans le calcul pre-match."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sys_foot_quant.final_engine.types import (
    CalibratedGoalDistribution,
    DecisionResult,
    GateResult,
    MatchDecisionOutput,
    ModelPrediction,
    PricingResult,
    QualificationResult,
)

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "predict_match.py"


def _load_predict_match():
    spec = importlib.util.spec_from_file_location("predict_match_for_test", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def predict_match():
    return _load_predict_match()


runner = CliRunner()


# --- 1. parsing/validation des arguments CLI --------------------------------


def test_parse_kickoff_utc_accepts_naive_iso_datetime(predict_match) -> None:
    parsed = predict_match.parse_kickoff_utc("2025-05-11T19:00:00")
    assert parsed == datetime(2025, 5, 11, 19, 0, 0)


def test_parse_kickoff_utc_rejects_malformed_string(predict_match) -> None:
    with pytest.raises(predict_match.PredictMatchError, match="invalide"):
        predict_match.parse_kickoff_utc("not-a-date")


def test_parse_kickoff_utc_rejects_timezone_aware_string(predict_match) -> None:
    with pytest.raises(predict_match.PredictMatchError, match="naif"):
        predict_match.parse_kickoff_utc("2025-05-11T19:00:00+02:00")


def test_validate_market_odds_returns_none_when_absent(predict_match) -> None:
    assert predict_match.validate_market_odds(None, None) is None


def test_validate_market_odds_returns_dict_when_both_present(predict_match) -> None:
    assert predict_match.validate_market_odds(1.85, 1.95) == {"Over": 1.85, "Under": 1.95}


# --- 2. refus propre des parametres manquants ou incoherents ----------------


def test_validate_market_odds_rejects_partial_pair_over_only(predict_match) -> None:
    with pytest.raises(predict_match.PredictMatchError, match="ensemble"):
        predict_match.validate_market_odds(1.85, None)


def test_validate_market_odds_rejects_partial_pair_under_only(predict_match) -> None:
    with pytest.raises(predict_match.PredictMatchError, match="ensemble"):
        predict_match.validate_market_odds(None, 1.95)


def test_validate_market_odds_rejects_odds_below_one(predict_match) -> None:
    with pytest.raises(predict_match.PredictMatchError):
        predict_match.validate_market_odds(0.9, 1.95)


def test_resolve_team_id_direct_understat_name(predict_match) -> None:
    team_id_by_name = {"Real Madrid": 100, "Barcelona": 200}
    assert predict_match.resolve_team_id("Real Madrid", team_id_by_name, "liga") == 100


def test_resolve_team_id_falls_back_to_football_data_translation(predict_match) -> None:
    team_id_by_name = {"Athletic Club": 300}
    assert predict_match.resolve_team_id("Ath Bilbao", team_id_by_name, "liga") == 300


def test_resolve_team_id_raises_for_completely_unknown_team(predict_match) -> None:
    with pytest.raises(predict_match.PredictMatchError, match="Equipe inconnue"):
        predict_match.resolve_team_id("Not A Real Team", {}, "liga")


def test_resolve_team_id_raises_when_translated_name_absent_from_corpus(predict_match) -> None:
    with pytest.raises(predict_match.PredictMatchError, match="absent du corpus"):
        predict_match.resolve_team_id("Ath Bilbao", {"Barcelona": 200}, "liga")


def test_build_prediction_inputs_rejects_identical_home_and_away_team(predict_match) -> None:
    with pytest.raises(predict_match.PredictMatchError, match="distinctes"):
        predict_match.build_prediction_inputs(
            "liga", "2024_25", "Real Madrid", "Real Madrid", datetime(2025, 1, 1)
        )


def test_load_understat_raw_rejects_unknown_competition(predict_match) -> None:
    with pytest.raises(predict_match.PredictMatchError, match="Competition inconnue"):
        predict_match._load_understat_raw("bundesliga", "2024_25")


def test_load_understat_raw_rejects_unknown_season(predict_match) -> None:
    with pytest.raises(predict_match.PredictMatchError, match="Saison inconnue"):
        predict_match._load_understat_raw("liga", "1999_00")


def test_cli_exits_nonzero_on_missing_required_option(predict_match) -> None:
    result = runner.invoke(predict_match.app, ["--competition", "liga", "--season", "2024_25"])
    assert result.exit_code != 0


def test_cli_exits_1_on_invalid_kickoff(predict_match) -> None:
    result = runner.invoke(
        predict_match.app,
        [
            "--competition", "liga", "--season", "2024_25",
            "--home-team", "Real Madrid", "--away-team", "Barcelona",
            "--kickoff-utc", "not-a-date",
        ],
    )
    assert result.exit_code == 1
    assert "ERREUR" in result.output


def test_cli_exits_1_on_partial_market_odds(predict_match) -> None:
    result = runner.invoke(
        predict_match.app,
        [
            "--competition", "liga", "--season", "2024_25",
            "--home-team", "Real Madrid", "--away-team", "Barcelona",
            "--kickoff-utc", "2025-05-11T19:00:00",
            "--market-odds-over-2-5", "1.85",
        ],
    )
    assert result.exit_code == 1
    assert "ensemble" in result.output


# --- formatage du rapport (aucun appel reel a run_match_decision) ----------


def _minimal_no_bet_output(predict_match) -> MatchDecisionOutput:
    pred = ModelPrediction(model="poisson_simple", lam=1.5, mu=1.1, rho=None, n_train_matches=50)
    calib = CalibratedGoalDistribution(
        model="poisson_simple", scale_c=0.9, n_calibration_used=40, goal_distribution=(0.1,) * 7, probabilities={2.5: 0.55}
    )
    return MatchDecisionOutput(
        match_id="test-match",
        timestamp_decision=datetime(2025, 1, 1, tzinfo=timezone.utc),
        competition="liga",
        season="2024_25",
        primary_model="poisson_simple",
        models={"poisson_simple": pred, "dixon_coles": None, "xg_model": None},
        calibration={"poisson_simple": calib},
        pricing={"poisson_simple": PricingResult(fair_price={2.5: 1.818})},
        market=None,
        qualification=QualificationResult(
            calibration_status={2.5: "OK"},
            discrimination_status="DEMONTREE",
            data_quality=["OK"],
            # incomplete_market_odds_gate fait TOUJOURS partie des
            # data_quality_gates produits par l'orchestrateur (INCHANGE),
            # meme non declenche - reproduit ici fidelement pour que le
            # fixture reflete une vraie sortie moteur.
            scientific_gates=[
                GateResult(
                    name="incomplete_market_odds_gate",
                    triggered=True,
                    reason="Aucune cote de marche disponible a decision_time.",
                    metric="market_odds",
                    observed_value=None,
                    threshold="cote complete requise",
                    failure_code="MARKET_DATA_UNAVAILABLE",
                )
            ],
            operational_gates=[],
        ),
        decision=DecisionResult(decision="NO_BET", decision_reason=["MARKET_DATA_UNAVAILABLE"]),
        engine_version="test-version",
        parameters_snapshot={},
    )


def test_format_decision_report_shows_decision_and_reason(predict_match) -> None:
    report = predict_match.format_decision_report(_minimal_no_bet_output(predict_match))
    assert "NO_BET" in report
    assert "MARKET_DATA_UNAVAILABLE" in report
    assert "poisson_simple" in report
    assert "lambda=1.5000" in report


def test_format_decision_report_handles_no_market(predict_match) -> None:
    report = predict_match.format_decision_report(_minimal_no_bet_output(predict_match))
    assert "Aucune cote de marche" in report


# --- 3. --odds-snapshot-file : integration du snapshot manuel --------------

def _future_kickoff_naive() -> datetime:
    """Naif (convention R3 existante), toujours dans le futur par
    rapport a l'horloge reelle - jamais une date fixe qui deviendrait
    perimee (capture_timestamp = 'maintenant' doit rester < kickoff)."""
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=30)


_SNAPSHOT_KICKOFF = _future_kickoff_naive()


def _write_snapshot_file(tmp_path: Path, observations: list[dict], bookmaker: str | None = None) -> Path:
    payload: dict = {"observations": observations}
    if bookmaker is not None:
        payload["bookmaker"] = bookmaker
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(payload))
    return path


def _ou25_observations(bookmaker: str = "Bet365") -> list[dict]:
    return [
        {"bookmaker": bookmaker, "market": "over_under", "selection": "OVER", "line": 2.5, "odds": 1.60},
        {"bookmaker": bookmaker, "market": "over_under", "selection": "UNDER", "line": 2.5, "odds": 2.30},
    ]


def test_load_odds_snapshot_from_file_returns_market_odds_and_offset(predict_match, tmp_path) -> None:
    path = _write_snapshot_file(tmp_path, _ou25_observations())
    resolution = predict_match.load_odds_snapshot_from_file(
        path, "liga", "2025_26", "Real Madrid", "Barcelona", _SNAPSHOT_KICKOFF,
    )
    assert resolution.market_odds == {"Over": 1.60, "Under": 2.30}
    assert resolution.decision_offset_hours > 0.0  # capture_timestamp (maintenant) est forcement avant le kickoff futur


# --- Tracabilite : bookmaker/marche/ligne conserves (amelioration demandee) --


def test_load_odds_snapshot_from_file_preserves_bookmaker_market_and_line(predict_match, tmp_path) -> None:
    path = _write_snapshot_file(tmp_path, _ou25_observations("Pinnacle"))
    resolution = predict_match.load_odds_snapshot_from_file(
        path, "liga", "2025_26", "Real Madrid", "Barcelona", _SNAPSHOT_KICKOFF,
    )
    assert resolution.bookmaker == "Pinnacle"
    assert resolution.market == "OU"
    assert resolution.line == 2.5


def test_load_odds_snapshot_from_file_rejects_missing_file(predict_match, tmp_path) -> None:
    with pytest.raises(predict_match.PredictMatchError, match="illisible"):
        predict_match.load_odds_snapshot_from_file(
            tmp_path / "absent.json", "liga", "2025_26", "Real Madrid", "Barcelona", _SNAPSHOT_KICKOFF,
        )


def test_load_odds_snapshot_from_file_rejects_empty_observations(predict_match, tmp_path) -> None:
    path = tmp_path / "empty.json"
    path.write_text(json.dumps({"observations": []}))
    with pytest.raises(predict_match.PredictMatchError, match="observations"):
        predict_match.load_odds_snapshot_from_file(
            path, "liga", "2025_26", "Real Madrid", "Barcelona", _SNAPSHOT_KICKOFF,
        )


def test_load_odds_snapshot_from_file_rejects_snapshot_after_kickoff(predict_match, tmp_path) -> None:
    """capture_timestamp est TOUJOURS 'maintenant' - si kickoff_utc est
    deja passe, le snapshot est refuse (jamais une capture apres le coup
    d'envoi)."""
    path = _write_snapshot_file(tmp_path, _ou25_observations())
    past_kickoff = datetime(2000, 1, 1, 0, 0, 0)
    with pytest.raises(predict_match.PredictMatchError):
        predict_match.load_odds_snapshot_from_file(
            path, "liga", "2025_26", "Real Madrid", "Barcelona", past_kickoff,
        )


def test_load_odds_snapshot_from_file_requires_explicit_bookmaker_when_ambiguous(predict_match, tmp_path) -> None:
    path = _write_snapshot_file(tmp_path, _ou25_observations("Bet365") + _ou25_observations("Pinnacle"))
    with pytest.raises(predict_match.PredictMatchError, match="Plusieurs bookmakers"):
        predict_match.load_odds_snapshot_from_file(
            path, "liga", "2025_26", "Real Madrid", "Barcelona", _SNAPSHOT_KICKOFF,
        )
    resolution = predict_match.load_odds_snapshot_from_file(
        path, "liga", "2025_26", "Real Madrid", "Barcelona", _SNAPSHOT_KICKOFF, bookmaker="Pinnacle",
    )
    assert resolution.market_odds == {"Over": 1.60, "Under": 2.30}


def test_load_odds_snapshot_from_file_bookmaker_in_json_payload_is_honored(predict_match, tmp_path) -> None:
    """Le champ 'bookmaker' au niveau racine du JSON sert de filtre par
    defaut si --odds-snapshot-bookmaker n'est pas passe en CLI."""
    path = _write_snapshot_file(tmp_path, _ou25_observations("Bet365") + _ou25_observations("Pinnacle"), bookmaker="Bet365")
    resolution = predict_match.load_odds_snapshot_from_file(
        path, "liga", "2025_26", "Real Madrid", "Barcelona", _SNAPSHOT_KICKOFF,
    )
    assert resolution.market_odds == {"Over": 1.60, "Under": 2.30}


def test_load_odds_snapshot_from_file_never_accepts_a_closing_odds_field(predict_match, tmp_path) -> None:
    """Meme si un fichier de snapshot contient malencontreusement un champ
    'closing_odds', il est simplement ignore - jamais utilise pour
    remplacer/completer la cote pre-match."""
    payload = {"observations": _ou25_observations(), "closing_odds": {"Over": 1.30, "Under": 3.50}}
    path = tmp_path / "snapshot_with_closing.json"
    path.write_text(json.dumps(payload))
    resolution = predict_match.load_odds_snapshot_from_file(
        path, "liga", "2025_26", "Real Madrid", "Barcelona", _SNAPSHOT_KICKOFF,
    )
    assert resolution.market_odds == {"Over": 1.60, "Under": 2.30}  # jamais 1.30/3.50


def test_cli_rejects_odds_snapshot_file_combined_with_manual_floats(predict_match, tmp_path) -> None:
    path = _write_snapshot_file(tmp_path, _ou25_observations())
    result = runner.invoke(
        predict_match.app,
        [
            "--competition", "liga", "--season", "2024_25",
            "--home-team", "Real Madrid", "--away-team", "Barcelona",
            "--kickoff-utc", "2025-05-11T19:00:00",
            "--market-odds-over-2-5", "1.85", "--market-odds-under-2-5", "1.95",
            "--odds-snapshot-file", str(path),
        ],
    )
    assert result.exit_code == 1
    assert "mutuellement exclusif" in result.output


def test_cli_rejects_odds_snapshot_file_with_only_one_manual_float(predict_match, tmp_path) -> None:
    path = _write_snapshot_file(tmp_path, _ou25_observations())
    result = runner.invoke(
        predict_match.app,
        [
            "--competition", "liga", "--season", "2024_25",
            "--home-team", "Real Madrid", "--away-team", "Barcelona",
            "--kickoff-utc", "2025-05-11T19:00:00",
            "--market-odds-over-2-5", "1.85",
            "--odds-snapshot-file", str(path),
        ],
    )
    assert result.exit_code == 1
    assert "mutuellement exclusif" in result.output


def test_existing_manual_float_arguments_still_work_unchanged(predict_match) -> None:
    """Retrocompatibilite explicite : le chemin --market-odds-over-2-5/
    --market-odds-under-2-5 (sans --odds-snapshot-file) produit exactement
    le meme dict qu'avant l'ajout du snapshot."""
    assert predict_match.validate_market_odds(1.85, 1.95) == {"Over": 1.85, "Under": 1.95}
    result = runner.invoke(
        predict_match.app,
        [
            "--competition", "liga", "--season", "2024_25",
            "--home-team", "Real Madrid", "--away-team", "Barcelona",
            "--kickoff-utc", "2025-05-11T19:00:00",
            "--market-odds-over-2-5", "1.85",
        ],
    )
    # Meme comportement qu'avant (test_cli_exits_1_on_partial_market_odds) :
    # une seule des deux cotes manuelles reste refusee de la meme facon.
    assert result.exit_code == 1
    assert "ensemble" in result.output


# --- 4. --odds-snapshot-file + --decision-offset-hours : desormais une erreur --


def test_cli_rejects_odds_snapshot_file_combined_with_decision_offset_hours(predict_match, tmp_path) -> None:
    """Amelioration demandee : plutot que d'ignorer silencieusement
    --decision-offset-hours quand --odds-snapshot-file est fourni, le CLI
    refuse desormais explicitement la combinaison."""
    path = _write_snapshot_file(tmp_path, _ou25_observations())
    result = runner.invoke(
        predict_match.app,
        [
            "--competition", "liga", "--season", "2024_25",
            "--home-team", "Real Madrid", "--away-team", "Barcelona",
            "--kickoff-utc", "2025-05-11T19:00:00",
            "--odds-snapshot-file", str(path),
            "--decision-offset-hours", "3.0",
        ],
    )
    assert result.exit_code == 1
    assert "mutuellement exclusif" in result.output
    assert "decision_time = capture_timestamp" in result.output


def test_cli_accepts_decision_offset_hours_alone_without_snapshot(predict_match) -> None:
    """Ne change pas le comportement quand une seule des deux options est
    utilisee : --decision-offset-hours seul (sans snapshot) continue de
    fonctionner exactement comme avant."""
    result = runner.invoke(
        predict_match.app,
        [
            "--competition", "liga", "--season", "2024_25",
            "--home-team", "Real Madrid", "--away-team", "Barcelona",
            "--kickoff-utc", "2025-05-11T19:00:00",
            "--decision-offset-hours", "3.0",
        ],
    )
    # Pas d'erreur de mutuelle exclusivite - le match/l'appel au moteur
    # peut echouer pour d'autres raisons (donnees), mais jamais celle-la.
    assert "mutuellement exclusif" not in result.output


def test_cli_accepts_odds_snapshot_file_alone_without_decision_offset_hours(predict_match, tmp_path) -> None:
    """Ne change pas le comportement quand --odds-snapshot-file est
    utilise seul (sans --decision-offset-hours explicite) - c'est le
    chemin nominal, deja teste par ailleurs, revalide ici pour la
    non-regression de ce point precis."""
    path = _write_snapshot_file(tmp_path, _ou25_observations())
    result = runner.invoke(
        predict_match.app,
        [
            "--competition", "liga", "--season", "2024_25",
            "--home-team", "Real Madrid", "--away-team", "Barcelona",
            "--kickoff-utc", "2025-05-11T19:00:00",
            "--odds-snapshot-file", str(path),
        ],
    )
    assert "mutuellement exclusif" not in result.output


# --- 5. Tracabilite bout-en-bout dans le journal Shadow Mode ----------------


def test_record_prediction_stores_odds_bookmaker_market_and_line(tmp_path) -> None:
    """Verifie directement au niveau de shadow_mode.journal (sans repasser
    par tout le pipeline R3) que les nouveaux champs de tracabilite sont
    bien ecrits et relisibles depuis le journal."""
    from sys_foot_quant.shadow_mode.journal import load_journal, record_prediction

    output = _minimal_no_bet_output(None)
    journal_path = tmp_path / "journal.jsonl"
    record, _ = record_prediction(
        output,
        competition="liga", season="2024_25", home_team="Real Madrid", away_team="Barcelona",
        kickoff_utc=datetime(2025, 5, 11, 19, 0, 0),
        decision_offset_hours=2.0,
        market_odds_over_2_5=1.60, market_odds_under_2_5=2.20,
        journal_path=journal_path,
        odds_bookmaker="Pinnacle", odds_market="OU", odds_line=2.5,
    )
    assert record["odds_bookmaker"] == "Pinnacle"
    assert record["odds_market"] == "OU"
    assert record["odds_line"] == 2.5

    reloaded = load_journal(journal_path)
    assert len(reloaded) == 1
    assert reloaded[0]["odds_bookmaker"] == "Pinnacle"
    assert reloaded[0]["odds_market"] == "OU"
    assert reloaded[0]["odds_line"] == 2.5


def test_record_prediction_traceability_fields_default_to_none_for_historical_path(tmp_path) -> None:
    """Retrocompatibilite : un appel sans les nouveaux parametres (le
    chemin --market-odds-over-2-5/--market-odds-under-2-5 historique)
    stocke explicitement None, jamais une valeur devinee."""
    from sys_foot_quant.shadow_mode.journal import record_prediction

    output = _minimal_no_bet_output(None)
    journal_path = tmp_path / "journal.jsonl"
    record, _ = record_prediction(
        output,
        competition="liga", season="2024_25", home_team="Real Madrid", away_team="Barcelona",
        kickoff_utc=datetime(2025, 5, 11, 19, 0, 0),
        decision_offset_hours=2.0,
        market_odds_over_2_5=1.85, market_odds_under_2_5=1.95,
        journal_path=journal_path,
    )
    assert record["odds_bookmaker"] is None
    assert record["odds_market"] is None
    assert record["odds_line"] is None


def test_traceability_fields_never_affect_prediction_id_dedup(tmp_path) -> None:
    """Les nouveaux champs sont une metadonnee pure : deux enregistrements
    avec les MEMES cotes/match/offset mais des bookmakers differents
    partagent le meme prediction_id (comportement de dedup inchange,
    jamais silencieusement modifie par cet ajout)."""
    from sys_foot_quant.shadow_mode.journal import record_prediction

    output = _minimal_no_bet_output(None)
    journal_path = tmp_path / "journal.jsonl"
    record1, existed1 = record_prediction(
        output, competition="liga", season="2024_25", home_team="Real Madrid", away_team="Barcelona",
        kickoff_utc=datetime(2025, 5, 11, 19, 0, 0), decision_offset_hours=2.0,
        market_odds_over_2_5=1.60, market_odds_under_2_5=2.20, journal_path=journal_path,
        odds_bookmaker="Bet365", odds_market="OU", odds_line=2.5,
    )
    record2, existed2 = record_prediction(
        output, competition="liga", season="2024_25", home_team="Real Madrid", away_team="Barcelona",
        kickoff_utc=datetime(2025, 5, 11, 19, 0, 0), decision_offset_hours=2.0,
        market_odds_over_2_5=1.60, market_odds_under_2_5=2.20, journal_path=journal_path,
        odds_bookmaker="Pinnacle", odds_market="OU", odds_line=2.5,
    )
    assert existed1 is False
    assert existed2 is True  # deduplique sur le meme prediction_id malgre le bookmaker different
    assert record1["prediction_id"] == record2["prediction_id"]


def test_predict_match_cli_end_to_end_journal_never_contains_closing_odds_key(tmp_path) -> None:
    """Verification structurelle : aucune cle liee a une cloture n'existe
    dans le schema du journal, meme apres l'ajout des champs de
    tracabilite."""
    from sys_foot_quant.shadow_mode.journal import record_prediction

    output = _minimal_no_bet_output(None)
    journal_path = tmp_path / "journal.jsonl"
    record, _ = record_prediction(
        output, competition="liga", season="2024_25", home_team="Real Madrid", away_team="Barcelona",
        kickoff_utc=datetime(2025, 5, 11, 19, 0, 0), decision_offset_hours=2.0,
        market_odds_over_2_5=1.60, market_odds_under_2_5=2.20, journal_path=journal_path,
        odds_bookmaker="Bet365", odds_market="OU", odds_line=2.5,
    )
    assert not any("closing" in str(k).lower() for k in record.keys())
