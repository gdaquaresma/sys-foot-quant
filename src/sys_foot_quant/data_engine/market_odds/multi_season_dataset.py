"""Concatenation chronologique de plusieurs saisons Understat en une seule
liste de ``RealMatchRecord``, pour permettre a R1/R2
(``calibration_dataset.py``/``future_match_dataset.py`` - INCHANGES,
aucune nouvelle logique de filtrage point-in-time ici) de considerer un
historique long terme (ex. 2024/25 + 2025/26) ETENDU par les matchs deja
joues d'une saison courante (ex. 2026/27) - jamais une saison courante
traitee comme "complete" ou "deja entierement connue" : c'est a
l'appelant de ne fournir, pour la saison courante, QUE les matchs
reellement disputes a la date de collecte (voir
``docs/current_season_data_contract.md``, et
``current_season_contract.validate_current_season_understat_raw`` pour
une verification explicite avant tout chargement).

Aucune ponderation temporelle introduite ici (``football_model/weighting.py``
et ``football_model/recent_form.py`` INCHANGES, non importes) : une fois
passes a ``PoissonModel``/``DixonColesModel``/``XGModel`` (via
``future_match_dataset``/``calibration_dataset``, INCHANGES), les matchs
de la saison courante recoivent exactement le meme poids que n'importe
quel match plus ancien (poids plat, ``football_model/weighting.flat_weights``,
meme mecanisme que E7/E8/``final_engine``). Ce module ne fait QUE
rassembler et trier des enregistrements deja produits par
``build_real_match_records`` (INCHANGE) - il ne modifie, n'estime ni ne
pondere rien lui-meme."""

from __future__ import annotations

from sys_foot_quant.backtesting_engine.real_data_walk_forward import (
    RealMatchRecord,
    build_real_match_records,
)


class DuplicateMatchIdError(ValueError):
    """Leve si deux sources (ex. deux fichiers de saison) partagent le meme
    ``match_id`` - jamais une deduplication silencieuse, qui masquerait
    une erreur de fichier (ex. le meme fichier fourni deux fois, ou un
    chevauchement reel entre deux sources)."""


def build_real_match_records_multi_season(
    sources: list[tuple[list[dict], str]],
) -> list[RealMatchRecord]:
    """Construit une liste UNIQUE de ``RealMatchRecord`` a partir de
    plusieurs sources brutes Understat (une paire ``(raw_matches,
    league_id)`` par fichier de saison, dans n'importe quel ordre), triee
    chronologiquement par ``kickoff_utc`` - jamais un regroupement par
    saison. Reutilise ``build_real_match_records`` (INCHANGE) source par
    source ; le filtrage point-in-time reste entierement delegue en aval
    a ``future_match_dataset.build_match_train_dataframes``/
    ``calibration_dataset.build_calibration_dataframe`` (INCHANGES), qui
    n'ont besoin d'aucun tri prealable de toute facon (ils trient
    eux-memes) - le tri est fait ici uniquement pour que la liste
    retournee soit directement inspectable/reproductible.

    Refuse explicitement toute collision de ``match_id`` entre deux
    sources (ex. le meme fichier de saison fourni deux fois par erreur)
    plutot que de la laisser produire silencieusement un historique
    duplique, qui fausserait tout calcul en aval (poids effectif double
    pour les matchs concernes)."""
    records: list[RealMatchRecord] = []
    seen_match_ids: set[str] = set()
    for raw_matches, league in sources:
        for record in build_real_match_records(raw_matches, league=league):
            if record.match_id in seen_match_ids:
                raise DuplicateMatchIdError(
                    f"match_id {record.match_id!r} present dans plusieurs sources passees a "
                    "build_real_match_records_multi_season - verifiez qu'aucun fichier de saison "
                    "n'a ete fourni deux fois et qu'aucun match n'apparait reellement dans deux "
                    "fichiers distincts."
                )
            seen_match_ids.add(record.match_id)
            records.append(record)
    records.sort(key=lambda r: r.kickoff_utc)
    return records
