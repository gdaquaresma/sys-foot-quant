"""Construction de ``(goals_train_df, xg_train_df)`` pour un match CIBLE
(passe ou futur), directement utilisables par
``final_engine.orchestrator.run_match_decision(goals_train_df=...,
xg_train_df=...)`` (docs/final_engine_specification.md sections 3, 16 :
"``goals_train_df``/``xg_train_df`` doivent DEJA etre filtres point-in-time
par l'appelant, jamais refiltres" par le moteur lui-meme).

AUCUNE nouvelle logique de filtrage point-in-time : reutilise
integralement, sans modification,
``backtesting_engine.real_data_walk_forward._goals_train_df``/
``._xg_train_df`` (deja la brique testee en leakage,
``tests/leakage/test_real_data_walk_forward_point_in_time.py``, deja
reutilisee sans modification par E7/E8/``calibration_engine.
calibration_dataset`` - R1). Le seul ajout ici est un point d'entree adapte
a un match dont le RESULTAT n'existe pas encore dans l'historique (un
match futur), par opposition au walk-forward retrospectif d'E7/E8/
``economic_dataset`` qui evalue un match DEJA present dans ``records`` et
doit alors l'exclure explicitement de son propre entrainement.

Pour resoudre le nom d'une equipe (source externe, convention
Football-Data - calendrier ou cotes a venir) vers son ``team_id``
Understat dans un corpus historique donne, reutilise
``data_engine.market_odds.team_mapping.resolve_understat_name`` (INCHANGE)
et les cles deja extraites par
``data_engine.market_odds.matching.build_understat_keys``/
``UnderstatMatchKey`` (INCHANGES) - jamais une nouvelle table de
correspondance de noms.

``data_engine.market_odds.time_resolution`` reste utilise EN AVAL, sans
duplication ici : la regle de fenetre de collecte de cote
(``conservative_knowledge_time_utc``/``AmbiguousCollectionWindowError``)
est deja appliquee par ``final_engine.gates.ambiguous_day_gate`` au moment
de la decision - elle concerne la disponibilite d'une COTE de marche,
jamais la construction de l'historique de buts/xG produite ici (qui n'en
depend pas)."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from sys_foot_quant.backtesting_engine.real_data_walk_forward import (
    RealMatchRecord,
    _goals_train_df,
    _xg_train_df,
)
from sys_foot_quant.data_engine.market_odds.matching import UnderstatMatchKey
from sys_foot_quant.data_engine.market_odds.team_mapping import resolve_understat_name

# Sentinel garanti de ne jamais collisionner avec un match_id Understat reel
# (toujours ``str(int)``, voir ``matching.build_understat_keys``/
# ``real_data_walk_forward.build_real_match_records``) : un match CIBLE
# reellement futur n'a par construction aucune raison de s'auto-exclure de
# son propre historique, puisqu'il n'y figure pas encore.
NO_MATCH_TO_EXCLUDE = "__no_match_to_exclude__"


def build_match_train_dataframes(
    records: list[RealMatchRecord],
    home_team_id: int,
    away_team_id: int,
    decision_time: datetime,
    exclude_match_id: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Construit ``(goals_train_df, xg_train_df)`` pour un match identifie
    par ses deux ``team_id`` et son ``decision_time`` - entrees minimales,
    l'appelant n'a JAMAIS a pre-filtrer ``records`` lui-meme (delegue
    integralement a ``_goals_train_df``/``_xg_train_df``, INCHANGEES ;
    ``records`` n'a besoin d'aucun tri prealable, comme ces fonctions).

    ``home_team_id``/``away_team_id`` ne filtrent PAS l'historique
    retourne (les trois modeles s'entrainent sur l'historique COMPLET
    disponible de la ligue - meme methodologie que E7/E8/B1/B3, jamais un
    historique tete-a-tete) : ils documentent l'intention de l'appel et
    permettent a l'appelant/aux gates en aval
    (``final_engine.gates.unknown_team_gate``) de verifier que ces deux
    equipes precises y apparaissent deja.

    ``exclude_match_id`` ne sert QUE pour re-evaluer retrospectivement un
    match DEJA present dans ``records`` (walk-forward historique, comme
    E7/E8) sans qu'il ne s'entraine sur lui-meme - laisser ``None``
    (valeur par defaut, resolue vers ``NO_MATCH_TO_EXCLUDE``, un sentinel
    qui ne peut jamais correspondre a un ``match_id`` reel) pour un match
    reellement futur, absent de ``records`` par construction."""
    exclude = exclude_match_id if exclude_match_id is not None else NO_MATCH_TO_EXCLUDE
    goals_train_df = _goals_train_df(records, decision_time, exclude_match_id=exclude)
    xg_train_df = _xg_train_df(records, decision_time, exclude_match_id=exclude)
    return goals_train_df, xg_train_df


def build_understat_team_id_by_name(understat_keys: list[UnderstatMatchKey]) -> dict[str, int]:
    """Table nom Understat -> ``team_id``, construite a partir des cles
    DEJA extraites par ``matching.build_understat_keys`` (INCHANGE) -
    jamais une nouvelle extraction du schema brut Understat. Leve
    explicitement en cas d'incoherence (meme nom associe a deux ``team_id``
    differents, ou l'inverse) - jamais une resolution approximative
    silencieuse (meme discipline que ``team_mapping.resolve_understat_name``)."""
    name_to_id: dict[str, int] = {}
    id_to_name: dict[int, str] = {}
    for k in understat_keys:
        for name, team_id in ((k.home_team_name, k.home_team_id), (k.away_team_name, k.away_team_id)):
            if name in name_to_id and name_to_id[name] != team_id:
                raise ValueError(
                    f"Nom Understat ambigu : {name!r} associe a la fois a "
                    f"team_id={name_to_id[name]} et team_id={team_id}."
                )
            if team_id in id_to_name and id_to_name[team_id] != name:
                raise ValueError(
                    f"team_id Understat ambigu : {team_id} associe a la fois a "
                    f"{id_to_name[team_id]!r} et {name!r}."
                )
            name_to_id[name] = team_id
            id_to_name[team_id] = name
    return name_to_id


def resolve_match_team_ids(
    understat_keys: list[UnderstatMatchKey],
    league: str,
    home_team_name_football_data: str,
    away_team_name_football_data: str,
) -> tuple[int, int]:
    """Resout les ``team_id`` Understat d'un match CIBLE a partir de noms
    d'equipe en convention Football-Data (celle d'une source de cotes/
    calendrier externe pour un match a venir) - reutilise integralement
    ``team_mapping.resolve_understat_name`` (INCHANGE) pour la traduction
    de nom, puis ``build_understat_team_id_by_name`` (ci-dessus) pour la
    resolution finale vers un ``team_id`` du corpus historique fourni.
    Leve explicitement (jamais silencieusement) si l'une des deux equipes
    est absente de ``understat_keys``."""
    home_name_understat = resolve_understat_name(league, home_team_name_football_data)
    away_name_understat = resolve_understat_name(league, away_team_name_football_data)
    team_id_by_name = build_understat_team_id_by_name(understat_keys)

    try:
        home_team_id = team_id_by_name[home_name_understat]
    except KeyError:
        raise KeyError(
            f"Equipe domicile {home_name_understat!r} (resolue depuis "
            f"{home_team_name_football_data!r}) absente du corpus historique fourni."
        ) from None
    try:
        away_team_id = team_id_by_name[away_name_understat]
    except KeyError:
        raise KeyError(
            f"Equipe exterieur {away_name_understat!r} (resolue depuis "
            f"{away_team_name_football_data!r}) absente du corpus historique fourni."
        ) from None
    return home_team_id, away_team_id
