# Phase I — décision stratégique finale sur le corpus Football-Data

**Nature de ce document.** Audit documentaire et stratégique pur. Aucune
expérience E17/Phase supplémentaire n'est lancée. Aucun backtest, aucun
seuil, aucune modification de `poisson_simple`/`dixon_coles`/`xg_model`,
d'E7/E8/E14/E15/E16, des gates, de `final_engine` ou de tout module de
production. `BET` reste non activé, `min_edge_threshold` reste `None`.
Ce document répond à une seule question : *reste-t-il, avec le corpus
Football-Data déjà présent dans le dépôt, une piste expérimentale
sérieuse et falsifiable, ou le corpus est-il désormais épuisé pour la
question de l'edge de pari ?*

Documents relus intégralement : `docs/research_synthesis_e1_e16.md`,
`docs/operational_validation_specification.md`,
`docs/operational_validation_report.md`, `docs/next_signal_strategy.md`
(Phase E), `docs/sot_incremental_information_experiment.md` (Phase F),
`docs/bfe_incremental_information_experiment.md` (Phase G),
`docs/market_data_inventory.md`, `docs/ah_experiment_specification.md`,
`docs/ah_incremental_information_experiment.md` (Phase H),
`docs/final_engine_specification.md`, `docs/final_engine_user_guide.md`,
`docs/architecture.md`. **Vérification directe** (pas une relecture de
conclusion) : les six fichiers CSV bruts (`research/market_odds/football_data/runs/*.csv`,
120 à 132 colonnes selon le fichier) ont été relus colonne par colonne
via `pandas` pour cet audit — deux constats non anticipés en résultent
(section 4).

---

## 1. État scientifique après Phase H

| Étape | Verdict | Statut |
|---|---|---|
| E1→E16 (campagne économique) | `RESEARCH PHASE CLOSED` — 6 angles indépendants (désaccord 1X2/O-U, dispersion multi-bookmaker, mouvement O→C), tous négatifs ou contradictoires | Close |
| Phase C | Cadrage méthodologique pur, aucun seuil fixé | Terminée |
| Phase D | `NO BET — EDGE NON VALIDÉ` — 3 seuils pré-enregistrés, tous rejetés sur VALIDATION | Terminée |
| Phase E | Audit stratégique — 6 pistes déclarées épuisées, 3 recommandées à coût nul (Max/Avg, BFE, statistiques de match) | Terminée |
| Phase F (SOT) | `NON VALIDÉ` — 97%(89%) du gain apparent est de la recalibration seule | Terminée |
| Phase G (BFE) | `NON VALIDÉ` sur les 4 sélections (H/D/A/Over) | Terminée |
| Phase H (AH) | `NON VALIDÉ` — 97% du gain apparent est de la recalibration seule | Terminée |

**Total : 16 expériences E1-E16 + 4 phases réelles supplémentaires (D, F,
G, H) = 20 tests indépendants de la question « existe-t-il une
information exploitable au-delà de ce que `poisson_simple` + B365
ouverture contiennent déjà ? ». Aucun n'a produit un résultat positif.**
Trois d'entre eux (F, G, H) partagent la même architecture rigoureuse
(contrôle de recalibration obligatoire) appliquée à des sources de nature
très différente — statistiques de match post-match, prix d'échange, marché
de handicap — avec, à chaque fois, la même conclusion mécanique : la
quasi-totalité du gain apparent est un pur effet de recalibration
générique, jamais une information spécifique à la nouvelle source.

**État du moteur** : `min_edge_threshold=None`, `BET` non activé, aucun
modèle modifié, 1485 tests verts au dernier commit (`494fa37`). Aucune
anomalie technique connue.

---

## 2. Inventaire complet des informations déjà testées

### 2.1 Modèle

| Élément | Statut | Référence |
|---|---|---|
| `poisson_simple` | Modèle de référence, **choix architectural** (jamais prouvé supérieur, jamais détrôné) | E11, synthèse §12 |
| `dixon_coles` | Mathématiquement **redondant** avec `poisson_simple` sur Over 2.5/3.5 (fait démontré) | K, E7/E8/E11 |
| `xg_model` | Statistiquement **indiscernable** de `poisson_simple` après E7/E8 ; dépendance de données supplémentaire (Understat) | Diagnostic post-E1, E4, E11 |
| Correction E7/E8 (facteur d'échelle walk-forward) | **VALIDÉ SCIENTIFIQUEMENT**, production | E7, E8 (Verdict A) |
| Recalibration locale E14 (zone [0.6,0.7)) | **REJETÉ** — gate de cohérence inter-seuils violé | E14 |
| A1 (décroissance calendaire), A2 (HFA dynamique), B1 (Dixon-Coles bas-score), B2 (bayésien séquentiel), B3/B3.2/B3.3 (xG, hybride, gate de désaccord), RecentForm/H2H | REJETÉ (A1, B1 Ligue1, B3.3) ou absence de preuve d'amélioration (A2, B2, B3, B3.2) — jamais promus en production | `research_framework.md` sections B1, A2, B2, B3 |
| Ensemble des 3 modèles (moyenne/vote/pondération) | **Jamais testé** — prémisse déjà contredite (E11 : indiscernables ; diagnostic post-E1 : erreurs xG plus corrélées au marché) | Synthèse §8 |

### 2.2 Marché

| Élément | Statut | Référence |
|---|---|---|
| B365 1X2 / O-U 2.5 (ouverture) | Référence de prix officielle du moteur | E1-E16 |
| Pinnacle (1X2, O/U 2.5, AH secondaire) | Redondant avec B365 à chaque fois testé | E9, E13, E16, Phase H |
| Multi-bookmaker (BW/PS/WH/LB, dispersion + arbitrage) | **Épuisé** — 0/1806 arbitrage, dispersion non informative | E9, E13 |
| Betfair Exchange (BFE, 1X2 + O2.5) | **`NON VALIDÉ`** sur les 4 sélections | Phase G |
| Mouvement ouverture→clôture | **Épuisé** — 4 hypothèses primaires non rejetées après Holm-Bonferroni | E16 |
| Handicap asiatique (Home/Away vs B365) | **`NON VALIDÉ`** | Phase H |
| Désaccord modèle/marché (1X2 et O/U) comme signal | **Épuisé** — 4 tests indépendants, jamais favorable, un cas contradictoire | Diagnostic post-E1, E5, E10, E12 |
| Cotes de clôture comme feature de décision | Interdiction structurelle (jamais un feature d'ouverture), testé rétrospectivement (E16) | E16, spec §4.4/§16 |

### 2.3 Signaux additionnels

| Élément | Statut | Référence |
|---|---|---|
| Tirs cadrés (HST/AST, historique walk-forward) | **`NON VALIDÉ`** — 89% du gain est recalibration pure | Phase F |
| xG (Understat) | Voir `xg_model` ci-dessus | B3 |

**Aucune autre variable Football-Data n'a été réellement testée à ce
jour** (tirs totaux, corners, fautes, cartons, score mi-temps, arbitre,
consensus élargi Max/Avg, BF/BFD, 1XB, ni les trois bookmakers découverts
dans cet audit — section 4).

---

## 3. Pistes non testées — classement A/B/C/D

Légende : **A** = testable maintenant et scientifiquement intéressante ;
**B** = testable mais probablement redondante/faible intérêt ; **C** =
impossible avec les données actuelles ; **D** = déjà épuisée par
généralisation directe d'une expérience déjà tranchée.

| Piste | Classe | Justification |
|---|---|---|
| BF/BFD (Betfair Sportsbook, marge ~5%, identique à B365) | **D** | Structurellement identique par construction aux bookmakers à marge fixe déjà démontrés redondants (E9/E13, 5 bookmakers, 0 anomalie/arbitrage sur 13926-18009 instances) ; jamais exécuté empiriquement mais la classe entière de question est tranchée |
| 1XB (1xBet, 1X2 seul, 2024/25 uniquement) | **B** | Même famille que ci-dessus, coverage limitée à une seule saison (puissance réduite) — jamais testé mais très faible probabilité de rompre le schéma déjà établi |
| BMGM (BetMGM), BV, CL — **découverts lors de cet audit, jamais documentés auparavant** (1X2 seul, 2025/26 uniquement, ~99%/99%/75% couverture) | **B** | Même famille de bookmakers à marge fixe ; CL a en outre une couverture dégradée (~25% manquant) ; une seule saison chacun |
| Max/Avg (consensus élargi, panel non divulgué, 1X2+O/U+AH) | **B** | Recommandé en Phase E (coût nul) mais jamais exécuté ; composition opaque déjà écartée par l'ADR 0006 ; 3 expériences ultérieures (F/G/H) sur des sources bien plus différenciées ont toutes échoué — le prior d'un résultat différent pour « plus de bookmakers à marge du même type » est très faible |
| BFE-AH (handicap Betfair Exchange) | **B** | Combine deux sources déjà `NON VALIDÉ` indépendamment (BFE, AH) ; différé deux fois (Phases G, H) |
| Modèle+1X2+AH | **C** | Nécessiterait une reformulation d'espace d'état (Home/Away conditionnel vs Home/Draw/Away) non triviale et non balisée par un précédent — aucune méthode validée n'existe aujourd'hui pour la construire sans introduire une hypothèse de modélisation non testée |
| Lignes O/U supplémentaires (0.5/1.5/3.5/4.5) | **C** | Absentes des six fichiers pour tout bookmaker, ouverture ou clôture — confirmé par grep exhaustif (`market_data_inventory.md` §2-3, reconfirmé section 4 ici) |
| Tirs totaux (HS/AS, historique) | **B** | Structurellement analogue à HST/AST (déjà `NON VALIDÉ`, Phase F) ; même mécanisme de fuite/recalibration attendu ; moins directement lié à la conversion en buts que les tirs cadrés déjà rejetés |
| Corners (HC/AC) | **B** | Jamais testé, lien mécanique avec les buts plus indirect que les tirs ; aucun marché de corners dans le corpus pour valider/comparer |
| Fautes (HF/AF) | **B** | Lien mécanique avec les buts très indirect, jamais testé, intérêt marginal attendu très faible |
| Cartons (HY/AY/HR/AR) | **B** | Lien mécanique indirect (expulsion rare), jamais testé, intérêt marginal attendu très faible |
| Score/résultat mi-temps (HTHG/HTAG/HTR) | **B** | Statistique du match lui-même (post-mi-temps), utilisable seulement en historique walk-forward comme HST/AST — jamais testé, même schéma de redondance attendu |
| Arbitre (`Referee`) | **C** | Présent uniquement sur les fichiers Premier League (E0) — absent de Ligue 1/Liga — couverture structurellement insuffisante pour une expérience multi-championnat cohérente avec la discipline du projet |
| Classement/forme dérivés des résultats déjà présents (points, différentiel de buts par équipe) | **A** | Voir section 6 — seul fil scientifique explicitement identifié comme ouvert par le projet lui-même (synthèse §15, E15) ; calculable sans acquisition ; portée strictement diagnostique |
| Compositions officielles/probables | **C** | Absentes du corpus ; risque de fuite le plus élevé identifié par le projet (Phase E §7) même si acquises |
| Blessures/suspensions | **C** | Absentes du corpus |
| Calendrier/repos (fatigue, congestion) sur données réelles | **B** | Partiellement calculable depuis les dates de coup d'envoi déjà présentes (même championnat uniquement) mais incomplet sans le calendrier des compétitions européennes/coupes (absent du corpus) — un test partiel sous-estimerait mécaniquement l'effet réel |
| xG/statistiques individuelles par joueur | **C** | Absentes du corpus, nécessiteraient un nouveau fournisseur |
| Toute donnée externe (météo, sentiment, etc.) | **C** | Absente du corpus, jamais évoquée par aucune expérience antérieure, spéculative |

---

## 4. Attention particulière — vérification directe des colonnes réelles

Audit direct des six fichiers CSV (pas une relecture de documentation
antérieure) : 150 colonnes distinctes au total, 120 (fichiers 2024/25) à
132 (fichiers 2025/26) par fichier. **Deux constats non anticipés** :

- **Trois bookmakers jamais documentés auparavant, présents uniquement
  dans les trois fichiers 2025/26** : `BMGM` (BetMGM, 1X2 ouverture +
  clôture, ~99% couverture), `BV` (1X2 ouverture + clôture, ~99%
  couverture), `CL` (1X2 ouverture + clôture, **~74-77% couverture,
  nettement dégradée** — jusqu'à 294/1140 cellules manquantes sur
  E0/SP1_2025_26). Aucune colonne O/U ni AH pour ces trois bookmakers.
- Confirmation directe (pas une relecture) de `1XB` (2024/25 uniquement,
  ~97-98% couverture), `BF`→`BFD` (renommage inter-saison identique à
  WH→LB, overround ~5%), `HS/AS/HST/AST/HC/AC/HF/AF/HY/AY/HR/AR` à 100%
  de couverture sur les six fichiers, `Referee` présent **uniquement**
  sur les deux fichiers Premier League (E0) — absent de Ligue 1/Liga.
- Confirmation exhaustive (grep sur le motif `<bookmaker><N.N`) : **aucune
  colonne O/U autre que 2.5** n'existe, pour aucun bookmaker, ouverture ou
  clôture, sur aucun des six fichiers.
- Aucune colonne de composition, blessure, classement, forme, ou
  calendrier multi-compétition n'existe dans le corpus — les 150 colonnes
  se répartissent exhaustivement en (a) métadonnées de match
  (équipe/date/heure/championnat), (b) statistiques du match lui-même
  (buts, tirs, corners, fautes, cartons — toutes post-match), et (c) cotes
  de marché (1X2, O/U 2.5, handicap asiatique, ouverture et clôture, une
  quinzaine de bookmakers au total).

### Tableau détaillé — pistes signalées par l'énoncé

| Variable | Existe réellement ? | Connue avant le match ? | PIT-utilisable ? | Couverture | Risque de fuite | Déjà testée ? | Intérêt marginal attendu |
|---|---|---|---|---|---|---|---|
| 1XB | Oui, 1X2 seul | Oui (cote pré-match) | Oui, même mécanisme que B365 | ~97-98%, **2024/25 seulement** | Faible (même schéma que B365) | Non | Très faible (bookmaker à marge fixe, classe déjà épuisée D) |
| BF/BFD (Betfair Sportsbook) | Oui, 1X2 seul, renommé entre saisons | Oui | Oui | ~100% | Faible | Non (jamais empiriquement) | Très faible (overround ~5% identique à B365) |
| BMGM/BV/CL (nouveaux, cet audit) | Oui, 1X2 seul, **2025/26 uniquement** | Oui | Oui | 99%/99%/75% | Faible | Non | Très faible (même classe) |
| Autres statistiques de match (HS/AS/HC/AC/HF/AF/cartons) | Oui, 100% de couverture | **Non** — connues seulement après le coup d'envoi (comme HST/AST) | Oui, en historique walk-forward uniquement (jamais comme feature du match décrit) | 100% | Faible si discipline walk-forward respectée (comme Phase F) | Non (sauf HST/AST, Phase F) | Faible — HST/AST (le proxy le plus direct) déjà `NON VALIDÉ` |
| Corners | Oui | Non (post-match) | Idem | 100% | Idem | Non | Faible, lien mécanique aux buts plus indirect que les tirs |
| Fautes | Oui | Non (post-match) | Idem | 100% | Idem | Non | Très faible |
| Cartons | Oui | Non (post-match) | Idem | 100% | Idem | Non | Très faible |
| Tirs (totaux) | Oui | Non (post-match) | Idem | 100% | Idem | Non | Faible (HST/AST, le proxy le plus qualitatif, déjà rejeté) |
| Variables uniquement post-match | HTHG/HTAG/HTR, FTHG/FTAG, tous les `H*`/`A*` de statistiques | Non par définition | Historique uniquement | 100% | Élevé si utilisées directement sur le match qu'elles décrivent | HTHG/HTAG partiellement via HT dans aucune expérience à ce jour | Faible |
| Asian Handicap | Oui | Oui (ouverture) | Oui | B365 100%, Pinnacle 76.6% | Faible (même mécanisme que B365) | **Oui — Phase H, `NON VALIDÉ`** | Nul (déjà tranché) |
| Lignes O/U supplémentaires | **Non** — absentes du corpus | — | — | 0% | — | Impossible à tester | — |
| Compositions | **Non** — absentes du corpus | Seraient connues ~1h avant le coup d'envoi (après `decision_time` actuel) | Non sans nouveau fournisseur documentant l'horodatage | 0% | **Le plus élevé identifié dans le projet** | Non | Incertain, jamais mesurable ici |
| Blessures | **Non** — absentes du corpus | Variable | Idem | 0% | Élevé (sous-ensemble de compositions) | Non | Incertain |
| Classement | Dérivable des résultats déjà présents, pas une colonne dédiée | Oui (mis à jour en continu) | Oui, si calculé point-in-time à partir des résultats déjà chargés | 100% (dérivable) | Faible si calculé strictement walk-forward | Non | Incertain mais ciblé — voir section 6 |
| Forme récente | Testée comme approche de modélisation (A1, RecentFormModel), pas une donnée de marché | Oui | Oui | 100% | Faible | **Oui — A1 REJETÉ, RecentFormModel/H2H sans signal net** | Nul (déjà tranché comme approche de modèle) |
| Calendrier (congestion) | Partiel (dates de match du même championnat) | Oui | Oui, partiellement | Incomplet (manque les coupes/compétitions européennes) | Faible | Non sur données réelles (E1/E7 : synthétique uniquement, étape 5) | Faible à modéré, mais test structurellement incomplet |
| Information externe absente du corpus | Non applicable | — | — | 0% | — | — | — |

---

## 5. Faux amis identifiés

1. **Toute statistique de match** (`HS`/`AS`/`HST`/`AST`/`HC`/`AC`/`HF`/
   `AF`/`HY`/`AY`/`HR`/`AR`, `HTHG`/`HTAG`/`HTR`) — paraît prédictive mais
   est connue seulement **après** le coup d'envoi du match qu'elle décrit ;
   utilisable uniquement en historique walk-forward (discipline déjà
   appliquée en Phase F, à reconduire à l'identique pour toute extension
   future).
2. **Toute cote de clôture** (y compris `AHCh`, `B365CAHH/AHA`) — semble
   être « la meilleure information disponible » mais n'est jamais
   disponible à `decision_time` ; déjà démontrée non informative même en
   usage rétrospectif légitime (E16).
3. **Compositions « probables »** (non officielles, médias) — semblent
   disponibles suffisamment tôt mais ne sont pas des faits vérifiés ; les
   traiter comme un fait serait une fuite d'un autre type (confiance non
   justifiée dans une prédiction externe).
4. **Max/Avg (consensus élargi)** — semble être une information nouvelle
   (accès à un panel plus large de bookmakers) mais sa composition exacte
   n'est jamais divulguée par Football-Data (exclusion déjà actée, ADR
   0006) — gonflerait le nombre de « sources testées » sans ajouter une
   information vérifiablement distincte.
5. **BF/BFD, 1XB, BMGM, BV, CL** — semblent être de nouvelles sources
   mais sont, par construction, des bookmakers à marge fixe
   structurellement identiques à B365/BW/PS/WH/LB déjà démontrés
   redondants (E9/E13) ; trois d'entre eux (BMGM/BV/CL) n'ont en outre
   qu'une seule saison de couverture.
6. **`Referee`** — paraît être une variable pré-match légitime, mais sa
   couverture est structurellement limitée à la Premier League (absente
   de Ligue 1/Liga) — toute conclusion serait non généralisable et
   biaiserait un diagnostic vers le championnat déjà connu pour son
   anomalie de discrimination (E4/E11/E15).
7. **Le désaccord modèle/marché** — a l'apparence intuitive d'un signal
   (« le modèle a raison contre le marché ») mais est démontré, à quatre
   reprises indépendantes, n'être jamais un signal fiable.
8. **`Modèle+1X2+AH`** — paraît être une extension naturelle du travail
   de la Phase H, mais combine deux espaces de probabilité incompatibles
   (Home/Away conditionnel vs Home/Draw/Away à 3 issues complémentaires)
   sans méthode validée — un faux ami méthodologique, pas seulement une
   question de données manquantes.
9. **Classement/forme dérivés des résultats bruts** — pourrait sembler
   être une mesure totalement indépendante du modèle, alors qu'elle
   reste, en partie, dérivée des mêmes matchs que `poisson_simple`
   utilise déjà en entrée (buts marqués/encaissés) — à ne jamais présenter
   comme une mesure « externe » au sens strict, contrairement à un
   classement officiel publié par un tiers (réserve déjà actée par E15
   sur les mesures « dérivées du modèle lui-même »).

---

## 6. Analyse de rendement décroissant

> **« Après E1→E16 + Phases F/G/H, quelle est la probabilité raisonnable
> qu'une nouvelle expérience sur les mêmes fichiers découvre une
> information réellement incrémentale ? »**

## **Très faible.**

Justification (aucune probabilité numérique n'est avancée, faute d'être
justifiable — seule une qualification est proposée, conformément à la
consigne) :

- **20 tests indépendants, 0 résultat positif.** E1-E16 ont interrogé la
  question sous 6 angles indépendants (désaccord 1X2, désaccord O/U,
  intersection fiabilité×prix, dispersion/arbitrage multi-bookmaker,
  mouvement O→C, recherche de seuil d'edge en Phase D) — tous négatifs ou
  contradictoires. Phases F, G, H ont ensuite testé trois sources
  **qualitativement très différentes** (statistiques de match post-match,
  prix d'un marché d'échange sans marge fixe, marché de handicap à
  structure de règlement entièrement différente du 1X2/O-U) avec la
  **même architecture rigoureuse** (contrôle de recalibration obligatoire)
  — les trois fois, le résultat converge : l'essentiel du gain apparent
  est un effet de recalibration générique, jamais une information
  spécifique à la source testée (89% pour SOT, 97% pour AH ; BFE ne montre
  même aucun gain apparent à expliquer).
- **Le mécanisme causal est désormais bien compris, pas seulement
  observé.** Phase D a montré directement, par simulation du moteur réel,
  que les matchs à edge élevé sont précisément ceux où le modèle est
  sur-confiant (E11 : zone [0.6,0.7)) — un mécanisme qui n'est pas
  spécifique à une source de marché particulière, et qui prédit que
  n'importe quelle nouvelle source de marché supplémentaire produira le
  même schéma (déjà vérifié trois fois : BFE, AH, et partiellement SOT).
- **Toutes les pistes de marché restantes appartiennent à des familles
  déjà tranchées.** BF/BFD/1XB/BMGM/BV/CL/Max-Avg sont tous des
  bookmakers à marge fixe (ou leur agrégat) — exactement la famille déjà
  démontrée homogène et non informative sur 5 bookmakers différents
  (E9/E13, 0 arbitrage sur 13926-18009 instances). Il n'existe aucune
  raison structurelle de s'attendre à ce qu'un 6ᵉ, 7ᵉ ou 8ᵉ bookmaker de
  la même famille rompe ce schéma.
- **Toutes les pistes de signal additionnel restantes appartiennent à une
  famille déjà tranchée.** Tirs totaux, corners, fautes, cartons partagent
  avec HST/AST (déjà `NON VALIDÉ`) le même statut structurel (statistique
  post-match, utilisable en historique walk-forward uniquement) et un
  lien mécanique aux buts **plus indirect** que les tirs cadrés, le proxy
  le plus qualitatif déjà rejeté.
- **La seule piste non déjà couverte par ce raisonnement** (classement/
  forme dérivés des résultats, section 3/4) est de nature diagnostique,
  pas une recherche d'edge — elle ne change pas cette qualification pour
  la question centrale (voir section 7).

---

## 7. Piste prioritaire ou corpus épuisé

Application stricte du critère de l'énoncé (« Une expérience ne doit être
recommandée que si elle a une hypothèse falsifiable et une chance
raisonnable de produire une information non redondante ») à l'ensemble
des pistes classées A/B/C/D en section 3-4 :

- Toutes les pistes classées **B** partagent une hypothèse falsifiable
  mais une **chance déraisonnablement faible** de produire une
  information non redondante, compte tenu du rendement décroissant
  démontré (section 6) — les recommander violerait directement
  l'interdiction de l'énoncé de proposer une expérience « simplement
  parce qu'une colonne existe ».
- Toutes les pistes classées **C** sont structurellement impossibles avec
  le corpus actuel.
- La seule piste classée **A** (classement/forme dérivés des résultats,
  sections 3-4) est **scientifiquement légitime mais hors-sujet pour la
  question posée par cette Phase I** : ce n'est pas une recherche
  d'information exploitable pour le pari — c'est le fil diagnostique
  explicitement identifié par le projet lui-même (`docs/research_synthesis_e1_e16.md`
  §15, issu d'E15) pour expliquer *pourquoi* la Premier League ne
  discrimine pas, jamais pour produire un signal de pari. Le document qui
  l'a proposée le qualifie lui-même d'« optionnelle » et « non
  bloquante » pour le moteur minimal viable. Même un résultat positif sur
  cette piste ne changerait ni le statut `BET`/`NO_BET` ni
  `min_edge_threshold` — elle résoudrait une question de compréhension du
  modèle, pas une question d'edge. Elle ne satisfait donc pas le critère
  d'une « expérience prioritaire » au sens de cette Phase I, qui porte
  explicitement sur l'existence d'une information exploitable pour le
  pari.

**Aucune piste ne satisfait donc le critère d'une expérience prioritaire
justifiée pour la question posée.**

## CORPUS FOOTBALL-DATA — PISTES SCIENTIFIQUEMENT ÉPUISÉES

**Explication.** Le corpus Football-Data actuellement présent dans le
dépôt a été interrogé, sur la question de l'edge de pari exploitable, sous
vingt angles indépendants (E1-E16 + Phases D/F/G/H), avec des méthodes
statistiques rigoureuses (bootstrap, corrections de comparaisons
multiples, contrôles de recalibration obligatoires, robustesse par
championnat/saison), et **jamais un résultat positif n'a été obtenu**.
Les pistes techniquement encore exécutables (bookmakers supplémentaires,
autres statistiques de match) appartiennent toutes à des familles déjà
démontrées non informatives par des expériences antérieures portant sur
la même classe de question. La seule piste réellement nouvelle et non
redondante identifiable (classement/forme comme mesure indépendante,
section 3-4) est un fil diagnostique explicitement optionnel, jamais une
recherche d'edge, et ne changerait rien à l'état opérationnel du moteur
même en cas de résultat positif. Continuer à chercher un edge dans ces
mêmes fichiers exposerait le projet à un risque de data dredging pur,
explicitement proscrit par le protocole du projet depuis son origine.

---

## 8. Besoins de données futures (corpus jugé épuisé)

### PRIORITÉ 1 — Données pré-match à forte valeur potentielle

| Information | Pourquoi elle résout une limite actuelle | Expérience future | Risque de fuite | Couverture minimale souhaitable |
|---|---|---|---|---|
| Classement/forme officiels d'un fournisseur **distinct** des résultats bruts déjà utilisés | Seule mesure explicitement identifiée par le projet (E15) comme véritablement indépendante de `poisson_simple`, pour trancher le puzzle Premier League | Réplication du diagnostic E15 avec une mesure de dispersion réellement externe | Faible (publié en continu, bien avant chaque match) | Table à jour à chaque journée, 3 championnats minimum |
| Calendrier complet multi-compétitions (coupes, compétitions européennes) par équipe | Permet enfin un test réel de fatigue/congestion sur données réelles (E1/E7 ne l'ont testé que sur données synthétiques) | Extension de `PoissonModel` avec une covariable de repos, walk-forward, contrôle de recalibration obligatoire (leçon F/G/H) | Faible (calendrier connu à l'avance) | Dates de tous les matchs (toutes compétitions) par équipe, mêmes 3 championnats/2 saisons |
| Compositions officielles avec horodatage de publication documenté | Seule source d'information tactique directe jamais testée ; pourrait, en principe, contenir une information non déjà intégrée par le marché | Comparaison stricte à `p_market` au même instant `T`, jamais après | **Le plus élevé de toute cette liste** (délai probable de quelques dizaines de minutes avec le marché) | Horodatage vérifié indépendamment pour chaque match, pas une hypothèse conservatrice |
| Blessures/suspensions horodatées | Sous-ensemble de l'information de composition | Idem | Idem (élevé) | Idem |
| Second fournisseur de xG (autre qu'Understat) | Teste la sensibilité de `xg_model`/B3 au fournisseur, vérifie si le xG Understat est représentatif | Réplication de B3 avec un fournisseur alternatif | Dépend du fournisseur | Comparable à Understat (mêmes 3 championnats, 2 saisons minimum) |

### PRIORITÉ 2 — Marchés supplémentaires réellement différents

| Information | Pourquoi elle résout une limite actuelle | Expérience future | Risque de fuite | Couverture minimale souhaitable |
|---|---|---|---|---|
| Lignes O/U supplémentaires (0.5/1.5/3.5/4.5) chez un nouveau fournisseur | Seule ligne 2.5 actuellement testable ; empêche toute validation de marché sur les seuils déjà affichés (0.5/1.5/3.5/4.5, calculables mais non comparables à un prix) | Réplication d'E11 étendue à ces lignes | Dépend de la garantie d'horodatage du fournisseur | Au moins une ligne adjacente (1.5 ou 3.5), mêmes championnats |
| Bookmakers structurellement différents (marchés asiatiques dédiés, réputés « sharps ») | Tous les bookmakers actuellement lus (B365, BW, PS, WH, LB, BFD, 1XB, BMGM, BV, CL) sont des bookmakers occidentaux à marge fixe classique — jamais un panel structurellement différent | Réplication E9/E13/Phase G | Dépend du fournisseur | Comparable aux 3 championnats/2 saisons actuels |

### PRIORITÉ 3 — Historique supplémentaire

| Information | Pourquoi elle résout une limite actuelle | Expérience future | Risque de fuite | Couverture minimale souhaitable |
|---|---|---|---|---|
| Saisons supplémentaires de Premier League spécifiquement | Puissance statistique accrue pour trancher le puzzle E15 (absence de discrimination confirmée mais inexpliquée) — **jamais présentée comme garantissant un résultat différent** (section 9) | Réplication ciblée du diagnostic E15 | Faible (même pipeline) | Au moins 2-3 saisons supplémentaires de Premier League |
| Nouveaux championnats (pas plus de saisons des 3 déjà couverts) | Teste la généralisabilité de `poisson_simple` hors Liga/Ligue1/PL, étend le gate de discrimination | Audit E15-like complet avant tout usage en production (déjà exigé par `final_engine_specification.md` §9) | Faible | Audit complet avant intégration, jamais un usage par défaut |

### PRIORITÉ 4 — Données de mouvement/liquidité du marché

| Information | Pourquoi elle résout une limite actuelle | Expérience future | Risque de fuite | Couverture minimale souhaitable |
|---|---|---|---|---|
| Flux d'odds horodaté à haute fréquence (pas seulement ouverture/clôture) | E16 n'a testé qu'un mouvement binaire ; résoudrait la réserve `TIMESTAMP_STATUS_HYPOTHETICAL`, jamais vérifiée indépendamment | Réplication d'E16 à granularité fine | **Élevé** si l'horodatage n'est pas garanti indépendamment | Historique horodaté pour n≥30 par sous-groupe minimum |
| Profondeur/volume d'un carnet d'ordres d'échange (Betfair Exchange) | BFE n'a été testé que sur son **prix** (Phase G) ; jamais sur son volume ou l'asymétrie de son carnet, une dimension d'information distincte du prix seul | Extension du protocole Phase G au volume/profondeur | Modéré, dépend de la disponibilité historique | Comparable à la couverture prix BFE déjà mesurée (~97%) |

---

## 9. « Plus de données identiques » ≠ « nouvelle information »

Distinction stricte, imposée par l'énoncé : ajouter des saisons
supplémentaires des trois championnats déjà couverts (Liga, Ligue 1,
Premier League) **n'est pas**, en général, une nouvelle information — les
20 tests déjà menés (E1-E16, Phases D/F/G/H) ont produit, dans l'immense
majorité des cas, des conclusions cohérentes entre les deux saisons
disponibles (jamais un renversement de signe sur le verdict global). Cela
suggère que les verdicts négatifs déjà obtenus ne sont pas de simples
artefacts de sous-puissance qu'un plus grand échantillon inverserait
mécaniquement — ajouter des saisons identiques produirait, très
probablement, la **même conclusion avec un intervalle de confiance plus
étroit**, pas une conclusion différente.

**Exception ciblée, déjà identifiée par le projet lui-même** : des saisons
supplémentaires de Premier League *spécifiquement* auraient une valeur
réelle pour trancher le puzzle E15 (absence de discrimination confirmée
mais inexpliquée) — non pas parce que plus de données est automatiquement
plus informatif, mais parce que ce diagnostic précis reste sous-déterminé
avec une seule mesure indépendante testée à ce jour (dispersion des buts
réels, E15, non concluante).

**Une nouvelle information**, au sens de ce document, est une donnée
d'une catégorie **jamais représentée** dans le corpus actuel — un marché
structurellement différent (Priorité 2), une donnée pré-match orthogonale
au marché et aux résultats déjà utilisés (Priorité 1), ou une granularité
de marché jamais mesurée (Priorité 4). Ce n'est **jamais** simplement
« plus de lignes du même fichier CSV ».

---

## 10. Recommandation unique pour la suite

## Recommandation principale : **D — nouvelle source de données pré-match**

**Justification du choix unique.** Les options A (davantage de calcul sur
le corpus actuel) et B (davantage de saisons du même corpus) sont
directement écartées par les sections 6 et 9 : leur rendement attendu est
très faible, et B en particulier reproduirait très probablement les
verdicts déjà obtenus avec une précision accrue, pas une conclusion
différente (exception ciblée Premier League, non bloquante). L'option C
(nouvelle source de marchés) reste théoriquement viable (Priorité 2) mais
appartient à la **même famille conceptuelle** (une transformation ou une
représentation supplémentaire du prix de marché) que quatre expériences
déjà négatives (E9/E13, E16, Phase G, Phase H) — son rendement attendu,
bien que non nul, reste modeste par le même raisonnement que la section 6.

L'option **D** est la seule catégorie de données qui n'a **jamais** été
testée sous aucune forme dans ce projet et qui est **structurellement
orthogonale** à tout ce qui a échoué jusqu'ici : elle ne dérive ni du
prix de marché (jamais informatif au-delà de ce qui est déjà capturé),
ni des statistiques du match lui-même (disponibles trop tard pour être un
feature légitime). Une donnée pré-match véritablement nouvelle
(composition, calendrier de congestion, classement indépendant) est la
seule catégorie qui pourrait, en principe, échapper au schéma de
recalibration déjà observé trois fois de suite (F/G/H) — parce qu'elle ne
serait pas, par construction, une nouvelle façon de mesurer une
information déjà présente dans le prix du marché d'ouverture.

**Ce que cela n'implique pas** : que la Priorité 1 produira nécessairement
un résultat positif — le projet a appris, à vingt reprises, à ne jamais
présumer un résultat avant de l'avoir testé selon un protocole
pré-enregistré. Cela signifie seulement que, de toutes les catégories de
données disponibles pour investissement futur, celle-ci a le **meilleur
rapport valeur/coût scientifique** au vu de l'état actuel de la
recherche — en commençant par les items à risque de fuite faible
(calendrier de congestion, classement d'un fournisseur distinct) avant
d'envisager les items à risque de fuite élevé (compositions, blessures).

---

## 11. Critères imposés à toute future nouvelle source de données

Avant toute acquisition ou intégration d'une nouvelle source (Priorités
1-4), la source candidate devra satisfaire, sans exception :

1. **Horodatage documenté et vérifiable** de chaque donnée
   (`knowledge_time`), au moins aussi explicite que la règle conservatrice
   déjà en vigueur pour Football-Data (`TIMESTAMP_STATUS_HYPOTHETICAL`) —
   une source sans garantie d'horodatage documentée n'est **jamais**
   intégrée, quelle que soit sa valeur informationnelle apparente.
2. **Couverture mesurée avant toute expérience** — jamais supposée à
   partir de la documentation du fournisseur seule (leçon de cet audit :
   trois bookmakers jamais documentés ont été découverts par inspection
   directe des fichiers déjà présents).
3. **Une seule variable nouvelle par expérience** (discipline appliquée
   sans exception depuis les Phases F/G/H) — jamais plusieurs nouvelles
   sources testées simultanément dans une même expérience.
4. **Contrôle de recalibration obligatoire** inclus **dès la conception**
   du protocole (jamais ajouté après un premier résultat trompeur) —
   discipline désormais non négociable, établie indépendamment par les
   Phases F, G et H.
5. **Protocole pré-enregistré et verrouillé avant toute lecture de
   résultat réel** — mêmes exigences que toutes les expériences
   précédentes (définition mathématique complète, hypothèses,
   population, critères de validation/rejet à 5 valeurs, verrouillage
   avant exécution).
6. **Distinction stricte des trois questions** (calibration probabiliste,
   information incrémentale, rentabilité opérationnelle) — jamais une
   amélioration de Brier interprétée comme une preuve de rentabilité.
7. **Tests unitaires et anti-fuite écrits et exécutés avant toute
   exécution sur données réelles** — même discipline que toutes les
   expériences précédentes.
8. **Aucune intégration au moteur de production** sans un verdict
   `VALIDÉ` explicite, robuste par championnat/saison, avec IC95%
   entièrement favorable — jamais une intégration anticipée sur la base
   d'un résultat prometteur mais non conclu.

---

## 12. Conclusion

**État scientifique** : recherche exhaustive sur le corpus Football-Data
(20 tests indépendants), toutes les pistes de marché et de signal
additionnel accessibles avec les données actuelles sont soit épuisées,
soit d'un intérêt marginal attendu trop faible pour justifier une
nouvelle expérience, soit structurellement impossibles avec ces données.

**Moteur** : reste `GELÉ` dans son état actuel (MVP Phase B) —
`min_edge_threshold=None`, `BET` non activé, aucun modèle modifié.

**Corpus actuel** : `CORPUS FOOTBALL-DATA — PISTES SCIENTIFIQUEMENT
ÉPUISÉES` pour la question de l'edge de pari.

**Prochaine étape recommandée** : acquisition ciblée d'une nouvelle
source de données pré-match (Priorité 1, section 8), en commençant par
les items à risque de fuite faible, sous réserve du respect intégral des
critères de la section 11 — aucune expérience supplémentaire n'est
entreprise sur les fichiers Football-Data actuels tant qu'une telle
source n'est pas acquise et documentée.

**Arrêt.** Conformément à l'instruction explicite de la Phase I, ce
document est un audit stratégique, pas une expérience. Aucune expérience
supplémentaire n'est lancée à sa suite — la décision d'acquérir une
nouvelle source de données reste entièrement à la discrétion de
l'utilisateur.
