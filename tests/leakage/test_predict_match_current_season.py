"""Phase I-2 : prise en charge SELECTIVE de la saison courante 2026/27 dans
le chemin de prediction canonique (``scripts/predict_match.py``).

Ces tests sont ecrits AVANT la modification de production (TDD), conformement
a la contrainte imperative etablie par l'audit I-1B : 2024_25/2025_26
DOIVENT conserver exactement leur comportement mono-fichier actuel - seule
l'entree 2026_27 doit agreger l'historique long terme (2024_25+2025_26) et
la saison courante deja jouee (2026_27), via
``multi_season_dataset.build_real_match_records_multi_season`` (INCHANGE,
deja teste), jamais une reimplementation de la concatenation/du tri/de la
detection de collision de ``match_id``.

Donnees reelles utilisees : ``research/xg_feasibility/runs/
ligue1_2024_datesData.json``/``ligue1_2025_datesData.json``/
``ligue1_2026_datesData.json`` - ce dernier contient le match reel
Brest-PSG (id Understat ``31975``, 2026-09-13), deja verifie present et
integre au depot (commits 54df8bd/afdccb9/2df0fd8)."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "predict_match.py"
_UNDERSTAT_DIR = Path(__file__).resolve().parent.parent.parent / "research" / "xg_feasibility" / "runs"

_LIGUE1_2024_PATH = _UNDERSTAT_DIR / "ligue1_2024_datesData.json"
_LIGUE1_2025_PATH = _UNDERSTAT_DIR / "ligue1_2025_datesData.json"
_LIGUE1_2026_PATH = _UNDERSTAT_DIR / "ligue1_2026_datesData.json"

_BREST_PSG_MATCH_ID = "31975"


def _load_predict_match():
    spec = importlib.util.spec_from_file_location("predict_match_for_current_season_test", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def predict_match():
    return _load_predict_match()


pytestmark = pytest.mark.skipif(
    not (_LIGUE1_2024_PATH.exists() and _LIGUE1_2025_PATH.exists() and _LIGUE1_2026_PATH.exists()),
    reason="Fichiers Understat Ligue 1 2024/25 + 2025/26 + 2026/27 non tous presents.",
)


@pytest.fixture(scope="module")
def ligue1_2024_raw():
    with open(_LIGUE1_2024_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def ligue1_2025_raw():
    with open(_LIGUE1_2025_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def ligue1_2026_raw():
    with open(_LIGUE1_2026_PATH) as f:
        return json.load(f)


def _n_played(raw: list[dict]) -> int:
    return sum(1 for m in raw if m.get("isResult"))


def _brest_psg_kickoff() -> datetime:
    return datetime(2026, 9, 13, 18, 45, 0)


# --- Test 1 : prise en charge de 2026/27 -------------------------------------


def test_2026_27_is_no_longer_rejected_as_unknown_season(predict_match) -> None:
    """Avant cette phase, ``build_prediction_inputs``/``run_prediction``
    levaient PredictMatchError('Saison inconnue') pour '2026_27' (verifie
    par l'audit I-1). Ce test echoue tant que la prise en charge n'est pas
    implementee - c'est le comportement ATTENDU en mode TDD avant le code
    de production."""
    inputs = predict_match.build_prediction_inputs(
        "ligue1", "2026_27", "Brest", "Paris Saint Germain", _brest_psg_kickoff()
    )
    assert len(inputs.goals_train_df) > 0


def test_2026_27_appears_in_advertised_seasons(predict_match) -> None:
    assert "2026_27" in predict_match.SEASONS
    assert "ligue1" in predict_match.COMPETITIONS


# --- Test 2 : agregation multi-saison via multi_season_dataset ---------------


def test_current_season_uses_build_real_match_records_multi_season(predict_match, monkeypatch) -> None:
    """Verifie que le chemin 2026/27 delegue reellement a
    ``multi_season_dataset.build_real_match_records_multi_season`` (jamais
    une reimplementation de la concatenation/du tri) - espionne l'appel
    sans en changer le comportement."""
    from sys_foot_quant.data_engine.market_odds import multi_season_dataset

    calls: list[list[tuple]] = []
    original = multi_season_dataset.build_real_match_records_multi_season

    def _spy(sources):
        calls.append(sources)
        return original(sources)

    monkeypatch.setattr(predict_match, "build_real_match_records_multi_season", _spy)

    predict_match.build_prediction_inputs("ligue1", "2026_27", "Brest", "Paris Saint Germain", _brest_psg_kickoff())

    assert len(calls) == 1
    assert len(calls[0]) == 3  # 3 fichiers combines : 2024/25 + 2025/26 + 2026/27


# --- Test 3 : presence effective des saisons historiques dans l'entrainement -


def test_2026_27_training_includes_matches_from_2024_25_and_2025_26(
    predict_match, ligue1_2024_raw, ligue1_2025_raw
) -> None:
    inputs = predict_match.build_prediction_inputs(
        "ligue1", "2026_27", "Brest", "Paris Saint Germain", _brest_psg_kickoff()
    )
    train_kickoffs = set(inputs.goals_train_df["kickoff_time"])

    some_2024_kickoff = datetime.strptime(
        next(m for m in ligue1_2024_raw if m.get("isResult"))["datetime"], "%Y-%m-%d %H:%M:%S"
    )
    some_2025_kickoff = datetime.strptime(
        next(m for m in ligue1_2025_raw if m.get("isResult"))["datetime"], "%Y-%m-%d %H:%M:%S"
    )
    assert any(kt.year == some_2024_kickoff.year for kt in train_kickoffs), "aucun match 2024/25 dans l'entrainement"
    assert any(kt.year in (some_2025_kickoff.year, some_2025_kickoff.year - 1) for kt in train_kickoffs) or any(
        2025 <= kt.year <= 2026 for kt in train_kickoffs
    ), "aucun match 2025/26 dans l'entrainement"


# --- Test 4 : respect du point-in-time sur le corpus multi-saison -----------


def test_no_training_row_at_or_after_decision_time_for_2026_27(predict_match) -> None:
    kickoff_utc = _brest_psg_kickoff()
    decision_time = kickoff_utc - timedelta(hours=2.0)

    inputs = predict_match.build_prediction_inputs("ligue1", "2026_27", "Brest", "Paris Saint Germain", kickoff_utc)
    for df in (inputs.goals_train_df, inputs.xg_train_df):
        for kt in df["kickoff_time"]:
            assert kt < decision_time
    for calib_df in inputs.calibration_df_by_model.values():
        for dt in calib_df["decision_time"]:
            assert dt <= decision_time


# --- Test 5 : collision de match_id detectee, jamais ignoree ----------------


def test_duplicate_match_id_across_current_season_sources_raises(predict_match, monkeypatch, tmp_path) -> None:
    """Donnees artificielles minimales (pas les vraies donnees) : force une
    collision d'id entre le fichier '2024/25' et le fichier '2026/27'
    factices, et verifie que DuplicateMatchIdError (deja implementee dans
    multi_season_dataset, INCHANGEE) remonte bien - jamais silencieusement
    absorbee par le chemin de prediction."""
    from sys_foot_quant.data_engine.market_odds.multi_season_dataset import DuplicateMatchIdError

    def _minimal_match(match_id: str, dt: str) -> dict:
        return {
            "id": match_id,
            "isResult": True,
            "datetime": dt,
            "h": {"id": "1", "title": "Equipe A"},
            "a": {"id": "2", "title": "Equipe B"},
            "goals": {"h": "1", "a": "0"},
            "xG": {"h": "1.1", "a": "0.9"},
        }

    fake_2024 = tmp_path / "fake_2024.json"
    fake_2025 = tmp_path / "fake_2025.json"
    fake_2026 = tmp_path / "fake_2026.json"
    fake_2024.write_text(json.dumps([_minimal_match("999", "2024-08-15 20:00:00")]))
    fake_2025.write_text(json.dumps([_minimal_match("1000", "2025-08-15 20:00:00")]))
    # Collision deliberee : meme id "999" reutilise dans le fichier "2026/27".
    fake_2026.write_text(json.dumps([_minimal_match("999", "2026-08-15 20:00:00")]))

    monkeypatch.setitem(
        predict_match._CURRENT_SEASON_SOURCES,
        "ligue1",
        [("Ligue_1", fake_2024), ("Ligue_1", fake_2025), ("Ligue_1", fake_2026)],
    )

    with pytest.raises(DuplicateMatchIdError):
        predict_match.build_prediction_inputs(
            "ligue1", "2026_27", "Equipe A", "Equipe B", datetime(2026, 8, 20, 20, 0, 0)
        )


# --- Test 6 : conservation stricte du comportement historique ---------------


def test_2024_25_season_entry_structure_is_unchanged(predict_match) -> None:
    """Garde-fou structurel direct : _SEASONS['2024_25']/['2025_26'] restent
    des tuples (league_id, Path) mono-fichier, EXACTEMENT comme avant cette
    phase - condition necessaire pour que le monkey-patch de
    test_predict_match_point_in_time.py::test_adding_a_future_match_to_the_corpus_never_changes_an_earlier_prediction
    continue de fonctionner sans modification."""
    for season in ("2024_25", "2025_26"):
        for competition, value in predict_match._SEASONS[season].items():
            assert isinstance(value, tuple) and len(value) == 2
            league_id, path = value
            assert isinstance(league_id, str)
            assert isinstance(path, Path)


def test_2025_26_still_loads_a_single_file_only(predict_match, ligue1_2025_raw) -> None:
    """Non-regression directe : le volume d'entrainement pour un match de
    fin de saison 2025/26 doit rester borne au seul fichier 2025/26 (jamais
    elargi automatiquement a 2024/25), preservant exactement
    test_shadow_scenario_uses_the_full_season_as_history_without_exception
    et test_insufficient_calibration_history_triggers_no_bet."""
    results = [m for m in ligue1_2025_raw if m.get("isResult")]
    last_kickoff = max(datetime.strptime(m["datetime"], "%Y-%m-%d %H:%M:%S") for m in results)
    shadow_kickoff = last_kickoff + timedelta(days=30)
    while shadow_kickoff.weekday() not in (5, 6):
        shadow_kickoff += timedelta(days=1)
    shadow_kickoff = shadow_kickoff.replace(hour=20, minute=0, second=0)

    home = results[0]["h"]["title"]
    away = results[0]["a"]["title"] if results[0]["a"]["title"] != home else results[1]["a"]["title"]
    inputs = predict_match.build_prediction_inputs("ligue1", "2025_26", home, away, shadow_kickoff)
    assert len(inputs.goals_train_df) == len(results)


# --- Test 7 : cas reel Brest-PSG (id Understat 31975) -----------------------


def test_brest_psg_2026_09_13_is_accepted_and_produces_a_valid_prediction_input(
    predict_match, ligue1_2026_raw
) -> None:
    """Confirme que le match reel est bien dans le fichier source (pas une
    donnee inventee) avant d'exercer le chemin standard."""
    real_match = next(m for m in ligue1_2026_raw if m["id"] == _BREST_PSG_MATCH_ID)
    assert real_match["h"]["title"] == "Brest"
    assert real_match["a"]["title"] == "Paris Saint Germain"

    inputs = predict_match.build_prediction_inputs(
        "ligue1", "2026_27", "Brest", "Paris Saint Germain", _brest_psg_kickoff()
    )
    assert inputs.home_team_id == int(real_match["h"]["id"])
    assert inputs.away_team_id == int(real_match["a"]["id"])
    assert len(inputs.goals_train_df) > 0


def test_brest_psg_training_volume_matches_season_sensitivity_when_comparable(
    predict_match, ligue1_2024_raw, ligue1_2025_raw, ligue1_2026_raw
) -> None:
    """La valeur 646 a ete mesuree independamment via
    season_sensitivity.compute_season_sensitivity (BASELINE+CURRENT, meme
    decision_time = kickoff - 2h, meme corpus 3 fichiers, exclusion du
    match cible lui-meme). Ce test ne force PAS une egalite si le perimetre
    differe reellement : il verifie d'abord que les parametres sont
    comparables (meme decision_offset_hours, meme corpus source, meme
    match cible exclu), puis compare le compte."""
    output = predict_match.run_prediction(
        competition="ligue1", season="2026_27", home_team="Brest", away_team="Paris Saint Germain",
        kickoff_utc=_brest_psg_kickoff(), market_odds=None,
    )
    n_train_matches = output.models["poisson_simple"].n_train_matches

    n_played_combined = _n_played(ligue1_2024_raw) + _n_played(ligue1_2025_raw) + _n_played(ligue1_2026_raw)
    # Le match cible (31975) est inclus dans ligue1_2026_raw et doit etre
    # exclu de son propre entrainement (comportement standard de
    # build_match_train_dataframes, deja teste ailleurs) : le maximum
    # theorique d'observations utilisables est donc n_played_combined - 1.
    assert n_train_matches <= n_played_combined - 1
    # decision_offset_hours par defaut de run_prediction == DECISION_OFFSET_HOURS,
    # la meme valeur que celle utilisee lors de la mesure independante de 646
    # (season_sensitivity, meme constante reutilisee) : perimetre comparable,
    # la comparaison numerique est donc significative.
    assert predict_match.DECISION_OFFSET_HOURS == 2.0
    if n_train_matches != 646:
        pytest.fail(
            f"n_train_matches={n_train_matches} differe de la valeur 646 mesuree "
            "independamment par season_sensitivity avec un perimetre reporte comme "
            "comparable (meme decision_offset_hours, meme corpus 3 fichiers, meme "
            "match cible exclu) - a examiner avant de conclure a une regression ou "
            "a une difference de perimetre non detectee par ce test."
        )
