# Inventaire des données de marché disponibles (lignes O/U et handicap asiatique)

Document **purement descriptif** — aucune expérience, aucun test
statistique, aucune modification de code de production. Répond
uniquement à la question : *le corpus Football-Data déjà présent
contient-il suffisamment de données de marché pour tester l'efficience
multi-lignes O/U ou le handicap asiatique ?*

Méthode : inspection directe des six fichiers CSV déjà présents
(`research/market_odds/football_data/runs/*.csv`, 2132 lignes au total)
via `pandas`, en lecture seule — **aucun téléchargement**, **aucune
extension du loader** (`football_data_loader.py` n'a pas eu besoin
d'être touché : les colonnes brutes sont lisibles directement en CSV
pour cet inventaire, voir section 8).

## 1. Corpus inspecté

Les six fichiers déjà utilisés depuis E1 : `E0_2024_25.csv`/
`E0_2025_26.csv` (Premier League), `F1_2024_25.csv`/`F1_2025_26.csv`
(Ligue 1), `SP1_2024_25.csv`/`SP1_2025_26.csv` (Liga). En-tête complet
inspecté ligne par ligne (120 colonnes sur le fichier le plus riche) pour
distinguer sans ambiguïté trois familles de colonnes qui se ressemblent
dans le nommage :

- **statistiques de match** (`HS`/`AS`/`HST`/`AST`/`HC`/`AC`/`HF`/`AF`/
  `HY`/`AY`/`HR`/`AR`, `HTHG`/`HTAG`/`HTR`) — déjà auditées en Phase F,
  **hors périmètre ici** (ne sont pas des prix de marché).
- **Over/Under (total de buts)** — colonnes `<bookmaker>>N.N`/
  `<bookmaker><N.N` (ex. `B365>2.5`, `P<2.5`).
- **Handicap asiatique** — colonnes `AHh`/`<bookmaker>AHH`/
  `<bookmaker>AHA` (ligne + prix domicile/extérieur).

## 2. Lignes O/U disponibles

**Une seule ligne de total de buts existe dans les six fichiers :
Over/Under 2.5.** Recherche exhaustive (grep sur le motif
`<colonne><N.N` dans l'en-tête brut des six fichiers) : aucune colonne
ne correspond à 0.5, 1.5, 3.5 ou 4.5, sous aucun bookmaker, ouverture ou
clôture.

| Ligne | Bookmaker | Ouverture | Clôture | Couverture (n=2132) | Utilisable PIT ? |
|---|---|---|---|---|---|
| O/U 2.5 | B365 | Oui (`B365>2.5`/`B365<2.5`) | Oui (`B365C>2.5`/`B365C<2.5`) | 100.0% | Oui — déjà exploité (E5, E7-E16, Phase D) |
| O/U 2.5 | P (Pinnacle) | Oui (`P>2.5`/`P<2.5`) | Oui (`PC>2.5`/`PC<2.5`) | 75.5% | Oui — déjà exploité (E13, E16) |
| O/U 2.5 | BFE (Betfair Exchange) | Oui (`BFE>2.5`/`BFE<2.5`) | Oui (`BFEC>2.5`/`BFEC<2.5`) | 96.1% | Oui — déjà exploité (Phase G, `NON VALIDÉ`) |
| O/U 2.5 | Max (agrégat) | Oui (`Max>2.5`/`Max<2.5`) | Oui (`MaxC>2.5`/`MaxC<2.5`) | 100.0% | **Non retenu** — agrégat à composition opaque, exclu par l'ADR 0006 (décision non revisitée) |
| O/U 2.5 | Avg (agrégat) | Oui (`Avg>2.5`/`Avg<2.5`) | Oui (`AvgC>2.5`/`AvgC<2.5`) | 100.0% | **Non retenu** — même exclusion que Max |

## 3. Lignes O/U absentes

0.5, 1.5, 3.5, 4.5 (et toute autre ligne de total non entière ou
supérieure) sont **absentes des six fichiers**, pour **tous** les
bookmakers, ouverture ET clôture, sans exception. Ce n'est pas une
lacune de lecture du loader — la colonne n'existe tout simplement pas
dans le fichier source.

> **Conclusion partielle** : le corpus Football-Data actuel ne permet
> pas de tester l'efficience multi-lignes O/U — la seule ligne de total
> de buts disponible est 2.5, déjà entièrement exploitée (E1-E16, Phase
> D, Phase G). Tester "l'efficience multi-lignes" nécessiterait une
> **nouvelle source de données** publiant au moins une seconde ligne
> (1.5 et/ou 3.5 étant les plus liquides typiquement).

## 4. Couverture (résumé chiffré)

Sur 2132 matchs au total (avant exclusion jour ambigu/PIT, qui retire
ensuite ~15% des matchs de façon identique pour tous les marchés, déjà
établi E1-E16) :

| Marché | B365 | Pinnacle (P) | BFE |
|---|---|---|---|
| O/U 2.5 (manquants) | 0/2132 (0%) | 523/2132 (24.5%) | 84/2132 (3.9%) |
| Handicap asiatique (manquants) | 0/2132 (0%) | 515/2132 (24.2%) | 72/2132 (3.4%) |

Le profil de dégradation Pinnacle (concentré sur les fichiers 2025/26 :
170-192 manquants par fichier cette saison, contre 2-3 en 2024/25) est
identique à celui déjà documenté pour le 1X2/O-U Pinnacle en E13/E16 —
cohérent, pas une anomalie nouvelle.

## 5. Bookmakers

Un bookmaker jusqu'ici **non documenté** a été repéré lors de cet
inventaire : **`1XB` (1xBet)** — 1X2 uniquement (`1XBH`/`1XBD`/`1XBA` +
clôture `1XBCH`/`1XBCD`/`1XBCA`), présent **uniquement** dans les trois
fichiers 2024/25 (absent des trois fichiers 2025/26) — même profil
d'exclusivité saisonnière que WH (2024/25 uniquement)/LB (2025/26
uniquement, E13). Aucune colonne O/U ni AH pour ce bookmaker. **Non lu**
à ce jour (hors périmètre de cet inventaire, simplement signalé pour
mémoire — une extension future du 1X2 multi-bookmaker devrait en tenir
compte).

Bookmakers O/U 2.5 et AH : B365, Pinnacle (P), Betfair Exchange (BFE),
plus les agrégats Max/Avg (exclus, section 2).

## 6. Ouverture/clôture

Toutes les colonnes O/U 2.5 et AH existent en **deux variantes** :
ouverture (colonnes nues) et clôture (suffixe `C`, ex. `B365C>2.5`,
`AHCh`). Structure identique à ce qui est déjà documenté pour le 1X2
depuis E16 — même réserve critique (la clôture n'est jamais disponible
au `decision_time`, uniquement exploitable en rétrospectif).

Point notable pour l'AH spécifiquement : la **ligne** de handicap
elle-même (`AHh` à l'ouverture, `AHCh` à la clôture) peut, en toute
généralité, **différer entre ouverture et clôture** (le bookmaker peut
déplacer la ligne, pas seulement le prix) — cette possibilité n'a pas
été quantifiée ici (purement documentaire), mais devra être vérifiée
avant toute future expérience AH portant sur un mouvement de ligne.

## 7. AH disponible

Le handicap asiatique est **structurellement complet** dans les six
fichiers :

- **`AHh`** (ouverture) / **`AHCh`** (clôture) : la **ligne** de handicap
  elle-même (ex. `-1`, `-0.5`, `-0.25`, `1.5`) — une valeur **différente
  par match** (pas une ligne fixe comme "2.5" pour l'O/U), généralement
  au domicile (négative = domicile favori). Couverture quasi totale
  (1 à 4 valeurs manquantes sur 2132, selon le fichier).
- **`B365AHH`/`B365AHA`** (prix domicile/extérieur pour cette ligne) :
  100% complet, ouverture ET clôture.
- **`PAHH`/`PAHA`** (Pinnacle) : 75.8% complet (même profil de
  dégradation que Pinnacle O/U — section 4).
- **`MaxAHH`/`AHA`**, **`AvgAHH`/`AHA`** : agrégats, exclus par la même
  décision ADR 0006 que pour l'O/U.
- **`BFEAHH`/`BFEAHA`** (Betfair Exchange) : 96.6% complet — colonnes
  déjà repérées en Phase G mais **délibérément non lues** (hors
  périmètre, une seule variable nouvelle à la fois par expérience).

Complexité méthodologique propre à l'AH (documentée ici, aucune
expérience menée) : contrairement à l'O/U (marché à deux issues
complémentaires), l'AH est un marché à **trois composantes**
(ligne + deux prix), et les lignes à quart de but (`-0.25`, `-0.75`,
...) impliquent un remboursement partiel dans certains scénarios de
score — la construction d'une probabilité implicite "propre" y est donc
structurellement plus complexe que la simple normalisation par retrait
de marge déjà réutilisée pour O/U/1X2/BFE (Phase G, section 5).

> **Conclusion partielle** : contrairement aux lignes O/U
> supplémentaires (section 3), **le handicap asiatique EST
> exploitable avec le corpus actuel** — couverture comparable à l'O/U
> 2.5 (B365 100%, Pinnacle ~76%, BFE ~97%), ouverture et clôture toutes
> deux présentes, ligne et prix tous deux publiés. Aucune expérience
> n'est lancée ici (hors périmètre de cet inventaire) — la piste reste
> disponible pour une future décision séparée.

## 8. Limitations

- Aucune extension du loader n'a été nécessaire pour cet inventaire —
  les colonnes brutes ont été lues directement via `pandas.read_csv`
  (lecture seule, aucun code de production modifié). Si une future
  expérience AH ou multi-ligne O/U était décidée, `football_data_loader.py`
  devrait être étendu (nouvelles colonnes à `_ALLOWED_COLUMNS`/nouveaux
  champs), exactement comme cela a été fait pour HST/AST (Phase F) et
  BFE (Phase G) — **non fait ici**, conformément à la consigne
  documentaire de cette étape.
- Les chiffres de couverture par fichier (section 2/4) portent sur le
  nombre brut de lignes CSV, **avant** l'exclusion jour ambigu/PIT qui
  retire ensuite ~15% des matchs de façon identique à tous les marchés
  déjà exploités (E1-E16, Phase D, Phase G) — cette exclusion n'a pas
  été recalculée ici (documentaire uniquement, pas un nouveau jeu de
  données construit).
- La découverte du bookmaker `1XB` (section 5) est un sous-produit de cet
  audit, pas son objet principal — sa pertinence éventuelle (1X2
  uniquement, une seule saison sur deux) n'a pas été évaluée plus avant.

## 9. Ce qui est testable avec les données actuelles

- **Handicap asiatique (AH)** : oui, structurellement — couverture et
  structure ouverture/clôture comparables à l'O/U 2.5 déjà exploité.
  Aucune expérience n'a été menée (hors périmètre de cet inventaire).
- **O/U 2.5 multi-bookmaker** (B365 vs Pinnacle vs BFE vs consensus
  Max/Avg) : déjà exploité intégralement (E9, E13, E16, Phase G) — rien
  de nouveau à tester ici avec la seule ligne 2.5.
- **1X2 avec un bookmaker supplémentaire (`1XB`)** : théoriquement
  possible (2024/25 uniquement), mais l'expérience E9/E13 a déjà montré
  que les bookmakers supplémentaires (BW, PS, WH, LB) sont redondants
  avec B365 — un nouveau bookmaker 1X2 supplémentaire n'est pas identifié
  comme une priorité par cet inventaire.

## 10. Ce qui nécessite une nouvelle source de données

- **Toute ligne O/U autre que 2.5** (0.5, 1.5, 3.5, 4.5) — absente des
  six fichiers Football-Data actuels, sous tout bookmaker, ouverture ou
  clôture. Tester l'efficience multi-lignes O/U exige d'acquérir une
  nouvelle source publiant au moins une seconde ligne de total de buts.
