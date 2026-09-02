# Pilote exploratoire : signal trader Polymarket vs marché (21 marchés / 7 matchs)

Expérience exploratoire construite exclusivement à partir des données déjà
collectées (`research/polymarket_raw_exports/`) et déjà auditées
(`research/polymarket_universe_collection_report.md`,
`research/polymarket_trader_depth_audit.md`). **Aucun nouveau fetch réseau.**
Aucun modèle de production ni pipeline de betting n'a été modifié. Aucun
classement de traders par P&L n'a été produit ; aucun wallet n'a été
sélectionné parce qu'il a "gagné" un match observé — les seuils de récurrence
utilisés (section 8) sont définis en marche avant (walk-forward), sans jamais
regarder le résultat du match courant.

**Avertissement liminaire, valable pour tout ce document** : avec 7 matchs et
20-21 marchés, aucun résultat ci-dessous n'a de valeur de preuve statistique.
C'est un test exploratoire au sens strict — il sert à décider s'il vaut la
peine d'investir dans un panel plus large, pas à trancher définitivement la
question.

## 1. Question et hypothèse

**Question centrale** : les positions des traders Polymarket prises avant le
kickoff contiennent-elles une information prédictive supplémentaire par
rapport au prix du marché lui-même ?

**Hypothèse testée (H1)** : un signal agrégé construit à partir des trades
pré-kickoff améliore (ou au moins égale) la performance prédictive du prix de
marché seul, mesurée en Brier score / log loss sur les 7 résultats de match
observés.

**Hypothèse nulle (H0)** : le prix de marché contient déjà toute
l'information utile ; l'agrégation des positions trader n'apporte rien, ou
dégrade la prédiction par rapport au marché seul.

## 2. Données utilisées

- 21 marchés moneyline, 7 matchs, 1 672 trades dédupliqués, 529 wallets
  (rapport de collecte précédent).
- Métadonnées de résolution (`resolved_outcome`) utilisées **uniquement**
  comme vérité terrain ex-post pour scorer les prédictions — jamais comme
  intrant du signal.
- Kickoff : champ `endDate` des 21 marchés (= `startTime` des événements,
  correspondance vérifiée dans l'audit de profondeur précédent sur les 7
  matchs).

## 3. Construction PIT

Pour chaque marché : seuls les trades avec `timestamp_utc < kickoff` sont
retenus ("PIT" = point-in-time / pré-kickoff). Aucun trade ≥ kickoff,
résolution ou résultat n'a été utilisé pour construire un signal.

Pour chaque wallet × match : position nette PIT reconstruite en sommant les
trades PIT par token (BUY = +taille, SELL = −taille), position de départ
supposée nulle. Seuls les wallets avec une position nette PIT non nulle sur
au moins un token du match (393 observations wallet × match, cf. audit de
profondeur) alimentent les signaux B et C ci-dessous.

**Un marché sur 21 n'a aucun trade PIT** : "FC Gagra win" (0 trade avant
kickoff, 9 après) — ni prix de marché PIT ni signal trader n'existent pour ce
marché précis. Il est exclu des scores marché-niveau et du score match-niveau
à 3 voies pour `geo1-gag-ibe-2026-08-31` (dont les 2 autres marchés restent
scorés individuellement). **20/21 marchés et 6/7 matchs (à 3 voies)** sont
effectivement exploitables.

## 4. Définition des signaux

### Signal A — Market

Probabilité implicite = prix du **dernier trade PIT** du marché (converti en
probabilité "Yes" : `price` si le trade porte sur le token Yes, `1 − price`
s'il porte sur le token No — les deux tokens étant en pratique quasi
complémentaires sur ces marchés neg-risk). C'est la meilleure estimation du
"prix juste avant kickoff" disponible dans les trades collectés (pas d'accès
à l'order book / mid-price, seulement aux trades exécutés).

### Signal B — Agrégation brute des traders

Sur les trades PIT des wallets qualifiés (exposition nette non nulle) :

- volume BUY / SELL (notionnel $ = prix × taille) ;
- nombre de wallets exposés ;
- exposition nette agrégée = flux notionnel signé vers "Yes"
  (BUY Yes et SELL No comptent +, SELL Yes et BUY No comptent −) ;
- déséquilibre = flux net signé / flux total absolu, borné dans [−1, 1] ;
- **signal trader = 0,5 + 0,5 × déséquilibre** — règle fixe choisie a priori
  (pas ajustée sur ces 7 matchs), qui transforme le déséquilibre BUY/SELL en
  une pseudo-probabilité comparable au prix de marché ;
- prix moyen pondéré d'entrée (VWAP des trades BUY, en probabilité implicite),
  reporté à titre descriptif (n'est pas la valeur utilisée pour le scoring).

### Signal C — Traders récurrents (walk-forward, sans fuite du futur)

Même construction que le Signal B, mais restreinte aux wallets ayant déjà
tradé **≥2** (puis **≥3**) matchs du panel **strictement avant** le match
courant, au sens du kickoff. L'ordre chronologique des 7 kickoffs est :

1. FK Liepaja vs. Riga FC — 2026-08-31 14:30 UTC
2. FC Gagra vs. FC Iberia 1999 — 2026-08-31 15:00 UTC *(ex æquo)*
2. FC Torpedo Kutaisi vs. FC Meshakhte Tkibuli — 2026-08-31 15:00 UTC *(ex æquo)*
4. Sumqayit FK vs. Qarabag FK — 2026-08-31 16:15 UTC
5. FC Dinamo Tbilisi vs. FC Dila Gori — 2026-08-31 17:00 UTC
6. Lanzhou Longyuan Athletic vs. Beijing Guoan — 2026-09-01 11:35 UTC *(ex æquo)*
6. Dalian Yingbo FC vs. Shanghai Shenhua FC — 2026-09-01 11:35 UTC *(ex æquo)*

Pour un wallet, le compteur "matchs historiques" au match *m* ne compte que
les matchs d'ordre strictement antérieur à *m* — jamais *m* lui-même ni un
match ultérieur. Conséquence mécanique attendue et vérifiée : les 3 premiers
matchs (Liepaja, Gagra, Torpedo — ex æquo en tête de chronologie) n'ont
**aucun** wallet éligible ≥2, puisqu'aucune activité antérieure n'existe
encore dans le panel à ce stade.

## 5. Résultats

### 5.1 Niveau marché (20/21 marchés scorés, tous wallets qualifiés)

| Match | Marché | y | p_market | p_trader | p_combiné | n wallets | Brier (m/t/c) |
|---|---|---|---|---|---|---|---|
| Sumqayit vs Qarabag | Qarabag win | 1 | 0.726 | 0.663 | 0.694 | 8 | 0.075 / 0.114 / 0.093 |
| Lanzhou vs Beijing | Lanzhou win | 0 | 0.075 | 0.085 | 0.080 | 37 | 0.006 / 0.007 / 0.006 |
| Lanzhou vs Beijing | draw | 0 | 0.130 | 0.031 | 0.081 | 26 | 0.017 / 0.001 / 0.007 |
| Lanzhou vs Beijing | Beijing win | 1 | 0.830 | 0.963 | 0.897 | 179 | 0.029 / 0.001 / 0.011 |
| Dalian vs Shanghai | Dalian win | 1 | 0.360 | 0.197 | 0.279 | 26 | 0.410 / 0.644 / 0.520 |
| Dalian vs Shanghai | draw | 0 | 0.250 | 0.587 | 0.419 | 18 | 0.062 / 0.345 / 0.175 |
| Dalian vs Shanghai | Shanghai win | 0 | 0.401 | 0.704 | 0.553 | 51 | 0.161 / 0.496 / 0.306 |
| Tbilisi vs Dila Gori | Tbilisi win | 1 | 0.490 | 0.972 | 0.731 | 16 | 0.260 / 0.001 / 0.072 |
| Tbilisi vs Dila Gori | draw | 0 | 0.290 | 1.000 | 0.645 | 16 | 0.084 / 1.000 / 0.416 |
| Tbilisi vs Dila Gori | Dila Gori win | 0 | 0.248 | 0.450 | 0.349 | 2 | 0.061 / 0.203 / 0.122 |
| Gagra vs Iberia | draw | 0 | 0.270 | 1.000 | 0.635 | 1 | 0.073 / 1.000 / 0.403 |
| Gagra vs Iberia | Iberia win | 0 | 0.500 | 0.210 | 0.355 | 9 | 0.250 / 0.044 / 0.126 |
| Torpedo vs Meshakhte | Torpedo win | 0 | 0.700 | 0.964 | 0.832 | 14 | 0.490 / 0.929 / 0.692 |
| Torpedo vs Meshakhte | draw | 0 | 0.180 | 0.737 | 0.458 | 4 | 0.032 / 0.543 / 0.210 |
| Torpedo vs Meshakhte | Meshakhte win | 1 | 0.110 | 0.587 | 0.349 | 4 | 0.792 / 0.170 / 0.424 |
| Liepaja vs Riga | Liepaja win | 1 | 0.130 | 0.456 | 0.293 | 14 | 0.757 / 0.295 / 0.500 |
| Liepaja vs Riga | draw | 0 | 0.190 | 0.154 | 0.172 | 6 | 0.036 / 0.024 / 0.030 |
| Liepaja vs Riga | Riga win | 0 | 0.700 | 0.892 | 0.796 | 19 | 0.490 / 0.795 / 0.633 |
| Sumqayit vs Qarabag | Sumqayit win | 0 | 0.110 | 0.059 | 0.084 | 7 | 0.012 / 0.003 / 0.007 |
| Sumqayit vs Qarabag | draw | 0 | 0.180 | 0.140 | 0.160 | 5 | 0.032 / 0.019 / 0.026 |

*(marché exclu : "FC Gagra win", 0 trade PIT — pas de p_market ni de signal
trader calculables.)*

**Moyennes (n = 20)** :

| | Market seul | Market + Trader (moy. simple) | Trader seul |
|---|---|---|---|
| Brier moyen | **0.2065** | 0.2390 | 0.3318 |
| Log loss moyen | **0.6137** | 0.6604 | 1.0778 |
| Accuracy directionnelle | **70,0 %** | — | 55,0 % |

### 5.2 Niveau match (6/7 matchs, score multi-classe à 3 voies, prix des 3
marchés du match renormalisés pour sommer à 1)

| Match | Vainqueur réel | Brier multi-classe (m/t/c) | Top-pick correct (marché / trader) |
|---|---|---|---|
| Sumqayit vs Qarabag | Qarabag win | 0.125 / 0.084 / 0.103 | Oui / Oui |
| Lanzhou vs Beijing | Beijing win | 0.060 / 0.019 / 0.035 | Oui / Oui |
| Dalian vs Shanghai | Dalian win | 0.633 / 1.132 / 0.863 | Non / Non |
| Tbilisi vs Dila Gori | Tbilisi win | 0.411 / 0.563 / 0.481 | Oui / Non |
| Torpedo vs Meshakhte | Meshakhte win | 1.323 / 0.834 / 1.048 | Non / Non |
| Liepaja vs Riga | Liepaja win | 1.267 / 0.847 / 1.046 | Non / Non |

**Moyennes (n = 6)** : Brier multi-classe — market 0.6366, trader 0.5798,
combiné 0.5959. Top-pick accuracy — market 3/6 (50 %), trader 2/6 (33 %).

**Ce résultat contredit numériquement le résultat marché-niveau** (où le
marché bat systématiquement le trader). Avec seulement 6 observations, cette
inversion est dominée par 2 matchs (Torpedo vs Meshakhte et Liepaja vs Riga)
où le marché s'est trompé de façon spectaculaire (favoris à 70-83 % qui
perdent) — le trader, bien que lui aussi dans le mauvais sens sur ces deux
matchs, l'était un peu moins fort en probabilité. Ce n'est pas une preuve que
le trader "voit" mieux le résultat ; c'est un artefact de très petit
échantillon (voir section 9). Le niveau marché (20 observations, plus
granulaire et plus stable) est la lecture la plus fiable disponible ici, et
elle est univoque : le marché domine.

## 6. Brier / log loss — synthèse

| Coupe | n | Brier market | Brier trader | Brier combiné | Logloss market | Logloss trader | Logloss combiné |
|---|---|---|---|---|---|---|---|
| Marché, tous wallets | 20 | 0.2065 | 0.3318 | 0.2390 | 0.6137 | 1.0778 | 0.6604 |
| Marché, ≥2 matchs historiques | 10 | 0.1116 | 0.4709 | 0.2348 | 0.3719 | 1.7451 | 0.6492 |
| Marché, ≥3 matchs historiques | 10 | 0.1116 | 0.4844 | 0.2307 | 0.3719 | 1.7500 | 0.6349 |
| Match, tous wallets (3 voies) | 6 | 0.6366 | 0.5798 | 0.5959 | 1.0979 | 0.9768 | 0.9874 |

**Sur les 3 coupes marché-niveau (les plus granulaires, n=10-20), le résultat
est cohérent et sans ambiguïté : le marché seul bat systématiquement le
trader seul, et la combinaison naïve 50/50 dégrade toujours la performance par
rapport au marché seul.** Seule la coupe match-niveau (n=6, la plus petite et
la plus bruitée) inverse ce constat, pour les raisons de petit échantillon
détaillées en 5.2.

## 7. Analyse de calibration

Avec 20 observations, une courbe de calibration par bin fin n'a aucun sens
statistique. Un découpage grossier en 2 buckets (prédiction < 0,5 vs ≥ 0,5)
donne, niveau marché tous wallets :

| Signal | Bucket | n | Prédiction moyenne | Fréquence réelle |
|---|---|---|---|---|
| Market | < 0,5 | 15 | 0.228 | 0.267 |
| Market | ≥ 0,5 | 5 | 0.691 | 0.400 |
| Trader | < 0,5 | 9 | 0.198 | 0.222 |
| Trader | ≥ 0,5 | 11 | **0.825** | **0.364** |

Le marché est raisonnablement calibré sur le bucket bas (22,8 % prédit vs
26,7 % réalisé) et surconfiant sur le bucket haut (69,1 % prédit vs 40 %
réalisé, n=5 seulement — à ne pas surinterpréter). **Le signal trader est
nettement plus surconfiant sur son bucket haut : 82,5 % prédit en moyenne pour
seulement 36,4 % de réalisation.**

Base rate globale (fréquence de "Yes" sur les 20 marchés scorés) = 30 %.
Moyenne des probabilités prédites : marché 34,3 % (proche de la base rate),
**trader 54,3 % (nettement au-dessus)**. Le signal trader tel que construit
ici est donc **systématiquement biaisé à la hausse** — voir la limite 9.3 sur
la construction du déséquilibre BUY/SELL, qui explique probablement une bonne
partie de cette surconfiance mécanique plutôt qu'une réelle divergence
d'opinion informée.

## 8. Robustesse traders récurrents

| Coupe | n marchés scorés | n wallets médian/marché | Brier trader | Accuracy directionnelle trader |
|---|---|---|---|---|
| Tous wallets qualifiés | 20 | — | 0.3318 | 55,0 % |
| ≥2 matchs historiques (walk-forward) | 10 | 2-5 | 0.4709 | 50,0 % |
| ≥3 matchs historiques (walk-forward) | 10 | 1-4 | 0.4844 | 40,0 % |

**La restriction aux traders récurrents n'améliore rien — elle dégrade la
performance et la précision directionnelle.** Ceci doit être lu avec beaucoup
de prudence : les groupes ≥2 et ≥3 comptent souvent seulement 1 à 5 wallets
par marché (cf. tableau détaillé du script), ce qui rend le signal
extrêmement bruyant et sujet à des valeurs dégénérées (`p_trader = 0` ou `1`
dès qu'un seul wallet domine le flux). Les 3 premiers matchs de la
chronologie (Liepaja, Gagra, Torpedo) sont structurellement exclus de cette
analyse (0 wallet éligible, aucune fuite du futur autorisée) — seuls
10 des 20 marchés scorés bénéficient d'au moins 1 wallet ≥2 matchs
historiques. **Aucun wallet du panel n'atteint 4, 5, 6 ou 7 matchs
historiques avant un match donné** (le maximum de récurrence *observable en
amont* d'un match, walk-forward, est 3 — atteint par une poignée de wallets
seulement sur les tout derniers matchs de la chronologie).

## 9. Limites

1. **Échantillon minuscule.** 20 marchés (6-10 selon la coupe), 6-7 matchs.
   Aucun test de significativité (t-test, bootstrap) n'a été calculé car il
   n'aurait aucune puissance à cette taille — les écarts observés peuvent
   entièrement s'expliquer par le hasard.
2. **Kickoff = heure programmée, pas confirmée.** Comme déjà noté dans
   l'audit de profondeur : `endDate`/`startTime` est la meilleure valeur
   disponible, mais reste déclarative (pas de confirmation d'heure réelle de
   coup d'envoi ni de détection de report).
3. **Construction du Signal B potentiellement biaisée.** Le panel est
   massivement BUY-only (97,5 % des observations wallet × match, cf. audit de
   profondeur) : très peu de SELL existent pour équilibrer le flux signé. La
   règle `0,5 + 0,5 × déséquilibre` peut donc mécaniquement pousser vers des
   valeurs extrêmes (proches de 0 ou 1) dès qu'un petit nombre de wallets
   achète unanimement un côté — ce qui est structurel à la façon dont les
   utilisateurs Polymarket interagissent avec l'interface (achat direct de
   l'outcome qu'ils pensent vrai, plutôt que vente à découvert de l'autre),
   pas nécessairement le signe d'une information distincte du marché. Une
   autre formulation du signal (ex. VWAP du prix d'entrée plutôt
   qu'imbalance BUY/SELL, ou pondération par profondeur/liquidité) pourrait
   donner un résultat différent — non testé ici, hors scope de ce pilote.
4. **Un marché sans aucun trade PIT** ("FC Gagra win") — exclu, réduisant
   l'échantillon marché-niveau à 20/21 et le score match-niveau 3-voies à
   6/7.
5. **Combinaison naïve non optimisée.** La règle de combinaison
   marché+trader (moyenne simple 50/50) est fixée a priori, comme demandé —
   elle n'a pas été calibrée pour maximiser la performance sur ces 7 matchs.
   Un poids différent (ex. 90 % marché / 10 % trader) donnerait
   mécaniquement un résultat plus proche du marché seul ; ceci n'a pas été
   exploré pour éviter tout surapprentissage sur un échantillon aussi petit.
6. **Aucune walk-forward temporelle inter-jours** : les 7 matchs couvrent
   une fenêtre de ~40 heures (30 août - 1er septembre 2026) — impossible de
   distinguer un effet "compétence stable dans le temps" d'un simple
   artefact de cette fenêtre courte (déjà noté dans l'audit de profondeur).
7. **Pas de résolution d'identité wallet, pas de vérification de solde
   on-chain** — mêmes réserves que l'audit de profondeur précédent.

## 10. Verdict

### **B — Signal faible / ambigu, échantillon insuffisant pour trancher**

Les preuves disponibles ne montrent **pas** d'avantage prédictif du signal
trader tel que construit ici. Au contraire, au niveau le plus granulaire et
le plus stable (marché, n=20), le marché domine systématiquement sur les 3
coupes testées (tous wallets, ≥2, ≥3 matchs historiques), avec une
combinaison naïve qui dégrade toujours la performance par rapport au marché
seul, et une accuracy directionnelle du signal trader qui tombe à 40-55 %
(proche ou en-dessous du hasard). Ce n'est pas un verdict C (signal nul)
pur et simple, pour deux raisons honnêtes :

- le résultat s'inverse au niveau match (n=6, le plus petit et le plus
  instable des deux niveaux d'analyse) — assez pour ne pas conclure à un
  signal strictement nul avec certitude ;
- la construction du Signal B est probablement biaisée par la structure
  BUY-only du panel (section 9.3), donc "le signal tel que construit ici ne
  bat pas le marché" n'équivaut pas rigoureusement à "aucune information
  trader n'existe" — une autre construction du signal pourrait donner un
  résultat différent, non testé.

Mais ce n'est pas non plus un A : rien dans les résultats — ni la
performance moyenne, ni la calibration, ni l'accuracy directionnelle —
ne va dans le sens d'un signal "clairement intéressant".

## 11. Recommandation : continuer ou abandonner cette piste

**Continuer, mais sans changer l'objectif immédiat : élargir d'abord le
panel à ~50 matchs (recommandation déjà posée dans l'audit de profondeur),
sans surinvestir dans le raffinement du signal tant que la taille
d'échantillon reste le facteur limitant.** Ce pilote ne fournit aucune preuve
qu'il faille abandonner l'hypothèse d'un signal trader — mais il ne fournit
pas non plus de motif d'accélérer ou d'investir davantage dans cette piste
avant d'avoir un échantillon capable de trancher. Deux ajustements
méthodologiques à prévoir pour la prochaine itération (pas pour cette
collecte de 50 matchs elle-même, qui reste inchangée) :

1. Tester au moins une formulation alternative du Signal B moins sensible au
   déséquilibre BUY/SELL structurel (ex. VWAP du prix d'entrée, ou part de
   wallets — pas de dollars — pariant sur chaque issue), pour vérifier que le
   résultat actuel n'est pas un artefact de cette seule formulation.
2. Conserver strictement la même discipline PIT / walk-forward pour la
   prochaine passe, en réutilisant le kickoff = `endDate`/`startTime` déjà
   validé.

---

## Résumé très court

- **Matchs effectivement utilisables** : 7/7 pour la construction PIT ;
  6/7 pour le score match-niveau à 3 voies (1 marché sans trade PIT sur le
  match Gagra/Iberia).
- **Snapshots PIT (marchés scorés)** : 20/21.
- **Résultat Market seul** : Brier 0.2065, log loss 0.6137, accuracy
  directionnelle 70 % (n=20).
- **Résultat Market + Traders (moyenne simple)** : Brier 0.2390, log loss
  0.6604 — **pire que le marché seul**.
- **Résultat Traders seul** : Brier 0.3318, log loss 1.0778, accuracy
  directionnelle 55 % (40-50 % pour les traders récurrents) — **pire que le
  marché seul, à chaque coupe testée**.
- **Verdict : B — signal faible/ambigu, échantillon insuffisant**, avec une
  tendance empirique plutôt défavorable au signal trader tel que construit
  (pas un C ferme, à cause de l'inversion au niveau match à n=6 et du biais
  de construction probable du signal).
- **Vaut-il la peine de collecter les 50 matchs supplémentaires ?** Oui, mais
  pour la raison déjà identifiée dans l'audit de profondeur (profondeur
  wallet × match insuffisante), pas parce que ce pilote a révélé un signal
  prometteur à confirmer. À 7 matchs, aucune conclusion positive ou négative
  n'est fiable — l'élargissement reste la seule façon d'obtenir une réponse
  exploitable, mais sans garantie que le résultat s'améliore : sur les
  données actuelles, le marché bat le signal trader construit ici, pas
  l'inverse.
