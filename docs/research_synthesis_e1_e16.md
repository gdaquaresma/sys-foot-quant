# Synthèse consolidée E1 → E16

**Nature de ce document.** Synthèse pure : aucune nouvelle expérience,
aucun nouveau modèle, aucune nouvelle donnée, aucun nouveau backtest,
aucune optimisation, aucune modification du moteur de production, aucun
code de moteur final écrit ici. Ce document réutilise exclusivement les
conclusions déjà établies et documentées dans `docs/research_framework.md`
(sections I → AA, plus les diagnostics J/K/L qui ont directement motivé
E2). Aucun résultat historique n'est modifié. Toute classification
respecte la règle épistémique du projet, rappelée une fois pour toutes :
**une absence de preuve n'est jamais transformée en preuve d'absence**,
sauf lorsqu'un test statistique dédié a explicitement démontré une absence
de signal selon un protocole pré-enregistré (c'est le cas d'E1, E10 §4,
E12, E13, E16 — jamais le cas d'un simple IC95% couvrant 0 par manque de
puissance).

Légende de classification utilisée dans la matrice (section 1) :

| Symbole | Signification |
|---|---|
| 🟢 | **VALIDÉ** — résultat démontré statistiquement selon un protocole pré-enregistré, reproduit sur au moins une dimension de robustesse (championnat, saison, ou modèle) |
| 🟡 | **PROMETTEUR — À CONFIRMER** — signe directionnel cohérent mais non démontré statistiquement (IC95% couvrant 0), ou démontré sur un sous-ensemble seulement |
| 🔴 | **REJETÉ — NON DÉMONTRÉ** — hypothèse testée et infirmée : IC95% entièrement défavorable, ou verdict contradictoire pré-enregistré |
| ⚪ | **LIMITE — ABSENCE DE PREUVE** — IC95% couvrant 0 sans direction nette, ou question non testable avec les données actuelles (jamais lu comme « pas de signal ») |

---

## 1. Matrice consolidée E1 → E16

**Diagnostics intermédiaires (entre E1 et E2), réutilisés sans recalcul** :
le diagnostic post-E1 (section J) a établi qu'aucune information
indépendante n'était détectable dans le désaccord `poisson_simple`/marché
(1X2, IC95% couvrant 0 sur les trois issues) et que les erreurs de
`xg_model` sont **plus** corrélées au marché (+0.845) que celles de
`poisson_simple` (+0.789) — le xG ne comble pas un angle mort du marché.
Le diagnostic K a établi que les trois modèles surestiment systématiquement
le total de buts, concentré dans la queue haute (facteur 2-3). Le
diagnostic L a établi un skill négatif par rapport à la climatologie sur
les six combinaisons testées (biais de calibration dominant une résolution
positive mais faible), motivant directement la recalibration testée en E2.
Ces trois diagnostics sont classés ⚪/🔴 selon la même grille et ont un
rôle causal direct dans la matrice ci-dessous (colonne « Conséquence »).

| ID | Question | Données | Méthode | Résultat principal | Métrique | Preuve | Verdict | Conséquence architecturale | Retenu / Rejeté |
|---|---|---|---|---|---|---|---|---|---|
| **E1** | `poisson_simple` bat-il B365 sur le 1X2 (règle EV>0 pré-enregistrée) ? | 1888 paris réels, B365 1X2 | Bootstrap apparié sur profit/pari | ROI −6.9 %, IC95 % entièrement négatif, sans exception sur 9 découpes | Profit moyen/pari, IC95 % | 🔴 démontré | **SIGNAL NÉGATIF** | Le marché n'est pas un adversaire à battre ; `poisson_simple` reste la référence mais n'est jamais présenté comme supérieur au marché | Rejeté (stratégie EV>0 brute) |
| **E2** | Une recalibration isotonique post-hoc améliore-t-elle les probabilités O/U ? | Split 40/30/30, `poisson_simple`/`xg_model` | Régression isotonique (PAVA), walk-forward simple | Amélioration démontrée sur 4/6 combinaisons (3 seuils xg_model, O3.5 poisson_simple), jamais de dégradation | Brier, IC95 % | 🟢 partiel / 🟡 partiel | Amélioration ciblée, non uniforme | Motive une recalibration walk-forward généralisée (→E7/E8) plutôt qu'une isotonique indépendante par seuil | Étape intermédiaire, dépassée par E7/E8 |
| **E3** | Les probabilités calibrées d'E2 sont-elles fiables sur des matchs futurs ? | Même split qu'E2 | Tables de fiabilité complètes (10 tranches) | Fiabilité confirmée en zone peuplée (57.0 %→55.3 % observé, xg_model) ; O3.5 non vérifiable (zones 50 %+ vides) | Écart annoncé/observé | 🟢 partiel | Fiabilité confirmée là où testable | Confirme la viabilité d'une couche de calibration mais révèle une limite de couverture par seuil | Retenu comme validation de méthode, dépassé par E7/E8 |
| **E4** | L'espérance de buts prédite discrimine-t-elle réellement les matchs ? | 640 matchs test, espérance brute | Tranches fixes + quintiles + corrélation | Discrimination réelle et quasi-monotone au niveau global (corr ~0.16) ; **absente en Premier League** (corr −0.02/+0.01) | Corrélation, biais | 🟢 global / 🔴 Premier League | Discrimination confirmée globalement, absente en PL | Première apparition du problème Premier League (repris 2×, E11 puis E15) | Retenu (discrimination brute) ; PL flaggé |
| **E5** | Le modèle reste-t-il fiable quand il diverge du marché (O2.5) ? | 542 matchs, gap modèle/marché | Tranches de désaccord fixes, IC95 % | Excellente calibration en zone d'accord (biais <0.3pt) ; désaccord fort → biais croissant **dans le sens qui invalide** l'opinion du modèle | Biais par tranche | 🔴 démontré (poisson_simple) | Le désaccord ne se valide pas | Le désaccord modèle/marché ne doit jamais être lu comme un signal | Rejeté (désaccord comme signal) |
| **E6** | Le marché apporte-t-il une information incrémentale sur le total de buts ? | 542 matchs, corrélations + tests conditionnels | Bootstrap non apparié, stratification par tranche | Ni A ni B démontrés statistiquement ; résolution du marché ≥ modèle sur 11/12 combinaisons | Résolution (Brier decomposition) | ⚪ (redondance dominante) | Redondance, jamais infériorité du modèle démontrée en sens inverse | Le marché reste au moins aussi informé ; motive de représenter fidèlement le total plutôt que chercher à le battre | Retenu (constat de redondance) |
| **E7** | Peut-on construire une distribution du total de buts cohérente et mieux calibrée ? | 640 matchs test, λ/μ | Correction scalaire `c=E[réel]/E[λ+μ]` sur calibration, matrice reconstruite | Brier amélioré (IC95 % entièrement négatif, 3 modèles) ; biais d'espérance ramené à quasi-zéro ; queue P(≥6) corrigée | Brier à 7 catégories | 🟢 démontré | Fondation officielle de la distribution du total de buts | Une seule matrice, jamais des seuils recalibrés séparément | **VALIDÉ — production** |
| **E8** | La correction E7 tient-elle en walk-forward strict hors échantillon ? | 640 matchs test, `c(m)` par match | Fenêtre expansive stricte (jamais de fuite inter-championnats) | Amélioration confirmée intégralement, aucune inversion sur 18 découpes, CV(c) ≤2.6 % | Brier, IC95 % | 🟢 démontré | **VERDICT A** pour les 3 modèles | Couche de correction officielle du moteur | **VALIDÉ — production** |
| **E9** | Peut-on construire une couche multi-bookmakers propre pour détecter anomalies/arbitrage ? | 1806 matchs, B365/BW/PS | Consensus, anomalie (seuils pré-enregistrés), arbitrage mathématique | 1X2 : 0 anomalie/13926, 0 arbitrage ; O/U 2.5 : 1 seul bookmaker, non évaluable | % anomalies, % arbitrage | ⚪ (infrastructure propre, rien détecté) | Infrastructure validée, aucun signal | Confirme la limite structurelle Football-Data sur l'O/U (un seul bookmaker) | Infrastructure retenue (audit uniquement) |
| **E10** | Existe-t-il des zones de désaccord modèle/marché historiquement fiables (O/U 2.5) ? | 542 matchs, gap E8 | Tranches fixes (identiques E5) + test d'asymétrie | Aucune zone de désaccord fiable ; asymétrie significative (poisson_simple) dans le sens **opposé** à l'hypothèse | Biais par tranche, IC95 % | 🔴 démontré | Aucune zone de désaccord conservée | Confirme et étend E5 au marché O/U | Rejeté (désaccord comme signal, confirmation n°2) |
| **E11** | Les probabilités de buts sont-elles fiables en absolu, et où ? | 640 matchs, 5 seuils (0.5–4.5) | Calibration absolue (10 tranches), pente de Cox, comparaison inter-modèles | Zone [0.4-0.6) bien calibrée ; **[0.6-0.7) sur-confiance significative, 3 modèles** ; `poisson_simple`/`xg_model` **statistiquement indiscernables** (5 seuils) ; PL confirmée non-discriminante (3ᵉ fois) | Biais par tranche, diff Brier appariée | 🟢 (calibration centrale) / 🔴 (zone [0.6,0.7)) | Cartographie complète de la fiabilité | Identifie précisément la zone à risque et confirme l'indistinguabilité des 3 modèles | Zone [0.6,0.7) flaggée ; aucun modèle éliminé |
| **E12** | Les zones fiables coïncident-elles avec les plus grands écarts de prix (O2.5) ? | 640/542 matchs | Grille de verdict à 4 niveaux, pré-enregistrée | `poisson_simple`/`dixon_coles` : **CONTRADICTOIRE** (zones fiables = écarts **plus petits**) ; `xg_model` : directionnelle non démontrée | diff \|gap\| IC95 % | 🔴 (poisson/DC) / 🟡 (xg) | L'intersection recherchée n'existe pas | Le plus grand écart de prix coïncide avec une zone où le **modèle** a tort, pas le marché | Rejeté (fiabilité×écart comme filtre de sélection) |
| **E13** | La dispersion multi-bookmakers est-elle informative ? Existe-t-il un arbitrage historique ? | 1806 matchs, B365+PS (O/U), 5 bookmakers (1X2) | Test dispersion haute/basse, consensus vs B365 seul, arbitrage mathématique | Absence de preuve sur les deux marchés (IC95 % couvrant 0) ; 0/1806 arbitrage ; consensus n'améliore pas B365 seul | diff Brier, IC95 % | ⚪ | Aucune information incrémentale, aucun arbitrage | Confirme et généralise E9 avec Pinnacle inclus | Rejeté (dispersion/arbitrage comme source d'edge) |
| **E14** | Une recalibration ciblée de la zone [0.6,0.7) est-elle exploitable sans casser la cohérence O/U ? | 640 matchs, zone n=117-128 | Isotonique + logistique, walk-forward, gate de cohérence obligatoire | `xg_model` : non démontré ; `poisson_simple` : démontré **mais gate de cohérence violé** (14-24/640, amplitude 0.169) et non stable par championnat | Brier local, violations de gate | 🟡 (poisson, invalidé par le gate) / 🔴 (xg) | Zone documentée comme limite structurelle, non corrigée | **E14 explicitement exclu de la production** | **REJETÉ comme couche de production** |
| **E15** | L'absence de discrimination en Premier League a-t-elle une cause identifiable ? | 3 championnats × 2 saisons, diagnostic pur | Audit données, réplication, dispersion réelle, calibration/discrimination A/B/C/D, bootstrap+permutation | Anomalie de données écartée ; sous-puissance écartée (3/4 tests) ; dispersion réelle des buts ne différencie pas PL/Liga ; PL = classe **B** (calibrée, non discriminante) | Corrélation, classification A/B/C/D | ⚪ (cause non identifiée, phénomène confirmé) | **ABSENCE DE SIGNAL CONFIRMÉE MAIS INEXPLIQUÉE** | Règle de gating analytique proposée (jamais une règle de pari) | PL flaggée en gate ; aucun coefficient créé |
| **E16** | Le mouvement de marché ouverture→clôture contient-il une information incrémentale ? | 1806 matchs, B365 (+PS secondaire) | 5 modèles walk-forward (O/C/M/O+M/O+C), Holm-Bonferroni sur 4 hypothèses | Les 4 hypothèses primaires **non rejetées** après correction ; M seul pire que O (mécanisme validé) ; O+C rétrospectif n'améliore pas non plus O | Diff Brier, p corrigé | 🔴 démontré | **MOUVEMENT NON INFORMATIF** | Le marché d'ouverture contient déjà l'essentiel de l'information détectable | Rejeté (mouvement comme feature de décision) |

---

## 2. Briques définitivement validées

### 2.1 Les trois modèles de buts — aucun rang inventé

`poisson_simple`, `dixon_coles` et `xg_model` restent, à l'issue d'E1-E16,
dans l'état suivant, **sans qu'aucune hiérarchie ne soit démontrée** :

- **`dixon_coles` vs `poisson_simple`** : mathématiquement **identiques**
  sur Over 2.5 et Over 3.5 (la correction Dixon-Coles ne touche que les
  cellules de score total ≤2, établi en K et reconfirmé à chaque
  expérience O/U ultérieure) ; un écart minime existe sur Over 1.5 (K)
  jamais caractérisé plus finement. `dixon_coles` est donc **redondant
  avec `poisson_simple` sur l'Over/Under 2.5/3.5 spécifiquement** — un
  fait mathématique démontré, pas une hiérarchie de qualité globale (rien
  n'a été testé sur le score exact ou les marchés bas-score, hors
  périmètre d'E1-E16).
- **`poisson_simple` vs `xg_model`** : après correction E7/E8, **aucune
  différence statistiquement significative** sur aucun des 5 seuils O/U
  (E11 §3, comparaison appariée sur les mêmes matchs). Avant correction,
  `xg_model` avait un biais d'espérance 2× plus fort (K) et une erreur
  plus corrélée au marché (diagnostic post-E1) — mais ce désavantage brut
  disparaît une fois la correction walk-forward appliquée. **Aucun
  vainqueur n'est désigné, conformément au protocole d'E11.**
- Conséquence : il n'existe **aucune justification scientifique tirée
  d'E1-E16 pour retirer un des trois modèles**, ni pour en désigner un
  supérieur. `dixon_coles` est la seule brique dont la redondance *sur
  l'O/U* est un fait mathématique démontré ; `xg_model` reste
  complémentaire mais non supérieur, avec une dépendance de données
  supplémentaire (xG Understat) que `poisson_simple` n'a pas. Les garder
  tous les trois comme modèles parallèles (un modèle de référence +
  modèles de contrôle) est un **choix architectural raisonnable**, pas
  une conclusion imposée par les données — voir section 12.

### 2.2 La correction E7/E8 — ce qu'elle corrige précisément

- **Ce qu'elle corrige** : un biais de **moyenne** du total de buts prédit
  (`E[λ+μ]` trop élevé), pas un biais de forme — établi par comparaison
  directe à un Poisson évalué à la bonne moyenne empirique (indice de
  dispersion 0.9611, quasi-superposition, E7 §2). Le biais se manifestait
  principalement dans la **queue haute** (6+ buts surestimés d'un facteur
  2-3, K/E7).
- **Comment elle est estimée** : `c = E[total_réel] / E[λ+μ_prédit]`, un
  **unique** degré de liberté, estimé exclusivement sur les données de
  calibration disponibles **avant** le match évalué (walk-forward strict
  depuis E8, corrigeant un risque de fuite inter-championnats identifié
  dans le split poolé d'E7). Appliqué multiplicativement à `(λ, μ)` avant
  reconstruction complète de la matrice de score.
- **Pourquoi walk-forward** : le split poolé d'E7 laissait `c` être ajusté
  sur une fenêtre de calibration qui, pour certains championnats,
  s'étendait *après* le début du test d'un autre championnat — un risque
  de fuite documenté et corrigé en E8 par un facteur `c(m)` réestimé par
  match, strictement à partir des matchs antérieurs.
- **Propriétés garanties** : cohérence **par construction** (jamais
  vérifiée a posteriori) entre `total_goals_distribution` et tous les
  seuils Over/Under dérivés de la même matrice — contrairement à une
  calibration isotonique indépendante par seuil (E2/E3), dont le risque
  d'incohérence croisée reste réel en principe (démontré : 0 violation
  observée sur ce corpus précis, mais l'absence de garantie structurelle
  est actée, E7 §3).
- **Seuils affectés** : tous les seuils dérivés de la matrice corrigée —
  testés jusqu'à présent sur 0.5/1.5/2.5/3.5/4.5 (E11). Le biais de
  calibration diminue sur les 9 combinaisons modèle×seuil testées en E7 ;
  la résolution est préservée ou légèrement améliorée dans 7/9 cas.
- **Statut** : **VALIDÉ SCIENTIFIQUEMENT** (Verdict A, E8, pour les trois
  modèles) — c'est la seule couche de calibration/correction dont la
  production est aujourd'hui justifiée par les données.

### 2.3 E14 doit être explicitement rejeté comme couche de production

E14 a testé une **seconde** couche de calibration, ciblée sur la zone
[0.6,0.7) d'Over 2.5 identifiée en E11 comme significativement
sur-confiante. Résultat : `xg_model` ne montre aucune amélioration
démontrée ; `poisson_simple` montre une amélioration démontrée **mais
viole substantiellement le gate obligatoire de cohérence inter-seuils**
(14-24/640 matchs, amplitude jusqu'à 0.169 point de probabilité) et n'est
pas stable par championnat (portée principalement par la Premier
League — précisément le championnat déjà identifié comme non fiable en
E4/E11/E15). **E14 est donc explicitement exclu de toute intégration en
production** — la zone [0.6,0.7) reste une limite structurelle documentée,
non corrigée, du moteur E7/E8.

### 2.4 La représentation officielle : distribution jointe, pas des seuils indépendants

L'architecture retenue depuis l'origine — une **seule** matrice de score
`(λ, μ, ρ)` → correction scalaire walk-forward → `total_goals_distribution`
**et** `over_under_probs` dérivés du même objet — doit être conservée
plutôt que des probabilités indépendantes par seuil, pour trois raisons
démontrées :

1. Elle garantit la cohérence `P(O0.5) ≥ P(O1.5) ≥ ... ≥ P(O4.5)` **par
   construction**, jamais par vérification a posteriori (E7 §1, §3).
2. Une calibration isotonique indépendante par seuil (E2/E3) n'offre
   **aucune garantie mathématique** de monotonicité croisée entre seuils,
   même si aucune violation n'a été observée empiriquement sur ce corpus
   (E7 §3) — le risque reste réel en principe.
3. La correction unique corrige la **cause identifiée** du biais (un biais
   de moyenne, E7 §2) sans introduire de paramètres supplémentaires par
   seuil, minimisant le risque de surajustement.

---

## 3. Limites connues

### 3.1 Zone [0.6,0.7) d'Over 2.5

- **Magnitude du biais** : sur-confiance significative et reproduite sur
  les trois modèles — biais −0.11 à −0.12 (le modèle annonce ~64-65 %,
  la fréquence réelle n'est que ~52 %), IC95 % entièrement négatif (E11).
- **Incertitude** : zone construite sur n=117-128 matchs sur le corpus de
  test walk-forward — un effectif modeste, cohérent avec les limites de
  puissance documentées ailleurs dans le projet (section G2 du framework).
- **Pourquoi E14 n'a pas été intégrée** : l'amélioration locale démontrée
  pour `poisson_simple` viole le gate obligatoire de cohérence inter-seuils
  de façon substantielle et n'est pas stable par championnat/sous-période
  (portée principalement par la Premier League) — un rejet motivé par le
  protocole, pas par l'absence de tout signal local.

### 3.2 Premier League

- **Absence de discrimination confirmée** : établie indépendamment à trois
  reprises, sur trois mécanismes de mesure différents — espérance brute
  (E4, corr ≈0), distribution corrigée walk-forward (E11, corr ≈0 à
  légèrement négative), et diagnostic structurel dédié (E15).
- **Calibration correcte mais discrimination faible** : la classification
  A/B/C/D d'E15 place la Premier League en classe **B** (bien calibrée,
  non discriminante) pour les deux modèles testés — jamais en classe A
  (non calibrée) ni C. Le problème est spécifiquement un déficit de
  discrimination, pas un biais de calibration.
- **Cause non établie** : anomalie de données écartée (audit intégralement
  propre), sous-puissance écartée comme explication principale (3/4 tests
  de puissance + 2 tests de permutation significatifs), dispersion réelle
  des buts écartée (ne différencie pas PL de la Liga, qui discrimine
  normalement). Un mécanisme proximal (compression des prédictions du
  modèle) est mesuré mais **dérivé du modèle lui-même**, donc non
  qualifiant comme explication indépendante au sens de la grille de
  verdict d'E15. **Verdict officiel : ABSENCE DE SIGNAL CONFIRMÉE MAIS
  INEXPLIQUÉE.**
- **Règle possible, jamais un coefficient** : E15 propose une règle de
  **gating analytique** — « ne pas interpréter l'espérance de buts prédite
  comme un signal discriminant en Premier League » — explicitement jamais
  une règle de pari. **Interdiction explicite et non négociable** : créer
  un coefficient correctif Premier League sans une nouvelle expérience
  dédiée.

### 3.3 Marché

- **B365 au moins aussi bon que le modèle** : établi de façon répétée et
  cohérente — calibration du marché 3 à 9× meilleure que `poisson_simple`
  sur le 1X2 (diagnostic post-E1), résolution du marché ≥ modèle sur
  11/12 combinaisons (E6), aucune zone de désaccord fiable (E10), aucun
  écart de prix associé aux zones fiables du modèle (E12, résultat
  **contradictoire** pour `poisson_simple`/`dixon_coles`).
- **Le désaccord modèle/marché n'est pas démontré comme signal** :
  testé à trois reprises indépendantes sur trois marchés/populations
  différents (diagnostic post-E1 sur le 1X2, E5/E10 sur l'O/U 2.5) —
  jamais un IC95 % favorable au modèle ; au contraire, une asymétrie
  significative (E10 §4) montre que le désaccord éloigne systématiquement
  le modèle de la réalité, dans les deux directions.
- **Le multi-bookmaker n'apporte aucune information supplémentaire** :
  E9 (0 anomalie/13926 sur le 1X2, O/U structurellement non évaluable à un
  seul bookmaker) et E13 (dispersion non informative sur les deux marchés
  une fois Pinnacle ajouté à l'O/U, 0/1806 arbitrage mathématique détecté,
  consensus statistiquement indiscernable de B365 seul).
- **Le mouvement ouverture→clôture n'apporte aucune information
  exploitable à l'ouverture** : E16, protocole complet (5 modèles, 4
  hypothèses primaires, correction Holm-Bonferroni) — toutes non
  rejetées ; le marché d'ouverture contient déjà l'essentiel de
  l'information détectable sur ce corpus.

---

## 4. Rôle exact du marché

**Point critique, explicitement tranché par E1-E16** : le moteur ne doit
**jamais** être conçu selon une hypothèse implicite « modèle > marché ».
Aucune des 16 expériences ne démontre une supériorité du modèle sur le
marché ; la quasi-totalité démontre l'inverse ou une équivalence. La
seule architecture cohérente avec ce constat est :

```
modèle → probabilité   +   marché → benchmark/prix   +   gates   →   décision
```

où le marché n'est **jamais** une cible à battre mais une **référence de
prix et de qualité de calibration** contre laquelle le modèle est
constamment audité.

**Définitions précises, imposées par le protocole** :

| Terme | Définition | Statut |
|---|---|---|
| **Probabilité modèle** (`p_model`) | Probabilité issue de la distribution de score corrigée walk-forward (architecture E7/E8), pour un des trois modèles (statistiquement indiscernables entre eux sur l'O/U, E11) | Objet **VALIDÉ** (calibration démontrée dans les zones testées) |
| **Probabilité implicite de marché** (`p_market`) | 1/cote décimale, débarrassée de l'overround par `remove_overround_proportional` (inchangé depuis E1) | Objet **VALIDÉ** (méthode de retrait de marge éprouvée depuis l'origine du projet) |
| **Cote/prix juste** (`fair price`) | `1 / p_model` — la cote théorique qu'impliquerait la probabilité du modèle si elle était mise sur le marché | Quantité calculable, jamais elle-même « juste » au sens où elle battrait le marché — c'est une transformation, pas une validation |
| **Edge théorique** | `p_model − p_market` (ou l'équivalent en cotes) | **Jamais appelé « value »** dans ce document ni dans le moteur futur tant que sa relation au prix et à l'incertitude n'est pas établie — voir ci-dessous |
| **Confiance** | Qualification de l'incertitude attachée à `p_model` dans une situation donnée : dépend (a) de la tranche de calibration (E11 : zone [0.4-0.6) fiable, [0.6-0.7) biaisée), (b) du championnat (Premier League : discrimination non démontrée), (c) de la taille d'échantillon disponible pour la cellule concernée | Concept défini, seuils numériques non fixés (section 5) |
| **Décision** | Action finale BET/NO BET | Non définie à ce stade — aucune règle de conversion probabilité→pari n'a été validée par E1-E16 (voir section 13) |
| **Abstention** | État par défaut en l'absence de validation complète des gates | Voir section 5 |

**Pourquoi `edge` n'est jamais « value »** : le terme « value » impliquerait
que l'écart `p_model − p_market` prédit une fréquence réelle plus proche de
`p_model` que de `p_market`. C'est précisément ce qui a été testé — et
**infirmé** — à trois reprises (diagnostic post-E1, E5, E10) et une
quatrième fois de façon contradictoire (E12 : les zones où le modèle est
fiable ont des écarts de prix **plus petits**, pas plus grands, avec le
marché). Tant qu'aucune expérience ne démontre qu'un `edge` donné, dans
une zone de confiance donnée, prédit une fréquence réelle nette de
l'incertitude, ce terme reste interdit dans le moteur.

---

## 5. Principe d'abstention

L'abstention (`NO BET`) est **l'état par défaut** du moteur — un pari
n'est jamais la sortie par défaut d'un calcul de probabilité. Les
circonstances suivantes déclenchent une abstention obligatoire, chacune
distinguée entre **GATE SCIENTIFIQUE** (mécanisme dont l'existence est
démontrée par E1-E16, seuil numérique non fixé) et **SEUIL OPÉRATIONNEL
À ESTIMER** (valeur numérique qui resterait à déterminer, jamais fixée
arbitrairement dans cette synthèse) :

| Circonstance | Statut | Justification (E1-E16) |
|---|---|---|
| Championnat sans discrimination démontrée (Premier League) | **GATE SCIENTIFIQUE** | E4/E11/E15 : absence de discrimination confirmée à trois reprises indépendantes |
| Zone de probabilité en biais de calibration démontré ([0.6,0.7) d'Over 2.5) | **GATE SCIENTIFIQUE** | E11 (biais démontré) + E14 (correction locale rejetée) |
| Edge trop faible | GATE SCIENTIFIQUE (le mécanisme « edge seul n'est pas fiable » est démontré) ; **le seuil numérique est un SEUIL OPÉRATIONNEL À ESTIMER** | E5/E10/E12 : le désaccord n'a jamais été validé comme signal, quelle que soit son amplitude |
| Incertitude trop élevée (effectif insuffisant dans la cellule considérée) | GATE SCIENTIFIQUE (convention n≥30 déjà utilisée systématiquement de E5 à E16) ; **le seuil exact de production reste un SEUIL OPÉRATIONNEL À ESTIMER** | Convention méthodologique constante du projet |
| Données insuffisantes (cote O/U indisponible à la décision, jour ambigu, historique insuffisant) | **GATE SCIENTIFIQUE** | Règles d'exclusion déjà implémentées et testées depuis E1 |
| Divergence modèle/marché non validée utilisée comme signal positif | **GATE SCIENTIFIQUE** | E5/E10/E12 : rejeté explicitement, y compris de façon contradictoire (E12) |
| Probabilités trop proches du bruit statistique inter-bookmakers | **GATE SCIENTIFIQUE** (la dispersion mesurée sur ce panel est démontrée non informative) | E9/E13 : dispersion trop faible et homogène pour constituer un signal |

Aucun seuil numérique n'est fixé dans ce document, conformément à la
consigne — leur estimation (si elle a lieu) devra faire l'objet d'un
protocole dédié, hors périmètre de cette synthèse.

---

## 6. Niveaux de sortie du moteur (conceptuel, seuils non fixés)

| Niveau | Nom | Contenu | Statut |
|---|---|---|---|
| 1 | **Projection** | Probabilité modèle seule (distribution corrigée E7/E8) | VALIDÉ pour les zones/championnats non flaggés |
| 2 | **Pricing** | Probabilité + cote juste dérivée | Calcul direct, jamais une prédiction supplémentaire |
| 3 | **Comparaison marché** | Cote juste + cote de marché (benchmark, jamais adversaire) | VALIDÉ comme outil d'audit ; jamais un signal en soi |
| 4 | **Qualification** | Application des gates de calibration/discrimination/données (section 5) | VALIDÉ (les gates eux-mêmes sont justifiés par les données) |
| 5 | **Décision** | BET/NO BET | **Non validé** — voir section 13 : aucune règle de conversion n'existe à ce jour au-delà de l'abstention |

---

## 7. Logique Over/Under

- **Lignes directement calculables** : 0.5/1.5/2.5/3.5/4.5, dérivées **en
  un seul appel** de la même matrice de score corrigée — propriété
  structurelle garantie depuis l'origine du projet et reconfirmée
  explicitement en E7 (§1) et E11 (Q3).
- **Lignes réellement validées expérimentalement (calibration walk-forward
  testée sur données réelles)** : principalement **1.5, 2.5, 3.5** —
  testées de façon répétée et approfondie (E2/E3/E7/E8/E11/E14). La ligne
  **2.5** est la seule pour laquelle une comparaison au marché existe
  (Football-Data ne publie que cette ligne, constat répété en E9/E12).
- **Lignes affichables mais non interprétables comme signal validé** :
  **0.5** et **4.5** — incluses dans la cartographie de calibration d'E11
  mais avec une masse concentrée sur 2-3 tranches extrêmes ; le rapport
  lui-même signale que « les pentes de Cox y sont peu fiables... doivent
  être lues avec prudence ». Elles peuvent être **affichées** (Niveau 1-2)
  mais ne doivent jamais être présentées comme un signal de discrimination
  ou de calibration démontré au même niveau que 1.5/2.5/3.5.
- **Limite structurelle des données actuelles** : Football-Data ne publie
  de cotes Over/Under que sur la ligne 2.5 (B365 et, depuis E13, Pinnacle
  partiellement) — **aucune comparaison au marché n'est possible** sur
  0.5/1.5/3.5/4.5 avec les données actuellement disponibles.

---

## 8. Rôle des trois modèles

**Aucune architecture d'ensemble n'a été testée par E1-E16 — l'ensemble
n'est pas validé expérimentalement.** Aucune expérience n'a mesuré une
moyenne, une pondération, ou une combinaison des sorties de
`poisson_simple`, `dixon_coles` et `xg_model`. Ce qui est établi :

- `dixon_coles` est **mathématiquement redondant** avec `poisson_simple`
  sur Over 2.5/3.5 (fait démontré, pas une opinion).
- `poisson_simple` et `xg_model` sont **statistiquement indiscernables**
  en Brier après correction E7/E8, sur les 5 seuils testés (E11) — ceci
  n'établit ni leur équivalence formelle, ni la supériorité de l'un,
  seulement l'absence de preuve de différence avec la puissance
  disponible.
- `xg_model` introduit une dépendance de données supplémentaire (xG
  Understat, avec une réserve documentée sur la stabilité temporelle de
  sa disponibilité) que `poisson_simple` n'a pas.

**Conséquence** : conserver un **modèle principal** (`poisson_simple`,
référence historique du projet, dépendance de données minimale) plus des
**modèles de contrôle** (`dixon_coles`, `xg_model`, conservés pour
traçabilité et comparaison continue, jamais fusionnés automatiquement) est
un **choix architectural raisonnable**, cohérent avec le statu quo déjà
documenté dans `architecture.md`, mais **ce n'est pas la seule
architecture possible** et **ce n'est pas une conclusion imposée par les
données**. Toute architecture d'ensemble (moyenne, vote, pondération
dynamique) reste une **hypothèse future** nécessitant une expérience
dédiée avant adoption.

---

## 9. Données nécessaires au moteur

**Obligatoires** :
- Résultats de matchs historiques horodatés point-in-time (buts marqués/
  encaissés par équipe) — fondation de `poisson_simple`/`dixon_coles`.
- Cotes B365 1X2 et Over/Under 2.5 **d'ouverture**, point-in-time, comme
  référence de marché (benchmark, jamais feature de décision autre que la
  comparaison).
- Métadonnées de championnat/saison/calendrier pour l'appariement
  point-in-time (déjà implémenté, `matching.py`/`time_resolution.py`).

**Optionnelles** :
- Features xG (Understat) pour `xg_model`, comme modèle de contrôle
  complémentaire — jamais indispensable, `poisson_simple` fonctionnant
  sans.
- Cotes Pinnacle (1X2 et O/U 2.5, ouverture) comme audit de second
  bookmaker — utilité démontrée **uniquement comme outil de vérification**
  (E13 a montré que le consensus B365+Pinnacle n'améliore pas B365 seul),
  jamais comme source d'edge.
- Cotes BW (1X2, ouverture) et WH/LB (1X2, ouverture, disponibilité
  saisonnière disjointe) — même statut : audit uniquement, utilité
  d'edge jamais démontrée (E9).

**Actuellement indisponibles** :
- Cotes Over/Under sur des lignes autres que 2.5, chez n'importe quel
  bookmaker (limite structurelle de Football-Data, constatée en E9/E12) —
  empêche toute validation de marché sur 0.5/1.5/3.5/4.5.
- Un timestamp d'odds réellement vérifié (seule une hypothèse
  conservatrice documentée, `TIMESTAMP_STATUS_HYPOTHETICAL`, est
  disponible depuis E1).
- Une mesure de dispersion de marché plus fine que l'ouverture/clôture
  (E16 a montré que même ce mouvement binaire n'est pas informatif — une
  granularité plus fine reste non testée faute de données).
- Une mesure véritablement **indépendante** du modèle pour la dispersion
  réelle du niveau des équipes en Premier League (E15 a explicitement
  écarté la dispersion des buts réels comme explication, et a proposé
  sans la tester une mesure externe — classement final, différentiel de
  buts par équipe — pour éviter toute sélection a posteriori).

**Intéressantes pour une future version** :
- Cotes Over/Under sur d'autres lignes (0.5/1.5/3.5/4.5), si un
  fournisseur les publiait — permettrait enfin de valider ou d'infirmer le
  marché sur ces lignes, actuellement affichables mais non validées
  (section 7).
- Une mesure indépendante de la force des équipes en Premier League
  (classement, valeur d'effectif) pour trancher le puzzle E15 sans
  sélection a posteriori.
- Un flux d'odds réellement horodaté (ex. API Pinnacle) pour retirer la
  réserve `TIMESTAMP_STATUS_HYPOTHETICAL`.
- Des relevés de marché plus fréquents qu'ouverture/clôture, pour tester
  si l'absence d'information du mouvement (E16) se généralise à une
  granularité plus fine.

**Rappel explicite** : la présence d'une donnée dans le corpus ne
justifie jamais son inclusion dans le moteur — chaque donnée listée
« optionnelle » ci-dessus a une utilité **démontrée uniquement comme outil
d'audit/vérification**, jamais comme source d'edge (E9/E13 pour le
multi-bookmaker).

---

## 10. Point-in-time et anti-fuite en production

Règles non négociables, toutes déjà implémentées et testées dans le
projet, à reconduire strictement dans le moteur final :

1. À l'instant de décision `T` (= `kickoff_utc − DECISION_OFFSET_HOURS`,
   règle conservatrice déjà documentée), le moteur ne peut utiliser
   **aucune** donnée dont `knowledge_time > T`.
2. Les cotes de **clôture ne doivent jamais** être utilisées comme feature
   d'une décision prise à l'ouverture — structurellement garanti et testé
   de façon exhaustive en E16 (champs retrospectifs strictement séparés,
   tests anti-fuite dédiés).
3. Tout paramètre ajusté (facteur de correction `c(m)`, courbe de
   recalibration, poids de régression) doit être estimé **exclusivement**
   à partir d'observations dont `decision_time` est strictement antérieur
   au match évalué — discipline walk-forward en fenêtre expansive
   (E8/E14/E16), jamais un ajustement poolé appliqué rétroactivement.
4. Les matchs à jour ambigu (lundi/mardi/vendredi) restent exclus (ou
   traités par une règle alternative explicite et testée), jamais rattachés
   par hypothèse silencieuse.
5. Contrôles de production obligatoires : (a) délégation intégrale du
   mécanisme point-in-time à `matching.py`/`time_resolution.py`, jamais
   réimplémenté ; (b) couverture de tests anti-fuite pour tout nouveau
   module, comme pour chacune des 16 expériences ; (c) une assertion
   explicite de `decision_time` avant toute émission de prédiction ; (d)
   `debug_get_full_table` (ou équivalent) jamais appelé depuis un chemin
   de décision (règle déjà actée dans `architecture.md`).

---

## 11. Architecture finale proposée

```
DONNÉES (résultats + cotes d'ouverture, point-in-time)
   → FEATURES (taux attaque/défense par équipe)
   → MODÈLE(S) (poisson_simple principal ; dixon_coles/xg_model en contrôle — aucun ensemble validé)
   → MATRICE DE SCORE UNIQUE (λ, μ, [ρ])
   → CORRECTION SCALAIRE WALK-FORWARD E7/E8 (validée)
   → DISTRIBUTION DE BUTS & PROBABILITÉS O/U (dérivées conjointement, cohérence garantie par construction)
   → GATES DE CALIBRATION/DISCRIMINATION (zone [0.6,0.7), championnat Premier League, effectif)
   → BENCHMARK DE PRIX MARCHÉ (B365 ouverture normalisé, Pinnacle en audit secondaire)
   → CALCUL DE L'EDGE (jamais appelé « value »)
   → ÉVALUATION D'INCERTITUDE (taille d'échantillon de la cellule, largeur d'IC, flags de limites connues)
   → GATES D'ABSTENTION (championnat, zone de calibration, disponibilité des données)
   → DÉCISION BET / NO BET
```

Ce schéma est cohérent avec E1-E16 **jusqu'à l'avant-dernière étape
inclusivement** — chaque bloc, du recueil des données jusqu'aux gates
d'abstention, s'appuie sur un résultat directement démontré. La **dernière
transformation** (edge + incertitude → décision positive de pari) n'est
**pas** couverte par une expérience validée : aucune règle convertissant
un edge qualifié en décision de pari rentable n'a jamais été testée dans
ce projet. Le schéma est donc retenu **jusqu'au Niveau 4 (Qualification)**
comme une conclusion d'architecture pleinement justifiée ; le Niveau 5
(Décision positive) reste, à ce stade, une abstention par défaut — voir
section 13.

---

## 12. Statut de chaque composant

| Composant | Statut |
|---|---|
| Pipeline point-in-time (appariement, `decision_time`, exclusions) | **VALIDÉ SCIENTIFIQUEMENT** — testé exhaustivement, 0 violation détectée sur tout le corpus réel, 16 expériences |
| `poisson_simple` comme modèle de référence | **CHOIX ARCHITECTURAL** — jamais détrôné, mais aussi jamais prouvé supérieur (E11) ; choix raisonnable par simplicité et antériorité |
| `dixon_coles`/`xg_model` conservés comme modèles de contrôle | **CHOIX ARCHITECTURAL** — aucun n'est scientifiquement inutile (E4 : xg_model discrimine ; K : dixon_coles diffère sur Over 1.5) mais aucun n'est prouvé supérieur non plus |
| Matrice de score unique → distribution jointe O/U | **VALIDÉ SCIENTIFIQUEMENT** (E7 §1, structurel + démontré supérieur en garantie de cohérence à une calibration indépendante par seuil) |
| Correction scalaire walk-forward E7/E8 | **VALIDÉ SCIENTIFIQUEMENT** (Verdict A, 3 modèles) |
| Recalibration locale E14 | **REJETÉ** — non intégré à la production |
| Gates de calibration/discrimination (concept) | **VALIDÉ SCIENTIFIQUEMENT** dans son principe (les biais qu'ils détecteraient — zone [0.6,0.7), Premier League — sont démontrés) ; **CHOIX ARCHITECTURAL** dans son implémentation exacte (blocage dur vs simple flag) |
| Marché comme benchmark plutôt qu'adversaire | **VALIDÉ SCIENTIFIQUEMENT** dans son constat (le marché égale ou bat le modèle sur toutes les dimensions testées) ; **CHOIX ARCHITECTURAL** dans la formulation « benchmark, jamais cible » |
| Edge = `p_model − p_market` (calcul) | **CHOIX ARCHITECTURAL** (calcul raisonnable) ; son interprétation comme signal est **REJETÉE** (E5/E10/E12) |
| Multi-bookmaker comme outil d'audit | **CHOIX ARCHITECTURAL** (inoffensif, utile en vérification) ; comme source d'edge : **REJETÉ** (E9/E13) |
| Mouvement de marché comme feature | **REJETÉ** (E16) |
| Ensemble des trois modèles | **HYPOTHÈSE FUTURE** — non testé, nécessite une expérience dédiée |
| Coefficient Premier League | **INTERDIT sans nouvelle expérience** (E15) ; une règle de gating (abstention) reste une **HYPOTHÈSE FUTURE** à formaliser opérationnellement |
| Règle de conversion edge → décision de pari | **HYPOTHÈSE FUTURE** — aucune règle de ce type n'a jamais été validée par E1-E16 |

---

## 13. Moteur final minimal viable

**Si la recherche s'arrêtait aujourd'hui, quelle est la version la plus
scientifiquement défendable que l'on puisse construire sans introduire
d'hypothèse non testée ?**

- **Données** : résultats point-in-time (buts) pour `poisson_simple` ;
  cotes B365 d'ouverture (1X2 + O/U 2.5) comme référence de prix
  uniquement.
- **Modèle** : `poisson_simple` → matrice de score → correction scalaire
  walk-forward E7/E8 → probabilités Over/Under pour les lignes
  **réellement validées** (1.5/2.5/3.5 en priorité ; 0.5/4.5 affichables
  avec réserve explicite).
- **Gates obligatoires** : (a) gate championnat — abstention/flag sur
  Premier League (E15) ; (b) gate de calibration — abstention/flag sur la
  zone [0.6,0.7) d'Over 2.5 (E11/E14) ; (c) gate de données — règles
  d'exclusion déjà en place (jour ambigu, historique insuffisant, cote
  incomplète).
- **Sorties livrables sans hypothèse nouvelle** : Niveaux 1 à 4
  (Projection, Pricing, Comparaison marché, Qualification) — chacun
  s'appuie directement sur un résultat démontré.
- **Niveau 5 (Décision)** : **la seule décision scientifiquement
  défendable aujourd'hui est l'abstention conditionnelle** — produire
  `NO BET` chaque fois qu'un gate échoue, et **ne produire aucune règle
  positive** convertissant une probabilité qualifiée en décision de pari,
  puisqu'aucune règle de ce type n'a jamais été validée par E1-E16 (E1 a
  même démontré qu'une telle règle simple, EV>0, est **perdante**). Le
  moteur minimal viable est donc un **moteur de projection, de pricing et
  de filtrage**, pas encore un moteur de décision de pari positive.

---

## 14. Composants explicitement rejetés / non soutenus

**Rejeté par un résultat statistique direct** :
- Recalibration locale ciblée de la zone [0.6,0.7) (E14) — gate de
  cohérence violé, instabilité par championnat.
- Mouvement de marché ouverture→clôture comme feature de décision (E16) —
  4 hypothèses primaires non rejetées après correction.
- Désaccord modèle/marché comme signal (diagnostic post-E1, E5, E10, E12)
  — jamais validé, et contredit de façon significative en E10 et E12.
- Coefficient Premier League créé sans nouvelle expérience — interdiction
  explicite du protocole E15.
- Arbitrage/dispersion multi-bookmaker comme source d'edge (E9, E13) — 0
  arbitrage détecté, dispersion non informative.
- Toute stratégie de pari présentée comme rentable sans expérience dédiée
  — E1 est la seule expérience économique réelle du projet et a démontré
  un ROI négatif significatif pour la règle testée (EV>0 brut) ; aucune
  autre règle n'a été testée depuis.
- Stratégie temps-décroissance A1, gate de désaccord B3.3 — rejetés par
  preuve directe d'infériorité (section G du framework, hors périmètre
  E1-E16 mais rappelé pour cohérence).

**Non soutenu faute de validation (absence de preuve, pas preuve
d'absence — à ne jamais présenter comme « rejeté »)** :
- Ensemble des trois modèles (moyenne/vote/pondération) — jamais testé.
- A2 (HFA dynamique par équipe), B2 (bayésien séquentiel), B3/B3.2 (xG,
  hybride) comme remplacement de `poisson_simple` — absence de preuve
  d'amélioration démontrée, jamais une infériorité démontrée ; restent en
  statut expérimental, non promus en production.
- Toute règle numérique de seuil d'edge, de confiance, ou d'effectif
  minimal pour la production — délibérément non fixée dans cette
  synthèse (section 5).

---

## 15. Verdict final

**`RESEARCH PHASE CLOSED`** pour la question centrale ayant motivé
l'ensemble de la campagne E1-E16 : *existe-t-il, avec les données
actuellement disponibles, un edge démontrable du modèle sur le marché
d'ouverture, exploitable via le désaccord, le mouvement, ou la dispersion
multi-bookmaker ?* Cette question a été posée sous **six angles
indépendants** (1X2 direct E1, désaccord 1X2 diagnostic post-E1, désaccord
O/U E5/E10, intersection fiabilité×prix E12, dispersion/arbitrage
multi-bookmaker E9/E13, mouvement ouverture→clôture E16) et a reçu, à
chaque fois, une réponse négative ou contradictoire, jamais positive.
Répéter cette question sans nouvelles données (nouveau fournisseur, nouvelle
ligne de marché, nouvel horizon temporel) exposerait le projet à un risque
de data snooping pur, explicitement proscrit par le protocole.

Un seul fil scientifique reste ouvert, **non bloquant** pour
l'implémentation du moteur minimal viable (section 13), que la
documentation E15 elle-même identifie comme la suite naturelle et bornée
si la recherche devait reprendre : **une mesure véritablement indépendante
de la dispersion du niveau des équipes en Premier League** (classement
final, différentiel de buts par équipe, ou une mesure externe équivalente
— jamais une mesure dérivée du modèle lui-même) pour déterminer si
l'absence de discrimination confirmée en E4/E11/E15 a une cause réelle ou
reste un fait structurel inexpliqué du championnat. Cette direction unique
est explicitement **optionnelle** — le moteur minimal viable fonctionne
dès aujourd'hui en traitant la Premier League par gate d'abstention,
sans attendre la résolution de ce puzzle.

**Prochaine étape** : conformément à l'instruction reçue, ce document
constitue l'arrêt de la phase de recherche E1-E16. Aucune nouvelle
expérience, aucun nouveau modèle, aucune nouvelle donnée, aucune
modification du moteur de production, et aucun code de moteur final ne
sont entrepris à ce stade. Une instruction séparée est requise avant de
passer à l'implémentation.
