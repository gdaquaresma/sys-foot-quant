"""Fusion differentielle idempotente du fichier "saison courante" (ex.
2026/27) - brique DATA INGESTION / VALIDATION / MERGE uniquement, jamais
un connecteur reseau (voir ``docs/current_season_data_contract.md`` et
l'etude d'architecture d'auto-alimentation).

Principe non negociable, identique au reste du projet : **refuser plutot
que corriger silencieusement**. Une source fraiche ne peut JAMAIS :
- faire disparaitre silencieusement un match deja present localement ;
- modifier silencieusement le contenu d'un match deja ingere (« dernier
  fichier telecharge gagne » est explicitement INTERDIT).

Dans les deux cas, la mise a jour est refusee EN BLOC et le fichier local
existant reste STRICTEMENT inchange (principe "last known good") -
jamais une fusion partielle.

Reutilise SANS MODIFICATION ``current_season_contract.validate_current_season_understat_raw``
(le contrat de schema/valeurs reste unique, jamais duplique ici). N'importe
et n'est jamais importe par ``final_engine/``, ``PoissonModel``/
``DixonColesModel``/``XGModel``, ``multi_season_dataset`` (ce module
produit le fichier QUE ``multi_season_dataset`` consomme ensuite, jamais
l'inverse)."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from sys_foot_quant.data_engine.market_odds.current_season_contract import (
    CurrentSeasonContractError,
    validate_current_season_understat_raw,
)

# Champs dont le contenu est compare pour decider si un match deja present
# est "strictement identique" ou "modifie" - exactement les champs du
# contrat minimal (docs/current_season_data_contract.md), jamais un champ
# accessoire (ex. un futur "forecast" non garanti par le contrat).
_COMPARED_FIELDS = ("id", "isResult", "datetime", "h", "a", "goals", "xG")


class CurrentSeasonSourceInconsistencyError(ValueError):
    """Levee quand la nouvelle source contredit l'etat local deja valide
    (match modifie ou disparu) - jamais resolue automatiquement, jamais
    un ecrasement silencieux. Le fichier local reste inchange."""


@dataclass(frozen=True)
class MergeDiff:
    """Resultat explicite de la comparaison local vs source fraiche - un
    match appartient a EXACTEMENT une categorie. Les tuples contiennent
    les dictionnaires bruts (schema Understat), jamais un objet
    intermediaire supplementaire."""

    new_matches: tuple[dict, ...]
    unchanged_matches: tuple[dict, ...]
    modified_matches: tuple[tuple[dict, dict], ...]  # (version locale, version source)
    missing_from_source: tuple[dict, ...]

    @property
    def has_inconsistency(self) -> bool:
        """Vrai si la source contredit l'etat local (modification ou
        disparition) - jamais vrai pour un simple ajout de nouveaux
        matchs, qui est le cas nominal attendu a chaque mise a jour."""
        return bool(self.modified_matches or self.missing_from_source)


def _canonical_signature(raw: dict) -> tuple:
    """Signature normalisee du CONTENU pertinent d'un match - deux
    representations du meme match (ex. ``"2"`` vs ``2`` pour un but)
    doivent produire la MEME signature, pour ne jamais signaler une
    "modification" a partir d'une simple difference de formatage entre
    deux telechargements. Toute vraie difference de valeur (score, xG,
    equipe, date, isResult) produit en revanche une signature differente."""
    return (
        str(raw["id"]),
        bool(raw["isResult"]),
        str(raw["datetime"]),
        str(raw["h"]["id"]),
        str(raw["h"]["title"]),
        str(raw["a"]["id"]),
        str(raw["a"]["title"]),
        int(raw["goals"]["h"]),
        int(raw["goals"]["a"]),
        float(raw["xG"]["h"]),
        float(raw["xG"]["a"]),
    )


def compute_diff(local_matches: list[dict], source_matches: list[dict]) -> MergeDiff:
    """Compare ``local_matches`` (etat actuel du fichier saison courante,
    peut etre vide - premiere execution) a ``source_matches`` (nouvelle
    source deja validee par l'appelant). Fonction PURE, aucune I/O,
    aucune ecriture - uniquement le calcul du diff, pour permettre un mode
    diagnostic qui n'ecrit jamais rien (voir ``update_current_season_file``,
    parametre ``dry_run``)."""
    local_by_id = {str(m["id"]): m for m in local_matches}
    source_by_id = {str(m["id"]): m for m in source_matches}

    new_matches: list[dict] = []
    unchanged_matches: list[dict] = []
    modified_matches: list[tuple[dict, dict]] = []
    for match_id, source_match in source_by_id.items():
        local_match = local_by_id.get(match_id)
        if local_match is None:
            new_matches.append(source_match)
        elif _canonical_signature(local_match) == _canonical_signature(source_match):
            unchanged_matches.append(source_match)
        else:
            modified_matches.append((local_match, source_match))

    missing_from_source = [
        local_match for match_id, local_match in local_by_id.items() if match_id not in source_by_id
    ]

    return MergeDiff(
        new_matches=tuple(new_matches),
        unchanged_matches=tuple(unchanged_matches),
        modified_matches=tuple(modified_matches),
        missing_from_source=tuple(missing_from_source),
    )


def merge_current_season(local_matches: list[dict], source_matches: list[dict]) -> tuple[list[dict], MergeDiff]:
    """Calcule le dataset fusionne et le diff correspondant - fonction
    PURE, aucune I/O. Ordre de validation strict :

    1. valider la source fraiche (toujours) ;
    2. valider l'etat local s'il n'est pas vide (un ``local_matches``
       vide signifie "aucun fichier local pour l'instant", un cas
       legitime de premiere execution - jamais confondu avec "fichier
       local vide", explicitement refuse par le contrat) ;
    3. calculer le diff ;
    4. refuser EN BLOC (``CurrentSeasonSourceInconsistencyError``) si un
       match est modifie ou a disparu - jamais une fusion partielle ;
    5. construire le dataset fusionne (local inchange + nouveaux matchs
       uniquement), trie chronologiquement par ``datetime`` (format
       ``"YYYY-MM-DD HH:MM:SS"``, tri lexicographique = tri
       chronologique) ;
    6. revalider le dataset final avant de le retourner - jamais un
       resultat non revalide remis a l'appelant."""
    validate_current_season_understat_raw(source_matches)
    if local_matches:
        validate_current_season_understat_raw(local_matches)

    diff = compute_diff(local_matches, source_matches)

    if diff.modified_matches:
        ids = [str(local_match["id"]) for local_match, _source_match in diff.modified_matches]
        raise CurrentSeasonSourceInconsistencyError(
            f"{len(diff.modified_matches)} match(s) deja ingere(s) ont un contenu different dans la "
            f"nouvelle source (match_id : {ids}) - refus explicite de la mise a jour, le fichier local "
            "reste inchange. Une correction retroactive d'un match deja valide (score/xG corrige, VAR) "
            "doit etre traitee manuellement, jamais acceptee silencieusement ('dernier fichier "
            "telecharge gagne' est interdit)."
        )
    if diff.missing_from_source:
        ids = [str(m["id"]) for m in diff.missing_from_source]
        raise CurrentSeasonSourceInconsistencyError(
            f"{len(diff.missing_from_source)} match(s) present(s) localement ont disparu de la nouvelle "
            f"source (match_id : {ids}) - refus explicite de la mise a jour, le fichier local reste "
            "inchange."
        )

    merged = [*local_matches, *diff.new_matches]
    merged_sorted = sorted(merged, key=lambda m: str(m["datetime"]))
    validate_current_season_understat_raw(merged_sorted)
    return merged_sorted, diff


def write_current_season_atomic(path: Path, matches: list[dict]) -> None:
    """Ecriture atomique : fichier temporaire dans le MEME repertoire que
    ``path`` (garantit que ``os.replace`` reste une operation atomique du
    systeme de fichiers, jamais un renommage inter-volumes), flush +
    fsync avant ``os.replace``. N'ouvre JAMAIS ``path`` directement en
    ecriture, ne le supprime jamais avant d'avoir un remplacant complet et
    valide - une interruption a tout moment laisse soit l'ancien fichier
    intact, soit le nouveau deja complet, jamais un etat intermediaire."""
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=directory, prefix=f".{path.name}.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(matches, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def update_current_season_file(path: Path, source_matches: list[dict], *, dry_run: bool = False) -> MergeDiff:
    """Orchestration complete UPDATE -> VALIDATE -> DIFF -> MERGE ->
    ATOMIC STORE pour le fichier ``path`` (cree s'il n'existe pas encore -
    premiere execution legitime).

    ``dry_run=True`` : calcule et retourne le diff (leve la meme
    exception en cas d'incoherence) SANS jamais ecrire quoi que ce soit -
    mode diagnostic explicite demande par l'etude d'architecture.

    Comportement "last known good" : si ``source_matches`` est invalide,
    incoherent avec l'etat local (modification/disparition), ou si le
    fichier local existant est corrompu (JSON invalide), une exception
    est levee et ``path`` n'est JAMAIS modifie - verifie par les tests
    dedies (aucune ecriture avant l'etape finale de ce chemin de code)."""
    local_matches: list[dict] = []
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                local_matches = json.load(f)
        except json.JSONDecodeError as exc:
            raise CurrentSeasonContractError(
                f"Fichier local {path} corrompu (JSON invalide) : {exc} - fichier local laisse inchange."
            ) from exc

    merged, diff = merge_current_season(local_matches, source_matches)

    if not dry_run:
        write_current_season_atomic(path, merged)

    return diff
