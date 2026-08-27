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
