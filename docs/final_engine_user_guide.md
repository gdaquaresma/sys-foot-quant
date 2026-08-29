# Guide utilisateur minimal - Moteur final (MVP, Phase B)

Ce document decrit, du point de vue d'un utilisateur du moteur (pas d'un
developpeur), ce que produit `sys_foot_quant.final_engine` aujourd'hui,
et surtout ce qu'il **ne pretend pas** faire. Reference technique
complete : `docs/final_engine_specification.md`. Base scientifique
complete : `docs/research_synthesis_e1_e16.md`.

## Ce qu'est ce moteur

Un systeme d'**analyse probabiliste et de qualification de prix** pour le
marche Over/Under 2.5 buts. Pour un match donne, il :

1. produit une **projection** de la distribution du nombre total de buts,
   a partir d'un modele de Poisson (`poisson_simple`) calibre par une
   correction validee statistiquement (E7/E8) ;
2. en derive un **prix juste** (la cote qu'impliquerait cette
   probabilite) ;
3. le **compare** au prix affiche par le marche a l'ouverture (Bet365) -
   jamais a la cloture ;
4. **qualifie** la confiance de cette projection (le modele est-il connu
   pour bien discriminer dans ce championnat ? cette tranche de
   probabilite est-elle connue pour etre biaisee ?) ;
5. rend une **decision** : `BET` ou `NO_BET`, toujours accompagnee d'un
   ou plusieurs codes expliquant pourquoi.

## Ce que ce moteur N'EST PAS

- **Il n'est pas presente comme rentable.** La seule experience
  economique reelle menee sur ce projet (E1) a montre qu'une regle simple
  fondee sur l'ecart modele/marche perdait de l'argent de facon
  statistiquement significative. Aucune regle de conversion
  probabilite -> pari n'a jamais ete validee depuis.
- **Il n'est pas presente comme predictif garanti.** Les probabilites
  qu'il produit sont calibrees dans certaines zones connues (voir
  "Limites" ci-dessous), pas dans toutes.
- **Il n'est pas presente comme superieur au marche.** Seize experiences
  independantes (E1-E16) montrent que le marche d'ouverture (Bet365) est
  au moins aussi bien calibre, sinon mieux, que le modele sur presque
  toutes les dimensions testees.

## Entree

Pour un match : identifiant, championnat, saison, heure du coup d'envoi,
equipes, historique de resultats (et de xG si disponible), historique de
calibration deja construit, et la cote d'ouverture Bet365 Over/Under 2.5
si elle est disponible. Aucune cote de cloture n'est jamais utilisee.

## Sortie

Un objet complet par match (voir `docs/final_engine_specification.md`
section 15) contenant, entre autres : la prediction brute de chaque
modele (`poisson_simple` principal, `dixon_coles`/`xg_model` en
comparaison - jamais fusionnes), la distribution de buts corrigee, les
probabilites Over/Under, le prix juste, la cote de marche et l'ecart avec
le modele, le statut de calibration et de discrimination, la liste des
gates declenches, et la decision finale avec ses raisons.

## `BET` vs `NO_BET`

`NO_BET` est la sortie **normale et attendue** du moteur dans sa
configuration actuelle, pas une erreur. Elle survient chaque fois que :

| Situation | Raison affichee |
|---|---|
| Historique de modele ou de calibration insuffisant | `INSUFFICIENT_HISTORY` |
| Match un lundi, mardi ou vendredi (fenetre de collecte de cote non fiable) | `AMBIGUOUS_COLLECTION_DAY` |
| Cote de marche absente ou invalide a l'heure de la decision | `MARKET_DATA_UNAVAILABLE` |
| Incoherence technique de la distribution (ne devrait jamais arriver) | `DISTRIBUTION_INCONSISTENT` |
| Probabilite Over 2.5 dans la zone [0.6,0.7), connue pour etre sur-confiante et jamais corrigee | `INSUFFICIENT_CONFIDENCE_CALIBRATION_ZONE` |
| Championnat sans discrimination demontree (Premier League, ou tout championnat jamais audite) | `DISCRIMINATION_NOT_DEMONSTRATED` |
| Aucun seuil d'edge minimal n'a encore ete valide scientifiquement | `EDGE_BELOW_THRESHOLD` |

**Avec la configuration par defaut du MVP, le moteur ne produit
actuellement jamais `BET`** : aucune experience n'a valide de seuil
d'edge minimal a partir duquel une divergence entre le modele et le
marche justifierait un pari. Le moteur reste utilisable pour la
projection, le pricing et la comparaison au marche (niveaux 1 a 4, voir
la synthese).

Ce n'est plus seulement une prudence par defaut : une experience dediee
(Phase D, `docs/operational_validation_report.md`) a explicitement testé
si une selection stricte par edge pouvait produire une performance
robuste hors echantillon, sur Liga et Ligue 1 (les championnats a
discrimination demontree). **Verdict : `NO BET - EDGE NON VALIDE`** -
aucun des seuils testes n'a ete retenu ; les matchs a fort edge se sont
averes etre precisement ceux ou le modele est sur-confiant, pas des
opportunites. `min_edge_threshold` reste `None`.

## Limites connues (a lire avant toute interpretation d'une sortie)

- **Zone [0.6,0.7) d'Over 2.5** : sur-confiance demontree sur les trois
  modeles (E11), jamais corrigee (E14 rejetee) - uniquement flaguee.
- **Premier League** : discrimination non demontree (E4, E11, E15) -
  bien calibree en moyenne, mais son pouvoir de separation entre matchs a
  faible/fort total de buts n'est pas etabli. Aucun autre championnat que
  Liga et Ligue 1 n'a ete audite a ce jour ; tout championnat non liste
  est traite avec la meme prudence que la Premier League.
- **Lignes Over/Under autres que 2.5** (0.5, 1.5, 3.5, 4.5) : calculables
  et affichables, mais 0.5/4.5 n'ont pas ete valides avec la meme rigueur
  que 1.5/2.5/3.5 (E11), et aucune n'a de cote de marche comparable dans
  les donnees actuelles hormis 2.5.
- **Le desaccord modele/marche n'est jamais un signal** : teste et
  infirme a plusieurs reprises (diagnostic post-E1, E5, E10, E12).
- **Le mouvement de marche (ouverture->cloture) n'apporte rien** :
  teste et infirme (E16) - jamais utilise par ce moteur.
- **La dispersion entre plusieurs bookmakers n'apporte rien** : testee et
  infirmee (E9, E13) - jamais utilisee comme source d'edge ici, meme si
  des cotes secondaires (Pinnacle, Bet&Win) restent lisibles a titre
  d'audit.
- **Les tirs cadres (historique, point-in-time) n'apportent pas
  d'information incrementale demontree** sur Over/Under 2.5 : teste et
  infirme (Phase F, `docs/sot_incremental_information_experiment.md`) -
  l'essentiel du gain apparent provenait d'une simple recalibration,
  jamais des tirs cadres eux-memes une fois ce facteur isole. Jamais
  utilise par ce moteur.
- **Betfair Exchange (BFE) n'apporte pas d'information incrementale
  demontree** par rapport a B365 : teste et infirme sur les quatre
  selections (1X2 H/D/A, Over 2.5) (Phase G,
  `docs/bfe_incremental_information_experiment.md`) - BFE se comporte
  comme un bookmaker fortement correle a B365, sans apport distinct.
  Jamais utilise par ce moteur.

Pour le detail scientifique complet de chacune de ces limites, voir
`docs/research_synthesis_e1_e16.md` (sections 3, 7, 8) et les sections
correspondantes de `docs/research_framework.md` (Y, Z, AA pour E14, E15,
E16 respectivement).
