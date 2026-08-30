# Audit de faisabilité des données Polymarket — Phase M

**Portée** : audit de données + protocole de déblocage, en vue d'une
future expérience testant si l'information des traders Polymarket
apporte quelque chose au modèle football. **Aucune expérience de
performance, aucun ROI, aucun seuil, aucune sélection rétrospective de
traders n'est fait dans ce document.** Le moteur final reste **GELÉ**
(`min_edge_threshold=None`, `BET` non activé, commits `df709cb`/`7a89cd1`/
`1356238`).

---

## 1. Executive summary

L'accès réseau sortant vers `gamma-api.polymarket.com`,
`clob.polymarket.com`, `data-api.polymarket.com`, `docs.polymarket.com` et
`pomet.com.br` est **toujours bloqué** dans cet environnement (re-testé au
début de cette phase, 403 explicite au niveau du proxy de sortie — voir
§2). **Aucune inspection primaire n'a donc été possible**, exactement
comme en Phase L. Cette phase a néanmoins approfondi, via recherche web,
des détails techniques précis et convergents (paramètres de pagination,
plafonds documentés, mécanisme de résolution UMA, exemples de marchés
football réels indexés) qui n'avaient pas été creusés en Phase L.

Conformément à la règle d'arrêt de cette phase, **aucune donnée n'a été
fabriquée, aucun exemple de reconstruction PIT n'a été construit sur des
données réelles** (impossible sans accès), et **`CANONICAL_TEAM_ALIASES`
reste vide** — y compris face à des noms d'équipes réels trouvés dans un
résumé de moteur de recherche (§10 : jugé insuffisant comme preuve
vérifiée).

**Verdict : C — Données intéressantes mais PIT non démontré.** Le
raisonnement complet est en §16.

---

## 2. APIs réellement accessibles

### 2.1 Test d'accès réel (obligatoire, étape 3)

Retesté explicitement en tout début de cette phase (nouvelle session,
distincte de la Phase L) :

```
$ curl -sS -m 10 https://gamma-api.polymarket.com/markets?limit=1
curl: (56) CONNECT tunnel failed, response 403
$ curl -sS -m 10 https://clob.polymarket.com/markets
curl: (56) CONNECT tunnel failed, response 403
$ curl -sS -m 10 https://data-api.polymarket.com/trades?limit=1
curl: (56) CONNECT tunnel failed, response 403
$ curl -sS -m 10 https://docs.polymarket.com/
curl: (56) CONNECT tunnel failed, response 403
$ curl -sS -m 10 https://www.pomet.com.br/
curl: (56) CONNECT tunnel failed, response 403
```

Confirmé par le statut du proxy de sortie (`recentRelayFailures`) :
`gateway answered 403 to CONNECT (policy denial or upstream failure)`
pour les cinq domaines, horodaté au moment du test. **Conformément à
l'étape 3 de la consigne : exécution réelle STOPPÉE. Aucune réponse n'a
été simulée, aucun marché/trade/wallet n'a été fabriqué.**

**Accès bloqué exactement** : tout accès sortant HTTPS vers
`gamma-api.polymarket.com`, `clob.polymarket.com`,
`data-api.polymarket.com`, `docs.polymarket.com`, `www.pomet.com.br`
(politique de sortie de cet environnement, restreinte à GitHub/registres
de paquets/API Anthropic).

**Ce qui doit être fourni manuellement pour continuer** (identique à la
procédure Phase K/ClubElo qui a fonctionné) :
1. Quelques réponses JSON réelles et complètes de `GET
   https://gamma-api.polymarket.com/markets?tag_slug=soccer&closed=true`
   (ou équivalent) pour 3-5 marchés football réellement résolus ;
2. La réponse réelle de `GET
   https://data-api.polymarket.com/trades?market=<market_id_reel>` pour
   au moins un de ces marchés ;
3. La réponse réelle de `GET
   https://clob.polymarket.com/prices-history?market=<token_id_reel>&interval=max`
   pour le même marché ;
4. Une capture d'écran ou un copié-collé intégral d'une fiche de trader
   Pomet réelle (comme cela a été fait pour ClubElo) ;
5. **Alternative** : exécuter cette même phase dans un environnement dont
   la politique réseau autorise ces cinq domaines.

### 2.2 Ce qui est documenté publiquement (sources secondaires convergentes, non vérifié par appel réel)

| API | Base URL | Authentification (lecture) | Rate limit documenté | Rôle |
|---|---|---|---|---|
| **Gamma** | `gamma-api.polymarket.com` | Aucune | ~4000 req/10s (source tierce) | Découverte marchés/événements, métadonnées, statut (`closed`/`archived`), tags |
| **CLOB** | `clob.polymarket.com` | Aucune pour la lecture ; EIP-712 + clés dérivées du wallet pour les ordres | ~9000 req/10s (lecture) documenté ; limites distinctes pour `/order` | Carnet d'ordres, `/prices-history` (prix historiques par token) |
| **Data** | `data-api.polymarket.com` | Aucune | ~1000 req/10s documenté | `/trades` (historique de trades par wallet ou marché), `/positions` (état courant), classement de traders (endpoint officiellement documenté : « Get trader leaderboard rankings ») |

**Détail des paramètres documentés** (non vérifiés par appel réel) :

- `GET /trades` (Data API) : `limit` (défaut 100, max documenté 500),
  `offset` (défaut 0), `takerOnly` (bool), `filterType`/`filterAmount`.
  **Plafond documenté critique** : au-delà de `offset=10000`, l'API
  rejetterait explicitement avec une erreur 400 plutôt que de tronquer
  silencieusement — pour un historique plus profond, il faudrait paginer
  par fenêtres temporelles (`before`/`after` ou équivalent) plutôt que par
  offset pur. **Non vérifié.**
- `GET /prices-history` (CLOB) : `market` (identifiant de token, pas
  l'identifiant de marché lui-même — distinction documentée entre
  `market_id`/`condition_id` et `token_id` par outcome), `startTs`/`endTs`
  (Unix, mutuellement exclusifs de) `interval` (`max`/`all`/`1m`/`1w`/`1d`/
  `6h`/`1h`), `fidelity` (résolution en minutes, ex. 1/60/1440). **Signalé
  par une source tierce (issue GitHub officielle `py-clob-client`)** :
  cet endpoint renverrait des données vides pour un marché déjà résolu à
  des granularités fines (<12h) — **si confirmé, ceci limiterait
  sérieusement la reconstruction de prix historiques fins sur un marché
  clos**, point CRITIQUE pour §6/§7 mais **non vérifié directement**.
- `GET /markets` (Gamma) : `closed` (bool), `archived` (bool), filtres par
  tag (ex. un tag sport/football documenté comme existant, valeurs
  exactes non confirmées).

### 2.3 Ce qui reste non déterminé

- Le nom exact de chaque champ JSON retourné par un appel réel.
- Si `/trades` couvre l'historique complet depuis la création du marché
  ou une fenêtre glissante limitée.
- Si le plafond `offset=10000` et le comportement vide de
  `/prices-history` sur marché résolu (§2.2) sont réels ou des artefacts
  de version/bug ponctuel signalés par un seul utilisateur tiers.
- Le tag exact utilisé pour catégoriser le football/soccer côté Gamma API
  (`soccer` vs `football` vs autre — les deux mots apparaissent dans des
  URLs publiques distinctes, `polymarket.com/sports/soccer/games` et
  `polymarket.com/sports/football/games`, sans que leur relation exacte
  avec un paramètre d'API `tag_slug` soit confirmée).

---

## 3. Marchés football

**Aucun marché football individuel n'a pu être inspecté directement**
(market ID, event ID, slug, dates exactes — tout ceci nécessite un appel
réel bloqué, §2.1).

Ce qui a pu être établi indirectement (résumés de pages publiques
indexées par un moteur de recherche, **pas une inspection de page ni un
appel API**) :
- Il existe des pages dédiées `polymarket.com/sports/soccer/games` et
  `polymarket.com/sports/football/games`, ainsi que des pages par
  compétition (`polymarket.com/sports/epl/games`,
  `polymarket.com/sports/elc/games` — EPL, EFL Championship) et par club
  (`polymarket.com/predictions/arsenal`, `.../english-premier-league`).
  Ceci suggère une couverture allant **au-delà des seules compétitions
  internationales** (Coupe du Monde) et incluant potentiellement des
  championnats domestiques comparables à ceux déjà couverts par
  Football-Data (Premier League au moins).
- Un résumé de recherche a cité des rencontres nommément : « Real Madrid
  CF vs. Málaga CF », « Chelsea FC vs. Brighton & Hove Albion FC », «
  Leeds United FC vs. Brentford FC » — format de titre apparent « Team A
  vs. Team B », noms complets avec suffixe de forme juridique/club (« CF »,
  « FC »), **différents de la convention abrégée de Football-Data**
  (ex. Football-Data : « Real Madrid », « Chelsea », « Brighton »,
  « Leeds », « Brentford » — voir `team_mapping.py`). **Ceci n'est PAS une
  observation vérifiée d'un marché réel** (pas de capture d'écran, pas de
  market_id, pas de slug, provient d'un résumé automatique de résultats de
  recherche) - traité comme un indice, jamais comme une preuve (§10).

Aucun des champs demandés (titre exact, slug, market ID, event ID,
équipes, compétition, dates d'ouverture/fermeture/résolution, outcome(s),
prix historiques) n'a pu être documenté avec une valeur réelle vérifiée
pour un marché précis.

---

## 4. Historique disponible (classification étape 2)

| # | Donnée | Classification | Justification |
|---|---|---|---|
| A | Marchés football historiques | **C** | Fortement suggéré disponible (Gamma expose `closed`/`archived`, pages publiques par compétition existent) mais aucun marché precis inspecté ; couverture réelle (nombre, profondeur temporelle) inconnue |
| B | Trades historiques | **C** | `/trades` documenté comme accessible par marché/wallet avec pagination ; structure de reponse et profondeur reelle non verifiees ; plafond de pagination documente (offset 10000) non confirme |
| C | Prix historiques | **C** (potentiellement **D** si le signalement §2.2 sur `/prices-history` vide pour marchés résolus se confirme) | Endpoint et parametres documentes de façon detaillee et convergente, mais un signalement tiers specifique remet en cause l'exploitabilite meme du mecanisme pour des marches DEJA RESOLUS - exactement le cas d'usage recherche ici (marches football passes) |
| D | Participants/wallets | **C** | `/positions` (etat courant) et `/trades` (wallet en parametre) documentes ; mais `/positions` est PIT-dangereux par nature (etat courant seul, voir Phase L) et aucune donnee reelle de wallet football n'a ete observee |
| E | Reconstruction de l'etat connu a `decision_time` | **D** | Aucun exemple concret n'a pu etre construit sur donnees reelles (§7) - la reconstruction depuis un journal de trades est methodologiquement solide (Phase L, `positions.py`/`pit.py`, deja teste sur donnees synthetiques) mais RIEN n'a ete demontre sur un marche football REEL |

Aucune de ces classifications n'a été portée à **A** ou **B** —
conformément à la règle explicite de ne jamais transformer une donnée
C/D en A par hypothèse.

---

## 5. PIT feasibility

**Aucun exemple concret de reconstruction PIT sur données réelles n'a pu
être construit** (§2.1 : accès bloqué). Ce qui suit décrit uniquement le
gabarit qu'un tel exemple devrait suivre, une fois des données réelles
disponibles — repris du mécanisme déjà implémenté et testé sur données
synthétiques en Phase L (`src/sys_foot_quant/polymarket/pit.py`) :

| Repère temporel | Rôle | Statut |
|---|---|---|
| `market_open_time` | Ouverture du marché — première trade possible | Concept documenté (`Market.start_time`), jamais observé sur un marché réel |
| `decision_time` | Instant de la décision (même convention que `final_engine` : avant le coup d'envoi, décalage à définir dans un futur protocole) | Défini par nous, pas par Polymarket |
| `last_allowed_observation` | Dernier trade/prix dont `timestamp_utc < decision_time` — strictement, jamais `<=` (cohérent avec `pit.py`) | Mécanisme déjà implémenté et testé (Phase L), mais jamais exercé sur une vraie série de trades |
| `market_close_time` | Fin des échanges (`Market.end_time`) | Concept documenté, jamais observé |
| `resolution_time` | Résolution effective (au plus tôt 2h après la proposition UMA, si non contestée — §2.2, §9) | Mécanisme général documenté ; **application à un marché football réel non vérifiée** |

**Données autorisées avant `decision_time`** : tout trade/prix dont le
timestamp est strictement antérieur ; toute métadonnée statique du marché
connue dès son ouverture (équipes, compétition, date de match — sous
réserve que ces métadonnées elles-mêmes ne soient pas éditées après coup,
point non vérifié).

**Données interdites** : résultat du match, résolution du marché,
n'importe quel trade/prix postérieur ou égal à `decision_time`,
métadonnée apparue après (ex. un correctif de titre après un report de
match — voir §9).

---

## 6. Trades

Voir §2.2/§4-B. Non vérifié : profondeur historique réelle, format exact
d'un trade individuel, présence garantie d'un identifiant de trade stable
(`trade_id`). `src/sys_foot_quant/polymarket/trades.py` (Phase L) est déjà
écrit pour parser plusieurs conventions de noms de clés possibles et pour
dédupliquer avec ou sans identifiant stable — mais reste **non exercé sur
un payload réel**.

---

## 7. Prix

Voir §2.2. C'est le point le plus incertain de cet audit : un
signalement tiers spécifique (issue GitHub officielle du client Python
CLOB) indique que `/prices-history` pourrait renvoyer une réponse vide
pour un marché **déjà résolu** en dessous d'une granularité de 12h — ce
qui, si confirmé, **casserait précisément le cas d'usage recherché ici**
(reconstruire le prix tel qu'il était avant un match déjà joué et résolu).
Seule une vérification réelle sur un marché football effectivement résolu
peut trancher ce point. **Non extrapolé plus loin.**

---

## 8. Traders/wallets

Reprend et affine §7 de l'audit Phase L. Primitives déjà disponibles
(architecture Phase L, données synthétiques uniquement) :

| Primitive demandée | Disponible dans le code (synthétique) | Disponible sur données réelles |
|---|---|---|
| Trades antérieurs | Oui (`pit.get_trader_information_as_of`) | Non vérifié |
| Volume antérieur | Oui (`TraderStatsAsOf.volume_notional`) | Non vérifié |
| Performance antérieure (P&L réalisé, win rate) | Oui, mais uniquement pour les marchés dont la résolution est connue avant `decision_time` (`traders.compute_trader_stats_as_of`) | Non vérifié - dépend de §7 (accès aux résolutions réelles) |
| Nombre de marchés tradés | Oui (dérivable de `positions_as_of`) | Non vérifié |
| Spécialisation football | Non implémenté - nécessite d'abord le tag/catégorisation Gamma réelle (§2.3) | Non disponible |
| Historique avant `decision_time` | Oui (filtrage strict `< decision_time`) | Non vérifié |

**Aucune métrique de « smart money » n'a été construite** — conforme à
la consigne. Ce tableau documente uniquement quelles primitives sont
*scientifiquement disponibles en principe*, pas leur valeur réelle.

---

## 9. Règlement (étape 5)

D'après la documentation publique convergente sur le mécanisme UMA
Optimistic Oracle (§2.2) :

- **Source qui fait foi** : définie par match, au niveau de chaque
  marché (« resolution source » spécifiée dans les règles du marché) -
  pas une source unique globale.
- **Quand le résultat devient déterminable** : au plus tôt 2h après la
  proposition d'issue par un premier proposant (fenêtre de contestation),
  potentiellement plus long si contesté (second arbitrage, puis vote DVM
  si contesté une seconde fois).
- **Reports/annulations/matchs interrompus** : la documentation mentionne
  une distinction explicite pour « un événement qui n'a pas encore eu
  lieu » côté proposition — suggère l'existence d'une règle dédiée pour
  les cas d'événement non joué/reporté, mais **le contenu exact de cette
  règle pour le football spécifiquement n'a pas été vérifié**.
- **Noms d'équipes** : aucune règle de normalisation documentée trouvée -
  vraisemblablement fixés au niveau du titre/texte du marché, sans
  garantie d'orthographe stable dans le temps.
- **Marchés invalidés** : mécanisme non documenté trouvé spécifiquement.
- **Passage à RESOLVED** : vraisemblablement reflété par le champ
  `closed`/équivalent côté Gamma API une fois la fenêtre UMA terminée
  sans contestation persistante - **non vérifié**.

**Aucun filtre strict de corpus expérimental ne peut être défini avec
confiance à partir de ces seules informations non vérifiées.** Un futur
protocole devra, au minimum, exclure tout marché pour lequel la
documentation de résolution n'est pas confirmée disponible et univoque
sur un échantillon réel inspecté à la main (même méthode que Phase K pour
ClubElo).

---

## 10. Matching football

**`CANONICAL_TEAM_ALIASES` reste vide.** Aucune entrée n'a été ajoutée,
y compris face aux noms d'équipes cités en §3 (« Real Madrid CF »,
« Chelsea FC », etc.), pour la raison suivante, explicitée ici pour
transparence totale :

Ces noms proviennent d'un **résumé de résultats de recherche**
(agrégation/synthèse automatique d'un moteur de recherche tiers sur une
page Polymarket publique), **pas d'une observation directe et vérifiable
d'un marché réel** — à la différence de la Phase K (ClubElo), où
l'utilisateur avait lui-même ouvert les pages réelles dans son navigateur
et retranscrit intégralement leur contenu (texte + captures d'écran),
permettant une vérification entrée par entrée. Un résumé de recherche
peut introduire des erreurs de transcription, être partiellement obsolète,
ou ne pas correspondre à un `market_id`/`slug` réel vérifiable. Accepter
ces noms comme base d'un mapping utilisé pour une future analyse
scientifique serait un niveau de rigueur strictement inférieur à celui
déjà appliqué sur ce projet pour Understat et ClubElo.

**Aucun tableau `canonical_name`/`polymarket_name`/`football_data_name`/
`competition`/`source de vérification` n'est donc rempli dans ce
document.** Cette table ne pourra être peuplée qu'après une observation
directe et vérifiable (accès réseau réel, ou transcription manuelle par
l'utilisateur d'une page réelle, comme en Phase K).

---

## 11. Pomet vs Polymarket (réévaluation)

Aucune nouvelle information primaire sur Pomet n'a pu être obtenue
(accès bloqué, §2.1). Reprise de la classification de l'audit Phase L
(`docs/polymarket_pomet_data_audit.md` §5), affinée par catégorie
demandée ici :

| Fonctionnalité Pomet potentielle | Classification |
|---|---|
| Score/confiance (comparaison taille de pari vs moyenne historique du trader) | **C — propriétaire, non reconstructible sans connaître la formule exacte** (l'idée générale - comparer une taille de trade à une moyenne mobile du même wallet - est banale et reconstructible, mais la formule/les seuils exacts de Pomet ne sont pas documentés) |
| Classement de traders | **A — directement disponible** (endpoint natif Polymarket documenté, §2.2) |
| Historique agrégé d'un trader | **B — reconstructible** depuis `/trades` (sous réserve de §6/§7) |
| Sélection de traders prête à l'emploi (« Pomet Selection ») | **C — propriétaire** par construction (c'est un jugement/une sélection humaine ou algorithmique propre à Pomet, pas une donnée brute) |
| Filtres (catégorie sport, période) | **B — reconstructible** une fois la catégorisation Gamma réelle vérifiée (§2.3) |
| Alertes Telegram / bot de copie | **C — service applicatif propriétaire**, hors du périmètre de données de ce projet (nous ne cherchons pas à copier des trades, seulement à tester une information incrémentale) |

**Conclusion inchangée par rapport à la Phase L** : aucune donnée brute
indispensable identifiée comme irremplaçable côté Pomet ; ses apports
distinctifs sont soit propriétaires et non nécessaires à notre objectif
scientifique (score de confiance, sélection), soit reconstructibles à
partir des API Polymarket elles-mêmes (classement, historique, filtres).

---

## 12. Corpus estimé

**Aucune estimation numérique n'est possible.** Aucun comptage réel de
marchés, matchs, ou période couverte n'a pu être effectué (accès bloqué).
Toute tentative de chiffrer un ordre de grandeur ici serait une
extrapolation non vérifiable, explicitement interdite par la consigne.

Seule indication qualitative disponible (§3) : la présence de pages
publiques dédiées par compétition domestique (EPL, EFL Championship,
MLS) suggère une couverture allant au-delà des seuls tournois
internationaux, mais **sans aucune mesure de profondeur temporelle ou de
volume de marchés**.

---

## 13. Limitations

1. Aucune vérification primaire d'un seul endpoint Polymarket ou Pomet
   n'a pu être réalisée dans cette phase (comme en Phase L).
2. Les paramètres d'API documentés en §2 proviennent tous de sources
   secondaires (guides tiers, issues GitHub, documentation indexée) -
   convergentes mais non confirmées par un appel réel.
3. Le point le plus critique et le moins résolu : la disponibilité réelle
   de prix historiques fins pour un marché football déjà résolu
   (`/prices-history`, signalement contradictoire non tranché, §7).
4. Aucun marché football réel n'a été identifié individuellement.
5. `CANONICAL_TEAM_ALIASES` reste vide - le matching est architecturalement
   prêt mais inopérant.
6. Le mécanisme de résolution (§9) n'est documenté qu'en général, jamais
   vérifié spécifiquement pour un marché football.
7. Aucune estimation quantitative du corpus n'est possible (§12).

---

## 14. Conditions nécessaires pour lancer une expérience

Toutes les conditions suivantes doivent être remplies - aucune n'est
remplie à ce jour :

1. Accès réel (réseau ou fourniture manuelle) à au moins la Gamma API et
   la Data API, avec inspection effective de plusieurs marchés football
   réellement résolus.
2. Confirmation ou infirmation du comportement de `/prices-history` sur
   un marché résolu (§7) - condition bloquante si infirmée sans
   alternative (les prix seraient alors inaccessibles pour la fenêtre
   pré-résolution qui nous intéresse).
3. Construction et vérification manuelle (méthode Phase K) d'au moins un
   `CANONICAL_TEAM_ALIASES` par championnat pertinent, à partir de
   marchés réellement observés.
4. Au moins un exemple end-to-end construit et vérifié de reconstruction
   PIT (`market_open_time`/`decision_time`/`last_allowed_observation`/
   `market_close_time`/`resolution_time`) sur un marché football réel.
5. Une estimation quantitative minimale du corpus (nombre de marchés
   football matchables à Football-Data, avec historique de prix ET de
   trades disponible) suffisante pour qu'une expérience walk-forward ait
   un sens statistique.
6. Vérification du mécanisme de résolution sur plusieurs marchés football
   réels (§9), avec un filtre d'exclusion explicite pour tout marché
   ambigu (report, invalidation, contestation UMA).
7. **Seulement alors** : rédaction d'un protocole d'expérience
   pré-enregistré fixant les critères d'éligibilité des traders - jamais
   avant, jamais en réutilisant les résultats pour choisir ces critères
   rétroactivement.

---

## 15. Préparation du protocole de future expérience (conditionnelle - non lancée)

Conformément à l'étape 12 de la consigne, si les conditions du §14
étaient un jour réunies, la première expérience devrait suivre exactement
le même schéma de contrôle que SOT/BFE/AH/Elo (Phases F/G/H/K) :

| Modèle | Rôle |
|---|---|
| **Modèle O** | `poisson_simple` brut, sans correction E7/E8, pour référence historique |
| **Modèle O-recalibré** | `poisson_simple` + correction scalaire E7/E8 walk-forward (mécanisme déjà validé, jamais remodifié) - **contrôle obligatoire**, exactement comme pour SOT/BFE/AH/Elo |
| **Modèle O + information Polymarket** | Ajout naïf de l'information Polymarket (ex. edge agrégé des traders éligibles) SANS recalibration supplémentaire - isole l'effet brut |
| **Modèle O + information Polymarket, recalibré si nécessaire** | Seulement si le modèle précédent montre un signal brut, une recalibration walk-forward serait appliquée pour distinguer un vrai gain d'une simple recalibration (piège déjà rencontré et isolé pour SOT et AH - Phases F et H) |

**Aucun seuil de BET n'est fixé ici ni ne le sera avant validation
complète.** `EligibilityRules` (Phase L, `traders.py`) reste sans aucun
seuil par défaut - les valeurs concrètes seraient fixées dans le
protocole pré-enregistré de cette future expérience, jamais avant, jamais
en fonction des résultats.

**Ce protocole n'est PAS lancé** - il est documenté ici uniquement en
préparation, conformément à l'étape 12, et reste conditionné à la levée
complète des blocages du §14.

---

## 16. Verdict

### **C — Données intéressantes mais PIT non démontré.**

Justification :
- Les trois API Polymarket documentées (Gamma/CLOB/Data) exposent, sur la
  base d'une documentation publique riche et convergente, exactement les
  primitives nécessaires (marchés, trades, prix historiques, positions,
  classement de traders) — ce n'est pas un manque de matière apparente,
  d'où l'exclusion du verdict **D**.
- Mais **aucune démonstration primaire** n'a pu être faite sur un seul
  marché, trade, prix ou wallet réel — le point central de la consigne
  (« construis au moins un exemple concret de reconstruction PIT si les
  données réelles sont accessibles ») n'a pas pu être exécuté, ce qui
  exclut les verdicts **A** et **B** (tous deux exigent une transformation
  *vérifiée*, pas seulement plausible).
- Un signalement tiers spécifique et non résolu (§7) met en doute la
  disponibilité même des prix historiques fins sur un marché déjà résolu
  — précisément le cas d'usage recherché — ce qui empêche de présenter
  cette phase comme un simple problème d'accès résiduel : il existe un
  doute méthodologique de fond, pas seulement un blocage d'infrastructure.

**Ce qui a été vérifié** : le blocage réseau lui-même (test direct,
403 reproductible sur les cinq domaines) ; la cohérence interne du code
Phase L (61 tests verts, aucune régression) ; la convergence de multiples
sources secondaires indépendantes sur l'existence et le rôle général des
trois API Polymarket, leurs paramètres documentés, et le mécanisme
général de résolution UMA.

**Ce qui n'a PAS été vérifié** : tout contenu réel d'une réponse API ou
d'une page Pomet ; l'existence, le nombre et la couverture réels de
marchés football sur Polymarket ; la disponibilité réelle de prix
historiques sur un marché résolu ; tout nom d'équipe Polymarket réel avec
un niveau de preuve suffisant pour peupler un mapping canonique ; le
mécanisme de résolution appliqué spécifiquement à un marché football.

**Une expérience scientifique n'est pas possible maintenant.** Les
conditions du §14 doivent d'abord être remplies, notamment un accès réel
(ou une fourniture manuelle) et la levée du doute spécifique sur les prix
historiques post-résolution (§7).

---

*Audit réalisé sans backtest, sans calcul de ROI/profit, sans recherche de
seuil, sans sélection rétrospective de traders, sans expérience
prédictive. Aucune modification de `final_engine`, aucune activation de
`BET`, aucune fixation de `min_edge_threshold`. Seule modification de code
: enrichissement documentaire (docstring) de `client.py`, aucun changement
de comportement, suite complète re-vérifiée verte. Fin de l'audit - aucune
Phase N ni expérience d'edge n'est entreprise à la suite de ce document.*
