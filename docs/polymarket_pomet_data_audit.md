# Audit Pomet / Polymarket — Phase L

**Portée** : audit de données et préparation d'une couche d'ingestion
isolée, en vue d'une future expérience visant à déterminer si les
décisions de certains traders Polymarket contiennent une information
incrémentale sur les matchs de football. **Aucune expérience de
performance n'est menée dans ce document.** Aucun résultat E1→K n'est
modifié. Le moteur final reste **GELÉ** (`min_edge_threshold=None`,
`BET` non activé, `df709cb`/`7a89cd1`).

---

## 1. Objectif

Auditer précisément ce que Pomet (pomet.com.br) et les API publiques
Polymarket exposent réellement, déterminer si Pomet est une dépendance
nécessaire, et construire — uniquement si les données sont suffisamment
accessibles — une couche isolée `src/sys_foot_quant/polymarket/` capable
de représenter des traders/trades/marchés de façon normalisée et
strictement point-in-time (PIT), sans jamais toucher `final_engine`.

---

## 2. Limitation d'environnement — à lire avant tout le reste

**L'audit direct des deux sites demandés (`pomet.com.br` et
`docs.polymarket.com`/les API Polymarket) n'a pas pu être réalisé par
inspection primaire.** L'environnement d'exécution de cette session
bloque tout accès réseau sortant en dehors d'une liste explicite
(GitHub, PyPI, npm, registres de paquets, API Anthropic) :

```
$ curl -sS -m 10 https://gamma-api.polymarket.com/markets?limit=1
curl: (56) CONNECT tunnel failed, response 403
$ curl -sS -m 10 https://www.pomet.com.br/
curl: (56) CONNECT tunnel failed, response 403
```

Confirmé par le statut du proxy de sortie (`recentRelayFailures`) :
`gateway answered 403 to CONNECT (policy denial or upstream failure)`
pour `gamma-api.polymarket.com:443` et `www.pomet.com.br:443`. Ce n'est
pas une panne réseau transitoire mais une **politique de sortie explicite
de cet environnement** (probablement restreinte à GitHub + registres de
paquets pour cette session).

Conformément à l'étape 10 de la consigne (« si l'environnement réseau ne
permet pas l'accès : STOP, ne fabrique aucune donnée, ne simule aucune
réponse API »), **cette règle a été appliquée à l'ensemble de l'audit**,
pas seulement à l'extraction de données réelles : aucune réponse JSON, ni
colonne CSV, ni structure d'API n'a été inventée dans ce document ou dans
le code. Toute affirmation ci-dessous provient soit :

- de la recherche web (résultats indexés de tiers, docs.polymarket.com,
  GitHub, blogs techniques) — outil distinct du proxy de sortie bloqué,
  donc fonctionnel, mais qui ne donne accès qu'à des **extraits/résumés
  indirects**, jamais au contenu brut d'une page ni à une réponse JSON
  réelle ;
- de conventions déjà établies et déjà **vérifiées dans ce dépôt** pour
  d'autres sources externes (Football-Data, Understat, ClubElo).

**Ce qui n'a PAS pu être vérifié par cet audit** (et ne doit être présenté
nulle part comme confirmé) : le nom exact des champs JSON retournés par
une requête réelle à une API Polymarket, l'existence ou non d'un export
CSV Pomet, les colonnes exactes d'un éventuel export, le format exact
d'un titre de marché Polymarket football réel, la couverture historique
réelle des marchés football sur Polymarket.

**Procédure pour débloquer un futur audit réel** :
1. Exécuter cette même phase dans un environnement dont la politique
   réseau autorise `gamma-api.polymarket.com`, `data-api.polymarket.com`,
   `clob.polymarket.com` et `pomet.com.br` ; ou
2. Fournir manuellement (comme cela a été fait pour ClubElo en Phase K) :
   quelques réponses JSON réelles de `GET /markets` (Gamma), `GET /trades`
   et `GET /positions` (Data API) pour 2-3 marchés football identifiés
   manuellement, et une capture/export réel d'une page Pomet (leaderboard
   + fiche d'un trader) ; ou
3. Exécuter le futur script d'extraction hors-bande (à écrire lors d'une
   phase ultérieure) depuis une machine disposant d'un accès réseau
   normal, puis fournir les fichiers JSON produits à `client.py` (§6).

---

## 3. Pomet — ce qui a pu être établi (source : recherche web, non vérifié par inspection primaire)

| Question (étape 1) | Réponse (confiance) |
|---|---|
| 1. Quelles données Pomet expose | Un classement de traders Polymarket (profit total, ROI, volume), filtrable par période (tout/30j/7j/24h) et par catégorie (sport, politique, crypto, économie), et une fiche individuelle par trader ("Analisador de Apostadores"). **Confiance : moyenne** (convergent sur plusieurs pages indexées). |
| 2. Sous quelle forme | Application web (dashboard/leaderboard) + bot Telegram d'alertes + robot de copie automatique de trades téléchargeable. **Confiance : moyenne.** |
| 3. Export CSV réellement disponible ? | **Aucune preuve trouvée.** Recherches dédiées (mots-clés "exportar", "CSV", "API") ne retournent aucun résultat mentionnant une fonctionnalité d'export chez Pomet. **Absence de preuve, pas preuve d'absence** — mais à rapprocher du modèle économique du produit (§3, point 15) qui pousse vers le bot/Telegram, pas vers l'export de données brutes. |
| 4. Colonnes disponibles | **Non déterminable** sans inspection directe de l'interface réelle. |
| 5. Trades individuels disponibles ? | Le produit met en avant les **positions réelles on-chain** ("real blockchain data", "voit ce que les traders parient réellement avec leur argent réel") — suggère un accès aux trades/positions individuels dans l'interface, mais la granularité exacte (trade-par-trade vs agrégé) n'est pas confirmée. |
| 6. Positions ouvertes disponibles ? | Suggéré par le marketing produit ("audite n'importe quel trader avant de le suivre"), non confirmé structurellement. |
| 7. Positions clôturées disponibles ? | Idem — non confirmé structurellement. |
| 8. Timestamps exacts des trades ? | **Non déterminable.** |
| 9. Adresse/wallet du trader disponible ? | Vraisemblable (le produit revendique une vérification blockchain, ce qui suppose l'exposition d'une adresse), **non confirmé**. |
| 10. Prix/taille/side/marché disponibles ? | **Non déterminable** avec certitude ; le "niveau de confiance" décrit (§3, point 13) implique nécessairement un accès à la taille de la position courante vs. historique moyenne du trader, ce qui suggère un accès au moins agrégé à la taille des trades. |
| 11. Identifiant stable de marché Polymarket exposé ? | **Non déterminable.** |
| 12. Historique complet ou vue filtrée ? | Vue filtrée par construction (périodes 24h/7j/30j/tout, catégories) — pas d'indication d'un accès à un flux brut complet. |
| 13. Informations calculées par Pomet lui-même | Le **"niveau de confiance"** (compare la taille d'un nouveau pari à la moyenne historique du trader, marque "haute confiance" si largement supérieure) est explicitement une métrique **calculée par Pomet**, pas une donnée Polymarket brute. Le classement lui-même (tri par profit/ROI/volume sur une fenêtre) est également une vue calculée. |
| 14. Informations provenant directement de Polymarket | Les positions/trades on-chain eux-mêmes (la donnée source), si effectivement exposés — Pomet revendique explicitement ne pas déformer la donnée blockchain publique. |
| 15. Fonctionnalités nécessitant un abonnement | Le produit est **payant par abonnement**, à partir de R$49,90/mois (plan trimestriel), donnant accès à une "Pomet Selection" (sélection propre) et à la possibilité de créer sa propre sélection de traders à suivre + alertes Telegram + bot de copie. |
| 16. API Pomet publique documentée ? | **Aucune trouvée.** Aucune page de documentation d'API Pomet n'apparaît dans les résultats de recherche, contrairement à Polymarket qui a une documentation publique bien indexée (`docs.polymarket.com`). |
| 17. Authentification nécessaire ? | Vraisemblable pour toute fonctionnalité au-delà du classement public (compte utilisateur payant), **non confirmé en détail**. |
| 18. Récupération automatique possible ? | **Aucune preuve d'une voie programmatique légitime** (API/export). Le produit semble conçu pour une consultation humaine (dashboard) + une livraison applicative fermée (bot Telegram, robot de trading) — pas pour l'intégration par un tiers. |

---

## 4. Polymarket direct — ce qui a pu être établi (source : recherche web, convergence forte de plusieurs sources indépendantes, non vérifié par appel réel)

Trois surfaces d'API publiques et documentées, décrites de façon
cohérente par de multiples sources indépendantes (pages officielles
`docs.polymarket.com` indexées, dépôts GitHub officiels `Polymarket/*`,
articles techniques tiers convergents) :

| API | Base URL (documentée, non appelée dans cet audit) | Rôle | Authentification (lecture) |
|---|---|---|---|
| **Gamma API** | `https://gamma-api.polymarket.com` | Catalogue / découverte : `/markets`, `/events`, `/events/slug/{slug}` — titres, tags, descriptions, volumes, dates de fin, issues résolues | **Publique, aucune authentification** (convergent sur toutes les sources) |
| **CLOB API** | `https://clob.polymarket.com` | Carnet d'ordres, prix (`/prices-history`), trades, tokens — chaîne Polygon (137) | Lecture publique sans authentification ; passage d'ordres nécessite une signature EIP-712 + clés API dérivées du wallet |
| **Data API** | `https://data-api.polymarket.com` | Données par wallet : `/positions` (position **courante**, paramètre `user` obligatoire), `/trades` (historique de trades pour un wallet ou un marché), classement de traders (page officielle indexée : « Get trader leaderboard rankings ») | **Publique, aucune authentification** pour la lecture (convergent) |

**Constat le plus important de cette section** : la documentation
officielle Polymarket (`docs.polymarket.com/api-reference/core/`) expose
elle-même des pages intitulées littéralement *« Get trades for a user or
markets »* et *« Get trader leaderboard rankings »* — c'est-à-dire que
**Polymarket documente et expose nativement un classement de traders**,
la fonctionnalité présentée comme le cœur de l'offre Pomet.

**Réserve explicite** : ces constats reposent sur la convergence de
sources secondaires indépendantes (documentation officielle indexée, code
source public `Polymarket/agents` sur GitHub, plusieurs guides techniques
tiers cohérents entre eux), ce qui donne une **confiance raisonnable**
sur l'existence et le rôle de ces trois API et de ces endpoints — mais
**aucun appel réel n'a été effectué dans cet environnement**, donc le nom
exact de chaque champ JSON retourné, la pagination exacte, les limites de
taux, et la couverture historique réelle **restent à confirmer**.

---

## 5. Comparaison Pomet vs Polymarket (étape 2)

| # | Élément | Disponible directement Polymarket | Disponible via Pomet | Reconstructible nous-mêmes | Uniquement calculé par Pomet | Impossible à obtenir (en l'état de cet audit) | Nécessite abonnement Pomet |
|---|---|---|---|---|---|---|---|
| A | Découverte des marchés | Oui (Gamma `/markets`, `/events`) | Oui (implicite, filtré par catégorie) | Oui | — | — | Non |
| B | Métadonnées des marchés | Oui (Gamma) | Oui (partiel, présentation) | Oui | — | — | Non |
| C | Trades individuels | Oui (Data API `/trades`) | Suggéré, non confirmé | Oui (via Data API) | — | — | Incertain |
| D | Positions (courantes) | Oui (Data API `/positions`, **état courant uniquement**) | Suggéré | Oui (état courant) ; **positions passées uniquement par reconstruction depuis `/trades`** | — | Positions historiques exactes à une date passée (aucune API ne les expose directement — reconstruction obligatoire, §7) | Incertain |
| E | Positions clôturées | Reconstructible depuis `/trades` + résolution du marché | Suggéré | Oui | — | — | Incertain |
| F | P&L | Non exposé tel quel par une API Polymarket documentée | Oui (mis en avant, "profit total") | Oui (calculable depuis trades + résolution, §7 de ce document) | — | — | Oui pour la vue Pomet |
| G | Wallet/address | Oui (c'est le paramètre `user` de Data API) | Probable | Oui | — | — | Non |
| H | Timestamps | Oui (Data API) | Non confirmé | Oui | — | — | Incertain |
| I | Prix d'entrée | Oui (`/trades`) | Non confirmé | Oui | — | — | Incertain |
| J | Taille des positions | Oui (`/trades`, `/positions`) | Oui (implicite, "niveau de confiance") | Oui | — | — | Incertain |
| K | Historique complet | Oui en principe (pagination `/trades`), couverture réelle non vérifiée | Non — vue filtrée par période (24h/7j/30j/tout) | Oui, à confirmer (limites de pagination/rate-limit réelles) | — | Couverture historique réelle non vérifiée des deux côtés | — |
| L | Classement des traders | **Oui — endpoint documenté nativement** | Oui (produit principal) | Oui | — | — | Non (Polymarket) / Oui (vue Pomet) |
| M | ROI | Non exposé tel quel, calculable depuis trades+résolutions | Oui (affiché) | Oui | — | — | Incertain |
| N | Win rate | Non exposé tel quel, calculable | Non confirmé explicitement | Oui | — | — | Incertain |
| O | Niveau de confiance Pomet | Non applicable | Oui | Non (heuristique propriétaire non documentée : comparaison taille du pari vs moyenne historique) | **Oui** | — | Oui |
| P | Catégorisation football/sport | Non nativement (Gamma expose des tags génériques, pas une taxonomie sport dédiée confirmée) | Oui (filtre "sports") | Partiellement (à construire nous-mêmes depuis les tags/titres Gamma, cf. §7) | Partiel | — | Oui pour le filtre Pomet |
| Q | Filtrage des meilleurs traders | Reconstructible depuis L+M+N | Oui (produit principal) | Oui (c'est l'objet de `traders.py`/`eligible_traders_as_of`) | — | — | Oui pour la sélection Pomet |

**Conclusion de la comparaison** : à l'exception de l'heuristique
propriétaire de « niveau de confiance » (O) et du filtrage/présentation
déjà mâchés (catégorie sport, sélection de traders prête à l'emploi), la
quasi-totalité des primitives de données nécessaires (wallet, trades,
positions, prix, taille, timestamps, classement) sont, sur la base de la
documentation publique Polymarket, **accessibles directement et sans
authentification** via les trois API Polymarket elles-mêmes.

---

## 6. Architecture retenue (étape 3)

```
src/sys_foot_quant/polymarket/
    __init__.py
    schemas.py     - Market, Trade, Trader, TraderStatsAsOf,
                     TraderInformationAsOf, MarketMatchResult
    reason_codes.py - POLYMARKET_MATCH_UNMATCHED / _AMBIGUOUS
    client.py      - chargeurs de FICHIERS JSON LOCAUX (voir decision ci-dessous)
    markets.py     - parse_market/parse_markets (brut -> Market)
    trades.py      - parse_trade/parse_trades/deduplicate_trades
    positions.py   - derive_positions_as_of (reconstruction PIT-sure)
    traders.py     - compute_trader_stats_as_of, EligibilityRules,
                     eligible_traders_as_of
    pit.py         - get_trader_information_as_of (point d'entree unique)
    matching.py    - normalize_team_name, CANONICAL_TEAM_ALIASES (vide),
                     match_market_to_football_data
```

**Décision architecturale : `client.py` ne fait AUCUN appel réseau.**
Justification à deux niveaux :
1. **Contrainte de cette session** : l'accès réseau sortant est bloqué
   (§2) — un client HTTP réel serait invérifiable ici.
2. **Convention déjà établie par ce projet, indépendamment de cette
   contrainte** : `football_data_loader.py` (Football-Data), le chargeur
   Understat, et `elo_archive_ingest.py` (ClubElo) ne font eux non plus
   **aucun appel réseau embarqué** — toutes les sources externes de ce
   dépôt sont ingérées depuis des fichiers locaux obtenus hors-bande
   (téléchargement manuel, export navigateur), jamais via un client HTTP
   dans `src/`. `client.py` suit exactement cette même convention :
   `load_gamma_markets_json(path)`, `load_gamma_events_json(path)`,
   `load_data_api_trades_json(path)`, `load_data_api_positions_json(path)`
   chargent des fichiers JSON déjà obtenus, avec le mapping vers les
   endpoints Polymarket documenté en commentaire (§4) mais jamais appelé.

Aucun chargeur Pomet n'a été créé (§3 : aucune API/export Pomet
confirmé — écrire un parseur pour un format non observé serait une
fabrication, explicitement interdite par la consigne).

**Isolation `final_engine`** : vérifiée par test AST dédié
(`tests/unit/test_polymarket_no_final_engine_dependency.py`) dans les
deux sens — aucun module de `final_engine/` ne référence `polymarket`,
aucun module de `polymarket/` ne référence `final_engine`.

---

## 7. Schéma normalisé (étape 4)

Voir `src/sys_foot_quant/polymarket/schemas.py` pour le détail complet.
Points notables par rapport à la demande initiale :

- **`Trader` ne porte aucune statistique** (pas de `historical_stats_as_of`/
  `ranking_as_of` stockés statiquement sur l'objet). Déviation
  **délibérée et documentée** par rapport à la lettre de la consigne :
  stocker une statistique sur l'objet `Trader` lui-même créerait un
  risque structurel de réutilisation d'un instantané périmé pour un
  `decision_time` différent de celui pour lequel il a été calculé —
  exactement le risque de fuite que l'étape 5 demande d'éliminer. À la
  place, toute statistique est portée par `TraderStatsAsOf`, un objet
  immuable **explicitement horodaté** (`as_of`), produit à la demande par
  `traders.compute_trader_stats_as_of`/`pit.get_trader_information_as_of`
  — jamais mis en cache sur le `Trader`.
- **`Market.outcome`** est une convention interne explicite (issue
  gagnante une fois résolu, `None` sinon) — **non vérifiée** contre la
  structure réelle de la Gamma API (§2).
- **`Trade.notional`** est toujours calculé (`price * size`) au parsing,
  jamais lu tel quel d'une source qui ne le fournirait pas.
- Tous les champs non strictement indispensables à l'usage interne
  restent `Optional` — aucun champ n'est présumé toujours présent.

---

## 8. Matching football (étape 6)

Pipeline implémenté dans `matching.py` :
`Market.home_team`/`away_team` (déjà renseignés en amont) → résolution
canonique via `CANONICAL_TEAM_ALIASES` (dictionnaire explicite par
championnat, **volontairement vide** — voir ci-dessous) → recherche parmi
des `FootballDataMatchCandidate` par équipes canoniques + fenêtre de date
(±12h) → `match_id` unique, ou rejet explicite.

**`CANONICAL_TEAM_ALIASES` est intentionnellement vide.** Ce projet a une
règle stricte, déjà appliquée trois fois (Understat via `team_mapping.py`,
ClubElo via `elo_team_mapping.py`, toutes deux vérifiées **à la main**
contre des données réelles) : un dictionnaire de correspondance de noms
d'équipes n'est jamais construit par supposition ou par convention de
wrapper tiers — toujours vérifié entrée par entrée contre la source
réelle. Aucun titre de marché Polymarket réel n'a pu être inspecté dans
cet audit (§2) : remplir cette table maintenant serait une fabrication.
**Cette table doit être construite lors d'un futur audit disposant d'un
accès réseau réel (ou de captures manuelles, comme cela a été fait pour
ClubElo en Phase K), jamais avant.**

**Réserve supplémentaire, plus fondamentale** : `matching.py` suppose que
`Market.home_team`/`away_team` sont déjà extraits. Un marché Polymarket
football réel se présente vraisemblablement comme un titre libre (ex.
« Will Real Madrid beat Barcelona? ») dont il faudrait extraire les deux
équipes par un parseur de texte dédié. **Ce parseur n'a pas été écrit** :
il nécessite des exemples réels de titres pour être conçu sans deviner un
format non confirmé (même principe que pour le reste de cet audit). Tant
qu'il n'existe pas, tout marché sans `home_team`/`away_team` déjà
renseignés est rejeté `POLYMARKET_MATCH_UNMATCHED` — jamais une tentative
de deviner ces champs depuis le titre.

Deux codes de rejet stables (`reason_codes.py`), jamais de correspondance
forcée :
- `POLYMARKET_MATCH_UNMATCHED` : équipes non résolues, ou aucun candidat
  Football-Data ne correspond (équipes + fenêtre de date).
- `POLYMARKET_MATCH_AMBIGUOUS` : plusieurs candidats correspondent
  simultanément.

---

## 9. Point-in-time (étape 5) — le point le plus important de cette phase

`pit.get_trader_information_as_of(wallet_id, decision_time, trades,
markets)` est le **seul point d'entrée** destiné à alimenter une future
analyse. Garanties, toutes couvertes par
`tests/leakage/test_polymarket_point_in_time.py` :

| Garantie demandée | Mécanisme | Test |
|---|---|---|
| Trades futurs exclus | Filtre strict `timestamp_utc < decision_time`, appliqué **dans la fonction elle-même** (jamais délégué à l'appelant, contrairement à `final_engine` — choix documenté dans `pit.py` : ici la fonction EST le point de filtrage) | `test_trades_as_of_never_includes_a_future_trade` |
| n_trades futur exclu | Idem, `compute_trader_stats_as_of` ne compte que les trades filtrés | `test_n_trades_as_of_ignores_the_20_future_trades` (reproduit l'exemple 100 avant / 20 après de la consigne) |
| Volume futur exclu | Idem | `test_volume_as_of_ignores_the_20_future_trades` |
| Positions futures exclues | `positions.derive_positions_as_of` ne nette que les trades `< decision_time` — **jamais** l'endpoint `/positions` (état courant, PIT-dangereux, voir avertissement dans `client.py`) | `test_positions_as_of_ignores_the_20_future_trades` |
| ROI/P&L réalisé jamais calculé avec une résolution pas encore connue | Un trade ne contribue au P&L réalisé QUE si `market.resolution_time` est connu ET `< decision_time` | `test_realized_pnl_and_win_rate_never_use_a_resolution_known_only_in_the_future` |
| Win rate jamais calculé avec des paris postérieurs | Même filtre que le P&L (dérivé des mêmes trades résolus avant `decision_time`) | même test |
| Classement futur exclu | `eligible_traders_as_of` délègue entièrement à `compute_trader_stats_as_of` (déjà PIT-sûr), jamais un tri sur des stats non bornées | `test_ranking_selection_never_uses_future_trades` |
| Deux `decision_time` différents ne partagent jamais un résultat mis en cache | Aucun état mutable partagé entre appels ; chaque appel recalcule tout | `test_two_different_decision_times_yield_different_stats_never_cached_or_reused` |

---

## 10. Risques de fuite identifiés (au-delà du strict PIT trade-log)

- **`/positions` (Data API) est un piège PIT** : cet endpoint documenté
  renvoie l'état courant, jamais un instantané passé. Un usage naïf pour
  une analyse historique (« quelle était la position du wallet X le jour
  Y ? » en appelant `/positions` à un jour Y passé) serait soit impossible
  (l'API ne prend pas de paramètre de date), soit trompeur. **Ce risque
  est neutralisé par construction** : `client.py` documente explicitement
  cette limite et aucune fonction de ce package n'utilise
  `load_data_api_positions_json` pour une reconstruction historique —
  seul `positions.derive_positions_as_of` (depuis le journal de trades)
  est utilisé à cette fin.
- **Timestamp non timezone-aware** : `trades.parse_trade` lève une
  erreur explicite plutôt que de supposer UTC silencieusement pour un
  timestamp textuel sans fuseau — élimine un risque de décalage silencieux
  (cohérent avec la rigueur déjà appliquée au moteur final,
  `docs/final_preproduction_audit.md` section 8).
- **Résolution de marché prématurée** : un marché dont l'issue est
  déjà connue dans les données mais dont `resolution_time` tombe après
  `decision_time` n'est jamais compté (test dédié, §9).
- **Aucune donnée n'est encore réellement ingérée** : ce risque n'a pu
  être testé que sur données synthétiques (§12) — un futur audit avec
  données réelles devra vérifier que les timestamps de résolution
  effectivement publiés par Polymarket sont bien des timestamps de
  RÉSOLUTION on-chain (connaissance publique immédiate) et non une date
  de traitement administratif différée, point non vérifiable ici.

---

## 11. Couverture réelle (étape 7, partielle)

**Aucune donnée réelle de marché football Polymarket n'a pu être
inspectée** (§2). Ce qui suit relève donc de connaissances publiques
générales sur Polymarket, pas d'un inventaire vérifié :

| Point demandé | Statut |
|---|---|
| Types de marchés football disponibles (moneyline, draw, O/U, handicap) | Polymarket propose historiquement des marchés binaires (Yes/No) par évènement — un marché « vainqueur » nécessiterait donc plusieurs marchés binaires liés par `event_id` (un par équipe + un pour le nul), plutôt qu'un marché ternaire natif. **Non confirmé pour le football spécifiquement.** |
| Disponibilité historique | Non vérifiée. |
| Résolution | Mécanique standard des jetons conditionnels (redemption 1$/0$), documentée publiquement pour Polymarket en général — non vérifiée spécifiquement pour un marché football réel. |
| Granularité / timestamps | Non vérifiée. |
| Volume / liquidité | Non vérifiée. |
| Couverture (championnats, saisons) | Non vérifiée. |

**Aucune décision sur quels marchés seraient utilisés dans une future
expérience n'est prise ici**, conformément à la consigne.

---

## 12. Données réelles (étape 10) — STOP appliqué

Aucune extraction historique, aucun appel réseau, aucune donnée réelle
n'a été récupérée dans cette phase. Voir §2 pour le détail exact du
blocage et la procédure de déblocage. Les 61 nouveaux tests (§13) portent
tous sur des données **synthétiques**, jamais sur un enregistrement réel
Polymarket/Pomet.

---

## 13. Limitations

1. Aucune vérification primaire des schémas de réponse Polymarket réels.
2. Aucune vérification de l'existence d'un export/API Pomet au-delà de
   l'absence de preuve trouvée.
3. `CANONICAL_TEAM_ALIASES` est vide — le matching football est
   architecturalement prêt mais **inopérant tant qu'aucune donnée réelle
   n'a permis de le peupler**.
4. Aucun parseur de titre de marché (extraction `home_team`/`away_team`
   depuis un texte libre) n'existe — étape préalable indispensable avant
   tout matching réel.
5. Le modèle de règlement (`_settlement_pnl_per_share`, redemption 1$/0$,
   traitement symétrique de `SELL`) est une convention documentée mais
   non vérifiée contre un règlement réel.
6. La couverture réelle des marchés football sur Polymarket (nombre,
   championnats, historique) est totalement inconnue à ce stade.

---

## 14. Conclusion Pomet vs Polymarket (étape 11)

### **B — Pomet apporte surtout une couche de présentation/filtrage, mais les données nécessaires sont accessibles directement via Polymarket.**

Justification factuelle (§5) :
- Polymarket documente et expose **nativement** un endpoint de classement
  de traders (« Get trader leaderboard rankings »), la fonctionnalité
  présentée comme le cœur du produit Pomet.
- Les primitives de données indispensables à une future analyse (wallet,
  trades individuels, prix, taille, timestamps, résolution de marché)
  sont, sur la base de la documentation publique convergente, accessibles
  **directement et sans authentification** via la Data API et la Gamma
  API de Polymarket.
- Aucune preuve d'un export/API Pomet structuré n'a été trouvée — le
  produit semble conçu pour une consultation humaine payante et une
  livraison applicative fermée (bot/Telegram), pas pour l'intégration
  programmatique par un tiers.
- Le seul apport véritablement propre à Pomet identifié est une
  heuristique propriétaire non documentée (le « niveau de confiance »,
  comparaison de la taille d'un pari à la moyenne historique du trader)
  et un filtrage déjà mâché (catégorie sport, sélection prête à l'emploi)
  — ni l'un ni l'autre n'est une donnée brute indispensable ; les deux
  sont **reconstructibles nous-mêmes** depuis les trades bruts une fois
  ceux-ci obtenus directement de Polymarket (`traders.py` de ce
  paquet implémente déjà cette reconstruction : `EligibilityRules`,
  `compute_trader_stats_as_of`).

Cette conclusion reste conditionnée à la réserve du §2 : elle s'appuie sur
des sources secondaires convergentes, pas sur une vérification primaire.
Un futur audit avec accès réseau réel pourrait la nuancer si la Data API
Polymarket se révélait, en pratique, plus limitée que documenté
(pagination, rate-limiting, couverture historique).

---

## 15. Ce qui serait nécessaire avant une future expérience

1. Lever le blocage réseau (§2) ou obtenir manuellement quelques réponses
   JSON réelles de la Gamma API et de la Data API.
2. Identifier manuellement quelques marchés football réels sur Polymarket
   pour observer le format exact des titres et construire, avec preuve à
   l'appui (même méthode que Phase K/ClubElo), un parseur de titre puis
   `CANONICAL_TEAM_ALIASES`.
3. Vérifier la couverture historique réelle (nombre de marchés football,
   championnats couverts, profondeur temporelle) avant d'envisager
   sérieusement une expérience — un historique trop faible rendrait
   `eligible_traders_as_of` inexploitable indépendamment de tout mérite
   scientifique de l'hypothèse.
4. Vérifier le mécanisme de règlement réel (redemption, traitement des
   `SELL`) contre au moins un marché réellement résolu.
5. Rédiger, **à ce moment seulement**, un protocole d'expérience
   pré-enregistré fixant explicitement les critères d'éligibilité des
   traders (`EligibilityRules`) et toute règle de conversion
   signal→décision — jamais avant, et jamais en réutilisant les résultats
   de l'expérience pour choisir ces critères rétroactivement.

Tant que ces points ne sont pas résolus, **aucune expérience n'est
techniquement possible** au-delà de tests sur données synthétiques.
