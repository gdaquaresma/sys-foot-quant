# Phase J — recherche et sélection d'une nouvelle source de données pré-match

**Nature de ce document.** Recherche et audit de fournisseurs de données
uniquement. **Aucune expérience scientifique, aucun backtest, aucun code
de production, aucune modification de `final_engine`.** `BET` reste non
activé, `min_edge_threshold` reste `None`. Ce document répond à une seule
question : *quelle nouvelle source de données pré-match apporterait une
information réellement orthogonale au corpus actuel, avec un risque de
fuite temporelle minimal, et par quelle stratégie l'acquérir
progressivement ?*

Documents relus intégralement avant cette recherche : `docs/final_data_strategy.md`
(Phase I), `docs/next_signal_strategy.md` (Phase E),
`docs/research_synthesis_e1_e16.md`, `docs/final_engine_specification.md`,
`docs/operational_validation_specification.md`,
`docs/final_engine_user_guide.md`, `docs/architecture.md`. Recherche web
réalisée le 30/08/2026 (voir sources citées par section) — toute
affirmation sur un fournisseur est tracée à une source publique ; ce qui
n'a pas pu être confirmé par une source publique est explicitement marqué
**non confirmé**.

---

## 1. Objectif

Identifier, parmi les fournisseurs de données pré-match réellement
disponibles aujourd'hui, celui qui permettrait de tester **une** variable
nouvelle avec (a) une information potentiellement orthogonale à tout ce
qui a déjà été testé (E1-E16, Phases D/F/G/H), et (b) une reconstruction
point-in-time **vérifiable**, pas supposée. Conformément à la leçon
centrale de la Phase I : la présence d'une donnée ne justifie jamais son
usage — ici, la présence d'un fournisseur qui *affiche* une information
historique ne justifie jamais son usage sans preuve qu'elle était
**connue avant** chaque match au moment où elle aurait dû l'être.

---

## 2. Critères d'évaluation

Repris et détaillés de l'énoncé, appliqués uniformément à chaque
fournisseur (section 5) :

| Critère | Question posée |
|---|---|
| Couverture championnats | Liga, Ligue 1, Premier League (les trois championnats déjà couverts) sont-ils inclus ? |
| Historique disponible | Couvre-t-il rétroactivement 2024/25 et 2025/26 (le corpus déjà utilisé) ? |
| Granularité temporelle | Snapshot quotidien ? Horaire ? Par match ? Une seule valeur "actuelle" sans historique ? |
| Reconstruction PIT | Peut-on obtenir, **aujourd'hui**, ce qui était connu **avant** un match déjà joué — ou seulement l'état actuel (potentiellement révisé depuis) ? |
| API/fichiers | Existe-t-il un accès programmatique documenté, ou seulement une page web ? |
| Coût | Gratuit / freemium / payant, et à quel palier |
| Conditions d'utilisation | Scraping autorisé ? API officielle ? Limites de redistribution ? |
| Stabilité | Fournisseur établi, actif, documentation à jour ? |
| Couverture compositions/blessures/suspensions/statistiques | Quels champs exacts, avec quelle fraîcheur ? |
| Identifiants équipes/joueurs | Mapping stable, réutilisable pour l'appariement déjà en place (`matching.py`) ? |
| Timestamps | Un timestamp de publication existe-t-il, ou seulement une date de match ? |
| Risque de survivorship bias | Le fournisseur ne montre-t-il que les cas où une information a été confirmée, en supprimant silencieusement les cas non résolus ? |
| Risque de fuite temporelle | Une requête sur un match passé peut-elle retourner un état **révisé après coup** plutôt que l'état réellement connu au moment de la décision ? |
| Archivabilité | Peut-on journaliser/conserver nous-mêmes les réponses pour construire notre propre historique vérifié ? |

---

## 3. Familles de données recherchées

### PRIORITÉ A — composition / disponibilité des joueurs
Compositions probables, compositions officielles, absences, suspensions,
blessures, statut des joueurs, titularisations attendues, gardien
titulaire.

### PRIORITÉ B — contexte pré-match
Jours de repos, congestion du calendrier, nombre de matchs récents,
déplacements, compétition précédente/suivante, changement d'entraîneur,
classement pré-match.

### PRIORITÉ C — forme pré-match indépendante
Performances récentes, xG récents, tirs, tirs cadrés, buts, qualité des
adversaires, forme domicile/extérieur — **retenue uniquement si
reconstructible strictement point-in-time** (contrainte explicite de
l'énoncé).

---

## 4. Grille de classification PIT (appliquée à chaque source, section 5)

- **A — donnée historiquement observable avant le match** : le fournisseur
  démontre (horodatage, snapshot daté, ou nature intrinsèquement
  immuable de la donnée) que la valeur récupérable aujourd'hui pour un
  match passé est **identique** à ce qui était connu avant ce match.
- **B — donnée historique mais publiée/révisée après le match** : la
  donnée existe pour la période passée mais a pu être corrigée,
  complétée ou requalifiée après le fait (ex. un statut de blessure
  finalement confirmé plus tard, une composition rectifiée).
- **C — donnée actuelle reconstruisant le passé** : le fournisseur ne
  garde aucune trace de l'état passé ; interroger son API/scraper son
  site pour un match d'il y a un an retourne l'état **actuel** de la
  base (ex. un statut de blessure « à jour » qui a pu changer depuis),
  jamais l'état réel connu au moment du match.
- **D — donnée impossible à dater précisément** : aucune indication,
  directe ou indirecte, de quand l'information est devenue disponible.

**Règle non négociable, reprise de l'énoncé** : une source classée C ou D
n'est **jamais** utilisée comme feature de production sans un mécanisme
supplémentaire (journalisation prospective indépendante, horodatage
vérifié par un tiers) permettant de reconstruire l'état de connaissance
historique — voir section 9.

---

## 5. Fournisseurs étudiés

### 5.A — Compositions / blessures / suspensions (Priorité A)

**API-Football (api-football.com / api-sports.io)**
- Endpoint `injuries` (introduit en avril 2021) : retourne `player`,
  `team`, `fixture`, `type` (Injury/Suspension), `reason` (ex. « Knee
  Injury », « Suspended 3 matches ») — [documentation officielle](https://www.api-football.com/documentation-v3), [annonce du endpoint](https://www.api-football.com/news/post/new-endpoint-injuries).
  Mise à jour toutes les 4 heures.
- Coverage par ligue exposée via l'endpoint `leagues` (champ `injuries`
  booléen par compétition/saison) — [documentation](https://www.api-football.com/documentation-v3).
- Tarification 2026 : palier gratuit 100 requêtes/jour ; palier « Pro »
  19 $/mois (7 500 req/jour) jusqu'à 39 $/mois (150 000 req/jour) —
  [pricing officiel](https://www.api-football.com/pricing). Les paliers
  payants débloquent un historique plus profond, pas de fonctionnalité
  supplémentaire.
- **Classification PIT : C pour tout usage rétroactif.** Rien dans la
  documentation publique ne garantit que l'endpoint `injuries` interrogé
  aujourd'hui pour un match de 2024/25 renvoie l'état **tel qu'il était
  avant ce match** plutôt que l'état actuellement connu (une blessure
  peut être requalifiée, un joueur peut être retiré rétroactivement de
  la liste une fois son retour confirmé). **Utilisable en A uniquement
  si interrogé prospectivement et journalisé par nous-mêmes**, match par
  match, à partir d'aujourd'hui.

**Sportmonks (sportmonks.com)**
- Données de disponibilité exposées via l'include `sidelined` sur les
  endpoints `teams`/`players`/`fixtures` : `player_id`, `team_id`,
  `season_id`, `type_id`, `category`, `start_date`, `end_date` (peut être
  `null`), `games_missed`, `completed` (booléen) — [documentation officielle](https://docs.sportmonks.com/v3/tutorials-and-guides/tutorials/teams-players-coaches-and-referees/teams), [glossaire](https://www.sportmonks.com/glossary/injuries-and-suspensions/).
  Inclus dans tous les paliers (Starter à Enterprise) — [pricing](https://www.sportmonks.com/football-api/plans-pricing/).
- « Predicted Lineups » (composition estimée avant confirmation
  officielle) : générée à partir des « données historiques, y compris les
  compositions précédentes, blessures et suspensions **connues** » —
  [tutoriel officiel](https://docs.sportmonks.com/v3/tutorials-and-guides/tutorials/includes/predicted-lineups).
  « Premium Expected Lineups » (add-on payant, 159-199 €/mois) publie une
  précision mesurée par compétition (75-88% selon le championnat) —
  [annonce officielle](https://www.sportmonks.com/blogs/premium-expected-lineups/).
- Historique : fixtures/inclus disponibles jusqu'à 3 saisons dans
  l'abonnement standard ; au-delà, add-on historique ponctuel (29 €) —
  [glossaire Seasons](https://www.sportmonks.com/glossary/seasons/).
  **Non confirmé** : si l'add-on historique restitue le `sidelined`
  **tel qu'il était** avant chaque match passé, ou l'état actuellement
  enregistré en base pour cette période — la documentation publique ne
  tranche pas cette question, ce qui est en soi la réponse (absence de
  garantie documentée = ne jamais présumer A).
- **Classification PIT : B/C selon le champ.** `start_date`/`end_date`
  d'un `sidelined` sont des dates factuelles rarement révisées une fois
  la blessure terminée (plutôt B, révision possible mais rare) ; les
  « Predicted Lineups » recalculées à la demande à partir de l'état
  **actuel** de la base sont structurellement **C** pour tout usage
  rétroactif — mêmes réserves qu'API-Football.

**FootyStats API** — paliers 29,99 à 389,99 £/mois selon le nombre de
championnats couverts (40 à 1500+), inclut compositions et cotes
pré-match — [documentation officielle](https://footystats.org/api).
Aucune information publique trouvée sur l'horodatage ou la conservation
d'un historique des compositions tel que connu avant chaque match —
**classification PIT : D** (aucune preuve, ni positive ni négative,
disponible publiquement) tant qu'un test direct de l'API n'a pas été
mené.

**PhysioRoom / Premier Injuries** — sites spécialisés, Premier League
uniquement. Premier Injuries revendique une base « depuis 2010 » avec
« analyse détaillée de chaque blessure rapportée » — [à propos](https://www.premierinjuries.com/about),
[page données](https://www.premierinjuries.com/newsroom/injury-data).
Aucune API publique documentée trouvée ; interface web uniquement.
**Classification PIT : D** — aucune preuve publique que la table
actuellement affichée pour une date passée reflète l'état connu à cette
date plutôt qu'un état corrigé depuis (le site affiche une table
« actuelle », pas un historique daté page par page). Une reconstruction
via la Wayback Machine (archive.org) est en principe possible **si**
des snapshots existent à des dates suffisamment rapprochées de chaque
match — non vérifié ici, coûteux à industrialiser, couverture Premier
League uniquement (pas Liga/Ligue 1).

**Transfermarkt** — page « historique des blessures » par joueur,
largement scrapée par des outils tiers (Apify, `worldfootballR`) —
[exemple de scraper](https://apify.com/curious_coder/transfermarkt/api),
[fonction R dédiée](https://jaseziv.github.io/worldfootballR/articles/extract-transfermarkt-data.html),
[discussion GitHub sur le scraping de l'historique blessures/suspensions](https://github.com/alan-turing-institute/AIrsenal/issues/482).
Aucune API officielle ; conditions d'utilisation de Transfermarkt non
confirmées publiquement pour cet usage précis (recherche n'a pas trouvé
de politique explicite autorisant/interdisant le scraping à des fins de
recherche) — **le risque juridique/ToS reste non tranché ici,
explicitement signalé comme tel plutôt que supposé résolu**. Sur le plan
PIT : la page « historique » de Transfermarkt liste des périodes de
blessure avec dates de début/fin, factuelles et rarement révisées après
coup — **classification B**, sous réserve du risque ToS non résolu.

### 5.B — Contexte pré-match / calendrier (Priorité B)

**Calendrier multi-compétitions (dates de matchs)** — reconstructible
sans fournisseur payant à partir de sources d'archives publiques
(résultats Wikipédia par compétition, FBref). FBref impose une limite de
10 requêtes/minute et bloque les sessions abusives jusqu'à 24h ;
important : « la plupart des données de Sports Reference proviennent de
tiers qui les leur vendent, et leurs accords avec ces tiers leur
interdisent de fournir ces données en téléchargement » — [politique officielle anti-bot](https://www.sports-reference.com/bot-traffic.html).
**Classification PIT : A** pour la donnée elle-même (une date de match
passé est un fait immuable, jamais révisé), mais avec une **réserve
d'accès** : usage à faible fréquence, à des fins de recherche, sans
redistribution — jamais un usage massif ou commercial. `worldfootballR`
(package R) documente l'extraction FBref/Transfermarkt/Understat —
[dépôt officiel](https://github.com/JaseZiv/worldfootballR),
[CRAN](https://cran.r-project.org/package=worldfootballR) — mais ne
fournit pas nativement un calcul de congestion/repos ; celui-ci devrait
être dérivé nous-mêmes des dates de matchs extraites.

**football-data.org** — API standings/fixtures gratuite pour 12
compétitions majeures (dont Premier League, La Liga, Ligue 1), 10
requêtes/minute — [couverture officielle](https://www.football-data.org/coverage),
[pricing](https://www.football-data.org/pricing). Classement dérivé
uniquement des matchs de championnat déjà présents dans le corpus
Football-Data — **faux ami identifié explicitement (voir section 9)** :
ne serait qu'une reformulation de résultats déjà utilisés par
`poisson_simple`, pas une information nouvelle.

**ClubElo (clubelo.com)** — ratings Elo journaliers/bimensuels (1er et
15 de chaque mois), API CSV publique sans clé, endpoint
« historique par club » remontant aux années 1940 pour les clubs
établis — [site officiel](https://clubelo.com/), [wrapper Python documenté `soccerdata`](https://soccerdata.readthedocs.io/en/latest/reference/clubelo.html).
Calcul **indépendant** du projet, intégrant **toutes les compétitions**
d'un club (championnat, coupes, Europe, sélection nationale des joueurs
non pertinent ici mais matchs de club oui) — une dimension que
`poisson_simple` (entraîné uniquement sur les résultats de championnat
déjà présents dans le corpus) ne voit jamais. **Classification PIT : A**
— chaque snapshot est daté ; interroger `api.clubelo.com` pour une date
passée retourne le rating **tel qu'il était calculé à cette date**, pas
une valeur recalculée aujourd'hui avec le recul (propriété structurelle
du format d'archive, pas une hypothèse). Gratuit, aucune clé API. Risque
de stabilité : projet à mainteneur unique (pas d'entreprise derrière),
disponibilité non garantie contractuellement — plusieurs miroirs
communautaires existent (ex. [snapshots quotidiens archivés sur GitHub](https://github.com/tonyelhabr/club-rankings)) qui réduisent ce risque en cas d'interruption.

### 5.C — Forme indépendante (Priorité C)

**xG d'un second fournisseur** (alternative à Understat, déjà utilisé
par `xg_model`) — aucune source gratuite équivalente à Understat trouvée
avec une couverture comparable pour Liga/Ligue 1/Premier League sur
2024/25-2025/26 ; les fournisseurs avec du xG de qualité comparable
(Opta/Stats Perform, StatsBomb) sont des solutions enterprise (voir
5.D). **Classification : non prioritaire** — un second fournisseur de
xG ne serait qu'un test de sensibilité du modèle déjà existant à sa
source de données, pas une famille d'information nouvelle au sens de
l'énoncé de la Phase I.

### 5.D — Fournisseurs enterprise (mentionnés pour mémoire, non retenus)

**Opta (Stats Perform), StatsBomb (Hudl), Wyscout (Hudl)** — licences
enterprise sans tarification publique ; ordre de grandeur rapporté :
flux Opta/StatsBomb à partir de 50 000 €/an, licence club Wyscout
15 000-25 000 €/an — [comparatif tiers](https://gamecode.ai/insights/articles/opta-vs-statsbomb-vs-wyscout/).
Couverture Opta ~70 ligues, Wyscout 200+ ligues (vidéo + stats basiques)
— même source. **Écartés à ce stade** : coût sans commune mesure avec
une acquisition progressive à faible risque (section 10), alors
qu'aucune expérience n'a encore démontré qu'une information de ce type
serait exploitable sur ce projet.

---

## 6. Tableau comparatif

| Fournisseur | Famille | Couverture 3 champ. | Historique 2024/25-25/26 | PIT | API/fichier | Coût | Archivable |
|---|---|---|---|---|---|---|---|
| API-Football | A (compositions/blessures) | Oui | Limité sur palier gratuit | **C** (rétroactif) / A (prospectif) | Oui, REST documenté | Gratuit (100 req/j) à 39 $/mois | Oui, si journalisé par nous |
| Sportmonks | A (compositions/blessures) | Oui | 3 saisons incluses, add-on au-delà | **B/C** selon champ | Oui, REST documenté | À partir de 29 €/mois | Oui, si journalisé par nous |
| FootyStats | A (compositions) | Oui | Non confirmé | **D** (non documenté) | Oui, REST documenté | 30-390 £/mois | Non confirmé |
| PhysioRoom/Premier Injuries | A (blessures, PL seule) | Non (PL uniquement) | Revendiqué depuis 2010, non horodaté | **D** | Non (web uniquement) | Gratuit (web) | Partiellement via Wayback Machine |
| Transfermarkt | A (blessures) | Oui | Oui (pages historiques) | **B**, sous réserve ToS non tranchée | Non officiel (scraping tiers) | Gratuit (scraping) | Oui |
| Calendrier multi-compétitions (FBref/Wikipédia) | B (congestion) | Oui | Oui, complet | **A** | Scraping à faible fréquence | Gratuit | Oui |
| football-data.org (classement) | B (classement) | Oui (12 comp.) | Oui | **A**, mais redondant (voir §9) | Oui, REST documenté | Gratuit (10 req/min) | Oui |
| ClubElo | B/C (rating indépendant) | Oui | Oui, décennies d'historique | **A** | Oui, CSV public sans clé | **Gratuit** | Oui (+ miroirs communautaires) |
| xG second fournisseur | C (forme) | Non confirmé équivalent | — | — | — | — | Non prioritaire |
| Opta/StatsBomb/Wyscout | A/C (enterprise) | Oui | Oui | Non évalué (accès non obtenu) | Oui, enterprise | 15 000-50 000+ €/an | Sous contrat |

---

## 7. Scoring de sélection (critères explicites, pré-enregistrés avant toute expérience)

Chaque candidat retenu pour le scoring (ceux classés PIT **A**, ou
**A pour un usage strictement prospectif**) est noté 0-2 sur chaque
critère (0 = ne satisfait pas, 1 = partiel, 2 = satisfait pleinement) —
**aucune pondération cachée** : la somme est indicative, la décision
finale (section 12) est justifiée qualitativement, pas par le score
seul, conformément à l'interdiction de l'énoncé (« ne donne pas un score
arbitraire caché »).

| Critère | ClubElo | Calendrier congestion | API-Football (compositions, prospectif) |
|---|---|---|---|
| Nouveauté informationnelle (info absente du corpus/modèle actuel) | 2 — intègre les compétitions hors championnat, jamais vu par `poisson_simple` | 1 — le repos/la fatigue n'a jamais été testé sur données réelles, mais l'intuition est ancienne dans la littérature de paris | 2 — jamais aucune information de composition testée dans ce projet |
| Qualité PIT (preuve, pas supposition) | 2 — snapshot daté, structurellement A | 2 — dates de match immuables | 0 rétroactif / 2 si prospectif uniquement |
| Couverture historique (2024/25-25/26 déjà utilisées) | 2 — décennies d'historique | 2 — reconstructible intégralement | 0 — aucune garantie PIT rétroactive |
| Couverture championnats (Liga/Ligue1/PL) | 2 | 2 | 2 |
| Couverture joueurs/équipes (mapping stable) | 2 — niveau équipe uniquement, suffisant ici | 2 — niveau équipe | 1 — mapping joueur nécessaire, plus complexe que l'équipe |
| Granularité temporelle | 1 — snapshot bimensuel (1er/15 du mois), pas quotidien | 2 — date exacte du match | 2 si prospectif (mise à jour 4h) |
| Stabilité du fournisseur | 1 — mainteneur unique, pas d'entreprise, mais miroirs communautaires existants | 2 — sources archivistiques multiples (Wikipédia, FBref) | 2 — service commercial établi |
| Coût | 2 — gratuit | 2 — gratuit (usage faible fréquence) | 2 (gratuit) à 1 (payant si volume) |
| Facilité d'intégration (format, mapping) | 2 — CSV simple, déjà wrappé par `soccerdata` | 1 — nécessite un calcul dérivé (jours de repos) non fourni nativement | 1 — mapping joueur/équipe à construire |
| Risque de fuite | 1 — granularité bimensuelle impose de choisir prudemment la dernière snapshot strictement antérieure à `decision_time` | 0 (risque quasi nul, fait immuable) | 2 rétroactif (rejeté) / 0 prospectif (aucun risque si journalisé au bon instant) |
| Reproductibilité (méthode de calcul documentée/stable) | 1 — méthode Elo documentée mais recalculée en continu par un tiers non contrôlé par le projet | 2 — simple différence de dates | 2 — format API stable et documenté |
| **Total (sur 22)** | **18** | **18** | **14** (usage prospectif uniquement) |

**Lecture du score** : ClubElo et le calendrier de congestion arrivent
à égalité et dominent largement toute piste de composition/blessure
testée en usage **immédiat**, précisément parce que ces deux dernières
sont les seules à satisfaire le critère PIT **sans aucune réserve**
sur le corpus déjà existant. Le score d'API-Football (compositions) n'a
de sens qu'en mode prospectif — sa valeur immédiate pour un test sur le
corpus 2024/25-2025/26 est nulle, pas simplement faible.

---

## 8. Le but n'est pas « la meilleure API en général »

Reformulation explicite de la question réellement posée par cette Phase
J : *quelle source permettrait de tester UNE information nouvelle,
pré-match, historiquement reconstructible, avec le minimum de risque de
fuite ?* — pas quel fournisseur a le plus de données, le plus de
championnats, ou la meilleure réputation. C'est ce critère, et lui seul,
qui explique pourquoi ClubElo (couverture minimale : un seul chiffre par
club) devance des fournisseurs bien plus riches en volume (FootyStats,
Sportmonks) dans le scoring de la section 7 — la richesse d'un
fournisseur n'est jamais un substitut à la preuve de sa qualité PIT.

---

## 9. Analyse spécifique : compositions / blessures

**Ce qu'il faudrait réellement connaître avant le match** : pour chaque
titulaire probable, un statut ternaire au moment de `decision_time`
(disponible / incertain / indisponible confirmé), et pour l'équipe dans
son ensemble, une mesure agrégée de la force de la composition attendue
par rapport à sa composition de référence (ex. nombre de titulaires
habituels absents, pondéré par leur importance). Ni la fiche de match
finale (composition officielle publiée ~1h avant coup d'envoi, donc
souvent après `decision_time` actuel de 2h) ni un statut de blessure
« actuel » interrogé après coup ne répondent à cette exigence.

**Blessure connue vs blessure publiée après coup** — distinction
centrale, souvent invisible dans la documentation des fournisseurs : une
blessure peut être **suspectée** (rumeur médiatique, sortie précoce au
match précédent) bien avant d'être **officiellement confirmée** par le
club, elle-même souvent publiée **après** `decision_time` pour le match
suivant si celui-ci est rapproché. Un fournisseur qui affiche
aujourd'hui « joueur X blessé depuis le 12/03 » ne dit jamais **quand**
cette information est devenue publique — seulement quand la blessure a
**commencé** (une date médicale, pas une date de connaissance publique).
Confondre les deux est précisément l'erreur que la classification PIT de
ce document (section 4) est conçue pour empêcher.

**Composition probable vs composition officielle** — la composition
*probable* (médias, sites spécialisés) est disponible plus tôt mais
n'est **jamais un fait vérifié** ; l'utiliser comme si elle était connue
avec certitude introduirait un biais différent (confiance non justifiée
dans une prédiction externe, elle-même potentiellement déjà influencée
par le marché). La composition *officielle* est un fait vérifié, mais
publiée trop tard par rapport à `decision_time` (~1h avant le coup
d'envoi, contre 2h actuellement) pour être utilisable sans modifier ce
paramètre déjà validé du moteur — une modification hors périmètre de
cette Phase J.

**Comment traiter l'incertitude** : si la piste composition est un jour
testée, la variable doit être construite comme une **probabilité de
disponibilité à `decision_time`**, jamais un fait binaire tardif importé
rétroactivement — ce qui suppose de connaître, pour chaque source
utilisée, sa propre date de publication, pas seulement la date du match.

**Comment éviter d'utiliser une information révélée trop tard** :
strictement la même discipline que celle déjà appliquée depuis l'étape 1
du projet (`knowledge_time <= decision_time`, délégué à
`matching.py`/`time_resolution.py`) — mais celle-ci exige un
`knowledge_time` **vérifié**, pas une date de match ou une date médicale
de blessure. Aucun fournisseur audité en section 5.A ne fournit
aujourd'hui ce timestamp de publication de façon documentée et
contractuelle.

**Comment construire un historique PIT** : la seule méthode
rigoureusement défendable identifiée par cette recherche est la
**journalisation prospective** — interroger un fournisseur (API-Football
ou Sportmonks, tous deux avec un palier gratuit/faible coût suffisant
pour ce volume) à intervalle régulier **à partir d'aujourd'hui**, stocker
chaque réponse avec son propre horodatage de collecte (notre
`knowledge_time`, vérifié par nous, pas supposé), et n'utiliser, pour
chaque futur match, que la dernière snapshot collectée strictement avant
`decision_time`. **Conséquence directe et non négociable** : cette piste
ne peut **pas** être testée sur le corpus 2024/25-2025/26 déjà utilisé
par ce projet — elle nécessite une période d'accumulation prospective
(a minima une saison complète, pour atteindre un effectif comparable aux
seuils déjà utilisés dans le projet, `n≥30` par sous-groupe) avant tout
test scientifique valide.

---

## 10. Analyse spécifique : classement / contexte calendrier

**Classement** — si dérivé des seuls résultats de championnat déjà
présents dans le corpus Football-Data (ex. via `football-data.org` ou un
calcul maison), il s'agit d'un **faux ami** explicitement anticipé par
la Phase I (section 5, point 9) : une reformulation des mêmes matchs déjà
utilisés en entrée de `poisson_simple`, pas une information nouvelle —
un classement par points n'est qu'une transformation non linéaire des
mêmes résultats (victoire/nul/défaite) déjà connus du modèle.

**ClubElo change cette conclusion** : en intégrant les résultats de
**toutes les compétitions** d'un club (coupes nationales, compétitions
européennes), il capture une dimension que le corpus actuel ne contient
tout simplement pas — un club engagé en Ligue des Champions un mercredi
soir a un profil de forme que `poisson_simple` (entraîné uniquement sur
les résultats de championnat des trois compétitions déjà couvertes) ne
voit jamais. C'est une information **structurellement absente** du
corpus, pas une reformulation.

**Congestion du calendrier (repos, déplacements)** — même raisonnement :
l'information n'est **pas** contenue dans les résultats de championnat
seuls (deux équipes peuvent avoir le même nombre de points mais des
calendriers de récupération très différents selon leur engagement
européen). C'est une information nouvelle, jamais testée sur données
réelles dans ce projet (E1/E7 ne l'ont testée que sur données
synthétiques, étape 5) — mais sa construction complète exige un
calendrier multi-compétitions, partiellement absent du corpus actuel
(section 5.B).

**Conclusion de cette analyse** : ni le classement ni la congestion ne
sont de simples reformulations si, et seulement si, la source retenue
inclut les compétitions **hors** championnat — un classement de
championnat seul, ou un calcul de repos limité au seul championnat déjà
couvert, resterait largement redondant.

---

## 11. Stratégie d'acquisition progressive

**Étape 1 — source/dataset minimal, une seule variable.**
Acquisition à coût nul : ClubElo (rating Elo pré-match, différence
domicile-extérieur) via l'API CSV publique. Aucun engagement financier,
aucune clé API, aucune négociation contractuelle. Récupération complète
de l'historique déjà disponible pour les 2024/25-2025/26 (les mêmes
matchs déjà utilisés par le corpus Football-Data), sans attendre.

**Étape 2 — validation de la qualité PIT et de la couverture.**
Avant toute expérience : (a) vérifier que chaque snapshot Elo utilisée
pour un match donné est bien strictement antérieure à `decision_time`
(test anti-fuite dédié, même discipline que Phases F/G/H) ; (b) mesurer
la couverture réelle (tous les clubs des 3 championnats ont-ils une
entrée ClubElo ? y a-t-il des clubs promus sans historique suffisant ?) ;
(c) vérifier la stabilité de l'identifiant club ClubElo pour
l'appariement avec les identifiants déjà utilisés (`matching.py`) ; (d)
documenter explicitement toute lacune trouvée, sans l'ignorer.

**Étape 3 — extension seulement si la donnée est propre.**
Si, et seulement si, l'étape 2 confirme une couverture et une qualité
PIT suffisantes : (a) lancer, dans une phase scientifique dédiée
ultérieure (hors périmètre de cette Phase J), le protocole complet
(pré-enregistrement, tests anti-fuite, contrôle de recalibration
obligatoire dès la conception, comme Phases F/G/H) pour tester le rating
Elo comme covariable ; (b) en parallèle, démarrer dès maintenant la
journalisation prospective d'un fournisseur de compositions/blessures
(section 9) pour permettre, dans 12+ mois, un test rigoureux de la
Priorité A — jamais avant, faute d'un historique PIT vérifiable.

---

## 12. Recommandation

## SOURCE RECOMMANDÉE :
**ClubElo** (`api.clubelo.com`, CSV public, gratuit, sans clé) pour un
test immédiat sur le corpus déjà existant ; **démarrage en parallèle**
d'une journalisation prospective (API-Football palier gratuit ou
Sportmonks Starter) pour construire, sur les 12 prochains mois, un
historique PIT vérifié des compositions/blessures.

## DONNÉE PRIORITAIRE :
Rating Elo pré-match par club (`decision_time`), intégrant les
compétitions hors championnat (coupes, Europe) — une dimension de force
d'équipe structurellement absente du corpus et du modèle actuels.

## PREMIÈRE VARIABLE À TESTER :
Écart de rating Elo (domicile − extérieur) à `decision_time`, comme
covariable additionnelle unique dans le même design de contrôle
obligatoire déjà utilisé en Phases F/G/H (Modèle-recalibré **vs**
Modèle+Elo) — jamais une variable supplémentaire testée simultanément,
conformément à la discipline « une seule variable nouvelle par
expérience ».

## POURQUOI :
C'est la **seule** piste de cette recherche qui satisfait simultanément
(a) une information potentiellement orthogonale (compétitions hors
championnat, jamais vues par `poisson_simple`) et (b) une reconstruction
PIT **immédiatement vérifiable** sur le corpus déjà existant, sans
période d'attente ni hypothèse non prouvée sur l'horodatage d'un
fournisseur commercial. Toutes les pistes de composition/blessure
(Priorité A, théoriquement plus prometteuses) échouent aujourd'hui ce
critère pour un usage rétroactif — aucun fournisseur audité ne prouve
publiquement que son état « historique » reflète l'état réellement connu
avant chaque match passé.

## RISQUE PRINCIPAL :
(1) Redondance : le rating Elo reste, in fine, dérivé de résultats de
matchs (buts/scores), donc potentiellement corrélé à ce que
`poisson_simple` capture déjà pour les matchs de championnat communs —
risque d'un schéma « recalibration explique tout » identique à celui
observé trois fois de suite (Phases F/G/H). (2) Imprécision temporelle :
la granularité bimensuelle (snapshots au 1er et 15 du mois) introduit un
décalage potentiel de plusieurs jours entre le rating utilisé et l'état
réel de la forme au moment exact de `decision_time` — jamais une fuite
(la snapshot reste strictement antérieure si sélectionnée correctement),
mais un bruit de mesure.

## COMMENT LE RÉDUIRE :
Contrôle de recalibration obligatoire inclus **dès la conception** du
futur protocole (discipline désormais non négociable, établie
indépendamment par les Phases F, G et H) pour isoler l'effet spécifique
d'Elo d'un effet de recalibration générique ; sélection stricte de la
dernière snapshot **antérieure** à `decision_time` (jamais la plus
proche en valeur absolue, même si postérieure) avec un test anti-fuite
dédié vérifiant cette propriété sur 100% du corpus ; documentation
explicite du bruit de granularité bimensuelle comme limite connue,
jamais corrigée arbitrairement.

## ALTERNATIVE :
Congestion de calendrier (jours de repos, déplacements, engagement
européen) — même niveau de garantie PIT (dates de match immuables),
même absence de coût, mais nécessite un travail de construction plus
lourd (calendrier multi-compétitions à assembler depuis des sources
d'archives publiques à faible fréquence de requête) avant tout test.

---

## 13. Si aucune source ne satisfaisait les critères PIT

Ce cas s'applique **précisément** à la Priorité A (compositions/
blessures) pour tout usage **rétroactif** sur le corpus déjà utilisé
(2024/25-2025/26) : **aucune source auditée dans cette recherche ne
satisfait aujourd'hui les critères PIT pour un usage rétroactif** —
API-Football, Sportmonks, FootyStats, PhysioRoom/Premier Injuries et
Transfermarkt sont chacune classées C, C, D, D et B-sous-réserve (section
5.A, 6). Cela ne disqualifie pas la piste en général — elle reste la
piste au potentiel informationnel le plus élevé selon la Phase I — mais
elle ne peut être testée qu'après une période de journalisation
prospective (section 9, 11), jamais achetée et testée immédiatement sur
l'historique déjà utilisé par ce projet.

---

## 14. Coûts (résumé)

| Source | Coût pour l'étape 1 | Coût si extension complète |
|---|---|---|
| ClubElo | 0 € | 0 € (gratuit par nature) |
| Calendrier multi-compétitions (scraping faible fréquence) | 0 € (temps d'ingénierie uniquement) | 0 € |
| API-Football (journalisation prospective) | 0 € (palier gratuit, 100 req/jour suffisant pour ~10-15 matchs/jour) | 19-39 $/mois si le volume dépasse le palier gratuit |
| Sportmonks (journalisation prospective, alternative) | 29 €/mois (palier Starter) | 159-199 €/mois pour l'add-on Expected Lineups (non nécessaire à ce stade) |
| Opta/StatsBomb/Wyscout | Non retenu à ce stade | 15 000-50 000+ €/an |

---

## 15. Protocole de validation préalable de toute donnée nouvelle

Repris et adapté des critères déjà imposés par la Phase I (section 11 de
`docs/final_data_strategy.md`), appliqués spécifiquement à ClubElo (ou
toute autre source retenue à l'étape 3) avant toute expérience future :

1. **Horodatage vérifié, pas supposé** : démontrer par construction
   (format d'archive daté) que la snapshot utilisée pour un match donné
   est bien celle en vigueur avant `decision_time` — jamais une hypothèse
   conservatrice non testée.
2. **Couverture mesurée avant toute expérience** — jamais supposée à
   partir de la documentation du fournisseur seule (leçon de la Phase I :
   trois bookmakers non documentés ont été découverts par inspection
   directe des fichiers déjà présents ; la même rigueur s'applique ici).
3. **Une seule variable nouvelle par expérience** — jamais Elo et
   congestion testés simultanément dans une même expérience.
4. **Contrôle de recalibration obligatoire** inclus dès la conception du
   protocole (Modèle-recalibré vs Modèle+nouvelle source), jamais ajouté
   après un premier résultat trompeur.
5. **Protocole pré-enregistré et verrouillé avant toute lecture de
   résultat réel** — définition mathématique complète, hypothèses,
   population, critères de validation/rejet à 5 valeurs
   (`VALIDÉ`/`NON VALIDÉ`/`ABSENCE DE PREUVE`/`DONNÉES INSUFFISANTES`/
   `PROBLÈME MÉTHODOLOGIQUE`), verrouillage avant exécution.
6. **Distinction stricte des trois questions** (calibration probabiliste,
   information incrémentale, rentabilité opérationnelle) — jamais une
   amélioration de Brier interprétée comme une preuve de rentabilité.
7. **Tests unitaires et anti-fuite écrits et exécutés avant toute
   exécution sur données réelles.**
8. **Aucune intégration au moteur de production** sans un verdict
   `VALIDÉ` explicite, robuste par championnat/saison, avec IC95%
   entièrement favorable.

---

## 16. Réponses directes aux six questions finales

**1. Quelle est la meilleure nouvelle information à acquérir ?**
Une mesure de force d'équipe intégrant les compétitions hors
championnat (rating Elo multi-compétitions) — la seule famille
identifiée qui soit à la fois potentiellement orthogonale au corpus
actuel et immédiatement vérifiable point-in-time.

**2. Quelle est la meilleure source pour l'obtenir ?**
ClubElo (`api.clubelo.com`), gratuite, sans clé, avec un historique daté
remontant à des décennies et une propriété PIT structurelle (snapshots
archivés, pas un état recalculé après coup).

**3. Peut-on réellement la reconstruire point-in-time ?**
Oui, pour le corpus déjà existant (2024/25-2025/26) — sous réserve de
sélectionner strictement la snapshot antérieure à `decision_time` (test
anti-fuite à écrire). Ce n'est **pas** le cas pour les compositions/
blessures (Priorité A), qui nécessitent une journalisation prospective
non encore démarrée.

**4. Quel serait le premier test scientifique à faire avec cette
donnée ?**
Reproduire exactement l'architecture de contrôle des Phases F/G/H :
Modèle brut / Modèle-recalibré (contrôle) / Modèle+Elo (test), sur la
même population que le corpus déjà utilisé, avec `paired_bootstrap_test`
sur la différence de Brier — jamais exécuté dans cette Phase J.

**5. Quel est le principal risque de faux positif/fuite ?**
Redondance masquée par un effet de recalibration générique (comme dans
les trois expériences précédentes) plutôt qu'une fuite au sens strict —
le risque de fuite temporelle proprement dit est faible pour ClubElo
(snapshots datés), à condition de vérifier explicitement, par un test
dédié, que seule la snapshot strictement antérieure à `decision_time`
est utilisée.

**6. Est-ce que cette acquisition vaut réellement le coût au regard des
20 expériences déjà réalisées ?**
Oui, dans la mesure où le coût est nul (ClubElo est gratuit) et où
l'information (compétitions hors championnat) est **structurellement**
absente de tout ce qui a été testé jusqu'ici — contrairement aux 20
expériences précédentes, qui ont toutes interrogé des transformations du
même prix de marché ou des statistiques post-match du même match. Le
rendement décroissant démontré en Phase I (section 6 de
`docs/final_data_strategy.md`) s'applique à la répétition d'une même
famille de question, pas à une famille génuinement nouvelle — mais rien
ne garantit un résultat positif, et le protocole (section 15) devra être
suivi intégralement avant toute conclusion.

---

## 17. Arrêt

Conformément à l'instruction explicite de la Phase J, cette recherche est
une phase documentaire de sélection de source, pas une expérience.
**Aucun code n'est écrit, aucun test n'est ajouté, aucune donnée n'est
téléchargée dans le dépôt, aucune expérience n'est lancée.** La décision
de procéder à l'étape 1 (acquisition ClubElo, gratuite) ou de lancer la
journalisation prospective des compositions reste entièrement à la
discrétion de l'utilisateur.
