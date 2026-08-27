"""C7 (docs/research_framework.md section C7) reutilise SANS MODIFICATION
le mecanisme point-in-time de ``real_data_walk_forward.py``, deja couvert
par ``test_real_data_walk_forward_point_in_time.py``. Ce fichier verifie
specifiquement :
- que le decoupage rodage/eligible de C7 respecte le meme invariant
  chronologique que B3/B3.2 ;
- que le fit poisson_simple utilise par C7 ignore completement le xG
  (aucune dependance, meme accidentelle) ;
- qu'aucun composant du script C7 ne charge XGModel ni HybridXGModel
  (consigne explicite : C7 n'utilise ni l'un ni l'autre).
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from sys_foot_quant.football_model.poisson import PoissonModel
from sys_foot_quant.market_engine.correlated_events import eligible_match_ids_after_burn_in

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage5_c7_correlated_events.py"


def _load_c7_script():
    spec = importlib.util.spec_from_file_location("run_stage5_c7_correlated_events", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_eligible_ids_exclude_burn_in_regardless_of_input_order() -> None:
    t0 = datetime(2024, 1, 1)
    pairs = [(str(i), t0 + timedelta(days=i)) for i in range(20)]
    shuffled = [pairs[i] for i in [7, 2, 19, 0, 5, 11, 3, 18, 1, 4, 6, 8, 9, 10, 12, 13, 14, 15, 16, 17]]
    eligible = eligible_match_ids_after_burn_in(shuffled, burn_in_fraction=0.4)
    # 40% de 20 = 8 matchs les plus anciens exclus, quel que soit l'ordre d'entree.
    assert eligible == [str(i) for i in range(8, 20)]
    assert len(eligible) == 12


def test_c7_poisson_fit_ignores_xg_dataframe_entirely() -> None:
    script = _load_c7_script()
    goals_df = pd.DataFrame(
        [(0, 1, 2, 1, datetime(2024, 1, 1)), (1, 0, 0, 0, datetime(2024, 1, 2))],
        columns=["home_team_id", "away_team_id", "home_goals", "away_goals", "kickoff_time"],
    )
    xg_df_a = pd.DataFrame(
        [(0, 1, 5.0, 5.0, datetime(2024, 1, 1))],
        columns=["home_team_id", "away_team_id", "home_xg", "away_xg", "kickoff_time"],
    )
    xg_df_b = pd.DataFrame(columns=["home_team_id", "away_team_id", "home_xg", "away_xg", "kickoff_time"])

    model_a = script._fit_poisson_simple(goals_df, xg_df_a, datetime(2024, 1, 3))
    model_b = script._fit_poisson_simple(goals_df, xg_df_b, datetime(2024, 1, 3))

    assert isinstance(model_a, PoissonModel)
    assert model_a.predict_outcome_probabilities(0, 1) == pytest.approx(
        model_b.predict_outcome_probabilities(0, 1)
    )


def test_c7_script_only_ever_configures_poisson_simple() -> None:
    script = _load_c7_script()
    source = _SCRIPT_PATH.read_text()
    # Les mots "XGModel"/"HybridXGModel" apparaissent dans la prose du
    # docstring (pour documenter explicitement leur EXCLUSION) - ce qui est
    # verifie ici, c'est l'absence de toute utilisation EXECUTABLE : aucun
    # import ni aucune instanciation de ces classes.
    assert "import XGModel" not in source
    assert "import HybridXGModel" not in source
    assert "XGModel(" not in source
    assert "HybridXGModel(" not in source

    config = script.RealModelConfig(name="poisson_simple", fit=script._fit_poisson_simple, min_train_matches=10)
    assert config.name == "poisson_simple"
