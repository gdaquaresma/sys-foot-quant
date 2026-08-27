"""Resolution du decalage horaire Football-Data <-> Understat (etape 2,
phase economique) et regle point-in-time conservatrice pour les cotes
Football-Data, qui ne portent AUCUN horodatage individuel a la source
(voir docs/decisions/0006-football-data-point-in-time.md).

CONSTAT EMPIRIQUE (etabli a partir des donnees deja disponibles dans ce
depot, PAS suppose a priori - voir le detail du calcul dans l'echange de
validation) : en comparant les heures de coup d'envoi des matchs deja
apparies par nom entre Football-Data et Understat sur les six fichiers
reels, le decalage observe (0 ou +60 minutes selon la periode de l'annee)
correspond exactement aux transitions heure d'ete/hiver europeennes (fin
mars / fin octobre), et ce de facon UNIFORME sur les trois championnats
(Premier League, Ligue 1, Liga) - pas seulement au Royaume-Uni, ce qui
exclut l'hypothese "chaque championnat en heure locale de son pays hote".
Taux d'accord observes : ~94-99% de diff=0 en periode hiver (GMT=UTC+0),
~87-97% de diff=+60min en periode ete (BST=UTC+1), coherent sur les trois
championnats. Conclusion retenue : la colonne `Time` de Football-Data est
publiee en HEURE CIVILE DU ROYAUME-UNI (Europe/London, GMT/BST) pour les
trois championnats quel que soit le pays hote, tandis qu'Understat
(`datetime`) est en UTC constant - deja le choix fait sans verification
independante dans `research/xg_feasibility/understat_source.py`
(`tzinfo=timezone.utc`), desormais corrobore empiriquement par ce
recoupement, pas seulement suppose par le nom du champ.

Les quelques pourcents de residu (dates de transition, matchs
reprogrammes par la TV) ne sont PAS resolus silencieusement ici.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

_LONDON = ZoneInfo("Europe/London")

TIMESTAMP_STATUS_VERIFIED = "verified"
TIMESTAMP_STATUS_HYPOTHETICAL = "hypothetical_documented"


class AmbiguousCollectionWindowError(ValueError):
    """Levee quand le jour de la semaine du match ne permet pas d'appliquer
    sans ambiguite la regle conservatrice documentee par la source
    (« week-end -> vendredi apres-midi », « semaine -> mardi apres-midi »)
    - les matchs du LUNDI et du VENDREDI (la source ne precise pas
    explicitement dans quelle fenetre ils tombent), ET les matchs du MARDI
    lui-meme (la collecte "du mardi apres-midi" ne peut pas etre garantie
    anterieure a un match qui a lieu CE MEME mardi, quelle que soit son
    heure de coup d'envoi - seule une reference a un jour calendaire
    STRICTEMENT anterieur au match garantit l'absence de fuite temporelle,
    quelle que soit l'heure de coup d'envoi). Volontairement PAS resolue
    par une hypothese supplementaire non documentee (voir echange de
    validation, etape D)."""


def football_data_kickoff_to_utc(date_str: str, time_str: str) -> datetime:
    """Convertit Date ('dd/mm/YYYY') + Time ('HH:MM') Football-Data,
    interpretes comme heure civile du Royaume-Uni (Europe/London - gere
    automatiquement la transition GMT/BST), en UTC timezone-aware,
    directement comparable a ``kickoff_utc`` d'Understat."""
    naive = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
    localized = naive.replace(tzinfo=_LONDON)
    return localized.astimezone(timezone.utc)


def conservative_knowledge_time_utc(kickoff_utc: datetime) -> datetime:
    """Heure de connaissance CONSERVATRICE et DOCUMENTEE (jamais un
    timestamp verifie - voir TIMESTAMP_STATUS_HYPOTHETICAL) de la cote
    Football-Data pour un match donne :

    - samedi/dimanche -> connue au plus tard le vendredi precedent,
      23:59:59 heure de Londres ;
    - mercredi/jeudi -> connue au plus tard le mardi precedent,
      23:59:59 heure de Londres.

    23:59:59 est un choix technique DELIBEREMENT conservateur pour fixer
    une borne comparable a un `decision_time`, PAS une pretention de
    connaitre l'heure exacte de collecte - la source ne documente qu'un
    jour ("apres-midi"), jamais une heure precise. Prendre la fin de
    journee minimise le risque de surestimer la duree pendant laquelle la
    cote etait reellement disponible. Le jour de reference choisi est
    TOUJOURS strictement anterieur (au moins un jour calendaire complet) au
    jour du match, jamais le jour meme - condition necessaire pour garantir
    `knowledge_time < kickoff` quelle que soit l'heure de coup d'envoi.

    Leve ``AmbiguousCollectionWindowError`` pour un match du LUNDI, du
    MARDI (la collecte du mardi ne peut pas etre garantie anterieure a un
    match ayant lieu ce meme mardi) ou du VENDREDI - la regle documentee
    ne precise pas ces cas, aucune hypothese supplementaire n'est inventee
    ici.
    """
    local_kickoff = kickoff_utc.astimezone(_LONDON)
    weekday = local_kickoff.weekday()  # lundi=0 ... dimanche=6

    if weekday in (5, 6):  # samedi, dimanche
        reference_date: date = local_kickoff.date() - timedelta(days=weekday - 4)  # vendredi=4
    elif weekday in (2, 3):  # mercredi, jeudi
        reference_date = local_kickoff.date() - timedelta(days=weekday - 1)  # mardi=1
    else:  # lundi (0), mardi (1) ou vendredi (4)
        jour = {0: "lundi", 1: "mardi", 4: "vendredi"}[weekday]
        raise AmbiguousCollectionWindowError(
            f"Kickoff {kickoff_utc.isoformat()} tombe un {jour} : la fenetre de collecte "
            "documentee par Football-Data (\"vendredi apres-midi pour le week-end, mardi "
            "apres-midi pour la semaine\") ne precise pas explicitement ce cas, ou ne peut pas "
            "garantir une reference strictement anterieure au match. Aucune hypothese "
            "supplementaire n'est introduite silencieusement."
        )

    reference_dt = datetime.combine(reference_date, time(23, 59, 59), tzinfo=_LONDON)
    return reference_dt.astimezone(timezone.utc)
