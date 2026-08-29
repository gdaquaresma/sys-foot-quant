"""Garde-fous point-in-time ABSOLUS pour les tirs cadres historiques
(Phase F, protocole etape 9 - non negociable) :
(a) aucune statistique d'un match FUTUR n'entre dans une moyenne
    historique ;
(b) une moyenne historique n'inclut jamais le match lui-meme ;
(c) aucune cote de CLOTURE n'est utilisee ici (`ShotsOnTargetMatchRecord`
    ne porte aucun champ de cote - verifie structurellement) ;
(d) aucune information posterieure a `decision_time` n'entre dans une
    feature ;
(e) aucun resultat futur n'influence la construction d'une feature.

Le dernier test de ce fichier injecte DELIBEREMENT une observation future
dans le pool et demontre a la fois qu'elle est exclue par le code reel ET
qu'elle AURAIT change le resultat si elle ne l'etait pas - un bug qui
romprait le filtre `sot_knowledge_time <= decision_time` ferait ECHOUER
ce test (jamais un test qui passerait silencieusement quoi qu'il arrive)."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.data_engine.market_odds.shots_on_target import (
    ShotsOnTargetMatchRecord,
    historical_sot_averages,
    sot_features_for_match,
    sot_training_pool,
)


def _record(match_id, kickoff, home_team_id, away_team_id, home_sot, away_sot):
    return ShotsOnTargetMatchRecord(
        match_id=match_id, league="premier_league", season="2024_25", kickoff_utc=kickoff,
        home_team_id=home_team_id, away_team_id=away_team_id,
        home_shots_on_target=home_sot, away_shots_on_target=away_sot,
        sot_knowledge_time=kickoff + timedelta(hours=2.0),
    )


# --------------------------------------------------------------------------
# (c) aucun champ de cote sur ShotsOnTargetMatchRecord - verification
# structurelle, jamais suppose.
# --------------------------------------------------------------------------


def test_shots_on_target_record_has_no_odds_field() -> None:
    field_names = {f.name for f in dataclasses.fields(ShotsOnTargetMatchRecord)}
    assert not any("odds" in n or "b365" in n or "close" in n for n in field_names)


# --------------------------------------------------------------------------
# (a)(b)(d)(e) le pool d'entrainement ne contient jamais le match evalue
# ni un match dont l'information n'etait pas encore connue.
# --------------------------------------------------------------------------


def test_pool_never_contains_a_match_with_knowledge_time_strictly_after_decision_time() -> None:
    decision_time = datetime(2024, 9, 1, tzinfo=timezone.utc)
    past = _record("1", datetime(2024, 8, 20, tzinfo=timezone.utc), 1, 2, 5, 3)
    future = _record("2", datetime(2024, 9, 10, tzinfo=timezone.utc), 3, 4, 9, 9)
    pool = sot_training_pool([past, future], decision_time, exclude_match_id="99")
    assert len(pool) == 1
    assert set(pool["home_team_id"]) == {1}


def test_pool_never_contains_the_evaluated_match_even_if_its_own_knowledge_time_would_pass() -> None:
    """Garde-fou redondant explicite (jamais suppose suffisant a lui
    seul) : meme un enregistrement dont `sot_knowledge_time` serait
    (de facon artificielle, hypothese jamais vraie en pratique)
    anterieur ou egal a `decision_time` doit rester exclu s'il porte le
    `match_id` du match evalue."""
    decision_time = datetime(2024, 9, 1, tzinfo=timezone.utc)
    self_record = _record("EVAL", datetime(2024, 8, 1, tzinfo=timezone.utc), 1, 2, 5, 3)
    pool = sot_training_pool([self_record], decision_time, exclude_match_id="EVAL")
    assert pool.empty


@given(
    decision_offset_days=st.integers(-30, 30),
)
@settings(max_examples=50)
def test_property_pool_only_contains_strictly_prior_knowledge(decision_offset_days) -> None:
    """Propriete generale : quel que soit `decision_time`, chaque ligne du
    pool provient d'un enregistrement dont `sot_knowledge_time <=
    decision_time` - jamais une exception."""
    base = datetime(2024, 9, 1, tzinfo=timezone.utc)
    decision_time = base + timedelta(days=decision_offset_days)
    records = [
        _record(str(i), base + timedelta(days=i * 3), 1, 2, i, i)
        for i in range(-10, 11)
    ]
    pool = sot_training_pool(records, decision_time, exclude_match_id="999")
    expected_n = sum(1 for r in records if r.sot_knowledge_time <= decision_time)
    assert len(pool) == expected_n


# --------------------------------------------------------------------------
# GARDE-FOU ABSOLU (protocole Phase F, etape 9) : un test de fuite doit
# ECHOUER si une observation future est artificiellement injectee.
# --------------------------------------------------------------------------


def test_artificially_injected_future_observation_is_excluded_and_would_have_changed_the_result_if_not() -> None:
    decision_time = datetime(2024, 9, 1, tzinfo=timezone.utc)
    past = _record("1", datetime(2024, 8, 20, tzinfo=timezone.utc), 1, 2, home_sot=3, away_sot=2)
    # Injection artificielle d'une observation FUTURE avec une valeur
    # EXTREME (15) pour l'equipe 1 - si elle fuitait dans le pool, la
    # moyenne de l'equipe 1 changerait de facon detectable.
    injected_future = _record("2", datetime(2024, 9, 10, tzinfo=timezone.utc), 1, 3, home_sot=15, away_sot=15)

    real_pool = sot_training_pool([past, injected_future], decision_time, exclude_match_id="99")
    assert len(real_pool) == 1  # l'injection est exclue par le code REEL
    avg_for_real, _, _, _ = historical_sot_averages(real_pool)
    assert avg_for_real[1] == pytest.approx(3.0)

    # Preuve que l'exclusion n'est pas un no-op : si l'injection N'ETAIT
    # PAS filtree (pool construit manuellement, sans passer par
    # sot_training_pool), le resultat serait DIFFERENT.
    leaked_pool = pd.DataFrame(
        [
            {"home_team_id": 1, "away_team_id": 2, "home_sot": 3, "away_sot": 2},
            {"home_team_id": 1, "away_team_id": 3, "home_sot": 15, "away_sot": 15},
        ]
    )
    avg_for_leaked, _, _, _ = historical_sot_averages(leaked_pool)
    assert avg_for_leaked[1] == pytest.approx((3.0 + 15.0) / 2)
    assert avg_for_leaked[1] != avg_for_real[1]  # la fuite AURAIT ete detectable


def test_sot_features_for_match_never_uses_the_injected_future_observation() -> None:
    """Meme demonstration bout-en-bout via `sot_features_for_match` (la
    fonction reellement utilisee par le script d'experience) plutot que
    directement via `historical_sot_averages`."""
    decision_time = datetime(2024, 9, 1, tzinfo=timezone.utc)
    records = [_record(str(i), datetime(2024, 8, 1, tzinfo=timezone.utc) + timedelta(days=i), 1, 2, 3, 2) for i in range(12)]
    injected_future = _record("future", datetime(2024, 12, 25, tzinfo=timezone.utc), 1, 2, 99, 99)

    pool_without_leak = sot_training_pool(records, decision_time, exclude_match_id="999")
    pool_with_attempted_leak = sot_training_pool(records + [injected_future], decision_time, exclude_match_id="999")

    result_without = sot_features_for_match(pool_without_leak, 1, 2, min_train_matches=10)
    result_with = sot_features_for_match(pool_with_attempted_leak, 1, 2, min_train_matches=10)
    assert result_without == result_with  # l'injection future n'a produit AUCUN effet
