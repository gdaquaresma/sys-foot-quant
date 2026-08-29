# Research Framework — Étape 1.5

Ce document consolide les hypothèses extraites de quatre sources documentaires
(Epstein, *The Theory of Gambling and Statistical Logic* ; Miller & Davidow,
*The Logic of Sports Betting* ; Appelbaum, *The Everything Guide to Sports
Betting* ; Miech, *Sports Betting for Winners* ; Dolan, *The Complete Guide
to Sports Betting* ; plus une synthèse croisée + audit critique déjà réalisé
sur les quatre premiers ouvrages) et les évalue selon un protocole unique en
8 points, dans le seul but de décider ce qui mérite d'être implémenté à
l'étape 2 (Poisson + calibration + benchmarks).

**Aucun code n'a été modifié pour produire ce document.**

**Historique des révisions**

- Version initiale (étape 1.5) : classification des hypothèses A à H à
  partir des 4 livres de vulgarisation + de la synthèse croisée et de son
  audit critique.
- Révision post-audit primaire : un audit indépendant a relu les 5 sources
  primaires *intégrales* (Epstein, Miller & Davidow, Appelbaum, Dolan,
  Miech — pas seulement la synthèse) et vérifié chaque hypothèse contre le
  texte original. Résultat consigné dans `docs/research_framework_audit.md`.
  **Aucune classification n'a été modifiée par cet audit** — il confirme le
  classement existant et ajoute des nuances méthodologiques et des
  précisions de preuve, intégrées ci-dessous aux endroits concernés (§B1,
  §B3, §E, §G1, §G2). Se référer à `research_framework_audit.md` pour le
  détail complet de la vérification section par section.

---

## 0. Avertissement épistémique sur le corpus

Avant de classer quoi que ce soit, trois réserves s'imposent — elles
s'appliquent à *toutes* les hypothèses ci-dessous, pas seulement à celles
classées "spéculative" :

1. **Ce sont des livres de vulgarisation professionnelle, pas des articles
   évalués par les pairs.** Epstein est le seul à démontrer mathématiquement
   ses affirmations ; les trois autres s'appuient sur l'expérience et des
   échantillons illustratifs souvent petits (le "Roxy Special" cite 162
   matchs, le RLM en NFL cite 200 situations). Un échantillon de cet ordre
   ne suffit pas à valider une hypothèse — il suffit tout juste à justifier
   qu'on la teste.
2. **La transplantation inter-sports n'est pas une preuve.** Une bonne
   partie du corpus concerne NFL, NBA, MLB, hockey ou le casino pur.
   Chaque fois qu'une hypothèse est "adaptée au football" dans le texte
   source, c'est une extrapolation non testée par l'auteur lui-même — elle
   doit être traitée comme une hypothèse *nouvelle*, pas comme un résultat
   importé.
3. **Le document de synthèse croisée et son "audit critique" sont eux-mêmes
   une couche d'interprétation**, pas une source primaire. Sa classification
   A/B/C/D est réutilisée ici comme un *input* parmi d'autres (elle est
   souvent juste — notamment sur EOR et sur la prudence envers les facteurs
   situationnels — mais elle est reprise ici avec sa propre grille, pas
   copiée telle quelle).

Le corpus fournit un excellent inventaire de *pistes* à tester. Il n'est la
preuve d'aucun edge sur le football.

---

## 1. Grille de classification utilisée

| Classe | Critère |
|---|---|
| **Fondation** | Mécanisme mathématiquement rigoureux et déjà démontré (pas seulement affirmé) ; variables observables avec les données déjà prévues à l'étape 2 ; testable immédiatement avec l'infrastructure existante ; risque d'overfitting faible par construction (peu ou pas de paramètre libre ajusté sur l'historique). |
| **Intéressante** | Mécanisme plausible et cohérent avec la théorie, mais preuve empirique absente ou insuffisante dans les sources, ou transplantée d'un autre sport/marché. Nécessite un protocole hors-échantillon dédié avant adoption — c'est un candidat de test, pas un candidat d'implémentation directe. |
| **Spéculative** | Mécanisme faible ou anecdotique dans les sources (poignée d'exemples, pas de test statistique formel), dépend de données que nous n'avons pas encore (tickets %, dollars %, xG temps réel), ou risque de data snooping élevé de par sa nature (seuils ad hoc, filtres multiples). |
| **À rejeter** | Mécanisme mathématiquement invalide dans son application au football (analogie fausse), contredit par la théorie de l'efficience de marché sans mécanisme d'exploitation identifié, ou relève du biais cognitif que le corpus lui-même dénonce (martingale, gambler's fallacy). |

---

## A. FOOTBALL MODEL — Candidats directs pour l'étape 2

### A1. Pondération temporelle de la forme récente (time-decay) sur λ et μ

- **Mécanisme supposé** : la force offensive/défensive d'une équipe évolue
  dans la saison ; pondérer les matchs récents plus fortement que les
  matchs anciens dans le calcul de λ (buts attendus domicile) et μ (buts
  attendus extérieur) capture mieux l'état actuel de l'équipe qu'une
  moyenne plate sur toute la saison.
- **Convergence des sources** : hypothèse citée indépendamment par Dolan
  (H-002 : fenêtre glissante de 6 matchs bat la saison complète sur
  Over/Under), par la synthèse croisée (adaptation du modèle "Grinder" de
  Ron Boyles, 5 derniers matchs), et implicitement par Epstein (mise à jour
  bayésienne de la force plutôt qu'attente de fin de saison). Trois sources
  indépendantes convergent sur le même mécanisme — c'est le signal de
  convergence le plus fort de tout le corpus.
- **Variables nécessaires** : historique de buts marqués/encaissés par
  équipe et par match (déjà dans notre schéma `match_results`), une
  fonction de décroissance (fenêtre glissante à N matchs, ou pondération
  exponentielle avec demi-vie à calibrer).
- **Testable historiquement** : oui, directement avec les données déjà
  prévues (`match_results` horodaté). Aucune donnée supplémentaire requise.
- **Hypothèse nulle (H0)** : la pondération temporelle n'améliore pas le
  log loss / Brier score hors échantillon par rapport à une moyenne plate
  sur la saison (ou sur une fenêtre fixe de référence, ex. 38 matchs).
- **Protocole hors-échantillon** : walk-forward strict (entraînement sur
  matchs `knowledge_time < T`, test sur les matchs suivants) ; comparer
  plusieurs largeurs de fenêtre (5, 10, 15, 20 matchs) et un lissage
  exponentiel, contre la moyenne pleine saison, sur au moins 2 saisons
  complètes et plusieurs championnats (pas un seul, pour éviter l'overfitting
  de championnat).
- **Benchmark** : Poisson simple sans pondération temporelle (déjà prévu
  comme configuration de base à l'étape 2).
- **Risques d'overfitting** : la largeur de fenêtre est un paramètre libre
  — ne pas la choisir en maximisant le score sur l'échantillon de test.
  Fixer la grille de valeurs *a priori* (protocole écrit avant de lancer le
  test) et ne conserver que la fenêtre validée hors échantillon sur
  plusieurs saisons/championnats disjoints.
- **Classification : Fondation.** Faible complexité, mécanisme
  statistiquement bien compris (moyenne mobile / lissage exponentiel),
  données déjà disponibles, convergence multi-sources. C'est un candidat
  naturel pour être testé *dans* le Poisson de base de l'étape 2 (Poisson
  avec vs sans décroissance temporelle, comme deux configurations
  benchmarkées l'une contre l'autre), pas une extension séparée.

- **Résultat empirique (étape 2, puis re-test étape 5) :**
  - Version initiale testée à l'étape 2 (`poisson_A1_decay`, décroissance
    exponentielle calendaire, demi-vie 45 jours gelée a priori) :
    significativement DOMINÉE par `poisson_simple` sur les deux scénarios
    synthétiques (constant et dérive) — voir
    `scripts/run_stage2_walk_forward.py` et
    `scripts/run_stage5_baseline_benchmark.py`.
  - Ce résultat a été jugé peu concluant sur le mécanisme lui-même : une
    décroissance calendaire à demi-vie unique ne traduit pas fidèlement
    l'intuition football ("une équipe change — joueurs, entraîneur,
    système — donc un résultat ancien devient vite peu représentatif,
    indépendamment du nombre de jours calendaires écoulés"). Un
    protocole de re-test a donc été explicitement validé et exécuté à
    l'étape 5 avec une définition football-réaliste de la forme
    récente : fenêtre glissante à nombre FIXE de matchs (poids plat
    dans la fenêtre, nul au-delà), et non plus une décroissance en
    jours calendaires (`football_model/recent_form.py`,
    `scripts/run_stage5_a1_recency.py`).
  - **Verdict du re-test (données synthétiques, walk-forward à trois
    voies rodage/validation/test, sélection de fenêtre confinée
    strictement à la validation) :**
    - **Q1 — la forme récente (fenêtre courte seule) apporte-t-elle une
      information supplémentaire au Poisson simple ? REJETÉ.** Même la
      meilleure fenêtre retenue sur validation (7 matchs, sur les deux
      scénarios) reste significativement PIRE que `poisson_simple` sur
      le test, y compris dans le scénario à dérive réelle où un
      bénéfice était pourtant plausible a priori — le bruit introduit
      par une fenêtre courte l'emporte sur le signal de forme récente
      captée.
    - **Q2 — quelle fenêtre fonctionne le mieux (informationnel,
      sélection validation uniquement) : 7 matchs**, sur les deux
      scénarios (jamais la fenêtre de référence 5, ni 3).
    - **Q3 — une faible mémoire de l'historique long (shrinkage
      bayésien empirique, `prior_k=2.0` fixé a priori) améliore-t-elle
      la fenêtre 5 seule ? VALIDÉ** (significatif sur les deux
      scénarios) — **mais ce constat ne doit pas être lu comme "la
      forme récente + mémoire bat le Poisson simple"** : comparée
      directement à `poisson_simple`, `forme_5_memoire` reste
      significativement PIRE sur les deux scénarios. Le shrinkage
      réduit le bruit de la fenêtre courte sans le supprimer.
    - **Q4 — la dernière confrontation directe (poids fixe 0.10)
      apporte-t-elle quelque chose au Poisson simple ? INDÉTERMINÉ**
      (IC95% incluant 0 sur les deux scénarios) — aucun signal
      détecté, ni positif ni négatif.
  - **Conclusion consolidée A1 : REJETÉ — infériorité significative
    confirmée** (force du verdict : preuve statistique directe contre le
    candidat, pas une simple absence de preuve — voir section "Force des
    conclusions / limites de puissance" en fin de document) pour toute
    variante testée de "forme récente" comme amélioration du Poisson simple, sur
    données synthétiques — que ce soit la décroissance calendaire
    (étape 2) ou la fenêtre glissante à nombre fixe de matchs, avec ou
    sans mémoire longue (étape 5). Cette conclusion remplace le statut
    précédent "INDÉTERMINÉ" affiché dans `docs/architecture.md` (qui ne
    reflétait qu'une non-signification, jamais un test explicite de la
    définition football-réaliste demandée). `poisson_simple` reste la
    baseline officielle, aucune configuration ci-dessus n'est promue
    automatiquement. Aucune combinaison n'a été testée (aucune brique
    autre que Q3 n'a individuellement validé, et Q3 ne bat pas la
    baseline en absolu) — voir `scripts/run_stage5_a1_recency.py` pour
    le détail complet et les chiffres.

### A2. Home Field Advantage (HFA) dynamique plutôt que constante globale

- **Mécanisme supposé** : l'avantage du terrain n'est pas une constante
  unique pour toute une ligue, mais varie par équipe (taille du terrain,
  soutien du public, distance parcourue par l'adversaire) et potentiellement
  dans le temps.
- **Variables nécessaires** : historique différentiel buts domicile vs
  extérieur par équipe (`match_results`), taille d'échantillon suffisante
  par équipe (plusieurs saisons) pour estimer un HFA spécifique sans trop
  de bruit.
- **Testable historiquement** : oui, avec les données déjà prévues.
- **H0** : un HFA spécifique par équipe n'améliore pas le log loss/Brier
  hors échantillon par rapport à un HFA unique estimé sur l'ensemble de la
  ligue.
- **Protocole hors-échantillon** : walk-forward, avec un HFA par équipe
  ré-estimé uniquement sur les données antérieures à `T` (jamais sur la
  saison en cours en cumulatif complet). Comparer HFA global vs HFA
  spécifique vs HFA à shrinkage bayésien (moyenne pondérée entre HFA
  spécifique et HFA global, pondérée par la taille d'échantillon de
  l'équipe) — cette troisième option est probablement la plus robuste et
  évite le surajustement sur les équipes à faible historique.
- **Benchmark** : Poisson avec HFA global unique (déjà la configuration de
  base envisagée).
- **Risques d'overfitting** : élevé si HFA est estimé équipe par équipe
  sans shrinkage — une équipe avec 10 matchs à domicile peut avoir un HFA
  apparent extrême par pur bruit d'échantillonnage. Le shrinkage bayésien
  n'est pas optionnel ici, c'est une condition de validité du test.
- **Classification : Fondation** (avec shrinkage) / **Intéressante** (HFA
  brut par équipe sans shrinkage — à ne pas tester tel quel).

- **Résultat empirique — RE-TEST SUR DONNÉES RÉELLES (étape 5, suite à
  B1/B3/B3.2/C7)** : A2 (`PoissonModel(use_team_hfa=True)`) avait été
  testé sur données SYNTHÉTIQUES à l'étape 2 (`run_stage2_walk_forward.py`,
  config `poisson_A2_hfa`) mais jamais confronté à `poisson_simple` sur
  données réelles — tous les scripts réels précédents (B1/B3/B3.2/C7)
  désactivaient explicitement le HFA par équipe des deux côtés pour
  isoler leur propre question. Ce re-test
  (`scripts/run_stage5_a2_hfa_real.py`) comble ce manque, avec
  `PoissonModel` strictement inchangé et `hfa_shrinkage_k=10.0` réutilisé
  tel quel (figé à l'étape 2, jamais réajusté).
  - **Protocole** : mêmes données Understat que B1/B3/B3.2/C7 (3
    championnats × 2 saisons 2024/25+2025/26), rodage 40% / validation
    30% / test 30% par championnat et par saison (saisons regroupées pour
    le résultat par championnat, détail par saison conservé pour
    vérifier la stabilité temporelle).
  - **Résultats (test regroupé par championnat, diff = `Brier_A2 -
    Brier_poisson_simple`)** :
    - Ligue 1 : diff moyenne -0.0006, IC95%=[-0.0094, +0.0079] (2024/25
      seul : +0.0040 ; 2025/26 seul : -0.0053) → indéterminé
    - Premier League : diff moyenne -0.0019, IC95%=[-0.0078, +0.0046]
      (2024/25 seul : -0.0015 ; 2025/26 seul : -0.0023) → indéterminé
    - Liga : diff moyenne +0.0022, IC95%=[-0.0065, +0.0110] (2024/25
      seul : -0.0076 ; 2025/26 seul : +0.0119) → indéterminé
  - **Verdict : REJETÉ — absence de preuve d'amélioration selon le
    protocole, pas réfutation.** Aucun des trois championnats n'atteint
    une amélioration significative de `poisson_simple`, mais aucun
    n'atteint non plus une infériorité significative : les trois IC95%
    incluent 0, conformément aux critères fixés avant calcul — 640
    matchs de test évalués au total. Le signe de la différence est
    instable d'une saison à l'autre pour Ligue 1 et Liga. Ce résultat ne
    doit pas être lu comme une preuve que le HFA par équipe n'a aucun
    effet réel : la puissance statistique des échantillons utilisés
    (voir section "Force des conclusions / limites de puissance" en fin
    de document) ne permet de trancher que pour des effets relativement
    marqués — un effet réel plus modeste reste possible et non exclu.
  - **Portée** : `poisson_simple` (HFA global unique) reste la baseline
    officielle, inchangée. `PoissonModel(use_team_hfa=True)` reste
    disponible dans le code (paramètre existant, pas un nouveau modèle),
    sans statut particulier ni promotion — aucune nouvelle recherche sur
    le HFA par équipe n'est prévue sans nouvelle décision explicite.

### A3. Modèle Power Rating (Dolan) comme variante d'Elo

- **Mécanisme supposé** : note numérique par équipe, ajustée du contexte
  (adversaire, domicile/extérieur, calendrier), donnant une marge de but
  attendue `Marginexp = (PR_A + HFA) − PR_B`.
- **Variables nécessaires** : historique des scores, différentiel de buts,
  force du calendrier (Strength of Schedule).
- **Testable historiquement** : oui.
- **H0** : un Power Rating de ce type ne prédit pas mieux les résultats
  (mesuré en Brier/log loss après conversion en probabilités 1X2) qu'un
  Elo standard déjà prévu comme benchmark.
- **Protocole hors-échantillon** : identique au protocole Elo déjà prévu
  dans l'architecture (comparaison de benchmarks). Pas de protocole
  nouveau à inventer.
- **Benchmark** : Elo (déjà dans notre liste de benchmarks obligatoires).
- **Risques d'overfitting** : le facteur HFA et les poids du Strength of
  Schedule sont des paramètres libres — mêmes précautions que A2.
- **Classification : Fondation, mais redondante.** C'est structurellement
  une variante d'Elo (notation continue + ajustement contextuel). Ne
  mérite pas une implémentation séparée : à traiter comme une variante
  paramétrique de l'Elo déjà prévu dans nos benchmarks, pas comme un
  nouveau modèle.

### A4. Test d'adéquation du Chi-Deux sur la distribution de scores

- **Mécanisme supposé** : vérifier si la distribution des scores réels
  observés est compatible avec la distribution de Poisson estimée par le
  modèle (Epstein, méthode générale du chapitre 2, appliquée aux scores de
  football dans la section méthodologie).
- **Variables nécessaires** : distribution empirique des scores exacts sur
  un large échantillon (≥1000 matchs, comme suggéré par la source),
  distribution théorique issue du modèle Poisson ajusté.
- **Testable historiquement** : oui.
- **H0** : la distribution empirique des scores n'est pas significativement
  différente de la distribution de Poisson estimée (test de non-rejet).
- **Protocole hors-échantillon** : ce n'est pas exactement un test hors
  échantillon au sens prédictif — c'est un test de qualité d'ajustement
  (goodness-of-fit) sur l'échantillon d'entraînement lui-même. À faire en
  complément, pas en remplacement, du walk-forward sur Brier/log loss.
  Utile en diagnostic : si le Chi-Deux rejette H0, cela indique un
  problème structurel du modèle (ex. sous-estimation des scores 0-0/1-1,
  ce qui est précisément le problème que Dixon-Coles corrige).
- **Benchmark** : n/a (test diagnostique, pas un modèle concurrent).
- **Risques d'overfitting** : aucun — c'est un outil de diagnostic, pas un
  paramètre ajusté sur les données.
- **Classification : Fondation.** Test de validation à intégrer au
  Calibration Engine de l'étape 2, en complément de Brier/log loss/reliability
  diagrams déjà prévus. Peu coûteux, informatif, aucun risque de data
  snooping puisqu'il ne sert pas à sélectionner un paramètre.

---

## B. FOOTBALL MODEL — Extensions expérimentales (déjà étape 5 dans l'architecture)

Ces hypothèses sont cohérentes avec l'architecture déjà validée qui les
place explicitement à l'étape 5 ("extensions expérimentales : xG,
Dixon-Coles, autres variables, doivent démontrer leur utilité hors
échantillon"). Le corpus ne donne aucune raison de les avancer à l'étape 2.
Elles sont documentées ici pour mémoire, avec leur protocole déjà défini,
afin de ne pas re-faire ce travail à l'étape 5.

### B1. Correction Dixon-Coles (interdépendance des scores faibles)

- **Mécanisme supposé** : le Poisson simple suppose l'indépendance
  statistique des buts des deux équipes ; en réalité les scores 0-0, 1-0,
  0-1, 1-1 sont sous/sur-représentés par rapport à ce que prédit un Poisson
  pur, car un but change la dynamique du match (l'équipe menée attaque
  davantage). Dixon-Coles introduit un paramètre de corrélation τ pour ces
  scores bas, plus un paramètre de dépréciation temporelle ξ.
- **Statut dans les sources** : absent des trois guides de paris sportifs du
  corpus (Dolan, Miech, Appelbaum — confirmé par lecture intégrale de leur
  texte primaire) ; absent également de Miller & Davidow. L'audit
  (`research_framework_audit.md`, §B) précise un point que la formulation
  "absent des quatre livres" masquait : Epstein, le cinquième auteur du
  corpus, ne traite d'aucun sport à score continu (football ou autre) — son
  livre couvre le Blackjack, les dés, les cartes et la théorie des jeux
  abstraite. Son silence sur Dixon-Coles n'a donc pas la même valeur
  probante que celui des quatre guides de paris sportifs : ce n'est pas un
  auteur qui aurait pu en parler et ne l'a pas fait, c'est un auteur dont le
  champ ne recouvre jamais ce sujet. La conclusion opérationnelle reste
  inchangée (Dixon-Coles est une importation académique externe, absente de
  toute théorie transmise par un auteur du corpus), mais elle repose sur le
  silence des quatre sources sportives, pas sur un "consensus des cinq
  sources" qui surpondérerait artificiellement le silence d'Epstein. Dolan
  ne le mentionne pas non plus explicitement, mais le recommande comme
  "module externe obligatoire" dans son cahier des charges (lui aussi une
  extrapolation de l'auteur du document de synthèse, pas de Dolan).
- **Variables nécessaires** : mêmes données que le Poisson simple
  (`match_results`), plus l'estimation des paramètres τ et ξ par maximum de
  vraisemblance sur les scores bas.
- **Testable historiquement** : oui.
- **H0** : la correction Dixon-Coles n'améliore pas le log loss/Brier
  hors échantillon par rapport au Poisson simple (éventuellement
  déjà amélioré par A1/A2).
- **Protocole hors-échantillon** : walk-forward, Poisson simple (+A1+A2)
  vs Poisson+Dixon-Coles, sur plusieurs championnats/saisons. Vérifier
  spécifiquement l'amélioration sur le sous-ensemble des scores bas (là où
  le mécanisme est censé agir), pas seulement le score agrégé — un modèle
  peut améliorer le score moyen sans réellement corriger le problème ciblé.
- **Benchmark** : Poisson simple (avec la meilleure configuration validée
  en A1/A2).
- **Risques d'overfitting** : deux paramètres libres supplémentaires
  (τ, ξ) — risque modéré mais réel si estimés sur un échantillon trop
  petit ou par championnat sans validation croisée.
- **Classification : Intéressante.** Reste à l'étape 5 comme prévu par
  l'architecture. Aucun élément du corpus ne justifie de l'avancer à
  l'étape 2 — au contraire, l'audit lui-même le classe "B — à tester",
  jamais "fondation".

- **Résultat empirique — RE-TEST SUR DONNÉES RÉELLES (étape 5, suite à
  B3/B3.2/C7)** : `DixonColesModel` avait été VALIDÉ sur données
  SYNTHÉTIQUES dédiées uniquement (`scripts/run_stage5_b1_dixon_coles.py`,
  ρ=-0.13 injecté artificiellement) — `docs/architecture.md` documentait
  explicitement que cela ne constituait pas une preuve sur données
  réelles. Ce re-test (`scripts/run_stage5_b1_dixon_coles_real.py`)
  utilise les mêmes données Understat que B3/B3.2/C7 (3 championnats × 2
  saisons 2024/25 + 2025/26, buts réels uniquement, aucun xG), avec
  `DixonColesModel` strictement inchangé (ρ ré-estimé par maximum de
  vraisemblance à chaque fit walk-forward, mécanisme déjà validé, pas une
  nouvelle procédure) et `poisson_simple` comme référence.
  - **Protocole** : rodage 40% / validation 30% / test 30%, par
    championnat et par saison (deux saisons traitées indépendamment puis
    jeux de test regroupés par championnat), `use_team_hfa=False` des
    deux côtés (isolation stricte de la question testée, même choix que
    le script synthétique).
  - **Résultats (test, diff = `dixon_coles - poisson_simple`, Brier)** :
    - Ligue 1 : diff moyenne +0.0029, IC95%=[+0.0004, +0.0053] →
      `poisson_simple` significativement meilleur
    - Premier League : diff moyenne -0.0009, IC95%=[-0.0044, +0.0028] →
      indéterminé
    - Liga : diff moyenne -0.0000, IC95%=[-0.0012, +0.0012] → indéterminé
  - **Sous-ensemble bas-score (0-0/1-0/0-1/1-1)**, ciblé par le mécanisme
    tau(x,y;ρ) : aucun signal cohérent avec une amélioration (Ligue 1
    diff +0.0033, Premier League +0.0014, Liga -0.0003 — jamais
    significatif, jamais cohéremment négatif).
  - **Verdict : REJETÉ — avec une nuance importante sur la force de la
    preuve.** Seule la **Ligue 1** porte une preuve statistique directe
    contre `dixon_coles` (IC95% entièrement positif, infériorité
    significative confirmée) ; Premier League et Liga sont chacune une
    simple **absence de preuve d'amélioration** (IC95% incluant 0), pas
    une infériorité démontrée. Le verdict agrégé REJETÉ reflète donc
    1 championnat sur 3 avec une infériorité significative, complété par
    2 championnats sans signal dans un sens ou l'autre — conformément aux
    critères d'agrégation fixés avant calcul, mais à ne pas lire comme
    "trois preuves contre `dixon_coles`". `poisson_simple` reste la
    baseline officielle, inchangée. Voir aussi la section "Force des
    conclusions / limites de puissance" en fin de document : ce résultat
    isolé de Ligue 1 est le seul de toute la campagne réelle à atteindre
    la significativité individuelle, ce qui invite à une prudence
    supplémentaire compte tenu du nombre de tests menés sur le même pool
    de données (aucune correction pour tests multiples n'a été appliquée
    au niveau du programme).
  - **Portée** : ce résultat REJETÉ, obtenu sur données réelles, prime sur
    le résultat VALIDÉ obtenu précédemment sur données synthétiques
    dédiées — le mécanisme de corrélation basse-score que Dixon-Coles
    corrige, bien que réel dans le générateur synthétique conçu pour
    l'exhiber, ne s'est pas manifesté de façon exploitable dans les
    résultats réels actuellement disponibles. `DixonColesModel` reste dans
    le code à titre expérimental et de référence (comme `XGModel`), sans
    promotion, aucune nouvelle recherche de correction basse-score n'est
    prévue sans nouvelle décision explicite.

### B2. Mise à jour bayésienne dynamique de la force des équipes

- **Mécanisme supposé** : au lieu d'estimer la force d'attaque/défense sur
  une fenêtre fixe (A1), utiliser une mise à jour bayésienne séquentielle
  après chaque match (prior → observation → posterior), qui devient le
  nouveau prior pour le match suivant.
- **Statut dans les sources** : le mécanisme général (théorème de Bayes)
  est rigoureusement démontré par Epstein, mais son application à la mise
  à jour de force d'équipe de football n'est détaillée dans aucune source
  — c'est une construction à faire nous-mêmes, pas une méthode "reprise"
  d'un livre.
- **Variables nécessaires** : identiques à A1 (historique de buts),
  plus le choix d'une fonction de vraisemblance et d'un prior initial
  (probablement informé par la force moyenne de la ligue ou d'une saison
  précédente).
- **Testable historiquement** : oui.
- **H0** : la mise à jour bayésienne séquentielle n'améliore pas le log
  loss/Brier hors échantillon par rapport à la pondération temporelle par
  fenêtre glissante (A1).
- **Protocole hors-échantillon** : walk-forward, comparaison directe A1
  (fenêtre glissante) vs B2 (bayésien séquentiel) — ce sont deux solutions
  concurrentes au même problème (captation de la forme récente), pas deux
  briques cumulatives. Le protocole doit les traiter comme des hypothèses
  mutuellement exclusives à départager, pas comme des additions.
- **Benchmark** : A1 (fenêtre glissante/décroissance exponentielle),
  puisque c'est la solution la plus simple au même problème.
- **Risques d'overfitting** : le choix du prior et de la fonction de
  vraisemblance est un espace de conception large — fort risque de
  data snooping si on ajuste ces choix en observant déjà les résultats du
  test. Spécifier la forme du modèle bayésien *avant* de voir les
  résultats hors échantillon.
- **Classification : Intéressante**, à traiter comme alternative à A1
  plutôt que comme extension supplémentaire. Reste étape 5.

- **Résultat empirique — RE-TEST SUR DONNÉES RÉELLES, COMPARAISON DIRECTE
  À `poisson_simple` (étape 5, suite à B1/A2/B3/B3.2/C7)** : B2
  (`BayesianSequentialModel`) n'avait été comparé qu'à A1 sur données
  SYNTHÉTIQUES (`scripts/run_stage5_b2_walk_forward.py`, B2 meilleur qu'A1
  mais A1 a depuis été définitivement REJETÉ contre `poisson_simple`,
  toutes variantes confondues) — jamais confronté directement à
  `poisson_simple`, ni sur synthétique ni sur réel. Ce re-test
  (`scripts/run_stage5_b2_bayesian_real.py`) comble ce manque, avec
  `BayesianSequentialModel` strictement inchangé et son design
  intégralement figé (`prior_strength=DEFAULT_PRIOR_STRENGTH=10.0`, même
  conjugaison Gamma-Poisson, même règle de mise à jour séquentielle —
  vérifié identique au code utilisé pour le test synthétique avant
  exécution).
  - **Protocole** : mêmes données Understat que B1/A2/B3/B3.2/C7 (3
    championnats × 2 saisons 2024/25+2025/26), rodage 40% / validation
    30% / test 30% par championnat et par saison (saisons regroupées pour
    le résultat par championnat, détail par saison conservé pour la
    stabilité temporelle). Test évalué une seule fois.
  - **Résultats (test regroupé par championnat, diff = `Brier_B2 -
    Brier_poisson_simple`)** :
    - Ligue 1 : diff moyenne -0.0114, IC95%=[-0.0232, +0.0005] (2024/25
      seul : -0.0050 ; 2025/26 seul : -0.0179) → indéterminé (proche de
      la significativité mais IC95% incluant 0)
    - Premier League : diff moyenne -0.0037, IC95%=[-0.0119, +0.0053]
      (2024/25 seul : -0.0004 ; 2025/26 seul : -0.0070) → indéterminé
    - Liga : diff moyenne -0.0011, IC95%=[-0.0115, +0.0091] (2024/25
      seul : +0.0094 ; 2025/26 seul : -0.0115) → indéterminé
  - **Verdict : REJETÉ — absence de preuve d'amélioration, avec une
    tendance favorable mais non significative.** Aucun des trois
    championnats n'atteint une amélioration significative de
    `poisson_simple` (tous les IC95% incluent 0), conformément aux
    critères fixés avant calcul — 640 matchs de test évalués au total.
    Le signe de la différence favorise systématiquement B2 (négatif) sur
    5 des 6 couples championnat/saison, et la Ligue 1 regroupée
    (IC95%=[-0.0232, +0.0005]) frôle le seuil de significativité sans
    l'atteindre. Ce résultat est le plus proche de la significativité de
    toute la campagne réelle : il ne doit pas être interprété comme une
    preuve d'absence d'effet, mais comme une hypothèse **non démontrée à
    la puissance actuelle** — le candidat le plus susceptible de changer
    de statut si une nouvelle saison de données réelles devenait
    disponible (voir section "Force des conclusions / limites de
    puissance" en fin de document).
  - **Portée** : `poisson_simple` reste la baseline officielle, inchangée.
    `BayesianSequentialModel` reste dans le code à titre expérimental
    (comme `XGModel`/`DixonColesModel`), sans promotion. Aucune nouvelle
    recherche sur la mise à jour bayésienne séquentielle (nouveau prior,
    nouvelle vraisemblance, nouvelle règle de mise à jour) n'est prévue
    sans nouvelle décision explicite.

### B3. Intégration du xG (Expected Goals)

- **Mécanisme supposé** : utiliser le xG plutôt que (ou en complément de)
  buts réels marqués/encaissés pour estimer λ et μ, sur l'argument que le
  xG élimine une partie de la variance/chance du score brut et reflète
  mieux la performance sous-jacente.
- **Statut dans les sources** : absent des quatre livres (confirmé
  explicitement par l'audit du document de synthèse : "totalement absent...
  il est intellectuellement malhonnête de l'attribuer aux théories des
  livres"), confirmation vérifiée par lecture intégrale des textes primaires
  eux-mêmes (aucune des cinq sources ne mentionne le xG). C'est une pure
  importation de la littérature moderne, non testée par aucune des sources
  fournies. Comme pour B1 (voir remarque ci-dessus), le silence d'Epstein
  spécifiquement ne doit pas être compté comme un cinquième témoignage
  indépendant de même poids que celui des quatre guides de paris sportifs :
  son livre ne traite d'aucun sport à score continu, donc il ne pouvait de
  toute façon pas mentionner le xG, qu'il en ait du mérite ou non pour le
  football.
- **Variables nécessaires** : source de données xG externe (type Opta/FBref
  ou équivalent), non prévue dans notre Data Engine actuel — c'est un
  connecteur de données entièrement nouveau à construire.
- **Testable historiquement** : oui, mais seulement une fois la source de
  données xG effectivement intégrée dans le Data Engine avec un
  `knowledge_time` correctement défini (le xG post-match est disponible
  avec un délai — attention à ne pas le traiter comme disponible au coup
  d'envoi).
- **H0** : remplacer les buts réels par le xG dans l'estimation de λ/μ
  n'améliore pas le log loss/Brier hors échantillon par rapport aux buts
  réels (éventuellement pondérés temporellement comme en A1).
- **Protocole hors-échantillon** : walk-forward, Poisson(buts réels,
  meilleure config A1/A2) vs Poisson(xG, même config). Tester aussi une
  version hybride (mélange buts réels / xG).
- **Benchmark** : Poisson sur buts réels, meilleure configuration validée
  à l'étape 2.
- **Risques d'overfitting** : modéré — le xG est lui-même un modèle
  (donc une source d'erreur supplémentaire, pas une vérité terrain), et le
  choix du fournisseur de xG influence les résultats (deux fournisseurs
  peuvent diverger significativement sur le même match).
- **Classification : Intéressante.** Nécessite d'abord un travail de Data
  Engine (nouveau connecteur, nouveau `knowledge_time`) avant même d'être
  testable — ce n'est pas prêt pour l'étape 2 pour une raison
  d'infrastructure, indépendamment de son mérite statistique. Reste
  étape 5, et conditionne l'ajout d'une source de données qui n'existe pas
  encore dans notre schéma.

- **Résultat empirique (étape 5, données réelles Understat) :**
  - **Source des données** : Understat (gratuit, non officiel), trois
    championnats 2025/26 complets (Ligue 1 306 matchs, Premier League 380,
    Liga 380 — 1066 matchs), récupérés via le navigateur de l'utilisateur
    et vérifiés intacts (aucun doublon de `match_id`, aucun score/xG
    manquant, nombre de matchs et d'équipes conforme à l'attendu pour
    chaque championnat) — voir `research/xg_feasibility/runs/` et le
    contrôle d'intégrité exécuté par `scripts/run_stage5_b3_xg_walkforward.py`.
  - **Modèle testé** : `XGModel` (`football_model/xg_model.py`), extension
    isolée de la même famille que `DixonColesModel`/`RecentFormModel` —
    formulation mathématique strictement identique à `poisson_simple`
    (pas de HFA par équipe, pas de shrinkage, aucun hyperparamètre libre),
    seule la source des "buts" utilisée pour estimer attaque/défense
    change (xG historique au lieu des buts réels).
  - **Point-in-time** : deux flux de connaissance indépendants par match
    (`backtesting_engine/real_data_walk_forward.py`) — score réel connu à
    kickoff+2h (convention déjà utilisée pour le générateur synthétique),
    xG connu à kickoff+48h. **Ce délai de 48h est une hypothèse
    conservatrice documentée, pas un fait vérifié** : Understat ne publie
    aucun horodatage officiel de publication par match. Ceci concerne la
    latence de publication d'une donnée déjà passée, pas une fuite
    d'information — l'invariant strict (aucun match à l'instant T ou après
    n'influence sa propre prédiction) est garanti par construction et
    vérifié par `tests/leakage/test_real_data_walk_forward_point_in_time.py`.
  - **Protocole** : scission chronologique à trois voies par championnat
    (rodage 40% / validation 30% / test 30%) ; `XGModel` n'ayant aucun
    hyperparamètre à sélectionner, la validation ne sert que de premier
    regard informatif — seul le test hors échantillon détermine le
    verdict. Métrique : Brier score, bootstrap apparié, IC95%, présenté
    comme `xg_model - poisson_simple` (négatif = xG meilleur).
  - **Résultats (test, IC95% de la différence de Brier)** :
    - Ligue 1 : diff moyenne -0.0177, IC95%=[-0.0429, +0.0071] → indéterminé
    - Premier League : diff moyenne -0.0103, IC95%=[-0.0344, +0.0132] → indéterminé
    - Liga : diff moyenne +0.0004, IC95%=[-0.0291, +0.0284] → indéterminé
  - **Verdict : INDÉTERMINÉ**, sur les trois championnats et en agrégé.
    Le signe de la différence est cohérent (xG légèrement meilleur ou
    neutre, jamais significativement pire) mais aucun des trois
    championnats ne montre une amélioration statistiquement significative
    hors échantillon. `poisson_simple` reste la baseline officielle,
    aucune promotion automatique. **Ce test est notamment sous-puissant**
    pour les tailles d'effet réellement observées (n≈92-114 matchs de
    test par championnat sur une seule saison, écart-type par match
    élevé pour cette paire de modèles) : un effet réel de l'ordre de
    0.01-0.02 avait une chance sérieuse de rester invisible même s'il
    existait — voir section "Force des conclusions / limites de
    puissance" en fin de document. INDÉTERMINÉ signifie ici données
    insuffisantes pour trancher, pas absence d'effet démontrée.
  - **Limite explicite** : ce résultat est une validation du **mécanisme**
    sur les données historiques Understat actuellement disponibles — il ne
    constitue PAS une preuve de stabilité des valeurs xG dans le temps
    (aucune mesure empirique de révision rétroactive n'a encore été faite,
    voir `research/xg_feasibility/` priorité 2). Aucune variante hybride
    xG/buts réels n'a été testée : `research_framework.md` ne fixait aucun
    poids a priori pour cette variante avant ce test.

- **Analyse de complémentarité (post-B3, même saison 2025/26,
  exploratoire — pas une hypothèse confirmatoire)** :
  `scripts/run_stage5_b3_xg_complementarity.py` a montré que `XGModel` et
  `poisson_simple` ont des erreurs fortement corrélées dans l'ensemble
  (~0.93) mais que `XGModel` bat significativement `poisson_simple`
  précisément sur le sous-ensemble des matchs où `poisson_simple` se
  trompe (agrégé sur 320 matchs : diff moyenne -0.0362,
  IC95%=[-0.0608, -0.0139], p=0.001). **Nature exacte de ce résultat** :
  c'est une **observation statistique établie sur un sous-groupe défini
  a posteriori** (le sous-groupe "poisson_simple se trompe" n'est
  identifiable qu'après avoir observé l'issue réelle des matchs, jamais
  avant le coup d'envoi) — la p-value et l'IC95% sont statistiquement
  corrects pour cette question rétrospective précise, mais ce résultat
  ne constitue **ni une règle utilisable en production, ni une preuve
  que mélanger xG et Poisson fonctionne** : aucune stratégie
  d'exploitation ex-ante (un moyen d'anticiper, avant le match, que
  `poisson_simple` va probablement se tromper) n'a été identifiée, ni
  même esquissée. Cette analyse a généré l'hypothèse d'un modèle hybride
  inconditionnel, testée séparément en B3.2 ci-dessous — elle n'a valeur
  que de générateur d'hypothèse, jamais de confirmation (mêmes données
  que le test B3 déjà consulté).

- **Résultat empirique B3.2 (hypothèse hybride, jeu de données VIERGE) :**
  - **Modèle testé** : `HybridXGModel` (`football_model/hybrid_xg_model.py`)
    — mélange linéaire de probabilités 1X2,
    `p_final = (1-w) * p_poisson + w * p_xg`, extension isolée n'important
    ni ne modifiant `PoissonModel`/`XGModel`.
  - **Isolation des données** : saison 2024/25 des trois mêmes championnats
    (1066 matchs neufs), entièrement disjointe de la saison 2025/26 utilisée
    par B3 et par l'analyse de complémentarité — aucun match commun, aucune
    réutilisation, vérifié avant exécution
    (`scripts/run_stage5_b3_2_hybrid_xg.py`).
  - **Protocole à deux étapes strictement séparées** : étape A (validation
    30% de la saison 2024/25) — sélection de `w` parmi {0.25, 0.50, 0.75}
    par Brier moyen le plus bas sur les trois championnats, **w=0.50
    retenu** ; étape B (test final 30%, `w` figé) — une seule exécution,
    jamais reconsidérée.
  - **Résultats (test final, IC95% de `hybrid - poisson_simple`)** :
    - Ligue 1 : diff moyenne +0.0039, IC95%=[-0.0129, +0.0200] → indéterminé
    - Premier League : diff moyenne -0.0063, IC95%=[-0.0157, +0.0029] → indéterminé
    - Liga : diff moyenne -0.0048, IC95%=[-0.0161, +0.0064] → indéterminé
  - **Verdict B3.2 : INDÉTERMINÉ**, sur les trois championnats et en
    agrégé (320 matchs de test). Direction incohérente entre championnats,
    aucun IC95% n'exclut 0. Comme pour B3, cette taille d'échantillon
    (n≈92-114 par championnat, une seule saison) offre une puissance
    limitée pour des effets de l'ordre de 0.01-0.02 — INDÉTERMINÉ signifie
    ici données insuffisantes/incohérentes pour trancher, pas la preuve
    que le mélange xG/Poisson n'apporte rien (voir section "Force des
    conclusions / limites de puissance" en fin de document).
  - **Même réserve point-in-time que B3** : le délai de connaissance xG
    (kickoff+48h) reste une hypothèse conservatrice documentée, pas une
    garantie historique auditée auprès d'Understat — distinct d'une fuite
    de données (invariant PIT garanti par construction et vérifié par
    tests dédiés).

- **CONCLUSION OFFICIELLE B3 / B3.2 (figée, ne pas rouvrir sans nouvelle
  donnée ou nouvelle décision explicite de l'utilisateur)** : l'analyse de
  complémentarité constitue une **observation statistique établie sur son
  échantillon conditionnel** (le xG bat significativement `poisson_simple`
  précisément quand ce dernier se trompe), **mais sans stratégie
  d'exploitation ex-ante identifiée** — ce n'est ni une méthode prête à
  être intégrée, ni une preuve que l'hybride xG fonctionne. Les données
  actuellement disponibles ne permettent pas de démontrer qu'un modèle xG
  seul (`XGModel`, B3) ou un mélange Poisson/xG (`HybridXGModel`, B3.2)
  améliore significativement la baseline Poisson hors échantillon ; ces
  deux résultats sont des hypothèses **non démontrées**, pas réfutées
  (voir section "Force des conclusions / limites de puissance").
  - `poisson_simple` reste le **modèle de référence / baseline
    officielle** — comportement inchangé, jamais remplacé par du xG.
  - `XGModel` est **conservé comme modèle complémentaire indépendant** —
    pas fusionné automatiquement avec `poisson_simple`.
  - `HybridXGModel` est **conservé dans le code pour traçabilité et
    reproductibilité de l'expérience B3.2**, statut strictement
    expérimental — non promu comme modèle officiel, aucune recherche
    d'un autre poids `w` n'est prévue sans nouvelle décision explicite.

### B3.3. Gate de désaccord Poisson/xG (exploitation ex-ante du signal de complémentarité)

- **Question testée** : le désaccord pré-match entre `poisson_simple` et
  `XGModel` (mesuré par la distance de variation totale, TVD, entre leurs
  deux distributions 1X2) constitue-t-il un signal ex-ante exploitable de
  la fiabilité relative des deux modèles, transformant le signal de
  complémentarité rétrospectif (B3) en amélioration réelle du Brier score ?
- **Mécanisme retenu après examen critique (spécification validée avant
  tout code)** : argument de régression vers la moyenne de la finition —
  un désaccord élevé signale que le profil de buts réels d'une équipe
  diverge de son profil de qualité d'occasions (xG), et le xG, moins
  sujet au bruit de conversion, serait alors le signal le plus fiable.
  Explicitement jugé **défendable mais non acquis** : le désaccord peut
  aussi n'être que du bruit d'estimation sans pouvoir prédictif — c'est
  précisément la question tranchée par ce test, pas une hypothèse validée
  a priori.
- **`GateDisagreementModel`** (`football_model/gate_disagreement_model.py`)
  : `w = TVD(p_poisson, p_xg)`, `p_final = (1-w)·p_poisson + w·p_xg`.
  **Zéro paramètre libre** — `w` est directement la mesure de désaccord,
  sans seuil ni coefficient à calibrer. Une seule mesure de désaccord
  retenue (TVD), décidée avant tout calcul (L2 et divergence de
  Jensen-Shannon examinées et écartées en spécification, aucun avantage
  démontré pour ce problème). N'importe ni ne modifie `PoissonModel` ni
  `XGModel`.
- **Protocole** : mêmes données que B1/A2/B2/B3/B3.2 (3 championnats × 2
  saisons 2024/25+2025/26), rodage 40% / calibration 30% (purement
  diagnostique — vérification de la distribution de TVD, aucun ajustement
  du gate) / test 30%, saisons regroupées par championnat au niveau du
  test, évalué une seule fois.
- **Diagnostic de calibration (informationnel, aucun ajustement)** : TVD
  moyenne observée 0.07-0.11 selon championnat/saison — désaccord
  généralement modeste, cohérent avec la forte corrélation d'erreur
  déjà mesurée en B3 (~0.93) : le gate reste proche de `poisson_simple`
  sur la majorité des matchs et ne s'approche significativement de `XGModel`
  que sur une minorité de matchs à fort désaccord.
- **Résultats (test regroupé par championnat, diff = `Brier_gate -
  Brier_poisson_simple`)** :
  - Ligue 1 : diff moyenne -0.0004, IC95%=[-0.0035, +0.0026] → indéterminé
  - Premier League : diff moyenne -0.0019, IC95%=[-0.0040, +0.0002] →
    indéterminé (proche du seuil, p=0.089)
  - Liga : diff moyenne -0.0023, IC95%=[-0.0050, +0.0003] → indéterminé
    (proche du seuil, p=0.080)
  - 640 matchs de test évalués au total.
- **Verdict : REJETÉ — absence de preuve d'amélioration, pas réfutation.**
  Aucun des trois championnats n'atteint une amélioration significative,
  mais le signe est négatif (favorable au gate) et cohérent sur les
  **trois** championnats — la direction la plus cohérente de toute la
  famille de tests xG (B3, B3.2, B3.3), sans jamais franchir le seuil de
  significativité. `poisson_simple` reste la baseline officielle,
  inchangée.
- **Réponse à la question posée** : **non, cette règle simple ne
  transforme pas, à ce stade et avec ce corpus, le signal xG rétrospectif
  en amélioration démontrée du Brier score.** Le résultat est directionnellement
  encourageant (cohérence des trois signes, deux championnats proches du
  seuil) mais ne constitue pas une preuve — voir section "Force des
  conclusions / limites de puissance". Conformément au protocole validé,
  aucune variante (autre mesure de désaccord, seuil, pondération) n'est
  testée à la suite de ce résultat.
- **Statut** : `GateDisagreementModel` conservé dans le code à titre
  expérimental, comme `HybridXGModel`, non promu. Aucun B3.4 n'est engagé.

---

## C. MARKET ENGINE — Hors scope étape 2, catalogué pour l'étape 3

### C1. Calcul du hold / marge et retrait de marge

- **Mécanisme** : convertir les cotes en probabilités de break-even,
  sommer sur toutes les issues d'un marché pour obtenir le hold.
- **Variables** : cotes par bookmaker et par issue.
- **Testable historiquement** : oui, trivialement, dès que les cotes sont
  dans le Data Engine.
- **H0** : n/a — c'est une définition mathématique, pas une hypothèse
  empirique. Rien à "tester", seulement à implémenter correctement.
- **Protocole** : validation unitaire de la formule (cf. ADR déjà prévu
  sur ce point), pas de protocole hors-échantillon nécessaire.
- **Benchmark** : n/a.
- **Risques d'overfitting** : aucun.
- **Classification : Fondation**, déjà prévue dans l'architecture
  (Market Engine, étape 3). Rappel important déjà acté à l'étape 1.5 par
  l'ADR 0003 : la cote de clôture ne peut servir de benchmark de décision
  pré-match que si elle était disponible au `decision_time` — le hold doit
  être calculé sur la cote *effectivement disponible* au moment évalué,
  jamais rétroactivement sur la clôture.

### C2. Marchés synthétiques à marge nulle (multi-bookmaker)

- **Mécanisme supposé** : en combinant la meilleure cote de chaque issue
  chez des bookmakers différents, on peut synthétiser un marché à hold
  quasi nul, réduisant voire annulant le désavantage structurel du hold.
- **Variables nécessaires** : cotes en temps réel d'au moins 3-5
  bookmakers pour les mêmes événements — **donnée non prévue dans notre
  Data Engine actuel** (nous n'avons prévu qu'une source de cotes par
  match jusqu'ici).
- **Testable historiquement** : conditionnellement — nécessite d'abord
  d'étendre le Data Engine à un scan multi-bookmaker.
- **H0** : le hold synthétique multi-bookmaker n'est pas significativement
  inférieur au hold du meilleur bookmaker unique sur l'échantillon.
- **Protocole hors-échantillon** : ce n'est pas vraiment une hypothèse
  prédictive à valider hors-échantillon — c'est une question d'ingénierie
  de données (disponibilité et fraîcheur des cotes multi-bookmaker) suivie
  d'un calcul déterministe.
- **Benchmark** : hold du bookmaker principal actuellement utilisé.
- **Risques d'overfitting** : aucun sur le calcul lui-même ; risque
  opérationnel réel signalé par les sources elles-mêmes (limitation de
  compte par les bookmakers qui détectent ce comportement).
- **Classification : Intéressante**, conditionnée à une extension du Data
  Engine (scan multi-bookmaker) non encore construite. Étape 3.

### C3. Reverse Line Movement (RLM) et disparité tickets vs dollars

- **Mécanisme supposé** : si la cote se déplace dans la direction opposée
  à la majorité des paris du public, cela signale un flux d'argent
  professionnel (sharp money) dans l'autre sens ; parier avec ce flux
  plutôt que contre lui serait profitable.
- **Convergence des sources** : citée indépendamment par Appelbaum, par
  Dolan (H-001), et reprise dans la synthèse (classée "B — à tester") —
  mais **contredite explicitement par Miller & Davidow**, qui affirment que
  les données de répartition tickets/dollars diffusées publiquement sont
  "souvent biaisées ou inutiles" et que les bookmakers retail ne bougent
  quasiment jamais leurs lignes sous le seul poids de l'argent public. Ce
  n'est donc pas une convergence de sources indépendantes mais une
  hypothèse activement disputée *à l'intérieur même du corpus*.
- **Variables nécessaires** : pourcentage de tickets et pourcentage de
  montant misé par issue — **donnée non disponible dans nos sources
  actuelles** (elle provient de plateformes spécifiques type action
  network / plateformes d'échange, à intégrer comme nouveau connecteur).
  De plus, tous les exemples chiffrés du corpus concernent NFL/NBA/MLB à
  deux issues (spread/moneyline) — aucune validation n'existe sur un
  marché à trois issues (1N2) comme le football.
- **Testable historiquement** : non, sans nouvelle source de données.
- **H0** : parier sur le côté soutenu par un RLM ne génère pas de ROI
  positif significatif sur le football, une fois la cote de clôture prise
  comme référence de qualité de décision (CLV).
- **Protocole hors-échantillon** : une fois la donnée disponible, tester
  sur un échantillon fixé *a priori* (ex. deux saisons complètes),
  mesurer le taux de couverture et le CLV moyen des sélections RLM contre
  un groupe de contrôle sans signal RLM, sur le marché 1X2 ET sur des
  marchés à deux issues (Draw No Bet) séparément, car la transposition du
  mécanisme à un marché à 3 issues n'est elle-même pas démontrée.
- **Benchmark** : ROI d'un flat betting sans signal RLM sur le même
  échantillon de matchs.
- **Risques d'overfitting** : élevé — le seuil de "pourcentage de tickets"
  et l'ampleur du mouvement de cote à retenir sont des paramètres libres
  ajustables après coup ; les exemples du corpus montrent déjà des seuils
  très différents d'un sport à l'autre (25% à 40% selon les cas), ce qui
  sent le seuil optimisé a posteriori plutôt qu'un principe stable.
- **Classification : Spéculative.** Contredite dans le corpus lui-même,
  donnée non disponible, mécanisme non démontré sur un marché à 3 issues.
  À ne pas prioriser pour l'étape 3 sans d'abord obtenir une source de
  données fiable, et à tester avec un scepticisme actif plutôt qu'une
  présomption de validité.

### C4. Contrarian betting (fade the public)

- **Mécanisme supposé** : le public amateur surévalue systématiquement
  favoris/domicile/overs ; parier contre le consensus public quand il
  dépasse un seuil (65-75% des tickets) serait profitable.
- **Variables nécessaires** : répartition des tickets par issue — même
  dépendance de donnée que C3, même absence de validation sur un marché à
  3 issues.
- **Testable historiquement** : non, sans nouvelle source de données.
- **H0** : parier contre un consensus public >65-70% ne génère pas de ROI
  positif significatif sur le football.
- **Protocole hors-échantillon** : identique à C3 en structure — fenêtre
  fixée a priori, comparaison à un groupe de contrôle, séparé par type de
  marché.
- **Benchmark** : flat betting sans filtre de consensus.
- **Risques d'overfitting** : le seuil de consensus (25%, 30%, 35%, 40%
  selon les exemples du livre) varie déjà d'un sport à l'autre dans le
  corpus — signe classique de seuil optimisé après coup plutôt que d'un
  principe stable et transférable.
- **Classification : Spéculative**, pour les mêmes raisons que C3
  (donnée absente, seuils instables entre sports, non testé sur marché à
  3 issues). Distincte de C3 mais partage son statut.

### C5. CLV comme métrique de validation (Closing Line Value)

- **Mécanisme** : mesurer la performance d'un modèle non sur le PnL brut à
  court terme, mais sur sa capacité à systématiquement obtenir un meilleur
  prix que la cote de clôture d'un bookmaker faiseur de marché — réduit le
  bruit du résultat binaire du match et permet une validation avec moins
  de paris.
- **Convergence des sources** : consensus explicite entre Miller &
  Davidow, Appelbaum et Dolan (les trois classent ceci comme validé/A).
- **Testable historiquement** : oui, une fois les cotes de clôture dans le
  Data Engine.
- **H0** : le CLV accumulé n'est pas corrélé au ROI réel à long terme.
- **Protocole** : régression CLV accumulé / ROI réel sur un large
  échantillon (le corpus suggère N≥1000 paris pour ce type de test) — mais
  ceci est un test *diagnostique de la métrique elle-même*, pas une
  hypothèse de trading. Notre usage du CLV est déjà cadré : ADR 0003
  explique précisément à quelles conditions la clôture peut servir de
  référence, et que c'est une métrique de qualité *a posteriori*, jamais
  un benchmark de décision pré-match.
- **Benchmark** : n/a — métrique de suivi, pas un modèle concurrent.
- **Risques d'overfitting** : aucun sur la métrique elle-même ; le risque
  serait de sur-interpréter un CLV positif sur un petit échantillon comme
  preuve d'edge (biais d'arrêt optionnel — voir section G).
- **Classification : Fondation.** Déjà intégrée dans nos principes de
  conception (ADR 0003). Rien de neuf à trancher ici — le corpus confirme
  simplement une décision déjà prise.

### C6. Marchés liés / conversion handicap ↔ moneyline (transposé : Asian Handicap ↔ 1X2)

- **Mécanisme supposé** : utiliser les taux de push historiques (fréquence
  exacte d'un écart de but donné) pour dériver une cote "juste" sur un
  marché dérivé à partir d'un marché plus liquide, et détecter les
  inéquations de prix entre les deux.
- **Variables nécessaires** : distribution historique des écarts de buts
  par ligue (calculable à partir de `match_results`, aucune donnée
  nouvelle requise), cotes sur au moins deux marchés lié (1X2 et handicap
  asiatique).
- **Testable historiquement** : oui, avec les données déjà prévues pour la
  partie "distribution des écarts", à condition d'avoir aussi les cotes de
  handicap asiatique dans le Data Engine (actuellement seul le marché 1X2
  est modélisé dans notre schéma de l'étape 1).
- **H0** : les cotes de handicap asiatique et de 1X2 d'un même bookmaker
  sont mutuellement cohérentes avec la distribution empirique des écarts
  de buts (pas d'inéquation exploitable).
- **Protocole hors-échantillon** : construire la distribution des écarts
  sur les données antérieures à `T` uniquement, dériver la cote "juste"
  implicite pour le marché dérivé, comparer à la cote réellement proposée,
  et vérifier hors échantillon si les écarts détectés se traduisent en ROI
  positif net de marge.
- **Benchmark** : cote du marché dérivé prise telle quelle (sans
  détection d'inéquation).
- **Risques d'overfitting** : modéré — dépend de la stabilité de la
  distribution des écarts de buts dans le temps (changements de règles,
  d'intensité de jeu d'une saison à l'autre).
- **Classification : Intéressante.** Mécanisme mathématiquement sain
  (aucune dépendance à des données de flux public non vérifiables,
  contrairement à C3/C4), mais nécessite l'extension du schéma de cotes
  au-delà du 1X2. Bon candidat étape 3 une fois cette extension faite.

### C7. Parlays corrélés

- **Mécanisme supposé** : si le bookmaker tarifie un combiné en supposant
  l'indépendance de deux événements alors qu'ils sont en réalité corrélés
  positivement, le combiné devient favorable au parieur.
- **Variables nécessaires** : historique conjoint de deux marchés (ex.
  victoire du favori à domicile ET Over 2.5 buts) pour estimer la
  corrélation réelle P(B|A) vs P(B).
- **Testable historiquement** : oui, avec les données déjà prévues
  (`match_results`).
- **H0** : la corrélation empirique entre les deux événements combinés
  n'est pas significativement différente de l'indépendance supposée par le
  prix du combiné (une fois la marge retirée).
- **Protocole hors-échantillon** : estimer la corrélation sur les données
  antérieures à `T`, vérifier hors échantillon si le combiné réellement
  proposé (avec sa marge) reste à EV positive une fois la vraie
  corrélation appliquée.
- **Benchmark** : prix du combiné sous hypothèse d'indépendance (ce que le
  bookmaker suppose, d'après l'hypothèse).
- **Risques d'overfitting** : faible à modéré si la paire d'événements
  testée est choisie *a priori* sur une base logique (comme victoire
  large + Over, qui a un lien causal évident) plutôt qu'en scannant toutes
  les paires possibles pour trouver la plus corrélée après coup (ce
  serait un cas classique de data snooping).
- **Classification : Intéressante.** Mécanisme statistiquement solide et
  peu coûteux à tester, mais dépend crucialement d'un choix a priori
  discipliné des paires testées.

- **Résultat empirique C7 — PHASE 1 UNIQUEMENT (existence de la
  corrélation, pas rentabilité d'un combiné réel)** :
  - **Paire d'événements testée, fixée avant tout calcul** :
    A = « l'équipe à domicile est favorite selon `poisson_simple`
    (point-in-time, comparaison stricte `P(victoire domicile) >
    P(victoire extérieur)`, aucun autre modèle, aucun seuil de
    magnitude) » ; B = « Over 2.5 buts (`home_goals + away_goals >= 3`) ».
    Aucune autre paire, aucun autre seuil Over/Under, aucun seuil de
    probabilité de favori n'a été testé.
  - **Protocole** : rodage de `poisson_simple` (40% de chaque saison,
    même convention que B3/B3.2), estimation sur la saison 2024/25,
    confirmation sur la saison 2025/26 (consultée une seule fois, méthode
    non réajustée) — `scripts/run_stage5_c7_correlated_events.py`. Test de
    différence de proportions (Chi-deux, `two_by_two_association_test`,
    `calibration_engine/significance.py`) par championnat et par saison.
  - **Réserve de transparence** : ces deux saisons ont déjà servi à B3 et
    B3.2, mais pour une question différente (performance comparée de
    modèles buts/xG, pas corrélation d'issues de match) — aucun résultat
    ni métrique de B3/B3.2 n'a été réutilisé pour définir ou ajuster ce
    protocole, mais ce n'est donc pas, au sens strict, un jeu de données
    vierge.
  - **Résultats (test du 27/08/2026, diff = `P(B|A) - P(B|¬A)`)** :
    - Ligue 1 : estimation diff=-0.005, IC95%=[-0.150, +0.140] ;
      confirmation diff=-0.037, IC95%=[-0.190, +0.116] → non positif
    - Premier League : estimation diff=+0.060, IC95%=[-0.070, +0.189] ;
      confirmation diff=+0.054, IC95%=[-0.084, +0.193] → non positif
    - Liga : estimation diff=+0.101, IC95%=[-0.037, +0.240] ;
      confirmation diff=+0.089, IC95%=[-0.049, +0.227] → non positif
  - **Verdict C7 (phase 1) : REJETÉ — absence d'association démontrée pour
    cette paire précise, sans généralisation aux autres marchés/parlays**,
    cohérent sur les trois championnats et les deux saisons — aucun
    intervalle de confiance n'exclut 0.
  - **Ce que ce résultat permet de conclure** : dans nos données actuelles,
    aucune corrélation exploitable n'a été détectée entre « favori à
    domicile selon `poisson_simple` » et « Over 2.5 buts » — la condition
    nécessaire au mécanisme de mauvaise tarification de combiné décrit
    dans le corpus n'est pas remplie pour cette paire d'événements précise.
  - **Ce que ce résultat NE permet PAS de conclure** : rien sur la
    rentabilité réelle d'un pari combiné en général (seule cette paire
    d'événements précise a été testée, pas C7 dans l'absolu, ni les
    marchés liés en général) ; rien non plus sur une éventuelle phase 2
    (EV réel sur cotes de combinés) — notre schéma de données ne contient
    aucune cote de marché combiné (seul le 1X2 est modélisé), une
    extension du Data Engine serait nécessaire et n'est pas engagée.
  - **Statut** : phase 1 close sur ce verdict REJETÉ pour cette paire
    d'événements. Aucune autre paire, aucun autre seuil, aucune phase 2
    ne sont testés sans nouvelle décision explicite de l'utilisateur.

---

## D. RISK ENGINE — Hors scope étape 2, catalogué pour l'étape 4

### D1. Kelly fractionnaire (Half-Kelly / Quarter-Kelly)

- **Mécanisme** : miser une fraction k (0.25 à 0.5) de la recommandation
  de Kelly complet pour réduire la volatilité tout en conservant une
  grande partie du taux de croissance (Epstein démontre : Half-Kelly ≈ 75%
  de la croissance maximale avec une volatilité nettement réduite).
- **Statut dans les sources** : le plus grand consensus de tout le
  corpus — présent chez Epstein (démontré mathématiquement), Dolan,
  Miller/Davidow, et la synthèse le classe "A — à conserver" à
  l'unanimité.
- **Testable historiquement** : oui, par simulation (Monte Carlo) une fois
  qu'un modèle produit des probabilités calibrées et qu'un historique de
  value bets est disponible — ce qui suppose les étapes 2 et 3 déjà
  faites.
- **H0** : n/a pour la formule elle-même (démontrée mathématiquement sous
  l'hypothèse que p est correctement calibrée) ; l'hypothèse empirique
  pertinente est plutôt : *la sensibilité du Kelly complet aux erreurs de
  calibration de p rend le Kelly fractionnaire préférable en pratique sur
  nos données.*
- **Protocole hors-échantillon** : simulation Monte Carlo comparant Flat
  Betting, Quarter-Kelly, Half-Kelly et Full Kelly sous différents niveaux
  de biais d'estimation de p injectés artificiellement (car notre modèle
  réel ne sera jamais parfaitement calibré) — mesurer drawdown maximal et
  croissance terminale pour chaque configuration.
- **Benchmark** : Flat Betting (déjà imposé comme point de départ
  obligatoire par notre architecture, avant toute Kelly).
- **Risques d'overfitting** : faible sur la formule ; le choix de la
  fraction k reste un paramètre à valider plutôt qu'à fixer arbitrairement.
- **Classification : Fondation.** Déjà prévu dans l'architecture (Risk
  Engine, étape 4, "Kelly fractionnaire uniquement après validation
  statistique suffisante"). Le corpus renforce ce choix déjà acté, rien à
  changer.

### D2. Effet de cliquet de Parrondo (portefeuille de marchés à EV négative combinés)

- **Mécanisme supposé** : combiner deux marchés individuellement à
  espérance négative, reliés par une variable d'état commune (ex.
  dynamique de la bankroll), peut produire un portefeuille globalement à
  espérance positive — démontré mathématiquement par Epstein sur des jeux
  de pièces artificiels.
- **Variables nécessaires** : deux marchés candidats à EV individuellement
  négative avec une variable d'état de couplage plausible — aucun exemple
  concret n'est donné pour le football dans les sources ; c'est une pure
  extrapolation du chapitre 4 d'Epstein.
- **Testable historiquement** : très difficilement — il faudrait déjà
  disposer de deux stratégies individuellement testées et démontrées
  déficitaires, ce qui suppose un travail de modélisation qui n'existe pas
  encore, plus la définition d'une règle de couplage non spécifiée par la
  source pour le football.
- **H0** : aucune combinaison de deux stratégies à EV négative sur le
  football ne produit un portefeuille à EV positive.
- **Protocole hors-échantillon** : non défini à ce stade — cette hypothèse
  n'est pas mûre pour un protocole concret, elle nécessite d'abord
  l'existence de deux stratégies candidates individuellement testées.
- **Benchmark** : n/a.
- **Risques d'overfitting** : très élevé — le paradoxe de Parrondo, dans
  sa forme originale, dépend de propriétés très spécifiques (dépendance
  modulo un entier, structure de chaîne de Markov précise) qui n'ont
  aucune raison de se transposer telles quelles à des marchés de paris
  sportifs. Le risque principal est de chercher a posteriori une paire de
  marchés dont la combinaison "marche" par pur hasard sur l'historique
  disponible.
- **Classification : Spéculative**, à la limite d'"à rejeter" en l'état.
  Intellectuellement intéressant, mais aucun mécanisme concret n'est
  proposé pour le football — à ne pas prioriser tant qu'aucune paire de
  stratégies candidates n'existe.

### D3. Simulation de Monte-Carlo et inégalité de Tchebychev pour le dimensionnement de bankroll

- **Mécanisme** : simuler des milliers de trajectoires de bankroll pour
  dimensionner le capital de départ et borner la probabilité de ruine sous
  un seuil cible, sans supposer que la distribution des gains suit une loi
  normale (Tchebychev, plus conservateur mais sans hypothèse de forme).
- **Testable historiquement** : oui, par simulation pure une fois les
  paramètres du modèle de risque définis (taux de value bets, distribution
  d'edge, fraction de Kelly retenue).
- **H0** : n/a — c'est un outil de dimensionnement, pas une hypothèse
  empirique testée contre des données historiques.
- **Protocole** : simulation avant tout déploiement réel, avec les
  paramètres estimés le plus conservativement possible (pas les
  paramètres les plus optimistes issus du backtest).
- **Benchmark** : n/a.
- **Risques d'overfitting** : aucun risque de data snooping directement,
  mais risque classique de sous-estimer la vraie variance si les
  paramètres d'entrée de la simulation sont eux-mêmes issus d'un backtest
  déjà optimisé (fuite indirecte).
- **Classification : Fondation.** Outil méthodologique déjà cohérent avec
  le Backtesting Engine prévu (drawdown, volatilité, robustesse). À
  intégrer nativement à l'étape 4, aucune hypothèse à trancher au
  préalable.

---

## E. FEATURES CONTEXTUELLES — à tester variable par variable, pas comme un modèle

Le corpus (surtout la synthèse croisée et Dolan) propose une longue liste de
variables contextuelles (fatigue, arbitre, météo, derby, motivation,
composition d'équipe). **Aucune ne doit être ajoutée en bloc au modèle de
l'étape 2.** Le principe directeur du projet ("ne jamais considérer une
variable comme utile simplement parce qu'elle améliore un backtest",
"éviter la sélection rétroactive des variables") s'applique ici plus qu'ailleurs :
ce sont exactement les variables les plus tentantes à empiler pour gonfler
artificiellement un backtest, et c'est explicitement le piège que Miller &
Davidow et Epstein dénoncent dans le corpus lui-même. Chacune doit être
testée **individuellement**, en ajout marginal à la meilleure configuration
déjà validée en section A, jamais en groupe.

**Contrôle méthodologique additionnel — test de "gliding" (Miller &
Davidow).** En plus du test en trois points déjà retenu pour qualifier un
"angle" exploitable (prévisible, quantifiable, non intégré dans la ligne),
Miller & Davidow proposent un critère de validation supplémentaire pour
distinguer un véritable angle d'une "tendance" fallacieuse : l'effet doit
varier de façon **continue** avec la variable causale invoquée ("gliding"),
et non présenter un seuil arbitraire (cutoff) sans justification causale
graduelle. Un effet qui n'apparaît qu'à partir d'un seuil précis (ex. "3ᵉ
match en 7 jours", "défaite par ≥4 buts") sans intensification progressive
autour de ce seuil est suspect ; un effet qui croît continûment avec la
variable causale est plus crédible. Ce contrôle s'applique en particulier à
E1 (seuil "3 matchs/7 jours") et E6 (seuil "≥4 buts") ci-dessous, dont les
seuils numériques n'ont pas encore été testés pour continuité : le protocole
hors-échantillon de chaque variable devra vérifier, en plus de la
significativité au-dessus/en-dessous du seuil retenu, que l'effet ne
présente pas une discontinuité artificielle autour de ce seuil. Ceci ne
change aucune classification ci-dessous — c'est une exigence de protocole
supplémentaire à appliquer au moment du test, pas un résultat déjà obtenu.
(Source : `research_framework_audit.md`, §E.)

| Hypothèse | Mécanisme | Donnée requise (déjà dispo ?) | H0 | Overfitting | Classe |
|---|---|---|---|---|---|
| **E1. Fatigue de calendrier chargé** (3ᵉ match en 7 jours) | Perte d'espérance de buts marqués (~15% cité, non sourcé formellement) | Dates de matchs (`kickoff_time`, dispo) — calculable sans nouvelle donnée | Aucune perte significative d'espérance de buts hors échantillon | Modéré (seuil "3 matchs/7 jours" à fixer a priori) | Intéressante |
| **E2. Fatigue de déplacement européen** (Europa League jeudi + championnat dimanche, >2000km) | Sur-évaluation du favori par le marché dans cette situation | Calendrier de coupes européennes + distances (donnée nouvelle : géolocalisation des stades) | Pas de sous-performance mesurable vs cote d'ouverture | Élevé (combinaison de 3 seuils : jours de repos, distance, calendrier europ.) | Spéculative |
| **E3. Biais de l'arbitre à domicile** | Ajustement HFA selon le taux historique de penalties/cartons de l'arbitre | Identité de l'arbitre par match — **donnée non prévue actuellement** | L'identité de l'arbitre n'améliore pas le modèle hors échantillon | Modéré à élevé (petit échantillon par arbitre) | Spéculative |
| **E4. Vent fort → Under** | Vent >40km/h corrélé à moins de buts | Données météo au stade — **donnée non prévue actuellement**, source externe à intégrer | Le vent n'est pas corrélé à une fréquence de buts significativement différente | Faible sur le mécanisme, mais échantillon de matchs à vent extrême probablement petit | Intéressante (une fois la donnée dispo) |
| **E5. Effet derby** (réduction de HFA) | Familiarité entre équipes annule une partie de l'avantage du terrain | Liste des rivalités/derbys — donnée nouvelle (référentiel à construire), calculable en partie via distance géographique | Le HFA des matchs de derby n'est pas significativement inférieur au HFA moyen | Modéré (définition de "derby" elle-même est un choix, source de data snooping) | Spéculative |
| **E6. Motivation de rebond après lourde défaite** | Équipe battue par ≥4 buts sur-performe son handicap au match suivant | `match_results` (dispo) | Pas de sur-performance significative après une défaite lourde | Élevé — proche du narratif "gambler's fallacy" qu'Epstein dénonce explicitement | Spéculative, proche d'à rejeter |
| **E7. "Must-Win" déjà pricé par le marché** | Le public sur-évalue les équipes à fort enjeu ; le marché intègre déjà ce biais, donc parier sur l'équipe motivée est risqué, pas rentable | Contexte de classement (calculable depuis `match_results` + calendrier) | Il n'y a pas de sous-performance systématique des cotes sur les équipes "must-win" | Faible — c'est une hypothèse *nulle* par nature (elle prédit l'absence d'edge), donc peu de risque de data snooping puisqu'on ne cherche pas un signal à exploiter mais une confirmation d'efficience | **Intéressante**, et méthodologiquement utile même si elle "ne trouve rien" — sert de garde-fou contre E6 |
| **E8. Impact de l'absence à un poste clé (gardien, défenseur central)** | Absence pèse plus lourd que celle d'un joueur non central, de façon non linéaire par poste | Compositions officielles + un rating d'impact joueur — **donnée non prévue actuellement**, et nécessite un modèle d'impact à concevoir (explicitement PAS l'analogie EOR, voir F1) | L'absence d'un titulaire à un poste clé n'a pas d'effet significatif mesurable sur λ/μ une fois contrôlé par la force globale de l'équipe | Élevé — nécessite un rating de "centralité" du poste qui est lui-même un choix de modélisation arbitraire si mal spécifié | Spéculative |
| **E9. Asymétrie 1ère/2nde mi-temps** | Plus de buts marqués en 2nde période que ne le supposent les modèles simplifiés de bookmakers | `match_results` par mi-temps — **donnée non prévue actuellement** (nous ne stockons que le score final) | Pas de différence significative de taux de buts entre les deux mi-temps une fois contrôlé par le score en cours | Faible sur le mécanisme, mais nécessite une extension de schéma | Intéressante (une fois la donnée dispo) |

---

## F. Hypothèses rejetées d'emblée

### F1. Analogie EOR (Effect of Removal) pour l'absence d'un joueur

- **Mécanisme invoqué par le corpus** : transposer l'EOR du Blackjack
  (impact du retrait d'une carte précise d'un sabot fini) à l'absence d'un
  joueur de football.
- **Pourquoi c'est invalide** : l'EOR d'Epstein repose sur un tirage sans
  remise dans un univers combinatoire fermé et fini (52 cartes, 8 jeux).
  Un joueur de football n'est pas une carte : son impact dépend
  d'interactions tactiques non additives avec ses coéquipiers, du système
  de jeu, et du remplaçant qui le remplace (qui n'est pas "une autre carte
  du même sabot" mais une entité à impact propre). L'audit du document de
  synthèse identifie explicitement cette erreur ("hérésie mathématique")
  et la classe D — à écarter. Nous reprenons cette conclusion en la
  justifiant nous-mêmes : le mécanisme mathématique ne se transpose
  simplement pas.
- **Alternative retenue** : E8 (impact d'absence via un rating de
  centralité de poste et un delta de qualité titulaire/remplaçant),
  explicitement *sans* le vocabulaire ni la mécanique EOR — et classée
  "Spéculative", pas "Fondation", précisément parce qu'elle reste à
  concevoir de zéro.
- **Classification : À rejeter.**

### F2. Full Kelly

- **Mécanisme invoqué** : miser exactement la fraction de Kelly complète.
- **Pourquoi c'est rejeté** : mathématiquement optimal seulement si p est
  connu exactement — ce qui n'est jamais le cas avec un modèle statistique
  de football. Consensus unanime du corpus (Epstein, Dolan, la synthèse)
  pour rejeter le Full Kelly en pratique, exactement pour la raison que
  notre architecture a déjà anticipée en imposant Flat Betting d'abord et
  Kelly fractionnaire ensuite.
- **Classification : À rejeter** (en tant que politique de mise réelle —
  reste utile comme borne théorique de référence dans les simulations D1).

### F3. Systèmes de progression (Martingale, d'Alembert, Labouchère)

- **Mécanisme invoqué** : ajuster la mise en fonction des résultats
  passés pour "récupérer" les pertes.
- **Pourquoi c'est rejeté** : Théorème I d'Epstein, démontré
  rigoureusement — aucun système de mise ne change l'espérance
  mathématique par unité misée sur des événements indépendants. Ces
  systèmes déplacent seulement la forme de la distribution de risque
  (haute probabilité de petit gain contre risque de ruine totale), ils ne
  créent pas d'edge.
- **Classification : À rejeter.**

### F4. Chasser les séries (Gambler's Fallacy)

- **Mécanisme invoqué** : une équipe "doit" gagner après une série de
  défaites, ou un résultat "doit" arriver car il ne s'est pas produit
  récemment.
- **Pourquoi c'est rejeté** : biais cognitif explicitement démonté par
  Epstein (Théorème II — aucun avantage à parier sur une sous-séquence
  d'événements indépendants) et par Dolan lui-même dans son livre. Se
  recoupe directement avec E6 (motivation de rebond), qui doit donc être
  traitée avec un scepticisme renforcé plutôt que comme une piste neutre.
- **Classification : À rejeter** (comme mécanisme narratif). Voir E6 pour
  la version testable et sceptique de cette idée.

### F5. Transplantation directe de systèmes propres à d'autres sports (Roxy Special / nombres clés NFL, premier buteur au hockey)

- **Mécanisme invoqué** : teaser combiné exploitant les "nombres clés" 3
  et 7 en NFL ; probabilité de victoire conditionnée au premier buteur en
  hockey (70%/90%).
- **Pourquoi c'est rejeté en l'état** : ces deux mécanismes dépendent de
  propriétés structurelles spécifiques à leur sport d'origine (distribution
  des écarts de score concentrée autour de valeurs entières précises en
  NFL ; dynamique de score très faible et quasi-monotone au hockey). Le
  football n'a pas d'équivalent démontré à des "nombres clés", et la
  transposition du modèle du premier buteur relève du live betting
  (explicitement hors scope avant l'étape 6). Aucune des deux hypothèses
  n'est testable avec l'infrastructure prévue avant plusieurs étapes.
- **Classification : À rejeter pour l'instant** (pas rejetée sur le fond,
  mais aucune forme testable n'existe encore pour le football — à
  reconsidérer seulement si une structure de marché équivalente aux
  "nombres clés" est un jour identifiée empiriquement sur le football, ou
  à l'étape 6 pour la version live).

---

## G. Risques méthodologiques transversaux identifiés par le corpus lui-même

Ces points ne sont pas des hypothèses à tester — ce sont des règles de
protocole que le corpus lui-même met en garde de violer, et qui
s'appliquent à *toutes* les hypothèses ci-dessus :

1. **Biais d'arrêt optionnel (Epstein, ch. 11)** : arrêter un backtest au
   moment où le ROI atteint un pic pour "valider" un modèle est une
   falsification statistique. Notre protocole doit fixer la taille de
   l'échantillon de test *a priori*, jamais l'ajuster après avoir vu le
   résultat. Ceci est déjà cohérent avec notre discipline de Repository
   point-in-time (étape 1), mais s'applique aussi à la *fenêtre de test*
   elle-même, pas seulement aux données visibles à chaque décision.
   **Précision (Epstein, ch. 11)** : Epstein distingue explicitement deux
   situations qui ne portent pas le même risque. (a) Un jeu à probabilité
   connue avec un seuil d'arrêt fixé *a priori* (ex. une simulation qui
   s'arrête dès qu'une trajectoire atteint un objectif de capital
   prédéterminé) n'est pas un test d'hypothèse — l'arrêt n'y introduit
   aucun biais, car ce n'est pas une hypothèse statistique qui est mise à
   l'épreuve, seulement une somme qui se conclut automatiquement en
   atteignant une valeur préétablie. (b) Un test d'hypothèse statistique où
   l'expérimentateur choisit d'arrêter la collecte de données en fonction
   du résultat déjà observé introduit, lui, un biais de rejet artificiel de
   l'hypothèse nulle — c'est ce cas précis que la règle ci-dessus vise.
   Concrètement pour notre architecture : le walk-forward du Calibration
   Engine (comparer Poisson simple vs Poisson+A1 sur un échantillon de
   test) relève du cas (b) et doit donc fixer sa fenêtre de test a priori,
   comme déjà prescrit ; la simulation Monte Carlo du Risk Engine (D3),
   qui caractérise une distribution de résultats sous paramètres
   contrôlés plutôt que de tester une hypothèse sur nos propres données,
   relève davantage du cas (a) et n'est pas exposée au même risque. Cette
   distinction ne change ni le protocole du Calibration Engine ni celui du
   Risk Engine déjà décrits plus haut — elle clarifie seulement *où* le
   risque d'arrêt optionnel s'applique avec toute sa force dans le
   pipeline. (Source : `research_framework_audit.md`, §G1.)
2. **Empilement de filtres contextuels (section E)** : la synthèse et
   Dolan mettent tous deux en garde contre l'overfitting par accumulation
   de variables situationnelles. Règle opérationnelle : chaque variable de
   la section E doit être testée **seule**, en ajout marginal à la
   meilleure configuration déjà validée en section A, avec sa propre
   fenêtre hors échantillon dédiée. Ne jamais construire un modèle
   multi-filtres directement.
   **Grille de validation additionnelle (Appelbaum, ch. 8 "Learn from the
   Past")** : avant qu'une variable de la section E ne soit considérée
   comme un candidat sérieux (même à l'issue d'un protocole hors-échantillon
   positif), elle doit satisfaire trois critères empruntés à Appelbaum pour
   juger un "betting system" :
   1. **Une hypothèse causale motivée *a priori*** — le mécanisme doit être
      explicable avant de regarder les résultats, jamais reconstruit après
      coup pour justifier un chiffre qui "marche".
   2. **Un échantillon suffisamment large** — repère numérique explicite
      donné par la source : au moins une centaine d'observations
      (matchs). Un taux de réussite impressionnant sur un petit échantillon
      (ex. "9 sur 10") est explicitement moins fiable qu'un taux plus
      modeste sur un grand échantillon.
   3. **Une stabilité pluriannuelle** — un effet concentré sur une ou deux
      saisons puis disparu (le marché s'ajuste) doit être traité avec
      suspicion même si le cumul reste positif sur la période totale.
   Cette grille ne remplace pas le protocole hors-échantillon déjà prévu
   (walk-forward, benchmark, H0 explicite pour chaque variable de la
   section E) — elle s'y ajoute comme critère de robustesse minimal avant
   toute adoption. Elle ne change aucune classification actuelle. (Source :
   `research_framework_audit.md`, §G2.)
3. **Petits échantillons anecdotiques du corpus lui-même** : plusieurs
   "résultats" cités dans les livres (162 matchs, 200 situations RLM,
   quelques exemples de matchs uniques pour le modèle hockey/baseball) ne
   sont pas des preuves statistiquement solides même dans leur domaine
   d'origine — a fortiori pas une fois transposés au football. Elles
   doivent être traitées comme des pistes à tester, jamais comme des
   résultats acquis à répliquer.
4. **La transplantation inter-sports est elle-même une hypothèse.** Sauf
   mention contraire ci-dessus, aucune affirmation chiffrée du corpus
   (taux de réussite, seuils de %tickets, ampleur d'effet) ne doit être
   réutilisée telle quelle comme paramètre de notre système — chaque seuil
   doit être ré-estimé sur nos propres données football, jamais importé
   directement d'un livre parlant de NFL ou de hockey.

---

## G2. Force des conclusions / limites de puissance (audit post-campagne réelle)

Cette section fait suite à un audit méthodologique critique de l'ensemble
des expériences réelles A1/A2/B1/B2/B3/B3.2/C7, mené après la clôture de
la campagne sur le pool de données actuel. Elle ne change **aucun**
chiffre, protocole ou verdict déjà obtenus — elle en précise uniquement la
force scientifique réelle, pour éviter toute lecture qui surinterpréterait
un résultat non significatif comme une preuve d'absence d'effet.

1. **Absence de significativité ≠ preuve d'absence d'effet.** Sur les
   hypothèses testées sur données réelles, seule **A1** (deux fois, sur
   synthétique) et **B1 en Ligue 1 spécifiquement** portent une preuve
   statistique directe *contre* le candidat (IC95% entièrement du côté
   défavorable). Pour A2, B2, B3, B3.2, C7, et B1 en Premier League/Liga,
   l'IC95% inclut 0 : c'est une **absence de preuve d'amélioration**, pas
   une démonstration de nullité. Les libellés de verdict de chaque section
   ci-dessus ont été précisés en conséquence.
2. **B3 et B3.2 sont particulièrement sous-puissants pour des effets
   faibles.** Ces deux tests portent sur une seule saison (n≈92-114 matchs
   de test par championnat) et comparent des modèles aux prédictions
   nettement plus divergentes que, par exemple, poisson_simple vs
   Dixon-Coles. En inversant la formule de l'intervalle bootstrap déjà
   publié (`SE = largeur_IC / (2×1.96)`, puis `écart-type par match =
   SE × √n`), l'écart-type des différences appariées par match observé
   dans ces deux expériences atteint 0.08-0.16 selon le championnat — ce
   qui, à ces tailles d'échantillon, place l'effet minimum détectable à
   80% de puissance au-delà de 0.03-0.04. C'est **supérieur à tous les
   diffs numériquement observés dans B3/B3.2**. Un effet réel de
   0.01-0.02 (l'ordre de grandeur systématiquement mesuré) avait donc une
   chance sérieuse de rester invisible même s'il existait.
3. **Les tests multiples au niveau du programme réduisent la confiance à
   accorder à un résultat isolé comme B1 Ligue 1.** Sept familles
   d'hypothèses ont été testées, chacune décomposée par championnat
   (~21 tests de niveau championnat au total), toutes à α=0.05, sans
   correction pour comparaisons multiples au niveau du projet. Sous
   l'hypothèse illustrative (conservatrice, ces tests n'étant pas
   strictement indépendants) qu'aucun effet réel n'existerait nulle part,
   la probabilité d'observer au moins un résultat nominalement
   significatif par pur hasard sur ~21 tests serait d'environ 66%. Le
   seul résultat individuellement significatif de toute la campagne
   réelle (B1, Ligue 1) est donc statistiquement compatible avec un faux
   positif accumulé — ce qui n'invalide pas ce résultat, mais invite à ne
   pas lui accorder plus de poids qu'à un signal isolé parmi beaucoup de
   tests, conformément à la règle déjà en place exigeant la cohérence sur
   les trois championnats pour toute promotion.
4. **Aucune correction statistique rétroactive n'est appliquée aux
   résultats déjà obtenus.** Cette section est une clarification de
   lecture, pas un recalcul : tous les chiffres, IC95%, p-values et
   verdicts d'agrégation publiés dans les sections A à C7 restent
   exactement ceux obtenus lors de chaque exécution, et aucun protocole
   historique n'est rouvert par cet audit.

---

## H. Recommandation priorisée pour l'étape 2

**À tester dans le cadre de l'étape 2 (Poisson + calibration + benchmarks)**,
comme configurations concurrentes du même modèle, benchmarkées les unes
contre les autres et contre le Poisson nu :

1. Poisson simple (base, déjà prévu) — configuration de référence.
2. Poisson + pondération temporelle (A1) — fenêtre glissante et lissage
   exponentiel, comparés entre eux et à la base.
3. Poisson + HFA à shrinkage bayésien par équipe (A2).
4. Test de Chi-Deux comme diagnostic de calibration (A4), intégré au
   Calibration Engine déjà prévu, en complément de Brier/log loss.
5. Le Power Rating de Dolan (A3) n'a pas besoin d'implémentation séparée —
   à traiter comme une paramétrisation de l'Elo déjà prévu comme benchmark.

**À garder explicitement hors de l'étape 2**, sans changement au plan déjà
validé : Dixon-Coles et mise à jour bayésienne séquentielle (B1, B2 — à
départager entre elles à l'étape 5, pas à cumuler), xG (B3 — bloqué par
l'absence de connecteur de données, indépendamment de son mérite), tout ce
qui relève du Market Engine (C1-C7, étape 3) et du Risk Engine (D1-D3,
étape 4).

**À garder en base de hypothèses documentée mais non prioritaire**,
section E : chaque variable contextuelle sera testée individuellement,
plus tard, en ajout marginal — jamais en bloc, jamais avant que la base
Poisson+A1+A2 soit elle-même validée hors échantillon.

**Rejetées, à ne pas implémenter** : F1 (EOR), F2 (Full Kelly, sauf comme
borne de référence théorique en simulation), F3 (progressions), F4
(gambler's fallacy narratif), F5 (transplantations non adaptées).

Prochaine étape naturelle : construire la configuration de base (Poisson +
A1 + A2) et le protocole de walk-forward comparatif décrit ci-dessus,
**uniquement sur demande explicite** — ce document reste une analyse, pas
une implémentation.

---

## I. Phase économique — Expérience 1 : `poisson_simple` vs marché B365 (1X2)

Première expérience économique réelle du projet, menée après la clôture de
la campagne de modélisation (A1-C7, section G2) et la construction de
l'infrastructure de cotes réelles Football-Data.co.uk
(`docs/decisions/0006-football-data-point-in-time.md`). Question unique,
pré-enregistrée : *« Le modèle `poisson_simple` produit-il, ex ante, des
probabilités suffisamment différentes du marché B365 pour identifier une
value mesurable sur le marché 1X2 ? »*

**Modèle** : `PoissonModel(use_team_hfa=False)`, benchmark officiel figé,
**inchangé**. **Marché** : Bet365 (`B365H`/`B365D`/`B365A`) uniquement,
1X2 uniquement, aucune colonne de clôture/agrégat/autre bookmaker/autre
marché. **Règle temporelle** : uniquement la règle conservatrice déjà
implémentée et documentée (`time_resolution.conservative_knowledge_time_utc`)
— aucun nouvel offset, aucune hypothèse alternative testée ; les matchs du
lundi, mardi et vendredi sont explicitement exclus et comptabilisés (la
source ne permet pas de garantir une fenêtre de connaissance strictement
antérieure au coup d'envoi pour ces jours). La cote Football-Data n'a
**jamais** un timestamp exact — seule une hypothèse conservatrice
documentée (`TIMESTAMP_STATUS_HYPOTHETICAL`) est utilisée.

### 1-2. Matchs exploitables et couverture

**1762 matchs économiquement exploitables** sur les 2132 matchs Understat
du corpus (3 championnats × 2 saisons, 2024/25 + 2025/26) :

| Championnat / saison | Understat | Apparié | Exploitable | Jour ambigu exclu | Historique insuffisant exclu | Non apparié |
|---|---|---|---|---|---|---|
| Premier League 2024/25 | 380 | 380 | 327 | 45 | 8 | 0 |
| Premier League 2025/26 | 380 | 380 | 318 | 54 | 8 | 0 |
| Ligue 1 2024/25 | 306 | 306 | 258 | 40 | 8 | 0 |
| Ligue 1 2025/26 | 306 | 298 | 256 | 34 | 8 | 8 |
| Liga 2024/25 | 380 | 380 | 305 | 69 | 6 | 0 |
| Liga 2025/26 | 380 | 379 | 298 | 75 | 6 | 1 |

L'exclusion « jour ambigu » (lundi/mardi/vendredi) retire à elle seule
environ 18 % du corpus apparié — une limite structurelle de la règle
temporelle conservatrice, pas un artefact du modèle. Les cotes étaient
complètes à 100 % sur les matchs appariés (0 exclusion pour cote
incomplète), et aucune violation point-in-time (`knowledge_time >
decision_time`) n'a été détectée sur le corpus réel (garde-fou vérifié,
compte = 0 partout).

### 3-4. Comparaison modèle / marché (purement descriptive)

| Portée | n | Brier `poisson_simple` | Brier marché normalisé | Brier marché brut (non standard) | log loss `poisson_simple` | log loss marché normalisé |
|---|---|---|---|---|---|---|
| Global | 1762 | 0.6251 | 0.5752 | 0.5757 | 1.3348 | 0.9678 |
| Liga | 603 | 0.5993 | 0.5568 | 0.5562 | 1.1375 | 0.9425 |
| Ligue 1 | 514 | 0.6336 | 0.5712 | 0.5711 | 1.4870 | 0.9624 |
| Premier League | 645 | 0.6425 | 0.5956 | 0.5975 | 1.3979 | 0.9958 |
| 2024/25 | 890 | 0.6071 | 0.5696 | 0.5700 | 1.2071 | 0.9602 |
| 2025/26 | 872 | 0.6434 | 0.5810 | 0.5814 | 1.4651 | 0.9755 |

Le marché B365 (probabilités normalisées, marge retirée) domine
`poisson_simple` sur Brier ET log loss, **sans aucune exception**, dans
les six découpages (global, 3 championnats, 2 saisons). Le Brier marché
brut (non standard — les probabilités implicites brutes ne somment pas à
1, cette valeur ne respecte donc pas la définition originale de Brier
1950 et n'est fournie qu'à titre indicatif comme demandé) est très proche
du Brier normalisé, l'overround moyen étant modeste sur ce marché.

**Calibration** (erreur absolue moyenne pondérée par tranche, one-vs-rest,
10 tranches) — global :

| Issue | `poisson_simple` | Marché normalisé |
|---|---|---|
| Domicile | 0.0794 | 0.0252 |
| Nul | 0.0525 | 0.0057 |
| Extérieur | 0.0696 | 0.0209 |

Le marché est mieux calibré que `poisson_simple` sur les trois issues, de
façon cohérente sur chaque championnat et chaque saison pris séparément
(mêmes tableaux détaillés dans la sortie du script,
`scripts/run_stage6_economic_b365_ev.py`) — jamais une exception isolée.

**Distribution des edges** (global, `p_model - p_marché`) :

| Issue | edge_raw (moyenne ± écart-type) | edge_norm (moyenne ± écart-type) | EV théorique (moyenne ± écart-type) |
|---|---|---|---|
| Domicile | -0.0214 ± 0.1437 | +0.0032 ± 0.1447 | -0.0658 ± 0.3504 |
| Nul | -0.0433 ± 0.0903 | -0.0296 ± 0.0900 | -0.1666 ± 0.3828 |
| Extérieur | +0.0091 ± 0.1293 | +0.0265 ± 0.1302 | +0.0029 ± 0.5194 |

`edge_raw` et `edge_norm` sont rapportés tous les deux, sans choisir lequel
serait « le meilleur », conformément au protocole — ils répondent à deux
questions différentes (désaccord brut de marché vs désaccord avec le
marché juste). Les deux versions concordent sur le sens du signal :
`poisson_simple` sous-estime systématiquement le nul par rapport au
marché, et son edge sur domicile/extérieur reste proche de 0 en moyenne.

### 5-6. Stratégie unique EV > 0, mise flat 1 unité — performance réalisée

Règle fixée avant observation : pari si `EV_modèle = p_model × cote_B365 -
1 > 0`, sur chaque (match, issue), mise flat 1 unité, aucun Kelly, aucun
staking, aucun filtre, aucune grille de seuils.

| Portée | n paris | Gagnants | Taux de réussite | Profit total | ROI |
|---|---|---|---|---|---|
| **Global** | **1888** | 712 | 0.377 | **-130.01** | **-0.0689** |
| Liga | 639 | 242 | 0.379 | -92.88 | -0.1454 |
| Ligue 1 | 530 | 216 | 0.408 | -26.61 | -0.0502 |
| Premier League | 719 | 254 | 0.353 | -10.52 | -0.0146 |
| 2024/25 | 967 | 364 | 0.376 | -40.00 | -0.0414 |
| 2025/26 | 921 | 348 | 0.378 | -90.01 | -0.0977 |
| Domicile | 751 | 350 | 0.466 | -70.73 | -0.0942 |
| Nul | 265 | 61 | 0.230 | -15.59 | -0.0588 |
| Extérieur | 872 | 301 | 0.345 | -43.69 | -0.0501 |

**ROI négatif sur les 9 découpages sans exception** (3 championnats, 2
saisons, 3 issues) — présenté ici comme une observation économique de
premier ordre, avant tout test d'incertitude.

### 7-8. Incertitude statistique et verdict

Bootstrap apparié (`paired_bootstrap_test`, réutilisé sans modification,
10 000 rééchantillonnages, seed=0) sur le profit par pari (n=1888) :

- profit moyen = **-0.0689** par unité misée
- **IC95% = [-0.1318, -0.0040]**, entièrement négatif
- p = 0.0384

L'intervalle de confiance à 95 % du profit moyen est **entièrement
négatif** → verdict, selon la grille imposée (résolution explicite : IC95%
entièrement > 0 → PREUVE D'AMÉLIORATION ÉCONOMIQUE ; IC95% entièrement < 0
→ SIGNAL NÉGATIF ; IC95% couvrant 0 avec ROI > 0 → SIGNAL POSITIF ; IC95%
couvrant 0 avec ROI ≤ 0 → ABSENCE DE PREUVE) :

## **VERDICT : SIGNAL NÉGATIF**

Avec n=1888 paris, ce signal n'est **pas** sous-puissant (seuil documenté
de 30 paris minimum très largement dépassé, sur les 9 découpages
également).

### Limites méthodologiques

- Timestamp Football-Data jamais vérifié — hypothèse conservatrice
  documentée (`TIMESTAMP_STATUS_HYPOTHETICAL`), jamais présentée comme un
  fait. Les matchs lundi/mardi/vendredi (~18 % du corpus apparié) sont
  exclus plutôt que rattachés par hypothèse silencieuse — un biais de
  couverture potentiel (si ces jours diffèrent structurellement des
  autres) n'est pas exclu et n'a pas été testé ici (hors périmètre de
  cette expérience).
- Le bootstrap utilisé est un rééchantillonnage i.i.d. par pari, **pas**
  un bootstrap par blocs temporels — aucune méthode de ce type n'est
  encore disponible dans le projet ; les paris d'une même journée/saison
  ne sont pas indépendants en toute rigueur (résultats de championnat
  corrélés), ce qui peut légèrement sous-estimer la largeur réelle de
  l'IC95%. Le signe du verdict (entièrement négatif) est néanmoins assez
  net (p=0.0384, cohérent sur les 9 découpages) pour rester robuste à
  cette réserve.
- Le corpus 2024/25+2025/26 a déjà servi aux expériences de modélisation
  A1/A2/B1/B2/B3/B3.2/B3.3/C7 (data snooping documenté) — la règle EV>0
  reste toutefois une règle économique fixée avant observation du ROI de
  **cette** expérience spécifique ; aucune variante de seuil n'a été
  testée ni ne sera testée après ce résultat.
- Le Brier marché « brut » est non standard (probabilités ne sommant pas à
  1) et n'est fourni qu'à titre indicatif, jamais utilisé pour le verdict.
- Comparaison faite uniquement à la cote **prise** (Bet365, hypothèse
  temporelle conservatrice), jamais à la clôture — conformément à ADR
  0003, aucune conclusion de CLV n'est tirée ici.

### Réponse à la question posée

*« Sur ce corpus réel et avec cette règle fixée à l'avance, avons-nous un
signal économique crédible, ou seulement un écart théorique entre modèle
et marché ? »*

**Ni l'un ni l'autre dans le sens positif : un signal économique crédible,
mais négatif.** `poisson_simple` n'est pas seulement « pas meilleur » que
le marché — il est mesurablement **moins bien calibré** (Brier et log loss
plus mauvais, calibration one-vs-rest plus mauvaise, sur les trois issues
et sur les six découpages testés, sans exception). L'écart théorique
positif (EV>0 selon le modèle) ne se traduit **pas** en profit réalisé :
au contraire, la stratégie EV>0 produit une perte statistiquement
significative (IC95% entièrement négatif, p=0.0384, n=1888 paris,
cohérente sur les 3 championnats, les 2 saisons et les 3 issues). Ce
résultat n'est pas une simple absence de preuve — c'est une preuve directe
que, sur ce corpus et avec cette règle, **suivre les désaccords de
`poisson_simple` avec le marché B365 aurait perdu de l'argent**, cohérente
avec le fait, déjà établi ci-dessus, que le marché reste mieux calibré que
le modèle.

**`poisson_simple` reste le modèle de référence officiel du système, sans
aucune modification.** Aucun autre seuil EV, aucun Kelly, aucun staking,
aucun CLV, aucun autre bookmaker/marché, aucun nouveau modèle (dont B3.3)
n'ont été testés après ce résultat, conformément au protocole (arrêt
obligatoire).

---

## J. Diagnostic post-E1 — décomposition de l'écart poisson/marché et information incrémentale de xG

Diagnostic **pur** (aucune nouvelle expérience économique, aucune
stratégie, aucune optimisation, `poisson_simple` inchangé) motivé
directement par le verdict SIGNAL NÉGATIF de l'expérience E1 (section I).
Question : *pourquoi `poisson_simple` est-il inférieur au marché B365, et
existe-t-il malgré tout une information indépendante exploitable
(notamment via xG) ?* Exécuté sur exactement les 1762 matchs du dataset
E1 (`scripts/run_stage7_diagnostic_e1_market_gap.py`, réutilisant
`economic_dataset.py` sans modification), avec les prédictions `xg_model`
(B3, inchangé) attachées via `real_data_walk_forward` — vérification
explicite (assertion, pas hypothèse) que le `decision_time` recalculé est
identique à celui d'E1 pour chaque match (partie 7). xG s'est avéré
disponible pour la **totalité** des 1762 matchs (le seuil
`MIN_TRAIN_MATCHES=10` ne s'est jamais révélé plus contraignant pour le
xG que pour les buts sur ce corpus — un constat, pas une hypothèse
supplémentaire).

### Partie 1 — Décomposition de l'écart (global)

| Issue | biais moyen | biais médian | dispersion (std) | calibration `poisson_simple` | calibration marché | % écart ≥ 0.05 | % écart ≥ 0.10 |
|---|---|---|---|---|---|---|---|
| Domicile | +0.0032 | -0.0009 | 0.1447 | 0.0794 | 0.0252 | 67.0 % | 38.8 % |
| Nul | -0.0296 | -0.0370 | 0.0900 | 0.0525 | 0.0057 | 44.0 % | 12.2 % |
| Extérieur | +0.0265 | +0.0138 | 0.1302 | 0.0696 | 0.0209 | 62.9 % | 34.2 % |

Le biais **moyen** est faible sur domicile/extérieur (le désaccord n'est
pas systématiquement dans un sens) mais `poisson_simple` **sous-estime
systématiquement le nul** (biais négatif, cohérent sur toutes les
sous-populations testées ci-dessous). Surtout : la **dispersion** de
l'écart est large (std 0.09-0.14) et la **calibration** de
`poisson_simple` est 3 à 9 fois pire que celle du marché selon l'issue —
`poisson_simple` n'est pas juste « en moyenne pareil au marché avec du
bruit symétrique », il est structurellement moins bien calibré. Près de
39 % des matchs présentent un écart ≥ 10 points de probabilité sur
l'issue domicile — un désaccord fréquent, pas un phénomène marginal.

**Par championnat et par saison** (mêmes tableaux détaillés dans la
sortie du script) : le marché domine `poisson_simple` en calibration sur
**tous** les découpages sans exception (ex. Ligue 1 domicile :
`poisson_simple` 0.1061 vs marché 0.0213 ; toutes saisons/championnats
confondus, jamais d'inversion). La calibration de `poisson_simple` se
dégrade même légèrement en 2025/26 par rapport à 2024/25 (domicile 0.0884
vs 0.0789, nul 0.0627 vs 0.0425) — aucune amélioration temporelle
spontanée.

**Par décile de probabilité de marché** : le biais de `poisson_simple`
n'est pas monotone — il alterne sur-confiance et sous-confiance selon la
tranche (ex. domicile : décile 7 biais +0.058 — sur-confiance nette —
puis décile 8 biais -0.021 ; extérieur : décile 7 biais +0.105, le plus
grand écart local observé, contre seulement +0.043 pour le marché sur la
même tranche). Le marché reste, lui, proche de la fréquence observée sur
la quasi-totalité des déciles. `poisson_simple` n'est donc pas
simplement « décalé » dans un sens fixe — il est **irrégulier**, ce qui
est cohérent avec une calibration globalement moins bonne plutôt qu'un
biais directionnel corrigible par un simple recalibrage additif.

### Partie 2 — Où `poisson_simple` perd (quintiles de probabilité du favori marché)

| Quintile | prob. favori (marché) | prob. favori (poisson) | fréquence observée | Brier `poisson_simple` | Brier marché | écart Brier |
|---|---|---|---|---|---|---|
| Q0 (plus équilibré) | 0.382 | 0.385 | 0.425 | 0.7145 | 0.6561 | 0.0584 |
| Q1 | 0.437 | 0.462 | 0.397 | 0.7200 | 0.6593 | 0.0607 |
| Q2 | 0.505 | 0.531 | 0.514 | 0.6514 | 0.6167 | 0.0347 |
| Q3 | 0.580 | 0.618 | 0.583 | 0.6315 | 0.5695 | 0.0620 |
| Q4 (plus gros favoris) | 0.717 | 0.743 | 0.770 | 0.4075 | 0.3737 | 0.0338 |

**Aucune caractérisation simple ne ressort** : l'écart Brier
`poisson_simple` − marché est présent dans **les cinq** quintiles
(0.033 à 0.062), sans tendance monotone claire selon la force du favori —
ce n'est pas spécifiquement sur les gros favoris, ni spécifiquement sur
les matchs équilibrés, que `poisson_simple` décroche : le désavantage est
**diffus sur tout le spectre**. Conformément au protocole, aucun
sous-groupe n'a été retenu sur la base d'un critère de rentabilité — cette
partie reste une caractérisation du biais/de la calibration, pas une
recherche de niche exploitable.

### Partie 3 — Comparaison des erreurs par match

`delta_error = erreur_poisson − erreur_marché` (Brier ligne par ligne,
n=1762) : moyenne +0.0499 (**identique**, comme attendu, à l'écart de
Brier global d'E1 — vérification de cohérence croisée réussie), écart-type
0.2750, médiane +0.0160. Distribution : `poisson_simple` fait
**strictement mieux** que le marché sur 35.5 % des matchs pris
individuellement (delta < -0.05), les deux sont proches sur 21.3 %
(|delta| ≤ 0.05), et le marché domine nettement sur 43.2 % (delta > 0.05).
**`poisson_simple` n'est donc pas uniformément pire** — il l'est **en
moyenne et de façon majoritaire**, avec une hétérogénéité match par match
substantielle.

### Partie 4 — Le désaccord contient-il une information indépendante ?

Question centrale : une fois la probabilité de marché prise en compte
(comparaison **démeanée par décile** de probabilité de marché — variable
disponible avant le match —, groupes non appariés comparés via
`two_sample_bootstrap_test`, réutilisé sans modification), le **signe**
du désaccord `poisson_simple` − marché prédit-il encore la fréquence
observée du résultat ?

| Issue | n (désaccord positif / négatif ou nul) | différence moyenne démeanée | IC95 % | p |
|---|---|---|---|---|
| Domicile | 875 / 887 | -0.0204 | [-0.0630, +0.0221] | 0.356 |
| Nul | 373 / 1389 | -0.0135 | [-0.0600, +0.0330] | 0.578 |
| Extérieur | 969 / 793 | +0.0097 | [-0.0306, +0.0492] | 0.613 |

**Aucun signal détecté sur les trois issues** — les trois IC95 % couvrent
largement 0. La méthode a été validée au préalable sur données
synthétiques (tests unitaires) : elle détecte correctement un signal
injecté délibérément informatif, et ne produit pas de faux positif quand
le désaccord est du bruit pur — ce résultat « pas de signal » n'est donc
pas un artefact de puissance insuffisante de la méthode elle-même, mais
une observation sur ces données. **Le désaccord de `poisson_simple` avec
le marché ne montre, sur ce corpus, aucune information indépendante
détectable au-delà de ce que la probabilité de marché contient déjà** —
cohérent avec le tableau de calibration de la partie 1 : `poisson_simple`
semble surtout plus bruité que le marché, pas porteur d'un angle mort
distinct que le marché ignorerait.

### Parties 5-6 — xG face au marché

Sur les 1762 matchs (xG disponible partout) :

| | Brier |
|---|---|
| `poisson_simple` | 0.6251 |
| `xg_model` (B3) | 0.6057 |
| Marché normalisé | 0.5752 |

**Corrélations des erreurs par match** (Brier ligne par ligne, Pearson) :
(poisson, marché) = **+0.789**, (xG, marché) = **+0.845**, (poisson, xG) =
**+0.838**.

**Différences appariées de Brier** (`paired_bootstrap_test`, réutilisé
sans modification, purement descriptif) :

| Comparaison | diff. moyenne | IC95 % | p |
|---|---|---|---|
| xG − marché | +0.0305 | [+0.0205, +0.0406] | <0.0001 |
| `poisson_simple` − marché | +0.0499 | [+0.0375, +0.0630] | <0.0001 (= E1, cohérent) |
| xG − `poisson_simple` | -0.0194 | [-0.0309, -0.0080] | 0.0006 |

**Réponse à la question centrale de la partie 5** (« le xG fait-il des
erreurs différentes de celles du marché ? ») : **non, pas dans le sens
recherché**. xG est significativement meilleur que `poisson_simple`
(confirme la complémentarité partielle déjà connue depuis B3/B3.2/B3.3)
**mais significativement moins bon que le marché**, et surtout ses
erreurs sont **encore plus corrélées au marché** (+0.845) que ne le sont
celles de `poisson_simple` (+0.789). Autrement dit, xG se trompe
**davantage aux mêmes endroits que le marché**, pas à des endroits
différents — l'amélioration de xG sur `poisson_simple` semble provenir
d'un rapprochement partiel vers ce que le marché sait déjà, pas d'un
angle mort distinct du marché.

### Partie 7 — Vérification temporelle

Contrainte respectée par construction et vérifiée par assertion (pas par
hypothèse) : les prédictions xG ont été calculées avec exactement les
mêmes constantes que E1 (`DECISION_OFFSET_HOURS=2.0`,
`MIN_TRAIN_MATCHES=10`) et le même mécanisme `real_data_walk_forward`
inchangé ; le `decision_time` recalculé ici a été comparé, match par
match, à celui déjà stocké dans le dataset E1 — identité stricte vérifiée
sans exception (le script se serait arrêté sinon). Aucune nouvelle
hypothèse temporelle introduite.

### Partie 8 — Data snooping

Cette analyse est directement motivée par le résultat SIGNAL NÉGATIF
d'E1 — elle est donc diagnostique et exploratoire par construction,
documentée comme telle. Aucune conclusion de rentabilité n'est tirée d'un
sous-groupe (quintile, décile, championnat, saison) découvert pendant
cette analyse — en particulier, la partie 2 caractérise explicitement le
biais sans jamais chercher ni retenir un sous-groupe rentable.

### Limites méthodologiques

- Le bootstrap utilisé (parties 4, 5-6) est un rééchantillonnage i.i.d.,
  pas un bootstrap par blocs temporels — même réserve que E1.
- La corrélation des erreurs (partie 5-6) est une mesure de
  **chevauchement**, pas une preuve causale que xG et marché « voient la
  même chose » pour la même raison — une corrélation élevée reste
  compatible avec des mécanismes différents produisant des erreurs
  corrélées. C'est un indice fort, pas une démonstration formelle.
  L'absence de signal en partie 4 (test dédié, validé sur données
  synthétiques) est un résultat sur `poisson_simple` spécifiquement, pas
  directement sur xG (testé séparément en parties 5-6 via une approche
  différente, la corrélation d'erreurs).
- Les quintiles/déciles ne couvrent que la dimension « force du favori » /
  « niveau de probabilité » — d'autres dimensions (calendrier, forme
  récente, etc., section E) n'ont pas été explorées ici, hors périmètre
  de ce diagnostic.

### Réponses aux trois questions posées

1. **Où et pourquoi `poisson_simple` est-il inférieur au marché ?**
   Partout et de façon diffuse plutôt que localisée : sa calibration est
   3 à 9 fois pire que celle du marché sur les trois issues, sur tous les
   championnats et les deux saisons sans exception, avec un biais
   irrégulier (tantôt sur-confiant, tantôt sous-confiant selon la
   tranche de probabilité) plutôt qu'un décalage directionnel simple. Le
   désavantage en Brier est présent dans les cinq quintiles de force du
   favori (0.033 à 0.062), sans zone où `poisson_simple` égalerait le
   marché — sauf au niveau du match individuel, où `poisson_simple` fait
   en réalité mieux que le marché sur 35.5 % des cas (hétérogénéité
   réelle, non exploitable ex ante faute de règle pour l'identifier à
   l'avance).
2. **Le désaccord `poisson_simple`/marché contient-il encore une
   information indépendante apparente ?** Non, sur ce corpus, pour
   aucune des trois issues (IC95 % couvrant largement 0 partout), avec
   une méthode validée pour détecter un signal injecté quand il existe
   réellement.
3. **Le xG semble-t-il contenir une information qui n'est PAS déjà
   capturée par B365 ?** **Non, pas dans cette analyse.** xG améliore
   `poisson_simple` (confirmant B3/B3.2/B3.3) mais reste inférieur au
   marché, et ses erreurs sont **plus** corrélées au marché que celles de
   `poisson_simple` — le signe inverse de ce qu'il faudrait observer pour
   soutenir l'hypothèse d'une information incrémentale exploitable.

**Conclusion, conformément au protocole** : la réponse à la question 3
étant négative, la pertinence de poursuivre les modèles xG **pour la
prédiction 1X2 face au marché** doit être sérieusement reconsidérée.
Aucune expérience économique dédiée au xG n'est engagée à ce stade.
Conformément à l'arrêt obligatoire du protocole, ce diagnostic ne débouche
sur aucune nouvelle stratégie, aucun nouveau modèle, aucune optimisation —
il sert uniquement à informer le choix de la prochaine hypothèse
scientifique.

---

## K. Diagnostic — calibration du total de buts et des marchés Over/Under

Diagnostic **pur** (aucune modification des modèles, aucune nouvelle
variante, aucune stratégie, aucune optimisation) : le système contient-il
déjà une information exploitable pour prédire le nombre total de buts et
les marchés Over/Under ? Réutilise sans modification les trois modèles
déjà figés produisant une matrice de score complète —
`PoissonModel(use_team_hfa=False)` (poisson_simple), `DixonColesModel
(use_team_hfa=False)` (B1) et `XGModel` (B3) — sur l'intégralité du
corpus réel (3 championnats × 2 saisons), avec les **mêmes contraintes
point-in-time** que partout ailleurs dans le projet
(`DECISION_OFFSET_HOURS=2.0`, `MIN_TRAIN_MATCHES=10`, constantes
réutilisées telles quelles depuis `economic_dataset.py`).
`scripts/run_stage8_diagnostic_total_goals_over_under.py`.

**Aucune comparaison au marché** : l'audit préalable des données de
marché (section correspondante) a confirmé qu'**aucune cote Over/Under
n'existe dans le corpus** (seul le 1X2 Bet365 est disponible) — ce
diagnostic mesure donc la calibration des modèles **contre le résultat
réel uniquement**, jamais contre un marché, conformément à la demande
explicite de ne pas chercher à battre le marché.

Couverture : 2072/2132 matchs pour `poisson_simple`/`dixon_coles`,
2056/2132 pour `xg_model` (même mécanisme d'exclusion par historique
insuffisant que partout ailleurs).

### Buts totaux attendus vs observés (biais global)

| Modèle | E[buts totaux] moyen prédit | Moyenne réelle observée | Biais |
|---|---|---|---|
| `poisson_simple` | 3.1033 | 2.7922 | **+0.3002** |
| `dixon_coles` | 3.1033 | 2.7922 | **+0.3002** |
| `xg_model` | 3.4143 | 2.7922 | **+0.6113** |

**Les trois modèles surestiment systématiquement le nombre total de buts**,
sans exception. `poisson_simple` et `dixon_coles` ont un biais identique
(attendu : la correction Dixon-Coles ne modifie que les quatre cellules
bas-score, dont la somme des probabilités — donc l'espérance globale — est
préservée par construction, voir `apply_dixon_coles_correction`, qui
renormalise sur l'ensemble de la matrice). `xg_model` surestime **deux
fois plus** que les deux autres.

### Calibration de la distribution complète (masse prédite moyenne vs fréquence observée)

| Total de buts | `poisson_simple` (écart) | `dixon_coles` (écart) | `xg_model` (écart) |
|---|---|---|---|
| 0 | +0.0154 | +0.0207 | -0.0138 |
| 1 | -0.0140 | -0.0246 | -0.0441 |
| 2 | -0.0408 | -0.0355 | -0.0538 |
| 3 | -0.0340 | -0.0340 | -0.0276 |
| 4 | +0.0025 | +0.0025 | +0.0228 |
| 5 | +0.0165 | +0.0165 | +0.0358 |
| **6+** | **+0.0544** | **+0.0544** | **+0.0806** |

Le biais global de la partie précédente s'explique très majoritairement
par une **surestimation de la queue haute (6 buts ou plus)** : les trois
modèles prédisent une masse de probabilité 2 à 3 fois supérieure à ce qui
est réellement observé sur cette tranche (6.3 % observé, contre 11.8 % à
14.4 % prédit selon le modèle), au prix d'une légère sous-estimation des
totaux « normaux » (2-3 buts, la tranche la plus fréquente en réalité).
`xg_model` est systématiquement le plus déséquilibré des trois sur cette
dimension (écart le plus grand sur presque toutes les tranches).

### Calibration Over/Under (global, seuils 1.5 / 2.5 / 3.5 — standards, non optimisés)

| Modèle | Seuil | Brier | log loss | taux over observé | p(over) prédite moyenne | erreur de calibration pondérée |
|---|---|---|---|---|---|---|
| `poisson_simple` | 1.5 | 0.1892 | 0.7394 | 0.779 | 0.777 | 0.0712 |
| `poisson_simple` | 2.5 | 0.2693 | 0.8397 | 0.533 | 0.573 | 0.1162 |
| `poisson_simple` | 3.5 | 0.2342 | 0.7520 | 0.300 | 0.374 | 0.1233 |
| `dixon_coles` | 1.5 | 0.1888 | 0.7382 | 0.779 | 0.783 | 0.0736 |
| `dixon_coles` | 2.5 | 0.2693 | 0.8397 | 0.533 | 0.573 | 0.1162 |
| `dixon_coles` | 3.5 | 0.2342 | 0.7520 | 0.300 | 0.374 | 0.1233 |
| `xg_model` | 1.5 | 0.1770 | 0.5509 | 0.778 | 0.836 | 0.0683 |
| `xg_model` | 2.5 | 0.2644 | 0.7312 | 0.534 | 0.646 | 0.1238 |
| `xg_model` | 3.5 | 0.2335 | 0.6613 | 0.300 | 0.439 | 0.1440 |

**Dixon-Coles est mathématiquement identique à `poisson_simple` sur les
seuils 2.5 et 3.5** (chiffres strictement égaux) : sa correction ne
touche que les cellules de score (0-0, 1-0, 0-1, 1-1), toutes de total
≤ 2, donc entièrement dans la zone « under » de ces deux seuils — ce
n'est pas un résultat numérique surprenant, c'est une conséquence directe
et attendue de la construction du modèle (voir `dixon_coles.py`). Un
écart minime apparaît sur le seuil 1.5 (la cellule 1-1, de total 2, est
« over » à ce seuil et reçoit une correction tau).

`xg_model` a un Brier et un log loss **légèrement meilleurs** que
`poisson_simple`/`dixon_coles` sur les trois seuils, mais une **erreur de
calibration pondérée systématiquement égale ou pire**, et une
sur-prédiction de p(over) nettement plus marquée (ex. Over 1.5 : 0.836
prédit contre 0.778 observé, un écart de +0.058, contre +0.004 seulement
pour `poisson_simple`). Ce n'est pas une contradiction : `xg_model`
produit des probabilités plus **extrêmes** (proches de 0 ou 1), ce qui
peut réduire le log loss/Brier moyens sur les cas où cette confiance est
correcte, tout en dégradant la calibration moyenne — deux mesures qui
répondent à des questions différentes, cohérent avec le biais
d'espérance de buts déjà 2× plus élevé observé ci-dessus pour ce modèle.

**Par championnat et par saison** (mêmes tableaux détaillés dans la sortie
du script) : le même schéma se répète sans exception - Dixon-Coles reste
strictement identique à `poisson_simple` sur Over 2.5/3.5 sur les 3
championnats et les 2 saisons ; `xg_model` a généralement une erreur de
calibration égale ou pire que `poisson_simple` sur Over 2.5/3.5, sauf en
Premier League où il fait légèrement mieux sur les deux seuils (seule
exception notée, non retenue comme sous-groupe exploitable conformément à
la consigne).

### Limites méthodologiques

- Diagnostic **modèle uniquement** : en l'absence de cotes Over/Under
  dans le corpus, aucune conclusion de rentabilité ni de comparaison au
  marché n'est possible ni recherchée ici.
- Les seuils 1.5/2.5/3.5 sont des seuils standards documentés, choisis
  avant tout calcul — aucune recherche de seuil optimal.
- L'erreur de calibration pondérée utilise `reliability_bins` (10
  tranches, réutilisé sans modification) — les tranches à faible effectif
  par saison/championnat restent moins fiables individuellement (nombre
  de tranches effectivement utilisées rapporté dans la sortie du script).

### Réponse à la question posée

**Les modèles existants ne sont pas dénués d'information sur le total de
buts** (ils distinguent des matchs à faible/forte espérance de buts, et
leurs probabilités Over/Under s'écartent sensiblement de valeurs
non-informatives), **mais ils sont mesurablement mal calibrés dans un sens
précis et systématique : une surestimation du nombre total de buts,
concentrée dans la queue haute de la distribution (6 buts ou plus,
surestimée d'un facteur 2 à 3), présente sur les trois modèles testés,
tous les championnats et les deux saisons, sans exception.** La correction
Dixon-Coles n'apporte, par construction mathématique, aucune amélioration
sur les seuils Over/Under usuels (2.5/3.5) ; le modèle xG, bien que
produisant un Brier/log loss légèrement meilleurs sur ces seuils, aggrave
en réalité le biais d'espérance de buts (+0.61 contre +0.30) et n'améliore
pas la calibration pondérée. Aucune conclusion de rentabilité n'est
tirée : ce diagnostic caractérise un défaut de calibration mesurable, pas
une opportunité de marché (qui resterait à établir face à de vraies cotes
Over/Under, non disponibles dans ce corpus). Conformément au protocole,
aucun modèle n'est modifié et aucune nouvelle variante n'est testée à ce
stade.

---

## L. Diagnostic — calibration par tranche des probabilités Over/Under (poisson_simple, xg_model)

Diagnostic **pur**, prolongeant directement la section K : aucun nouveau
modèle prédictif, aucune modification des modèles existants, aucune
nouvelle donnée, aucune comparaison au marché, aucune optimisation de
seuil. Réutilise **sans recalcul** les probabilités Over 1.5/2.5/3.5 déjà
produites par `run_stage8_diagnostic_total_goals_over_under.build_total_goals_dataframe()`
(mêmes 2132 matchs, mêmes contraintes point-in-time, `poisson_simple` et
`xg_model` uniquement, comme demandé).

### Inspection préalable des outils de calibration déjà présents

Avant toute implémentation, inventaire du dépôt (`calibration_engine/`,
`football_model/`) :

- `calibration_engine.reliability.reliability_bins` — **réutilisée sans
  modification** pour produire la table complète par tranche (10 tranches),
  au lieu du seul résumé pondéré déjà calculé en section K.
- `football_model.elo.EloModel` contient déjà une forme de « calibration
  isotonique par tranches » (bins empiriques appliqués en lookup) —
  **précédent étudié mais délibérément NON réutilisé** : l'appliquer aux
  probabilités Over/Under reviendrait à construire un nouveau modèle
  recalibré, explicitement exclu par la consigne. Ce diagnostic reste
  purement analytique.
- **Aucune décomposition de Brier** (fiabilité/résolution/incertitude, Murphy
  1973) et **aucune métrique de discrimination** (monotonicité) n'existaient
  dans le dépôt avant ce diagnostic — ajoutées comme outils de **mesure
  purs** (`calibration_engine/decomposition.py`), même statut que
  `goodness_of_fit.py`/`low_score_metrics.py` déjà présents : analysent un
  ensemble (probabilité, résultat) déjà produit, ne génèrent et ne
  modifient aucune prédiction. Décomposition : `Brier = Fiabilité −
  Résolution + Incertitude` — la résolution (pouvoir de discrimination)
  est, par construction mathématique, **indépendante de toute
  recalibration monotone** (celle-ci ne peut modifier que la fiabilité) :
  c'est l'outil exact requis pour répondre à « une calibration ex-ante
  pourrait-elle corriger le biais sans détruire la discrimination ? ».

### Résultat central : un skill négatif par rapport à la climatologie, sur les 6 combinaisons testées

| Modèle | Seuil | Fiabilité | Résolution | Incertitude | Skill vs climatologie |
|---|---|---|---|---|---|
| `poisson_simple` | 1.5 | 0.0183 | 0.0017 | 0.1722 | **-0.0963** |
| `poisson_simple` | 2.5 | 0.0216 | 0.0017 | 0.2489 | **-0.0798** |
| `poisson_simple` | 3.5 | 0.0241 | 0.0017 | 0.2101 | **-0.1067** |
| `xg_model` | 1.5 | 0.0067 | 0.0022 | 0.1726 | **-0.0262** |
| `xg_model` | 2.5 | 0.0196 | 0.0043 | 0.2488 | **-0.0616** |
| `xg_model` | 3.5 | 0.0267 | 0.0035 | 0.2100 | **-0.1106** |

Sur les six combinaisons (2 modèles × 3 seuils), le **skill vs climatologie
est négatif sans exception** : la fiabilité (biais) dépasse systématiquement
la résolution (discrimination). Concrètement, en termes de score de Brier
« groupé », prédire *toujours* le taux de base observé (climatologie
constante) ferait **mieux** que les probabilités actuelles de
`poisson_simple`/`xg_model` sur Over/Under — pas parce qu'elles ne
discriminent rien (la résolution est positive partout, un vrai signal
existe), mais parce que le biais de calibration l'emporte largement sur ce
signal. `xg_model` a un skill un peu moins négatif que `poisson_simple`
sur Over 1.5/2.5 (plus de résolution, ex. 0.0043 contre 0.0017 sur Over
2.5) mais reste négatif partout, et son biais est généralement plus
prononcé en valeur absolue sur les tranches hautes (voir tableau suivant).

### Biais par tranche de probabilité prédite

Le biais (`prédit − observé`) suit un **schéma quasi systématique en
« S »** sur les six tables (10 tranches chacune, détail complet dans la
sortie du script) : **négatif** dans les tranches basses (le modèle
sous-estime la probabilité, la fréquence réelle est plus haute que prédit)
et **positif, souvent nettement plus large en amplitude**, dans les
tranches hautes (le modèle est trop confiant). Exemples représentatifs :

- `poisson_simple`, Over 2.5 : tranche [0.0-0.1] biais -0.464 (n=42) →
  tranche [0.9-1.0] biais +0.273 (n=51).
- `poisson_simple`, Over 3.5 : tranche [0.0-0.1] biais -0.203 (n=110) →
  tranche [0.9-1.0] biais +0.581 (n=11, effectif faible).
- `xg_model`, Over 3.5 : tranche [0.1-0.2] biais -0.002 (n=72) → tranche
  [0.7-0.8] biais +0.387 (n=66).

C'est la signature classique d'une distribution de probabilités prédites
**trop dispersée** par rapport à la vraie variabilité du phénomène
(« overconfidence ») — exactement le type de biais qu'une recalibration
monotone standard (Platt scaling, régression isotonique) est conçue pour
corriger. Les tranches extrêmes (0.9-1.0 avec n=11 à n=51 selon le cas)
restent peu peuplées — le biais y est directionnellement cohérent avec le
reste de la table mais numériquement moins fiable.

### Monotonicité (condition de plausibilité d'une recalibration monotone)

| Modèle | Seuil | Violations / transitions | Taux |
|---|---|---|---|
| `poisson_simple` | 1.5 | 4/9 | 0.444 |
| `poisson_simple` | 2.5 | 2/9 | 0.222 |
| `poisson_simple` | 3.5 | 2/9 | 0.222 |
| `xg_model` | 1.5 | 3/8 | 0.375 |
| `xg_model` | 2.5 | 2/9 | 0.222 |
| `xg_model` | 3.5 | 2/9 | 0.222 |

Les violations de monotonicité (la fréquence observée qui redescend d'une
tranche à la tranche suivante, plus haute) sont **concentrées dans les
tranches basses et peu peuplées** (Over 1.5, où la plupart des matchs
dépassent déjà 50 % de probabilité prédite, laissant les tranches basses
avec n=13 à 38 seulement) — cohérent avec du bruit d'échantillonnage
plutôt qu'une non-monotonicité structurelle. Sur Over 2.5/3.5, mieux
peuplés sur toute la plage, le taux de violation descend à 22 %, et les
tranches à fort effectif (n>100) suivent une progression globalement
croissante. Cette lecture reste qualitative : les violations résiduelles
dans les tranches peu peuplées ne permettent pas d'affirmer une
monotonicité parfaite, seulement une monotonicité plausible sur la partie
bien échantillonnée de la distribution.

### Stabilité du biais par championnat et par saison

Le biais change de comportement selon le seuil :
- **Over 2.5 et 3.5** : biais **positif dans presque tous les
  découpages**, pour les deux modèles (ex. `poisson_simple` Over 2.5 :
  Liga +0.060, Ligue 1 +0.065, Premier League -0.002 — seule quasi-exception ;
  `xg_model` Over 2.5 : +0.082 à +0.135 partout, sans aucune exception).
  Un biais stable en direction est une condition favorable à la
  généralisation d'une recalibration.
- **Over 1.5** : le signe du biais de `poisson_simple` **s'inverse** selon
  le championnat (Liga/Ligue 1 positifs, Premier League négatif à -0.034)
  et selon la saison (2024/25 négatif, 2025/26 positif) — une
  recalibration globale unique serait ici moins susceptible de bien
  généraliser à tous les sous-groupes. `xg_model`, en revanche, reste
  positif sur Over 1.5 dans tous les découpages (plus stable que
  `poisson_simple` à ce seuil précis).

### Limites méthodologiques

- Analyse **purement diagnostique** : aucune recalibration n'a été
  effectivement ajustée ni appliquée — cela constituerait un nouveau
  modèle, explicitement exclu par la consigne. Les indicateurs de
  résolution/monotonicité renseignent sur la **plausibilité** qu'une
  recalibration future puisse réduire le biais sans dégrader la
  discrimination, pas sur une démonstration qu'elle fonctionnerait
  effectivement hors échantillon (une recalibration ajustée sur ce même
  échantillon devrait, par construction, être elle-même validée sur un
  échantillon disjoint pour éviter le surajustement — non fait ici,
  hors périmètre).
- La décomposition de Brier utilise le score « groupé » (probabilité
  moyenne par tranche) — l'écart avec le Brier « brut » (probabilités
  individuelles) est rapporté explicitement (`grouping_error`,
  systématiquement < 0.002 en valeur absolue ici) plutôt que masqué.
- Les tranches extrêmes de faible effectif (n<20, notamment sur Over 3.5)
  restent des estimations bruitées du biais réel à ces niveaux de
  probabilité.

### Réponse à la question posée

**Oui, un biais de calibration précis et récurrent est identifié** : un
schéma en « S » (sous-confiance en zone basse, sur-confiance marquée en
zone haute), présent sur les six combinaisons modèle × seuil testées,
suffisamment large pour que le **skill par rapport à une simple
climatologie constante soit négatif partout** — le biais de calibration
domine actuellement le pouvoir de discrimination réel (résolution
positive mais faible : 0.0017 à 0.0043 contre une fiabilité de 0.007 à
0.027). Puisque la résolution est mathématiquement indépendante de toute
recalibration monotone (celle-ci ne peut agir que sur la fiabilité), une
recalibration ex-ante **pourrait en principe** réduire fortement le biais
sans dégrader la discrimination déjà mesurée — cette conclusion est
renforcée par la relative stabilité du biais sur Over 2.5/3.5 (positif
presque partout) mais nuancée sur Over 1.5, où le signe du biais
s'inverse selon le championnat et la saison pour `poisson_simple`
spécifiquement. Ce diagnostic caractérise la plausibilité d'une telle
correction ; il ne la met pas en œuvre ni ne démontre son efficacité hors
échantillon — conformément au protocole, aucune recalibration n'est
implémentée à ce stade.

---

## M. Expérience E2 — recalibration isotonique des probabilités Over/Under

Prolonge directement la section L : une recalibration apprise
**uniquement sur le passé** améliore-t-elle les probabilités Over/Under
sur des matchs **futurs, hors échantillon, sans fuite** ? `poisson_simple`
et `xg_model` restent **strictement inchangés** — seule une couche de
recalibration post-hoc est testée, appliquée à leurs probabilités déjà
produites. `scripts/run_stage10_over_under_recalibration.py`.

### Inspection préalable et choix de la méthode (avant implémentation)

Inventaire des mécanismes de calibration déjà présents : `reliability_bins`
et `brier_decomposition` (section L) réutilisés sans modification ;
`football_model.elo.EloModel` (calibration empirique par tranches, sans
contrainte de monotonicité) étudié mais **non réutilisé** — l'appliquer ici
reviendrait à construire un nouveau modèle. **Une seule méthode retenue** :
la **régression isotonique** (`scipy.optimize.isotonic_regression`, PAVA —
déjà une dépendance du projet, aucune nouvelle dépendance), choisie et
justifiée *avant* tout calcul pour trois raisons : (1) monotone par
construction, donc ne peut pas dégrader le pouvoir de discrimination au
sens du **rang** des probabilités ; (2) aucune forme paramétrique
supposée, adaptée au biais en « S » déjà documenté (contrairement à un
Platt scaling, qui suppose une sigmoïde) ; (3) aucun hyperparamètre à
ajuster — PAVA est déterministe une fois les données de calibration
fixées. Aucune variante, aucune autre méthode testée, aucune sélection
fondée sur le résultat.

### Protocole

Walk-forward strict, **même découpage 40/30/30 que B1/A2/B2/B3.3** (rodage
jeté, calibration, test), même corpus (3 championnats × 2 saisons). La
courbe isotonique est ajustée **uniquement sur la calibration** (n=640
pooled) et évaluée **uniquement sur le test** (n=640 pooled), jamais
l'inverse — vérifié par des tests anti-fuite dédiés
(`tests/leakage/test_over_under_recalibration_point_in_time.py`) montrant
que la courbe ajustée est rigoureusement indépendante du contenu du test.
Une courbe séparée par (modèle, seuil).

### Résultats (TEST uniquement, n=640 par combinaison)

| Modèle | Seuil | Brier avant→après | log loss avant→après | biais avant→après | fiabilité avant→après | résolution avant→après | IC95% (diff Brier) | Verdict |
|---|---|---|---|---|---|---|---|---|
| `poisson_simple` | 1.5 | 0.1892→0.1866 | 0.574→0.561 | +0.048→+0.041 | 0.0042→0.0018 | 0.0022→0.0021 | [-0.0060,+0.0007] p=0.122 | **ABSENCE DE PREUVE** |
| `poisson_simple` | 2.5 | 0.2527→0.2467 | 0.700→0.686 | +0.067→+0.015 | 0.0092→0.0008 | 0.0046→0.0017 | [-0.0144,+0.0021] p=0.154 | **ABSENCE DE PREUVE** |
| `poisson_simple` | 3.5 | 0.2153→0.2053 | 0.622→0.639 | +0.087→+0.017 | 0.0144→0.0016 | 0.0059→0.0019 | [-0.0192,-0.0007] p=0.035 | **AMÉLIORATION DÉMONTRÉE** |
| `xg_model` | 1.5 | 0.1932→0.1881 | 0.591→0.643 | +0.095→+0.043 | 0.0097→0.0049 | 0.0025→0.0010 | [-0.0091,-0.0012] p=0.012 | **AMÉLIORATION DÉMONTRÉE** |
| `xg_model` | 2.5 | 0.2643→0.2456 | 0.727→0.684 | +0.136→+0.020 | 0.0203→0.0013 | 0.0058→0.0056 | [-0.0285,-0.0090] p<0.0001 | **AMÉLIORATION DÉMONTRÉE** |
| `xg_model` | 3.5 | 0.2297→0.2052 | 0.651→0.607 | +0.158→+0.011 | 0.0278→0.0028 | 0.0029→0.0031 | [-0.0360,-0.0127] p<0.0001 | **AMÉLIORATION DÉMONTRÉE** |

**4 des 6 combinaisons montrent une amélioration statistiquement
démontrée** (les 3 seuils pour `xg_model`, et Over 3.5 pour
`poisson_simple`) ; les 2 restantes (`poisson_simple` Over 1.5/2.5)
montrent un diff négatif (favorable) mais une absence de preuve — jamais
une dégradation démontrée sur aucune des 6 combinaisons. Le biais moyen
est réduit massivement dans tous les cas (ex. `xg_model` Over 3.5 :
+0.158 → +0.011), cohérent avec la chute de la fiabilité (le terme de
biais de la décomposition de Brier) sur toutes les combinaisons.

### Deux nuances honnêtes, non lissées

1. **Le log loss ne s'améliore pas toujours alors que le Brier
   s'améliore** (`poisson_simple` Over 3.5 : 0.622→0.639 ; `xg_model`
   Over 1.5 : 0.591→0.643). Cause identifiée dans les tables de
   calibration détaillées : la fonction isotonique produit un escalier
   avec des paliers proches de 0 ou 1 dans certaines tranches peu
   peuplées du test, et le log loss pénalise beaucoup plus fortement
   qu'un Brier une prédiction extrême qui se révèle fausse. Le protocole
   demandait Brier ET log loss avant/après explicitement : les deux sont
   rapportés sans en écarter un parce qu'il est défavorable.
2. **La « résolution » mesurée diminue parfois après recalibration**,
   notamment pour `poisson_simple` (Over 2.5 : 0.0046→0.0017 ; Over 3.5 :
   0.0059→0.0019) — alors que la section L avait établi que la résolution
   est mathématiquement **indépendante du rang** sous une transformation
   monotone. Ce n'est pas une contradiction, mais une précision
   importante : cette garantie porte sur le **rang** des prédictions, pas
   sur la valeur mesurée par `brier_decomposition`, qui rebinne les
   probabilités **transformées** en tranches de largeur fixe. Or PAVA,
   ajusté sur un ensemble de calibration modeste (n=640) et un signal
   bruité, produit ici une fonction très **aplatie** (paliers larges,
   ex. 630/640 points du test regroupés dans une seule tranche
   [0.5-0.6] pour `poisson_simple` Over 2.5) : le rang exact est
   préservé, mais la **variété** des valeurs prédites s'effondre, ce qui
   réduit la résolution telle que mesurée ici. `xg_model` pool beaucoup
   moins (tables « après » nettement plus étalées) et voit sa résolution
   globalement préservée (0.0058→0.0056, 0.0029→0.0031) ou seulement
   partiellement réduite (0.0025→0.0010) — cohérent avec un signal moins
   bruité en calibration pour ce modèle. Le gain de Brier reste net dans
   les deux cas car la chute de fiabilité dépasse largement la baisse de
   résolution.

### Limites méthodologiques

- Un seul découpage 40/30/30, une seule graine de bootstrap (`seed=0`,
  10 000 rééchantillonnages) — pas de répétition sur plusieurs
  découpages temporels alternatifs (hors périmètre, aucune variante
  n'a été testée conformément au protocole).
- n=640 par combinaison (test) reste modeste — cohérent avec le fait que
  seuls 2 des 6 verdicts individuels de `poisson_simple` atteignent la
  significativité malgré un diff systématiquement favorable.
- Aucune conclusion de rentabilité : ce protocole ne compare à aucune
  cote de marché (aucune cote Over/Under réelle disponible, comme établi
  aux sections K/L) — seule la fiabilité probabiliste face au résultat
  réel est évaluée, conformément à l'objectif énoncé (« obtenir des
  probabilités de buts fiables », pas battre le marché).

### Réponse à la question posée

**Oui, sur ce corpus et avec cette méthode unique, une recalibration
apprise uniquement sur le passé améliore mesurablement les probabilités
Over/Under de `xg_model` sur les trois seuils (démontré), et celles de
`poisson_simple` sur Over 3.5 (démontré) — jamais une dégradation
démontrée sur aucune des six combinaisons.** `poisson_simple` sur Over
1.5/2.5 reste une amélioration non démontrée (diff favorable, IC95%
couvrant 0), pas un échec de la méthode. `poisson_simple` et `xg_model`
restent inchangés ; cette expérience caractérise uniquement une couche de
recalibration séparée, jamais intégrée au système de prédiction en
production à ce stade. Conformément au protocole, aucune autre méthode,
aucun hyperparamètre, aucune comparaison au marché n'ont été testés.

---

## N. Expérience E3 — validation de la fiabilité hors échantillon des probabilités calibrées

Question précise : **quand le système annonce une probabilité calibrée
d'Over, cette probabilité correspond-elle réellement à la fréquence
observée sur des matchs futurs ?** Aucune comparaison au bookmaker, aucun
ROI, aucune sélection de pari, aucun seuil de cote, aucune optimisation.
`poisson_simple` et `xg_model` restent inchangés.

**Aucun recalcul** : ce rapport réutilise **exactement** le pipeline déjà
testé d'E2 (même découpage 40/30/30, même courbe isotonique ajustée
uniquement sur la calibration n=640, même test n=640, même bootstrap
apparié) — vérifié par les mêmes chiffres globaux que la section M
(Brier/log loss/biais/résolution/IC95% identiques). Deux ajouts,
strictement des mises en forme de données déjà calculées : la table de
calibration **complète** (10 tranches fixes, y compris les tranches
vides, jamais déplacées) et une lecture pratique agrégée des zones
50-60 % / 60-70 % / 70-80 % / 80 %+ (fusion pondérée de [0.8-0.9] et
[0.9-1.0] uniquement) sur les probabilités **calibrées**.
`scripts/run_stage11_e3_reliability_validation.py`.

### Lecture pratique — Over 2.5 (priorité)

| Modèle | Zone | n | Annoncé | Observé | Écart |
|---|---|---|---|---|---|
| `poisson_simple` | 50-60 % | 630 | 53.6 % | 52.2 % | 1.4 pt |
| `poisson_simple` | 60-70 % | 0 | — | — | — |
| `poisson_simple` | 70-80 % | 2 | 75.0 % | 100 % | n trop faible |
| `poisson_simple` | 80 %+ | 0 | — | — | — |
| `xg_model` | 50-60 % | 387 | 57.0 % | 55.3 % | 1.7 pt |
| `xg_model` | 60-70 % | 33 | 61.9 % | 66.7 % | 4.8 pt |
| `xg_model` | 70-80 % | 2 | 72.8 % | 100 % | n trop faible |
| `xg_model` | 80 %+ | 0 | — | — | — |

*« Lorsque `xg_model` calibré annonçait environ 57 % d'Over 2.5 (n=387,
zone la plus peuplée), l'Over 2.5 s'est produit 55.3 % du temps — un écart
de 1.7 point. »* C'est le résultat le plus directement lisible du
protocole demandé.

**Nuance importante pour `poisson_simple`** : sa zone 50-60 % concentre
**630 des 640 matchs de test** (98 %) — un seul palier isotonique domine
presque tout le test (déjà signalé en section M : PAVA a fortement aplati
la courbe pour cette combinaison). La fiabilité y est bonne (écart
1.4 pt), mais elle porte sur une annonce **presque identique pour
n'importe quel match** — la question posée (« correspond-elle à la
fréquence observée ? ») reçoit une réponse positive, mais avec très peu
de variété de probabilités annoncées pour la juger. `xg_model` conserve
davantage de paliers distincts (387/33/2/0 répartis sur plusieurs zones)
et reste bien calibré sur chacun.

### Lecture pratique — Over 1.5 et Over 3.5

| Modèle | Seuil | 50-60 % | 60-70 % | 70-80 % | 80 %+ |
|---|---|---|---|---|---|
| `poisson_simple` | 1.5 | n=0 | n=39, 69.5→64.1 % | n=200, 76.9→71.0 % | n=401, 81.6→78.6 % |
| `xg_model` | 1.5 | n=10, 60.0→70.0 % | n=3, 63.4→100 % | n=305, 76.2→72.8 % | n=321, 83.7→77.6 % |
| `poisson_simple` | 3.5 | n=0 | n=0 | n=0 | n=0 |
| `xg_model` | 3.5 | n=0 | n=0 | n=0 | n=0 |

**Over 3.5 : les quatre zones sont vides pour les deux modèles.** Après
recalibration, aucune probabilité calibrée d'Over 3.5 n'atteint 50 % sur
le corpus de test — Over 3.5 est un événement suffisamment rare (~30 %
observé globalement, sections K/L) pour que le modèle calibré ne se
déclare jamais franchement confiant dans ce sens. La question centrale
d'E3 **ne peut donc pas être vérifiée dans ces zones pour Over 3.5** avec
ce corpus — un résultat honnête à rapporter, pas une omission. Sur Over
1.5, un résidu de biais subsiste même après calibration dans la zone
80 %+ (`poisson_simple` : 81.6→78.6 %, écart 3.0 pt ; `xg_model` :
83.7→77.6 %, écart 6.1 pt) — la calibration réduit le biais sans
l'annuler complètement dans cette zone, cohérent avec les tables
complètes ci-dessous.

### Tables de calibration complètes (10 tranches fixes, y compris tranches vides)

Le détail complet (avant ET après, les 10 tranches, tranches vides
conservées avec leur taille plutôt que déplacées) est dans la sortie du
script — extraits significatifs :

- `poisson_simple` Over 3.5, après calibration : toute la masse tombe
  dans 4 tranches basses (`[0.0-0.1]` n=7, `[0.1-0.2]` n=32, `[0.2-0.3]`
  n=224, `[0.3-0.4]` n=377) — cohérent avec l'absence totale de matchs
  dans les zones 50 %+ ci-dessus.
- `xg_model` Over 2.5, après calibration : masse concentrée sur
  `[0.4-0.5]` (n=215) et `[0.5-0.6]` (n=387), avec un résidu bien réparti
  sur les tranches `[0.6-0.7]` (n=33) et `[0.7-0.8]` (n=2) — plus étalé
  que `poisson_simple` sur la même paire (modèle, seuil).

### Métriques globales (section 5 — déjà définies en E2, aucune nouvelle)

| Modèle | Seuil | Brier avant→après | log loss avant→après | biais moyen absolu avant→après | résolution avant→après |
|---|---|---|---|---|---|
| `poisson_simple` | 1.5 | 0.1892→0.1866 | 0.574→0.561 | 0.0481→0.0409 | 0.0022→0.0021 |
| `poisson_simple` | 2.5 | 0.2527→0.2467 | 0.700→0.686 | 0.0667→0.0151 | 0.0046→0.0017 |
| `poisson_simple` | 3.5 | 0.2153→0.2053 | 0.622→0.639 | 0.0870→0.0169 | 0.0059→0.0019 |
| `xg_model` | 1.5 | 0.1932→0.1881 | 0.591→0.643 | 0.0950→0.0425 | 0.0025→0.0010 |
| `xg_model` | 2.5 | 0.2643→0.2456 | 0.727→0.684 | 0.1363→0.0203 | 0.0058→0.0056 |
| `xg_model` | 3.5 | 0.2297→0.2052 | 0.651→0.607 | 0.1575→0.0107 | 0.0029→0.0031 |

Chiffres strictement identiques à la section M (même pipeline, même
segment de test, aucun recalcul) — vérifié comme non-régression.

### Incertitude (section 6)

IC95% bootstrap apparié (`paired_bootstrap_test`, réutilisé sans
modification) sur `diff = Brier_après − Brier_avant`, exactement comme en
section M : **AMÉLIORATION STATISTIQUEMENT DÉMONTRÉE** pour `xg_model`
sur les 3 seuils et pour `poisson_simple` sur Over 3.5 ; **ABSENCE DE
PREUVE D'AMÉLIORATION** (jamais dégradation) pour `poisson_simple` sur
Over 1.5/2.5 — chiffres identiques à la section M.

### Limites méthodologiques

- Les zones 60-70 %/70-80 % sont parfois trop peu peuplées (n=2, n=3) pour
  être lues de façon fiable — rapportées avec leur taille plutôt que
  masquées ou fusionnées arbitrairement, conformément à la consigne.
- La bonne fiabilité apparente de `poisson_simple` Over 2.5 (zone
  50-60 %) reflète en grande partie une concentration extrême de la
  courbe isotonique (98 % du test dans une seule tranche), pas une
  calibration fine sur plusieurs niveaux de confiance — nuance déjà
  documentée en section M (perte de résolution mesurée).
- Over 3.5 ne peut pas être évalué dans les zones 50 %+ demandées, faute
  de matchs de test où le modèle calibré atteint ce niveau de confiance.

### Réponse à la question posée

**Oui, avec des nuances par seuil et par modèle.** Quand `xg_model`
calibré annonce une probabilité d'Over 2.5 (le marché prioritaire),
celle-ci correspond bien à la fréquence observée dans sa zone la plus
peuplée (57.0 % annoncé → 55.3 % observé, n=387) et reste raisonnablement
fiable sur les autres zones peuplées. `poisson_simple` calibré est
également bien calibré sur Over 2.5, mais avec une variété de
probabilités annoncées beaucoup plus faible (un seul palier dominant).
Sur Over 1.5, un résidu de biais subsiste dans la zone 80 %+ pour les
deux modèles, même après calibration. Sur Over 3.5, la question ne peut
pas être vérifiée dans les zones de confiance élevée (50 %+), le modèle
calibré n'y atteignant jamais ce niveau sur ce corpus. Aucune règle de
pari n'est créée à partir de ces résultats ; `poisson_simple` et
`xg_model` restent inchangés.

---

## O. Expérience E4 — discrimination de l'espérance totale de buts prédite

Question exacte : **lorsque le modèle prédit un total attendu de buts
plus élevé, les matchs produisent-ils effectivement davantage de buts ?**
Objectif : démontrer une **discrimination réelle**, pas une calibration
parfaite (une surestimation globale n'annule pas cette propriété).
`poisson_simple` et `xg_model` restent inchangés ; **aucune calibration
isotone n'est utilisée ici** — la variable étudiée est l'espérance
**brute** `expected_total_goals = λ_home + λ_away`, déjà calculée et
exposée par `run_stage8...build_total_goals_dataframe()` (colonnes
`{model}_lambda_plus_mu`), réutilisée sans recalcul. Même découpage
40/30/30 que B1/A2/B2/B3.3/E2/E3 (réutilisé via
`run_stage10...build_calibration_and_test_sets`) ; la calibration (30 %)
n'est ici utilisée pour rien (vérifié par test dédié — aucun ajustement
n'est nécessaire pour cette analyse), seul le TEST (n=640, 3 championnats
× 2 saisons) sert à l'évaluation. `scripts/run_stage12_e4_expected_goals_discrimination.py`.

### Tranches fixes — GLOBAL (analyse principale, section 4 du protocole)

| Tranche | `poisson_simple` n | prédit→observé | biais | `xg_model` n | prédit→observé | biais |
|---|---|---|---|---|---|---|
| <1.5 | 0 | — | — | 0 | — | — |
| 1.5-2.0 | 12 | 1.844→2.167 | +0.323 | 0 | — | — |
| 2.0-2.5 | 77 | 2.328→2.429 | +0.100 | 5 | 2.353→1.800 | -0.553 |
| 2.5-3.0 | 203 | 2.761→2.621 | -0.140 | 119 | 2.816→2.361 | -0.455 |
| 3.0-3.5 | 193 | 3.236→2.850 | -0.387 | 244 | 3.256→2.734 | -0.523 |
| 3.5+ | 155 | 3.905→3.039 | -0.866 | 272 | 3.899→2.974 | -0.924 |

**Sur les tranches suffisamment peuplées, le total réellement observé
augmente de façon monotone avec la tranche prédite, pour les deux
modèles** (`poisson_simple` : 2.167→2.429→2.621→2.850→3.039 ; `xg_model` :
2.361→2.734→2.974, en ignorant la tranche 2.0-2.5 à n=5 trop faible pour
être lue). Le biais suit un schéma différent selon le modèle :
`poisson_simple` passe d'une sous-estimation dans les tranches basses à
une surestimation croissante dans les tranches hautes (schéma
« en éventail », signature d'une dispersion prédite trop large — cohérent
avec la section L) ; `xg_model` surestime dans **toutes** les tranches,
avec un biais qui croît en valeur absolue avec le niveau prédit (décalage
plutôt qu'éventail).

### Quintiles de l'espérance prédite (section 5, complément)

| Quintile | `poisson_simple` prédit→observé | `xg_model` prédit→observé |
|---|---|---|
| Q1 | 2.354→2.523 | 2.804→2.344 |
| Q2 | 2.769→2.469 | 3.148→2.758 |
| Q3 | 3.062→2.789 | 3.405→2.719 |
| Q4 | 3.397→2.914 | 3.663→2.891 |
| Q5 | 3.980→3.102 | 4.183→3.086 |

**Relation monotone stricte : NON, pour les deux modèles** (une seule
inversion sur les quatre transitions dans chaque cas — `poisson_simple` :
Q1→Q2 ; `xg_model` : Q2→Q3 — les trois autres transitions sont
croissantes). Le résultat global reste net : Q5 est nettement au-dessus
de Q1 pour les deux modèles (`poisson_simple` : +0.579 ; `xg_model` :
+0.742), et l'analyse des tranches fixes ci-dessus (plus large, donc plus
stable) est monotone sans exception. La finesse des quintiles (128 matchs
chacun) rend une inversion locale isolée statistiquement plausible sans
remettre en cause la tendance d'ensemble.

### Corrélation, MAE, biais moyen (section 6) — GLOBAL

| Modèle | n | corrélation | MAE (IC95%) | biais moyen (IC95%) |
|---|---|---|---|---|
| `poisson_simple` | 640 | +0.164 | 1.381 [1.303, 1.460] | -0.353 [-0.482, -0.224] |
| `xg_model` | 640 | +0.160 | 1.481 [1.402, 1.560] | -0.681 [-0.809, -0.553] |

La décomposition de Brier (E2/E3) **ne s'applique pas ici** : elle
suppose une probabilité dans [0,1] et un résultat binaire, alors que
`expected_total_goals` est une estimation ponctuelle continue — la
corrélation en tient lieu comme mesure de discrimination pour une
variable continue (aucune métrique sophistiquée ajoutée). Les deux
corrélations sont **positives mais modestes** (~0.16), et l'IC95% du
biais moyen est entièrement négatif pour les deux modèles (surestimation
systématique confirmée avec certitude statistique, cohérent avec K/L). La
MAE (~1.4 but) reste large en valeur absolue — un rappel explicite que
discrimination et précision ponctuelle sont deux propriétés différentes :
le modèle sépare correctement les matchs à faible/fort total en moyenne,
mais son estimation ponctuelle individuelle reste grossière.

### Stabilité par championnat et par saison

| Portée | `poisson_simple` corr. | `xg_model` corr. |
|---|---|---|
| Liga | +0.252 | +0.239 |
| Ligue 1 | +0.186 | +0.175 |
| **Premier League** | **-0.024** | **+0.012** |
| 2024/25 | +0.241 | +0.194 |
| 2025/26 | +0.081 | +0.123 |

**Le signal n'est pas uniforme sur le corpus : la Premier League fait
exception**, avec une corrélation quasi nulle pour les deux modèles
(-0.024 et +0.012), alors que Liga, Ligue 1 et les deux saisons montrent
toutes une corrélation positive du même ordre de grandeur (~0.08 à
0.25). Le biais moyen (surestimation), lui, reste négatif et
statistiquement non nul sur **tous** les découpages sans exception (voir
sortie complète du script) — c'est la discrimination, pas le biais, qui
varie selon le championnat.

### P(Over 2.5 observé) par tranche fixe (section 9, descriptif, aucune calibration)

| Tranche | `poisson_simple` (n) | `xg_model` (n) |
|---|---|---|
| 1.5-2.0 | 33.3 % (12) | — |
| 2.0-2.5 | 44.2 % (77) | 20.0 % (5) |
| 2.5-3.0 | 48.3 % (203) | 42.0 % (119) |
| 3.0-3.5 | 57.0 % (193) | 53.3 % (244) |
| 3.5+ | 56.8 % (155) | 56.2 % (272) |

**La fréquence d'Over 2.5 augmente avec la tranche d'espérance prédite,
pour les deux modèles**, quasiment sans exception (les deux dernières
tranches de `poisson_simple` sont à égalité statistique, 57.0 % vs
56.8 %, pas une inversion significative). C'est la lecture la plus
directement utile pour l'objectif final du projet (marchés Over/Under) :
l'espérance de buts, même non calibrée, ordonne correctement les matchs
selon leur probabilité réelle d'Over 2.5.

### Limites méthodologiques

- Corrélations modestes (~0.16 au niveau global) : la discrimination est
  réelle mais loin d'être forte — cohérent avec la résolution mesurée en
  E2/E3 sur les probabilités Over/Under dérivées de cette même variable.
- Premier League ne montre aucun signal de discrimination détectable
  pour aucun des deux modèles — la structure du signal n'est donc pas
  garantie sur tout sous-ensemble du corpus, un résultat à ne pas ignorer
  pour toute exploitation future.
- Aucun bootstrap n'a été construit pour la corrélation elle-même (aucun
  outil générique de ce type déjà présent dans le dépôt, non ajouté
  conformément à la consigne « ne pas ajouter de tests statistiques
  multiples ») — seuls le biais moyen et la MAE portent un IC95%
  bootstrap (réutilisation directe de `paired_bootstrap_test`).
- MAE élevée (~1.4-1.5 but) : la discrimination établie ici ne dit rien
  sur la précision individuelle des prédictions, qui reste grossière.

### Réponse à la question posée

**« Notre estimation du total attendu permet-elle réellement de
distinguer les matchs à faible total de buts des matchs à fort total de
buts, et cette discrimination est-elle suffisamment stable pour
constituer la base d'une future estimation fiable des probabilités
Over/Under ? »**

**Oui pour la discrimination, avec une réserve claire sur la stabilité.**
Sur les tranches fixes (l'analyse principale demandée), le total réel
observé et la fréquence d'Over 2.5 augmentent tous deux de façon
quasi-monotone avec l'espérance prédite, pour `poisson_simple` **et**
`xg_model`, au niveau global. Les quintiles nuancent ce constat (une
inversion locale sur quatre transitions) sans le contredire (Q5 nettement
au-dessus de Q1 dans les deux cas). Cette discrimination reste toutefois
**modeste en intensité** (corrélation ~0.16) et **non uniforme sur le
corpus** : absente en Premier League pour les deux modèles, présente et
comparable en Liga, Ligue 1 et sur les deux saisons. Une surestimation
systématique de l'espérance (déjà établie en K/L) n'annule pas cette
propriété de discrimination, conformément au critère de succès du
protocole — mais toute exploitation future devra tenir compte du fait que
le signal n'est pas structurellement garanti sur tout le corpus. Aucune
conclusion de rentabilité n'est tirée ici ; `poisson_simple` et
`xg_model` restent inchangés, aucune nouvelle calibration créée.

---

## P. Expérience E5 — fiabilité des probabilités Over 2.5 calibrées dans les situations de désaccord avec le marché B365

Question centrale : **quand notre modèle et B365 donnent des probabilités
différentes pour Over 2.5, notre probabilité est-elle encore fiable dans
les situations de désaccord ?** Pas « le modèle gagne-t-il de l'argent »
— « le modèle reste-t-il calibré quand son opinion diverge du marché ? »
`poisson_simple` et `xg_model` restent inchangés ; aucun nouveau modèle.

### Infrastructure ajoutée (documentée avant tout résultat)

Les cotes B365 Over/Under 2.5 n'étaient pas encore lues par le projet
(seul le 1X2 l'était depuis l'ADR 0006). Extension **explicitement
anticipée par l'ADR 0006** (« toute extension future... devra repartir de
`_ALLOWED_COLUMNS` et non l'étendre implicitement ») : `_ALLOWED_COLUMNS`
de `football_data_loader.py` étendue à `B365>2.5`/`B365<2.5` (complétude
vérifiée à 100 % sur les six fichiers réels avant l'extension, comme
B365H/D/A ; colonnes de clôture `B365C>2.5`/`B365C<2.5` explicitement
exclues, testé). Nouveau module `data_engine/market_odds/over_under_odds.py`
réutilisant **sans aucune modification** `matching.match_league_season`
et `time_resolution.conservative_knowledge_time_utc` — même mécanisme
point-in-time que le 1X2 (E1), aucune nouvelle hypothèse temporelle,
mêmes exclusions (jour ambigu, cotes incomplètes, violation PIT). La
probabilité de marché utilise **la formule de retrait d'overround déjà
existante et inchangée** (`market_engine.overround.remove_overround_proportional`) :
probabilité implicite brute = 1/cote pour chaque issue, puis
normalisation à somme 1 (implicite brute / somme des implicites brutes).

Les probabilités **calibrées** sont obtenues en ré-ajustant la même
courbe isotonique qu'E2/E3 (`fit_isotonic_calibration`, INCHANGÉE)
uniquement sur la partie calibration du même découpage 40/30/30, appliquée
au test — reproduction exacte du calcul d'E2/E3, avec conservation du
`match_id` pour joindre les cotes marché (absent du retour agrégé de
`evaluate_recalibration`).

### Couverture

Cotes B365 Over/Under 2.5 point-in-time exploitables : **1806/2132**
(84.7 %, jour ambigu exclu=317, cotes incomplètes exclues=0, non
appariés=9 — mêmes proportions que le 1X2 en E1, cohérent). Sur les 640
matchs du TEST, **542 matchs (84.7 %) sont joints** à une cote marché
valide pour chaque modèle (98 exclus et documentés, faute de cote O/U
point-in-time).

### Tableau central — fiabilité par tranche de désaccord

`model_market_gap = P_model_calibré − P_marché_normalisé`, tranches
fixées avant exécution.

| Tranche | `poisson_simple` n | p_model moy. | Over réel | réel−annoncé | `xg_model` n | p_model moy. | Over réel | réel−annoncé |
|---|---|---|---|---|---|---|---|---|
| ≤−15 pts | 19 | 56.1 % | 73.7 % | **+0.175** | 3 | 38.2 % | 33.3 % | -0.049 |
| −15/−10 | 33 | 54.6 % | 63.6 % | +0.090 | 39 | 57.4 % | 61.5 % | +0.041 |
| −10/−5 | 81 | 54.7 % | 59.3 % | +0.045 | 73 | 55.0 % | 61.6 % | +0.066 |
| **−5/+5 (accord)** | **286** | **53.5 %** | **53.8 %** | **+0.003** | **293** | **54.4 %** | **54.6 %** | **+0.002** |
| +5/+10 | 66 | 52.7 % | 43.9 % | -0.088 | 94 | 52.5 % | 40.4 % | **-0.121** |
| +10/+15 | 44 | 52.1 % | 43.2 % | -0.089 | 37 | 52.2 % | 51.4 % | -0.009 |
| ≥+15 pts | 13 | 54.1 % | 30.8 % | **-0.234** | 3 | 51.5 % | 66.7 % | +0.152 |

### Lecture — `poisson_simple`

**Schéma quasi parfaitement monotone et symétrique.** Dans la zone
d'accord (−5/+5, 53 % du test), le modèle est **excellemment calibré**
(écart de 0.3 point seulement). Mais l'écart réel−annoncé se dégrade
**progressivement et dans le sens attendu** à mesure que le désaccord
grandit dans chaque direction : quand `poisson_simple` est plus pessimiste
que le marché (gap négatif), la réalité est **encore plus haute** que ce
que le modèle annonce (jusqu'à +17.5 points à ≤−15) ; quand il est plus
optimiste que le marché (gap positif), la réalité est **plus basse** que
ce qu'il annonce (jusqu'à −23.4 points à ≥+15). **Le désaccord de
`poisson_simple` avec le marché ne se valide donc PAS** — il pointe
plutôt vers une direction où le modèle est en réalité moins fiable, pas
plus informé. Ce résultat **confirme et prolonge** la partie 4 du
diagnostic post-E1 (aucune information indépendante détectée dans le
désaccord poisson/marché sur le 1X2) avec des probabilités calibrées et
un marché différent (Over 2.5).

### Lecture — `xg_model`

Plus bruité, notamment dans les tranches extrêmes (n=3 des deux côtés,
non interprétables). Sur la tranche la mieux peuplée de désaccord
(+5/+10, n=94, la plus grande tranche de désaccord positif des deux
modèles), le même phénomène apparaît nettement : réel−annoncé = **-0.121**
— le modèle surestime quand il est plus optimiste que le marché, comme
`poisson_simple`. La tranche +10/+15 (n=37) ne suit pas ce schéma
(-0.009, proche de 0) et les tranches extrêmes (n=3) sont trop peu
peuplées pour trancher. Le tableau reste **cohérent avec la même
conclusion générale que `poisson_simple`** sur sa zone de désaccord la
plus fiable statistiquement, sans la même netteté sur l'ensemble du
spectre.

### Comparaison de Brier par tranche (caractérisation, pas un test de rentabilité)

Sur les 14 combinaisons (2 modèles × 7 tranches), **aucun IC95% bootstrap
n'est entièrement d'un côté de 0** — aucune tranche ne montre le modèle
significativement meilleur OU pire que le marché en Brier, à ces tailles
d'échantillon (les tranches extrêmes, n=3 à 19, sont explicitement
signalées « incertitude élevée »). Ceci ne contredit pas le tableau de
fiabilité ci-dessus (qui porte sur le biais de calibration, pas sur le
Brier global de la tranche) — conformément à la consigne, cette
comparaison caractérise les situations de désaccord, elle ne constitue
pas un nouveau test « battre le marché ».

### Concentration (part du test par tranche)

| Tranche | `poisson_simple` | `xg_model` |
|---|---|---|
| ≤−15 pts | 3.5 % | 0.6 % |
| −15/−10 | 6.1 % | 7.2 % |
| −10/−5 | 14.9 % | 13.5 % |
| −5/+5 | **52.8 %** | **54.1 %** |
| +5/+10 | 12.2 % | 17.3 % |
| +10/+15 | 8.1 % | 6.8 % |
| ≥+15 pts | 2.4 % | 0.6 % |

Plus de la moitié du test se situe dans la zone d'accord (−5/+5) pour les
deux modèles ; les désaccords forts (≥15 points, dans un sens ou l'autre)
restent rares (0.6 % à 3.5 % selon le modèle et la direction) — cohérent
avec le faible effectif des tranches extrêmes et la réserve
« incertitude élevée » qui les accompagne.

### Limites méthodologiques

- Tranches extrêmes à très faible effectif (n=3 pour `xg_model` aux deux
  bouts, n=13-19 pour `poisson_simple`) — rapportées avec leur taille,
  jamais fusionnées, mais leur lecture individuelle reste fragile.
- Un seul découpage temporel (le même que E2/E3), aucune répétition sur
  des découpages alternatifs.
- Aucune conclusion de value/rentabilité : ni l'écart de calibration ni
  la comparaison de Brier par tranche ne sont transformés en règle de
  pari à ce stade.
- Extension de `football_data_loader.py` documentée dans l'ADR 0006 mais
  non ré-auditée aussi exhaustivement que le fut le 1X2 initial (E1) -
  la complétude à 100 % a toutefois été vérifiée directement sur les six
  fichiers avant l'extension.

### Réponse à la question posée

**Non, le modèle ne conserve pas sa calibration quand son opinion diverge
fortement du marché — au contraire, la fiabilité se dégrade de façon
quasi monotone avec l'ampleur du désaccord, pour `poisson_simple` de
façon particulièrement nette et symétrique.** Dans la zone d'accord
(la majorité des matchs), les deux modèles calibrés sont excellemment
fiables (écart <0.3 point). Mais plus le modèle s'éloigne du marché, plus
son biais de calibration grandit **dans le sens qui invalide son
opinion divergente** : un désaccord positif franc (`poisson_simple` en
particulier) est suivi d'une fréquence réelle d'Over 2.5 **inférieure**
à ce qu'il annonce, pas supérieure. C'est l'exemple donné en tête de
protocole (« modèle 62 %, marché 53 % ») qui est directement infirmé par
ce résultat sur ce corpus : un tel désaccord n'a **pas** historiquement
correspondu à une fréquence réelle proche de l'opinion du modèle. Aucune
conclusion de rentabilité n'est tirée ; `poisson_simple` et `xg_model`
restent inchangés.

---

## Q. Expérience E6 — le marché Over/Under 2.5 apporte-t-il une information incrémentale sur le total de buts ?

Question centrale, reformulée après E5 : pas « peut-on battre le marché »,
mais **« le marché contient-il une information sur le total de buts que
notre modèle ne possède pas déjà ? »** `poisson_simple` et `xg_model`
restent inchangés ; aucun nouveau modèle ; aucune nouvelle calibration
(réutilise exactement la courbe isotonique d'E2/E3 et les cotes marché
point-in-time d'E5, sans recalcul).

### Inspection préalable des outils existants

- `calibration_engine.decomposition.brier_decomposition` (E2/E3) :
  directement applicable pour comparer le pouvoir de discrimination de la
  probabilité modèle calibrée et de la probabilité marché sur le même
  événement (Over 2.5) — réutilisée sans modification.
- `calibration_engine.significance.two_sample_bootstrap_test` (déjà
  utilisé au diagnostic post-E1, partie 4) : l'outil exact pour la
  question centrale d'E6 — comparer deux groupes non appariés définis par
  une variable, en contrôlant (par stratification) une autre variable.
  Réutilisée sans modification pour les deux tests d'information
  incrémentale (sections 5 et 6).
- `market_engine.overround.remove_overround_proportional` (E1/E5) :
  formule de marché inchangée.
- Seuils de coupure des tests conditionnels : 50 % pour la probabilité de
  marché (le seuil naturel de décision Over/Under) et 2.5 buts pour
  l'espérance du modèle (la ligne du marché elle-même) — jamais
  recherchés, jamais optimisés après observation.

### Couverture

Mêmes 542/640 matchs du TEST joints à une cote marché point-in-time
valide qu'en E5, pour chaque modèle (mêmes exclusions déjà documentées).

### Section 2 — corrélations (descriptif, aucune conclusion isolée)

| | `expected_goals` | `p_model_over25` | `p_market_over25` |
|---|---|---|---|
| **poisson_simple** — expected_goals | 1.000 | 0.784 | 0.738 |
| p_model_over25 | 0.784 | 1.000 | 0.556 |
| p_market_over25 | 0.738 | 0.556 | 1.000 |
| **xg_model** — expected_goals | 1.000 | 0.812 | 0.790 |
| p_model_over25 | 0.812 | 1.000 | 0.680 |
| p_market_over25 | 0.790 | 0.680 | 1.000 |

La probabilité de marché est **fortement corrélée à l'espérance de buts
du modèle** (0.74-0.79) — cohérent avec le fait que les deux estiment la
même grandeur sous-jacente. Conformément à la consigne, cette corrélation
seule ne permet aucune conclusion sur la redondance ou la complémentarité
— c'est l'objet des sections suivantes.

### Section 3 — tranches fixes d'espérance de buts (GLOBAL)

| Tranche | `poisson_simple` n | Total réel | Over25 réel | p_model | p_market | `xg_model` n | Total réel | Over25 réel | p_model | p_market |
|---|---|---|---|---|---|---|---|---|---|---|
| <2.0 | 10 | 2.400 | 40.0% | 49.1% | 36.7% | 0 | — | — | — | — |
| 2.0-2.5 | 70 | 2.414 | 44.3% | 50.0% | 44.4% | 5 | 1.800 | 20.0% | 29.8% | 36.8% |
| 2.5-3.0 | 170 | 2.671 | 51.2% | 50.7% | 50.6% | 102 | 2.441 | 46.1% | 48.2% | 44.6% |
| 3.0-3.5 | 163 | 2.828 | 57.1% | 56.1% | 55.5% | 212 | 2.726 | 53.8% | 53.4% | 51.8% |
| ≥3.5 | 129 | 3.101 | 57.4% | 56.8% | 62.9% | 223 | 3.013 | 57.0% | 58.1% | 60.6% |

À espérance comparable, `p_market` et `p_model` restent proches l'un de
l'autre dans les tranches centrales, mais **le marché s'écarte
nettement au-dessus du modèle dans la tranche ≥3.5** pour les deux
modèles (poisson : 62.9 % vs 56.8 % ; xg : 60.6 % vs 58.1 %) — une
première indication descriptive (pas encore une conclusion) que le
marché pourrait voir quelque chose de plus dans les matchs à forte
espérance.

### Section 5 — test d'information incrémentale : le marché apporte-t-il quelque chose au modèle ?

À l'intérieur de chaque tranche fixe d'espérance, comparaison (bootstrap
non apparié) entre les matchs où `p_market_over25` < 50 % et ≥ 50 % :

| Tranche | `poisson_simple` diff (haut−bas) | IC95% | `xg_model` diff (haut−bas) | IC95% |
|---|---|---|---|---|
| 2.0-2.5 | +0.002 | [-0.26, +0.28] | — (n_bas=5, n_haut=0) | — |
| 2.5-3.0 | +0.081 | [-0.07, +0.23] | +0.026 | [-0.20, +0.25] |
| 3.0-3.5 | +0.107 | [-0.10, +0.31] | +0.089 | [-0.05, +0.23] |
| ≥3.5 | +0.246 | [-0.40, +0.63] (n_bas=3) | +0.178 | [-0.15, +0.48] (n_bas=10) |

**Aucun IC95% n'est entièrement positif au niveau global** — le signal
n'est pas statistiquement démontré à ces tailles d'échantillon. Mais la
direction est **remarquablement cohérente : les 7 tranches interprétables
(sur les deux modèles) montrent toutes un diff positif** (marché plus
haut → fréquence réelle plus haute), jamais négatif — un signe directionnel
net, bien qu'individuellement non significatif.

### Section 6 — test inverse : le modèle apporte-t-il quelque chose au marché ?

À l'intérieur de chaque tranche fixe de probabilité marché, comparaison
entre les matchs où `expected_goals` < 2.5 et ≥ 2.5.

**Résultat structurel important, non anticipé** : dans la majorité des
tranches de probabilité marché (notamment 50-55 %, 55-60 %, ≥60 %), le
groupe « espérance < 2.5 » est **quasi vide ou vide** (n=0 à 14 selon la
tranche, contre 60 à 171 pour le groupe ≥2.5) — parce que l'espérance
prédite par les deux modèles est rarement inférieure à 2.5 sur ce corpus
(cohérent avec le biais de surestimation déjà établi en K/L/E4 : espérance
moyenne ~3.1-3.4). **Le seuil naturel de 2.5 (la ligne du marché
elle-même), bien que non arbitraire, crée un déséquilibre structurel qui
rend ce test peu interprétable sur la majorité des tranches** — un résultat
en soi, pas un artefact caché : la variable de conditionnement du modèle
(l'espérance) ne se répartit pas symétriquement autour de cette valeur.
Les quelques cellules interprétables donnent des résultats **incohérents
entre eux** (`poisson_simple` : IC95% négatif significatif à 55-60% ;
`xg_model` : IC95% positif significatif à <45%, négatif significatif à
45-50%) - pas de conclusion nette possible sur cette direction.

### Section 7 — discrimination (réutilisation directe)

| Portée | `poisson_simple` résolution modèle | résolution marché | `xg_model` résolution modèle | résolution marché |
|---|---|---|---|---|
| GLOBAL | 0.0016 | **0.0062** | 0.0061 | **0.0062** |
| Liga | 0.0028 | **0.0152** | 0.0105 | **0.0152** |
| Ligue 1 | 0.0031 | **0.0194** | 0.0098 | **0.0194** |
| Premier League | 0.0000 | **0.0058** | 0.0025 | **0.0058** |
| 2024/25 | 0.0019 | **0.0071** | **0.0081** | 0.0071 |
| 2025/26 | 0.0041 | **0.0110** | 0.0065 | **0.0110** |

**La résolution (discrimination) du marché est égale ou supérieure à
celle du modèle sur 11 des 12 combinaisons** (seule exception : `xg_model`
en 2024/25, où le modèle dépasse légèrement le marché) — cohérent avec
tous les résultats précédents (E1 diagnostic, E5) : le marché discrimine
au moins aussi bien, généralement mieux, que nos modèles sur cet
événement. **Réserve de comparabilité** : la fiabilité (biais) du modèle
apparaît systématiquement meilleure que celle du marché dans ce tableau,
mais ce n'est **pas une comparaison équitable** — la probabilité modèle a
été explicitement recalibrée par régression isotonique **sur cette
population de test** (E2/E3), alors que la probabilité marché est
seulement débarrassée de l'overround, jamais recalibrée de la même façon.
Cette asymétrie mécanique favorise la fiabilité du modèle par
construction et ne doit pas être lue comme une supériorité réelle de
calibration.

### Stabilité par championnat et saison

Le schéma global se reproduit dans le détail (voir sortie complète du
script) : la plupart des tests conditionnels par sous-groupe portent sur
des cellules à très faible effectif (n=1 à 3 sur l'un des deux côtés dans
la majorité des cas où un IC95% ressort significatif) - ces résultats
« significatifs » isolés sont **explicitement signalés incertains** et ne
doivent pas être lus comme des preuves. **Une seule cellule atteint une
significativité avec un effectif raisonnable des deux côtés** : `xg_model`,
Ligue 1, tranche d'espérance 3.0-3.5, marché <50% (n=22) vs ≥50% (n=45) —
diff=+0.395, IC95%=[+0.15, +0.60], p=0.0016 (encore signalée « incertitude
élevée » par le seuil de 30 déjà documenté, mais nettement mieux pourvue
que les autres). Un seul résultat individuel parmi ~50 cellules testées ne
constitue pas une preuve robuste (risque de faux positif sur tests
multiples, jamais corrigé formellement ici) - rapporté pour complétude,
pas comme un signal retenu.

### Limites méthodologiques

- **Confusion résiduelle intra-tranche** : la stratification par tranches
  fixes ne contrôle qu'approximativement la variable de conditionnement -
  une corrélation résiduelle entre espérance et probabilité marché peut
  subsister à l'intérieur d'une même tranche (l'espérance et la
  probabilité marché sont corrélées à 0.74-0.79, voir section 2). Les
  tests de ce rapport ne prétendent pas à un contrôle causal parfait.
- Le test inverse (section 6) est structurellement déséquilibré sur ce
  corpus (espérance rarement <2.5) - limite intrinsèque, pas corrigée
  après coup (aucun nouveau seuil recherché, conformément au protocole).
- Comparaison de fiabilité modèle/marché asymétrique (modèle calibré sur
  cette population, marché non recalibré) - déjà signalée ci-dessus.
- Cellules à faible effectif nombreuses dans la ventilation par
  championnat/saison - signalées systématiquement, jamais masquées ni
  fusionnées.
- Aucun test corrigé pour comparaisons multiples (nombreuses cellules
  testées) - la lecture privilégie la cohérence directionnelle d'ensemble
  plutôt que des cellules individuelles isolées.

### Réponse à la question posée (grille A/B/C du protocole)

**Ni A (complémentarité démontrée) ni B (information du modèle
démontrée) au sens statistique strict à ces tailles d'échantillon — le
tableau d'ensemble penche vers C (redondance), avec une réserve
directionnelle notable en faveur du marché.**

- **A - Information complémentaire du marché** : non démontrée
  statistiquement (aucun IC95% entièrement positif au niveau global), mais
  le signe est **positif sur les 7 tests interprétables sans exception** -
  un indice directionnel cohérent, pas une preuve.
- **B - Information complémentaire du modèle** : non établie - le test
  inverse est structurellement dégénéré sur la majorité des tranches de
  ce corpus, et les rares cellules interprétables donnent des résultats
  contradictoires entre les deux modèles.
- **C - Redondance** : c'est la lecture la plus soutenue par l'ensemble
  des résultats - forte corrélation entre espérance et probabilité
  marché (0.74-0.79), et surtout **la résolution du marché égale ou
  dépasse celle du modèle sur 11 des 12 combinaisons testées**, cohérent
  avec le diagnostic post-E1 et E5 (le marché discrimine au moins aussi
  bien que nos modèles).

**Verdict de synthèse** : le marché et le modèle capturent majoritairement
le même signal sous-jacent. Il n'est pas démontré que le marché contient
une information incrémentale statistiquement établie sur ce corpus et à
ces tailles d'échantillon, mais tout le faisceau d'indices disponible
(direction systématiquement favorable au marché en section 5, résolution
du marché égale ou supérieure en section 7, cohérence avec E5 et le
diagnostic post-E1) pointe vers **le marché au moins aussi informé que le
modèle, jamais l'inverse** - aucune preuve, dans ce rapport, que le modèle
détient une information sur le total de buts que le marché ne posséderait
pas déjà. Aucune conclusion de rentabilité n'est tirée ; `poisson_simple`
et `xg_model` restent inchangés.

## R. Expérience E7 — construction d'une distribution finale cohérente du total de buts

**Contexte et cadrage.** E6 a établi que le marché et le modèle capturent
majoritairement le même signal sous-jacent sur le total de buts, sans
preuve que le modèle détienne une information incrémentale. Le résultat a
été acté comme contrainte architecturale : le marché n'est pas un
adversaire à battre, mais le modèle conserve une information prédictive
réelle sur le total qu'il convient de représenter aussi fidèlement que
possible. E7 ne cherche donc PAS une nouvelle victoire contre le marché ;
il cherche une représentation du total de buts qui soit (a) cohérente par
construction entre tous les seuils Over/Under, et (b) mieux calibrée que
la distribution brute produite par `poisson_simple`, `dixon_coles` et
`xg_model`. Les trois modèles restent INCHANGÉS ; aucun nouveau modèle
prédictif n'est créé. Aucune conclusion de rentabilité n'est tirée.

### 1. Rappel structurel : une seule matrice, jamais des seuils séparés

L'architecture existante dérive déjà `total_goals_distribution` ET
`over_under_probs` de la MÊME matrice de score `score_matrix(lam, mu)` /
`apply_dixon_coles_correction(matrix, lam, mu, rho)` — la propriété de
source unique était donc déjà garantie avant E7. Le travail d'E7 porte
uniquement sur l'amélioration de la matrice elle-même (via λ, μ), jamais
sur un ajustement séparé par seuil.

### 2. Diagnostic de la queue haute — un problème de moyenne, pas de forme

Comparaison de la distribution empirique observée (corpus complet, 6
championnats-saisons) à une distribution de référence Poisson évaluée à
la moyenne empirique réelle (2.7922 buts) :

| Total | Observé | Poisson(moyenne réelle) |
|---|---|---|
| 0 | 0.0549 | 0.0613 |
| 1 | 0.1689 | 0.1711 |
| 2 | 0.2462 | 0.2389 |
| 3 | 0.2326 | 0.2224 |
| 4 | 0.1506 | 0.1552 |
| 5 | 0.0835 | 0.0867 |
| 6+ | 0.0633 | 0.0644 |

Indice de dispersion (Var/Moyenne, =1 pour un Poisson exact) : **0.9611**.

La distribution empirique et la référence Poisson-à-la-bonne-moyenne se
superposent presque exactement, y compris dans la queue (6+ : 0.0633 vs
0.0644). Le problème identifié aux étapes K/L/E4 (surestimation
systématique, concentrée dans la queue haute) n'est donc PAS un problème
de forme (le total de buts reste bien approximé par un mélange de
Poisson) : c'est un problème de **moyenne prédite trop élevée**. Une
correction de la forme de la distribution serait donc mal ciblée ; une
correction du niveau (de λ+μ) est la piste justifiée par ce diagnostic.

### 3. Démonstration empirique de l'incohérence potentielle de l'isotonique par seuil (E2/E3)

Sur le test walk-forward (n=640), vérification, pour chaque match, que
les probabilités calibrées E2/E3 respectent P(Over1.5) ≥ P(Over2.5) ≥
P(Over3.5) :

| Modèle | n | violations Over1.5<Over2.5 | violations Over2.5<Over3.5 | au moins une violation |
|---|---|---|---|---|
| poisson_simple | 640 | 0 | 0 | 0 |
| xg_model | 640 | 0 | 0 | 0 |

**Aucune violation n'est observée empiriquement sur ce corpus.** Ce
résultat n'invalide pas le risque structurel : une calibration isotonique
indépendante par seuil n'offre AUCUNE garantie mathématique de
monotonicité croisée entre seuils (chaque courbe est ajustée séparément,
sans contrainte conjointe), et rien ne garantit que ce risque reste nul
sur un corpus plus large, d'autres seuils, ou une distribution de marché
différente. La conclusion honnête est donc : le risque est réel en
principe et non démontré empiriquement sur ce corpus précis — ce qui
justifie une approche structurellement garantie plutôt qu'une
vérification a posteriori.

### 4. Méthode proposée : correction scalaire du taux prédit, une seule avant implémentation

**Méthode retenue : correction scalaire unique du taux total prédit.**
Un facteur `c = E[total_réel] / E[λ+μ prédit]` est estimé UNIQUEMENT sur
le split calibration, puis appliqué multiplicativement à (λ, μ) → (c·λ,
c·μ) avant reconstruction de la matrice de score complète (Dixon-Coles ou
indépendante selon le modèle). Justification :

- **Cohérence garantie par construction** : la correction s'applique en
  amont de la matrice, qui reste l'unique source de `total_goals_distribution`
  et `over_under_probs` — aucun risque d'incohérence entre seuils, par
  construction et non par vérification a posteriori.
- **Un seul degré de liberté**, directement motivé par le diagnostic de
  l'étape 2 (le problème est un biais de moyenne, pas de forme) — pas de
  sur-paramétrisation, pas de nouvelle hypothèse de forme.
- **Aucune modification des modèles prédictifs** : `poisson_simple`,
  `dixon_coles`, `xg_model` restent inchangés ; la correction est une
  étape de post-traitement de la distribution, strictement analogue en
  esprit à l'isotonique d'E2 (ajustée sur calibration, évaluée sur test),
  mais appliquée au niveau de la matrice plutôt qu'à chaque seuil
  séparément.
- Alternative écartée : recalibration isotonique de chaque cellule de la
  matrice ou de chaque seuil — reproduirait exactement le risque
  d'incohérence structurelle diagnostiqué à l'étape 3.

Vérification automatique (non-négativité, somme=1, monotonicité
Over/Under, reproduction exacte des probabilités depuis la distribution)
sur un échantillon de 50 matchs réels après application de la correction :
**cohérence vérifiée = True**, et sur balayage aléatoire (`hypothesis`,
200 tirages de λ, μ, ρ, facteur d'échelle) en tests unitaires/anti-fuite,
0 échec.

Facteurs de correction ajustés sur calibration uniquement :

| Modèle | c |
|---|---|
| poisson_simple | 0.8895 |
| dixon_coles | 0.8895 |
| xg_model | 0.8101 |

(poisson_simple et dixon_coles partagent le même c car leurs λ, μ prédits
sont identiques — seule la structure de corrélation bas-score diffère.)

### 5. Résultats — évaluation sur TEST (jamais utilisé pour ajuster c)

Métriques : Brier à 7 catégories (0,1,2,3,4,5,6+) avec IC95% bootstrap
apparié (`paired_bootstrap_test`, réutilisé sans modification) sur le
diff corrigé−brut, log loss à 7 catégories, biais et MAE de l'espérance
totale, P(≥6) prédite vs observée, et décomposition de Murphy
(calibration/résolution) par seuil Over 1.5/2.5/3.5.

**Global (TEST, n=640, tous championnats/saisons confondus) :**

| Modèle | Brier brut | Brier corrigé | diff (IC95%) | p | biais E[Total] brut | biais corrigé | P(≥6) brut | P(≥6) corrigée | P(≥6) observée |
|---|---|---|---|---|---|---|---|---|---|
| poisson_simple | 0.8283 | 0.8229 | [-0.0092, -0.0015] | 0.0056 | +0.2720 | -0.0376 | 0.1062 | 0.0714 | 0.0703 |
| dixon_coles | 0.8294 | 0.8240 | [-0.0093, -0.0016] | 0.0046 | +0.2720 | -0.0376 | 0.1062 | 0.0714 | 0.0703 |
| xg_model | 0.8384 | 0.8207 | [-0.0247, -0.0107] | <0.0001 | +0.5655 | -0.0153 | 0.1414 | 0.0696 | 0.0703 |

**Amélioration statistiquement démontrée du Brier global pour les trois
modèles** (IC95% entièrement négatif). Le biais de l'espérance totale
passe d'une surestimation forte (+0.27 à +0.57) à un biais résiduel quasi
nul (entre -0.04 et -0.02). La probabilité de queue P(≥6) corrigée est
quasiment superposée à la fréquence observée pour les trois modèles
(écarts ≤1.1pt), contre une surestimation d'un facteur ~1.5 à 2 à l'état
brut — confirmant la lecture du diagnostic de l'étape 2 : corriger la
moyenne corrige la queue.

**Décomposition Over/Under (calibration = biais de fiabilité, résolution
inchangée en théorie sous une transformation monotone du taux — mais ici
la correction déplace aussi la matrice sous-jacente, donc la résolution
peut légitimement bouger) — global :**

| Modèle | Seuil | calibration brute | calibration corrigée | résolution brute | résolution corrigée |
|---|---|---|---|---|---|
| poisson_simple | O1.5 | 0.0556 | 0.0513 | 0.0022 | 0.0015 |
| poisson_simple | O2.5 | 0.0828 | 0.0601 | 0.0046 | 0.0062 |
| poisson_simple | O3.5 | 0.0992 | 0.0599 | 0.0059 | 0.0053 |
| dixon_coles | O1.5 | 0.0575 | 0.0504 | 0.0028 | 0.0017 |
| dixon_coles | O2.5 | 0.0828 | 0.0601 | 0.0046 | 0.0062 |
| dixon_coles | O3.5 | 0.0992 | 0.0599 | 0.0059 | 0.0053 |
| xg_model | O1.5 | 0.0950 | 0.0328 | 0.0025 | 0.0029 |
| xg_model | O2.5 | 0.1368 | 0.0302 | 0.0058 | 0.0063 |
| xg_model | O3.5 | 0.1575 | 0.0383 | 0.0029 | 0.0048 |

Le biais de calibration diminue systématiquement sur les 9
combinaisons ; la résolution est préservée ou légèrement améliorée dans
7/9 cas (seule dégradation notable : poisson_simple/dixon_coles Over1.5,
0.0022→0.0015 et 0.0028→0.0017, effet modeste et cohérent avec un léger
"pooling" analogue à celui déjà documenté pour l'isotonique en E2).

**Stabilité par championnat (TEST) :** l'amélioration du Brier global
reste significative pour xg_model sur les trois championnats (p=0.0014
Liga, p=0.0420 Ligue1, p=0.0034 Premier League) et pour poisson_simple/
dixon_coles en Liga (p≈0.03) ; en Ligue1 et Premier League pour
poisson_simple/dixon_coles, l'IC95% contient 0 (p=0.18-0.27, absence de
preuve d'amélioration, jamais de dégradation démontrée). Le biais de
l'espérance totale et la surestimation de la queue sont corrigés dans les
trois championnats pour les trois modèles.

**Stabilité par saison (TEST) :** amélioration significative pour
xg_model sur les deux saisons (p=0.0002 / p=0.0010) ; pour poisson_simple/
dixon_coles, significative en 2025/26 (p≈0.02) mais pas en 2024/25
(p≈0.12, IC95% contenant 0, absence de preuve — jamais de dégradation).
Aucun signe défavorable (IC95% entièrement positif) sur aucune des
combinaisons championnat×saison×modèle testées.

### 6. Limites

- La correction scalaire est un DEGRÉ DE LIBERTÉ UNIQUE : elle corrige un
  biais de niveau, pas d'éventuels biais différentiels par contexte
  (favori/outsider, championnat, phase de saison) qui resteraient à
  investiguer séparément et ne sont pas dans le périmètre d'E7.
- L'absence de violation isotonique empirique (étape 3) ne prouve pas
  l'absence structurelle du risque ; elle documente seulement qu'il ne
  s'est pas matérialisé sur ce corpus précis.
- Les gains ne sont pas uniformément significatifs sur toutes les
  découpes championnat/saison pour poisson_simple/dixon_coles (absence de
  preuve ≠ absence d'effet, échantillons de n=180-320 par découpe) — voir
  section G2 pour la discussion générale des limites de puissance déjà
  documentée sur ce corpus.
- Aucune conclusion de rentabilité n'est tirée ; aucune règle de pari,
  ROI, yield, Kelly, staking, seuil de cote, sélection de bookmaker n'est
  calculée à cette étape.

### 7. Verdict final

**Quelle représentation du total de buts est actuellement la plus fiable
et peut-elle servir de fondation unique pour dériver les marchés
Over/Under ?**

La distribution de score corrigée par facteur d'échelle scalaire (λ, μ
multipliés par `c` ajusté uniquement sur calibration, puis matrice de
score reconstruite en une seule fois) est, à ce stade, la représentation
la plus fiable disponible dans le système :

1. Elle **garantit par construction** — et non par vérification a
   posteriori — la cohérence entre P(Total), P(Over1.5), P(Over2.5) et
   P(Over3.5), contrairement à une calibration isotonique indépendante
   par seuil (E2/E3), dont le risque d'incohérence croisée reste réel en
   principe même s'il ne s'est pas matérialisé empiriquement ici.
2. Elle **corrige la cause identifiée** du biais (un biais de moyenne, pas
   de forme — étape 2), et le fait de façon démontrée : amélioration
   statistiquement significative du Brier global pour les trois modèles,
   biais de l'espérance totale ramené à un niveau quasi nul, et
   correction quasi parfaite de la queue P(≥6).
3. Elle **préserve, dans l'ensemble, la résolution** (pouvoir de
   discrimination) des modèles sous-jacents, sans jamais la dégrader de
   façon substantielle.

Elle doit donc remplacer la distribution brute comme fondation unique
pour dériver tous les marchés Over/Under du système — chaque seuil restant
dérivé de la même matrice corrigée, jamais recalculé indépendamment. Ceci
reste une conclusion de CALIBRATION, pas de rentabilité : aucune règle de
pari n'est validée par ce rapport. `poisson_simple`, `dixon_coles` et
`xg_model` restent inchangés ; seule une étape de post-traitement de leur
sortie est ajoutée, reproduisant exactement le schéma d'E2 (ajustement sur
calibration, évaluation sur test) mais appliquée au niveau de la matrice
plutôt que par seuil.

**Arrêt.** E7 est terminé conformément au protocole. Aucune expérience
suivante n'est lancée automatiquement.

## S. Expérience E8 — validation walk-forward hors échantillon de la distribution corrigée (E7)

**Contexte.** E7 a montré une amélioration significative de la distribution
du total de buts après correction scalaire (`c = E[total_réel]/E[λ+μ]`,
ajustée sur le split calibration, évaluée sur le split test). Mais `c`
était ajusté **une seule fois, sur l'ensemble poolé** (3 championnats
confondus) du split calibration, puis appliqué tel quel à tout le split
test. E8 vérifie si ce résultat tient sous un protocole véritablement
walk-forward, où le facteur de correction de chaque match de test n'utilise
que l'information réellement disponible avant ce match.

### 1. Inspection du pipeline E7 et des frontières temporelles — un risque de fuite identifié

Calcul direct des bornes calendaires du split rodage/calibration/test
(40/30/30, chronologique, **par championnat-saison**) :

| Championnat | Saison | Calibration | Test |
|---|---|---|---|
| ligue1 | 2024/25 | 2024-12-08 → 2025-03-02 | 2025-03-02 → 2025-05-17 |
| premier_league | 2024/25 | 2024-12-14 → 2025-02-26 | 2025-02-26 → 2025-05-25 |
| liga | 2024/25 | 2024-12-07 → 2025-03-09 | 2025-03-09 → 2025-05-25 |
| ligue1 | 2025/26 | 2025-11-30 → 2026-03-01 | 2026-03-01 → 2026-05-17 |
| premier_league | 2025/26 | 2025-12-13 → 2026-02-21 | 2026-02-22 → 2026-05-24 |
| liga | 2025/26 | 2025-12-12 → 2026-03-08 | 2026-03-08 → 2026-05-24 |

Le découpage est chronologique **à l'intérieur** de chaque
championnat-saison, mais **pas globalement** : la calibration de `liga`
2024/25 s'étend jusqu'au 2025-03-09, soit **après** le début du test de
`premier_league` 2024/25 (2025-02-26). Le facteur `c` poolé d'E7, ajusté
sur la calibration poolée des trois championnats, incorpore donc, pour une
partie des matchs de test, des informations issues de matchs
**postérieurs** provenant d'un autre championnat. Ce n'est pas une fuite
du résultat du match test lui-même, mais cela viole la règle stricte
demandée ici ("aucune donnée d'un match ultérieur, aucun paramètre
calibré sur le futur") lorsqu'on l'applique globalement plutôt que
championnat par championnat. C'est exactement le risque de "fausse
validation" anticipé par le protocole (point 7).

### 2. Correction méthodologique appliquée par E8

Pour chaque match de test `m` (trié par `decision_time` = kickoff − 2h,
règle identique partout ailleurs dans le projet, réutilisée sans
modification via `DECISION_OFFSET_HOURS`), le facteur `c(m)` est réestimé
à partir du **seul sous-ensemble du jeu de calibration** (jamais le test,
jamais un autre jeu) dont `decision_time < decision_time(m)` —
exclusivement. Ceci garantit, par construction et indépendamment de tout
chevauchement calendaire entre championnats, qu'aucune information
postérieure au match évalué n'influence son propre facteur de correction.
Aucune nouvelle méthode de calibration n'est introduite : c'est
strictement la même formule qu'E7 (`c = E[total_réel]/E[λ+μ]`), réévaluée
de façon expansive et propre à chaque match.

**Règle d'exclusion (définie avant observation des résultats)** : un match
de test est exclu si moins de 30 matchs de calibration antérieurs sont
disponibles pour estimer `c(m)` (seuil usuel minimal pour une estimation
raisonnablement stable d'un ratio de moyennes). Sur les données réelles,
**0 match exclu** pour les trois modèles (640/640 matchs de test évalués
dans tous les cas) — dès le premier match de test, plus de 30 matchs de
calibration antérieurs poolés étaient déjà disponibles.

### 3. Tests de cohérence et anti-fuite

Reprend sans modification les vérifications d'E7 (non-négativité, somme=1,
monotonicité Over/Under, reproduction exacte). Tests anti-fuite dédiés
écrits avant l'exécution réelle : démonstration qu'un match de calibration
déplacé après `as_of_time` ne change jamais `c(m)` (y compris avec une
valeur de total de buts délibérément aberrante), qu'un match de test
n'entre jamais dans le calcul de `c(m)` (vérifié à la fois par test
synthétique et par inspection statique de la signature de
`fit_scale_correction_as_of`), et balayage aléatoire (`hypothesis`, 150
tirages) confirmant qu'un déplacement temporel d'une ligne de calibration
vers le futur ne peut jamais augmenter le nombre de matchs utilisés, et
vers le passé ne peut jamais le diminuer.

### 4. Stabilité chronologique du facteur c(m) (section 6 du protocole)

| Modèle | n | moyenne | médiane | écart-type | min | max | CV |
|---|---|---|---|---|---|---|---|
| poisson_simple / dixon_coles | 640 | 0.9130 | 0.9139 | 0.0233 | 0.8891 | 0.9399 | 0.0255 |
| xg_model | 640 | 0.8236 | 0.8247 | 0.0134 | 0.8100 | 0.8408 | 0.0162 |

Par saison :

| Modèle | Saison | n | moyenne | écart-type | min | max |
|---|---|---|---|---|---|---|
| poisson_simple / dixon_coles | 2024/25 | 320 | 0.9362 | 0.0007 | 0.9331 | 0.9399 |
| poisson_simple / dixon_coles | 2025/26 | 320 | 0.8897 | 0.0009 | 0.8891 | 0.8947 |
| xg_model | 2024/25 | 320 | 0.8369 | 0.0008 | 0.8342 | 0.8408 |
| xg_model | 2025/26 | 320 | 0.8103 | 0.0009 | 0.8100 | 0.8151 |

**Le facteur est très stable dans le temps** (coefficient de variation
global ≤2.6% pour les trois modèles) : la quasi-totalité de sa variation
provient d'un **écart modeste et net entre les deux saisons** (écart-type
intra-saison quasi nul, 0.0007-0.0009), pas d'une dérive continue ou
erratique à l'intérieur d'une saison. Aucune instabilité sérieuse
détectée.

### 5. Résultats — évaluation walk-forward stricte (aucune exclusion)

**Global (TEST, n=640, walk-forward, IC95% bootstrap apparié sur le diff
Brier corrigé_walk-forward − brut) :**

| Modèle | Brier brut | Brier corrigé WF | diff (IC95%) | p | log loss brut | log loss corrigé WF | biais E[Total] brut | biais corrigé WF |
|---|---|---|---|---|---|---|---|---|
| poisson_simple | 0.8283 | 0.8234 | [-0.0080, -0.0018] | 0.0008 | 1.8394 | 1.8214 | +0.2720 | +0.0279 |
| dixon_coles | 0.8294 | 0.8244 | [-0.0081, -0.0019] | 0.0006 | 1.8442 | 1.8255 | +0.2720 | +0.0279 |
| xg_model | 0.8384 | 0.8212 | [-0.0237, -0.0108] | <0.0001 | 1.8807 | 1.8139 | +0.5655 | +0.0274 |

**L'amélioration statistiquement démontrée en E7 tient sous protocole
walk-forward strict**, pour les trois modèles (IC95% du Brier entièrement
négatif au niveau global). Comme attendu d'un protocole plus strict que
celui d'E7 (chaque match utilise moins de calibration que la version
poolée globalement), le biais résiduel de l'espérance totale n'est pas
ramené aussi près de zéro qu'en E7 (walk-forward : +0.027 à +0.028 contre
E7 poolé : entre -0.04 et -0.02) mais reste très largement inférieur au
biais brut (+0.27 à +0.57) — la correction reste donc très majoritairement
efficace, avec un résidu honnête et attendu compte tenu de la contrainte
temporelle plus stricte.

**Queue P(≥6)** : quasi parfaitement corrigée pour les trois modèles
(0.0738-0.0780 corrigée contre 0.0703 observée, contre 0.1062-0.1414
brute) — la correction de la queue haute, résultat central d'E7, se
confirme intégralement en walk-forward.

**Décomposition Over/Under (Brier, log loss, biais, calibration,
résolution — dérivées exclusivement de la distribution, aucune
calibration indépendante par seuil) — global, priorité Over 2.5 :**

| Modèle | Seuil | Brier brut | Brier corrigé WF | diff (IC95%) | biais brut | biais corrigé WF |
|---|---|---|---|---|---|---|
| poisson_simple | O2.5 | 0.2527 | 0.2487 | [-0.0087, +0.0007] | +0.0667 | +0.0083 |
| dixon_coles | O2.5 | 0.2527 | 0.2487 | [-0.0087, +0.0007] | +0.0667 | +0.0083 |
| xg_model | O2.5 | 0.2643 | 0.2466 | [-0.0274, -0.0081] | +0.1363 | +0.0105 |
| poisson_simple | O3.5 | 0.2153 | 0.2067 | [-0.0128, -0.0041] | +0.0870 | +0.0290 |
| xg_model | O3.5 | 0.2297 | 0.2041 | [-0.0348, -0.0161] | +0.1575 | +0.0270 |

Le biais Over/Under est réduit sur les 9 combinaisons (modèle × seuil) ;
la significativité globale de l'amélioration du Brier de seuil (au niveau
global poolé) est démontrée pour xg_model sur les trois seuils et pour
poisson_simple/dixon_coles sur Over 3.5 uniquement (IC95% entièrement
négatif) — Over 1.5/2.5 pour poisson_simple/dixon_coles restent en
"absence de preuve" au niveau du seuil isolé (IC95% contenant 0), bien que
le Brier à 7 catégories (dont ces seuils sont dérivés) soit lui
significativement amélioré : cohérent avec le fait que la métrique à 7
catégories a davantage de puissance statistique qu'un seuil binaire isolé.

**Stabilité par championnat et par saison (walk-forward)** : le résultat
global tient sur les deux saisons prises séparément (IC95% du Brier
entièrement négatif pour les trois modèles, p<0.05 sauf poisson_simple/
dixon_coles en 2024/25 où p≈0.03-0.04, tout de même significatif). Par
championnat, `liga` montre systématiquement une amélioration significative
pour les trois modèles ; `premier_league` montre une amélioration
significative pour xg_model uniquement (poisson_simple/dixon_coles :
IC95% contenant 0, absence de preuve, jamais d'inversion) ; `ligue1`
montre une amélioration significative pour xg_model, une absence de
preuve proche du seuil pour poisson_simple/dixon_coles (p≈0.086-0.087).
**Aucune des 18 combinaisons (3 modèles × 6 découpes championnat/saison)
n'affiche d'inversion** (IC95% entièrement positif) — condition centrale
de la grille de verdict.

### 6. Grille de verdict (définie avant observation des résultats)

| Modèle | Verdict |
|---|---|
| poisson_simple | **A — VALIDATION RÉUSSIE** |
| dixon_coles | **A — VALIDATION RÉUSSIE** |
| xg_model | **A — VALIDATION RÉUSSIE** |

Critère appliqué mécaniquement : amélioration démontrée au niveau global
(IC95% du Brier entièrement ≤0), aucune inversion dans les 18 découpes
championnat/saison testées, et coefficient de variation du facteur c(m)
très inférieur au seuil de 10% pré-enregistré (2.55%/2.55%/1.62%).

### 7. Limites

- Le résidu de biais walk-forward (+0.027 à +0.028) n'est pas nul :
  attendu, puisque chaque match de test utilise moins de calibration que
  la version poolée d'E7 (surtout en tout début de fenêtre de test).
- Les découpes fines par championnat pour poisson_simple/dixon_coles
  (Premier League, Ligue 1) restent en "absence de preuve" plutôt qu'en
  amélioration démontrée — échantillons de n=184-228, cohérent avec les
  limites de puissance déjà documentées en section G2.
- La règle d'exclusion (n≥30) n'a jamais été activée sur ce corpus ; sa
  pertinence sur un corpus plus restreint ou débutant plus tôt dans une
  saison n'est pas testée ici.
- Aucune conclusion de rentabilité n'est tirée ; aucune règle de pari,
  ROI, yield, Kelly, staking, seuil de cote, sélection de bookmaker n'est
  calculée à cette étape.

### 8. Verdict final

**La distribution de buts corrigée par E7 est-elle suffisamment robuste
en walk-forward pour devenir le moteur officiel de probabilités de
buts ?**

**Oui.** Sous un protocole walk-forward strict — où le facteur de
correction de chaque match de test est réestimé exclusivement à partir des
matchs de calibration réellement antérieurs, corrigeant le risque de fuite
inter-championnats identifié dans le pipeline poolé d'E7 — l'amélioration
démontrée en E7 **tient intégralement** : Brier global significativement
amélioré pour les trois modèles, queue haute quasi parfaitement corrigée,
aucune inversion sur aucune des 18 découpes testées, et facteur de
correction stable dans le temps (CV ≤2.6%). Verdict A (validation réussie)
pour `poisson_simple`, `dixon_coles` et `xg_model`.

`poisson_simple`, `dixon_coles` et `xg_model` restent inchangés ; la
distribution de score corrigée par facteur d'échelle walk-forward peut
donc servir de fondation officielle pour dériver les probabilités de buts
et tous les marchés Over/Under associés. Conformément au cadrage du
protocole, cette conclusion reste strictement une conclusion de
**calibration** — aucune règle de pari, ROI, yield, Kelly, staking, ou
recherche de value n'est validée par ce rapport.

**Arrêt.** E8 est terminé conformément au protocole. Aucune expérience
suivante n'est lancée automatiquement.

## T. Expérience E9 — couche multi-bookmakers et détection d'anomalies/arbitrage

**Contexte et cadrage.** E8 a validé, en walk-forward strict, que la
distribution de buts corrigée par E7 tient hors échantillon (verdict A
pour les trois modèles). E9 ne cherche PAS à battre le marché : il
construit l'infrastructure permettant de comparer notre probabilité
calibrée aux prix de plusieurs bookmakers, et de distinguer explicitement
trois phénomènes différents : (A) écart modèle/marché (ne prouve rien
seul), (B) anomalie bookmaker/marché (un bookmaker isolé du consensus),
(C) arbitrage mathématique (phénomène différent, jamais confondu avec A/B).
Aucune conclusion de rentabilité, aucun ROI, aucune règle de pari.
`poisson_simple`, `dixon_coles` et `xg_model` restent inchangés.

### 1. Audit préalable et extension des données

Inspection de `football_data_loader.py`, `market_engine/` (`overround.py`,
`shin.py`, `model_vs_market.py`), `over_under_odds.py`, ADR 0006 et E5/E6/E8
: l'infrastructure point-in-time (appariement, fuseau horaire, règle de
connaissance conservatrice, `DECISION_OFFSET_HOURS`) était déjà complète et
générique ; seule la **lecture** des données de marché était limitée à un
seul bookmaker (B365). Inspection directe des six fichiers Football-Data
réels : `BW` (Bet&Win) et `PS` (Pinnacle) publient des cotes 1X2 pré-match
non-clôture, mais **aucune colonne Over/Under** pour ces deux bookmakers
(seul B365 porte ce marché dans les fichiers sources) ; `BFE` (Betfair
Exchange) est présent mais explicitement exclu — sa nature d'exchange
(prix déterminés par un carnet d'ordres, pas une marge de bookmaker fixe)
n'est pas clarifiée, décision différée. Complétude constatée (pas
supposée) : `BW` et `PS` sont chacun **partiellement complets**, avec un
profil qui **s'inverse entre les deux saisons** (BW ~0-40% manquant en
2024/25 mais ~0-0.3% manquant en 2025/26 ; PS ~0% manquant en 2024/25 mais
~45-50% manquant en 2025/26) — un artefact de couverture du fournisseur de
données, pas un signal, documenté explicitement comme réserve (section 6).

`_ALLOWED_COLUMNS` étendue à `BWH/D/A` et `PSH/D/A` (1X2 uniquement,
jamais les colonnes de clôture `BWCH/CD/CA`/`PSCH/CD/CA`, vérifié par
test dédié) — voir ADR 0006, section "Extension réalisée (E9)".

### 2. Représentation générique multi-bookmakers

Nouveau module `data_engine/market_odds/multi_bookmaker_odds.py` :
réutilise **sans modification** le mécanisme point-in-time déjà validé
(`matching.py`, `time_resolution.py`, `DECISION_OFFSET_HOURS`) pour
produire, par match, une structure générique `bookmaker → marché →
sélection → cote` (1X2 : H/D/A × B365/BW/PS ; Over/Under 2.5 : Over/Under
× B365 uniquement). Un match reste exploitable dès lors que B365 1X2 est
complet (même condition que E1/E5) ; un bookmaker secondaire absent ou
partiel sur un match donné est simplement absent de son dictionnaire —
**jamais inventé ni imputé**. Corpus exploitable réel : **1806/2123**
matchs appariés (le résidu, ~15%, correspond aux exclusions déjà connues
— jour ambigu lundi/mardi/vendredi — non une nouvelle perte).

### 3. Conversion cote → probabilité et retrait d'overround

`market_engine/overround.remove_overround_proportional`/`hold_percentage`
réutilisés **sans modification**, appliqués **par bookmaker** (jamais sur
un agrégat brut de plusieurs bookmakers — un bookmaker n'est normalisé que
s'il cote **toutes** les sélections du marché, sinon son marché est
partiel et n'est jamais normalisé). Nouveaux modules purs :
`market_engine/consensus.py` (moyenne/médiane/min/max/écart-type des
probabilités normalisées entre bookmakers, aucun poids optimisé, chaque
bookmaker reste identifiable individuellement), `market_engine/anomaly.py`
(grille de classification d'écart **pré-enregistrée**, seuils 0.05/0.10
point de probabilité — réutilise la granularité déjà employée en E5,
jamais qualifié de "value"), `market_engine/arbitrage.py` (détection
**mathématique** pure : `1 - Σ(1/meilleure_cote_i) > 0`, présentée
explicitement comme une détection historique, jamais une opportunité
réelle).

### 4. Résultats — structure du marché (corpus complet, n=1806)

**Marché 1X2 :**

| Bookmaker | Couverture | Overround moyen | Overround médian |
|---|---|---|---|
| B365 | 1806/1806 (100.0%) | 0.0556 | 0.0550 |
| BW | 1453/1806 (80.5%) | 0.0567 | 0.0570 |
| PS | 1383/1806 (76.6%) | 0.0363 | 0.0353 |

Pinnacle (PS) affiche une marge nettement plus basse que B365/BW (~3.6%
contre ~5.6%), cohérent avec sa réputation de bookmaker "sharp" à faible
marge — observation descriptive, aucune conclusion de rentabilité.

Sur les 5418 instances (sélection × match) disposant d'au moins 2
bookmakers : **écart-type moyen entre bookmakers = 0.0053** (0.53 point de
probabilité) — très faible. Conséquence directe : sur les **13926**
instances bookmaker-vs-consensus évaluables, **100% sont classées "proche
du consensus"** (seuil 0.05 jamais atteint) — **aucune anomalie de prix
1X2 détectée sur ce corpus**, ni aucun arbitrage mathématique
(0/1806 matchs).

**Marché Over/Under 2.5 :**

| Bookmaker | Couverture | Overround moyen | Overround médian |
|---|---|---|---|
| B365 | 1806/1806 (100.0%) | 0.0497 | 0.0533 |

Un seul bookmaker disponible sur ce marché dans les fichiers sources :
**0 instance avec ≥2 bookmakers**, consensus et dispersion **structurellement
non calculables**. Les 3612 instances (Over + Under × 1806 matchs) sont
marquées **"n=1, non interprétable"** — statut honnête plutôt qu'un faux
"proche du consensus". Arbitrage : 0/1806 — attendu et documenté comme un
**contrôle de cohérence interne d'un seul bookmaker** (le "meilleur prix
Over" et "meilleur prix Under" proviennent nécessairement tous deux de
B365), **pas une détection d'arbitrage inter-bookmakers réelle** — la
détection d'arbitrage inter-bookmakers sur l'Over/Under 2.5 n'est
**structurellement pas possible** avec les données Football-Data
actuellement disponibles (aucun second bookmaker sur ce marché).

### 5. Modèle vs marché (A), Over 2.5, split TEST walk-forward validé (E8)

Restreint, par construction, à l'intersection du split TEST hors
échantillon d'E8 (n=640, jamais in-sample) et du corpus multi-bookmaker
exploitable (n=542 après intersection, cohérent avec le taux de couverture
~85% déjà observé) :

| Modèle | n | écart moyen (modèle−consensus) | écart médian | proche du consensus | écart notable | écart marqué |
|---|---|---|---|---|---|---|
| poisson_simple | 542 | −0.0114 | −0.0128 | 225 (41.5%) | 195 (36.0%) | 122 (22.5%) |
| xg_model | 542 | −0.0078 | −0.0057 | 318 (58.7%) | 176 (32.5%) | 48 (8.9%) |

Les deux modèles affichent un écart moyen **négatif** (le modèle, après
correction E7/E8, tend légèrement à sous-estimer P(Over 2.5) par rapport
au consensus de marché). `poisson_simple` s'écarte plus fréquemment et
plus fortement du consensus (58.5% de son échantillon en écart
notable/marqué) que `xg_model` (41.4%). **Rappel explicite (protocole
point 12-A)** : cet écart ne prouve à lui seul ni une erreur du modèle, ni
une opportunité de marché — il n'est jamais qualifié de "value" dans ce
rapport ; sa signification économique éventuelle sortirait du périmètre
d'E9.

### 6. Limites

- La couverture BW/PS varie fortement et **s'inverse entre les deux
  saisons** (artefact du fournisseur de données, pas un signal) — toute
  analyse future stratifiée par bookmaker doit tenir compte de cette
  hétérogénéité temporelle avant d'interpréter une différence de
  couverture comme informative.
- L'absence totale d'anomalie 1X2 détectée (0/13926) et d'arbitrage
  (0/1806 sur les deux marchés) peut refléter soit une réelle efficience
  de ce sous-ensemble de bookmakers sur ce corpus, soit une couverture de
  bookmakers encore trop restreinte (3 bookmakers 1X2 seulement, 1 seul
  Over/Under) pour qu'un écart franc apparaisse — non tranché ici.
- La comparaison modèle/marché est restreinte au sous-échantillon
  intersection (n=542/640, ~85%) — les matchs perdus (jours ambigus)
  ne sont pas un échantillon aléatoire du calendrier, réserve déjà
  documentée pour toute analyse Football-Data (ADR 0006).
- Aucune détection d'arbitrage inter-bookmakers n'est possible sur
  l'Over/Under 2.5 avec les données actuellement disponibles (un seul
  bookmaker) — extension future nécessaire pour évaluer ce marché sous
  cet angle.
- Aucune conclusion de rentabilité n'est tirée ; aucun ROI, yield, Kelly,
  staking, profit, ou règle de pari n'est calculé à cette étape.

### 7. Verdict final

**Les données historiques disponibles permettent-elles désormais de
construire une représentation multi-bookmakers suffisamment propre pour
passer ensuite à l'étude des anomalies de prix et de l'arbitrage ?**

**Oui, avec un périmètre clairement délimité.** La couche de données est
construite, testée (anti-fuite compris) et exécutée sur le corpus réel
sans aucune violation point-in-time détectée. Pour le **1X2**, la couche
est riche (3 bookmakers, ~77-100% de couverture individuelle, 5418
instances comparables) et suffisamment propre pour une étude future des
anomalies/arbitrage — à ce stade, sur ce corpus, aucune anomalie ni
arbitrage n'apparaît, ce qui est en soi un résultat descriptif valide (pas
un échec de l'infrastructure). Pour l'**Over/Under 2.5** — notre marché
prioritaire — la couche est propre mais **structurellement limitée à un
seul bookmaker** avec les données Football-Data actuelles : la détection
d'anomalies bookmaker-vs-consensus et d'arbitrage inter-bookmakers n'y est
**pas évaluable**, et ne le deviendra que si une source de données future
apporte un second bookmaker sur ce marché précis. `poisson_simple`,
`dixon_coles` et `xg_model` restent inchangés ; aucune conclusion de
rentabilité n'est tirée.

**Arrêt.** E9 est terminé conformément au protocole. Aucune expérience E10
n'est lancée automatiquement.

## U. Expérience E10 — fiabilité des zones de désaccord modèle/marché (Over/Under 2.5)

**Contexte et cadrage.** E9 a construit la couche multi-bookmakers ; pour
l'Over/Under 2.5, seul B365 est disponible dans Football-Data (limitation
documentée, jamais contournée : aucune analyse inter-bookmakers ni
arbitrage O/U n'est produite ici). E10 teste l'idée centrale du projet :
lorsque `P_model` diverge de `P_market`, certaines zones de désaccord
sont-elles historiquement plus fiables que d'autres ? **Il ne s'agit
toujours pas d'une recherche de stratégie de pari** — la question posée
est uniquement celle de la calibration conditionnelle au désaccord.
`poisson_simple`, `dixon_coles` et `xg_model` restent inchangés ; aucune
nouvelle calibration, aucune sélection de modèle/championnat/saison après
observation.

### 1. Protocole (figé avant exécution réelle)

`P_model` = probabilité Over 2.5 issue **exactement** du pipeline walk-forward
validé en E8 (verdict A) — jamais recalculée. `P_market` = cote B365
Over/Under 2.5, décomposée en probabilité brute (1/cote), overround
(`hold_percentage`) et probabilité normalisée (`remove_overround_proportional`),
toutes deux conservées séparément, jamais confondues. `gap = P_model −
P_market_normalisé`. Tranches de désaccord **identiques à celles déjà
pré-enregistrées en E5** (continuité méthodologique explicite, mêmes
bornes de 5 points, jamais choisies après observation) :

    <=-15pts / -15/-10 / -10/-5 / -5/+5 / +5/+10 / +10/+15 / >=+15pts

Zones d'accord/désaccord (mêmes seuils 5/10/15, point 8) : accord
(|gap|<5), désaccord modéré (5-10), désaccord important (10-15), désaccord
extrême (≥15). Seuil d'incertitude élevée : n<30 (identique à E5). Corpus :
intersection du split TEST walk-forward d'E8 (n=640) et du corpus
multi-bookmaker exploitable d'E9 avec cote B365 O/U complète — **n=542**
pour les trois modèles (même intersection, donc même n, pour
`poisson_simple`, `dixon_coles` et `xg_model`).

### 2. Résultats globaux par tranche de gap

`poisson_simple` et `dixon_coles` produisent des résultats **strictement
identiques** sur ce marché (déjà établi en K : Dixon-Coles ne diffère de
Poisson simple que sur les cellules de score ≤2, sans effet sur Over 2.5) :

| Tranche | n | P_model moy. | Fréq. observée | Biais (IC95%) | Brier | Résolution |
|---|---|---|---|---|---|---|
| ≤−15pts | 22 | 0.380 | 0.636 | **+0.256 [+0.066, +0.435]** | 0.264 | 0.044 |
| −15/−10 | 57 | 0.416 | 0.526 | +0.111 [−0.021, +0.238] | 0.262 | 0.013 |
| −10/−5 | 102 | 0.454 | 0.451 | −0.003 [−0.098, +0.094] | 0.246 | 0.007 |
| −5/+5 (accord) | 225 | 0.542 | 0.564 | +0.022 [−0.045, +0.087] | 0.252 | 0.003 |
| +5/+10 | 93 | 0.604 | 0.505 | −0.099 [−0.200, +0.003] | 0.252 | 0.050 |
| +10/+15 | 34 | 0.695 | 0.618 | −0.077 [−0.226, +0.066] | 0.200 | 0.070 |
| ≥+15pts | 9 | 0.660 | 0.444 | −0.216 [−0.558, +0.131] | 0.315 | 0.006 |

Pour `xg_model` (n=542, même intersection) :

| Tranche | n | P_model moy. | Fréq. observée | Biais (IC95%) | Brier |
|---|---|---|---|---|---|
| ≤−15pts | 8 | 0.414 | 0.375 | −0.039 [−0.312, +0.329] | 0.234 |
| −15/−10 | 30 | 0.481 | 0.633 | +0.152 [−0.019, +0.313] | 0.241 |
| −10/−5 | 92 | 0.493 | 0.544 | +0.051 [−0.049, +0.151] | 0.245 |
| −5/+5 (accord) | 318 | 0.531 | 0.513 | −0.019 [−0.074, +0.036] | 0.250 |
| +5/+10 | 84 | 0.593 | 0.607 | +0.014 [−0.088, +0.113] | 0.231 |
| +10/+15 | 9 | 0.611 | 0.333 | −0.278 [−0.517, +0.012] | 0.251 |
| ≥+15pts | 1 | 0.691 | 0.000 | — | 0.477 |

**Seul un résultat atteint la significativité statistique au niveau
global** : pour `poisson_simple`/`dixon_coles`, la tranche `≤−15pts`
(n=22, modèle nettement plus pessimiste sur Over que le marché) affiche un
biais **positif et significatif** (IC95% entièrement > 0) — le modèle
**sous-estime** systématiquement P(Over 2.5) précisément dans cette zone,
la fréquence réelle d'Over étant plus proche de ce que disait le marché
que de ce que disait le modèle. Aucune autre tranche, pour aucun modèle,
n'atteint la significativité au niveau global. La zone d'accord (−5/+5)
est bien calibrée pour les trois modèles (IC95% du biais contenant
largement 0) — résultat attendu, pas une découverte.

### 3. Zones accord/désaccord (point 8) et comparaison de Brier

| Zone | n (poisson/DC) | Brier (poisson/DC) | n (xg) | Brier (xg) |
|---|---|---|---|---|
| Accord (\|gap\|<5) | 225 | 0.2516 | 318 | 0.2504 |
| Désaccord modéré (5-10) | 195 | 0.2489 | 176 | 0.2380 |
| Désaccord important (10-15) | 91 | 0.2388 | 39 | 0.2434 |
| Désaccord extrême (≥15) | 31 | 0.2788 | 9 | 0.2606 |

**Aucune des comparaisons de Brier (désaccord vs accord) n'atteint la
significativité statistique**, pour aucun modèle (tous les IC95% bootstrap
contiennent 0, p entre 0.17 et 0.81) — voir tableau détaillé dans le
script. Autrement dit : **aucune zone de désaccord ne démontre une
fiabilité (ou une dégradation) statistiquement distincte de la zone
d'accord** sur cet échantillon. Les zones `désaccord extrême` restent à
faible effectif (n=9 à 31 selon le modèle) — comparaisons non concluantes,
pas des absences de preuve de fiabilité.

### 4. Test d'asymétrie (point 10) — résultat le plus net d'E10

| Modèle | n (modèle>marché) | Biais | n (modèle<marché) | Biais | Diff (IC95%) | p |
|---|---|---|---|---|---|---|
| poisson_simple / dixon_coles | 242 | −0.0642 | 300 | +0.0615 | **[−0.2097, −0.0430]** | **0.0040** |
| xg_model | 245 | −0.0334 | 297 | +0.0307 | [−0.1498, +0.0197] | 0.1324 |

Pour `poisson_simple`/`dixon_coles`, l'asymétrie est **statistiquement
significative** : quand le modèle est plus optimiste que le marché sur
Over 2.5 (gap>0), il tend à **sur-estimer** (biais négatif, la fréquence
réelle est inférieure à ce qu'il annonçait) ; quand il est plus
pessimiste (gap<0), il tend à **sous-estimer** (biais positif). Dans les
deux cas, **le désaccord du modèle avec le marché va, en moyenne, dans le
mauvais sens** — la fréquence réelle est systématiquement plus proche de
ce qu'impliquait le marché que de ce que le modèle ajoutait en s'en
écartant. Ce résultat est cohérent avec le diagnostic post-E1, E5 et E6 :
**aucune preuve, ici non plus, que le désaccord du modèle avec le marché
contienne une information fiable** — le marché reste, sur cet échantillon,
la référence la plus proche de la réalité dans les deux directions de
désaccord. Pour `xg_model`, la même tendance directionnelle existe mais
n'atteint pas la significativité (IC95% contenant 0).

### 5. Stabilité par championnat et saison

Les biais significatifs identifiés au niveau global (tranche `≤−15pts`)
ne se répliquent **pas de façon cohérente** au niveau des sous-groupes :
`premier_league` (n=11, biais +0.296, IC95% [+0.026,+0.529]) et `ligue1`
(n=9, biais +0.331, IC95% [+0.038,+0.586]) montrent un biais positif
significatif dans cette même tranche, mais `liga` (n=2) est trop réduit
pour conclure. Par saison, `2025_26` seule atteint la significativité
(n=14, biais +0.273, IC95% [+0.043,+0.482]) ; `2024_25` (n=8) ne l'atteint
pas. La majorité des découpes fines (championnat × tranche, saison ×
tranche) tombent sous le seuil n<30 et sont marquées **incertitude
élevée** — conformément au protocole, aucune conclusion n'en est tirée.

### 6. Diagnostic secondaire 1X2 (victoire à domicile, `poisson_simple` brut)

Fourni à titre secondaire uniquement (priorité restée sur l'Over/Under
2.5, conformément au protocole) : la tranche extrême `≥+15pts` (n=35,
modèle nettement plus optimiste que le marché sur la victoire à domicile)
affiche un biais négatif significatif (−0.242, IC95% [−0.387,−0.094]) —
même lecture qualitative que pour l'Over/Under : quand le modèle
`poisson_simple` s'écarte fortement et à la hausse du marché sur le 1X2,
il tend à sur-estimer. La tranche `≤−15pts` (n=18) montre un biais positif
significatif symétrique (+0.249, IC95% [+0.015,+0.479]). Ce diagnostic
n'a pas vocation à être approfondi dans ce rapport.

### 7. Limites

- **Limitation Over/Under structurelle (documentée, non contournée)** :
  B365 est le seul bookmaker Over/Under 2.5 disponible dans Football-Data
  — aucune analyse inter-bookmakers, aucun arbitrage, aucune dispersion
  multi-bookmakers O/U ne peut être produite à ce stade.
- Les zones de désaccord extrême (≥15 points) restent à très faible
  effectif (n=1 à 31 selon le modèle/découpe) — non concluant, pas une
  absence de signal démontrée.
- Le résultat le plus robuste (asymétrie significative pour
  poisson_simple/dixon_coles) ne se réplique pas avec la même
  significativité pour xg_model — différence de comportement entre
  modèles, non résolue ici, cohérente avec les limites de puissance déjà
  documentées en section G2.
- Aucune conclusion de rentabilité n'est tirée ; aucun ROI, yield, Kelly,
  staking, règle de pari, recherche de meilleur bookmaker n'est calculé.

### 8. Verdict final

**Existe-t-il des zones de désaccord modèle/marché dans lesquelles notre
estimation du total de buts reste historiquement fiable, et ces zones
sont-elles suffisamment stables pour justifier leur conservation dans le
futur moteur d'analyse ?**

**Non, pas sur ce corpus.** Aucune zone de désaccord ne démontre une
fiabilité statistiquement distincte de la zone d'accord (aucune
comparaison de Brier significative, section 3). Le résultat le plus net
va dans le sens **opposé** à l'hypothèse recherchée : pour
`poisson_simple`/`dixon_coles`, une **asymétrie significative** montre que
le désaccord du modèle avec le marché tend, dans les deux directions, à
s'éloigner de la réalité plutôt qu'à s'en rapprocher (section 4) — cohérent
avec l'ensemble des résultats précédents du projet (diagnostic post-E1,
E5, E6). Une seule tranche isolée (`≤−15pts`, désaccord extrême où le
modèle est nettement plus pessimiste que le marché) montre un biais
significatif, mais dans le sens d'une **sous-estimation** du modèle, pas
d'une fiabilité supérieure, et ce signal ne se réplique pas de façon
cohérente entre championnats/saisons à si faible effectif (n=22 au
niveau global). **Aucune zone de désaccord n'est donc suffisamment stable
ni suffisamment démontrée pour être conservée comme composante fiable du
futur moteur d'analyse** — cette conclusion reste strictement de
calibration, jamais de rentabilité ; l'hypothèse d'une éventuelle "value"
future n'est ni validée ni infirmée par ce rapport, simplement non
soutenue par les données actuelles.

`poisson_simple`, `dixon_coles` et `xg_model` restent inchangés.

**Arrêt.** E10 est terminé conformément au protocole. Aucune expérience
E11 n'est lancée automatiquement.

## V. Expérience E11 — cartographie de la fiabilité absolue des probabilités de buts vs B365

**Contexte et cadrage.** E10 a montré qu'aucune zone de désaccord
modèle/marché n'est fiable en soi — le désaccord ne doit donc pas être
utilisé comme signal. E11 change de perspective : au lieu de partir du
gap, il mesure d'abord la **fiabilité absolue** des probabilités du
moteur officiel E8 (H1), puis, seulement dans un second temps et de façon
**exploratoire** (H2), regarde comment les prix B365 se répartissent
parmi les probabilités jugées fiables. `poisson_simple`, `dixon_coles` et
`xg_model` restent inchangés ; aucune nouvelle calibration, aucun tuning,
aucun arbitrage (hors périmètre — un seul bookmaker Over/Under 2.5 dans
Football-Data).

### 1. Protocole

Pour chaque match du split TEST walk-forward d'E8, la matrice de score
**corrigée** (facteur `c(m)` walk-forward) produit, en un seul appel,
les probabilités Over/Under pour 5 seuils dérivés de **la même
distribution** : 0.5 / 1.5 / 2.5 / 3.5 / 4.5 — jamais une calibration
indépendante par seuil (propriété structurelle déjà garantie depuis
l'architecture initiale, confirmée à nouveau ici). Calibration absolue
(H1) mesurée par 10 tranches de probabilité annoncée fixées ex ante
(`reliability_bins`, réutilisé sans modification, [0-10%) … [90-100%]),
augmentées de biais + IC95% bootstrap, Brier, log loss. Complété par la
pente et l'ordonnée à l'origine de la régression de calibration de Cox
(1958) — mesure pure, jamais utilisée pour corriger une prédiction —,
la corrélation point-bisériale, et la décomposition de Brier (E2/E4,
réutilisée sans modification). Comparaison inter-modèles par
`paired_bootstrap_test` sur l'intersection exacte des matchs. H2
(exploratoire) restreinte aux tranches de probabilité jugées fiables au
sens H1 (n≥30, IC95% du biais contenant 0) — décidées **mécaniquement**
à partir de la table de calibration, avant tout examen des prix — puis
catégorisées par écart relatif entre la cote B365 et la cote juste du
modèle, grille fixée ex ante (<2% / 2-5% / 5-10% / ≥10%).

### 2. Résultats H1 — calibration absolue par seuil (GLOBAL, n=640)

| Seuil | Pente | Intercept | Corrélation | Résolution | Tranches significatives (biais IC95% hors 0) |
|---|---|---|---|---|---|
| Over 0.5 | 0.39–0.46 | +1.56 à +1.75 | 0.04–0.07 | 0.0002–0.0015 | aucune (données concentrées en [0.8,1.0), n négligeable ailleurs) |
| Over 1.5 | 0.35–0.53 | +0.48 à +0.70 | 0.08–0.09 | 0.0012–0.0020 | aucune tranche à n≥30 significative (poisson/DC [0.4-0.5) l'est mais n=6) |
| **Over 2.5** | 0.52–0.66 | −0.001 à +0.02 | 0.13 | 0.0035–0.0077 | **[0.6-0.7) sur-confiance, tous modèles** ; [0.3-0.4) sous-confiance (poisson/DC uniquement) |
| Over 3.5 | 0.46–0.64 | −0.40 à −0.54 | 0.12–0.13 | 0.0037–0.0093 | [0.1-0.2) sous-confiance (poisson/DC) ; [0.4-0.5) sur-confiance (xg_model) |
| Over 4.5 | 0.65–0.73 | −0.50 à −0.64 | 0.13–0.16 | 0.0020–0.0052 | [0.3-0.4) sur-confiance (poisson/DC) |

Détail Over 2.5 (priorité, GLOBAL, n=640) :

| Tranche | n | p moyen | Fréq. réelle | Biais (IC95%) |
|---|---|---|---|---|
| [0.3-0.4) | 69 | 0.360 | 0.493 | **+0.133 [+0.016, +0.250]** (poisson/DC) |
| [0.4-0.5) | 178–192 | 0.45–0.46 | 0.45–0.49 | ≈0, IC95% contenant 0 |
| [0.5-0.6) | 201–253 | 0.54–0.55 | 0.55–0.56 | ≈0, IC95% contenant 0 |
| [0.6-0.7) | 117–128 | 0.63–0.65 | 0.52–0.52 | **−0.11 à −0.12, IC95% entièrement <0 (tous modèles)** |

**Résultat central et robuste** : dans la tranche [0.6-0.7), les trois
modèles (poisson_simple/dixon_coles identiques par construction, xg_model
indépendamment) montrent une **sur-confiance statistiquement
significative** — quand le modèle annonce ~64-65%, la fréquence réelle
n'est que ~52%. À l'inverse, la tranche [0.4-0.5) et [0.5-0.6) — la zone
où se concentre la majorité des matchs (n=379 à 445 selon le modèle) —
est **bien calibrée** pour les trois modèles (IC95% du biais contenant
largement 0). Les pentes de Cox restent uniformément **inférieures à 1**
(0.35 à 0.73 selon le seuil) : signe d'une sur-confiance systémique
modérée (les variations de probabilité annoncées sont plus marquées que
les variations réelles de fréquence), cohérent avec le pattern observé
par tranche.

### 3. Comparaison inter-modèles (Brier, paires appariées, mêmes matchs)

| Seuil | poisson_simple vs xg_model : diff Brier (IC95%) | p |
|---|---|---|
| Over 0.5 | [-0.0010, +0.0009] | 0.983 |
| Over 1.5 | [-0.0011, +0.0067] | 0.153 |
| Over 2.5 | [-0.0037, +0.0080] | 0.460 |
| Over 3.5 | [-0.0024, +0.0076] | 0.324 |
| Over 4.5 | [-0.0033, +0.0030] | 0.921 |

**Aucune différence significative entre `poisson_simple` et `xg_model`
sur aucun des 5 seuils** — après correction walk-forward E7/E8, les deux
modèles produisent des distributions Over/Under statistiquement
indiscernables en Brier, malgré un biais brut pré-correction très
différent (xg_model 2× plus fort, établi en K/E7). `dixon_coles`
reproduit exactement `poisson_simple` (déjà établi). **Aucun "gagnant"
n'est désigné**, conformément au protocole.

### 4. Stabilité par championnat et saison

Constat le plus net et **reproduit à travers les 5 seuils et les 3
modèles** : la **Premier League** affiche une corrélation
probabilité-issue proche de zéro ou négative sur presque toutes les
combinaisons (ex. Over 2.5 : corr=−0.006 à +0.037 selon le modèle ; Over
0.5 : jusqu'à −0.09), et une pente de Cox parfois négative (ex.
poisson_simple Over 0.5 : slope=−0.37). `liga` et `ligue1` montrent au
contraire une discrimination positive et modérée (corr 0.10 à 0.26)
partout. **Ce résultat n'est pas nouveau** : il reproduit exactement le
constat déjà établi en E4 ("discrimination réelle mais absente en
Premier League") — désormais confirmé une troisième fois, sur un
mécanisme de mesure différent (calibration walk-forward E8 plutôt que
discrimination brute). Aucune conclusion n'est tirée pour autant sur une
sélection de championnat — signalé comme observation descriptive stable,
pas comme règle.

### 5. H2 (exploratoire) — écarts de prix B365 parmi les probabilités fiables (Over 2.5)

Tranches jugées fiables au sens H1 (décidées avant tout examen des prix) :
`poisson_simple` → [0.4-0.5), [0.5-0.6), [0.7-0.8) (n=350/542) ;
`xg_model` → [0.3-0.4), [0.4-0.5), [0.5-0.6) (n=416/542).

| Modèle | Catégorie d'écart | n | p modèle moyen | Fréq. réelle | Biais (IC95%) |
|---|---|---|---|---|---|
| poisson_simple | <2% | 32 | 0.578 | 0.469 | −0.109 [−0.282, +0.067] |
| poisson_simple | 2-5% | 46 | 0.549 | 0.522 | −0.027 [−0.162, +0.113] |
| poisson_simple | 5-10% | 82 | 0.542 | 0.622 | +0.080 [−0.027, +0.186] |
| poisson_simple | ≥10% | 190 | 0.503 | 0.505 | +0.002 [−0.070, +0.073] |
| xg_model | <2% | 41 | 0.504 | 0.463 | −0.040 [−0.191, +0.113] |
| xg_model | 2-5% | 64 | 0.506 | 0.484 | −0.022 [−0.140, +0.099] |
| xg_model | 5-10% | 106 | 0.508 | 0.509 | +0.002 [−0.095, +0.099] |
| xg_model | **≥10%** | 205 | 0.482 | 0.556 | **+0.074 [+0.006, +0.141]** |

Pour `xg_model`, la catégorie `≥10%` (n=205, l'écart de prix le plus
large avec B365) montre un biais **positif et statistiquement
significatif** : parmi les matchs où `xg_model` est déjà bien calibré ET
où sa cote juste diffère de B365 d'au moins 10%, la fréquence réelle
d'Over 2.5 dépasse légèrement ce que `xg_model` annonçait lui-même. Pour
`poisson_simple`, aucune catégorie n'atteint la significativité. **Ce
résultat est exploratoire (H2)** : il ne constitue ni une "value"
démontrée, ni une stratégie — il documente un écart statistique
descriptif dans une seule sous-catégorie d'un seul modèle, sans
réplication indépendante ni contrôle multi-test.

### 6. Limites

- Les seuils Over 0.5/1.5/4.5 concentrent la quasi-totalité des matchs
  dans 2-3 tranches extrêmes — les pentes de Cox y sont peu fiables
  (variance de p trop faible pour bien identifier la pente) et doivent
  être lues avec prudence.
- Les tranches à n<30 (marquées explicitement) restent nombreuses,
  notamment aux extrêmes de chaque seuil — aucune conclusion n'en est
  tirée.
- Le résultat H2 significatif (xg_model, ≥10%) porte sur une seule
  catégorie d'un seul modèle, non répliqué sur `poisson_simple` ni sur un
  second échantillon — descriptif uniquement, pas un fondement de
  stratégie.
- La discrimination quasi nulle en Premier League reste non expliquée
  (facteurs structurels du championnat non testés ici).
- Aucune conclusion de rentabilité n'est tirée ; aucun ROI, yield, Kelly,
  staking, sélection de championnat/saison/modèle après observation, ni
  arbitrage (hors périmètre).

### 7. Réponses aux questions du protocole

**Q1 — Les probabilités de total de buts sont-elles réellement
fiables ?** Globalement oui, avec une réserve précise : la zone centrale
(40-60% de probabilité annoncée, la plus peuplée) est bien calibrée pour
Over 2.5 sur les trois modèles ; mais une **sur-confiance statistiquement
démontrée et reproduite sur les trois modèles** apparaît dans la tranche
60-70% (biais −0.11 à −0.12). La fiabilité n'est donc pas uniforme sur
toute la plage de probabilité.

**Q2 — À quels niveaux la fiabilité est-elle la meilleure ou la plus
faible ?** Meilleure : 40-60% pour Over 2.5 (zone la plus peuplée et la
mieux calibrée, tous modèles). Plus faible : 60-70% pour Over 2.5 (sur-confiance
significative, tous modèles) et, plus généralement, les tranches
extrêmes de chaque seuil (n souvent <30, non concluant plutôt que
"mauvais").

**Q3 — La distribution E8 permet-elle de dériver de façon cohérente
plusieurs marchés Over/Under ?** Oui — démontré à nouveau ici : les 5
seuils (0.5 à 4.5) sont dérivés en un seul appel de la même matrice
corrigée par match, sans aucune calibration indépendante par seuil,
propriété structurelle déjà garantie depuis E7/E8 et reconfirmée par
l'exécution réelle.

**Q4 — Lorsque la probabilité est fiable, observe-t-on des écarts de
prix intéressants avec B365 ?** Un seul écart statistique atteint la
significativité (xg_model, catégorie ≥10%, biais +0.074, IC95%
[+0.006,+0.141], n=205) — descriptif uniquement, non répliqué, **jamais
interprété comme une rentabilité démontrée**.

`poisson_simple`, `dixon_coles` et `xg_model` restent inchangés.

**Arrêt.** E11 est terminé conformément au protocole. Aucune expérience
E12 n'est lancée automatiquement.
