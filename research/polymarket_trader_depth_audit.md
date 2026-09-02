# Audit de suffisance statistique PIT — panel neutre Polymarket (21 marchés / 7 matchs)

Construit exclusivement à partir des 21 marchés moneyline déjà collectés et validés
(`research/polymarket_universe_collection_report.md`) et de leurs trades bruts
(`research/polymarket_raw_exports/trades_market_*.json`). Aucun nouveau fetch réseau
n'a été nécessaire. Aucun code de production n'a été modifié ; aucun modèle ni
pipeline de betting n'a été touché. Aucun classement de performance des traders
n'est produit dans ce document.

## 1. Méthodologie PIT

### 1.1 Unité d'analyse

L'unité d'analyse principale est **wallet × match** (7 matchs), et non
wallet × market (21 marchés). Un même match génère 3 marchés moneyline
(win A / draw / win B) qui ne sont **pas** 3 événements sportifs indépendants :
ce sont 3 formulations mutuellement exclusives d'un seul résultat. Un wallet qui
trade les 3 marchés d'un même match ne fournit qu'**une seule** observation
indépendante du point de vue du résultat sportif sous-jacent, même s'il apparaît
3 fois au niveau wallet × market. Toutes les statistiques de profondeur
(section 3) et d'exposition (section 4) sont donc calculées au niveau match, en
fusionnant les 3 marchés de chaque match par wallet.

### 1.2 Définition du kickoff / decision_time

Les 21 marchés moneyline collectés portent un champ `endDate` dans les
métadonnées (`moneyline_21_markets_metadata.json`), identique pour les 3 marchés
d'un même match. Ce champ n'avait pas été interprété comme un kickoff lors de la
collecte initiale. En recroisant avec le fichier d'événements déjà collecté
précédemment (`events_neutral_soccer_tagslug_closed_2026-09-01.json`, qui contient
les événements complets — moneyline, exact score, first-to-score, etc. — pour
chacun des 7 matchs), on constate que **chaque événement porte un champ
`startTime` explicite, systématiquement identique à `endDate`** sur les 7 matchs
vérifiés. `startTime` est le champ le plus explicite d'intention "heure de
coup d'envoi" fourni par Polymarket (les descriptions textuelles des marchés
"exact score" le confirment, ex. *"scheduled for September 1, 2026 at 7:35 AM ET"*
= `2026-09-01T11:35:00Z`, exactement `startTime`/`endDate`).

**Le kickoff utilisé ici est donc `endDate` (= `startTime`), une valeur
effectivement présente et sourcée dans les données déjà collectées — pas une
valeur inventée.** Deux réserves doivent néanmoins être signalées explicitement :

- C'est l'heure de coup d'envoi **programmée**, telle que déclarée par Polymarket
  au moment de la création du marché. Elle peut différer de l'heure réelle en cas
  de retard/report (aucune correction de ce type n'est visible dans les données
  actuelles — aucun signal de report n'est disponible).
- **Le marché reste ouvert au trading après ce timestamp** (`enableOrderBook: true`
  dans les événements), et les trades observés le confirment massivement : voir
  section 8.1. Ce n'est donc pas un "cutoff" de marché, seulement le meilleur
  repère disponible pour distinguer trade pré-match et trade en direct/post-coup
  d'envoi.

**Trade PIT (pre-kickoff)** = trade dont `timestamp_utc < endDate` du match
correspondant. **Aucun trade post-kickoff, aucune résolution et aucun résultat de
match n'a été utilisé pour construire les métriques d'exposition des sections 3-5.**
La résolution (`resolved_outcome`) n'a servi qu'au contrôle qualité déjà effectué
lors de la collecte (rapport précédent), jamais ici.

### 1.3 Reconstruction wallet × match

Pour chaque wallet ayant au moins un trade PIT sur un match donné, sont
reconstruits à partir des seuls trades PIT :

- nombre de trades PIT et nombre total de trades (PIT + post-kickoff, pour
  contexte) ;
- marchés du match tradés (PIT et all-time) ;
- BUY / SELL (comptes et volumes, en parts et en notionnel $ = prix × taille) ;
- position nette par token = Σ(taille BUY) − Σ(taille SELL), en supposant une
  position de départ nulle (voir limite en section 8.2) ;
- "exposition nette non nulle au kickoff" = au moins un token du match a une
  position nette PIT non nulle (seuil |position| > 1e-6) ;
- prix moyen d'entrée = VWAP des trades BUY PIT (Σ prix×taille / Σ taille) ;
- dernier trade PIT et délai avant kickoff (`kickoff − dernier_trade_PIT`) ;
- activité multi-issues = trades PIT sur ≥ 2 des 3 marchés du match ;
- conditionId(s) et token(s)/outcome(s) concernés.

Le fichier détaillé (394 lignes wallet × match avec activité PIT, plus les 267
paires sans activité PIT) est conservé dans le scratchpad de session — non commité
(données dérivées, reproductibles depuis les payloads déjà commités/gitignorés).

## 2. Universe summary

| Métrique | Valeur |
|---|---|
| Matchs | 7 |
| Marchés moneyline | 21 (3 par match) |
| Trades dédupliqués (tous marchés, tout horaire) | 1 672 |
| Wallets distincts (toute activité, tout marché) | 529 |
| Observations **wallet × market** (any time) | 804 |
| Observations **wallet × match** (any time) | 661 |
| Observations **wallet × match avec ≥1 trade PIT** | 394 |
| Observations **wallet × match avec exposition nette non nulle au kickoff (PIT)** | 393 |

Le nombre d'observations wallet × match (661, ou 394 en restriction PIT) est
l'unité pertinente pour toute inférence future — **pas** les 804 wallet × market,
qui sur-comptent artificiellement par un facteur ~1,2× à cause des 3 marchés
liés par match (voir section 7).

## 3. Wallet × match depth

### 3.1 Distribution du nombre de matchs distincts tradés par wallet (any time, 529 wallets)

| Matchs tradés | Wallets |
|---|---|
| 1 | 439 |
| 2 | 68 |
| 3 | 12 |
| 4 | 3 |
| 5+ | 7 |

### 3.2 Seuils cumulés (any time)

| Seuil | Wallets |
|---|---|
| ≥ 2 matchs | 90 |
| ≥ 3 matchs | 22 |
| ≥ 5 matchs | 7 |
| ≥ 7 matchs | 0 |
| ≥ 10 matchs | N/A (univers ne contient que 7 matchs) |

**83 % des wallets (439/529) n'ont tradé qu'un seul match de cet univers.**
Seuls 7 wallets (1,3 %) ont touché 5 matchs ou plus, et aucun n'a touché les 7.

## 4. Distribution des expositions au kickoff (PIT)

C'est la métrique demandée comme prioritaire. Elle est proche, mais pas
identique, de la distribution "any time" ci-dessus : restreindre aux trades
PIT élimine une partie substantielle de l'activité (voir section 8.1), donc la
population de wallets "actifs pré-match" est plus petite que la population
"actifs à un moment quelconque".

### 4.1 Distribution du nombre de matchs avec exposition nette non nulle au kickoff

| Matchs avec exposition PIT non nulle | Wallets |
|---|---|
| 1 | 295 |
| 2 | 28 |
| 3 | 5 |
| 4 | 0 |
| 5+ | 5 |

### 4.2 Seuils cumulés (exposition nette non nulle au kickoff)

| Seuil | Wallets |
|---|---|
| ≥ 2 matchs | 38 |
| ≥ 3 matchs | 10 |
| ≥ 5 matchs | 5 |
| ≥ 7 matchs | 0 |
| ≥ 10 matchs | N/A |

Sur les 333 wallets ayant une exposition PIT non nulle sur au moins un match,
**89 % (295/333) n'ont d'exposition PIT que sur un seul match**. Seuls
**10 wallets** ont une exposition PIT sur 3 matchs ou plus, et **5** en ont sur
5 matchs ou plus (le maximum observable étant 7).

*(Pour référence, la distribution "≥1 trade PIT" — sans filtrer sur position
nette — est numériquement quasi identique à la distribution "exposition non
nulle" : 394 vs 393 observations, la quasi-totalité des wallets actifs PIT
finissant avec une position nette non nulle, cohérent avec le déséquilibre
BUY/SELL massif de la section 6.)*

## 5. Distribution des volumes (PIT, notionnel $ par wallet × match)

Basé sur les 394 observations wallet × match avec ≥1 trade PIT. Le
"notionnel" = Σ(prix × taille) sur BUY + SELL PIT pour ce wallet sur ce match
(mesure en dollars-équivalents, pas en parts).

| Statistique | Valeur |
|---|---|
| n | 394 |
| min | 0.01 $ |
| p25 | 5.00 $ |
| médiane | 39.88 $ |
| p75 | 58.30 $ |
| max | 8 000.00 $ |
| n(< 5 $ notionnel) | 112 (28,4 %) |
| n(≥ 50 $ notionnel) | 109 (27,7 %) |

**Plus d'un quart des observations wallet × match (28,4 %) représentent moins
de 5 $ de notionnel** — des positions quasi symboliques, pas des paris
informatifs. À l'autre bout, seuls 27,7 % dépassent 50 $, seuil raisonnable pour
une position "significative". Le reste (≈44 %) est dans une zone intermédiaire.
La distribution est très asymétrique (médiane 40 $, max 8 000 $) : quelques
wallets portent l'essentiel du volume en dollars, la masse des observations est
de faible montant.

### 5.1 Distribution du nombre de trades par wallet × match (PIT)

| Statistique | Valeur |
|---|---|
| n | 394 |
| min | 1 |
| p25 | 1 |
| médiane | 1 |
| p75 | 1 |
| max | 24 |
| n(exactement 1 trade) | 299 (75,9 %) |

**76 % des observations wallet × match ne comportent qu'un seul trade PIT.**
La grande majorité du panel est donc composée de positions "one-shot", pas de
construction de position itérative — ce qui limite fortement ce qu'on peut
inférer sur la conviction ou la stratégie d'un wallet à partir d'une seule
observation.

## 6. Distribution BUY/SELL (wallet × match, PIT)

| Catégorie | Wallet × match |
|---|---|
| BUY uniquement | 384 (97,5 %) |
| SELL uniquement | 5 (1,3 %) |
| BUY et SELL (les deux côtés) | 5 (1,3 %) |

Le panel est presque exclusivement composé de positions BUY-only avant kickoff —
comportement cohérent avec un flux retail directionnel plutôt qu'un
market-making ou un ajustement actif de position. Ceci limite la pertinence de
la métrique "prix moyen d'entrée" pour la grande majorité des wallets (une seule
transaction = un seul prix, pas de moyenne réelle) et confirme que la quasi-
totalité des positions PIT non nulles proviennent d'achats, pas de ventes à
découvert ou de couvertures.

Activité multi-issues (trades PIT sur ≥2 des 3 marchés du même match) :
**58 / 394 observations wallet × match (14,7 %)**. La plupart des wallets actifs
PIT ne tradent qu'une seule des 3 issues du match.

## 7. Dépendance intra-match

Les 3 marchés moneyline d'un même match sont **fortement dépendants** : ils
partagent le même résultat sportif sous-jacent (un seul des 3 peut résoudre
"Yes"), le même kickoff, et souvent les mêmes wallets actifs sur plusieurs des
3 marchés. Traiter wallet × market comme unité d'observation indépendante
gonflerait artificiellement le nombre d'observations et biaiserait toute future
estimation de compétence par pseudo-réplication.

| Unité de comptage | N observations (any time) |
|---|---|
| wallet × market | 804 |
| wallet × match | 661 |

Ratio 804/661 ≈ 1,22 — l'inflation réelle est plus modeste qu'un facteur 3
théorique, car la majorité des wallets ne tradent qu'un seul des 3 marchés d'un
match donné (cohérent avec la faible activité multi-issues mesurée en
section 6). Il reste néanmoins impératif d'utiliser **wallet × match** comme
unité pour toute inférence statistique future — jamais wallet × market.

## 8. Limites des données

### 8.1 Le trading se poursuit massivement après le kickoff (in-play)

Contrôle effectué marché par marché (trades PIT vs post-kickoff, sur le proxy
`endDate`/`startTime`) :

| Match | Marché | Pré-kickoff | Post-kickoff | % pré-kickoff |
|---|---|---|---|---|
| chfa-lan-bjg | Lanzhou win | 71 | 50 | 58,7 % |
| chfa-lan-bjg | draw | 38 | 28 | 57,6 % |
| chfa-lan-bjg | Beijing Guoan win | 267 | 331 | 44,6 % |
| chfa-dy-shs | Dalian win | 38 | 101 | 27,3 % |
| chfa-dy-shs | draw | 21 | 28 | 42,9 % |
| chfa-dy-shs | Shanghai win | 82 | 230 | 26,3 % |
| geo1-tbi-gor | Tbilisi win | 20 | 5 | 80,0 % |
| geo1-tbi-gor | draw | 20 | 4 | 83,3 % |
| geo1-tbi-gor | Dila Gori win | 2 | 2 | 50,0 % |
| geo1-gag-ibe | Gagra win | 0 | 9 | 0,0 % |
| geo1-gag-ibe | draw | 1 | 3 | 25,0 % |
| geo1-gag-ibe | Iberia win | 11 | 2 | 84,6 % |
| geo1-tku-met | Torpedo win | 20 | 12 | 62,5 % |
| geo1-tku-met | draw | 4 | 1 | 80,0 % |
| geo1-tku-met | Meshakhte win | 4 | 11 | 26,7 % |
| lva1-lie-rfc | Liepaja win | 14 | 65 | 17,7 % |
| lva1-lie-rfc | draw | 7 | 18 | 28,0 % |
| lva1-lie-rfc | Riga win | 20 | 28 | 41,7 % |
| aze1-sum-qar | Sumqayit win | 8 | 20 | 28,6 % |
| aze1-sum-qar | draw | 6 | 1 | 85,7 % |
| aze1-sum-qar | Qarabag win | 16 | 53 | 23,2 % |

La part de trades pré-kickoff varie de **0 % à 85,7 %** selon le marché, sans
motif évident (ni par ligue, ni par côté favori/outsider). Cela confirme que ces
marchés Polymarket restent activement tradés pendant le match (`enableOrderBook`
actif, pas de coupure automatique au coup d'envoi). Conséquence directe : la
restriction PIT n'est pas un simple sous-échantillonnage proportionnel — elle
élimine une fraction très variable (14 % à 100 %) de l'activité totale selon le
marché, et fait chuter le nombre d'observations utilisables de 661 (wallet ×
match any time) à 394 (wallet × match PIT).

### 8.2 Pas de solde de position réelle (position de départ supposée nulle)

Les données collectées sont des **trades**, pas des positions/soldes de compte.
L'exposition nette par wallet × match × token est reconstruite en sommant les
trades PIT observés, en supposant qu'un wallet part de zéro sur ce token à
l'ouverture du marché. C'est une hypothèse raisonnable dans ce contexte
(un token de marché n'existe qu'à partir de la création du marché) mais elle
n'est **pas vérifiée** contre un solde on-chain ou une API de positions —
aucune vérification indépendante n'a été effectuée.

### 8.3 Kickoff programmé, pas confirmé exécuté

Voir section 1.2. Le proxy `endDate`/`startTime` est la meilleure valeur
disponible mais reste une heure **programmée**, pas une confirmation d'heure de
coup d'envoi réel. Aucun signal de report/retard n'est présent dans les données
actuelles pour ces 7 matchs — mais cette absence de signal ne prouve pas
l'absence de report, seulement l'absence d'information à ce sujet dans les
champs collectés.

**Meilleure méthode pour fiabiliser ce point à l'avenir** : lors de la
prochaine collecte, interroger explicitement le endpoint `gamma-api` pour
l'événement sportif sous-jacent (déjà disponible via le fichier `events_*`
existant, champ `startTime`) et, si un identifiant de fixture externe existe
(ex. lien Flashscore/Sofascore mentionné dans les descriptions de marché comme
sources de résolution), envisager un recoupement avec une source sportive
tierce pour confirmer l'heure réelle de coup d'envoi et détecter d'éventuels
reports — non fait ici, hors-scope de cet audit (pas de nouveau fetch requis
pour répondre à la question posée).

### 8.4 Pas de résolution d'identité wallet

Un même individu ou groupe peut opérer plusieurs adresses wallet ; aucune
tentative de clustering d'identité n'a été faite (ni demandée). Toute future
étude de "compétence persistante" devra garder à l'esprit que l'unité "wallet"
n'est pas garantie équivalente à l'unité "trader".

### 8.5 Univers de 7 matchs, tous collectés le même jour calendaire

Les 7 matchs proviennent tous de la fenêtre de collecte du 30 août au
1er septembre 2026 (voir rapport de collecte précédent). Il n'y a donc **aucune
variation de période** dans cet échantillon — impossible de distinguer un effet
"compétence persistante dans le temps" d'un effet "activité concentrée sur une
fenêtre de 2 jours". C'est une limite structurelle indépendante de la taille de
l'échantillon.

## 9. Recommandation sur la taille du prochain échantillon

### Réponse à la question posée

**Non — avec seulement ces 7 matchs, nous n'avons pas une profondeur wallet ×
match suffisante pour tester sérieusement l'hypothèse d'une compétence
persistante.** Les chiffres le montrent sans ambiguïté :

- Sur 333 wallets ayant une exposition PIT non nulle sur au moins un match,
  **295 (89 %) n'en ont que sur un seul match** — structurellement inutilisables
  pour mesurer une "persistance" (qui nécessite par définition ≥2 observations
  indépendantes par wallet).
- Seuls **10 wallets** atteignent 3 matchs ou plus avec exposition PIT, et
  seulement **5** atteignent 5 matchs ou plus — sur un maximum possible de 7.
- Même en ignorant la contrainte PIT (tolérant toute activité, pas seulement
  pré-match), seuls 22 wallets atteignent 3 matchs et 7 atteignent 5.
- Aucun wallet n'a d'activité sur les 7 matchs.
- 76 % des observations wallet × match PIT ne comportent qu'un seul trade, et
  28 % représentent moins de 5 $ de notionnel — même les rares wallets multi-
  matchs livrent des observations individuellement peu informatives.

Un test de compétence persistante — que ce soit une approche à effets fixes par
wallet, un modèle hiérarchique/bayésien avec shrinkage, ou une simple
corrélation de performance inter-matchs — requiert un nombre minimal
d'observations répétées par wallet nettement supérieur à ce qui est disponible
ici (dans la pratique, de l'ordre de 10 à 30+ observations indépendantes par
wallet pour un effet individuel estimable avec une puissance minimale, et
plusieurs dizaines de wallets à ce niveau de profondeur pour toute inférence de
population). Le panel actuel compte **5 wallets** à 5 matchs et **0** au-delà —
très en-dessous de ce seuil, quel que soit l'angle de modélisation retenu.

### Choix recommandé : **B — élargir d'abord le panel à ~50 matchs**

Justification à partir des distributions observées, pas d'une préférence
générique :

1. **Le déficit est un déficit de profondeur, pas seulement de volume.** Passer
   de 7 à 50 matchs (~×7) ne garantit pas mécaniquement ×7 wallets à 5+ matchs —
   l'échantillon actuel montre qu'une minorité de wallets (≈1,3 % du panel)
   revient sur plusieurs matchs ; ce taux de récurrence pourrait rester stable,
   augmenter (effet réseau, familiarité avec la plateforme) ou stagner. **Il faut
   ré-observer la courbe de profondeur à une échelle intermédiaire avant
   d'investir dans une collecte à 100-200 matchs**, qui reste un processus
   manuel lent (un marché à la fois, aucun accès réseau direct pour cet agent).
2. Passer directement à 100-200 matchs (option C) sans ce point de contrôle
   intermédiaire risque de multiplier l'effort de collecte manuel par 15-30× sans
   garantie que la distribution de récurrence des wallets s'améliore
   proportionnellement — un pari coûteux à faire à l'aveugle.
3. Analyser maintenant les wallets récurrents (option A) n'est pas défendable
   statistiquement : avec seulement 5 wallets à 5 matchs et une majorité
   d'observations à un seul trade de quelques dollars, toute conclusion sur une
   "compétence" serait non significative et potentiellement trompeuse — exactement
   le type de sélection biaisée que les contraintes de ce projet cherchent à
   éviter (« ne cherche pas les meilleurs traders », « pas de sélection sans
   base statistique »).

**Prochaine étape concrète proposée** : élargir la collecte neutre (même
protocole que l'étape 1 — sélection de matchs indépendante des traders) à
environ 50 matchs, puis reproduire cet audit de profondeur à l'identique
(sections 2 à 6) pour mesurer si le taux de wallets multi-matchs et le volume
médian par observation progressent de façon exploitable. Si à 50 matchs la
distribution reste aussi concentrée sur 1 match par wallet, cela indiquera un
problème structurel (base de traders de niche par ligue/marché) qui devra être
diagnostiqué avant d'envisager un passage à 100-200 matchs plutôt que
d'agrandir mécaniquement l'échantillon.

---
*Données sources : `research/polymarket_raw_exports/` (gitignored). Fichiers
intermédiaires (agrégats wallet × match) conservés dans le scratchpad de
session, reproductibles depuis les payloads déjà commités/gitignorés — non
commités eux-mêmes (dérivés, non canoniques).*
