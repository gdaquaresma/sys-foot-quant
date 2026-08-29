# Protocole pré-enregistré — Handicap Asiatique (Phase H)

**Nature de ce document.** Protocole méthodologique complet, verrouillé
**avant** toute exécution sur données réelles et avant tout code de
production. Contient l'audit documentaire (§0), l'inventaire des
primitives réutilisables (§1), la définition mathématique complète du
marché AH (§2), les données et la couverture (§3), le protocole
walk-forward (§4), les modèles comparés (§5), les métriques (§6), les
hypothèses (§7), les critères de validation/rejet (§8), le traitement
des cas limites (§9), et les interdictions explicites (§10). **Aucune
donnée réelle n'a été utilisée pour fixer une quelconque des définitions
mathématiques ci-dessous** — seuls des chiffres de *couverture* (combien
de lignes existent, combien sont manquantes) ont été mesurés, jamais un
résultat de performance, de calibration ou d'edge.

---

## 0. Audit documentaire (relu intégralement avant rédaction)

`docs/market_data_inventory.md`, `docs/research_synthesis_e1_e16.md`,
`docs/operational_validation_specification.md`,
`docs/operational_validation_report.md`, `docs/next_signal_strategy.md`,
`docs/sot_incremental_information_experiment.md`,
`docs/bfe_incremental_information_experiment.md`,
`docs/final_engine_specification.md`, `docs/final_engine_user_guide.md`,
`docs/architecture.md`.

**Constats déterminants pour ce protocole** :

- Le handicap asiatique n'a **jamais** été mentionné dans aucune des 16
  expériences E1-E16 ni dans les Phases C-G — c'est une hypothèse
  entièrement nouvelle, jamais tranchée, jamais data-dredgée.
- `docs/market_data_inventory.md` (§7) a déjà établi que l'AH est
  **structurellement exploitable** avec le corpus actuel — couverture
  B365 100%, Pinnacle ~76%, BFE ~97% (BFE volontairement exclu ici, §10).
- La leçon méthodologique des Phases F et G (`sot_incremental_information_experiment.md`
  §6, `bfe_incremental_information_experiment.md` §6) est **directement
  réutilisée** : un contrôle « modèle-recalibré » est **obligatoire**
  avant de conclure à une information incrémentale d'une nouvelle
  source, faute de quoi un simple effet de recalibration générique
  pourrait être confondu avec un signal spécifique — c'est exactement
  l'hypothèse D de l'énoncé de cette Phase H.
- `docs/final_engine_specification.md` (§11) interdit explicitement de
  renommer un edge en « value » et exige de toujours distinguer edge
  théorique / incertitude / décision — repris ici sans exception.
- `docs/operational_validation_specification.md` établit la distinction
  A (exactitude probabiliste) / B (edge théorique) / C (rentabilité
  opérationnelle), **jamais confondues** — directement reprise en §7 ici,
  correspondant exactement aux trois questions demandées par cette Phase
  H.

---

## 1. Primitives réutilisées (inspection du code, aucune réimplémentation)

| Besoin | Primitive | Emplacement | Modification |
|---|---|---|---|
| Chargement Football-Data | `load_football_data_csv`, `FootballDataMatchRecord` | `data_engine/market_odds/football_data_loader.py` | **Extension additive** : `AHh`, `B365AHH`, `B365AHA`, `PAHH`, `PAHA` ajoutées à `_ALLOWED_COLUMNS` (couverture vérifiée §3) — BFE-AH, Max/Avg-AH, clôture-AH **non lus** (§10) |
| Matching / point-in-time | `build_understat_keys`, `match_league_season` | `data_engine/market_odds/matching.py` | Aucune (réutilisé tel quel, comme Phases F/G) |
| Résolution des timestamps | `conservative_knowledge_time_utc`, `AmbiguousCollectionWindowError` | `data_engine/market_odds/time_resolution.py` | Aucune |
| Validation des cotes | `validate_odds` | `market_engine/overround.py` | Aucune |
| Retrait de marge | `remove_overround_proportional` | `market_engine/overround.py` | Aucune — **margin-agnostique**, déjà utilisée pour B365/BFE (Phase G §5), directement applicable à un marché à 2 issues (Home/Away conditionnel, §2.5) |
| Correction E7/E8 | `calibrate_prediction`, `fit_scale_correction_as_of` | `final_engine/calibration.py`, `calibration_engine/scalar_correction.py` | Aucune — **non utilisée directement** ici : ce protocole a besoin de la matrice de score complète `(λ,μ)` déjà corrigée, pas seulement des probabilités O/U ; réutilise le même mécanisme via `e7.build_lambda_mu_dataframe`/walk-forward, comme Phase F |
| Edge / EV | `edge`, `expected_value` | `value_engine/edge.py` | Aucune — génériques, réutilisées telles quelles (§2.6) |
| Comparaison modèle/marché | `compare_model_to_market` | `market_engine/model_vs_market.py` | Aucune — générique par construction (dict par sélection), réutilisée telle quelle sur `{"Home":.., "Away":..}` |
| Brier multi-classes | `brier_score`, `log_loss` | `calibration_engine/metrics.py` | Aucune — **déjà générique à K classes** (K=3 pour Home/Push/Away, vérifié dans le code : `_validate` n'impose aucune contrainte K=3 spécifique) |
| Test statistique | `paired_bootstrap_test` | `calibration_engine/significance.py` | Aucune |
| Régression logistique walk-forward | `fit_logistic`, `predict_logistic`, `_safe_logit`, `walk_forward_logistic` | `scripts/run_stage25_e16_market_movement_information.py` | Aucune — réutilisée pour le test binaire principal (§5), import dynamique comme Phases F/G |
| Gates scientifiques / décision | `gates.py`, `decision.py` | `final_engine/` | **Aucune modification** — cette expérience ne touche jamais au moteur de production (§10) |

**Nouvelle primitive nécessaire, aucun équivalent existant** :
`asian_handicap_probabilities(matrix, h) -> {"home":.., "push":.., "away":..}`
— une fonction pure, dérivée de la matrice de score déjà corrigée,
strictement analogue à `over_under_probs` (même fichier cible,
`football_model/goal_distribution.py`), utilisant `np.subtract.outer`
au lieu de `np.add.outer` (§2.3). C'est une **transformation
supplémentaire de la même matrice déjà validée**, pas un nouveau modèle
de buts, pas une nouvelle correction de calibration.

---

## 2. Définition mathématique complète du marché AH

### 2.1 Interprétation de `AHh`/`AHCh`

`AHh` (ouverture) et `AHCh` (clôture) publient la **ligne de handicap
appliquée au DOMICILE**, un nombre réel (positif, négatif ou nul),
constant sur les six fichiers (même convention de nommage entre saisons
— vérifié directement, contrairement à `BF`/`BFD`, Phase G). Convention
standard, déjà cohérente avec les valeurs observées (§3) : une ligne
**négative** favorise le domicile (il doit gagner par plus de
`|AHh|` buts pour couvrir) ; une ligne **positive** avantage le
domicile (il peut perdre par moins de `AHh` buts, ou faire nul, et
couvrir quand même).

**Marge ajustée** pour un match de résultat réel `d = home_goals −
away_goals` et une ligne `h` :

```
m(d, h) = d + h
```

`m > 0` → le domicile couvre ; `m < 0` → l'extérieur couvre ; `m = 0` →
remboursement (« push »), possible **uniquement** si `h` est un entier
(§2.2).

### 2.2 Handicaps entiers, demi-entiers, quart de ligne

Trois familles de lignes, distinguées par `h mod 0.5` :

- **Entier** (`h mod 1 = 0`, ex. `0`, `-1`, `2`) : un push est
  **possible** (`m = 0` atteignable puisque `d` est entier).
- **Demi-entier** (`h mod 1 = 0.5`, ex. `-0.5`, `1.5`) : un push est
  **structurellement impossible** (`d + h` ne peut jamais être entier
  nul si `d` est entier et `h` demi-entier) — ligne « propre », toujours
  Home ou Away.
- **Quart de ligne** (`h mod 0.5 ∈ {0.25, 0.75}`, ex. `-0.25`, `0.75`) :
  n'est **pas** une ligne unique au sens du marché — c'est, par
  définition et convention universellement admise du handicap asiatique,
  une mise **divisée en deux demi-mises égales** sur les deux lignes
  propres adjacentes `h₋ = h − 0.25` et `h₊ = h + 0.25` (l'une entière,
  l'autre demi-entière). Ce n'est **jamais une approximation** — c'est
  la définition structurelle de l'instrument.

### 2.3 Probabilité théorique du modèle pour les trois issues (Home/Push/Away)

Pour une ligne **propre** (`h` entier ou demi-entier), à partir de la
matrice de score déjà corrigée `M[i][j] = P(home=i, away=j)` (E7/E8,
inchangée) :

```
P(Home | h) = Σ_{i,j : i-j+h > 0} M[i][j]
P(Push | h) = Σ_{i,j : i-j+h = 0} M[i][j]     (= 0 si h non entier)
P(Away | h) = Σ_{i,j : i-j+h < 0} M[i][j]
```

Implémentation directe et analogue à `over_under_probs` :
`diffs = np.subtract.outer(np.arange(n), np.arange(n))` (au lieu de
`np.add.outer`), puis les trois masques `diffs + h > 0`, `== 0`, `< 0`.
Ces trois quantités somment exactement à 1 (partition complète de la
matrice), aucune approximation.

Pour une ligne **quart** `h`, décomposée en `h₋`, `h₊` (§2.2), la
probabilité théorique du modèle est la **moyenne simple** (poids
0.5/0.5, reflétant la mise à parts égales) des deux distributions
propres :

```
P(X | h) = 0.5 · P(X | h₋) + 0.5 · P(X | h₊)      pour X ∈ {Home, Push, Away}
```

**Preuve que ceci n'est pas une approximation mais la représentation
exacte du règlement réel** : pour un résultat `d` donné, le parieur
domicile sur une ligne quart `h = h₋ + 0.25` détient une demi-mise sur
`h₋` et une demi-mise sur `h₊`. Si `d + h₋ = 0` (push sur cette jambe)
et `d + h₊ < 0` (perte sur l'autre jambe), le règlement réel est
« demi-remboursé, demi-perdu » — **exactement** ce que produit la
moyenne 0.5·Push + 0.5·Away pour cette valeur de `d` (démonstration
complète, tous cas de `d`, dans les tests unitaires, §12). Cette
propriété généralise : **la moyenne des deux distributions propres est,
terme à terme sur chaque valeur de `d`, identique à la fraction de mise
réellement remboursée/perdue/gagnée** — pas une simplification.

### 2.4 Prix juste

Un push rembourse la mise (profit nul), il n'entre donc jamais dans le
calcul d'une cote « juste » au sens économique (`fair_price`, section 6
de `docs/research_synthesis_e1_e16.md`) — seule la probabilité de
gagner **conditionnellement au fait que le pari ne pousse pas** est
pertinente pour un prix. Convention standard du secteur, retenue ici
explicitement :

```
P(Home | h, not push) = P(Home | h) / (P(Home | h) + P(Away | h))
P(Away | h, not push) = P(Away | h) / (P(Home | h) + P(Away | h))
fair_price_home = 1 / P(Home | h, not push)
fair_price_away = 1 / P(Away | h, not push)
```

Cette normalisation s'applique **identiquement** que `h` soit propre ou
quart (elle opère sur `P(Home|h)`/`P(Away|h)` déjà calculées §2.3,
aucune branche supplémentaire).

### 2.5 Probabilité implicite de marché

Le marché AH ne publie **que** deux cotes décimales (Home, Away) par
ligne — jamais de prix explicite pour le push (un push rembourse
mécaniquement, il n'a pas de prix). Le couple `{Home: cote_home, Away:
cote_away}` est donc **structurellement déjà** une expression
« conditionnelle au non-push » du marché (symétrique à §2.4 côté
modèle). `remove_overround_proportional({"Home": cote_home, "Away":
cote_away})` (réutilisée sans modification, margin-agnostique comme en
Phase G) produit directement `p_market_home`/`p_market_away`,
directement comparables à `P(Home|h, not push)`/`P(Away|h, not push)`
du modèle — **aucune transformation supplémentaire, aucune hypothèse de
marge non vérifiable**.

### 2.6 `raw_edge` et `price_edge`

Réutilisation **exacte**, sans modification, des définitions déjà
figées (`docs/final_engine_specification.md` §11) :

```
raw_edge_home   = edge(P(Home|h, not push), p_market_home)                  # value_engine.edge.edge
price_edge_home = expected_value(P(Home|h, not push), cote_home_B365)       # value_engine.edge.expected_value
```

(et symétriquement pour Away). **Jamais appelés « value »**, comme dans
tout le reste du projet.

### 2.7 Remboursements / demi-gains / demi-pertes — rendement réalisé

Fonction de règlement pure, pour un unique stake unitaire sur le côté
Home à la ligne `h`, résultat réel `d`, cote décimale `o` :

```
settle(d, h) =  Σ_legs (1/n_legs) · outcome_leg
  où pour chaque jambe leg ∈ {h} (ligne propre) ou {h₋, h₊} (ligne quart) :
    outcome_leg = +1  si d + leg > 0   (gain plein sur cette jambe)
    outcome_leg =  0  si d + leg = 0   (remboursement sur cette jambe)
    outcome_leg = -1  si d + leg < 0   (perte pleine sur cette jambe)

profit(d, h, o) = settle(d, h) > 0  → settle(d, h) · (o − 1)
                  settle(d, h) < 0  → settle(d, h)  (perte proportionnelle)
                  settle(d, h) = 0  → 0
```

`settle ∈ {−1, −0.5, 0, +0.5, +1}` — reproduit exactement perte pleine,
demi-perte, push, demi-gain, gain plein. **Ceci est une métrique
descriptive de rendement (catégorie C, §7), jamais utilisée comme
critère de validation** (§8) — conformément à l'interdiction explicite
de confondre rendement réalisé et qualité probabiliste.

### 2.8 Métrique probabiliste (Brier à 3 classes)

`P(Home|h)`, `P(Push|h)`, `P(Away|h)` (§2.3) forment une distribution de
probabilité complète à 3 catégories, directement compatible avec
`calibration_engine.metrics.brier_score`/`log_loss` (déjà génériques à K
classes, §1) — **aucune nouvelle métrique n'est inventée**, seule la
categorie réellement observée (`Home` si `d+h>0`, `Push` si `d+h=0`,
`Away` si `d+h<0` — **pour la ligne réellement cotée sur ce match**,
jamais une moyenne de deux catégories réalisées : pour une ligne quart,
l'issue réalisée est déterminée en tirant, avec probabilité 0.5/0.5,
laquelle des deux jambes sert de référence de classification — voir
§9.2 pour la convention exacte retenue) doit être fournie en `one_hot`.

---

## 3. Données et couverture (mesurée, jamais un résultat de performance)

Audit direct sur le corpus réel (2132 lignes brutes, 2123 appariées
Understat, 1806 exploitables après exclusion jour ambigu/PIT — même
population que E9/E13/Phase G) :

| Élément | Valeur mesurée |
|---|---|
| `AHh` manquant (brut, 2132 lignes) | 5 (0.23%) |
| `n` exploitable (PIT valide, jour non ambigu) | 1806 |
| `AHh`/prix B365 AH incomplet sur les 2123 matchs appariés | 5 |
| Couverture B365 AH (`B365AHH`/`B365AHA`) sur l'exploitable | **1806/1806 (100%)** |
| Couverture Pinnacle AH (`PAHH`/`PAHA`) sur l'exploitable | **1383/1806 (76.6%)** — même profil de dégradation par saison que Pinnacle 1X2/O-U déjà documenté (E13) |
| Couverture BFE AH | ~97% mesurée (Phase G) — **non utilisée ici**, §10 |
| Format de colonnes entre saisons | **Constant** (`AHh`, `B365AHH/AHA` identiques sur les 6 fichiers) — contrairement à `BF`/`BFD` (Phase G), aucune renomination saisonnière |
| Répartition par championnat (exploitable) | Liga 615, Ligue 1 530, Premier League 661 |
| Répartition par saison (exploitable) | 2024/25 : 912, 2025/26 : 894 |
| Répartition par type de ligne (exploitable) | Quart : 956 (53.0%), Demi-entier : 434 (24.0%), Entier : 414 (22.9%), manquant : 2 |
| Lignes les plus fréquentes | `-0.25` (343), `-0.5` (265), `0` (245), `-0.75` (217), `0.25` (211) |
| Ouverture/clôture | Les deux existent (`AHh`/`AHCh`, `B365AHH/AHA`/`B365CAHH/AHA`) — **seule l'ouverture est lue** dans ce protocole (§10) |
| Taux de règlement propre (`settle=±1`, hors push/demi-gain/demi-perte) | 1436/1804 (79.6%) — population du test binaire principal (§5) |

**Conclusion de l'audit** : aucune catégorie n'est trop peu représentée
pour être exclue par précaution — même le sous-groupe le plus étroit
(lignes entières, n=414 exploitables) dépasse largement les seuils
d'effectif déjà utilisés dans le projet (`n≥30`).

---

## 4. Protocole point-in-time

**Identique, sans exception, au mécanisme déjà validé** : `decision_time
= kickoff_utc − DECISION_OFFSET_HOURS` (2.0h, réutilisé), cotes AH
d'**ouverture** uniquement (`AHh`, `B365AHH/AHA`, `PAHH/PAHA`) — jamais
`AHCh`/`B365CAHH/AHA`/`PCAHH/AHA`, qui restent **strictement réservées**
à une éventuelle analyse rétrospective séparée du mouvement de ligne
(non menée ici, hors périmètre — voir §10), jamais mélangées à une
feature de décision. Exclusion jour ambigu (lundi/mardi/vendredi)
identique à tout le reste du projet (`conservative_knowledge_time_utc`).
Aucune nouvelle règle temporelle.

---

## 5. Modèles comparés (figés avant exécution)

Reproduit **exactement** l'architecture de contrôle validée en Phase F/G
(§6 de chaque rapport), appliquée ici à la cible AH plutôt qu'O2.5/1X2 :

| Modèle | Définition | Paramètres |
|---|---|---|
| **Modèle_AH** | `P(Home\|h, not push)` dérivée de la matrice `poisson_simple` corrigée E7/E8 (§2.3-2.4) | 0 (passe-plat) |
| **Marché_AH** | `p_market_home` normalisée B365 AH (§2.5) | 0 (passe-plat) |
| **Modèle_AH-recalibré** (CONTRÔLE OBLIGATOIRE) | `sigmoid(a + b·logit(Modèle_AH))`, walk-forward (E16, `fit_logistic`/`walk_forward_logistic`, INCHANGÉS) | 2, walk-forward |
| **Modèle+Marché_AH** (TEST) | `sigmoid(a + b·logit(Modèle_AH) + c·logit(Marché_AH))`, walk-forward (mêmes primitives) | 3, walk-forward |

Reprend `_MIN_TRAIN=30` (E16). Une seule passe walk-forward sur le
corpus complet trié par `decision_time` — **pas** de split
rodage/validation/test (aucun seuil à protéger contre le
surapprentissage, exactement la justification déjà écrite en Phase F
§3bis/Phase G §6 : ceci est un test d'information pur, jamais une
recherche de seuil).

`Modèle+1X2+AH` (mentionné dans l'énoncé comme comparaison
« éventuelle ») : **non retenue comme hypothèse primaire** — combiner
une probabilité AH (espace Home/Away conditionnel au non-push) avec une
probabilité 1X2 (espace Home/Draw/Away à 3 issues strictement
complémentaires) nécessiterait une reformulation d'espace d'état non
triviale et non déjà balisée par un précédent du projet ; l'introduire
ici violerait la discipline « une seule variable nouvelle à la fois »
déjà appliquée en Phases F/G. **Documentée mais non exécutée.**

**Population du test binaire principal** : uniquement les matchs à
règlement **propre** (`settle=±1`, §2.7, §3) — cible binaire
`y=1[Home couvre]`. Les matchs push/demi-gain/demi-perte (20.4% du
corpus) sont **exclus de ce test binaire précis** (jamais du test de
calibration à 3 classes, §6/§8.A) — choix structurel, pas un seuil
inventé : exactement analogue à l'exclusion d'« Under » comme
complémentaire dégénéré d'« Over » (E13) ou à l'exclusion du cas
`total=2.5` (structurellement impossible) — ici, un résultat mixte
(push/demi-gain/demi-perte) n'est **pas** un « Home couvre » binaire
propre, l'inclure de force romprait la définition même de la variable
cible plutôt que de refléter une exclusion arbitraire.

---

## 6. Métriques

| Métrique | Fonction réutilisée | Rôle |
|---|---|---|
| Brier à 3 classes (Home/Push/Away) | `calibration_engine.metrics.brier_score` (K=3, INCHANGÉE) | Test A — calibration du modèle sur l'AH, population complète (1804 matchs) |
| Brier binaire (population propre) | Formule standard `(p-y)²`, comme Phases F/G | Test B — information incrémentale, population propre (n=1436) |
| Log loss | `calibration_engine.metrics.log_loss` / formule binaire équivalente | Idem, secondaire |
| Calibration (erreur pondérée) | `reliability_bins` (INCHANGÉE, comme Phases F/G) | Test A |
| Test statistique | `paired_bootstrap_test` (INCHANGÉ, 10 000 rééchantillonnages) | IC95%, test B |
| Rendement réalisé (`settle`, §2.7) | Nouvelle fonction pure, jamais un critère de validation | Catégorie C uniquement — **jamais confondue avec A/B** |

---

## 7. Trois questions à ne jamais confondre (reprise exacte d'`operational_validation_specification.md` §2)

| # | Question | Mesure | Statut avant cette expérience |
|---|---|---|---|
| **A** | Le modèle est-il correctement calibré sur les résultats AH ? | Brier/calibration à 3 classes (§6), population complète | Jamais testé — hypothèse ouverte |
| **B** | Le modèle apporte-t-il une information incrémentale **au-dessus** du marché AH (et vice versa) ? | `paired_bootstrap_test` sur Brier binaire, Modèle+Marché_AH **vs Modèle_AH-recalibré** (jamais vs Modèle_AH brut — leçon Phases F/G) | Jamais testé |
| **C** | Existe-t-il une stratégie AH dont l'edge est suffisamment robuste pour activer `BET` ? | **Hors périmètre de cette expérience** — nécessiterait le protocole complet de `docs/operational_validation_specification.md` (split train/validation/test verrouillé, grille de seuils pré-enregistrée, IC95% sur ROI net de marge) | **Non exécuté ici**, quel que soit le résultat de A/B (§10) |

Une amélioration de Brier (test B) n'est **jamais**, à elle seule, une
preuve de rentabilité (C) — rappel explicite non négociable de l'énoncé.

---

## 8. Critères de validation et de rejet

Grille figée **avant** observation des résultats, verdict unique parmi
les cinq valeurs autorisées (§17 de l'énoncé) :

- **`VALIDÉ`** — **uniquement si toutes les conditions suivantes** :
  IC95% de la différence de Brier binaire (Modèle+Marché_AH −
  Modèle_AH-recalibré) **entièrement < 0** au niveau global (n=1436) ;
  robustesse confirmée sur **chaque** championnat et **chaque** saison
  (aucune inversion, IC95% ci_low > 0, dans aucune décomposition) ;
  robustesse confirmée sur les trois types de ligne (entier/demi/quart,
  §9) ; aucune dégradation majeure de calibration (erreur pondérée
  Modèle+Marché_AH ≤ 1.5× celle du contrôle) ; aucune fuite détectée
  (§12) ; effectif ≥ 30 dans chaque sous-groupe examiné.
- **`NON VALIDÉ`** — IC95% chevauchant zéro **et** direction du point
  estimate stable (pas d'inversion nette) — le résultat le plus probable
  au vu des précédents Phases F/G (redondance/absence d'apport
  spécifique).
- **`ABSENCE DE PREUVE`** — effectif insuffisant dans un sous-groupe
  clé (< 30) empêchant une conclusion, **sans que la population globale
  ne soit elle-même trop restreinte** (auquel cas voir `DONNÉES
  INSUFFISANTES`) ; ou IC95% très large sans direction nette (couvrant
  une plage de magnitude non informative des deux côtés de zéro).
- **`DONNÉES INSUFFISANTES`** — si la couverture ou l'effectif global
  s'avéraient, contrairement à l'audit du §3, insuffisants pour toute
  conclusion (n global < 30, ou couverture B365 AH inférieure au seuil
  déjà mesuré).
- **`PROBLÈME MÉTHODOLOGIQUE`** — si un test de fuite (§12) échoue, si
  une incohérence est détectée entre la probabilité théorique (§2.3) et
  son implémentation (violation d'un test unitaire non corrigible sans
  revoir le protocole), ou si la décomposition quart-de-ligne (§2.3) ne
  vérifie pas la propriété démontrée en §2.3 sur les données réelles.

**Aucune formulation intermédiaire n'est autorisée.** Une amélioration
numérique non significative reste `NON VALIDÉ` ou `ABSENCE DE PREUVE`
selon l'effectif — jamais transformée en signal.

**Correction pour comparaisons multiples** : une seule hypothèse
primaire est pré-enregistrée (Modèle+Marché_AH vs Modèle_AH-recalibré,
B365, population globale propre) — **aucune correction n'est
nécessaire** pour cette hypothèse unique (même discipline que Phases
F/G, où le test global unique décide seul du verdict). Pinnacle AH,
décompositions championnat/saison/type-de-ligne sont des **diagnostics
de robustesse**, jamais des tests de significativité indépendants
utilisés pour le verdict — s'ils l'étaient, une correction
Holm-Bonferroni serait requise (comme E16/Phase C), mais ce n'est
explicitement **pas** le design retenu ici.

---

## 9. Traitement des cas limites

### 9.1 Ligne manquante ou cote incomplète

Un match sans `AHh` ou sans `B365AHH`/`B365AHA` complet est **exclu**
(jamais imputé) — 2 cas sur 1806 (§3), sans impact sur la puissance.

### 9.2 Classification de l'issue réalisée pour le Brier à 3 classes sur une ligne quart

Pour le test A (Brier à 3 classes, §2.8), l'issue réellement observée
sur une ligne quart doit être classée en **une seule** des trois
catégories (Home/Push/Away), pas une moyenne — car `brier_score`
consomme un indice de classe entier, pas une distribution. Convention
retenue, dérivée directement de §2.3 (jamais un choix arbitraire
supplémentaire) : la classe observée est **celle de la jambe dominante**
— si `settle(d,h) > 0` → `Home` ; si `< 0` → `Away` ; si `= 0`
(demi-gain et demi-perte s'annulant exactement, uniquement possible sur
une ligne quart avec un push sur une jambe et... **ce cas ne peut
mathématiquement pas se produire** pour une ligne quart, car `push`
exige une jambe entière et l'autre jambe demi-entière ne peut jamais
produire l'opposé exact d'un push — voir démonstration en tests
unitaires §12) → non atteint. Le mapping est donc total et sans
ambiguïté : `settle > 0 → Home`, `settle < 0 → Away`, `settle = 0 → Push`
(ce dernier cas n'existant que pour les lignes entières).

### 9.3 Historique insuffisant (walk-forward)

`Modèle_AH` (transform déterministe de la matrice E7/E8) hérite
directement de la règle déjà en vigueur (`MIN_TRAIN_MATCHES=10`,
`_MIN_CALIBRATION_MATCHES_FOR_SCALE=30`) — un match sans matrice
corrigée disponible (historique insuffisant) est exclu, comme pour tout
usage de `calibrate_prediction`. `Modèle_AH-recalibré`/`Modèle+Marché_AH`
héritent de `_MIN_TRAIN=30` (E16) sur le sous-ensemble éligible.

### 9.4 Lignes extrêmes / rarement observées

Aucune exclusion additionnelle par magnitude de ligne — la partition
Home/Push/Away (§2.3) est valide pour toute valeur de `h`, aucune
troncature nécessaire au-delà de `max_goals=20` déjà en vigueur pour la
matrice de score.

---

## 10. Interdictions explicites (non négociables pour cette Phase H)

- Aucune modification de `poisson_simple`/`dixon_coles`/`xg_model`,
  d'E7/E8/E14/E15/E16, des gates ou de `decision.py`.
- Aucune activation de `BET`. `min_edge_threshold` reste `None`.
- Aucune donnée BFE-AH, Max/Avg-AH, ou de clôture AH n'est lue dans ce
  protocole (une seule source nouvelle : le marché AH B365, Pinnacle en
  secondaire) — cohérent avec la discipline « une seule variable
  nouvelle par expérience » déjà appliquée en Phases F/G.
- Aucune recherche de seuil d'edge, aucune grille inventée après coup.
- Aucune sélection a posteriori de championnat/saison/type de ligne
  « gagnant ».
- Aucune conclusion de rentabilité (question C, §7) tirée de cette
  expérience.
- Cette expérience est la seule autorisée pour cette Phase — aucun
  enchaînement automatique sur une nouvelle expérience après le rapport
  final.

---

## 11. Livrables de cette phase

1. Ce document (`docs/ah_experiment_specification.md`) — **verrouillé**.
2. Extension additive de `football_data_loader.py` (`AHh`, `B365AHH/AHA`,
   `PAHH/PAHA` — ouverture uniquement).
3. Nouvelle primitive pure `asian_handicap_probabilities` (`football_model/goal_distribution.py`).
4. Nouveau module de jointure isolé `data_engine/market_odds/asian_handicap_odds.py`
   (mirroir de `betfair_exchange_odds.py`/`over_under_odds.py`), **jamais importé par `final_engine`**.
5. Script d'expérience `scripts/run_stage29_phase_h_ah_incremental_information.py`.
6. Tests unitaires et anti-fuite (§12 de l'énoncé) — écrits et exécutés
   **avant** toute exécution réelle.
7. `docs/ah_incremental_information_experiment.md` — rapport final,
   après exécution unique.

---

## 12. Tests requis avant exécution réelle (checklist, détaillée en implémentation)

- Handicaps entiers : push correctement détecté, Home/Away sinon.
- Demi-lignes : jamais de push, Home/Away exhaustif.
- Quart de lignes : décomposition en deux jambes propres vérifiée
  algébriquement contre un calcul de référence indépendant (brute force
  sur `d ∈ [-10,10]`), démonstration de la propriété du §2.3
  (« la moyenne des deux distributions égale exactement la fraction de
  mise réglée ») pour tous les cas de figure possibles de `d`.
- Résultats Home/Push/Away : somme des trois probabilités = 1 dans tous
  les cas (propre et quart).
- Demi-gain/demi-perte : `settle(d,h) ∈ {+0.5,-0.5}` vérifié sur des cas
  concrets construits à la main.
- Absence d'utilisation de la clôture : aucun champ contenant `close`/`C`
  ambigu dans le nouveau dataclass (inspection de champs, comme Phases
  F/G/E16).
- Point-in-time : `knowledge_time <= decision_time` toujours vérifié +
  test d'injection d'une observation future qui DOIT échouer si le
  filtre est retiré (garde-fou absolu, comme Phases F/G).
- Absence de fuite entre saisons : le pool walk-forward ne mélange
  jamais un match futur (test dédié, comme Phase F).
- Cohérence des probabilités : `check_distribution_validity`-style sur
  `(P(Home), P(Push), P(Away))`.
- Cohérence des prix justes : `fair_price_home` et `fair_price_away`
  cohérents avec `P(Home|not push)`/`P(Away|not push)` par construction.
- Comportement sur données manquantes : ligne/cote absente → exclusion
  propre, jamais une valeur inventée.
