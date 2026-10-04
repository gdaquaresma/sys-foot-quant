from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

from sys_foot_quant.data_engine.market_odds.football_data_loader import FootballDataMatchRecord
from sys_foot_quant.data_engine.market_odds.match_catalog import MatchSummary
from sys_foot_quant.final_engine.types import (
    CalibratedGoalDistribution,
    DecisionResult,
    MatchDecisionOutput,
    ModelPrediction,
    PricingResult,
    QualificationResult,
)
from sys_foot_quant.shadow_mode import historical_evaluation as he


def _us_raw(match_id, date_str, time_str, home, away, hg, ag):
    return {
        "id": match_id,
        "isResult": True,
        "datetime": f"{date_str} {time_str}:00",
        "h": {"id": 1, "title": home},
        "a": {"id": 2, "title": away},
        "goals": {"h": hg, "a": ag},
    }


def _fd(date_str, home, away, b365_over=None, b365_under=None, b365_close_over=None, b365_close_under=None):
    return FootballDataMatchRecord(
        league="ligue1", season="2025_26", source="football_data", bookmaker="B365", market="1x2",
        date_str=date_str, time_str="19:45", home_team_fd=home, away_team_fd=away,
        home_goals=9, away_goals=9,  # volontairement incoherent avec le score Understat - jamais lu par le pont odds
        b365_home=1.5, b365_draw=4.0, b365_away=6.0,
        b365_over_2_5=b365_over, b365_under_2_5=b365_under,
        b365_close_over_2_5=b365_close_over, b365_close_under_2_5=b365_close_under,
    )


def _output(p_over_2_5: float = 0.6, decision="NO_BET", reasons=None) -> MatchDecisionOutput:
    pred = ModelPrediction(model="poisson_simple", lam=1.5, mu=1.1, rho=None, n_train_matches=50)
    calib = CalibratedGoalDistribution(
        model="poisson_simple", scale_c=0.9, n_calibration_used=40,
        goal_distribution=(0.1,) * 7, probabilities={2.5: p_over_2_5},
    )
    return MatchDecisionOutput(
        match_id="test-match",
        timestamp_decision=datetime(2025, 8, 15, 17, 45, 0),
        competition="ligue1",
        season="2025_26",
        primary_model="poisson_simple",
        models={"poisson_simple": pred, "dixon_coles": None, "xg_model": None},
        calibration={"poisson_simple": calib},
        pricing={"poisson_simple": PricingResult(fair_price={2.5: 1.0 / p_over_2_5})},
        market=None,
        qualification=QualificationResult(
            calibration_status={2.5: "OK"}, discrimination_status="DEMONTREE",
            data_quality=["OK"], scientific_gates=[], operational_gates=[],
        ),
        decision=DecisionResult(decision=decision, decision_reason=reasons or []),
        engine_version="test-version",
        parameters_snapshot={},
    )


# Fixtures Rennes-Marseille utilisees pour les tests synthetiques (pas le
# match reel 29683, reserve au test end-to-end dedie plus bas). match_id
# "31967" est VOLONTAIREMENT fictif pour ces tests isoles (ce n'est PAS le
# vrai match_id Rennes-Marseille 2025/26 du catalogue reel) - le catalogue
# est donc explicitement remplace (monkeypatch) pour que ces tests restent
# independants du contenu reel du depot, voir ``_mock_catalog``.
_RAW = [_us_raw("31967", "2025-08-15", "19:45", "Rennes", "Marseille", 1, 0)]
_MATCH_SUMMARY = MatchSummary(
    match_id="31967", competition="ligue1", season="2025_26",
    kickoff_utc=datetime(2025, 8, 15, 19, 45, tzinfo=timezone.utc),
    home_team="Rennes", away_team="Marseille", is_played=True,
)


def _mock_catalog(monkeypatch) -> None:
    monkeypatch.setattr(he.match_catalog, "list_matches", Mock(return_value=(_MATCH_SUMMARY,)))


def test_historical_match_with_odds_available(tmp_path, monkeypatch) -> None:
    fd = [_fd("15/08/2025", "Rennes", "Marseille", b365_over=1.88, b365_under=1.98)]
    monkeypatch.setattr(he, "run_prediction", Mock(return_value=_output()))
    _mock_catalog(monkeypatch)
    result = he.evaluate_historical_match(
        _RAW, fd, "ligue1", "2025_26", "31967", journal_path=tmp_path / "j.jsonl",
    )
    assert result["match_id"] == "31967"
    assert result["market_odds_over_2_5"] == pytest.approx(1.88)
    assert result["market_odds_under_2_5"] == pytest.approx(1.98)
    assert result["status"] == "SETTLED"
    assert result["settlement"]["home_goals_actual"] == 1
    assert result["settlement"]["away_goals_actual"] == 0
    assert result["settlement"]["market_result_over_2_5"] == "Under"  # 1 but total, 1 < 2.5


def test_historical_match_without_football_data_file(tmp_path, monkeypatch) -> None:
    """football_data_records=None (aucun fichier reel pour cette saison,
    ex. ligue1/2026_27) - jamais une cote inventee, observation produite
    quand meme via le chemin existant (MARKET_DATA_UNAVAILABLE)."""
    monkeypatch.setattr(
        he, "run_prediction",
        Mock(return_value=_output(decision="NO_BET", reasons=["MARKET_DATA_UNAVAILABLE"])),
    )
    _mock_catalog(monkeypatch)
    result = he.evaluate_historical_match(
        _RAW, None, "ligue1", "2025_26", "31967", journal_path=tmp_path / "j.jsonl",
    )
    assert result["market_odds_over_2_5"] is None
    assert result["market_odds_under_2_5"] is None
    assert result["decision_reason"] == ["MARKET_DATA_UNAVAILABLE"]


def test_historical_result_matches_canonical_understat_score(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(he, "run_prediction", Mock(return_value=_output()))
    _mock_catalog(monkeypatch)
    result = he.evaluate_historical_match(
        _RAW, None, "ligue1", "2025_26", "31967", journal_path=tmp_path / "j.jsonl",
    )
    assert (result["settlement"]["home_goals_actual"], result["settlement"]["away_goals_actual"]) == (1, 0)
    assert result["settlement"]["total_goals_actual"] == 1


def test_run_prediction_is_the_production_path_used(tmp_path, monkeypatch) -> None:
    """Verifie explicitement que evaluate_historical_match appelle bien
    run_prediction (le chemin de production, api.prediction_adapter) -
    jamais une seconde logique de prediction."""
    mock_run = Mock(return_value=_output())
    monkeypatch.setattr(he, "run_prediction", mock_run)
    _mock_catalog(monkeypatch)
    fd = [_fd("15/08/2025", "Rennes", "Marseille", b365_over=1.88, b365_under=1.98)]
    he.evaluate_historical_match(_RAW, fd, "ligue1", "2025_26", "31967", journal_path=tmp_path / "j.jsonl")

    mock_run.assert_called_once()
    _, kwargs = mock_run.call_args
    assert kwargs["competition"] == "ligue1"
    assert kwargs["season"] == "2025_26"
    assert kwargs["home_team"] == "Rennes"
    assert kwargs["away_team"] == "Marseille"
    assert kwargs["market_odds"] == {"Over": pytest.approx(1.88), "Under": pytest.approx(1.98)}
    assert kwargs["kickoff_utc"].tzinfo is None  # kickoff naif, meme convention que predict_match.py


def test_point_in_time_prediction_is_independent_of_the_real_score(tmp_path, monkeypatch) -> None:
    """Point-in-time : la prediction (sorties modele/decision) ne doit
    JAMAIS dependre du score reel. Deux corpus identiques sauf le score
    du match evalue doivent produire EXACTEMENT la meme prediction, seul
    le settlement differe."""
    monkeypatch.setattr(he, "run_prediction", Mock(return_value=_output(p_over_2_5=0.6123)))
    _mock_catalog(monkeypatch)

    raw_a = [_us_raw("31967", "2025-08-15", "19:45", "Rennes", "Marseille", 1, 0)]
    raw_b = [_us_raw("31967", "2025-08-15", "19:45", "Rennes", "Marseille", 5, 4)]  # score "futur" different

    result_a = he.evaluate_historical_match(raw_a, None, "ligue1", "2025_26", "31967", journal_path=tmp_path / "a.jsonl")
    result_b = he.evaluate_historical_match(raw_b, None, "ligue1", "2025_26", "31967", journal_path=tmp_path / "b.jsonl")

    # Tout ce qui est pre-match est identique...
    for key in ("decision", "decision_reason", "models", "market_odds_over_2_5", "market_odds_under_2_5"):
        assert result_a[key] == result_b[key]
    # ...seul le reglement post-match differe, exactement comme attendu.
    assert result_a["settlement"]["total_goals_actual"] == 1
    assert result_b["settlement"]["total_goals_actual"] == 9


def test_never_uses_closing_odds_even_when_present(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(he, "run_prediction", Mock(return_value=_output()))
    _mock_catalog(monkeypatch)
    fd = [_fd("15/08/2025", "Rennes", "Marseille", b365_over=1.88, b365_under=1.98, b365_close_over=99.0, b365_close_under=99.0)]
    result = he.evaluate_historical_match(_RAW, fd, "ligue1", "2025_26", "31967", journal_path=tmp_path / "j.jsonl")
    assert result["market_odds_over_2_5"] == pytest.approx(1.88)
    assert result["market_odds_under_2_5"] == pytest.approx(1.98)


def test_unknown_match_id_raises() -> None:
    with pytest.raises(he.HistoricalEvaluationError, match="introuvable dans le catalogue"):
        he.evaluate_historical_match(_RAW, None, "ligue1", "2025_26", "no-such-id", journal_path=Path("unused.jsonl"))


def test_match_id_absent_from_understat_raw_raises(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(he, "run_prediction", Mock(return_value=_output()))
    _mock_catalog(monkeypatch)
    empty_raw: list[dict] = []
    with pytest.raises(he.HistoricalEvaluationError, match="introuvable dans le corpus Understat"):
        he.evaluate_historical_match(empty_raw, None, "ligue1", "2025_26", "31967", journal_path=tmp_path / "j.jsonl")


# --- test end-to-end REEL (donnees reelles du depot, aucun mock) ----------


def test_end_to_end_real_le_havre_angers_29683(tmp_path) -> None:
    """Match reel deja utilise comme golden case (P2-P16) : Le Havre -
    Angers, Ligue1 2025/26, match_id 29683. Confirme que le pont cotes
    reelles + l'evaluation historique produisent exactement les memes
    cotes B365 d'ouverture (Over=2.20, Under=1.67) que la demonstration
    bout-en-bout deja faite lors de l'ajout du bridge, et que le resultat
    historique est correctement recupere - PAS une demonstration de
    rentabilite (un seul match)."""
    from sys_foot_quant.data_engine.market_odds.football_data_loader import (
        football_data_csv_path,
        load_football_data_csv,
    )

    repo_root = Path(__file__).resolve().parent.parent.parent
    understat_path = repo_root / "research" / "xg_feasibility" / "runs" / "ligue1_2025_datesData.json"
    if not understat_path.exists():
        pytest.skip("Corpus Understat reel absent.")
    with open(understat_path) as f:
        understat_raw = json.load(f)

    fd_path = football_data_csv_path("ligue1", "2025_26", root=repo_root / "research" / "market_odds" / "football_data" / "runs")
    if fd_path is None or not fd_path.exists():
        pytest.skip("Fichier Football-Data reel absent.")
    fd_records = load_football_data_csv(fd_path, league="ligue1", season="2025_26")

    result = he.evaluate_historical_match(
        understat_raw, fd_records, "ligue1", "2025_26", "29683", journal_path=tmp_path / "real.jsonl",
    )

    assert result["match_id"] == "29683"
    assert result["home_team"] == "Le Havre"
    assert result["away_team"] == "Angers"
    assert result["market_odds_over_2_5"] == pytest.approx(2.20)
    assert result["market_odds_under_2_5"] == pytest.approx(1.67)
    assert result["decision"] in ("BET", "NO_BET")
    assert result["status"] == "SETTLED"
    assert result["settlement"]["total_goals_actual"] is not None
    assert result["settlement"]["market_result_over_2_5"] in ("Over", "Under")
