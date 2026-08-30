# Protocole de collecte de données Polymarket — Phase N

**Objectif de ce document** : permettre à une personne disposant d'un
accès Internet normal de récupérer, à la main, exactement les fichiers
nécessaires pour débloquer l'audit de faisabilité PIT (Phase M, verdict
C) — sans qu'aucune connaissance du code ne soit requise. Ce document ne
lance aucune expérience et ne préjuge d'aucun résultat.

**Rappel des règles absolues de cette phase** (toujours en vigueur) :
aucun ROI, aucun seuil, aucune activation de `BET`, aucune modification
de `final_engine`, aucune prétention que Polymarket ou Pomet apporte un
signal. Ce document sert uniquement à rendre des données observables et
vérifiables.

---

## 0. Pourquoi ce document existe

L'environnement d'exécution de cette session (Claude) a un accès réseau
sortant bloqué vers `gamma-api.polymarket.com`, `clob.polymarket.com`,
`data-api.polymarket.com`, `docs.polymarket.com` et `pomet.com.br` —
retesté explicitement en Phase M et en Phase N (403 reproductible à
chaque tentative, politique de sortie explicite de cet environnement, pas
une panne). Ce blocage ne peut pas être contourné depuis cette session
(et ne doit pas l'être). **Une personne avec un navigateur normal, en
revanche, n'a aucune de ces restrictions.**

---

## 1. Ce qu'il faut récupérer, exactement

### 1.1 Marchés football (obligatoire)

**Où** : `https://gamma-api.polymarket.com/markets`

**Comment** (dans un navigateur, ou avec `curl`/Postman) :
```
https://gamma-api.polymarket.com/markets?tag_slug=soccer&closed=true&limit=100
```
(le paramètre exact de tag n'est pas confirmé — essayer aussi `sports`,
`football`, ou parcourir sans filtre de tag et filtrer ensuite à la main
sur le titre si le tag ne fonctionne pas comme attendu). Répéter avec
`offset=100`, `offset=200`, etc. pour paginer, jusqu'à couvrir la période
souhaitée (ex. 2024/25 et 2025/26, comme le corpus Football-Data déjà
utilisé par ce projet).

**Format à sauvegarder** : la réponse JSON brute, TELLE QUELLE, dans un
fichier `.json` — ne rien transformer, ne rien filtrer, ne rien
renommer. Un fichier par page de résultats est acceptable (ex.
`gamma_markets_page1.json`, `gamma_markets_page2.json`, ...).

**Champs à vérifier présents** (obligatoires pour ce projet) :
- un identifiant de marché stable (`id` ou équivalent)
- un titre (`question` ou équivalent)
- une date de début et de fin
- un statut de résolution (`closed`, `resolved`, ou équivalent) et,
  si résolu, l'issue gagnante
- idéalement : un identifiant d'événement (`eventId`) regroupant les
  marchés liés à un même match

**Champs facultatifs mais utiles** : tags/catégorie, slug, volume.

### 1.2 Trades (obligatoire pour au moins 2-3 marchés football résolus)

**Où** : `https://data-api.polymarket.com/trades`

**Comment** :
```
https://data-api.polymarket.com/trades?market=<market_id_reel>&limit=500
```
Remplacer `<market_id_reel>` par un identifiant obtenu en 1.1. Répéter
avec `offset` croissant si plus de 500 trades existent sur ce marché
(vérifier si l'API rejette au-delà de `offset=10000` — si oui, le
signaler explicitement, c'est une information en soi).

**Format à sauvegarder** : réponse JSON brute complète, un fichier par
marché (ex. `trades_market_<id>.json`).

**Champs à vérifier présents** :
- un timestamp par trade (obligatoire — sans timestamp exploitable,
  cette donnée est inutilisable pour ce projet)
- une adresse de wallet
- un côté (BUY/SELL) et une issue (`outcome`)
- un prix et une taille
- idéalement : un identifiant de trade stable

### 1.3 Prix historiques (obligatoire — c'est le point le plus incertain)

**Où** : `https://clob.polymarket.com/prices-history`

**Comment** :
```
https://clob.polymarket.com/prices-history?market=<token_id_reel>&interval=max&fidelity=60
```
Le paramètre `market` ici attend un **`token_id`** (identifiant de
l'issue cotée, PAS le `market_id`/`condition_id` du marché lui-même — ces
deux identifiants sont documentés comme distincts). Le `token_id` doit
normalement apparaître quelque part dans la réponse Gamma API du §1.1
(souvent sous une clé listant les tokens/outcomes du marché) — si ce
n'est pas le cas, le signaler explicitement, c'est une information
bloquante en soi.

**Test spécifique à faire, absolument, pour au moins un marché DÉJÀ
RÉSOLU** : vérifier si cette requête renvoie des points de prix, ou une
liste vide/une erreur. **Ce test à lui seul peut suffire à débloquer ou
invalider toute la suite** (voir Phase M §7 : un signalement tiers non
vérifié indique un risque d'indisponibilité des prix fins sur un marché
déjà résolu).

**Format à sauvegarder** : réponse JSON brute, un fichier par
`token_id` (ex. `prices_token_<id>.json`).

### 1.4 Positions (optionnel, pour un audit ponctuel uniquement)

**Où** : `https://data-api.polymarket.com/positions?user=<wallet>`

**Ne PAS utiliser pour reconstruire un état passé** (cet endpoint ne
renvoie que l'état courant — voir avertissement déjà présent dans
`src/sys_foot_quant/polymarket/client.py::load_data_api_positions_json`).
Utile seulement pour vérifier ponctuellement la structure d'une réponse
"positions", pas pour l'analyse historique.

### 1.5 Pomet (optionnel — seulement si vous avez un abonnement actif)

Si vous disposez d'un compte Pomet payant, ouvrez la fiche complète d'un
trader réel (historique, classement, "niveau de confiance") et :
- faites une capture d'écran intégrale, ET
- copiez-collez le texte brut de la page (comme cela a été fait pour
  ClubElo en Phase K).

**Ne cherchez PAS d'API ou d'export Pomet** — aucune preuve qu'un tel
mécanisme existe n'a été trouvée (Phases L/M). Si vous en trouvez un
réellement (documentation publique, bouton d'export visible), signalez
son existence et son URL exacte — mais ne l'utilisez pas avant validation.

---

## 2. Comment préserver les timestamps (critique)

- **Ne convertissez jamais un timestamp Unix en date locale avant de le
  sauvegarder.** Conservez la valeur brute exactement telle que l'API
  la renvoie (nombre de secondes Unix, ou chaîne ISO8601 avec son
  fuseau).
- Si vous devez copier-coller depuis une interface web (pas une réponse
  JSON brute), notez explicitement le fuseau horaire affiché par
  l'interface (souvent le fuseau local du navigateur) — une date sans
  fuseau explicite sera **rejetée** par le code de validation de ce
  projet (`imports.py`), volontairement, pour éviter une fuite
  silencieuse.
- Notez la date et l'heure exactes (UTC) auxquelles VOUS avez effectué
  chaque requête — cette information ("snapshot time") sera nécessaire
  pour vérifier qu'aucune donnée de résolution n'a été mélangée à un état
  antérieur (voir `imports.validate_market_resolution_consistency`).

---

## 3. Comment éviter la fuite d'information en collectant les données

- Ne mélangez jamais, dans un même fichier, des trades/prix
  antérieurs et postérieurs à la résolution d'un marché sans le noter
  explicitement — préférez un fichier par marché, avec le statut de
  résolution constaté au moment de la collecte inclus dans le nom de
  fichier (ex. `market_123_RESOLVED.json` vs `market_123_OPEN.json`).
- Si un marché est résolu au moment où vous le consultez, la réponse
  Gamma API contiendra déjà l'issue gagnante — c'est normal et attendu,
  ce n'est PAS une fuite en soi. La fuite se produirait seulement si
  cette information de résolution était ensuite utilisée pour représenter
  un état antérieur à la résolution elle-même — c'est précisément ce que
  `imports.validate_market_resolution_consistency` détecte et rejette.
- Ne complétez jamais manuellement un champ manquant par une valeur
  plausible ("je suppose que c'est Chelsea") — laissez le champ absent,
  le code de ce projet le traite explicitement comme tel.

---

## 4. Où déposer les fichiers dans le dépôt

Créer un répertoire **non suivi par git** (déjà exclu ou à exclure via
`.gitignore` si nécessaire — ne jamais committer un export brut
volumineux ni des données potentiellement soumises à conditions
d'utilisation tierces) :

```
research/polymarket_raw_exports/
    gamma_markets_page1.json
    gamma_markets_page2.json
    trades_market_<id>.json
    prices_token_<id>.json
    positions_<wallet>.json          (optionnel)
    pomet_trader_<wallet>_screenshot.png   (optionnel)
    pomet_trader_<wallet>_transcript.txt   (optionnel)
    COLLECTION_LOG.md                (voir §5)
```

Ne PAS déposer les fichiers directement dans `src/` ou `tests/` — ce sont
des données brutes, pas du code.

---

## 5. Journal de collecte à fournir (`COLLECTION_LOG.md`)

Pour chaque fichier déposé, noter dans un simple fichier texte :
- l'URL exacte interrogée (avec tous les paramètres) ;
- la date et l'heure UTC exactes de la requête ;
- le code de statut HTTP reçu ;
- si le marché était déjà résolu au moment de la requête (oui/non) ;
- toute anomalie constatée (réponse vide, erreur, pagination bloquée,
  champ manquant inattendu).

Ce journal est indispensable : sans lui, il est impossible de distinguer
une vraie limitation de l'API d'une erreur de manipulation.

---

## 6. Contrôles qui seront exécutés ensuite (dans une future phase)

Une fois les fichiers déposés dans `research/polymarket_raw_exports/`,
la suite consistera à :
1. Charger chaque fichier via `src/sys_foot_quant/polymarket/client.py`
   (`load_gamma_markets_json`, `load_data_api_trades_json`,
   `load_clob_prices_history_json`).
2. Valider chaque enregistrement via
   `src/sys_foot_quant/polymarket/imports.py`
   (`validate_trades_export`, `validate_price_history_export`,
   `validate_market_resolution_consistency`) — tout enregistrement
   incohérent sera rejeté avec un code de raison explicite, jamais
   silencieusement.
3. Construire, pour au moins un marché, l'exemple concret de
   reconstruction PIT demandé par la Phase M (`market_open_time`,
   `decision_time` choisi, `last_allowed_observation`,
   `market_close_time`, `resolution_time`), et vérifier avec
   `imports.classify_information_timing` qu'aucune observation
   postérieure à `decision_time` n'est classée comme disponible.
4. Tenter de peupler `matching.CANONICAL_TEAM_ALIASES` **uniquement**
   avec des paires de noms observées dans les fichiers réels déposés
   (jamais par supposition) — tout titre non résolu restera marqué
   `POLYMARKET_MATCH_UNMATCHED`/`_AMBIGUOUS`.
5. Mesurer la couverture réelle avec
   `imports.compute_coverage_report`.

**Rien de tout cela n'est fait tant que les fichiers réels ne sont pas
fournis** — conformément à la règle d'arrêt de cette phase.

---

## 7. Ce qu'il faut faire si un point bloque

| Constat | Action |
|---|---|
| L'API renvoie une erreur d'authentification pour un endpoint documenté "public" | Noter l'erreur exacte, chercher si une clé API gratuite est proposée (Polymarket documente un système de clés pour certains usages) |
| `/prices-history` renvoie une liste vide pour un marché résolu | **Ne pas contourner ni deviner un prix** - documenter ce résultat précisément (marché, token_id, paramètres exacts utilisés) - c'est en soi une réponse à la question bloquante de la Phase M |
| Aucun marché football clairement identifiable | Essayer de parcourir directement `polymarket.com/sports/soccer/games` dans un navigateur pour trouver des `market_id`/slugs réels à interroger ensuite via l'API |
| Le tag de catégorisation football ne fonctionne pas comme paramètre d'API | Récupérer les marchés sans filtre et noter les valeurs réelles du champ de catégorie observées dans la réponse |
| Pagination bloquée au-delà d'un certain `offset` | Noter le seuil exact observé, essayer un filtrage par plage de dates à la place si l'API le permet |

---

## Annexe — fonctions déjà écrites qui attendent ces données réelles

Relecture complète de `src/sys_foot_quant/polymarket/` (Phase N, étape 1)
— aucune de ces fonctions n'a été réécrite, seules deux modifications
additives ont été faites (`schemas.PricePoint`,
`client.load_clob_prices_history_json`) pour représenter les prix, absents
du schéma avant cette phase :

| Module | Fonction | Nécessite des données réelles pour... |
|---|---|---|
| `client.py` | `load_gamma_markets_json`/`_events_json`/`load_data_api_trades_json`/`_positions_json`/`load_clob_prices_history_json` | Recevoir un premier fichier JSON réel à charger - actuellement jamais appelées hors tests synthétiques |
| `markets.py` | `parse_market` | Vérifier que le mapping de clés (`id`/`question`/`startDate`...) correspond réellement à la Gamma API |
| `trades.py` | `parse_trade` | Idem pour la Data API (`proxyWallet`/`market`/`timestamp`...) |
| `imports.py` | `parse_price_point` | Idem pour la CLOB API (`t`/`p`) - **jamais exercé sur un payload réel** |
| `imports.py` | `validate_market_resolution_consistency` | Vérifier sur un marché réellement résolu que `resolution_time` est bien renseigné et cohérent |
| `matching.py` | `resolve_canonical_team_name`/`match_market_to_football_data` | **Bloquée tant que `CANONICAL_TEAM_ALIASES` reste vide** - nécessite des titres de marché réels observés (§1.1) |
| `traders.py` | `compute_trader_stats_as_of` | Vérifier le mécanisme de règlement réel (redemption 1$/0$) contre au moins un marché résolu réel |
| `imports.py` | `compute_coverage_report` | Nécessite un ensemble de marchés réels pour produire un chiffre non trivial |

Toutes les autres fonctions (`positions.derive_positions_as_of`,
`pit.get_trader_information_as_of`, `traders.eligible_traders_as_of`,
`imports.classify_information_timing`/`validate_trades_export`/
`validate_premarket_trades_bundle`/`validate_price_history_export`) sont
des primitives de logique pure, déjà testées de façon exhaustive sur
données synthétiques (Phases L/N) - leur correction algorithmique ne
dépend pas de données réelles, seule leur PERTINENCE sur le monde réel
(la forme exacte des données Polymarket) reste à démontrer.

## 8. Résumé en une phrase

**Récupérez, pour 3 à 5 marchés football réellement résolus : leur fiche
Gamma complète, tous leurs trades via la Data API, et l'historique de
prix de leurs tokens via la CLOB API — sauvegardez chaque réponse JSON
brute sans transformation, avec un journal des requêtes effectuées, et
déposez le tout dans `research/polymarket_raw_exports/`.**
