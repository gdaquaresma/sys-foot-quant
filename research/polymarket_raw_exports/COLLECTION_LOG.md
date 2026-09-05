# Journal de collecte — Phase N (récupération d'urgence)

**Avertissement sur la provenance de ce journal** : ces deux fichiers
n'ont PAS été déposés normalement par l'utilisateur dans ce répertoire.
Ils ont été collés directement dans la conversation (session
`5c09f8b0-bf58-5a13-a017-839ef6d6a8da`), la requête a échoué
(`Prompt is too long`), puis le contexte a été compacté sans que ce
message soit traité. Les deux payloads ont été récupérés a posteriori en
relisant le transcript brut de la session
(`~/.claude/projects/.../5c09f8b0-....jsonl`, message utilisateur horodaté
`2026-08-31T14:57:46.904Z`) et sauvegardés ici tels quels. **Aucune URL
exacte ni heure UTC précise de la requête HTTP originale n'est
disponible** — seule l'heure d'arrivée du message dans la session
(`2026-08-31T14:57:46Z`) est connue, à traiter comme une approximation de
la "snapshot time".

## Fichier 1 — `league_events_paste1.json`

- **Origine déclarée par l'utilisateur** : onglet Réseau du navigateur,
  requête nommée `league-events?seriesId=1018...` (endpoint frontend
  Polymarket, PAS l'endpoint documenté `gamma-api.polymarket.com/markets`
  du protocole §1.1 — structure différente, voir constat ci-dessous).
- **Code HTTP** : inconnu (non capturé).
- **Contenu** : 20 événements Premier League (EPL) à venir, chacun avec
  ses marchés liés (1713 marchés au total), les deux équipes nommées
  explicitement (`event.teams`, `event.resolvedTeams` avec labels
  `home`/`away`), et par marché : `id`, `question`, `conditionId`,
  `slug`, `startDate`, `endDate`, `outcomes`, `outcomePrices`,
  `clobTokenIds`, `closed`, `active`.
- **Marché déjà résolu au moment de la collecte ?** NON — les 20
  événements et les 1713 marchés ont tous `closed: false`. Ce fichier ne
  permet donc PAS de tester `validate_market_resolution_consistency` sur
  un cas réel, ni de vérifier le format du champ de résolution
  (`resolvedDate`/`closedTime` attendus par `markets.py` — le champ
  observé ici est `closed_time` en snake_case, absent tant qu'aucun
  marché n'est résolu, donc pas encore comparable).
- **Anomalie constatée** : structure de haut niveau très différente de
  celle attendue par `client.load_gamma_markets_json` (qui exige une
  racine `list`) — ici la racine est un `dict` avec les clés `events`,
  `teams`, `games`, `sections`, `gameIdToSlug`,
  `parentToChildEventIds`, `summary`, `marketsSections`,
  `marketsSectionsState`. Chaque `event["markets"]` est en revanche une
  `list` de dicts dont les clés individuelles (`id`, `question`,
  `startDate`, `endDate`, `clobTokenIds`, ...) correspondent bien aux
  clés déjà tolérées par `markets.parse_market`.

## Fichier 2 — `books_paste1.json`

- **Origine déclarée par l'utilisateur** : requête `books?token_ids=...`
  (carnet d'ordres CLOB courant — PAS l'historique `/prices-history` du
  protocole §1.3, qui reste non testé).
- **Code HTTP** : inconnu (non capturé).
- **Contenu** : 26 carnets d'ordres (`bids`/`asks` par palier de prix),
  un par `asset_id`. Chaque `asset_id` correspond exactement à un
  `clobTokenIds` du fichier 1 (26/26 recoupés avec succès) — confirme le
  lien `event → market → token → book`.
- **Horodatage** : `timestamp` en millisecondes Unix (ex.
  `1788187675814` → `2026-08-31T14:47:55Z`), cohérent avec l'heure
  d'arrivée du message ci-dessus.
- **Limite critique** : c'est un instantané du carnet d'ordres COURANT
  pour des marchés encore ouverts, pas une série temporelle historique.
  Le test bloquant du protocole §1.3 (existe-t-il un historique de prix
  sur un marché DÉJÀ RÉSOLU ?) reste donc entièrement non répondu par ces
  données.

## Fichier 3 — `prices_history_westham_leeds_1.json`

- **Origine déclarée par l'utilisateur** : onglet Réseau, requête
  `prices-history?startTs=17796...`, capturée sur la page du match
  **West Ham United FC vs Leeds United FC** (`epl-wes-lee-2026-05-24`),
  déjà résolu au moment de la capture (score final 3-0, issue affichée
  "Yes — West Ham United FC").
- **Code HTTP** : inconnu (non capturé, mais réponse JSON valide reçue).
- **Contenu** : `{"history": [...]}`, 250 points `{t, p}` — `t` en
  secondes Unix, de `1779634806` à `1779649743` ; `p` (probabilité
  implicite) évolue de 0.575 → creux ~0.335 → hausse nette jusqu'à 0.9995,
  cohérent avec une victoire 3-0 de West Ham.
- **Résultat critique** : **répond OUI à la question la plus incertaine du
  protocole (§1.3)** — `clob.polymarket.com/prices-history` retourne bien
  un historique de prix exploitable pour un marché **déjà résolu**, pas
  seulement pour un marché ouvert. C'est la première confirmation réelle
  (non synthétique) de ce point.
- **Validation exécutée** : `imports.validate_price_history_export(points,
  market_id='westham_leeds_moneyline_placeholder',
  source='manual_devtools_paste')` → `n_accepted=250, n_rejected=0`.
  Première exécution de cette fonction sur des données réelles (jusque-là
  testée uniquement en synthétique).

## Fichiers 3b/3c — `prices_history_westham_leeds_2.json` et `_3.json`

- Mêmes conditions de capture que le fichier 3 (page West Ham/Leeds,
  déjà résolue), mais pour les 2 autres `market=` observés dans le
  filtre `clob` de DevTools (`110545...` et `809604...` — probablement
  Nul et Leeds, sans certitude sur l'assignation exacte car l'URL
  complète n'a pas été capturée, seul le corps JSON).
- **Fichier 2** : 249 points, `p` passe de ~0.205-0.285 (plateau) à
  0.0005, cohérent avec une issue perdante.
- **Fichier 3** : 249 points, `p` passe de ~0.225-0.425 (plateau, monte
  un peu avant l'effondrement) à 0.0005, cohérent avec une issue
  perdante également.
- **Validation** : `validate_price_history_export` → 249/249 acceptés
  pour chacun des deux fichiers, 0 rejet.
- **Vérification croisée d'intégrité** : à un instant `t` donné commun
  aux 3 fichiers, la somme des 3 prix ≈ 1.00 (1.005 au premier point
  commun, 1.0005 au dernier) — cohérent avec un marché 3 voies
  (West Ham / Nul / Leeds) correctement échantillonné aux mêmes
  timestamps par le CLOB. Bonne confirmation indépendante de
  l'intégrité des 3 séries récupérées séparément.
- **Limite** : on ne sait pas avec certitude laquelle des deux séries
  (2 ou 3) correspond à "Nul" et laquelle à "Leeds" — l'URL complète
  (`market=...`) n'a pas été conservée avec le corps de la réponse.
  Sans conséquence pour tester `validate_price_history_export`, mais à
  clarifier avant tout usage applicatif (matching token_id → outcome).

## Fichier 4 — `keyset_parent_event_868900.json`

- **Origine déclarée par l'utilisateur** : requête
  `keyset?parent_event_id=868900`, capturée depuis la même session de
  navigation que le fichier 3, mais **PAS depuis la page West Ham/Leeds**
  — `parent_event_id=868900` correspond en réalité à l'événement
  `epl-ast-ars-2026-08-31` (Aston Villa FC vs Arsenal FC).
- **Schéma** : `"$schema":
  "https://gamma-api.polymarket.com/schemas/EventsKeysetListResponse.json"`
  — c'est le vrai endpoint Gamma API documenté (racine `{"events": [...]}`),
  contrairement au fichier 1 (`league-events`, endpoint frontend interne).
- **Contenu** : 22 événements, tous `closed: false` au niveau événement —
  **aucun n'est le match West Ham/Leeds recherché**. Ce sont des
  événements "frères"/liés : EPL Aston Villa-Arsenal (+ ses sous-marchés
  mi-temps/score exact/corners/props), La Liga Barcelone-Rayo Vallecano
  (idem), tennis US Open (WTA Navarro-Boisson, ATP Tirante-Mannarino,
  ATP Landaluce-Fearnley), et un match CS2 (G2 vs Aurora Gaming).
- **Constat important malgré tout** : bien que les *événements* soient
  `closed: false`, plusieurs *marchés individuels* à l'intérieur (sets de
  tennis déjà joués, maps CS2 déjà jouées) sont réellement résolus :
  `closed: true`, `umaResolutionStatus: "resolved"`,
  `outcomePrices: ["1","0"]` ou `["0","1"]`, et surtout un champ
  `closedTime` (camelCase, ex. `"2026-08-31 00:05:04+00"`) — cette clé
  correspond exactement à une des clés déjà tolérées par
  `markets._RESOLUTION_KEYS`.
- **Test exécuté contre le code existant (non modifié)** :
  `markets.parse_market(raw, source='keyset_devtools_paste')` sur le
  marché résolu "Set 1 Winner: Navarro vs Boisson" →
  `resolution_time` correctement parsé à partir de `closedTime`
  (`2026-08-31T00:05:04+00:00`). **Première confirmation réelle que le
  parsing de la date de résolution de `markets.py` fonctionne sur une
  donnée authentique.**
- **Lacune constatée (non corrigée, à valider avec l'utilisateur avant tout
  changement de code)** : `parse_market` ne peuple jamais `market.outcome`
  (aucune clé `_OUTCOME_KEYS` n'existe, `outcomePrices` n'est pas lu) — en
  conséquence `imports.validate_market_resolution_consistency` reçoit
  toujours `market.outcome is None` et retourne systématiquement `None`
  (aucune incohérence ne peut jamais être détectée) pour tout `Market`
  construit via `parse_market` en l'état actuel. Ce n'est pas un bug de ce
  fichier de données, mais un angle mort du code de production identifié
  grâce à cette première donnée réelle.
- **Ne répond PAS** à la question "métadonnées de résolution du match
  West Ham/Leeds lui-même" — le `keyset` récupéré est pour le mauvais
  `parent_event_id`. Il faudrait relancer la capture depuis la page
  West Ham/Leeds elle-même (ou trouver son propre `parent_event_id`) pour
  obtenir sa fiche Gamma complète.

## Fichier 5 — `keyset_parent_event_481717_fed_decision.json`

- **Origine déclarée par l'utilisateur** : "keyset" envoyé en pensant qu'il
  s'agissait du match West Ham/Leeds — en réalité mauvais
  `parent_event_id` de nouveau (message reçu `2026-08-31T15:48:35Z`,
  session `5c09f8b0-...`, récupéré depuis le transcript brut car trop
  volumineux pour rester dans le contexte compacté).
- **Code HTTP** : inconnu (non capturé).
- **Contenu** : même schéma `EventsKeysetListResponse.json` que le fichier
  4, mais `parent_event_id=481717` correspond à l'événement racine
  `fed-decision-in-september-762` — 20 événements listés, tous de
  géopolitique/élections/actualité US (Iran, Brésil, France, Elon Musk
  tweets, etc.), **aucun événement sportif, aucun lien avec
  West Ham/Leeds**. Vérifié par recherche exhaustive de "west ham",
  "leeds", "wes-lee" dans le texte brut → 0 occurrence.
- **Conclusion** : ce fichier ne répond à aucune question ouverte de la
  Phase N. Conservé uniquement par souci de complétude du journal — ne
  pas le confondre avec le fichier 4 (qui, lui, est bien sportif mais
  pour le mauvais match Aston Villa/Arsenal).
- **Point métier à retenir** : deux tentatives de suite ont capturé le
  mauvais `parent_event_id` pour le match West Ham/Leeds. Cela suggère
  que la valeur `parent_event_id` utilisée dans DevTools n'est probablement
  pas filtrée sur la bonne requête réseau (le filtre `keyset` seul ne
  suffit pas à isoler la bonne ligne — il y a apparemment plusieurs
  requêtes `keyset?parent_event_id=...` différentes chargées sur/around
  la page, une par section de la page d'accueil ou du carrousel, pas
  spécifiquement liée à la page du match consultée).

## Fichier 6 — `market_2227393_westham_leeds_moneyline.json`

- **Origine** : requête GET directe faite par l'utilisateur dans son
  navigateur vers `https://gamma-api.polymarket.com/markets/2227393`
  (endpoint public, sans authentification) — `market_id=2227393` repéré
  via le réseau DevTools filtré sur `gamma`, requête
  `market-clarifications?market_id=2227393` observée 4 fois sur la page
  du match West Ham/Leeds (piste bien plus directe que le `keyset`, qui
  s'est avéré ne renvoyer que des carrousels sans rapport avec la page
  consultée — 2 tentatives infructueuses avec `parent_event_id`
  auparavant, voir fichiers 4 et 5).
- **Code HTTP** : 200 confirmé (vu directement dans l'onglet, réponse
  JSON valide reçue).
- **Contenu** : c'est **la fiche Gamma réelle du marché "Will West Ham
  United FC win on 2026-05-24?"** (`slug`:
  `epl-wes-lee-2026-05-24-wes`, un des 3 marchés binaires probables du
  match — suffixe `-wes`, sans doute `-draw` et `-lee` pour les 2
  autres, non encore récupérés). `closed: true`,
  `umaResolutionStatus: "resolved"`, `outcomes: ["Yes","No"]`,
  `outcomePrices: ["1","0"]` (résolu "Yes" = West Ham gagne — cohérent
  avec le score final 3-0 connu), `closedTime: "2026-05-24
  19:09:16+00"` (même format espace + offset court `+00` que le fichier
  4), `clobTokenIds`: 2 tokens (`110545219743...054` pour Yes,
  `214756143346...591` pour No).
- **Test exécuté contre le code existant (non modifié)** :
  `markets.parse_market(raw, source='gamma_devtools_paste_2227393')` →
  `resolution_time` correctement parsé
  (`2026-05-24T19:09:16+00:00`, format espace+offset-court donc bien
  toléré par `datetime.fromisoformat`), `start_time`/`end_time`
  également corrects. `market.outcome` reste **`None`** — confirme une
  seconde fois, cette fois sur la fiche du match cible lui-même (pas un
  marché tiers comme au fichier 4), le gap déjà identifié :
  `parse_market` ne lit jamais `outcomePrices`. En conséquence
  `imports.validate_market_resolution_consistency(m,
  claimed_snapshot_time=...)` retourne `None` (aucune incohérence
  détectable) alors même qu'on sait, de façon indépendante, que ce
  marché est bien résolu "Yes" — ce cas concret illustre bien l'angle
  mort : la fonction ne peut jamais servir à detecter une vraie fuite de
  résolution tant que `outcome` n'est pas peuplé.
- **Lien avec les fichiers 3/3b/3c (historiques de prix)** : incertain à
  ce stade. Le token `110545219743...054` (Yes) de ce marché *pourrait*
  correspondre au `market=110545...` tronqué mentionné dans le journal
  pour le fichier 3b (`_2.json`, série qui BAISSE vers 0.0005) — mais
  c'est contradictoire avec le sens attendu (Yes/West Ham a gagné, donc
  sa série devrait monter, pas descendre comme fichier 3b). Coïncidence
  de préfixe probable plutôt qu'un vrai match, non confirmée. Ne pas
  assigner de token_id aux fichiers 3/3b/3c sur cette seule base.
- **Répond PARTIELLEMENT** au point 1 de la liste "ce qui manque" :
  c'est bien la fiche Gamma du match visé, mais seulement pour LE
  marché "Will West Ham win", pas encore pour les marchés "Nul" et
  "Will Leeds win" du même match (nécessaires pour désambiguïser
  définitivement les fichiers 3b/3c).

## Fichier 7 — `event_472535_westham_leeds_full.json`

- **Origine** : requête GET directe de l'utilisateur vers
  `https://gamma-api.polymarket.com/events?slug=epl-wes-lee-2026-05-24`
  (endpoint événement, public, sans authentification). Réponse racine =
  `list` d'1 élément (l'événement `id=472535`), directement compatible
  avec la forme attendue par `client.load_gamma_markets_json` une fois
  qu'on extrait `event["markets"]` (liste de 3 dicts) — même remarque
  structurelle que pour le fichier 1 (`league-events`), mais ici c'est le
  **vrai** endpoint Gamma documenté, pas le endpoint frontend interne.
- **Code HTTP** : 200 confirmé.
- **Contenu** : la fiche complète de l'événement `West Ham United FC vs.
  Leeds United FC` (`closed: true`, `score: "3-0"`, `ended: true`,
  `finishedTimestamp`), avec ses **3 marchés binaires** :
  - `2227393` "Will West Ham United FC win" → `outcomePrices: ["1","0"]`
    (résolu Yes), `clobTokenIds`: Yes=`110545219743...054`,
    No=`21475614334...591`, `lastTradePrice: 0.999`.
  - `2227394` "Will ... end in a draw" → `outcomePrices: ["0","1"]`
    (résolu No), `clobTokenIds`: Yes=`80960470251...322`,
    No=`10565294138...724`, `lastTradePrice: 0.001`.
  - `2227397` "Will Leeds United FC win" → `outcomePrices: ["0","1"]`
    (résolu No), `clobTokenIds`: Yes=`99006346120...957`,
    No=`54622509811...182`, `lastTradePrice: 0.001`.
  - Équipes, ligue, contexte narratif (`eventMetadata`), tags, série
    (`premier-league-2025`) également présents.
- **Correction d'une hypothèse précédente** : le fichier 6 (marché
  `2227393` seul) notait une possible coïncidence de préfixe entre le
  token Yes de `2227393` (`110545...`) et un `market=110545...` tronqué
  mentionné pour le fichier 3b (`_2.json`, série descendante) — jugée
  contradictoire (Yes de West Ham a gagné, donc devrait monter, pas
  descendre). Avec les 3 marchés maintenant identifiés, cette
  contradiction est confirmée : `110545...054` est bel et bien le token
  Yes de West Ham (déjà utilisé par le fichier 1, qui monte à 0.9995 —
  cohérent avec `lastTradePrice: 0.999` de `2227393`, excellente
  confirmation croisée indépendante). Le `market=110545...` noté à
  l'origine pour le fichier 3b était donc très probablement une erreur
  d'attribution lors de la capture d'urgence (mémoire/annotation
  incorrecte), pas une vraie coïncidence de token. **Conclusion révisée** :
  fichier 1 = West Ham Yes (confirmé, sans ambiguïté).
  Fichiers 2 et 3 = Nul-Yes (`80960470...322`) et Leeds-Yes
  (`99006346...957`) dans un ordre encore **non confirmé** avec
  certitude absolue (les tokens tronqués notés à l'origine ne sont pas
  fiables) — mais sans conséquence pratique : les deux marchés ont
  résolu "No" (`lastTradePrice: 0.001` chacun), et les deux fichiers
  convergent vers 0.0005, cohérent avec les deux dans tous les cas. Pour
  lever l'ambiguïté définitivement il faudrait re-capturer les
  `prices-history` avec l'URL complète (`asset_id=...`) conservée cette
  fois, mais ce n'est plus nécessaire pour répondre aux questions du
  protocole.
- **Test exécuté contre le code existant (non modifié)** :
  `markets.parse_markets(event['markets'],
  source='gamma_devtools_paste_event_472535')` → les 3 marchés sont
  correctement parsés (`resolution_time` peuplé pour chacun,
  `19:09:16Z`/`19:09:33Z`/`19:08:22Z`), puis
  `imports.validate_market_resolution_consistency(m,
  claimed_snapshot_time=...)` → `None` pour les 3 (aucune incohérence
  détectée) — **troisième confirmation** du même gap
  (`market.outcome` jamais peuplé par `parse_market`), cette fois sur
  l'intégralité des 3 marchés du match cible avec vérité terrain connue
  de façon indépendante (score 3-0, `event.score == "3-0"`).
- **Répond COMPLÈTEMENT** au point 1 de la liste "ce qui manque" :
  fiche Gamma complète du match West Ham/Leeds obtenue, avec ses 3
  marchés, leurs `closedTime`, `outcomePrices` et `clobTokenIds`.

## Correction du gap `market.outcome` (`markets.py`)

Suite aux 3 confirmations ci-dessus (fichiers 4, 6, 7) que
`parse_market` ne peuplait jamais `market.outcome`, le gap a été corrigé
dans `src/sys_foot_quant/polymarket/markets.py` :

- Ajout de `_OUTCOME_KEYS` (clés directes alternatives : `outcome`,
  `resolved_outcome`, `winning_outcome`).
- Ajout de `_resolve_outcome_from_prices(raw)` : décode
  `outcomes`/`outcomePrices` (formes liste native ou chaîne JSON, comme
  observé sur la vraie Gamma API) et retourne le libellé dont le prix
  vaut exactement `1.0` — un marché encore ouvert n'a jamais de prix
  exactement à 1.0, donc aucun risque de confondre une forte probabilité
  avec une résolution. Retourne `None` si les champs sont absents,
  malformés, de longueurs incohérentes, ou si aucun/plusieurs libellés
  ont un prix de 1.0.
- `parse_market` utilise d'abord une clé directe, puis ce fallback.
- 7 nouveaux tests unitaires (`test_polymarket_markets.py`), suite
  polymarket (36 tests) et suite complète relancées, aucune régression.
- **Revalidé sur la vraie donnée récupérée** (fichier 7,
  `event_472535_westham_leeds_full.json`) : les 3 marchés du match
  portent maintenant `outcome` = `"Yes"`/`"No"`/`"No"` (cohérent avec le
  score 3-0). `validate_market_resolution_consistency` détecte
  désormais correctement l'incohérence si on lui fait croire à un
  `claimed_snapshot_time` antérieur au match (`IMPORT_REJECT_RESOLUTION_BEFORE_ITS_TIME`)
  et renvoie `None` si le snapshot est bien postérieur à la résolution —
  la fonction est enfin opérante sur donnée réelle, ce qu'elle ne
  pouvait jamais faire auparavant.

## Ce qui manque encore pour compléter la Phase N

1. ~~La fiche Gamma complète du match West Ham/Leeds lui-même~~ —
   **FAIT** (fichier 7, `events?slug=epl-wes-lee-2026-05-24`) : les 3
   marchés (West Ham/Nul/Leeds), leurs `closedTime`, `outcomePrices` et
   `clobTokenIds` sont obtenus.
2. Les trades de ce marché résolu (`data-api.polymarket.com/trades`) —
   toujours non capturés. On dispose maintenant des `conditionId` des 3
   marchés pour tenter la requête (ex.
   `?market=0xee512df0318ec5405f477a02ac1bd4b2d824aa2338a87e046d90cc4872f64599`
   pour le marché "Will West Ham win").
3. ~~L'historique de prix de ses tokens~~ — **FAIT** (fichier 3, voir
   ci-dessus) : le point le plus critique du protocole est résolu.
4. Éventuellement les `prices-history` restants visibles dans DevTools
   (jusqu'à 5 autres lignes) pour couvrir les autres marchés du même
   match (ex. score exact, over/under) et non uniquement le moneyline —
   non prioritaire.
5. (Mineur, non bloquant) Confirmer avec certitude laquelle des séries
   `prices_history_westham_leeds_2.json` / `_3.json` correspond au token
   Nul-Yes (`80960470...322`) vs Leeds-Yes (`99006346...957`) — nécessite
   une nouvelle capture avec l'URL complète (`asset_id=...`) conservée.

## Phase O — Sélection neutre des marchés (Étape 1)

**Contrainte méthodologique explicite de l'utilisateur** : *« Ne cherche
PAS les marchés en fonction des traders »* — la sélection des marchés du
futur univers de recherche doit se faire indépendamment de tout wallet
déjà connu (notamment `suntori`, tracé en Phase précédente), pour éviter
un biais de sélection.

### Fichier 8 — `events_neutral_soccer_tagslug_closed_2026-09-01.json`

- **Origine déclarée par l'utilisateur** : requête proposée
  `https://gamma-api.polymarket.com/events?tag_slug=soccer&closed=true&limit=40&order=startDate&ascending=false`
  (filtre neutre — sport + statut + tri chronologique uniquement, aucun
  wallet/trader en entrée).
- **Récupération** : ce message (reçu `2026-09-01T17:52:44.992Z`, session
  `5c09f8b0-...`) a été collé après un précédent envoi trop volumineux
  (`Prompt is too long`, cf. avertissement en tête de ce journal), puis le
  contexte a été compacté avant traitement. Payload récupéré a posteriori
  depuis le transcript brut de la session (ligne 18994 du fichier
  `.jsonl`) et sauvegardé ici tel quel — même mode opératoire que pour
  les fichiers 1/2 en Phase N.
- **Code HTTP** : inconnu (non capturé), réponse JSON valide et complète
  reçue (vérifié : la chaîne se termine proprement par `}]` suivi de la
  balise de fermeture du bloc code, pas de troncature).
- **Contenu** : racine = `list` de **40 événements** (endpoint Gamma
  documenté, structure `event.markets[]` imbriquée — compatible avec
  `markets.parse_markets`), totalisant **418 marchés imbriqués**, tous
  `closed: true` / `umaResolutionStatus: "resolved"` au niveau des
  marchés racine (moneyline). Ils couvrent **7 matchs distincts** dans
  **4 ligues** :
  - China FA Cup (`chfa`) : Lanzhou Longyuan Athletic vs. Beijing Guoan
    (`chfa-lan-bjg-2026-09-01`, résolu "Beijing Guoan"), Dalian Yingbo FC
    vs. Shanghai Shenhua FC (`chfa-dy-shs-2026-09-01`, résolu "Dalian
    Yingbo FC").
  - Georgia Erovnuli Liga (`geo1`) : FC Torpedo Kutaisi vs. FC Meshakhte
    Tkibuli, FC Gagra vs. FC Iberia 1999, FC Dinamo Tbilisi vs. FC Dila
    Gori (3 matchs, `geo1-*-2026-08-31`).
  - Latvia Virslīga (`lva1`) : FK Liepaja vs. Riga FC
    (`lva1-lie-rfc-2026-08-31`).
  - Azerbaijan Premier League (`aze1`) : Sumqayit FK vs. Qarabag FK
    (`aze1-sum-qar-2026-08-31`, seul match avec un marché
    `total-corners` en plus de la famille standard).
  - Chaque match a une famille de marchés similaire : moneyline (3
    marchés binaires "Team A win"/"draw"/"Team B win"), score exact,
    mi-temps, 2e mi-temps, premier buteur, et un événement
    `-more-markets` (spreads/totals/BTTS agrégés).
- **Divulgation de transparence (contrainte trader)** : le match `Dalian
  Yingbo FC vs. Shanghai Shenhua FC` (`chfa-dy-shs-2026-09-01`) recoupe un
  marché déjà aperçu incidemment dans l'historique de trades du wallet
  `suntori` (Phase précédente). Ce recoupement n'est **pas** le résultat
  d'une sélection biaisée : le match provient d'une requête neutre
  (filtrée uniquement par sport/statut/date), et n'a pas été
  délibérément choisi parce qu'il était connu via `suntori`. Il est
  néanmoins consigné ici pour transparence totale, conformément à la
  contrainte de l'utilisateur — à garder à l'esprit si ce match est
  conservé dans l'univers final (ex. exclusion possible par prudence, à
  trancher avec l'utilisateur).
- **Vers la cible ~20 marchés** : 7 matchs neutres identifiés à ce stade
  (bien au-delà des 6 mentionnés lors de la demande initiale — le match
  Lanzhou/Beijing, découpé en 3 marchés moneyline, était inclus dans le
  même payload). En comptant uniquement les marchés moneyline simples
  (1 par équipe + 1 nul = 3 par match), les 7 matchs fournissent déjà 21
  marchés binaires simples ; en incluant score exact/mi-temps/etc., 418
  marchés bruts sont disponibles. Suffisant pour couvrir la cible ~20 en
  priorisant moneyline — pas besoin de requête neutre supplémentaire pour
  l'instant, sauf si l'utilisateur souhaite plus de diversité
  géographique/temporelle.
- **Non fait à ce stade** : sélection finale des ~20 marchés (à choisir
  parmi les 418 disponibles), récupération des trades par marché, et
  découverte des wallets actifs sur ces marchés — prochaines étapes de la
  Phase O.

### Validation utilisateur (2026-09-01)

Univers validé tel quel par l'utilisateur : les 7 matchs résolus
constituent l'univers de départ. Décision explicite sur
`chfa-dy-shs-2026-09-01` (overlap `suntori`) : **conservé**, mais marqué
`suntori_overlap: true` dans les métadonnées pour permettre une analyse de
sensibilité avec/sans ce match plus tard.

### Fichier 9 — `moneyline_21_markets_metadata.json`

Extraction locale (Python, pas de nouvel appel réseau) des 3 marchés
moneyline binaires (`sportsMarketType: "moneyline"`) de chacun des 7
matchs, à partir du Fichier 8. 21 marchés au total. Pour chacun :
`gamma_market_id` (`id`), `conditionId`, `question`, `slug`, `outcomes`,
`outcomePrices`, `token_ids` (`clobTokenIds`), `resolved_outcome` (déduit
des `outcomePrices`, un seul label à prix exactement 1.0 par marché —
vérifié : aucune anomalie, chaque match a exactement un gagnant sur ses 3
marchés), `resolution_time_closedTime` (champ `closedTime`, format
`"YYYY-MM-DD HH:MM:SS+00"` — compatible avec le parseur existant
`markets._parse_datetime` via la clé `_RESOLUTION_KEYS`, testé), et
`suntori_overlap` (booléen, `true` uniquement pour les 3 marchés du match
Dalian Yingbo FC vs. Shanghai Shenhua FC).

### Étape suivante — collecte des trades (en cours)

Pour chacun des 21 `conditionId`, requête
`data-api.polymarket.com/trades?market=<conditionId>&limit=1000&offset=0`
à faire fetcher par l'utilisateur (pas d'accès réseau direct — confirmé à
nouveau ce tour : `curl` vers `data-api.polymarket.com` rejeté par la
politique réseau de l'environnement, `CONNECT tunnel failed, 403`),
pagination par `offset` tant que la page retournée est pleine (1000
éléments). Payloads bruts à sauvegarder un par un dans ce répertoire au
fur et à mesure de leur réception.

### Fichier 10 — `trades_market_aze1-sum-qar_qar-win_0x59fdb4ab_offset0.json`

Marché "Will Qarabag FK win on 2026-08-31?" (`conditionId`
`0x59fdb4ab41e61027326bf6b285a95b2f4a22df8c89efcfc3ed3dc3d1a9862a27`), 1/21.
Premier fetch signalé vide par l'utilisateur malgré un volume CLOB réel
(`volumeClob=11928.99`) — retenté avec succès (69 trades reçus,
`offset=0`, page incomplète donc pas de pagination supplémentaire
nécessaire). Cause de l'échec initial non déterminée (probable aléa
côté client de l'utilisateur), pas une anomalie du marché lui-même.

QC (via `sys_foot_quant.polymarket.trades.parse_trades` /
`deduplicate_trades`, code source non modifié) :
- 69 trades bruts, 69 après dédup par `transactionHash` (aucun doublon).
- 22 wallets uniques.
- Période : 2026-08-30 20:26:33 UTC → 2026-08-31 18:13:19 UTC.
- 61 BUY / 8 SELL.
- Jointure token/outcome cohérente : `asset`
  `371075637911...4624344` toujours vu avec `outcome="Yes"` (=
  `token_ids[0]` des métadonnées), `874803071002...0221320` toujours vu
  avec `outcome="No"` (= `token_ids[1]`) — aucune anomalie.
- Aucun trade postérieur à `resolution_time_closedTime`
  (2026-08-31 20:08:01 UTC) : dernier trade à 18:13:19, avant résolution.
  Premier trade à 20:26:33, 2 min après `startDate` (20:24:11) —
  cohérent avec l'ouverture du marché au coup d'envoi.

### Fichier 11 — `trades_market_chfa-lan-bjg_lan-win_0xfa748d54_offset0.json`

Marché "Will Lanzhou Longyuan Athletic win on 2026-09-01?" (`conditionId`
`0xfa748d5447c3f94afa243e60700b93c61cf5579642e83f7b433c456db75d85d1`),
2/21. 121 trades reçus à `offset=0` (< 1000, pas de pagination requise).

QC : 121 bruts = 121 après dédup (aucun doublon) ; 56 wallets uniques ;
97 BUY / 24 SELL ; période 2026-09-01 01:05:43 → 16:36:49 UTC, tous
avant `resolution_time_closedTime` (17:32:21 UTC) — 0 trade
post-résolution ; jointure `asset↔outcome↔token_ids` cohérente (`token
487596700645270...`→"Yes"=`token_ids[0]`, `token
853691939625268...`→"No"=`token_ids[1]`) ; `resolved_outcome`="No"
confirmé côté métadonnées. Premier trade ~9h après `startDate`
(16:07:12) — faible activité initiale, pas une anomalie.

**Découverte méthodologique à signaler** : le wallet `suntori` (déjà
connu via son historique de trades tracé en Phase précédente) apparaît
**4 fois** dans ce marché — alors que ce match n'était PAS celui identifié
comme `suntori_overlap` dans les métadonnées (seul
`chfa-dy-shs-2026-09-01` l'était, sur la base d'un souvenir partiel de la
Phase précédente). Cela indique que le flag `suntori_overlap` des
métadonnées, basé sur un rappel incomplet, est **insuffisant** : `suntori`
trade en réalité sur plusieurs marchés de cet univers neutre. À partir de
maintenant, la détection se fait sur les DONNÉES réelles reçues (colonne
`name`/`proxyWallet` des trades), pas sur un souvenir a priori. Ceci reste
compatible avec la contrainte "ne pas sélectionner via un trader" : les
marchés ont été choisis avant tout examen des trades, et cette présence
est constatée a posteriori, pas causale de la sélection.

### Fichier 12 — `trades_market_chfa-lan-bjg_draw_0x69bcfe7e_offset0.json`

Marché "draw" du même match (`0x69bcfe7e568dc2a0ffa97b17e54b794d1a117595266c5c4242a0ce6462f8f169`),
3/21. 66 trades bruts = 66 après dédup, 47 wallets, 57 BUY / 9 SELL,
période 2026-08-31 17:18:22 → 2026-09-01 15:38:57 UTC, résolution
17:31:49 UTC — 0 trade post-résolution. Jointure token/outcome
cohérente. `suntori` présent 1 fois de plus.

### Fichier 13 — `trades_market_chfa-lan-bjg_bjg-win_0xf69fbd42_offset0.json`

Marché "Beijing Guoan win" (`0xf69fbd421e5210288aa592b02c072a4f68a6822a385421e1939fb51df695d509`),
4/21 — **résolu Yes** (seul marché "win" gagnant du match). **Incident
de collecte corrigé** : la première tentative de sauvegarde par
retype manuel du payload collé par l'utilisateur (598 trades, ~450 Ko)
a été tronquée après ~60 entrées faute d'attention à la taille. Détecté
avant tout calcul de QC, corrigé par la même méthode de récupération
que pour le Fichier 8 : relecture du transcript brut de session
(recherche du dernier hash de transaction du payload,
`0x56da90b1e9ae6ab43c5d98eb85809b753d02f2642d7ccd3b4057afea348390e9`,
extraction programmatique du message utilisateur complet). Le fichier
final contient bien les 598 trades. **Leçon retenue pour la suite de
cette collecte** : pour tout payload volumineux, extraire depuis le
transcript plutôt que retyper à la main, afin d'éliminer ce risque de
troncature silencieuse.

QC (sur les 598 trades corrects) : 598 bruts = 598 après dédup (aucun
doublon) ; 267 wallets uniques ; 494 BUY / 104 SELL ; période
2026-08-31 18:03:18 → 2026-09-01 17:11:31 UTC, toutes avant
`resolution_time_closedTime` (17:32:21 UTC) — 0 trade post-résolution ;
jointure `asset↔outcome↔token_ids` cohérente ; `resolved_outcome`="Yes"
confirmé. `suntori` très actif sur ce marché (47 trades) — poursuit la
tendance observée sur les autres marchés de ce match.

### Fichier 14 — `trades_market_chfa-dy-shs_dy-win_0x0a529ab1_offset0.json`

Marché "Dalian Yingbo FC win" (`0x0a529ab12b2ae559fdeb8caae0362d40c6e56227059ba6d0a7036cdab6e08aca`),
5/21, match déjà signalé `suntori_overlap: true`. Extraction directe
depuis le transcript dès réception (leçon du Fichier 13 appliquée) —
aucune troncature. 139 trades bruts = 139 après dédup ; 59 wallets ;
103 BUY / 36 SELL ; période 2026-08-31 15:39:49 → 2026-09-01 16:21:45
UTC, résolution 17:32:22 UTC — 0 trade post-résolution ; jointure
cohérente ; `resolved_outcome`="Yes" confirmé (seul marché "win"
gagnant du match). `suntori` présent 1 fois — cohérent avec l'overlap
déjà connu.

### Fichier 15 — `trades_market_chfa-dy-shs_draw_0x5c3c171e_offset0.json`

Marché "draw" du même match (`0x5c3c171e0e194a58752c80263599d46bbae0517caf4d7804aa3aa3d20e625e58`),
6/21. Extraction transcript. 49 trades bruts = 49 après dédup ; 34
wallets ; 45 BUY / 4 SELL ; période 2026-09-01 03:37:13 → 15:06:00 UTC,
résolution 17:34:01 UTC — 0 trade post-résolution ; jointure cohérente ;
`resolved_outcome`="No" confirmé. `suntori` présent 1 fois.

### Fichier 16 — `trades_market_chfa-dy-shs_shs-win_0x7c98095d_offset0.json`

Marché "Shanghai Shenhua FC win" (`0x7c98095d33362609ea64043ff31fd5376f66286f5ae96bca1f7630a2826a363b`),
7/21, dernier marché du match `chfa-dy-shs-2026-09-01` (`suntori_overlap: true`
déjà signalé dans les métadonnées). Extraction transcript dès réception
(pas de retype manuel). 312 trades bruts = 312 après dédup (aucun
doublon) ; 118 wallets uniques ; 268 BUY / 44 SELL ; période
2026-08-31 13:41:30 → 2026-09-01 16:35:55 UTC, résolution
(`closedTime`) 17:33:01 UTC — 0 trade post-résolution ; jointure
`asset↔outcome↔token_ids` cohérente ; `resolved_outcome`="No" confirmé
(cohérent avec Dalian win="Yes" et Shanghai draw="No" déjà validés —
un seul vainqueur possible, résultat interne du match cohérent).
`suntori` très actif sur ce marché (11 trades) — confirme que ce
wallet trade sur les 3 marchés du match, pas seulement le marché
initialement repéré. Ceci reste une observation post-hoc, sans impact
sur la sélection des marchés (choisis avant tout examen des trades).

**Match `chfa-dy-shs-2026-09-01` complet : 3/3 marchés collectés**
(Fichiers 14, 15, 16 — Dalian win / draw / Shanghai win), tous
exploitables (0 trade post-résolution, jointure cohérente, résultats
internes cohérents entre eux).

### Fichier 17 — `trades_market_geo1-tbi-gor_tbi-win_0xe8706a06_offset0.json`

Marché "FC Dinamo Tbilisi win" (`0xe8706a060c9b9d759e1c3b1e84429fc06c82b63e94ab793643b894e0cd9682e6`),
8/21, match `geo1-tbi-gor-2026-08-31` (métadonnées : `suntori_overlap: false`).
Extraction transcript. 25 trades bruts = 25 après dédup ; 19 wallets ;
22 BUY / 3 SELL ; période 2026-08-31 10:41:09 → 18:57:12 UTC,
résolution 21:02:19 UTC — 0 trade post-résolution ; jointure cohérente ;
`resolved_outcome`="Yes" confirmé. `suntori` présent 1 fois **malgré
le flag `suntori_overlap: false` en métadonnées** — confirme une
nouvelle fois (cf. constat déjà fait au Fichier 11) que ce flag a
priori est incomplet ; la détection réelle se fait sur les données de
trades reçues, pas sur le flag précalculé. Marché de petite taille
(25 trades) mais exploitable.

### Fichier 18 — `trades_market_geo1-tbi-gor_draw_0x3f462b53_offset0.json`

Marché "draw" du même match (`0x3f462b53383ab6c64eee7b46333183319ae2c646510ba2676f0f3b0bc27ed73f`),
9/21. Extraction transcript. 24 trades bruts = 24 après dédup ; 19
wallets ; 22 BUY / 2 SELL ; période 2026-08-31 10:42:59 → 17:31:07 UTC,
résolution 21:02:04 UTC — 0 trade post-résolution ; jointure cohérente ;
`resolved_outcome`="No" confirmé (cohérent avec Dinamo Tbilisi win="Yes"
déjà validé). `suntori` absent de ce marché.

### Fichier 19 — `trades_market_geo1-tbi-gor_gor-win_0xe90c5389_offset0.json`

Marché "FC Dila Gori win" (`0xe90c53898c9231407ec41e5f4a27ef3d9fbbc20027788427972d1bdeeb13018c`),
10/21, dernier marché du match `geo1-tbi-gor-2026-08-31`. Extraction
transcript. **Marché très fin** : seulement 4 trades bruts = 4 après
dédup ; 3 wallets uniques ; 3 BUY / 1 SELL ; période 2026-08-31
16:30:43 → 17:18:54 UTC, résolution 21:03:19 UTC — 0 trade
post-résolution ; jointure cohérente ; `resolved_outcome`="No" confirmé
(cohérent avec Dinamo Tbilisi win="Yes"). `suntori` absent. Techniquement
exploitable (0 anomalie) mais à signaler explicitement comme marché à
très faible profondeur (3 wallets) dans le rapport final — la
significativité de tout futur signal wallet issu de ce marché sera
limitée.

**Match `geo1-tbi-gor-2026-08-31` complet : 3/3 marchés collectés**
(Fichiers 17, 18, 19), tous exploitables, résultats internes cohérents
entre eux.

### Fichier 20 — `trades_market_geo1-gag-ibe_gag-win_0x893a54a0_offset0.json`

Marché "FC Gagra win" (`0x893a54a0d2054ab36d0bdd16e94318fc045a2e10991517e7586259ec0fded393`),
11/21, match `geo1-gag-ibe-2026-08-31`. Extraction transcript.
**Marché fin** : 9 trades bruts = 9 après dédup ; 6 wallets uniques ;
8 BUY / 1 SELL ; période 2026-08-31 15:14:03 → 18:01:04 UTC, résolution
19:02:51 UTC — 0 trade post-résolution ; jointure cohérente ;
`resolved_outcome`="Yes" confirmé. `suntori` absent. Exploitable mais
faible profondeur (6 wallets).

### Fichier 21 — `trades_market_geo1-gag-ibe_draw_0xaf6f4f94_offset0.json`

Marché "draw" du même match (`0xaf6f4f940c314271e121f1f95d7ea09ae34a83f7310eca60096586ec913dabbc`),
12/21. Extraction transcript. **Marché très fin** : 4 trades bruts = 4
après dédup ; 3 wallets uniques ; 4 BUY / 0 SELL ; période 2026-08-31
10:43:02 → 16:07:18 UTC, résolution 19:02:51 UTC — 0 trade
post-résolution ; jointure cohérente ; `resolved_outcome`="No" confirmé
(cohérent avec Gagra win="Yes"). `suntori` absent. Exploitable mais
profondeur très faible (3 wallets).

### Fichier 22 — `trades_market_geo1-gag-ibe_ibe-win_0xdac059fb_offset0.json`

Marché "FC Iberia 1999 win" (`0xdac059fb1d95edb8775f355942858349a94fbe70156763629c4f0f0246256e7c`),
13/21, dernier marché du match `geo1-gag-ibe-2026-08-31`. Extraction
transcript. 13 trades bruts = 13 après dédup ; 10 wallets uniques ;
12 BUY / 1 SELL ; période 2026-08-31 10:43:00 → 16:06:54 UTC, résolution
19:00:01 UTC — 0 trade post-résolution ; jointure cohérente ;
`resolved_outcome`="No" confirmé (cohérent avec Gagra win="Yes"). `suntori`
absent.

**Match `geo1-gag-ibe-2026-08-31` complet : 3/3 marchés collectés**
(Fichiers 20, 21, 22), tous exploitables mais tous de faible profondeur
(3 à 10 wallets par marché) — à signaler dans le rapport final.

### Fichier 23 — `trades_market_geo1-tku-met_tku-win_0xfa7e093d_offset0.json`

Marché "FC Torpedo Kutaisi win" (`0xfa7e093dacc200ccc36893d6321afc988ee47d06361e38da71ee3089e335f2dc`),
14/21, match `geo1-tku-met-2026-08-31` (`suntori_overlap: false` en
métadonnées). Extraction transcript. 32 trades bruts = 32 après dédup ;
23 wallets ; 29 BUY / 3 SELL ; période 2026-08-31 10:43:03 → 17:01:21
UTC, résolution 19:04:03 UTC — 0 trade post-résolution ; jointure
cohérente ; `resolved_outcome`="No" confirmé. `suntori` présent 2 fois
**malgré le flag `suntori_overlap: false`** — nouvelle confirmation
que le flag précalculé est incomplet (déjà observé aux Fichiers 11
et 17).

### Fichier 24 — `trades_market_geo1-tku-met_draw_0x01764da6_offset0.json`

Marché "draw" du même match (`0x01764da622a38cef9fa20203365e6c93542f88e1c7e7d41261ed8cb563f4d32f`),
15/21. Extraction transcript. **Marché très fin** : 5 trades bruts = 5
après dédup ; 5 wallets uniques ; 5 BUY / 0 SELL ; période 2026-08-31
10:43:05 → 16:07:12 UTC, résolution 19:02:52 UTC — 0 trade
post-résolution ; jointure cohérente ; `resolved_outcome`="No" confirmé
(cohérent avec Torpedo win="No" — le match n'était donc ni un Torpedo
win ni un draw, ce qui implique un Meshakhte win, cohérence à vérifier
au marché suivant). `suntori` absent.

### Fichier 25 — `trades_market_geo1-tku-met_met-win_0xec6f8436_offset0.json`

Marché "FC Meshakhte Tkibuli win" (`0xec6f8436633bce86972382e1c57f6828ec3efe02053223acf952df420bbe8673`),
16/21, dernier marché du match `geo1-tku-met-2026-08-31`. Extraction
transcript. 15 trades bruts = 15 après dédup ; 7 wallets uniques ;
11 BUY / 4 SELL ; période 2026-08-31 12:25:52 → 17:06:49 UTC, résolution
19:04:01 UTC — 0 trade post-résolution ; jointure cohérente ;
`resolved_outcome`="Yes" confirmé — cohérent avec la déduction du
Fichier 24 (Torpedo win="No", draw="No" ⇒ Meshakhte win="Yes"). `suntori`
absent.

**Match `geo1-tku-met-2026-08-31` complet : 3/3 marchés collectés**
(Fichiers 23, 24, 25), tous exploitables, résultats internes cohérents.

### Fichier 26 — `trades_market_lva1-lie-rfc_lie-win_0x4ec28eee_offset0.json`

Marché "FK Liepaja win" (`0x4ec28eeed1e2567d915f2754dd81a859142b86940eb9cabd64324b465a861596`),
17/21, match `lva1-lie-rfc-2026-08-31`. Extraction transcript. 79 trades
bruts = 79 après dédup ; 40 wallets uniques ; 69 BUY / 10 SELL ;
période 2026-08-30 21:54:19 → 2026-08-31 16:33:57 UTC, résolution
18:32:03 UTC — 0 trade post-résolution ; jointure cohérente ;
`resolved_outcome`="Yes" confirmé. `suntori` absent.

### Fichier 27 — `trades_market_lva1-lie-rfc_draw_0x37df1f93_offset0.json`

Marché "draw" du même match (`0x37df1f93c16a9b2664cdb8ce36c38c0aa020b6cbc19cb3b28c8047b93c4cbbc6`),
18/21. Extraction transcript. 25 trades bruts = 25 après dédup ; 15
wallets ; 24 BUY / 1 SELL ; période 2026-08-30 22:04:28 → 2026-08-31
16:33:25 UTC, résolution 18:32:01 UTC — 0 trade post-résolution ;
jointure cohérente ; `resolved_outcome`="No" confirmé (cohérent avec
Liepaja win="Yes"). `suntori` absent.

### Fichier 28 — `trades_market_lva1-lie-rfc_rfc-win_0x4d8a8fb1_offset0.json`

Marché "Riga FC win" (`0x4d8a8fb1012aba4a87fa3d14f9cf43fc60dba6295fdc3633bafd553cb3b29ad1`),
19/21, dernier marché du match `lva1-lie-rfc-2026-08-31`. Extraction
transcript. 48 trades bruts = 48 après dédup ; 33 wallets uniques ;
42 BUY / 6 SELL ; période 2026-08-30 22:04:27 → 2026-08-31 16:33:33
UTC, résolution 18:32:01 UTC — 0 trade post-résolution ; jointure
cohérente ; `resolved_outcome`="No" confirmé (cohérent avec Liepaja
win="Yes"). `suntori` présent 1 fois malgré `suntori_overlap: false`.

**Match `lva1-lie-rfc-2026-08-31` complet : 3/3 marchés collectés**
(Fichiers 26, 27, 28), tous exploitables, résultats internes cohérents.

### Fichier 29 — `trades_market_aze1-sum-qar_sum-win_0x3efd468f_offset0.json`

Marché "Sumqayit FK win" (`0x3efd468f83894c29139be3ce879f1eaac397f76f12390adc3a989df0de187539`),
20/21, match `aze1-sum-qar-2026-08-31` (Sumqayit FK vs. Qarabag FK — le
marché "Qarabag FK win" de ce même match a déjà été collecté et validé
comme marché 1/21, 69 trades). Extraction transcript. 28 trades bruts =
28 après dédup ; 12 wallets uniques ; 28 BUY / 0 SELL ; période
2026-08-30 20:26:33 → 2026-08-31 17:50:00 UTC, résolution 20:07:19 UTC
— 0 trade post-résolution ; jointure cohérente ; `resolved_outcome`="No"
confirmé — cohérence à vérifier avec le marché "Qarabag FK win" déjà
collecté et le marché "draw" restant. `suntori` absent.

### Fichier 30 — `trades_market_aze1-sum-qar_draw_0x9e3708f0_offset0.json`

Marché "draw" du même match (`0x9e3708f065b985e3ede53994ca33a062110bf4a597679b99cf075decf8ca8c6d`),
21/21, dernier marché de tout l'univers neutre. Extraction transcript.
7 trades bruts = 7 après dédup ; 6 wallets uniques ; 6 BUY / 1 SELL ;
période 2026-08-30 20:26:33 → 2026-08-31 16:41:33 UTC, résolution
20:08:03 UTC — 0 trade post-résolution ; jointure cohérente ;
`resolved_outcome`="No" confirmé. `suntori` absent.

**Match `aze1-sum-qar-2026-08-31` complet : 3/3 marchés collectés**
(Fichier 1 pour Qarabag win = 69 trades, marché 1/21, résolu "Yes" ;
Fichiers 29-30 pour Sumqayit win et draw, tous deux résolus "No") —
résultats internes parfaitement cohérents (un seul vainqueur, Qarabag
FK).

## Collecte terminée : 21/21 marchés de l'univers neutre collectés et validés.

---

# Phase panel élargi (~50 matchs) — collecte en continuité

Voir `research/polymarket_50_match_collection.md` pour le protocole complet
(règles, checkpoint à ~25). Journal détaillé des fichiers ci-dessous.

## Fichier 31 — `events_neutral_soccer_tagslug_closed_offset40_2026-09-02.json`

- **Origine** : `GET https://gamma-api.polymarket.com/events?tag_slug=soccer&closed=true&limit=40&order=startDate&ascending=false&offset=40`,
  fetch manuel navigateur par l'utilisateur, collé dans la conversation le
  2026-09-02. Code HTTP non capturé explicitement mais JSON valide reçu
  (racine `list`, 40 éléments — parse et validé avec `json.loads`).
- **Contenu** : 40 événements. Après inspection systématique
  (`sportsMarketType`, `series.title`, dédup par titre contre le seed de 7
  matchs déjà collecté à `offset=0`) :
  - **5 événements moneyline en doublon** avec le seed déjà collecté :
    FK Liepaja vs Riga FC (id 938586), Sumqayit FK vs Qarabag FK (id
    938306), FC Gagra vs FC Iberia 1999 (id 940909), FC Torpedo Kutaisi vs
    FC Meshakhte Tkibuli (id 940908), FC Dinamo Tbilisi vs FC Dila Gori
    (id 940910) — confirme le chevauchement de pagination temporelle déjà
    identifié (le tri `startDate` descendant se décale entre deux fetches
    séparés par ~24h car de nouveaux événements plus récents s'insèrent).
  - **29 sous-événements non-moneyline** liés à ces mêmes 5 matchs + au
    match Barranquilla/Boca (More Markets, Exact Score, First/Second Half
    Result, Halftime Result, Total Corners) — hors périmètre (règle
    moneyline uniquement), ignorés.
  - **3 événements moneyline réellement nouveaux**, `sportsMarketType`
    homogène (3 marchés binaires chacun, tous `outcomePrices` résolus
    `["1","0"]`/`["0","1"]`) : Umraniyespor vs Muglaspor (id 941270,
    Turkey 1. Lig, victoire Muglaspor), Bandirmaspor vs Antalyaspor (id
    941269, Turkey 1. Lig, victoire Antalyaspor), Barranquilla FC vs Boca
    Juniors de Cali (id 940469, Primera B Colombie, victoire Barranquilla
    FC). ConditionIds et clobTokenIds extraits et reportés dans
    `polymarket_50_match_collection.md` Étape 2, lignes 1-3.
  - **1 match partiel exclu** : Araz Nakhchivan PFK vs Sabah Masazir — seul
    le sous-événement "More Markets" (id 938200) apparaît dans ce batch ;
    l'événement moneyline de base (probablement `startDate` légèrement
    antérieur à 2026-08-30T19:54:15Z) n'y figure pas. Non ajouté à l'Étape
    2 faute de conditionIds moneyline complets — à rechercher dans un
    batch ultérieur (`offset=80`) si besoin.
- **QC** : 40/40 événements parsés sans erreur ; aucun conditionId dupliqué
  entre les 3 nouveaux matchs et le seed de 7 ; les 3 nouveaux matchs ont
  chacun exactement 3 marchés moneyline avec `outcomePrices` binaires
  résolus et somme cohérente (exactement une issue "Yes" par match parmi
  Home/Draw/Away).

*(Batches `offset=80` à `offset=320` : détail des matchs nouveaux/partiels
exclus par batch documenté directement dans les notes de
`research/polymarket_50_match_collection.md` Étape 1, plutôt que sous forme
de fichiers numérotés séparés ici — pas de fichier "Fichier 32" etc.)*

---

## DÉCISION FINALE DU PILOTE (2026-09-05) — collecte d'événements CLÔTURÉE à 34 matchs

L'objectif initial de ~50 matchs (mentionné dans l'en-tête de section
ci-dessus, « Phase panel élargi (~50 matchs) ») est **abandonné**. La
pagination des événements Polymarket s'arrête définitivement à
`offset=320` (34 matchs moneyline complets au total dans
`research/polymarket_50_match_collection.md` Étape 2). **Aucun batch
`offset=360` ou ultérieur ne sera récupéré.**

Toute mention antérieure dans ce journal de « poursuite prévue »,
« batch ultérieur si retrouvé » (pour les deux candidats qatariens partiels
d'`offset=320`, Al Ahli Doha SC vs Qatar SC et Al-Sailiya SC vs Al Arabi
Doha SC) ou de continuation vers 50 matchs est **historique** et n'est plus
actionnable — ces deux matchs partiels restent définitivement exclus du
panel.

**Prochaine étape (Fichiers 32+, à venir)** : collecte des trades pour les
3 marchés moneyline de chacun des 34 matchs du panel, avec la même
méthodologie QC que les Fichiers 1-30 (dédup par `transactionHash`,
vérification `resolved_outcome`, période, `suntori`), en continuité de
numérotation dans ce journal.
