# Audit stratégique des voies d'amélioration (Phase E)

**Nature de ce document.** Audit documentaire pur. Aucun code exécuté,
aucun backtest lancé, aucune expérience E17, aucun modèle modifié, aucun
seuil modifié, `BET` non activé, `min_edge_threshold` non touché. Aucune
donnée externe téléchargée. Ce document répond à une seule question :
*existe-t-il une voie scientifiquement justifiée pour rendre le système
réellement exploitable, et si oui laquelle ?*

Documents relus intégralement pour cet audit : `docs/research_synthesis_e1_e16.md`,
`docs/final_engine_specification.md`, `docs/operational_validation_specification.md`,
`docs/operational_validation_report.md` (qui contient, dans sa section
« Pré-enregistrement », le contenu que ce document appelle
`operational_validation_preregistration.md` — aucun fichier séparé de ce
nom n'existe dans le dépôt ; le pré-enregistrement a été intégré
directement au rapport plutôt que publié à part), `docs/final_engine_user_guide.md`,
`docs/architecture.md`, `docs/research_framework.md`. Code inspecté :
`src/sys_foot_quant/final_engine/`, les loaders de `data_engine/market_odds/`,
les primitives de `football_model/` et `market_engine/`, les scripts
E1→E16 et `scripts/run_stage26_phase_d_operational_validation.py`, ainsi
que le contenu **brut** des fichiers Football-Data déjà présents dans le
dépôt (`research/market_odds/football_data/runs/*.csv`) — cette dernière
inspection a produit deux constats concrets non anticipés, détaillés en
section 4.

---

## 1. État actuel

- **E1→E16** : campagne close, verdict `RESEARCH PHASE CLOSED` sur la
  question centrale (existe-t-il un edge démontrable sur le marché
  d'ouverture, exploitable via le désaccord, le mouvement, ou la
  dispersion multi-bookmaker) — posée sous six angles indépendants,
  toujours négative ou contradictoire.
- **Phase A-B** : spécification puis implémentation du MVP du moteur
  final (`src/sys_foot_quant/final_engine/`) — pipeline Prediction →
  Calibration (E7/E8) → Pricing → Market comparison → Qualification
  (scientific + operational gates) → Decision.
- **Phase C** : cadrage méthodologique de la validation opérationnelle
  (`docs/operational_validation_specification.md`).
- **Phase D** : première et seule expérience réelle de validation d'un
  seuil d'edge opérationnel. **Verdict : `NO BET — EDGE NON VALIDÉ`.**
  Les trois candidats pré-enregistrés (`raw_edge≥0.05`, `raw_edge≥0.10`,
  `price_edge≥0.0`) ont tous un profit moyen négatif sur le segment de
  validation, jamais un IC95 % entièrement positif ni supérieur à la
  baseline « marché seul » — rejetés avant même d'atteindre le segment de
  test, qui reste scellé. Résultat le plus explicatif : le sous-ensemble
  de matchs qu'un seuil d'edge sélectionnerait est précisément celui où
  le modèle est **sur-confiant** (p_model moyen ~0.65-0.68 contre une
  fréquence réelle ~0.48-0.49) — confirmation, par simulation directe du
  moteur réel, du mécanisme déjà identifié indépendamment par le
  diagnostic post-E1, E5, E10, E11 et E12.
- **État du moteur** : `min_edge_threshold=None`, `BET` non activé, 1200
  tests verts, commit `ebc875d` poussé. Aucune anomalie technique
  bloquante connue.

Le système sait aujourd'hui, de façon scientifiquement défendable :
projeter une distribution de buts calibrée (E7/E8), la comparer au prix
de marché d'ouverture, et qualifier la confiance de cette projection. Il
ne sait pas, et n'a jamais démontré savoir, transformer cette
qualification en décision de pari rentable.

---

## 2. Ce qui est définitivement épuisé avec le corpus actuel

Chacune des pistes suivantes a été testée, au moins une fois, selon un
protocole pré-enregistré, avec un résultat négatif ou contradictoire net
— les retester sur exactement le même corpus reviendrait à répéter un
test déjà tranché, un risque de data dredging explicitement écarté par
le projet depuis son origine.

| Piste | Expérience(s) | Résultat |
|---|---|---|
| Recalibrer localement la zone [0.6,0.7) d'Over 2.5 | E14 | Amélioration locale démontrée pour `poisson_simple` mais gate de cohérence inter-seuils violé substantiellement ; non stable par championnat. **NON VALIDÉE, ne pas retenter sans nouvelles données.** |
| Chercher un nouveau seuil d'edge sur ce même corpus | Phase D | 3 candidats pré-enregistrés, tous rejetés sur validation ; le mécanisme explicatif (edge élevé = sur-confiance) est structurel, pas un artefact d'échantillonnage isolé. **Relancer une recherche de seuil sur les mêmes données reproduirait exactement le schéma déjà réfuté.** |
| Battre B365 via le désaccord modèle/marché (1X2 ou O/U) | Diagnostic post-E1, E5, E10, E12 | Quatre tests indépendants, jamais un signal favorable ; E12 montre même l'inverse (zones fiables = écarts de prix plus *petits*). **Question posée et tranchée à quatre reprises.** |
| Exploiter la dispersion B365/Pinnacle (ou tout panel de bookmakers réglementés déjà lu) | E9, E13 | Dispersion structurellement trop faible et homogène pour contenir un signal détectable ; 0 arbitrage mathématique sur 1806 matchs. **Épuisé avec ce panel de bookmakers.** |
| Exploiter le mouvement ouverture→clôture | E16 | 4 hypothèses primaires pré-enregistrées, toutes non rejetées après correction Holm-Bonferroni ; le marché d'ouverture contient déjà l'essentiel de l'information détectable. **Épuisé avec les données de clôture actuellement disponibles.** |
| Créer un ensemble de modèles arbitraire (`poisson_simple`/`dixon_coles`/`xg_model`) | Jamais testé — mais la prémisse même (les trois modèles apporteraient des erreurs suffisamment différentes pour qu'une combinaison aide) est directement contredite par E11 (indiscernables en Brier) et par le diagnostic post-E1 (erreurs xG **plus** corrélées au marché, pas moins, que celles de `poisson_simple`) | **Construire un ensemble maintenant serait un choix non justifié par les données, pas une piste non testée légitime — resterait une HYPOTHÈSE FUTURE nécessitant une justification préalable que le corpus actuel ne fournit pas.** |

Un point commun à ces six pistes : chacune interroge une **transformation
du signal déjà présent** dans B365 + résultats + xG (désaccord,
recalibration, dispersion, mouvement, combinaison) — jamais une source
**d'information réellement nouvelle**. C'est cette distinction qui motive
directement la section 4.

---

## 3. Limites structurelles du corpus actuel

- **Couverture temporelle** : 2 saisons (2024/25, 2025/26), 3
  championnats (Liga, Ligue 1, Premier League) — un corpus modeste au
  sens statistique (limites de puissance déjà documentées, section G2 de
  `docs/research_framework.md`), jamais la cause identifiée d'un edge
  manqué, mais une contrainte sur la capacité à détecter un effet petit
  s'il existait.
- **Un seul marché O/U réellement couvert** : Football-Data.co.uk ne
  publie l'Over/Under que sur la ligne **2.5** — vérifié directement
  ici, dans l'en-tête brut des fichiers déjà présents dans le dépôt
  (`research/market_odds/football_data/runs/*.csv`) : aucune colonne
  `>0.5`/`<0.5`, `>1.5`/`<1.5`, `>3.5`/`<3.5` ni `>4.5`/`<4.5` n'existe,
  pour aucun bookmaker, dans aucun des six fichiers. Ce n'est pas une
  limite du code du projet — c'est une limite de la source de données
  elle-même.
- **Timestamp jamais vérifié** : toute la chaîne d'appariement
  cote/décision repose sur `TIMESTAMP_STATUS_HYPOTHETICAL`
  (`conservative_knowledge_time_utc`) — une hypothèse conservatrice
  documentée depuis E1, jamais un fait vérifié indépendamment.
- **Aucune donnée de composition d'équipe, de blessure, ou de joueur
  individuel** n'est actuellement lue par le projet, alors même que
  certaines statistiques de match (voir section 4) sont déjà présentes
  dans les fichiers sources sans avoir jamais été exploitées.
- **Un seul type de marché structurel** : uniquement des bookmakers à
  marge (B365, BW, PS, WH, LB) ont été lus jusqu'ici — aucune donnée
  d'exchange n'a été intégrée, alors qu'elle existe déjà dans les
  fichiers (section 4).

---

## 4. Nouvelles sources possibles

Deux catégories bien distinctes émergent de cet audit — une distinction
volontairement mise en évidence, car elle change radicalement le coût
d'accès :

### 4.A — Déjà présentes dans les fichiers actuels, jamais lues (coût quasi nul)

Une inspection directe de l'en-tête des fichiers Football-Data déjà
présents dans le dépôt révèle des colonnes **jamais incluses** dans
`_ALLOWED_COLUMNS`/`_OPTIONAL_COLUMNS` de `football_data_loader.py` :

**(a) Cotes agrégées multi-bookmakers `Max>2.5`/`Max<2.5`,
`Avg>2.5`/`Avg<2.5`** (et leurs pendants 1X2 `Max`/`Avg`).

1. *Information nouvelle* : un agrégat (max et moyenne) calculé par
   Football-Data lui-même sur un panel de bookmakers **plus large** que
   les 5 déjà lus par ce projet (B365/BW/PS/WH/LB) — potentiellement
   plusieurs dizaines de bookmakers non identifiés individuellement.
2. *Orthogonalité potentielle* : E9/E13 ont montré que la dispersion
   entre les 5 bookmakers actuellement lus est trop faible et homogène
   pour être informative — mais ce panel restreint (tous des bookmakers
   réglementés « grand public ») pourrait ne pas représenter la
   dispersion d'un panel plus large incluant des bookmakers plus
   spécialisés ou moins alignés. Reste à vérifier, pas à supposer.
3. *Hypothèse testable* : « le consensus `Avg` sur un panel élargi
   discrimine-t-il mieux, ou diverge-t-il du panel B365/BW/PS/WH/LB déjà
   lu, d'une façon qui reproduirait ou contredirait le résultat déjà
   négatif d'E9/E13 ? » — une réplication à effectif de panel plus large,
   pas une nouvelle famille d'hypothèse.
4. *Intégration sans fuite* : triviale — même mécanisme point-in-time
   déjà utilisé pour B365/BW/PS (ouverture uniquement, `Max`/`Avg`
   n'ayant pas de statut différent de `Max2.5`/`Avg2.5` déjà présents).
5. *Mesure de la valeur incrémentale* : reproduire exactement le
   protocole déjà pré-enregistré d'E9/E13 (dispersion, anomalie,
   arbitrage) avec ce panel élargi comme unique nouveauté.

**(b) Cotes d'échange `BFEH/D/A`, `BFE>2.5/<2.5` (Betfair Exchange) et
`BFDH/D/A` (une seconde cotation Betfair)** — déjà repérées et
**explicitement exclues sans être lues** en E9 (« nature d'exchange non
clarifiée, décision différée »), jamais réexaminées depuis.

1. *Information nouvelle* : un prix formé par un **carnet d'ordres**
   (offre/demande entre parieurs), pas par une marge de bookmaker fixe —
   un mécanisme de formation de prix structurellement différent de tout
   ce qui a été testé jusqu'ici (E1-E16 n'ont jamais examiné un marché
   sans marge fixe).
2. *Orthogonalité potentielle* : un exchange peut, en principe, réagir
   différemment (plus vite, ou porté par des flux d'ordres différents)
   qu'un bookmaker à marge — c'est précisément le type de « marché
   structurellement différent » que l'Option C de la section 9 envisage,
   et il est **déjà dans les fichiers du dépôt**.
3. *Hypothèse testable* : « le prix Betfair Exchange diverge-t-il
   systématiquement du consensus bookmaker d'une façon associée à la
   fréquence réelle du résultat ? » (réplication du protocole E9/E10,
   jamais un nouveau design).
4. *Intégration sans fuite* : nécessite une clarification préalable
   documentée par une ADR (dans l'esprit de l'ADR 0006) sur la
   sémantique exacte de `BFEH`/`BFDH` (une seule cotation exchange ou
   deux échantillonnages différents ? à quel instant ?) avant toute
   lecture — ce travail de clarification n'a jamais été fait, contexte
   qui explique pourquoi E9 avait prudemment exclu ces colonnes plutôt
   que de les lire sans les comprendre.
5. *Mesure de la valeur incrémentale* : comparaison directe au
   consensus bookmaker déjà lu (E9/E10 étendus), jamais une conclusion de
   rentabilité isolée.

**(c) Handicap asiatique (`AHh`, `B365AHH/AHA`, `PAHH/PAHA`,
`MaxAHH/AHA`, `AvgAHH/AHA`, `BFEAHH/AHA`)** — un marché **entier**,
jamais mentionné dans aucune expérience E1-E16, déjà présent dans les
mêmes fichiers.

1. *Information nouvelle* : un marché structurellement différent du 1X2
   et de l'Over/Under (une ligne de handicap continue, souvent perçue
   comme le marché le plus « efficient » par les parieurs professionnels
   — une affirmation qualitative, jamais vérifiée par ce projet).
2. *Orthogonalité potentielle* : le handicap asiatique combine
   information de force relative (proche du 1X2) et un mécanisme de
   remboursement partiel selon la ligne — sa relation exacte à `p_model`
   n'a jamais été établie ici et n'est pas triviale à dériver de la seule
   distribution de buts.
3. *Hypothèse testable* : uniquement après un travail de modélisation
   préalable (dériver une probabilité de handicap asiatique à partir de
   la même matrice de score E7/E8 — une extension mathématique non
   triviale mais faisable, jamais tentée) — l'hypothèse elle-même
   resterait à formuler précisément avant tout test.
4. *Intégration sans fuite* : même mécanisme point-in-time, aucun
   obstacle technique nouveau.
5. *Mesure de la valeur incrémentale* : à définir avec le nouveau
   protocole de dérivation (point 3 ci-dessus) avant toute exécution.

**(d) Statistiques de match déjà présentes (`HS`/`AS` tirs, `HST`/`AST`
tirs cadrés, `HC`/`AC` corners, `HF`/`AF` fautes, `HY`/`AY`/`HR`/`AR`
cartons, `Referee`)** — disponibles dans les mêmes fichiers depuis le
début du projet, jamais lues.

1. *Information nouvelle* : des statistiques de match **agrégées**,
   analogues en esprit au xG déjà utilisé par `xg_model` (B3), mais issues
   d'une source différente (Football-Data plutôt qu'Understat) et
   disponibles pour un historique potentiellement plus long/plus large
   que le xG Understat actuel.
2. *Orthogonalité potentielle* : `xg_model` (B3) a montré une
   discrimination réelle sur le total de buts (E4) mais des erreurs
   **plus** corrélées au marché que `poisson_simple` (diagnostic post-E1)
   — un signal alternatif basé sur les tirs/tirs cadrés pourrait, en
   principe, capturer une dimension différente (volume de jeu plutôt que
   qualité d'occasion), mais ceci reste une hypothèse non testée, jamais
   une certitude.
3. *Hypothèse testable* : « un modèle d'attaque/défense construit sur
   l'historique de tirs cadrés (au lieu des buts ou du xG) discrimine-t-il
   le total de buts d'une façon non déjà capturée par `poisson_simple`/
   `xg_model` ? » — une extension directe et méthodologiquement balisée
   du protocole déjà utilisé pour construire `xg_model` (B3).
4. *Intégration sans fuite* — **point critique, à traiter avec un soin
   particulier** : `HS`/`HST`/etc. sont des statistiques **du match
   lui-même**, connues seulement **après** le coup d'envoi (comme
   `FTHG`/`FTAG`) — **jamais utilisables comme feature du match qu'elles
   décrivent**, seulement comme entrée de l'historique **d'un match
   antérieur** pour construire une force d'équipe walk-forward (exactement
   la même discipline que `home_goals`/`away_goals` ou `home_xg`/`away_xg`
   aujourd'hui). Un nouveau modèle de ce type devrait suivre exactement
   le patron déjà validé de `xg_model.py`.
5. *Mesure de la valeur incrémentale* : réplication directe du protocole
   de complémentarité déjà utilisé pour B3 (corrélation des erreurs avec
   le marché et avec `poisson_simple`, jamais une conclusion de
   rentabilité isolée).

**Conséquence de 4.A** : avant d'envisager l'acquisition d'un nouveau
fournisseur de données, il existe un travail à coût quasi nul (aucune
nouvelle donnée à acquérir, seulement à lire et tester) qui n'a jamais
été fait. Ceci est développé comme recommandation principale en section
10.

### 4.B — Nécessitent un nouveau fournisseur de données

| Source | Info nouvelle | Orthogonalité potentielle | Hypothèse testable | Intégration sans fuite | Mesure incrémentale |
|---|---|---|---|---|---|
| Lignes O/U supplémentaires (0.5/1.5/3.5/4.5) chez un autre fournisseur | Prix de marché sur des lignes actuellement invisibles | Élevée si le fournisseur diffère de B365 — mais reste à vérifier, pas à supposer | « La distribution E7/E8 est-elle mieux/moins bien calibrée que le marché sur ces lignes que sur 2.5 ? » | Même mécanisme point-in-time, à condition que le nouveau fournisseur documente une règle de connaissance temporelle aussi explicitement que Football-Data (jamais garanti a priori) | Réplication du protocole E11 étendu à ces lignes |
| Bookmakers structurellement différents (marchés asiatiques, marchés de niche) | Prix formés par une base de parieurs différente | Potentiellement élevée (littérature externe au projet suggère une efficience variable selon les marchés — jamais vérifiée ici) | « Ce panel diverge-t-il du consensus B365/BW/PS d'une façon associée au résultat réel ? » | Dépend entièrement de la documentation temporelle du nouveau fournisseur — risque principal de toute cette catégorie | Réplication E9/E13 |
| Compositions officielles / probables | Information tactique directe (qui joue) | Potentiellement élevée si publiée suffisamment tôt et non déjà intégrée par le marché | « La composition connue à `T` change-t-elle la probabilité de buts au-delà de ce que le marché à `T` reflète déjà ? » | **Risque de fuite le plus élevé de cette liste** — voir section 7 | Comparaison à `p_market` au même instant `T`, jamais après |
| Blessures/suspensions | Sous-ensemble de l'information de composition | Idem | Idem | Idem (section 7) | Idem |
| xG/tirs/possession **individuels** (joueur par joueur) | Granularité plus fine que l'agrégat d'équipe | Incertaine — la littérature externe est partagée ; jamais testée dans ce projet | Nécessiterait d'abord un modèle team-level dérivé d'agrégats joueurs, une construction non triviale | Risque de fuite si les données individuelles post-match sont mal séparées de l'information pré-match disponible | À définir après construction du modèle |
| Saisons supplémentaires (mêmes 3 championnats) | Voir section 8 — **puissance, pas information nouvelle en général** | Faible pour la plupart des hypothèses déjà tranchées ; utile spécifiquement pour la Premier League (E15) | Voir section 8 | Aucun obstacle technique nouveau | Réplication directe des protocoles déjà pré-enregistrés |

---

## 5. Matrice comparative

| Piste | Nouvelle information ? | Potentiel théorique | Risque leakage | Coût/complexité | Priorité |
|---|---|---|---|---|---|
| Recalibrer O2.5 [0.6,0.7) à nouveau | Non | Nul sur ce corpus (E14 tranché) | — | — | 🔴 |
| Nouveau seuil d'edge sur le même corpus | Non | Nul (Phase D tranché) | — | — | 🔴 |
| Redémontrer le désaccord modèle/marché comme signal | Non | Nul (4 tests indépendants) | — | — | 🔴 |
| Dispersion B365/Pinnacle/WH/LB | Non | Nul (E9/E13 tranché) | — | — | 🔴 |
| Mouvement ouverture/clôture (données actuelles) | Non | Nul (E16 tranché) | — | — | 🔴 |
| Ensemble arbitraire des 3 modèles | Non (prémisse déjà contredite) | Non justifié sans nouvelle preuve | Faible techniquement | Faible | 🔴 |
| Cotes `Max`/`Avg` (panel élargi, déjà dans les fichiers) | Oui (panel plus large) | Incertain, jamais mesuré | Faible (même mécanisme que B365) | **Très faible** (lecture de colonnes déjà présentes) | 🟢 |
| Betfair Exchange (`BFE`/`BFD`, déjà dans les fichiers) | Oui (mécanisme de prix différent) | Incertain mais structurellement distinct | Moyen (sémantique non clarifiée) | **Faible** (données présentes, clarification à documenter) | 🟢 |
| Statistiques de match (tirs/tirs cadrés/corners, déjà dans les fichiers) | Oui (signal alternatif au xG) | Incertain, jamais mesuré | Faible si discipline walk-forward respectée (comme B3) | **Faible** (données présentes, construction analogue à `xg_model`) | 🟢 |
| Handicap asiatique (déjà dans les fichiers) | Oui (marché entier) | Incertain | Faible | Moyen (dérivation mathématique à construire) | 🟡 |
| Lignes O/U supplémentaires (nouveau fournisseur) | Oui | Incertain | Dépend du fournisseur | Élevé (nouvelle source, nouvelle ADR point-in-time) | 🟡 |
| Bookmakers/marchés structurellement différents (nouveau fournisseur) | Oui | Incertain | Dépend du fournisseur | Élevé | 🟡 |
| Compositions/blessures officielles | Oui | Incertain, risque de redondance avec le marché | **Élevé** (section 7) | Élevé | ⚪ |
| xG/statistiques individuelles par joueur | Oui | Incertain | Élevé si mal séparé | Élevé | ⚪ |
| Saisons supplémentaires (mêmes championnats) | Non en général ; utile ciblé sur la PL (E15) | Puissance, pas signal nouveau | Faible | Faible à moyen (dépend de la disponibilité) | 🟡 (ciblé uniquement) |

Aucun score numérique n'est attribué : la colonne « Priorité » reflète un
jugement qualitatif fondé sur les colonnes précédentes, pas une moyenne
pondérée qui prétendrait à une précision non justifiable.

---

## 6. Analyse O/U multi-lignes

Disposer de prix sur plusieurs lignes (0.5/1.5/2.5/3.5/4.5) permettrait,
en principe, de tester des questions **actuellement impossibles** faute
de prix de marché sur ces lignes :

- **Cohérence croisée du marché lui-même** : le marché est-il, comme le
  moteur E7/E8, structurellement cohérent entre les lignes (monotonicité
  implicite), ou existe-t-il des micro-incohérences entre lignes chez un
  même bookmaker (un signal théoriquement différent de tout ce qui a été
  testé — jamais un désaccord modèle/marché, mais un désaccord du marché
  **avec lui-même**) ?
- **Calibration relative par ligne** : E11 a montré une calibration
  fiable du modèle sur 1.5/2.5/3.5 mais des tranches insuffisamment
  peuplées sur 0.5/4.5 — un prix de marché sur ces lignes permettrait
  enfin la comparaison actuellement impossible (section 7 de
  `docs/final_engine_specification.md` le signale déjà comme limite).
- **Structure de marge par ligne** : la marge bookmaker n'est peut-être
  pas uniforme sur toutes les lignes (hypothèse plausible mais jamais
  vérifiée dans ce projet) — une marge variable pourrait révéler quelles
  lignes le bookmaker considère comme plus incertaines, une information
  indirecte sur sa propre confiance.

**Ce que cela ne permettrait PAS de conclure automatiquement** : qu'un
edge existe sur ces lignes. E1-E16 ont précisément montré, à réitérées
reprises, qu'une information de marché supplémentaire (multi-bookmaker,
mouvement) n'a **jamais** produit de signal exploitable sur ce projet —
il n'y a aucune raison structurelle de supposer qu'une ligne
supplémentaire échapperait à ce schéma. La valeur de cette piste est
d'**élargir le champ de ce qui est mesurable**, pas de présumer un
résultat.

---

## 7. Analyse données joueurs / compositions

**`team-level model → player-level information`** — évaluation séparée,
comme demandé.

**Ce qui pourrait apporter une information complémentaire réelle** :
l'absence d'un attaquant clé, une rotation massive (rencontre européenne
la veille), ou un changement tactique connu pourraient en principe
affecter l'espérance de buts d'une façon que ni `poisson_simple` (qui
suppose une force d'équipe stable) ni le marché n'intègrent
instantanément — mais cette dernière hypothèse (le marché n'intègre pas
instantanément) est **précisément le type d'affirmation que ce projet a
appris à ne jamais accepter sans preuve** (le marché s'est révélé, sur
toutes les dimensions testées, au moins aussi informé que le modèle).

**Le problème crucial, non négociable** : toute donnée de composition
doit être disponible **avant** l'instant exact de décision
(`decision_time = kickoff_utc − DECISION_OFFSET_HOURS`, actuellement 2
heures). Or :

- Les **compositions officielles** sont typiquement publiées environ 1
  heure avant le coup d'envoi — **après** `decision_time` tel que
  configuré aujourd'hui. Les utiliser nécessiterait soit de réduire
  `DECISION_OFFSET_HOURS` (une modification de paramètre déjà utilisé
  par tout le moteur, à ne jamais faire sans une justification et une
  validation dédiées — hors périmètre de cette piste elle-même), soit de
  les exclure purement et simplement comme feature de décision à
  l'horizon actuel.
- Les **compositions probables** (media, sites spécialisés) sont
  disponibles plus tôt mais **ne sont pas garanties correctes** — les
  traiter comme un fait serait une fuite d'un autre type (une confiance
  non justifiée dans une prédiction externe, pas un vrai fait connu à
  `T`).
- **Une composition publiée après le moment de décision ne peut jamais
  être utilisée pour une décision antérieure** — ce principe, déjà au
  cœur de toute la discipline point-in-time du projet depuis l'étape 1,
  s'applique ici avec une acuité particulière car le décalage entre
  disponibilité de la donnée et disponibilité du prix de marché est
  probablement **très court** (souvent quelques dizaines de minutes) —
  rendant le risque de fuite subtile (off-by-a-few-minutes) plus élevé
  que pour n'importe quelle autre source déjà utilisée par ce projet.

**Conclusion pour cette piste** : théoriquement non exclue, mais classée
⚪ (impossible à évaluer sans un fournisseur documentant précisément
l'horodatage de publication de chaque composition) — et son risque de
fuite structurel est le plus élevé de toutes les pistes examinées dans ce
document. Elle ne doit être envisagée qu'après qu'un fournisseur propose
une garantie d'horodatage au moins aussi explicite que celle
(déjà hypothétique) de Football-Data.

---

## 8. Analyse nouvelles saisons

**Ce que des saisons supplémentaires apporteraient** : de la **puissance
statistique**, pas de l'information nouvelle en général. Les tests déjà
menés (E1-E16, Phase D) sur 2 saisons ont, dans l'immense majorité des
cas, produit des conclusions cohérentes entre les deux saisons
disponibles (jamais un renversement de signe) — ce qui suggère que les
verdicts négatifs déjà obtenus ne sont pas de simples artefacts de
sous-puissance qu'un plus grand échantillon inverserait mécaniquement.

**Exception ciblée, déjà identifiée par le projet lui-même** : E15
propose explicitement, comme piste future non testée, une mesure
**indépendante** de la dispersion du niveau des équipes en Premier
League (classement final, différentiel de buts par équipe) pour trancher
le puzzle « absence de discrimination confirmée mais inexpliquée ». Des
saisons supplémentaires de Premier League **spécifiquement** pourraient
avoir une valeur réelle ici — non pas parce que plus de données est
automatiquement plus informatif, mais parce que ce diagnostic précis
reste à ce jour sous-déterminé (une seule mesure indépendante testée à
ce jour, la dispersion des buts réels, s'est révélée non concluante).

**Ne jamais présenter** l'ajout de saisons comme une garantie de
résultat différent — la discipline du projet (résultat négatif accepté
comme valide, jamais réinterrogé sans nouvelle justification) s'applique
également ici.

---

## 9. Options stratégiques A→E

| Option | Description | Évaluation |
|---|---|---|
| **A — Continuer à améliorer le modèle de buts** | Nouveaux signaux team-level (tirs/tirs cadrés, section 4.A.d), éventuellement une piste de dispersion réelle pour la Premier League (section 8) | Coût le plus faible (données déjà présentes pour 4.A.d), mais l'historique du projet (aucune extension testée — A2/B1/B2/B3/B3.2/B3.3 — n'a démontré de supériorité substantielle sur `poisson_simple`) invite à des attentes mesurées, pas nulles |
| **B — Chercher une information exogène au marché des cotes** | Compositions/blessures (section 7), statistiques de match déjà présentes (section 4.A.d) | La sous-piste "statistiques déjà présentes" est peu coûteuse et bien balisée méthodologiquement ; la sous-piste "compositions/blessures" porte le risque de fuite le plus élevé de tout ce document et nécessite un nouveau fournisseur documenté |
| **C — Chercher un marché/bookmaker structurellement différent** | Betfair Exchange (déjà dans les fichiers, section 4.A.b), bookmakers/marchés externes (nouveau fournisseur) | La sous-piste "déjà dans les fichiers" est la plus actionnable immédiatement de toute cette liste — coût quasi nul, jamais tentée |
| **D — Changer d'univers de marché (lignes O/U supplémentaires)** | Nécessite un nouveau fournisseur (Football-Data ne les publie pas) ; le handicap asiatique est une variante déjà disponible dans les fichiers actuels | Potentiel réel mais non garanti (section 6) ; coût variable selon la sous-option choisie |
| **E — Conclure que le corpus actuel ne permet pas de construire un moteur BET fiable** | Position par défaut légitime si aucune des options A-D n'est retenue | **Ce n'est pas la conclusion de cet audit** — des pistes à coût quasi nul et jamais testées existent encore (section 4.A) ; l'Option E resterait la conclusion honnête si ces pistes échouaient aussi, mais il serait prématuré de s'y résoudre avant de les avoir tentées |

Ces options ne sont **pas classées par promesse de rendement** (aucune
n'a de rendement démontré) mais par le rapport entre ce qu'elles
coûtent à explorer et ce qu'elles pourraient, en principe, révéler.

---

## 10. Recommandation principale — une seule prochaine étape

### Étape recommandée

**Étendre `football_data_loader.py` pour lire les colonnes déjà
présentes dans les fichiers actuels mais jamais exploitées — cotes
`Max`/`Avg` (consensus élargi), cotes Betfair Exchange (`BFE`/`BFD`), et
statistiques de match (`HS`/`AS`/`HST`/`AST`/`HC`/`AC`) — puis mener
**une seule** expérience diagnostique dédiée aux statistiques de match
comme signal alternatif d'attaque/défense (la sous-piste au potentiel le
mieux balisé, car structurellement identique au protocole déjà validé de
`xg_model`/B3).**

Cette étape ne nécessite **aucune acquisition de nouvelle donnée** — les
fichiers sont déjà dans le dépôt. C'est délibérément l'étape la moins
coûteuse de tout cet audit, et elle n'a, à ce jour, jamais été tentée.

### 1. Hypothèse scientifique

Un modèle d'attaque/défense construit sur l'historique de tirs cadrés
(`HST`/`AST`) discrimine-t-il le total de buts d'un match futur d'une
façon qui ne soit pas déjà capturée par `poisson_simple` (buts réels) ni
par `xg_model` (xG Understat) — mesuré par une corrélation d'erreurs plus
faible avec le marché que celle déjà observée pour `xg_model`
(diagnostic post-E1 : +0.845, la plus forte des trois séries testées) ?

### 2. Donnée nécessaire

`HS`/`AS`/`HST`/`AST` (tirs et tirs cadrés, domicile/extérieur) —
**déjà présents** dans `research/market_odds/football_data/runs/*.csv`
pour les six fichiers déjà utilisés par le projet. Aucune acquisition.

### 3. Pourquoi cette donnée est nouvelle

Jamais lue ni utilisée par aucune des seize expériences E1-E16, ni par
le moteur final. Source différente d'Understat (xG), donc potentiellement
porteuse d'un bruit de mesure différent — une condition nécessaire (pas
suffisante) pour capturer une information non redondante.

### 4. Risque principal

Que les tirs cadrés soient, comme le xG avant eux, **plus corrélés au
marché** que `poisson_simple` plutôt que moins — reproduisant exactement
le résultat déjà obtenu pour `xg_model` dans le diagnostic post-E1. Ce
risque n'est pas un défaut du protocole ; c'est précisément la question
posée, et une réponse négative resterait un résultat valide, comme
chacun des seize résultats négatifs déjà acceptés par ce projet.

### 5. Protocole de validation futur (décrit, pas exécuté)

Reproduire **exactement** le protocole déjà utilisé pour construire et
évaluer `xg_model` (B3) et le diagnostic post-E1 (partie 5-6) :
walk-forward strict (mêmes `DECISION_OFFSET_HOURS`/`MIN_TRAIN_MATCHES`,
inchangés), construction d'un modèle d'attaque/défense sur l'historique
de tirs cadrés (forme mathématique identique à `xg_model.py`, source de
données différente uniquement), puis comparaison de la corrélation
d'erreurs avec le marché et avec `poisson_simple`/`xg_model` — jamais une
conclusion de rentabilité, jamais un nouveau seuil, jamais une
intégration en production avant une validation complète et un rapport
dédié, selon la même discipline que toutes les expériences précédentes
(protocole écrit et gelé avant exécution, tests écrits avant les
données réelles, verdict accepté quel qu'il soit).

### 6. Critère d'abandon

Si la corrélation des erreurs du nouveau modèle avec le marché est égale
ou supérieure à celle déjà mesurée pour `xg_model` (+0.845) — reproduisant
le schéma déjà observé où une source de données alternative se rapproche
du marché plutôt que de s'en écarter —, la piste est abandonnée
définitivement pour ce type de statistique, sans nouvelle tentative de
reparamétrage, exactement comme E14/Phase D ont été closes sans
recherche d'un nouveau seuil après un résultat négatif.

---

## 11. Décision de gel du moteur

**`FREEZE`.**

Le moteur (`src/sys_foot_quant/final_engine/`) reste gelé dans son état
actuel : `min_edge_threshold=None`, `BET` non activé, aucun modèle
modifié, aucun seuil modifié. Aucune modification du moteur n'est
justifiée dans le seul but de produire davantage de décisions `BET` —
seule la découverte d'une source de signal réellement nouvelle et
validée selon un protocole pré-enregistré justifierait de réexaminer
cette position, et une telle découverte, si elle survient, ferait
l'objet d'une phase dédiée ultérieure, jamais d'une modification directe
du moteur à l'occasion d'une exploration.

---

## Résumé exécutif

Le corpus actuel a été interrogé de façon approfondie et honnête ; six
pistes distinctes sont désormais définitivement épuisées avec ces
données (section 2). Il ne s'ensuit pas que la recherche doive s'arrêter
purement et simplement (Option E) : une inspection directe des fichiers
déjà présents dans le dépôt révèle plusieurs colonnes jamais lues
(consensus multi-bookmaker élargi, cotes d'échange Betfair, statistiques
de match) qui n'ont **jamais** été soumises à un protocole de test,
alors qu'elles ne nécessitent aucune acquisition de données
supplémentaire. La recommandation de cet audit est donc de commencer par
ce travail à coût quasi nul avant d'envisager l'acquisition de tout
nouveau fournisseur de données (compositions, blessures, lignes O/U
supplémentaires) — des pistes au potentiel réel mais au coût et au
risque de fuite structurellement plus élevés.
