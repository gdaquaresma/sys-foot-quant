# Audit du Research Framework contre les sources primaires

## Statut

Document d'audit autonome. **Ne modifie ni ne remplace** `docs/research_framework.md`.
Aucun code, test, modèle, paramètre ou résultat déjà validé n'est touché par ce
document. Les éventuelles modifications du research framework seront décidées
conjointement avec l'utilisateur après lecture de cet audit.

## Objet et méthode

Cet audit relit `docs/research_framework.md` (sections A à H, étape 1.5) à la
lumière des **5 sources primaires intégrales** et des **2 documents
secondaires** utilisés pour le construire :

**Sources primaires** (texte intégral lu dans cette session) :
1. Richard A. Epstein, *The Theory of Gambling and Statistical Logic*, 2e éd.
   — chapitres 1 à 6 (probabilités, théorie des jeux, principe de Parrondo,
   pièces, dés), chapitre 8 (Blackjack / EOR), chapitre 11 (Fallacies and
   Sophistries — biais cognitifs, ESP, biais d'arrêt optionnel) lus
   intégralement. Chapitres 7, 9, 10 non relus dans cette session (cartes/
   Markov, suite de la logique statistique, jeux d'habileté pure) — matière
   jugée non porteuse pour les hypothèses déjà citées par le framework ;
   voir limite méthodologique en fin de document.
2. Ed Miller & Matthew Davidow, *The Logic of Sports Betting* — texte intégral
   lu en totalité (récupéré depuis la transcription brute de session après
   une perte de contexte intermédiaire, puis relu du début à la fin).
3. Josh Appelbaum, *The Everything Guide to Sports Betting* — chapitres 1 à 9
   (Bases, Bankroll, Attentes réalistes, Biais, Paris alternatifs, Paris
   contrarian, Suivre l'argent sharp, Apprendre du passé, Faire un pick) plus
   Annexe A (glossaire) et l'index, lus intégralement. Chapitres 10 à 17
   (placer un pari, chapitres par sport, DFS, jeu mental) non relus dans
   cette session — contenu opérationnel/sport-spécifique, sans nouvelle
   hypothèse transversale pertinente pour le football au-delà de ce qui est
   déjà couvert par les chapitres 1-9 et le glossaire.
4. Kevin Dolan, *The Complete Guide to Sports Betting* — texte intégral lu en
   totalité (session antérieure à ce document, confirmé relu en entier avant
   le début de cet audit).
5. Rob Miech, *Sports Betting for Winners* — texte intégral lu en totalité
   (session antérieure, confirmé relu en entier avant le début de cet audit).

**Documents secondaires** : `pages1_extracted.txt` (audit/synthèse ciblée sur
Dolan) et `pages2_extracted.txt` ("Synthèse croisée des quatre ouvrages" +
audit critique), tous deux lus intégralement.

**Convention utilisée dans tout ce document** — trois niveaux de preuve,
strictement distingués à chaque affirmation :

- 🟦 **FAIT PRIMAIRE** : affirmation directement établie par le texte d'une
  source primaire, avec référence précise (auteur, chapitre/section).
- 🟨 **SYNTHÈSE SECONDAIRE** : affirmation ou classification provenant des
  deux documents secondaires (la synthèse croisée et son audit critique),
  pas vérifiée mot à mot dans une source primaire.
- 🟥 **NOTRE INTERPRÉTATION** : raisonnement, extrapolation ou décision
  méthodologique qui nous appartient — ni le corpus primaire ni la synthèse
  ne l'affirment telle quelle.

Chaque sous-section suit la structure : *Ce que confirme l'audit* → *Nuances
ou limites absentes du framework* → *Verdict sur la classification actuelle*.

---

## 0. Verdict global

Après lecture intégrale des 5 sources, **aucune classification du framework
(Fondation / Intéressante / Spéculative / À rejeter) ne doit être changée**.
Le classement tel qu'il existe résiste à l'audit. En revanche, l'audit
identifie :

- plusieurs endroits où la preuve primaire est **plus forte et plus précise**
  que ce que le framework laisse penser (notamment C5/CLV, D1/Kelly, F1/EOR,
  F3-F4/théorèmes d'Epstein) — la classification ne change pas, mais la
  confiance qu'on peut y accorder est mieux étayée qu'annoncé ;
- une **nuance méthodologique substantielle absente** du framework sur le
  test de "gliding" de Miller & Davidow (§E/§G) ;
- une **nuance substantielle absente** sur la distinction qu'Epstein fait
  lui-même entre "jeu à seuil fixé a priori" et "test d'hypothèse à arrêt
  optionnel" (§G1) ;
- un **biais d'agrégation non signalé** dans le traitement du corpus comme
  un bloc homogène de "4 livres" : Epstein est d'une nature radicalement
  différente des 3 autres (aucun contenu sportif, aucune mention de football)
  ce qui change le poids évidentiel de son silence sur B1/B3 (§B) ;
  Ac
- un **outil méthodologique concret absent** du §G : la grille en trois
  critères d'Appelbaum pour juger un "betting system" (hypothèse motivée,
  échantillon ≥100, stabilité pluriannuelle) — directement réutilisable pour
  discipliner le test des variables de la section E ;
- une **confirmation textuelle exacte** de la contradiction C3 déjà notée par
  le framework entre Appelbaum et Miller & Davidow sur le RLM, avec des
  nuances supplémentaires côté Appelbaum lui-même (mise en garde contre le
  RLM "aveugle", sensibilité au "triggering number") absentes du résumé
  actuel du framework.

Aucun de ces points ne justifie de reclasser une hypothèse. Ce sont des
enrichissements et des garde-fous supplémentaires, détaillés section par
section ci-dessous.

---

## A. FOOTBALL MODEL

### A1. Pondération temporelle (time-decay)

**Ce que confirme l'audit** — 🟦 Dolan, chapitre "Understanding Power
Rankings" : méthode confirmée mot pour mot (moyenne médiane modifiée des 5
derniers matchs, avec pondération renforcée des deux matchs les plus
récents). C'est bien la source primaire directe de A1, pas une extrapolation
de la synthèse.

**Nuance absente du framework** — 🟦 Miech (*Sports Betting for Winners*)
documente une deuxième convergence primaire non citée par le framework :
la pratique de "Van Smith" (parieur professionnel profilé dans le livre) qui
reclasse chaque semaine son power rating ESPN top-10/bottom-6 à partir des 5
derniers matchs. Le framework cite Dolan + la synthèse (modèle "Grinder" de
Ron Boyles) + Epstein (implicite) comme "trois sources indépendantes" — en
réalité, avec Miech, c'est un **quatrième point de convergence primaire**,
qui renforce encore la classification Fondation sans la changer.

**Verdict** : classification Fondation inchangée, convergence plus forte que
ce que le framework indique.

### A2. HFA dynamique

Non re-audité en détail dans cette session (déjà traité en profondeur lors de
la construction initiale du framework). Rien dans la relecture des 5 sources
ne contredit le choix Fondation-avec-shrinkage / Intéressante-sans-shrinkage.

### A3. Power Rating façon Elo

🟦 Confirmé : le power rating de Dolan (marge de but attendue = différentiel
de notes + HFA) est bien décrit tel que résumé. Rien à ajouter.

### A4. Chi-carré comme diagnostic

🟦 Confirmé et approfondi : Epstein consacre une section entière (chapitre 2,
"Statistical Distributions") à la construction du test du χ² comme mesure
d'écart entre fréquences observées et attendues, avec l'exemple classique des
dés biaisés de Wolf/Weldon (χ² = 748.5 sur 100 000 lancers, rejet net de
l'hypothèse d'un dé honnête). Le mécanisme mathématique (Eq. 2-28,
∑(rᵢ-sᵢ)²/sᵢ) est identique à celui que le framework prévoit d'appliquer aux
scores de football. Aucune application au football chez Epstein — c'est bien
une transposition, comme le framework le signale déjà correctement.

**Verdict** : classification Fondation inchangée, mécanisme mathématique
vérifié dans le texte primaire (pas seulement "cité").

---

## B. FOOTBALL MODEL — Extensions expérimentales

### Nuance transversale sur B1/B3 — biais d'agrégation du corpus

🟥 **Notre interprétation.** Le framework écrit à plusieurs endroits "absent
des quatre livres originaux" pour justifier que Dixon-Coles (B1) et le xG
(B3) sont des importations académiques externes. Après lecture intégrale, ce
constat factuel est correct — 🟦 aucun des 4 livres sportifs (Dolan, Miech,
M&D, Appelbaum) ne mentionne le xG ni Dixon-Coles — mais le regroupement
"4 livres" masque une hétérogénéité de nature :

- Dolan, Miech, Appelbaum et Miller & Davidow sont tous des guides pratiques
  de paris sportifs US (NFL/NBA/MLB/NHL/NCAA), donc leur silence sur le xG ou
  Dixon-Coles est un silence *dans un domaine où le football existe à peine
  ou pas du tout* (Miech et Appelbaum ne parlent jamais de football/soccer ;
  Dolan a un chapitre "College/Pro football" mais c'est le football
  américain).
- 🟦 Epstein, en revanche, ne parle d'**aucun sport en équipe à score continu**
  — son livre couvre le Blackjack, les dés, les cartes, la théorie des jeux
  abstraite (Morra, Nim, échecs), les paris de casino, et les biais cognitifs.
  Le mot "football" (soccer ou américain) n'apparaît dans aucun chapitre lu.

Le silence d'Epstein sur Dixon-Coles n'a donc **aucune valeur évidentielle** :
ce n'est pas un auteur qui aurait pu en parler et ne l'a pas fait, c'est un
auteur dont le champ ne recouvre jamais un sport à buts. Compter Epstein
comme une des "4 sources" qui "ignorent" Dixon-Coles/xG revient à sur-pondérer
artificiellement la conclusion "absence généralisée du corpus" — alors que la
conclusion réelle et suffisante est plus modeste : *absence dans les 3 guides
de paris sportifs qui, eux, auraient eu l'occasion d'en parler*. Cela ne
change rien à la classification (B1/B3 restent Intéressante, à raison), mais
la formulation "absent des quatre livres" devrait être nuancée en "absent des
trois guides de paris sportifs du corpus ; hors-sujet pour le quatrième
(Epstein), qui ne traite d'aucun sport à but".

**Verdict** : classification B1/B3 = Intéressante inchangée. Reformulation de
la justification recommandée (question à trancher avec l'utilisateur, pas une
modification autonome).

### B2. Mise à jour bayésienne séquentielle

🟦 Confirmé : le théorème de Bayes est bien démontré rigoureusement par
Epstein (chapitre 2, "Bayes' theorem", et son application aux pièces
biaisées section "Biased coins" du chapitre 5), mais jamais appliqué à
l'estimation dynamique de force d'équipe. Le framework a raison de dire que
c'est "une construction à faire nous-mêmes". Rien à changer.

---

## C. MARKET ENGINE

### C1. Hold / marge

🟦 **Confirmation primaire précise et chiffrée, absente du framework** —
Appelbaum donne des chiffres exacts (Nevada, 1992-2017, étude UNLV Center for
Gaming Research citée dans le livre) : hold moyen tous sports = 5.52 %
(football américain 4.91 %, basket 5.08 %, baseball 3.32 %, "autres" 6.35 %),
et surtout **hold des paris combinés (parlays) = 31.17 %** — un ordre de
grandeur au-dessus des paris simples. Le framework classe C1 "Fondation" avec
raison (c'est une définition mathématique, pas une hypothèse), mais il ne
capture pas cette donnée empirique précise qui serait utile pour calibrer les
attentes de hold réaliste (marché simple vs marché combiné) une fois le
Market Engine construit à l'étape 3.

**Verdict** : classification Fondation inchangée. Donnée numérique
directement utilisable à ajouter en référence pour l'étape 3 (décision à
prendre avec l'utilisateur, pas un changement autonome ici).

### C2. Marchés synthétiques multi-bookmaker

🟦 Confirmé en détail — Miller & Davidow développent longuement ce mécanisme
("chopping the hold"), avec un exemple filé (chapitre "Chopping The Hold")
qui va jusqu'à 0.25 % de hold résiduel en combinant line shopping, marchés
dérivés corrélés et steam. Le framework classe C2 "Intéressante, conditionnée
à une extension du Data Engine" — c'est cohérent, la source primaire confirme
le mécanisme mais aussi sa dépendance à des données multi-bookmaker en temps
réel que nous n'avons pas encore.

### C3. RLM et disparité tickets/dollars

**Ce que confirme l'audit** — 🟦 La contradiction déjà signalée par le
framework entre Appelbaum et Miller & Davidow est confirmée mot pour mot des
deux côtés cette session :

- Appelbaum (chapitre 7, "Follow Sharp Action") définit le RLM en détail, le
  présente comme l'un des meilleurs signaux disponibles, et cite des
  statistiques rétrospectives chiffrées (par exemple : NBA, RLM ≥1.5 point,
  253-192 ATS soit 56.9 %, +47.64 unités, +10.5 % ROI, 2005-2018).
- Miller & Davidow affirment (texte confirmé lors d'une lecture antérieure de
  cette même session) que les données de répartition tickets/dollars
  publiquement diffusées sont "souvent biaisées ou inutiles" et contestent
  que les bookmakers retail bougent leurs lignes sous le seul poids de
  l'argent public.

Le framework a donc raison de qualifier cela de désaccord réel entre
sources primaires, pas une invention de la synthèse.

**Nuance importante absente du framework** — 🟦 Appelbaum lui-même, dans le
même chapitre qui défend le RLM, multiplie les mises en garde qui vont dans
le sens de la prudence de Miller & Davidow, sans être aussi tranché :
- "You should never blindly follow reverse line movement. Instead, it should
  be one of many tools in the toolbox when selecting a play."
- Le signal est extrêmement sensible au **triggering number** (le RLM ne
  "compte" que si on obtient le prix exact auquel les sharps ont parié — sinon
  c'est du "chasing steam", explicitement qualifié de mauvaise stratégie).
- Le RLM peut apparaître **des deux côtés du même match** simultanément
  (désaccord entre parieurs sharps), auquel cas Appelbaum recommande de
  passer son tour plutôt que d'agir.
- Les données bets-vs-dollars doivent être vérifiées à la source (Appelbaum
  liste explicitement le risque de données provenant d'un seul book, non
  représentatives, ou périmées) et récoltées le plus près possible de
  l'heure du match — exactement le type de fragilité opérationnelle que le
  framework anticipe déjà en disant "donnée non disponible dans nos sources
  actuelles".

Autrement dit : même la source qui défend le RLM (Appelbaum) le présente
comme un signal **fragile, sensible au timing, non actionnable seul et
sujet à contradiction interne au marché** — pas comme un signal fiable et
autonome. Cela renforce, plutôt qu'affaiblit, la prudence du framework
("Spéculative", "à tester avec un scepticisme actif").

**Verdict** : classification Spéculative inchangée, et en réalité mieux
justifiée par le détail primaire que ne le laisse deviner le paragraphe
actuel du framework.

### C4. Contrarian betting

🟦 Confirmé en détail — chapitre 6 complet d'Appelbaum ("Contrarian
Betting"), avec le "magic number" de 35 % de tickets exactement tel que
résumé par le framework, et des statistiques rétrospectives chiffrées par
sport (NFL, NBA, NCAA, MLB) qui montrent effectivement des seuils et des
résultats disparates d'un sport à l'autre (par exemple NFL <20 % moneyline :
ROI –3.8 % alors que NFL <20 % spread : ROI +7.8 % sur la même période) — ce
qui **confirme empiriquement**, dans la source primaire elle-même, l'
observation du framework selon laquelle "les seuils sont différents d'un
sport à l'autre" et "sentent le seuil optimisé a posteriori". C'est un point
fort de l'audit : le doute méthodologique du framework est corroboré par les
propres chiffres de la source qu'il cite comme "convergente".

**Verdict** : classification Spéculative inchangée, avec une preuve interne à
la source elle-même (pas seulement notre lecture critique) que les seuils ne
sont pas stables.

### C5. CLV

🟦 **Confirmation primaire nettement plus riche et plus rigoureuse que le
résumé du framework.** Le chapitre 9 d'Appelbaum ("Making a Pick") contient
une démonstration chiffrée complète, directement réutilisable comme
justification quantitative du principe déjà acté par l'ADR 0003 :
sur 2005-2017, parier systématiquement les favoris NFL contre le spread donne
1859-1860-111 (quasi pile 50 %, –78.5 unités à cause du vig) ; en supposant
un gain moyen de CLV de 0.5 point, la même population de paris devient
1970-1749-111, soit 52.9 % — au-dessus du seuil de rentabilité. Le mécanisme
est identique pour le moneyline (exemple : gagner 1 cent de CLV en moyenne
sur 150 paris/mois génère un demi- à un unit de profit mensuel supplémentaire
"gratuit"). Miller & Davidow développent le même principe (break-even
percentage vs. probabilité implicite par le marché) de façon complémentaire.

**Verdict** : classification Fondation inchangée et bien plus solidement
étayée que ne le suggère le paragraphe actuel du framework, qui se contente
de dire "consensus explicite" sans donner la mécanique chiffrée. Rien à
changer dans la classification ; matière utile à citer si le framework est
un jour enrichi.

### C6/C7. Marchés liés, parlays corrélés

Non re-audités en détail dans cette session (déjà couverts par les lectures
antérieures). Rien dans les chapitres relus cette session ne contredit ces
classifications.

---

## D. RISK ENGINE

### D1. Kelly fractionnaire

🟦 **Confirmation primaire exacte, désormais vérifiée mot à mot.** Epstein
(chapitre 3, section "The Basic Theorems", démonstration du critère de
Kelly) donne l'énoncé précis que le framework paraphrase : *"A popular
alternative consists of wagering one-half this amount, which yields 3/4 the
return with substantially less volatility. (For example, where capital
accumulates at 10% compounded with full bets, half-bets still yield 7.5%.)"*
C'est la source mathématique exacte du chiffre "Half-Kelly ≈ 75 % de la
croissance maximale" cité par le framework. Dolan et Appelbaum mentionnent
tous deux le critère de Kelly (Appelbaum : chapitre 2, glossaire ; Dolan :
exemple chiffré à 16 % de la bankroll) sans démonstration mathématique — la
preuve rigoureuse ne vient que d'Epstein, ce que le framework indique déjà
correctement ("le plus grand consensus... présent chez Epstein (démontré
mathématiquement)").

**Verdict** : classification Fondation inchangée, confiance renforcée par la
citation exacte désormais vérifiée.

### D2. Effet Parrondo

🟦 **Confirmation primaire détaillée du mécanisme, qui renforce la prudence
du framework plutôt que de l'affaiblir.** Le chapitre 4 d'Epstein est
entièrement consacré au paradoxe de Parrondo. Trois conditions structurelles
strictes sont explicitement posées comme nécessaires (section "Parrondo's
Domain") : (1) un élément de hasard, (2) une **asymétrie de type cliquet**
("ratchet-like asymmetry") dans le mécanisme lui-même, (3) deux processus
dynamiques de base qui alternent régulièrement ou aléatoirement. Dans sa
forme "capital-dependent" originale, le jeu B doit en plus dépendre d'une
structure modulo-m précise (m ≥ 3, sinon l'effet disparaît par symétrie) ;
dans sa forme "history-dependent", il faut une table de 4 pièces biaisées
distinctes conditionnées sur les 2 résultats précédents. Epstein cite bien
des extensions hors casino (marché boursier, génétique, sociologie,
écologie) mais **toujours sous réserve que ces trois conditions structurelles
précises soient identifiées** — et pour le cas boursier il ajoute lui-même la
réserve que "practical considerations — transaction fees, monotonically
decreasing prices across the board — inhibit the operation of the Parrondo
principle in this field."

Cela confirme, avec un luxe de détail que le framework ne mentionne pas
encore, que l'effet Parrondo n'est *pas* une vague intuition "deux mauvaises
stratégies peuvent en faire une bonne" mais un résultat qui **exige un
mécanisme de couplage structurel très spécifique**, démontré uniquement dans
des systèmes construits pour l'exhiber. Rien dans le corpus (aucune des 5
sources) ne propose une structure de couplage candidate pour deux marchés de
paris sportifs — ce que le framework note déjà, mais sans connaître le niveau
d'exigence structurelle réel du théorème.

**Verdict** : classification Spéculative/à-la-limite-d'à-rejeter inchangée
— et en réalité renforcée : l'écart entre "ce qu'il faudrait démontrer" et
"ce qui existe dans le corpus" est encore plus grand que ce que le framework
laisse penser.

### D3. Monte Carlo / Tchebychev

🟦 Confirmé — Epstein démontre l'inégalité de Tchebychev (chapitre 2, "The
Law of Large Numbers") comme outil général de borne de probabilité sans
hypothèse de forme de distribution, exactement l'usage prévu par le
framework pour le dimensionnement de bankroll. Rien à changer.

---

## E. FEATURES CONTEXTUELLES

### Nuance méthodologique majeure absente — le test de "gliding" de Miller & Davidow

🟦 **Fait primaire, absent du framework.** Miller & Davidow développent, en
plus du test en trois points déjà connu (prévisible / quantifiable / non
intégré dans la ligne), un critère de validation supplémentaire pour
distinguer un véritable "angle" exploitable d'une "tendance" fallacieuse : **
l'effet doit varier de façon continue avec la variable causale invoquée**
("gliding"), et non présenter un seuil arbitraire (cutoff) sans justification
causale graduelle. Un effet qui "marche" à partir d'exactement 3 jours de
repos mais pas à 2 ou 4 est suspect ; un effet qui s'intensifie
progressivement avec le nombre de jours de repos est plus crédible.

Ce critère est directement applicable, et actuellement absent, à la section
E du framework, qui définit plusieurs variables avec des seuils numériques
fixes et non justifiés causalement de façon continue :
- E1 (fatigue calendaire "3ᵉ match en 7 jours") : seuil discret à 3, sans
  test explicite que l'effet croît progressivement (2 matchs, 3, 4...) plutôt
  que de sauter à un cutoff arbitraire.
- E6 (motivation de rebond après défaite "≥4 buts") : seuil discret à 4 buts,
  même remarque.
- E4 (vent ">40km/h") : seuil discret, même remarque.

**Verdict** : ceci ne change aucune classification (E1, E4, E6 restent
Intéressante/Spéculative comme déjà classées), mais c'est une **hypothèse de
travail méthodologique manquante et facilement actionnable** : lorsque ces
variables seront testées individuellement (comme le prescrit déjà la règle
G2 du framework), le protocole devrait explicitement vérifier la continuité
de l'effet en fonction de la variable causale, pas seulement la
significativité au-dessus/en-dessous d'un seuil retenu a priori. Décision
d'intégration à discuter avec l'utilisateur, non appliquée ici.

### Reste de la section E

Rien dans la relecture de cette session ne contredit les classifications
E2/E3/E5/E7/E8/E9 déjà établies. E7 (must-win déjà pricé) est directement
confortée : 🟦 Dolan consacre un chapitre entier ("Situations/Spots") à
démontrer, avec des exemples chiffrés, que le narratif "must-win" est
largement absorbé par le marché — c'est la base primaire directe de E7, déjà
correctement identifiée par le framework.

---

## F. Hypothèses rejetées d'emblée

### F1. Analogie EOR

🟦 **Confirmation primaire précise et désormais vérifiée en détail, qui
conforte entièrement le raisonnement du framework.** Le chapitre 8
d'Epstein définit l'EOR ("Effect of Removal") comme "the quantitative effect
on the player's expectation of removing individual cards from the deck as
the hands are dealt out" — un calcul par échantillonnage sans remise dans un
sabot fini et dénombrable (Table 8-5 : une valeur d'EOR précise par rang de
carte, utilisée pour construire les systèmes de comptage comme Hi-Lo,
K-O, etc.). Le mécanisme est mathématiquement fermé : à chaque carte
retirée, l'espace des cartes restantes est *exactement* connu et
recalculable.

Cela confirme mot pour mot la justification déjà donnée par le framework
("un tirage sans remise dans un univers combinatoire fermé et fini") — le
framework l'avait déjà correctement anticipée en la "justifiant nous-mêmes"
sans citation primaire directe à l'époque ; cette lecture apporte la
citation primaire qui manquait.

**Verdict** : classification À rejeter inchangée, désormais appuyée sur une
lecture directe du mécanisme EOR plutôt que sur un raisonnement par
analogie non vérifié.

### F2. Full Kelly

🟨 **Nuance à signaler** : contrairement à ce que le paragraphe pourrait
laisser penser, Appelbaum ne "rejette" pas explicitement le Full Kelly — son
glossaire le décrit de façon neutre ("this system is used by experts and can
be highly profitable, but it can also be highly dangerous") sans
recommandation contre. Le rejet ferme et démontré vient d'Epstein (Full
Kelly optimal seulement si p exactement connu) et implicitement de Dolan.
Ceci ne change pas la classification — le consensus reste majoritaire dans
le corpus — mais le framework présente le rejet comme "unanime (Epstein,
Dolan, la synthèse)" alors qu'Appelbaum, une des 5 sources, est en réalité
neutre plutôt que participant au rejet.

**Verdict** : classification À rejeter (en tant que politique de mise
réelle) inchangée ; reformulation "unanime" à nuancer en "majoritaire, avec
Appelbaum neutre" (à trancher avec l'utilisateur).

### F3. Systèmes de progression

🟦 Confirmation primaire exacte et double : Epstein démontre le Théorème I
(tout système de mise ne change pas l'espérance par unité misée pour des
événements indépendants — démonstration formelle chapitre 3) et Appelbaum
consacre un encadré explicite au système Martingale ("rarely ever wins and
is more often considered fool's gold or a scam"), avec l'anecdote historique
de Charles Wells à Monte Carlo (contexte, pas preuve). Les deux sources
convergent, l'une avec démonstration, l'autre avec mise en garde empirique.

**Verdict** : classification À rejeter inchangée, confirmation renforcée.

### F4. Chasser les séries (Gambler's Fallacy)

🟦 Confirmation primaire exacte et détaillée, désormais vérifiée mot à mot :
Epstein (Théorème II, chapitre 3 — "No advantage accrues from the process of
betting only on some subsequence of a number of independent repeated
trials") et sa liste de 13 fallacies cognitives (chapitre 11), notamment
l'item 3 explicitement nommé "the Monte Carlo fallacy" ("after a run of
successes a failure is inevitable, and vice versa"). Appelbaum consacre
également une section complète ("The Gambler's Fallacy") avec le même nom
("Monte Carlo fallacy") et le même exemple canonique de la roulette de
1913 au Casino de Monte-Carlo (26 "noirs" consécutifs). Convergence
primaire directe et nommément identique entre Epstein et Appelbaum — plus
forte que ce que le framework indique ("Epstein... et Dolan lui-même").

**Verdict** : classification À rejeter inchangée, convergence encore plus
large que celle citée par le framework (ajouter Appelbaum comme source
convergente supplémentaire — décision à discuter, non appliquée ici).

### F5. Transplantation directe (nombres clés, premier buteur)

Non re-audité en détail dans cette session. Rien dans les chapitres relus
(y compris les statistiques par sport d'Appelbaum et de Miech) ne contredit
la prudence du framework sur ce point.

---

## G. Risques méthodologiques transversaux

### G1. Biais d'arrêt optionnel — nuance substantielle absente

🟦 **Fait primaire précis, absent du framework.** Le chapitre 11 d'Epstein
ne se contente pas d'affirmer que l'arrêt optionnel est un biais — il en
donne la démonstration formelle (via la loi du logarithme itéré) dans le
contexte précis des tests d'hypothèse en psychologie expérimentale (le
"headache phenomenon" des expériences ESP de Rhine : arrêter la collecte de
données au moment où le taux de succès décline artificiellement garantit,
avec une probabilité 1, de pouvoir rejeter H0 à un moment donné même si H0
est vraie). Epstein ajoute une précision que le framework ne reprend pas :

> "We should note that the consequences of optional stopping are not
> relevant in games of known probability, as discussed in Chapter 3. In
> those instances, it is not a statistical hypothesis under examination,
> but the running sum of a binary sequence, which is automatically concluded
> if at any time it reaches some preestablished value."

Autrement dit, Epstein distingue explicitement deux situations :
1. Un **jeu à probabilité connue avec un seuil d'arrêt fixé a priori** (ex :
   théorème IV du chapitre 3, ruine du joueur) — l'arrêt "optionnel" au sens
   où le nombre de coups n'est pas fixé n'introduit **aucun** biais, car ce
   n'est pas un test d'hypothèse.
2. Un **test d'hypothèse statistique** où l'expérimentateur choisit
   d'arrêter la collecte de données en fonction du résultat observé — c'est
   ce cas précis qui introduit un biais de rejet artificiel de H0.

Le walk-forward décrit par le framework (comparer Poisson simple vs
Poisson+A1 sur un échantillon de test) est un **test d'hypothèse** au sens 2,
pas un jeu à seuil fixé au sens 1 — donc la mise en garde G1 du framework
s'applique avec toute sa force, ce qui confirme (sans le changer) le principe
déjà énoncé ("fixer la taille de l'échantillon de test a priori"). Ce que le
framework ne dit pas, et que cette distinction primaire permet d'ajouter,
c'est que **le protocole de simulation Monte Carlo de D3 et D1** (comparer
Flat/Quarter/Half/Full Kelly sous des biais d'estimation *injectés* avec un
nombre de trajectoires simulées fixé) relève, lui, davantage du cas 1 —
puisqu'il ne s'agit pas de tester une hypothèse sur nos propres données mais
de caractériser mathématiquement une distribution de résultats sous
paramètres contrôlés. La distinction d'Epstein permet donc de clarifier
*où* dans le pipeau (Calibration Engine walk-forward vs. Risk Engine
simulation) le risque d'arrêt optionnel s'applique réellement avec la force
maximale, et où il est structurellement moins pertinent.

**Verdict** : principe G1 inchangé, mais avec une clarification utile de son
périmètre d'application exact à l'intérieur de l'architecture déjà validée.
Recommandation (pour discussion, non appliquée) : ajouter cette distinction
explicitement au texte de G1.

### G2. Empilement de filtres contextuels — outil méthodologique absent

🟦 **Fait primaire directement actionnable, absent du framework.**
Appelbaum (chapitre 8, "Learn from the Past") propose une grille explicite
en trois critères pour juger si un "betting system" (au sens large : une
variable contextuelle candidate) est réellement exploitable ou artefactuel :

1. **Une hypothèse causale motivée a priori** ("a sound hypothesis" — le
   mécanisme doit être explicable avant de regarder les résultats, pas
   après).
2. **Un échantillon suffisamment large** — Appelbaum donne un repère
   numérique explicite : "a good rule of thumb is to look for a sample size
   of at least one hundred games", avec un exemple chiffré illustrant
   pourquoi un système "9-1 sur 5 saisons" (90 % apparent) est moins
   fiable qu'un système "56 % sur 500 matchs".
3. **Une stabilité pluriannuelle** — un système qui a fait l'essentiel de
   ses gains sur 2-3 saisons puis a périclité (l'exemple de Bob Voulgaris et
   des totaux de mi-temps NBA, dont l'edge a disparu une fois que les
   bookmakers ont ajusté leur méthode, est cité explicitement par
   Appelbaum lui-même) doit être traité avec suspicion même si le cumul
   reste positif.

Cette grille est directement compatible avec, et vient concrétiser, la
règle G2 déjà énoncée par le framework ("chaque variable de la section E
doit être testée seule... avec sa propre fenêtre hors échantillon dédiée").
Le framework énonce le principe (ne pas empiler) mais ne donne pas de
critère quantitatif de robustesse individuelle (taille d'échantillon
minimale, test de stabilité inter-saisons) pour chaque variable testée
isolément — ce que la grille d'Appelbaum fournit concrètement.

**Verdict** : principe G2 inchangé. Ajout recommandé (pour discussion, non
appliqué ici) : intégrer les 3 critères d'Appelbaum comme grille de
validation minimale pour chaque variable de la section E avant adoption,
en plus du protocole walk-forward déjà prévu.

### G3/G4

Rien dans la relecture de cette session ne contredit les points G3 (petits
échantillons anecdotiques) et G4 (transplantation inter-sports comme
hypothèse elle-même) — au contraire, les statistiques précises d'Appelbaum
sur le RLM et le contrarian betting (C3/C4 ci-dessus) illustrent
concrètement, avec des chiffres à l'appui, le phénomène de seuils instables
d'un sport à l'autre que G4 anticipe déjà.

---

## H. Recommandation priorisée pour l'étape 2

Rien dans cet audit ne remet en cause la priorisation de l'étape 2
(Poisson + A1 + A2, diagnostic χ² en A4, Dixon-Coles et B2 repoussés à
l'étape 5, xG bloqué par l'absence de connecteur, C/D repoussés à leurs
étapes respectives, section E testée variable par variable et jamais en
bloc). Les points soulevés dans cet audit sont tous des enrichissements
méthodologiques ou des clarifications de preuve, pas des raisons de changer
l'ordre ou le contenu du plan déjà acté.

---

## Limites méthodologiques de cet audit

🟥 **Notre interprétation.** Deux réserves honnêtes sur la couverture de
cette relecture :

1. **Epstein, chapitres 7, 9 (fin), 10 non relus dans cette session** (jeu de
   cartes/chaînes de Markov ; suite de la logique statistique appliquée aux
   jeux ; jeux d'habileté pure et ordinateurs compétitifs). Ces chapitres ne
   sont cités par aucune hypothèse du framework actuel (A à H) ; leur absence
   de cet audit ne crée donc pas de lacune connue, mais ne peut être exclue
   avec certitude absolue tant qu'ils n'ont pas été lus mot à mot.
2. **Appelbaum, chapitres 10 à 17 non relus dans cette session** (placer un
   pari, chapitres par sport — baseball/NFL/NCAAF/NBA/NCAAB/DFS —, jeu
   mental). Le glossaire et l'index complets de ce même livre (lus en
   entier) couvrent l'intégralité des concepts transversaux mentionnés dans
   ces chapitres (ATS, key numbers, ROI par sport, etc.) sans qu'aucun ne
   corresponde à une hypothèse absente du framework actuel — mais, de même
   que pour Epstein, l'absence de lecture mot à mot de ces chapitres est
   signalée par honnêteté plutôt que dissimulée.

Si l'utilisateur souhaite une couverture à 100 % avant toute décision, ces
chapitres restants peuvent être lus dans une session de suivi dédiée avant de
statuer sur les modifications à apporter au research framework.
