"""Regles temporelles communes a tout le systeme.

Principe central du projet : chaque fait porte un ``knowledge_time``
(quand l'information est devenue disponible) distinct de son
``event_time`` (quand la chose s'est produite). Toute comparaison
temporelle dans le pipeline doit passer par des datetimes timezone-aware
en UTC pour eviter les erreurs de fuseau horaire silencieuses.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone


def to_utc(value: datetime) -> datetime:
    """Normalise un datetime en UTC timezone-aware.

    Un datetime naif est explicitement rejete : dans un systeme qui
    raisonne sur "qu'est-ce qui etait connu a l'instant T", accepter un
    datetime sans fuseau serait une source silencieuse de look-ahead bias
    (ou de son inverse) selon la machine qui execute le code.
    """
    if value.tzinfo is None:
        raise ValueError(
            f"Datetime naif refuse ({value!r}) : toutes les timestamps du "
            "systeme doivent etre timezone-aware (UTC recommande)."
        )
    return value.astimezone(timezone.utc)


def assert_strictly_sorted(timestamps: Sequence[datetime]) -> None:
    """Verifie qu'une sequence de decision times est triee de facon non decroissante.

    Le backtester doit rejouer l'histoire dans l'ordre chronologique : une
    sequence non triee est un signe qu'un appelant construit ses points de
    decision de facon incorrecte, potentiellement en incluant des
    informations obtenues apres coup.
    """
    normalized = [to_utc(t) for t in timestamps]
    for previous, current in zip(normalized, normalized[1:]):
        if current < previous:
            raise ValueError(
                "Les decision times doivent etre tries par ordre "
                f"chronologique non decroissant : {current!r} suit {previous!r}."
            )
