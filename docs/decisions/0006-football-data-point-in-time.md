# ADR 0006 - Cotes reelles Football-Data.co.uk : provenance, fuseau horaire et reserve point-in-time

## Statut
Accepte (infrastructure de donnees de marche, phase economique - suite a
la campagne de modelisation A1-C7, close). Concerne
`data_engine/market_odds/`, `market_engine/model_vs_market.py`.

## Contexte
Le depot ne contenait auparavant aucune cote de marche reelle (audit
prealable : seules des cotes synthetiques, `bookmaker="synthetic_book"`,
existaient). Un audit des sources externes disponibles a retenu
**Football-Data.co.uk** (gratuit, couverture exacte des 3 championnats x 2
saisons deja utilises par le corpus Understat) comme source de depart,
avec une reserve explicite : cette source ne publie **aucun horodatage
individuel par cote**, contrairement aux cotes deja utilisees ailleurs
dans le projet (synthetiques, ou issues d'Understat pour les buts/xG).

## Decision

### 1. Perimetre retenu
- Championnats : Ligue 1, Premier League, Liga - saisons 2024/25 et
  2025/26 uniquement (memes six fichiers que le corpus Understat, aucune
  saison supplementaire).
- Marche : 1X2 uniquement.
- Bookmaker : **Bet365 (`B365H`/`B365D`/`B365A`) uniquement** - le seul
  bookmaker complet a 100% (0 valeur manquante) sur les six fichiers.
  D'autres bookmakers presents dans les fichiers sources (`BW`, `PS`,
  `BFE`, et des colonnes propres a chaque saison) ne sont PAS lus par
  `football_data_loader.py` - seule `_ALLOWED_COLUMNS` y figure, testee
  pour ne jamais contenir de colonne de cloture.
- Colonnes explicitement EXCLUES : toute colonne de cloture (suffixe `C`,
  ex. `B365CH`), les agregats de marche (`Max*`, `Avg*`), tout autre
  bookmaker.

### 2. Correspondance des equipes (mapping deterministe)
`data_engine/market_odds/team_mapping.py` associe, a la main, chaque nom
d'equipe Football-Data a son equivalent Understat, verifie individuellement
contre les listes completes des deux sources. Aucun fuzzy matching : une
equipe absente du mapping leve une erreur explicite. `validate_mapping_bijective`
garantit l'absence de collision et la couverture complete des equipes
Understat pertinentes - execute en test pour les trois championnats.

### 3. Fuseau horaire (etabli empiriquement, pas suppose)
En comparant les heures de coup d'envoi des matchs deja apparies par nom
entre les deux sources (donnees deja dans le depot), le decalage observe
(0 ou +60 minutes selon la periode de l'annee) correspond exactement aux
transitions heure d'ete/hiver europeennes, de facon **uniforme sur les
trois championnats** - pas seulement au Royaume-Uni, ce qui exclut
l'hypothese "chaque championnat en heure locale de son pays hote".
**Conclusion retenue** : la colonne `Time` de Football-Data est publiee en
heure civile du Royaume-Uni (Europe/London, GMT/BST) pour les trois
championnats, tandis qu'Understat (`datetime`) est en UTC constant - deja
le choix fait sans verification independante dans
`research/xg_feasibility/understat_source.py`, desormais corrobore
empiriquement. `time_resolution.football_data_kickoff_to_utc` implemente
cette conversion via `zoneinfo("Europe/London")`.

### 4. Regle point-in-time conservatrice (HYPOTHESE DOCUMENTEE, jamais un timestamp verifie)
Football-Data ne publie qu'une politique de collecte generale ("cotes du
week-end collectees le vendredi apres-midi, cotes de semaine le mardi
apres-midi"), jamais un horodatage par ligne. `time_resolution.conservative_knowledge_time_utc`
implemente cette regle avec deux garde-fous explicites :
- la reference n'est **jamais le jour meme du match**, toujours un jour
  calendaire strictement anterieur, pour garantir `knowledge_time <
  kickoff` quelle que soit l'heure de coup d'envoi (verifie par test
  base sur `hypothesis`, ~potentiel de fuite identifie et corrige durant
  le developpement : une premiere version utilisait "le mardi lui-meme"
  pour un match du mardi, ce qui pouvait produire une heure de
  connaissance posterieure au coup d'envoi) ;
- les matchs du **lundi, mardi et vendredi** sont explicitement **exclus**
  (leve `AmbiguousCollectionWindowError`) plutot que rattaches par
  hypothese silencieuse a l'une ou l'autre fenetre documentee - la source
  ne precise pas ces cas.
- 23:59:59 (heure de Londres) est un choix technique deliberement
  conservateur pour fixer une borne, **pas une pretention de connaitre
  l'heure exacte de collecte** - la source ne documente qu'un jour, jamais
  une heure.
- Toute donnee produite par ce module porte, dans son usage ulterieur, la
  distinction entre `TIMESTAMP_STATUS_VERIFIE` et
  `TIMESTAMP_STATUS_HYPOTHETIQUE_DOCUMENTE` - Football-Data.co.uk relevant
  strictement du second cas.

### 5. Interface economique generique (etape 6)
`market_engine/model_vs_market.py::compare_model_to_market` calcule,
pour un match et un marche donnes : probabilite modele, cote marche,
probabilite implicite brute, overround, probabilite implicite normalisee
(retrait de marge proportionnel, reutilise de `overround.py` sans
modification), difference modele-marche. **Ne calcule ni ROI, ni yield, ni
CLV, ni staking, ni seuil de selection** - fonction generique
(`dict[str, float]`), reutilisable pour d'autres marches (Over/Under,
BTTS, ...) sans modification de ce module le jour ou l'un d'eux serait
construit.

## Consequences
- **Aucune conclusion de rentabilite n'a ete tiree a ce stade** - cette
  ADR couvre exclusivement l'infrastructure et la qualite des donnees.
- Appariement final sur le corpus reel : **2123/2132 matchs (99.58%)**.
  Le residu de 9 matchs non apparies (8 en Ligue 1 2025/26, 1 en Liga
  2025/26) est root-cause individuellement (voir
  `tests/leakage/test_football_data_point_in_time.py`) : dans chaque cas,
  Football-Data et Understat datent le meme match a un jour calendaire
  different (ecart de 1 a 2 jours, pas un simple decalage horaire),
  probable reprogrammation TV enregistree differemment par les deux
  sources independantes. Pas resolu par fuzzy-matching de date, conforme a
  la consigne.
- Les matchs du lundi/mardi/vendredi ne peuvent pas recevoir de
  `knowledge_time` conservateur sous la regle actuelle - toute experience
  economique future devra soit les exclure explicitement, soit faire
  l'objet d'une nouvelle decision documentee (jamais silencieuse).
- Toute extension future vers un autre bookmaker ou un autre marche devra
  repartir de `_ALLOWED_COLUMNS` (football_data_loader.py) et non
  l'etendre implicitement.
- **Extension realisee (E5, phase economique)** : `_ALLOWED_COLUMNS`
  etendue a `B365>2.5`/`B365<2.5` (Over/Under 2.5, meme bookmaker B365,
  memes colonnes source non-cloture - `B365C>2.5`/`B365C<2.5` explicitement
  exclues, verifie par test dedie) - completude verifiee a 100% sur les
  six fichiers reels avant l'extension, meme niveau que B365H/D/A. Aucune
  nouvelle regle temporelle : le meme mecanisme point-in-time (fuseau
  horaire, regle de connaissance conservatrice, exclusion
  lundi/mardi/vendredi) s'applique identiquement, les cotes O/U et 1X2
  provenant de la meme ligne/du meme moment de collecte. Voir
  `data_engine/market_odds/over_under_odds.py` et
  docs/research_framework.md section P (E5) pour l'utilisation complete.
- **Extension realisee (E9, couche multi-bookmakers)** : `_ALLOWED_COLUMNS`
  etendue a `BWH`/`BWD`/`BWA` (Bet&Win) et `PSH`/`PSD`/`PSA` (Pinnacle),
  1X2 uniquement, colonnes source non-cloture - `BWCH/CD/CA` et
  `PSCH/CD/CA` explicitement exclues, verifie par test dedie.
  Contrairement a B365, BW et PS sont chacun PARTIELLEMENT complets
  (couverture variable par saison - constate par inspection directe des
  six fichiers, jamais suppose) : un bookmaker absent ou partiel sur un
  match donne est simplement absent du snapshot multi-bookmaker, jamais
  invente ni impute. Aucune colonne Over/Under BW/PS n'existe dans les
  fichiers sources - perimetre Over/Under reste limite a B365 uniquement.
  `BFE` (Betfair Exchange) explicitement EXCLU - nature d'exchange (prix
  determines par un carnet d'ordres, pas un bookmaker a marge fixe) non
  clarifiee, decision differee. Meme mecanisme point-in-time, aucune
  nouvelle regle temporelle. Nouveau module
  `data_engine/market_odds/multi_bookmaker_odds.py` (bookmaker -> marche
  -> selection -> cote, reutilise le mecanisme d'appariement/PIT SANS
  MODIFICATION) et nouveaux modules `market_engine/consensus.py`,
  `.anomaly.py` (grille de classification d'ecart PRE-ENREGISTREE,
  seuils 0.05/0.10 point de probabilite), `.arbitrage.py` (detection
  MATHEMATIQUE uniquement, jamais presentee comme une opportunite reelle).
  Voir docs/research_framework.md section T (E9) pour l'utilisation
  complete et le detail des resultats.
- **Extension realisee (E13, inventaire multi-bookmaker approfondi)** :
  inspection directe des six fichiers reels a revele deux colonnes
  1X2 supplementaires jamais lues auparavant : `WHH/D/A` (William Hill,
  present UNIQUEMENT dans les fichiers 2024/25) et `LBH/D/A` (Ladbrokes,
  present UNIQUEMENT dans les fichiers 2025/26) - Football-Data renomme
  ce "5e" bookmaker suivi d'une saison a l'autre ; ce sont deux
  bookmakers DIFFERENTS, jamais fusionnes sous un meme nom, jamais
  simultanement presents pour un meme match. Contrairement a
  `_ALLOWED_COLUMNS` (colonnes garanties presentes dans les six fichiers,
  echec explicite si absentes), `WHH/D/A`/`LBH/D/A` sont ajoutees a une
  nouvelle liste `_OPTIONAL_COLUMNS` : lues seulement si presentes DANS
  LE FICHIER (jamais une erreur si absentes du fichier entier, exactement
  comme un bookmaker absent d'un match individuel). Couverture constatee
  (jamais supposee) : ~70-76% de valeurs manquantes evitees selon le
  fichier, ordre de grandeur similaire a BW/PS. Aucune colonne de
  cloture (`WHCH/CD/CA`, `LBCH/CD/CA`), aucun agregat `Max*`/`Avg*`
  (decision d'exclusion de l'ADR non revisitee), aucun `BFE` (nature
  d'exchange toujours non clarifiee) - perimetre strictement limite a ce
  qui existe reellement. `BOOKMAKERS_1X2` etendue a
  `("B365", "BW", "PS", "WH", "LB")`. Aucune colonne Over/Under
  WH/LB n'existe dans les fichiers sources - perimetre Over/Under reste
  limite a B365 uniquement, structurellement inchange. Meme mecanisme
  point-in-time, aucune nouvelle regle temporelle - `multi_bookmaker_odds.py`
  reutilise `odds_1x2_by_bookmaker()` sans modification et beneficie de
  l'extension automatiquement. Voir docs/research_framework.md section X
  (E13) pour l'utilisation complete et le detail des resultats.
- **Extension realisee (E16, cotes de CLOTURE - reserve critique)** :
  extension de `_ALLOWED_COLUMNS` aux equivalents de cloture des
  bookmakers deja lus a l'ouverture, deja presents dans les six fichiers
  (verifie colonne par colonne avant extension, jamais suppose) :
  `B365CH/CD/CA`, `BWCH/CD/CA`, `PSCH/CD/CA` (1X2, 100% des six fichiers)
  et `B365C>2.5/C<2.5`, `PC>2.5/PC<2.5` (Over/Under 2.5, 100% des six
  fichiers). `WHCH/CD/CA`/`LBCH/CD/CA` ajoutees a `_OPTIONAL_COLUMNS`
  (meme exclusivite saisonniere que leurs equivalents d'ouverture).
  Couverture constatee (jamais supposee) : B365 cloture 100% complete sur
  les 2132 matchs (identique a l'ouverture) ; BW/PS/P cloture 75-81%
  complete (legerement inferieure a leur ouverture respective) - B365
  reste le seul bookmaker offrant une couverture ouverture ET cloture
  totale, utilise comme candidat primaire pour toute analyse de
  mouvement. Nouvelles methodes `closing_odds_1x2_by_bookmaker()` et
  `closing_over_under_2_5_by_bookmaker()` sur `FootballDataMatchRecord`,
  STRICTEMENT SEPAREES des methodes d'ouverture deja existantes (jamais
  fusionnees, jamais substituees). **RESERVE CRITIQUE NON NEGOCIABLE** :
  la cloture n'est disponible qu'au voisinage du coup d'envoi, jamais au
  `decision_time` (kickoff - `DECISION_OFFSET_HOURS`, meme regle que
  partout ailleurs) - elle sert EXCLUSIVEMENT a une etude RETROSPECTIVE
  du mouvement de marche (ouverture -> cloture -> resultat), et ne doit
  JAMAIS etre utilisee comme feature d'une prediction censee etre
  disponible a l'ouverture. Meme mecanisme point-in-time pour l'ouverture
  (aucune nouvelle regle temporelle) ; aucun script anterieur (E1-E15) ne
  lit ces nouveaux champs, leur ajout n'affecte donc aucun resultat deja
  publie. Voir docs/research_framework.md section AA (E16) pour
  l'utilisation complete et le detail des resultats.
