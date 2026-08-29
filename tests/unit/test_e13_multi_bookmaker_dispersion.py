"""Tests unitaires des fonctions PURES d'E13
(scripts/run_stage22_e13_multi_bookmaker_dispersion.py) - avant toute
execution reelle."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage22_e13_multi_bookmaker_dispersion.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage22_e13_multi_bookmaker_dispersion", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e13_module():
    return _load_script()


# --- raw_over_under_column_inventory ------------------------------------------


def test_raw_inventory_detects_only_b365_ou(e13_module, tmp_path) -> None:
    header = "Div,Date,B365H,B365D,B365A,BWH,PSH,B365>2.5,B365<2.5,Max>2.5,Max<2.5,Avg>2.5,BFE>2.5,B365C>2.5\n"
    path = tmp_path / "E0.csv"
    path.write_text(header + "E0,16/08/2024,1.6,4.2,5.25,1.65,1.63,1.85,1.95,1.9,2.0,1.88,1.87,99.9\n")
    out = e13_module.raw_over_under_column_inventory(path)
    assert out["bookmakers_with_ou_column"] == sorted({"Avg", "B365", "BFE", "Max"})


def test_raw_inventory_detects_pinnacle_ou_column(e13_module, tmp_path) -> None:
    """Verifie explicitement la correction E13 : la colonne ``P>2.5``/
    ``P<2.5`` (Pinnacle) doit etre detectee comme un bookmaker distinct,
    jamais confondue avec ``PS`` (utilise pour le 1X2)."""
    header = "Div,Date,B365H,PSH,B365>2.5,B365<2.5,P>2.5,P<2.5\n"
    path = tmp_path / "E0.csv"
    path.write_text(header + "E0,16/08/2024,1.6,1.63,1.85,1.95,1.80,1.90\n")
    out = e13_module.raw_over_under_column_inventory(path)
    assert out["bookmakers_with_ou_column"] == sorted({"B365", "P"})


def test_raw_inventory_excludes_closing_columns(e13_module, tmp_path) -> None:
    header = "Div,B365>2.5,B365<2.5,B365C>2.5,B365C<2.5\n"
    path = tmp_path / "E0.csv"
    path.write_text(header + "E0,1.85,1.95,1.88,1.92\n")
    out = e13_module.raw_over_under_column_inventory(path)
    assert "B365C>2.5" not in out["ou_columns_non_closing"]
    assert "B365C<2.5" not in out["ou_columns_non_closing"]


# --- classify_dispersion / classify_spread ------------------------------------


@pytest.mark.parametrize(
    "std,expected",
    [(0.0, "<0.5pt"), (0.0049, "<0.5pt"), (0.005, "0.5-1.0pt"), (0.0099, "0.5-1.0pt"), (0.01, "1.0-2.0pt"), (0.0199, "1.0-2.0pt"), (0.02, ">=2.0pt"), (0.5, ">=2.0pt")],
)
def test_classify_dispersion_boundaries(e13_module, std, expected) -> None:
    assert e13_module.classify_dispersion(std) == expected


def test_classify_dispersion_never_takes_outcome(e13_module) -> None:
    import inspect

    assert list(inspect.signature(e13_module.classify_dispersion).parameters) == ["std"]


@pytest.mark.parametrize(
    "spread,expected",
    [(0.0, "faible (<5pts)"), (0.0499, "faible (<5pts)"), (0.05, "moderee (5-10pts)"), (0.0999, "moderee (5-10pts)"), (0.10, "elevee (>=10pts)"), (0.9, "elevee (>=10pts)")],
)
def test_classify_spread_boundaries(e13_module, spread, expected) -> None:
    assert e13_module.classify_spread(spread) == expected


# --- build_result_lookup / build_dispersion_dataframe -------------------------


class _FakeRecord:
    def __init__(self, match_id, league, season, **kwargs):
        self.match_id = match_id
        self.league = league
        self.season = season
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_build_dispersion_dataframe_skips_single_bookmaker_selection(e13_module) -> None:
    class _FakeE9:
        @staticmethod
        def normalized_probs_by_selection(odds):
            return {"H": {"B365": 0.5}, "D": {"B365": 0.3}, "A": {"B365": 0.2}}  # un seul bookmaker partout

    rec = _FakeRecord("1", "premier_league", "2024_25", odds_1x2={})
    df = e13_module.build_dispersion_dataframe(
        _FakeE9(), [rec], {"1": (1, 0)}, "odds_1x2", e13_module._outcome_by_selection_1x2
    )
    assert df.empty  # aucune selection avec >=2 bookmakers


def test_build_dispersion_dataframe_basic_1x2(e13_module) -> None:
    class _FakeE9:
        @staticmethod
        def normalized_probs_by_selection(odds):
            return {
                "H": {"B365": 0.50, "BW": 0.52, "PS": 0.48},
                "D": {"B365": 0.30, "BW": 0.28, "PS": 0.30},
                "A": {"B365": 0.20, "BW": 0.20, "PS": 0.22},
            }

    rec = _FakeRecord("1", "premier_league", "2024_25", odds_1x2={})
    df = e13_module.build_dispersion_dataframe(
        _FakeE9(), [rec], {"1": (1, 0)}, "odds_1x2", e13_module._outcome_by_selection_1x2
    )  # home win
    assert len(df) == 3  # H, D, A toutes avec 3 bookmakers
    row_h = df[df["selection"] == "H"].iloc[0]
    assert row_h["outcome"] == 1.0
    assert row_h["n_bookmakers"] == 3
    assert row_h["reference_prob"] == pytest.approx(0.50)
    row_a = df[df["selection"] == "A"].iloc[0]
    assert row_a["outcome"] == 0.0


def test_build_dispersion_dataframe_basic_over_under(e13_module) -> None:
    class _FakeE9:
        @staticmethod
        def normalized_probs_by_selection(odds):
            return {
                "Over": {"B365": 0.55, "P": 0.53},
                "Under": {"B365": 0.45, "P": 0.47},
            }

    rec = _FakeRecord("1", "premier_league", "2024_25", odds_over_under_2_5={})
    df = e13_module.build_dispersion_dataframe(
        _FakeE9(), [rec], {"1": (2, 1)}, "odds_over_under_2_5", e13_module._outcome_by_selection_over_under_25
    )  # 2+1=3 buts -> Over
    assert len(df) == 2
    row_over = df[df["selection"] == "Over"].iloc[0]
    assert row_over["outcome"] == 1.0
    assert row_over["n_bookmakers"] == 2
    assert row_over["reference_prob"] == pytest.approx(0.55)
    row_under = df[df["selection"] == "Under"].iloc[0]
    assert row_under["outcome"] == 0.0


def test_build_dispersion_dataframe_skips_unknown_match(e13_module) -> None:
    class _FakeE9:
        @staticmethod
        def normalized_probs_by_selection(odds):
            return {"H": {"B365": 0.5, "BW": 0.5}}

    rec = _FakeRecord("unknown", "premier_league", "2024_25", odds_1x2={})
    df = e13_module.build_dispersion_dataframe(
        _FakeE9(), [rec], {}, "odds_1x2", e13_module._outcome_by_selection_1x2
    )  # pas de resultat connu
    assert df.empty


# --- build_individual_vs_consensus_dataframe ----------------------------------


def test_build_individual_vs_consensus_dataframe_classifies_gap(e13_module) -> None:
    class _FakeE9:
        @staticmethod
        def normalized_probs_by_selection(odds):
            return {"H": {"B365": 0.50, "BW": 0.50, "PS": 0.70}}  # PS nettement different

    rec = _FakeRecord("1", "premier_league", "2024_25", odds_1x2={})
    df = e13_module.build_individual_vs_consensus_dataframe(
        _FakeE9(), [rec], {"1": (1, 0)}, "odds_1x2", e13_module._outcome_by_selection_1x2
    )
    assert len(df) == 3
    ps_row = df[df["bookmaker"] == "PS"].iloc[0]
    assert ps_row["gap_category"] in {"ecart notable", "ecart marque"}


def test_build_individual_vs_consensus_dataframe_over_under(e13_module) -> None:
    class _FakeE9:
        @staticmethod
        def normalized_probs_by_selection(odds):
            return {"Over": {"B365": 0.55, "P": 0.53}}

    rec = _FakeRecord("1", "premier_league", "2024_25", odds_over_under_2_5={})
    df = e13_module.build_individual_vs_consensus_dataframe(
        _FakeE9(), [rec], {"1": (2, 1)}, "odds_over_under_2_5", e13_module._outcome_by_selection_over_under_25
    )
    assert len(df) == 2
    assert set(df["bookmaker"]) == {"B365", "P"}
    assert (df["outcome"] == 1.0).all()  # 3 buts -> Over


# --- restrict_to_canonical_selection --------------------------------------------


def test_restrict_to_canonical_selection_keeps_only_that_selection(e13_module) -> None:
    df = pd.DataFrame({"selection": ["Over", "Under", "Over"], "value": [1, 2, 3]})
    out = e13_module.restrict_to_canonical_selection(df, "Over")
    assert list(out["selection"]) == ["Over", "Over"]
    assert list(out["value"]) == [1, 3]


def test_restrict_to_canonical_selection_empty_df_is_noop(e13_module) -> None:
    df = pd.DataFrame({"selection": [], "value": []})
    out = e13_module.restrict_to_canonical_selection(df, "Over")
    assert out.empty


def test_pooling_over_and_under_without_restriction_forces_zero_bias(e13_module) -> None:
    """Documente explicitement la degenerescence algebrique qui motive
    `restrict_to_canonical_selection` : sans restriction, le biais agrege
    d'un marche a 2 issues completement complementaires est TOUJOURS
    exactement 0, quelle que soit la vraie qualite de calibration -
    jamais un vrai resultat d'absence de biais."""
    df = pd.DataFrame(
        {
            "cat": ["A"] * 4,
            "p": [0.7, 0.3, 0.6, 0.4],  # Over=0.7/0.6 (biaise), Under=1-Over
            "outcome": [1.0, 0.0, 0.0, 1.0],  # Over gagne match 1, perd match 2
        }
    )
    table = e13_module.calibration_by_category_table(df, "cat", ["A"], "p")
    assert table.iloc[0]["biais"] == pytest.approx(0.0)  # force a 0 par construction, pas un vrai resultat

    over_only = df.iloc[[0, 2]]  # ne garder que les lignes "Over"
    table_over = e13_module.calibration_by_category_table(over_only, "cat", ["A"], "p")
    assert table_over.iloc[0]["biais"] != pytest.approx(0.0)  # le vrai biais redevient visible


# --- calibration_by_category_table --------------------------------------------


def test_calibration_by_category_table_basic(e13_module) -> None:
    df = pd.DataFrame({"cat": ["A"] * 4, "p": [0.5, 0.5, 0.5, 0.5], "outcome": [1.0, 1.0, 0.0, 0.0]})
    table = e13_module.calibration_by_category_table(df, "cat", ["A"], "p")
    row = table.iloc[0]
    assert row["p_moyen"] == pytest.approx(0.5)
    assert row["freq_reelle"] == pytest.approx(0.5)
    assert row["biais"] == pytest.approx(0.0)


def test_calibration_by_category_table_empty_category(e13_module) -> None:
    df = pd.DataFrame({"cat": ["A"], "p": [0.5], "outcome": [1.0]})
    table = e13_module.calibration_by_category_table(df, "cat", ["A", "B"], "p")
    row_b = table[table["categorie"] == "B"].iloc[0]
    assert row_b["n"] == 0
    assert bool(row_b["insuffisant"]) is True


# --- test_high_dispersion_worse_calibrated ------------------------------------


def test_high_dispersion_worse_calibrated_insufficient_data(e13_module):
    e12 = e13_module._load_e12()
    df = pd.DataFrame({"dispersion_std": [0.001], "consensus_mean": [0.5], "outcome": [1.0]})
    out = e13_module.test_high_dispersion_worse_calibrated(df, e12)
    assert out["boot"] is None


def test_high_dispersion_worse_calibrated_runs(e13_module):
    e12 = e13_module._load_e12()
    rng = np.random.default_rng(0)
    n = 50
    df = pd.DataFrame(
        {
            "dispersion_std": np.concatenate([rng.uniform(0.0, 0.003, n), rng.uniform(0.02, 0.05, n)]),
            "consensus_mean": rng.uniform(0.3, 0.7, 2 * n),
            "outcome": rng.binomial(1, 0.5, 2 * n).astype(float),
        }
    )
    out = e13_module.test_high_dispersion_worse_calibrated(df, e12)
    assert out["boot"] is not None
    assert out["verdict"] in {
        e12.VERDICT_DEMONTREE,
        e12.VERDICT_CONTRADICTOIRE,
        e12.VERDICT_DIRECTIONNELLE,
        e12.VERDICT_ABSENCE_PREUVE,
    }


# --- compare_consensus_vs_reference_alone --------------------------------------


def test_compare_consensus_vs_reference_alone_basic(e13_module) -> None:
    df = pd.DataFrame(
        {
            "reference_prob": [0.6, 0.4, 0.5, 0.5],
            "consensus_mean": [0.55, 0.45, 0.5, 0.5],
            "outcome": [1.0, 0.0, 1.0, 0.0],
        }
    )
    out = e13_module.compare_consensus_vs_reference_alone(df)
    assert out is not None
    assert out["n"] == 4


def test_compare_consensus_vs_reference_alone_drops_nan_reference(e13_module) -> None:
    df = pd.DataFrame(
        {"reference_prob": [0.6, np.nan, 0.5], "consensus_mean": [0.55, 0.45, 0.5], "outcome": [1.0, 0.0, 1.0]}
    )
    out = e13_module.compare_consensus_vs_reference_alone(df)
    assert out["n"] == 2  # la ligne NaN est exclue


def test_compare_consensus_vs_reference_alone_none_when_too_few_rows(e13_module) -> None:
    df = pd.DataFrame({"reference_prob": [0.6, np.nan], "consensus_mean": [0.55, 0.45], "outcome": [1.0, 0.0]})
    assert e13_module.compare_consensus_vs_reference_alone(df) is None


# --- compare_model_vs_ou_consensus ---------------------------------------------


def test_compare_model_vs_ou_consensus_basic(e13_module) -> None:
    df = pd.DataFrame(
        {
            "match_id": ["1", "2", "3"],
            "selection": ["Over", "Over", "Under"],
            "consensus_mean": [0.55, 0.60, 0.40],
            "outcome": [1.0, 0.0, 1.0],
        }
    )
    model_probs = {"1": 0.58, "2": 0.55}
    out = e13_module.compare_model_vs_ou_consensus(df, model_probs)
    assert out is not None
    assert out["n"] == 2  # seulement les lignes "Over" avec un p_model connu ("3" est "Under")


def test_compare_model_vs_ou_consensus_none_when_too_few_rows(e13_module) -> None:
    df = pd.DataFrame({"match_id": ["1"], "selection": ["Over"], "consensus_mean": [0.55], "outcome": [1.0]})
    model_probs = {"1": 0.58}
    assert e13_module.compare_model_vs_ou_consensus(df, model_probs) is None


def test_compare_model_vs_ou_consensus_ignores_under_selection(e13_module) -> None:
    df = pd.DataFrame(
        {
            "match_id": ["1", "2"],
            "selection": ["Under", "Under"],
            "consensus_mean": [0.45, 0.40],
            "outcome": [0.0, 1.0],
        }
    )
    model_probs = {"1": 0.42, "2": 0.38}
    assert e13_module.compare_model_vs_ou_consensus(df, model_probs) is None


# --- arbitrage_report -----------------------------------------------------------


def test_arbitrage_report_detects_none_when_normal_margins(e13_module) -> None:
    class _Rec:
        odds_1x2 = {"H": {"B365": 1.90}, "D": {"B365": 3.50}, "A": {"B365": 4.00}}

    out = e13_module.arbitrage_report([_Rec()], "odds_1x2")
    assert out["n_arbitrage_positive"] == 0
    assert out["n_matches"] == 1
    assert out["n_evaluable"] == 1


def test_arbitrage_report_detects_manufactured_arb(e13_module) -> None:
    class _Rec:
        odds_1x2 = {"H": {"B365": 4.0}, "D": {"B365": 4.0}, "A": {"B365": 4.0}}  # somme = 0.75 < 1

    out = e13_module.arbitrage_report([_Rec()], "odds_1x2")
    assert out["n_arbitrage_positive"] == 1
    assert out["n_evaluable"] == 1


def test_arbitrage_report_skips_non_evaluable_match(e13_module) -> None:
    class _Rec:
        odds_1x2 = {"H": {"B365": 1.90}, "D": {}, "A": {"B365": 4.00}}  # D sans aucun bookmaker

    out = e13_module.arbitrage_report([_Rec()], "odds_1x2")
    assert out["n_matches"] == 1
    assert out["n_evaluable"] == 0
    assert out["n_arbitrage_positive"] == 0


def test_arbitrage_report_over_under(e13_module) -> None:
    class _Rec:
        odds_over_under_2_5 = {"Over": {"B365": 1.90, "P": 1.95}, "Under": {"B365": 2.00, "P": 1.98}}

    out = e13_module.arbitrage_report([_Rec()], "odds_over_under_2_5")
    assert out["n_matches"] == 1
    assert out["n_evaluable"] == 1
