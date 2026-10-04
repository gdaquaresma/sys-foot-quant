"""Jours de repos / congestion intra-championnat - Brique 1, Phase I/E
(docs/final_data_strategy.md, docs/next_signal_strategy.md section 4.B,
docs/fixture_congestion_experiment_specification.md).

Question posee a terme (jamais tranchee par ce module) : le nombre de
jours de repos depuis le dernier match d'une equipe apporte-t-il une
information PREDICTIVE INCREMENTALE sur le total de buts, au-dela de ce
que le moteur actuel possede deja ? Ce module se limite STRICTEMENT a la
construction du signal (jours de repos point-in-time) - AUCUNE
comparaison de modele, AUCUN test statistique, AUCUN seuil, AUCUNE
decision BET ici.

VARIANTE VOLONTAIREMENT PARTIELLE ("Brique 1", intra-championnat
uniquement) : seuls les matchs du MEME (competition, season) deja
catalogues par ``match_catalog`` sont consideres - les matchs de coupe et
de competitions europeennes sont ABSENTS du corpus actuel
(docs/final_data_strategy.md section 3) et ne sont donc jamais comptes
ici. Consequence assumee et deja documentee avant toute execution :
cette variante SOUS-ESTIME mecaniquement le repos reel d'une equipe qui
joue aussi ces competitions - jamais presentee comme une mesure complete
de la congestion.

PLACEMENT ARCHITECTURAL : ce module ne manipule aucune cote de marche,
mais rejoint ``data_engine/market_odds/`` par coherence avec les modules
deja isoles qui y vivent pour la meme raison (signal PIT construit a
partir du corpus deja catalogue, jamais un nouveau fournisseur de
cotes) - exactement le meme choix deja fait pour ``elo_ratings.py``/
``elo_archive_ingest.py`` (note de force d'equipe, pas une cote) et
``shots_on_target.py`` (statistique de match, pas une cote). Aucun
nouveau sous-package ``data_engine/schedule/`` n'est cree : l'architecture
existante justifie deja ce choix plutot que d'en ouvrir un nouveau pour
un seul module.

AUCUNE DONNEE NOUVELLE : reutilise EXCLUSIVEMENT
``data_engine.market_odds.match_catalog.list_matches`` (INCHANGE, deja
trie de facon deterministe par coup d'envoi puis ``match_id``) - les
dates de coup d'envoi sont deja chargees par le reste du projet, aucune
acquisition, aucun nouveau fichier.

REGLE PIT (non negociable, verifiee par
``tests/leakage/test_fixture_congestion_point_in_time.py``) : pour un
match cible, seuls les matchs dont le coup d'envoi est STRICTEMENT
anterieur a celui du match cible sont consideres pour trouver le
"dernier match" d'une equipe - jamais le match cible lui-meme (exclu
explicitement, garde-fou redondant volontaire, meme discipline que
``shots_on_target.sot_training_pool``), jamais un match posterieur."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sys_foot_quant.data_engine.market_odds.match_catalog import MatchSummary


class FixtureCongestionError(ValueError):
    """Refus explicite (equipe ne jouant pas le match cible, match hors
    perimetre (competition, season) de la cible) - jamais un resultat
    partiel ou un melange implicite de championnats/saisons."""


@dataclass(frozen=True)
class RestDaysResult:
    """Jours de repos d'UNE equipe avant UN match - ``rest_days`` vaut
    ``None`` explicitement (jamais 0, jamais une valeur inventee) quand
    aucun match anterieur n'existe dans le perimetre (premier match de la
    saison pour cette equipe) : historique insuffisant, pas une absence de
    repos."""

    team: str
    match_id: str
    kickoff_utc: datetime
    is_home: bool
    previous_match_id: str | None
    previous_kickoff_utc: datetime | None
    rest_days: float | None


@dataclass(frozen=True)
class MatchCongestionFeature:
    """Vue combinee domicile/exterieur pour un match - jamais fusionnee en
    une seule valeur ici (une eventuelle difference domicile-exterieur se
    calcule explicitement via ``rest_days_diff``, jamais implicitement)."""

    match_id: str
    home_team: str
    away_team: str
    kickoff_utc: datetime
    home_rest_days: float | None
    away_rest_days: float | None
    home_previous_match_id: str | None
    away_previous_match_id: str | None


def _validate_same_scope(matches: tuple[MatchSummary, ...], target: MatchSummary) -> None:
    for m in matches:
        if m.competition != target.competition or m.season != target.season:
            raise FixtureCongestionError(
                f"Match {m.match_id!r} ({m.competition!r}, {m.season!r}) hors du perimetre de la "
                f"cible {target.match_id!r} ({target.competition!r}, {target.season!r}) - cette "
                "variante Brique 1 est volontairement limitee au meme championnat/saison "
                "(voir docs/fixture_congestion_experiment_specification.md), jamais un melange implicite."
            )


def _team_matches_strictly_before(
    matches: tuple[MatchSummary, ...], team: str, kickoff_utc: datetime, exclude_match_id: str
) -> list[MatchSummary]:
    """Matchs impliquant ``team``, dont le coup d'envoi est STRICTEMENT
    anterieur a ``kickoff_utc``, a l'exclusion explicite de
    ``exclude_match_id`` - jamais le match cible lui-meme (garde-fou
    redondant : ``m.kickoff_utc < kickoff_utc`` exclut deja
    structurellement le match cible et tout match posterieur, mais
    ``exclude_match_id`` reste verifie separement, jamais suppose
    suffisant a lui seul - meme discipline que
    ``shots_on_target.sot_training_pool``)."""
    return [
        m
        for m in matches
        if m.match_id != exclude_match_id
        and (m.home_team == team or m.away_team == team)
        and m.kickoff_utc < kickoff_utc
    ]


def rest_days_before_match(matches: tuple[MatchSummary, ...], target: MatchSummary, team: str) -> RestDaysResult:
    """Jours de repos de ``team`` avant ``target``, calcules EXCLUSIVEMENT
    a partir des matchs de ``matches`` strictement anterieurs au coup
    d'envoi de ``target``. ``matches`` peut contenir ``target`` lui-meme
    et/ou des matchs posterieurs : ils sont filtres ici, jamais supposes
    deja absents en entree - l'appelant n'a donc pas a pre-filtrer.

    Deterministe : le "dernier match" est celui dont ``kickoff_utc`` est
    maximal ; en cas d'egalite exacte de coup d'envoi (ne devrait jamais
    survenir dans un calendrier reel a une seule competition), le
    depart-egalite se fait sur ``match_id`` - jamais un ordre d'iteration
    non garanti.

    Leve ``FixtureCongestionError`` si ``team`` ne joue pas ``target``, ou
    si ``matches`` contient un match hors du (competition, season) de
    ``target``."""
    if team not in (target.home_team, target.away_team):
        raise FixtureCongestionError(
            f"{team!r} ne joue pas le match {target.match_id!r} ({target.home_team} - {target.away_team})."
        )
    _validate_same_scope(matches, target)

    prior = _team_matches_strictly_before(matches, team, target.kickoff_utc, target.match_id)
    is_home = team == target.home_team
    if not prior:
        return RestDaysResult(
            team=team,
            match_id=target.match_id,
            kickoff_utc=target.kickoff_utc,
            is_home=is_home,
            previous_match_id=None,
            previous_kickoff_utc=None,
            rest_days=None,
        )

    last = max(prior, key=lambda m: (m.kickoff_utc, m.match_id))
    rest_days = (target.kickoff_utc - last.kickoff_utc).total_seconds() / 86400.0
    return RestDaysResult(
        team=team,
        match_id=target.match_id,
        kickoff_utc=target.kickoff_utc,
        is_home=is_home,
        previous_match_id=last.match_id,
        previous_kickoff_utc=last.kickoff_utc,
        rest_days=rest_days,
    )


def congestion_feature_for_match(matches: tuple[MatchSummary, ...], target: MatchSummary) -> MatchCongestionFeature:
    """Vue combinee domicile/exterieur pour ``target`` - compose deux
    appels independants de ``rest_days_before_match`` (une par equipe),
    jamais un calcul partage qui risquerait de confondre les deux
    historiques."""
    home = rest_days_before_match(matches, target, target.home_team)
    away = rest_days_before_match(matches, target, target.away_team)
    return MatchCongestionFeature(
        match_id=target.match_id,
        home_team=target.home_team,
        away_team=target.away_team,
        kickoff_utc=target.kickoff_utc,
        home_rest_days=home.rest_days,
        away_rest_days=away.rest_days,
        home_previous_match_id=home.previous_match_id,
        away_previous_match_id=away.previous_match_id,
    )


def rest_days_diff(feature: MatchCongestionFeature) -> float | None:
    """``home_rest_days - away_rest_days`` - indicateur symetrique
    domicile/exterieur optionnel (demande explicitement, section 1 de
    l'etape 1). ``None`` si l'un des deux cotes a un historique
    insuffisant - jamais une valeur par defaut inventee (ex. 0) qui
    masquerait silencieusement l'absence de donnee d'un cote."""
    if feature.home_rest_days is None or feature.away_rest_days is None:
        return None
    return feature.home_rest_days - feature.away_rest_days


def congestion_dataset_for_season(
    competition: str, matches: tuple[MatchSummary, ...]
) -> tuple[MatchCongestionFeature, ...]:
    """Feature de congestion pour TOUS les matchs de ``matches`` (deja
    obtenus via ``match_catalog.list_matches(competition, season)`` par
    l'appelant - ce module ne fait lui-meme aucune lecture de fichier,
    meme discipline que ``shots_on_target.build_shots_on_target_dataset``
    qui recoit des donnees deja chargees). ``competition`` n'est utilise
    que pour un message d'erreur explicite si ``matches`` est vide -
    jamais pour filtrer silencieusement."""
    if not matches:
        raise FixtureCongestionError(f"Aucun match fourni pour {competition!r} - rien a calculer.")
    return tuple(congestion_feature_for_match(matches, target) for target in matches)
