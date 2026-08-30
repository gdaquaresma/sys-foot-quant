"""Chargeur de donnees Polymarket - AUCUN APPEL RESEAU (Phase L, etape 3).

Decision architecturale documentee (voir docs/polymarket_pomet_data_audit.md
section 6) : l'environnement d'execution de cette session bloque tout acces
sortant vers ``gamma-api.polymarket.com``, ``data-api.polymarket.com``,
``clob.polymarket.com`` et ``pomet.com.br`` (verifie directement, 403 -
politique de sortie reseau explicite, voir audit reseau de la Phase L).
Independamment de cette contrainte, CE PROJET n'a jamais embarque de client
HTTP dans ``src/`` pour aucune source externe (Football-Data, Understat,
ClubElo sont tous charges depuis des fichiers locaux obtenus hors-bande) -
ce module suit exactement la meme convention, deliberement, pas seulement
a cause du blocage reseau de cette session.

Ce module charge donc des fichiers JSON locaux DEJA obtenus hors-bande
(export manuel navigateur, ou futur script d'extraction execute dans un
environnement disposant d'un acces reseau reel). Il n'invente, ne simule
et ne devine AUCUNE reponse API.

Correspondance documentee (sources publiques tierces convergentes, NON
verifiee par appel reel dans cet environnement - a confirmer avant tout
chargement de donnees reelles ; Phase M, docs/polymarket_data_feasibility_audit.md
section 2) :

| Fonction ci-dessous | API Polymarket documentee | Endpoint | Parametres cles documentes (non verifies) |
|---|---|---|---|
| ``load_gamma_markets_json`` | Gamma API (public, sans authentification, ~4000 req/10s documente) | GET https://gamma-api.polymarket.com/markets | ``closed``/``archived`` (filtrage statut), tags |
| ``load_gamma_events_json`` | Gamma API | GET https://gamma-api.polymarket.com/events | idem |
| ``load_data_api_trades_json`` | Data API (public, sans authentification, ~1000 req/10s documente) | GET https://data-api.polymarket.com/trades | ``limit`` (defaut 100, max 500 documentes), ``offset`` (plafond documente a 10000 - au-dela, 400 explicite, jamais silencieux ; paginer par fenetre temporelle au-dela) |
| ``load_data_api_positions_json`` | Data API | GET https://data-api.polymarket.com/positions | ``user`` (wallet, obligatoire) |
| ``load_clob_prices_history_json`` | CLOB API | GET https://clob.polymarket.com/prices-history | ``market`` (token id), ``startTs``/``endTs`` (Unix, exclusifs de) ``interval``, ``fidelity`` (minutes) - **disponibilite non demontree pour un marche deja resolu, voir avertissement ci-dessous** |

Resolution (UMA Optimistic Oracle, documentation publique) : requete ->
proposition (bond 750 USDC) -> fenetre de contestation de 2h -> si
contestee, second arbitrage puis vote DVM si contestee une seconde fois.
Pertinent pour ``Market.resolution_time`` (etape 5/6 de l'audit Phase M) :
un marche n'est determinable au plus tot que 2h apres la proposition
d'issue, jamais avant - mais cette regle generale n'a pas ete verifiee
specifiquement sur un marche football reel (mecanisme de resolution
sportive potentiellement distinct, cf. audit Phase M section 9).

Pomet n'a pas d'export/API public documente identifie lors de cet audit -
aucun chargeur Pomet n'est cree ici (voir l'audit, section 2 : aucune
fabrication d'API non confirmee)."""

from __future__ import annotations

import json
from pathlib import Path


def _load_json_records(path: str | Path) -> list[dict]:
    """Charge une liste de dictionnaires JSON depuis un fichier local.
    Leve une erreur explicite si le fichier est absent, illisible, ou si
    la racine n'est pas une liste - jamais une liste vide inventee en cas
    d'echec de lecture."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Fichier d'export Polymarket introuvable : {p}.")
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(
            f"Format inattendu dans {p} : racine JSON de type {type(data).__name__}, liste attendue."
        )
    return data


def load_gamma_markets_json(path: str | Path) -> list[dict]:
    """Charge un export local de la reponse Gamma API ``GET /markets``
    (liste de dictionnaires bruts, un par marche). A passer a
    ``markets.parse_market`` pour normalisation."""
    return _load_json_records(path)


def load_gamma_events_json(path: str | Path) -> list[dict]:
    """Charge un export local de la reponse Gamma API ``GET /events``."""
    return _load_json_records(path)


def load_data_api_trades_json(path: str | Path) -> list[dict]:
    """Charge un export local de la reponse Data API ``GET /trades``
    (liste de dictionnaires bruts, un par trade). A passer a
    ``trades.parse_trade`` pour normalisation."""
    return _load_json_records(path)


def load_data_api_positions_json(path: str | Path) -> list[dict]:
    """Charge un export local de la reponse Data API ``GET /positions``.

    ATTENTION PIT (etape 5) : cet endpoint, tel que documente
    publiquement, renvoie l'etat COURANT (« maintenant ») des positions
    d'un wallet, jamais un instantane a une date passee. Il ne doit donc
    JAMAIS etre utilise pour reconstruire l'etat d'un wallet a une
    ``decision_time`` passee - seul ``positions.derive_positions_as_of``
    (reconstruction depuis le journal de trades, filtre par timestamp)
    est PIT-sur. Ce chargeur reste utile uniquement pour un audit ponctuel
    de l'etat present, jamais pour une analyse historique."""
    return _load_json_records(path)


def load_clob_prices_history_json(path: str | Path) -> list[dict]:
    """Charge un export local de la reponse CLOB API ``GET
    /prices-history`` (liste de points ``{t, p}`` ou equivalent, un par
    observation de prix). A passer a ``imports.parse_price_point``
    (Phase N) pour normalisation.

    RESERVE CRITIQUE NON RESOLUE (Phase N, docs/polymarket_data_feasibility_audit.md
    section 7) : un signalement tiers non verifie indique que cet
    endpoint pourrait ne renvoyer AUCUNE donnee a granularite fine pour un
    marche DEJA RESOLU - precisement le cas d'usage recherche ici
    (reconstruire le prix tel qu'il etait avant un match deja joue). Ce
    chargeur ne fait QUE lire un fichier local deja obtenu - il ne peut ni
    confirmer ni infirmer cette limite ; seul un export reel le pourra."""
    return _load_json_records(path)
