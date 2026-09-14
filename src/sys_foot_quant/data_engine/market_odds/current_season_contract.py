"""Validation explicite du contrat minimal d'un fichier "saison courante"
(ex. 2026/27) avant tout usage par
``multi_season_dataset.build_real_match_records_multi_season`` -
``docs/current_season_data_contract.md`` pour la definition complete et
le raisonnement.

Ce module refuse tot, avec un message precis identifiant le match en
cause, plutot que de laisser ``build_real_match_records`` echouer
profondement avec un ``KeyError`` peu lisible. Il ajoute UNE regle
propre a la notion de "saison courante", absente du schema Understat brut
lui-meme et absente de ``build_real_match_records`` (qui, lui, ignore
silencieusement les matchs non joues - comportement correct pour un
fichier de saison COMPLETE et close, mais dangereux pour un fichier
cense ne contenir QUE des matchs deja joues) : aucun match a venir
(``isResult=False``) ne doit figurer dans ce fichier. Aucune donnee n'est
corrigee, completee ou devinee ici - uniquement un refus explicite.

Validations numeriques ajoutees pour l'auto-alimentation (etape merge) :
``goals.h``/``goals.a`` doivent etre des entiers >= 0, ``xG.h``/``xG.a``
des nombres finis >= 0, et l'equipe domicile doit differer de l'equipe
exterieure - chacune est une propriete objective d'un score/xG/match
reel, jamais une regle metier arbitraire."""

from __future__ import annotations

_REQUIRED_TOP_LEVEL_KEYS = ("id", "isResult", "h", "a", "datetime")


class CurrentSeasonContractError(ValueError):
    """Fichier saison courante non conforme au contrat minimal - jamais
    une correction silencieuse ni une valeur de repli."""


def _parse_non_negative_int(value: object, field_name: str, index: int, match_id: object) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise CurrentSeasonContractError(
            f"Match d'index {index} (id={match_id!r}) : '{field_name}' n'est pas un entier valide ({value!r})."
        ) from None
    if parsed < 0:
        raise CurrentSeasonContractError(
            f"Match d'index {index} (id={match_id!r}) : '{field_name}' doit etre >= 0 (recu {parsed})."
        )
    return parsed


def _parse_non_negative_float(value: object, field_name: str, index: int, match_id: object) -> float:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise CurrentSeasonContractError(
            f"Match d'index {index} (id={match_id!r}) : '{field_name}' n'est pas un nombre valide ({value!r})."
        ) from None
    if parsed != parsed or parsed in (float("inf"), float("-inf")):
        raise CurrentSeasonContractError(
            f"Match d'index {index} (id={match_id!r}) : '{field_name}' doit etre fini (recu {value!r})."
        )
    if parsed < 0:
        raise CurrentSeasonContractError(
            f"Match d'index {index} (id={match_id!r}) : '{field_name}' doit etre >= 0 (recu {parsed})."
        )
    return parsed


def validate_current_season_understat_raw(raw_matches: list[dict]) -> None:
    """Verifie que chaque entree du fichier "saison courante" respecte le
    schema minimal attendu par ``build_real_match_records`` (INCHANGE) et
    la regle supplementaire propre a une saison EN COURS : ``isResult``
    doit etre ``True`` pour toutes les entrees (le fichier ne doit
    contenir que des matchs reellement joues et connus a la date de
    collecte, jamais un calendrier incluant les matchs a venir).

    Leve ``CurrentSeasonContractError`` des la premiere anomalie trouvee,
    avec l'index et l'``id`` du match en cause - ne retourne jamais un
    diagnostic partiel silencieux."""
    if not isinstance(raw_matches, list):
        raise CurrentSeasonContractError(
            f"Le fichier saison courante doit contenir une liste de matchs (recu : {type(raw_matches).__name__})."
        )
    if not raw_matches:
        raise CurrentSeasonContractError(
            "Le fichier saison courante est vide - une saison courante sans aucun match joue "
            "ne doit pas etre fournie au chargement multi-saisons (utilisez uniquement "
            "l'historique long terme tant qu'aucun match 2026/27 n'est joue)."
        )

    match_ids: set[str] = set()
    for i, raw in enumerate(raw_matches):
        missing = [k for k in _REQUIRED_TOP_LEVEL_KEYS if k not in raw]
        if missing:
            raise CurrentSeasonContractError(
                f"Match d'index {i} : champ(s) obligatoire(s) manquant(s) {missing} "
                "(contrat minimal, voir docs/current_season_data_contract.md)."
            )
        if raw["isResult"] is not True:
            raise CurrentSeasonContractError(
                f"Match d'index {i} (id={raw.get('id')!r}) : isResult doit etre True - le fichier "
                "saison courante ne doit contenir QUE des matchs deja joues, jamais un match a "
                "venir (docs/current_season_data_contract.md section 2)."
            )
        goals = raw.get("goals")
        if not isinstance(goals, dict) or "h" not in goals or "a" not in goals:
            raise CurrentSeasonContractError(
                f"Match d'index {i} (id={raw.get('id')!r}) : 'goals.h'/'goals.a' manquant(s) ou invalide(s)."
            )
        xg = raw.get("xG")
        if not isinstance(xg, dict) or "h" not in xg or "a" not in xg:
            raise CurrentSeasonContractError(
                f"Match d'index {i} (id={raw.get('id')!r}) : 'xG.h'/'xG.a' manquant(s) ou invalide(s) - "
                "le xG est un champ obligatoire de RealMatchRecord, jamais une valeur de repli inventee."
            )
        for side in ("h", "a"):
            side_payload = raw.get(side)
            if not isinstance(side_payload, dict) or "id" not in side_payload or "title" not in side_payload:
                raise CurrentSeasonContractError(
                    f"Match d'index {i} (id={raw.get('id')!r}) : '{side}.id'/'{side}.title' manquant(s) ou invalide(s)."
                )
        if str(raw["h"]["id"]) == str(raw["a"]["id"]):
            raise CurrentSeasonContractError(
                f"Match d'index {i} (id={raw.get('id')!r}) : equipe domicile et exterieure identiques "
                f"({raw['h']['id']!r}) - impossible pour un match reel."
            )
        _parse_non_negative_int(goals["h"], "goals.h", i, raw.get("id"))
        _parse_non_negative_int(goals["a"], "goals.a", i, raw.get("id"))
        _parse_non_negative_float(xg["h"], "xG.h", i, raw.get("id"))
        _parse_non_negative_float(xg["a"], "xG.a", i, raw.get("id"))
        match_id = str(raw["id"])
        if match_id in match_ids:
            raise CurrentSeasonContractError(
                f"match_id {match_id!r} duplique dans le fichier saison courante lui-meme (index {i})."
            )
        match_ids.add(match_id)
