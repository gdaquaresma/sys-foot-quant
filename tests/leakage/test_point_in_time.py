"""Suite anti-look-ahead : preuve que le futur est structurellement inaccessible.

Deux niveaux de preuve :

1. Un test base sur les donnees "naturelles" du generateur (les
   resultats sont, par construction, connus apres le coup d'envoi) : on
   verifie qu'interroger juste avant qu'un resultat existe ne le renvoie
   jamais.
2. Un test "poison pill" (Hypothesis) : on injecte une ligne dont le
   ``knowledge_time`` est tres loin dans le futur (annee 2999) et on
   verifie, pour un grand nombre d'instants ``as_of`` tires aleatoirement
   dans la periode reelle du dataset, qu'elle n'apparait JAMAIS. C'est la
   preuve la plus forte : elle ne depend pas de la structure "normale"
   des donnees, seulement du filtre point-in-time lui-meme.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from sys_foot_quant.data_engine.storage.repository import DuckDBRepository
from sys_foot_quant.data_engine.storage.writer import write_dataset
from sys_foot_quant.data_engine.synthetic.generator import SyntheticDataset

POISON_MATCH_ID = 999_999
POISON_KNOWLEDGE_TIME = datetime(2999, 1, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# 1. Invariant general, sur donnees naturelles : knowledge_time <= as_of
# ---------------------------------------------------------------------------

_PIT_ENTITIES = ("matches", "match_results", "odds_snapshots")


#  SMALL_SYNTHETIC_CONFIG.start_date (voir conftest.py) est le 2024-08-01.
#  Fenetre couvrant largement la periode reelle du dataset genere par la
#  fixture `repo` (annonce des fixtures ~14j avant le premier match,
#  derniere confirmation de resultat quelques jours plus tard), avec de
#  la marge avant/apres pour aussi exercer les cas hors-plage.
_STAGE1_DATASET_REFERENCE = datetime(2024, 8, 1, tzinfo=timezone.utc)


@given(offset_minutes=st.integers(min_value=-20 * 24 * 60, max_value=60 * 24 * 60))
@settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_invariant_knowledge_time_never_exceeds_as_of(
    repo: DuckDBRepository, offset_minutes: int
) -> None:
    """Propriete fondamentale, testee sur des centaines d'instants aleatoires.

    Pour n'importe quel ``as_of`` genere par Hypothesis, chaque ligne
    retournee par ``get_as_of`` doit verifier knowledge_time <= as_of.

    Le fixture `repo` est en lecture seule (interroge un dataset deja
    ecrit sur disque) : le reutiliser sans le regenerer entre chaque
    exemple Hypothesis est intentionnel et sans effet de bord, d'ou la
    suppression explicite du health check correspondant.
    """
    as_of = _STAGE1_DATASET_REFERENCE + timedelta(minutes=offset_minutes)

    for entity in _PIT_ENTITIES:
        visible = repo.get_as_of(entity, as_of)
        if visible.empty:
            continue
        assert (visible["knowledge_time"] <= pd.Timestamp(as_of)).all(), (
            f"Fuite detectee sur '{entity}' a as_of={as_of} : au moins une ligne "
            "a un knowledge_time posterieur a l'instant de decision."
        )


def test_result_absent_until_the_instant_it_becomes_known(
    repo: DuckDBRepository,
) -> None:
    full_results = repo.debug_get_full_table("match_results")
    earliest_known_result = full_results.sort_values("knowledge_time").iloc[0]
    t_known = earliest_known_result["knowledge_time"]
    match_id = int(earliest_known_result["match_id"])

    just_before = t_known - timedelta(seconds=1)
    visible_before = repo.get_as_of("match_results", just_before)
    assert match_id not in set(visible_before["match_id"]), (
        "Un resultat est visible AVANT l'instant ou le systeme est cense "
        "en avoir connaissance : violation de la garantie point-in-time."
    )


# ---------------------------------------------------------------------------
# 2. Poison pill : une ligne au knowledge_time extreme, jamais visible
#    dans la fenetre temporelle reelle du dataset.
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class _PoisonedRepo:
    repository: DuckDBRepository
    dataset_start: datetime
    dataset_end: datetime


def _build_poisoned_repository(tmp_path: Path, synthetic_dataset: SyntheticDataset) -> _PoisonedRepo:
    poison_row = pd.DataFrame(
        [
            {
                "match_id": POISON_MATCH_ID,
                "home_goals": 9,
                "away_goals": 9,
                "knowledge_time": POISON_KNOWLEDGE_TIME,
            }
        ]
    )
    poisoned_results = pd.concat(
        [synthetic_dataset.match_results, poison_row], ignore_index=True
    )
    poisoned_dataset = dataclasses.replace(synthetic_dataset, match_results=poisoned_results)
    write_dataset(poisoned_dataset, tmp_path)

    dataset_start = synthetic_dataset.matches["knowledge_time"].min()
    dataset_end = synthetic_dataset.match_results["knowledge_time"].max()
    return _PoisonedRepo(
        repository=DuckDBRepository(tmp_path),
        dataset_start=pd.Timestamp(dataset_start).to_pydatetime(),
        dataset_end=pd.Timestamp(dataset_end).to_pydatetime(),
    )


def test_poison_row_absent_at_the_exact_instant_before_its_knowledge_time(
    tmp_path: Path, synthetic_dataset: SyntheticDataset
) -> None:
    poisoned = _build_poisoned_repository(tmp_path, synthetic_dataset)
    try:
        just_before_poison = POISON_KNOWLEDGE_TIME - timedelta(seconds=1)
        visible = poisoned.repository.get_as_of("match_results", just_before_poison)
        assert POISON_MATCH_ID not in set(visible["match_id"])

        visible_at_poison_time = poisoned.repository.get_as_of(
            "match_results", POISON_KNOWLEDGE_TIME
        )
        assert POISON_MATCH_ID in set(visible_at_poison_time["match_id"])
    finally:
        poisoned.repository.close()


def test_poison_row_never_visible_within_the_dataset_real_time_span(
    tmp_path: Path, synthetic_dataset: SyntheticDataset
) -> None:
    """Le test le plus fort de la suite.

    Pour des centaines d'instants ``as_of`` tires aleatoirement dans la
    periode reelle du dataset (annees 2020-2030, tres largement avant
    l'annee 2999 de la ligne empoisonnee), on verifie systematiquement
    que la ligne empoisonnee n'apparait jamais. Contrairement au test
    precedent (qui verifie une seule frontiere), celui-ci echantillonne
    l'ensemble de l'espace des instants plausibles.
    """
    poisoned = _build_poisoned_repository(tmp_path, synthetic_dataset)
    try:

        @given(
            year=st.integers(min_value=2020, max_value=2030),
            day_offset=st.integers(min_value=0, max_value=364),
        )
        @settings(max_examples=150)
        def _check(year: int, day_offset: int) -> None:
            as_of = datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(days=day_offset)
            visible = poisoned.repository.get_as_of("match_results", as_of)
            assert POISON_MATCH_ID not in set(visible["match_id"]), (
                f"La ligne empoisonnee (knowledge_time={POISON_KNOWLEDGE_TIME}) "
                f"est visible a as_of={as_of}, largement avant sa knowledge_time : "
                "fuite critique."
            )

        _check()
    finally:
        poisoned.repository.close()
