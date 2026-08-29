# Architecture technique - sys-foot-quant

Ce document reprend l'architecture validee avant le debut de l'implementation,
avec les deux corrections suivantes actees :

1. La reproductibilite exigee est **deterministe et verifiable**, pas
   bit-a-bit (voir `docs/decisions/0004-reproductibilite-deterministe.md`).
2. Le benchmark "marche" doit etre manie avec prudence : la cote de
   cloture ne peut servir de benchmark d'un modele pre-match que si elle
   etait reellement disponible au moment de la decision evaluee. Pour un
   modele pre-match, elle sert avant tout a mesurer le CLV, pas a simuler
   une decision qui aurait utilise une information non disponible a
   l'epoque (voir `docs/decisions/0003-prudence-benchmark-marche.md`).

## 1. Principe directeur

Chaque donnee porte deux temps :

- `event_time` : quand la chose s'est produite (coup d'envoi, but marque).
- `knowledge_time` : quand cette information est devenue disponible pour
  le systeme.

Le backtester ne doit jamais pouvoir joindre une donnee dont
`knowledge_time > decision_time`. C'est la garantie structurelle centrale
du projet, implementee dans un unique composant : le Repository
(`data_engine/storage/repository.py`).

## 2. Etat d'implementation par module

| Module | Etat | Etape prevue |
|---|---|---|
| `common` | Implemente | 1 |
| `data_engine` (schemas, synthetique, stockage PIT, `market_odds/` phase economique) | Implemente (etendu etape 2 : force d'equipe + derive simulees ; etape 3 : plancher realiste du marche synthetique ; **phase economique : `market_odds/` ajoute cotes REELLES Football-Data.co.uk** - 3 championnats x 2 saisons 2024/25+2025/26, marche 1X2, bookmaker Bet365 uniquement, 2123/2132 matchs apparies (99.58%) au corpus Understat via mapping d'equipes deterministe, AUCUN timestamp individuel a la source - regle point-in-time conservatrice documentee (jamais verifiee), matchs lundi/mardi/vendredi explicitement exclus - voir docs/decisions/0006-football-data-point-in-time.md ; **`economic_dataset.py` (Experience 1)** assemble ces cotes avec les probabilites point-in-time de `poisson_simple` (`real_data_walk_forward.py`, inchange) - 1762 matchs economiquement exploitables sur 2132, exclusions comptabilisees explicitement (jour ambigu, historique insuffisant, cotes incompletes, non apparies) - voir docs/research_framework.md section I pour le verdict complet : **SIGNAL NEGATIF** (IC95% du profit moyen entierement negatif sur la strategie EV>0 pre-enregistree, n=1888 paris) ; **diagnostic post-E1** (`run_stage7_diagnostic_e1_market_gap.py`, purement descriptif, `poisson_simple` et `xg_model` INCHANGES) : calibration de `poisson_simple` 3 a 9x pire que le marche sur les trois issues sans exception, biais diffus (pas de sous-groupe localise), AUCUNE information independante detectee dans le desaccord poisson/marche (test demeanne par decile, IC95% couvrant 0 sur les trois issues), et erreurs xG PLUS correlees au marche (+0.845) que celles de poisson_simple (+0.789) - reponse negative a "xG contient-il une information non deja capturee par B365 ?", voir docs/research_framework.md section J pour le detail complet. Aucune modification de `poisson_simple`.) ; **`over_under_odds.py` (E5)** etend la lecture Football-Data a B365 Over/Under 2.5 (`_ALLOWED_COLUMNS` de `football_data_loader.py` etendue, extension anticipee par l'ADR 0006, completude 100% verifiee, colonnes de cloture exclues) et reutilise SANS MODIFICATION le mecanisme point-in-time (matching.py/time_resolution.py) - voir docs/research_framework.md section P ; **`multi_bookmaker_odds.py` (E9)** etend `_ALLOWED_COLUMNS` a BW/PS (1X2 uniquement, colonnes non-cloture, `BFE` explicitement exclu - nature d'exchange non clarifiee) et reutilise SANS MODIFICATION le meme mecanisme point-in-time, produit une representation generique bookmaker->marche->selection->cote - 1806/2123 matchs exploitables, couverture BW 80.5%/PS 76.6% (profil de completude qui s'inverse entre les deux saisons - artefact du fournisseur, documente comme reserve) - voir docs/research_framework.md section T ; **experience E13 - correction d'inventaire** : `football_data_loader.py` etend `_ALLOWED_COLUMNS` a `P>2.5`/`P<2.5` (Pinnacle publie AUSSI l'Over/Under 2.5, prefixe `P` distinct de `PS` utilise pour son 1X2 - suppose a tort limite a B365 seul en E9-E12, corrige apres inspection directe de l'en-tete brut) et ajoute `_OPTIONAL_COLUMNS` pour `WHH/D/A`/`LBH/D/A` (William Hill et Ladbrokes, saisons disjointes 2024/25 vs 2025/26, jamais coexistants) ; `_parse_optional_float` traite desormais toute valeur `<=1.0` (ex. le sentinelle litteral `"0"` trouve sur un match reel pour `P>2.5`/`P<2.5`) comme absente plutot que comme une cote reelle ; `multi_bookmaker_odds.py` corrige en consequence (`_odds_over_under_snapshot` inclut Pinnacle) - E9/E10/E11/E12 restent NUMERIQUEMENT INCHANGES (cle `"B365"` explicite, jamais un parcours generique) - voir docs/research_framework.md section X ; **experience E16 - extension cotes de CLOTURE** : `football_data_loader.py` etend `_ALLOWED_COLUMNS` a `B365CH/CD/CA`, `BWCH/CD/CA`, `PSCH/CD/CA` (1X2) et `B365C>2.5/C<2.5`, `PC>2.5/PC<2.5` (O/U 2.5), toutes verifiees presentes dans les six fichiers (100% pour B365, 75-81% pour BW/PS/P) ; `_OPTIONAL_COLUMNS` etendue a `WHCH/CD/CA`/`LBCH/CD/CA` (meme exclusivite saisonniere que l'ouverture) ; nouvelles methodes `closing_odds_1x2_by_bookmaker()`/`closing_over_under_2_5_by_bookmaker()` STRICTEMENT separees des methodes d'ouverture - **RESERVE CRITIQUE non negociable : la cloture est reservee a une etude RETROSPECTIVE du mouvement de marche (E16), jamais utilisee comme feature d'une decision a l'ouverture** ; E1-E15 non affectes (aucun ne lit ces nouveaux champs) - voir docs/research_framework.md section AA) | 1 (base) / phase economique (`market_odds/`) |
| `backtesting_engine` (boucle chronologique minimale + walk-forward synthetique + walk-forward donnees reelles) | Implemente (`real_data_walk_forward.py` ajoute etape 5 pour B3 - walk-forward isole sur DataFrames en memoire avec deux flux de connaissance point-in-time independants (buts/xG), n'est PAS un connecteur de donnees reelles general pour le reste du projet, specifique au test B3) | 1 (boucle) / 2 (walk-forward synthetique) / 5 (walk-forward donnees reelles) |
| `football_model` (Poisson simple, attaque/defense, A1 (decroissance calendaire + re-test fenetre glissante), A2, benchmarks naif/Elo, B2 bayesien sequentiel, B1 Dixon-Coles, forme recente/H2H (re-test A1), B3 xG + B3.2 hybride + B3.3 gate de desaccord, controles negatifs E1/E7) | Implemente (A1 REJETE (infériorité significative confirmée) - decroissance calendaire (etape 2) ET fenetre glissante football-realiste avec/sans memoire longue (etape 5, `recent_form.py`/`head_to_head.py`) toutes deux significativement dominees par poisson_simple sur synthetique ; H2H seul INDETERMINE (aucun signal) ; B2 VALIDE contre A1 sur synthetique ; B1 (Dixon-Coles) VALIDE contre poisson_simple sur le sous-ensemble bas-score sur donnees SYNTHETIQUES uniquement, mais **REJETE lors du re-test sur donnees REELLES - avec nuance** : infériorité significative confirmée en Ligue 1 uniquement (IC95% entierement positif), absence de preuve d'amelioration (pas d'infériorité démontrée) en Premier League/Liga (memes donnees Understat que B3/B3.2/C7, 3 championnats x 2 saisons 2024/25+2025/26, buts reels uniquement, `DixonColesModel` inchange) - sous-ensemble bas-score sans signal coherent non plus - voir docs/research_framework.md section B1 pour le detail complet ; **A2 (HFA dynamique par equipe) REJETE - absence de preuve d'amelioration, pas refutation** lors du re-test sur donnees REELLES (`PoissonModel(use_team_hfa=True)`, `hfa_shrinkage_k=10.0` fige a l'etape 2, memes donnees que B1/B3/B3.2/C7, 640 matchs de test evalues) - aucun des trois championnats n'atteint une amelioration significative de poisson_simple, mais aucun n'atteint non plus une inferiorite significative (IC95% incluant 0 partout), signe instable entre saisons pour Ligue 1 et Liga - puissance statistique limitee, voir docs/research_framework.md section A2 et section G2 (limites de puissance) pour le detail complet ; **B2 (bayesien sequentiel) REJETE - absence de preuve d'amelioration, avec tendance favorable mais non significative** lors de la comparaison DIRECTE a poisson_simple sur donnees REELLES (`BayesianSequentialModel` inchange, `prior_strength=10.0` fige a l'etape 5, memes donnees que B1/A2/B3/B3.2/C7, 640 matchs de test evalues ; B2 n'avait ete compare qu'a A1 - desormais rejete - jamais directement a poisson_simple) - aucun des trois championnats n'atteint une amelioration significative (IC95% incluant 0 partout, Ligue 1 proche du seuil a -0.0114 [-0.0232, +0.0005], candidat le plus susceptible de changer de statut avec plus de donnees) - voir docs/research_framework.md section B2 et section G2 (limites de puissance) pour le detail complet ; **B3 (xG, `xg_model.py`) INDETERMINE**, **B3.2 (hybride Poisson/xG, `hybrid_xg_model.py`) INDETERMINE** et **B3.3 (gate de desaccord Poisson/xG, `gate_disagreement_model.py`, w=TVD zero parametre libre) REJETE - absence de preuve d'amelioration** sur donnees REELLES Understat (B3 : 3 championnats 2025/26 ; B3.2 : jeu vierge 2024/25, protocole validation/test isole ; B3.3 : 3 championnats x 2 saisons, 640 matchs test, signe favorable au gate cohérent sur les trois championnats sans jamais atteindre la significativite, PL/Liga proches du seuil p=0.089/0.080 ; les trois tests sont sous-puissants pour des effets de l'ordre de 0.01-0.02, voir section G2 de research_framework.md) - conclusion figee : l'analyse de complementarite est une observation statistique etablie sur son echantillon conditionnel (xG bat poisson_simple precisement quand ce dernier se trompe), mais sans strategie d'exploitation ex-ante identifiee - ni un modele xG seul, ni un hybride inconditionnel, ni un gate de desaccord a zero parametre n'ameliorent significativement poisson_simple hors echantillon avec les donnees actuelles (B3.3 montre neanmoins un signe favorable coherent sur les trois championnats, jamais significatif) ; ces resultats sont des hypotheses non demontrees, pas refutees ; **poisson_simple reste le modele de reference officiel** (inchange), **XGModel conserve comme modele complementaire independant** (jamais fusionne automatiquement), **HybridXGModel et GateDisagreementModel conserves pour tracabilite/reproductibilite, statut strictement experimental, non promus** ; reserve documentee sur la stabilite temporelle du xG Understat (delai de connaissance suppose, non verifie, distinct d'une fuite de donnees) - voir docs/research_framework.md section B3 pour la conclusion officielle complete. **BILAN GLOBAL (post-audit)** : aucune extension testee (A2, B1, B2, B3, B3.2, B3.3) n'a fourni a ce jour une amelioration statistiquement demontree et reproductible suffisante pour justifier le remplacement de poisson_simple ; A1 seul est refute par une preuve directe. Plusieurs hypotheses restent non demontrees plutot que refutees, notamment A2, B2 et B3/B3.2, en raison notamment de la puissance limitee des echantillons - voir docs/research_framework.md section G2 pour l'audit complet de la force des verdicts ; **diagnostic total de buts/Over-Under (purement descriptif, AUCUN modele modifie)** : poisson_simple/dixon_coles/xg_model surestiment tous les trois systematiquement le total de buts (biais +0.30/+0.30/+0.61 sur 2.79 buts observes en moyenne), concentre dans la queue haute (6+ buts surestime d'un facteur 2-3) ; Dixon-Coles mathematiquement identique a poisson_simple sur Over 2.5/3.5 (correction confinee aux cellules de total<=2) ; xg_model n'ameliore pas la calibration ponderee malgre un Brier/log loss legerement meilleur - voir docs/research_framework.md section K pour le detail complet ; **diagnostic calibration Over/Under par tranche (purement analytique, AUCUN modele modifie ni recalibre)** : decomposition de Murphy du Brier (nouvel outil de mesure pur, `calibration_engine/decomposition.py`, reutilise `reliability_bins` sans modification) montre un skill NEGATIF par rapport a la climatologie sur les 6 combinaisons testees (poisson_simple/xg_model x Over 1.5/2.5/3.5) - biais de fiabilite (0.007-0.027) superieur a la resolution (0.0017-0.0043), schema de biais en "S" (sous-confiance basse, sur-confiance haute) plausiblement corrigible par une recalibration monotone future (resolution mathematiquement preservee par construction) sans que cela soit demontre ici - voir docs/research_framework.md section L ; **experience E2 (recalibration isotonique Over/Under, poisson_simple/xg_model INCHANGES)** : `calibration_engine/isotonic_calibration.py` (PAVA via scipy, deja une dependance, aucune nouvelle), walk-forward 40/30/30 identique a B1/A2/B2/B3.3, courbe ajustee sur calibration uniquement (n=640), evaluee sur test uniquement (n=640) - AMELIORATION STATISTIQUEMENT DEMONTREE du Brier sur les 3 seuils pour xg_model et sur Over 3.5 pour poisson_simple (IC95% bootstrap entierement negatif), absence de preuve (jamais degradation) pour poisson_simple Over 1.5/2.5 - voir docs/research_framework.md section M pour le detail complet, y compris la nuance log loss/resolution ; **experience E3 (fiabilite hors echantillon des probabilites CALIBREES, rapport pur, aucun recalcul - reutilise le pipeline E2 a l'identique)** : sur Over 2.5 (priorite), xg_model calibre annonce ~57% dans sa zone la plus peuplee (n=387) pour 55.3% observe (ecart 1.7pt) ; poisson_simple calibre montre une bonne fiabilite apparente mais concentree a 98% sur un seul palier (perte de resolution deja notee en E2) ; Over 3.5 non verifiable dans les zones 50%+ (aucun match calibre n'y atteint ce niveau) - voir docs/research_framework.md section N ; **experience E4 (discrimination de l'esperance totale de buts BRUTE, aucune calibration, poisson_simple/xg_model INCHANGES)** : sur les tranches fixes (analyse principale), le total reel observe ET la frequence d'Over 2.5 augmentent de facon quasi-monotone avec l'esperance predite pour les deux modeles (niveau global) ; corrélation modeste (~0.16), biais de surestimation confirme (IC95% negatif) ; signal ABSENT en Premier League pour les deux modeles (corr. -0.02/+0.01) mais present en Liga/Ligue 1/les deux saisons (~0.08-0.25) - discrimination reelle mais non uniforme sur le corpus, voir docs/research_framework.md section O ; **experience E5 (fiabilite du desaccord modele/marche B365, Over 2.5, poisson_simple/xg_model INCHANGES)** : `football_data_loader.py` etendu (B365>2.5/B365<2.5, extension anticipee par l'ADR 0006, completude 100% verifiee) + nouveau module `over_under_odds.py` (reutilise SANS MODIFICATION matching.py/time_resolution.py) ; resultat central : dans la zone d'accord modele/marche (~53% du test), calibration excellente (ecart <0.3pt) pour les deux modeles, mais la fiabilite se degrade de facon quasi monotone avec l'ampleur du desaccord - poisson_simple particulierement net et symetrique (jusqu'a -23.4pt a >=+15pts de desaccord positif) - le desaccord ne se valide PAS, confirme la partie 4 du diagnostic post-E1, voir docs/research_framework.md section P ; **experience E6 (information incrementale du marche sur le total de buts, poisson_simple/xg_model INCHANGES, aucune nouvelle calibration)** : reutilise sans recalcul les probabilites calibrees E2/E3 et les cotes O/U point-in-time E5 ; resolution du marche egale ou superieure a celle du modele sur 11/12 combinaisons (championnats/saisons x 2 modeles) ; test d'information incrementale (two_sample_bootstrap_test, reutilise) directionnellement favorable au marche sur les 7 tranches interpretables sans exception mais non significatif a ces tailles d'echantillon ; test inverse structurellement degenere (esperance rarement <2.5 sur ce corpus) - verdict de synthese : redondance dominante, aucune preuve que le modele detient une information que le marche n'a pas deja, voir docs/research_framework.md section Q) ; **experience E7 (distribution finale coherente du total de buts, poisson_simple/dixon_coles/xg_model INCHANGES, aucun nouveau modele)** : diagnostic confirme que la surestimation de la queue haute (K/L/E4) est un probleme de MOYENNE (indice de dispersion 0.9611, distribution empirique quasi identique a un Poisson evalue a la moyenne empirique reelle), pas de forme ; demonstration empirique (0 violation trouvee sur n=640, risque structurel neanmoins reel en principe) que la calibration isotonique par seuil (E2/E3) n'offre aucune garantie de coherence croisee entre seuils ; methode retenue - correction scalaire unique `c = E[total_reel]/E[lambda+mu]` ajustee sur calibration uniquement puis appliquee a (lambda, mu) avant reconstruction de la matrice de score complete (coherence Over/Under garantie PAR CONSTRUCTION, jamais verifiee a posteriori) ; resultat - amelioration statistiquement demontree du Brier global pour les trois modeles (poisson_simple p=0.0056, dixon_coles p=0.0046, xg_model p<0.0001), biais de l'esperance totale ramene de +0.27/+0.57 a un niveau quasi nul, queue P(>=6) quasi parfaitement corrigee, resolution globalement preservee - voir docs/research_framework.md section R pour le detail complet, y compris la stabilite par championnat/saison et les limites) ; **experience E8 (validation walk-forward hors echantillon de la correction E7, poisson_simple/dixon_coles/xg_model INCHANGES, meme formule de correction, aucune nouvelle methode)** : inspection des frontieres temporelles du split E7 revele un risque de fuite reel (calibration poolee sur 3 championnats non synchronisee globalement - ex. calibration `liga` 2024/25 s'etend jusqu'au 2025-03-09, apres le debut du test `premier_league` 2024/25 le 2025-02-26) ; corrige par un facteur c(m) reestime PAR MATCH DE TEST, exclusivement a partir des matchs de calibration dont decision_time precede strictement celui du match evalue (regle d'exclusion n>=30 pre-enregistree, jamais activee - 0/640 matchs exclus) ; resultat - l'amelioration d'E7 TIENT integralement sous ce protocole plus strict : Brier global significativement ameliore pour les trois modeles (poisson_simple p=0.0008, dixon_coles p=0.0006, xg_model p<0.0001), queue P(>=6) quasi parfaitement corrigee, aucune inversion sur les 18 decoupes championnat/saison testees, facteur c(m) stable dans le temps (CV<=2.6%, variation dominee par un ecart net mais modeste entre les deux saisons, pas de derive intra-saison) ; VERDICT A (validation reussie) pour les trois modeles selon la grille pre-enregistree - la distribution corrigee peut servir de fondation officielle pour les probabilites de buts et marches Over/Under - voir docs/research_framework.md section S pour le detail complet) | 2 (base) / 5 (A1 re-test, B1, B2, B3, B3.2, B3.3, E1, E7) |
| `calibration_engine` (Brier, log loss, reliability, tests de significativite, Chi-Deux, `decomposition.py` fiabilite/resolution/incertitude, `isotonic_calibration.py` recalibration post-hoc PAVA) | Implemente (E7 ajoute une correction scalaire post-hoc du taux total predit, appliquee en amont de la matrice de score plutot qu'au niveau des probabilites de seuil - garantit la coherence Over/Under par construction, voir docs/research_framework.md section R ; E8 valide cette correction sous un protocole walk-forward strict PAR MATCH (facteur reestime a partir des seuls matchs de calibration anterieurs a chaque match de test, corrigeant un risque de fuite inter-championnats identifie dans le split poole d'E7) - amelioration confirmee, verdict A pour les trois modeles, voir docs/research_framework.md section S ; **experience E14 (recalibration ciblee de la sur-confiance [0.6,0.7) d'Over 2.5 identifiee en E11, poisson_simple/dixon_coles/xg_model INCHANGES, aucune modification d'E1-E13)** : teste une SECONDE couche de calibration walk-forward (meme principe que le facteur c(m) d'E8, applique ici a une methode de recalibration plutot qu'a l'echelle) - methode A (isotonic sur tout le domaine, PAVA, `isotonic_calibration.py` reutilise) et methode B (logistique a 2 parametres, EXACTEMENT la forme de `calibration_slope_intercept` d'E11 reutilisee comme mecanisme d'ajustement plutot que comme seule mesure) - GATE OBLIGATOIRE de coherence inter-seuils (P(O1.5)>=P(O2.5)_recalibree>=P(O3.5) de la MEME distribution E7/E8, jamais recalculee) ; resultat reel (n=640 test, zone cible n=117-128) - `xg_model` : amelioration OOS NON demontree dans la zone cible pour les deux methodes (IC95% contenant 0) ; `poisson_simple` : amelioration OOS demontree (IC95% [-0.0242,-0.0021] methode A, [-0.0320,-0.0002] methode B) MAIS **gate de coherence viole substantiellement** (14-24/640 matchs, amplitude jusqu'a 0.169 point de probabilite) et amelioration non stable par championnat (portee principalement par la Premier League) - **VERDICT : E14 - RECALIBRATION NON VALIDEE** pour les 4 combinaisons testees, zone [0.6,0.7) documentee comme limite structurelle du moteur actuel, aucune nouvelle tentative sans nouvelles donnees - voir docs/research_framework.md section Y pour le detail complet ; **experience E15 (diagnostic STRUCTUREL, purement descriptif, aucun modele/hyperparametre/correction E7-E8 modifie)** : la discrimination quasi nulle/negative en Premier League (constatee 3x en E4/E11) est-elle une anomalie de donnees, une sous-puissance, une caracteristique distributionnelle reelle, une difference de calibration, ou une absence reelle de signal ? Audit des donnees (etape 1) INTEGRALEMENT PROPRE sur les 3 championnats (round-robin exact, 0 doublon, 0 conflit nom/id, 0 desequilibre dom/ext, continuite inter-saisons verifiee) - anomalie de donnees ECARTEE ; replication E4/E11 CONFIRMEE exactement (PL poisson_simple corr=-0.0241 brut / -0.0056 corrige, xg_model +0.0119/+0.0367, vs Liga/Ligue1 +0.15 a +0.25) ; dispersion REELLE des buts (nouvel indicateur, `distribution_moments`) NE differencie PAS PL de la Liga (0.896 vs 0.926, IC95% [-0.159,+0.101]) alors que la Liga discrimine normalement - explication par la variance reelle ECARTEE ; predictions du modele mesurablement plus COMPRIMEES en PL (ecart-type/IQR les plus bas des 3 championnats, 2 modeles) mais mecanisme derive du modele lui-meme, pas une caracteristique independante au sens de la grille de verdict ; classification calibration/discrimination (nouvelle regle figee avant execution) : PL = **B - bien calibree mais peu discriminante** (jamais A ni C) pour les 2 modeles - difference de calibration ECARTEE ; test de puissance (bootstrap + permutation, nouvelles primitives `bootstrap_correlation_diff`/`permutation_test_correlation_diff`) demontre la difference PL vs Liga/Ligue1 dans 3 comparaisons sur 4 (p=0.005 a 0.041) et les 2 tests de permutation (p=0.0015/0.016) - sous-puissance ECARTEE comme explication principale ; phenomene commun aux 2 modeles et stable sur les 2 saisons (jamais concentre sur une sous-periode) - **VERDICT : E15 - ABSENCE DE SIGNAL CONFIRMEE MAIS INEXPLIQUEE** - aucune cause independante identifiee au-dela d'un mecanisme proximal non qualifiant (compression des predictions) ; regle de gating analytique proposee ("ne pas interpreter l'esperance de buts comme un signal discriminant en Premier League"), jamais une regle de pari - voir docs/research_framework.md section Z pour le detail complet ; **experience E16 (information contenue dans le mouvement de marche ouverture->cloture, poisson_simple/dixon_coles/xg_model NON UTILISES - marche etudie independamment du modele, E7/E8/E14/E15 non lus/non modifies, RETROSPECTIF - la cloture n'est jamais un feature d'ouverture)** : `football_data_loader.py` etendu aux cotes de CLOTURE deja presentes dans les six fichiers (B365/BW/PS 1X2, B365/P O/U 2.5) - B365 seul a une couverture ouverture ET cloture 100% (n=1806), candidat primaire ; 5 modeles figes (O ouverture seule zero-parametre, C cloture seule zero-parametre RETROSPECTIF, M mouvement seul 2-parametres, O+M 3-parametres TEST CENTRAL, O+C 3-parametres RETROSPECTIF), tous ajustes en FENETRE GLISSANTE EXPANSIVE (meme principe que le facteur c(m) d'E8) ; resultat reel - **les 4 hypotheses primaires pre-enregistrees (O+M vs O, Home/Draw/Away/Over2.5) sont toutes NON REJETEES apres correction de Holm-Bonferroni** (p=0.047 a 0.96, aucun IC95% demontrant une amelioration) ; M seul significativement PIRE que O (attendu, valide le mecanisme) ; O+C retrospectif n'ameliore pas non plus O ; reproduit avec Pinnacle (PS, secondaire, p=0.12 a 0.54) et stable par championnat/saison (1 seule decoupe sur 20 montre une dégradation marginale, jamais une amelioration) ; seule exception exploratoire non corrigee : cloture significativement meilleure que l'ouverture dans la tranche de mouvement le plus large pour Home (n=92) - ne change pas le verdict global ; price discovery reel constate (le marche bouge et la direction est associee a la frequence reelle) mais jamais exploitable retroactivement (O+M n'ameliore pas O) - **VERDICT : E16 - MOUVEMENT NON INFORMATIF** - le marche d'ouverture contient deja l'essentiel de l'information exploitable, aucune couche de mouvement de marche ajoutee au moteur - voir docs/research_framework.md section AA pour le detail complet) | 2 |
| `market_engine` (snapshot, retrait de marge proportionnel + Shin, comparaison, `correlated_events.py` ajoute etape 5 pour C7, `model_vs_market.py` phase economique, `consensus.py`/`anomaly.py`/`arbitrage.py` E9) | Implemente (**`model_vs_market.py` (phase economique)** : interface generique modele<->marche (probabilite implicite, overround, normalisation, diff) reutilisant `overround.py` sans modification, desormais utilisee par `economic_dataset.py` pour l'Experience 1 (verdict SIGNAL NEGATIF - voir `data_engine` ci-dessus et docs/research_framework.md section I) ; **C7 phase 1 (parlays correles, `correlated_events.py`) REJETE - absence d'association demontree pour cette paire precise, sans generalisation aux autres marches/parlays** - aucune correlation exploitable detectee entre favori a domicile selon poisson_simple et Over 2.5 buts, coherent sur 3 championnats et 2 saisons (estimation 2024/25, confirmation 2025/26) - teste uniquement l'EXISTENCE d'une correlation, aucune cote de marche combine dans le schema actuel donc aucune conclusion possible sur la rentabilite reelle d'un combine - voir docs/research_framework.md section C7 pour le detail complet ; **experience E9 (couche multi-bookmakers, `consensus.py`/`anomaly.py`/`arbitrage.py` nouveaux, purement descriptif, aucun ROI/strategie de pari, poisson_simple/dixon_coles/xg_model INCHANGES)** : overround retire PAR BOOKMAKER (`overround.py` reutilise sans modification) ; consensus = moyenne/mediane/min/max/ecart-type entre bookmakers SANS poids optimise ; anomalie book-vs-consensus classee selon grille PRE-ENREGISTREE (seuils 0.05/0.10 point, jamais qualifiee de "value") ; arbitrage detecte MATHEMATIQUEMENT (somme des probabilites inverses des meilleurs prix), toujours presente comme une detection historique jamais une opportunite reelle ; resultats reels (n=1806 matchs) - 1X2 : 3 bookmakers (B365 100%, BW 80.5%, PS 76.6%), overround PS (~3.6%) nettement plus bas que B365/BW (~5.6%), dispersion entre bookmakers tres faible (ecart-type moyen 0.0053) -> AUCUNE anomalie ni arbitrage detecte sur les 13926 instances evaluables ; Over/Under 2.5 : un seul bookmaker (B365) dans les donnees sources -> detection d'anomalie/arbitrage inter-bookmakers structurellement non evaluable sur ce marche ; comparaison modele/marche (Over 2.5, split TEST walk-forward valide en E8, n=542) : ecart modele-consensus legerement negatif pour les deux modeles (poisson_simple -0.0114, xg_model -0.0078), jamais qualifie de "value" - voir docs/research_framework.md section T pour le detail complet ; **experience E10 (fiabilite des zones de desaccord modele/marche, Over/Under 2.5, poisson_simple/dixon_coles/xg_model INCHANGES, aucune nouvelle calibration)** : gap = P_model (walk-forward E8) - P_market (B365 normalise), tranches FIGEES identiques a E5 (pas de 5 points) ; sur n=542 (intersection E8 test x E9 corpus), UNE SEULE tranche significative globalement - poisson_simple/dixon_coles sous-estiment P(Over2.5) dans la tranche de desaccord extreme ou le modele est bien plus pessimiste que le marche (biais +0.256, IC95% [+0.066,+0.435], n=22) ; AUCUNE zone de desaccord ne montre une difference de Brier significative par rapport a la zone d'accord (toutes IC95% contenant 0) ; test d'asymetrie SIGNIFICATIF pour poisson_simple/dixon_coles (diff IC95% [-0.210,-0.043] p=0.004) - quelle que soit la direction du desaccord avec le marche, le modele s'eloigne plutot qu'il ne se rapproche de la realite (non reproduit avec la meme significativite pour xg_model) ; verdict : AUCUNE zone de desaccord fiable demontree, cohérent avec le diagnostic post-E1/E5/E6 - voir docs/research_framework.md section U pour le detail complet, y compris le diagnostic secondaire 1X2 ; **experience E11 (cartographie de la fiabilite ABSOLUE des probabilites de buts E8 vs B365, poisson_simple/dixon_coles/xg_model INCHANGES, aucune nouvelle calibration)** : les 5 seuils Over/Under (0.5/1.5/2.5/3.5/4.5) sont derives EN UN SEUL APPEL de la MEME matrice corrigee walk-forward - propriete de coherence structurelle reconfirmee ; calibration absolue (H1, tranches de probabilite fixees ex ante [0-10%)...[90-100%], pente/intercept de Cox, correlation, decomposition de Brier E2/E4 reutilisee) - resultat central REPRODUIT SUR LES TROIS MODELES : sur-confiance significative dans la tranche [0.6-0.7) d'Over 2.5 (biais -0.11 a -0.12, IC95% entierement <0), zone [0.4-0.6) (la plus peuplee) bien calibree partout ; pentes de Cox uniformement <1 (sur-confiance systemique moderee, tous seuils) ; AUCUNE difference de Brier significative entre poisson_simple et xg_model sur aucun des 5 seuils (paires appariees) malgre un biais brut tres different avant correction (deja etabli en K/E7) ; Premier League confirme (3e fois, apres E4) une discrimination quasi nulle ou negative sur presque toutes les combinaisons seuil/modele, Liga/Ligue1 restent discriminants ; H2 (EXPLORATOIRE, restreint aux tranches jugees fiables au sens H1, decidees AVANT examen des prix) - un seul ecart significatif : xg_model, categorie d'ecart de prix >=10% avec B365 (n=205, biais +0.074, IC95% [+0.006,+0.141]), jamais qualifie de "value" ni de strategie - voir docs/research_framework.md section V pour le detail complet ; **experience E12 (intersection fiabilite x ecart de prix, Over 2.5 prioritaire, poisson_simple/dixon_coles/xg_model INCHANGES, aucune nouvelle calibration, aucune strategie de pari)** : teste si les tranches de probabilite ou le modele est fiable (H1) coincident avec les tranches a plus fort ecart de prix B365 - quatre notions distinguees explicitement (fiable / desaccord / anomalie de prix reservee a E9 / value potentielle jamais evaluee) ; grille de verdict a 4 niveaux FIGEE avant execution (demontree / contradictoire / directionnelle non demontree / absence de preuve) ; resultat reel - poisson_simple/dixon_coles : VERDICT CONTRADICTOIRE (n_fiable=350, n_non_fiable=168, diff IC95% [-0.0189,-0.0013] p=0.024) - les tranches fiables ont un ecart de prix PLUS PETIT, pas plus grand, l'inverse de l'hypothese ; xg_model : VERDICT DIRECTIONNELLE MAIS NON DEMONTREE (IC95% [-0.0060,+0.0092] p=0.646) ; lecture mecanique : le plus grand ecart de prix observe coincide avec la tranche [0.3-0.4) ou poisson_simple/dixon_coles sont eux-memes demontres non fiables (biais +0.133) - le desaccord de prix y reflete probablement une erreur du modele plutot qu'une opportunite ; intersection non testable au-dela d'Over 2.5 (Football-Data ne publie que cette ligne pour l'O/U) - voir docs/research_framework.md section W pour le detail complet) ; **experience E13 (dispersion multi-bookmakers et arbitrage mathematique, Over/Under 2.5 prioritaire, poisson_simple/dixon_coles/xg_model INCHANGES, aucune nouvelle calibration, aucune strategie de pari)** : question distincte de E9-E12 - la dispersion entre bookmakers contient-elle une information exploitable, et existe-t-il un arbitrage mathematique historique ? Correction d'inventaire prealable (Pinnacle publie aussi l'O/U 2.5, cf. `data_engine` ci-dessus) rend enfin evaluable la dispersion sur ce marche (2 bookmakers, n=1374) ; correction methodologique decouverte en cours d'execution (`restrict_to_canonical_selection`) - regrouper Over ET Under dans une meme table est degenere pour un marche a 2 issues strictement complementaires (biais force a exactement 0 par construction algebrique), seule la selection canonique Over est retenue, IDENTIQUE a la convention deja utilisee en E10/E11/E12 ; resultats reels - Over/Under 2.5 : test central dispersion haute/basse ABSENCE DE PREUVE (IC95% [-0.0278,+0.0271] p=0.953), consensus B365+P n'ameliore pas mesurablement B365 seul (IC95% [-0.0001,+0.0003]), 0 anomalie individuelle (100% "proche du consensus"), consensus statistiquement indiscernable de la distribution E8 (poisson_simple IC95% [-0.0051,+0.0125], xg_model [-0.0036,+0.0097]) ; 1X2 (5 bookmakers, n=5418) : meme conclusion ABSENCE DE PREUVE (IC95% [-0.0259,+0.0085] p=0.296), 0 anomalie sur 18009 instances ; **0/1806 matchs avec arbitrage mathematique detecte sur les DEUX marches** (marge moyenne stable +3.35% a +3.78%, ecart meilleure-pire cote ne depassant jamais 5 points de probabilite dans ce corpus) - reponse NEGATIVE aux deux questions du protocole (information supplementaire des bookmakers ; existence d'arbitrages historiques), expliquee par une dispersion structurellement trop faible et homogene sur ce panel de bookmakers reglementes - voir docs/research_framework.md section X pour le detail complet) | 2 (benchmark) / 3 (complet) / 5 (C7) / phase economique (E9, E10, E11, E12, E13) |
| `value_engine` (edge, EV, CLV, selection - AUCUNE selection sur EV seule) | Implemente (`edge.py::expected_value`/`edge` reutilises sans modification par l'Experience 1 economique, voir `data_engine` ci-dessus - `selection.py` non utilise, la strategie EV>0 de l'Experience 1 est deliberement plus simple, definie localement dans `scripts/run_stage6_economic_b365_ev.py`) | 3 |
| `risk_engine` (bankroll, Flat Betting, Kelly informatif + quality gates, limites, metriques de risque, Monte Carlo) | Implemente (Flat Betting seul active en production - Kelly verrouille, voir `risk_engine/kelly.py`) | 4 |
| `final_engine` (**MVP du moteur final, Phase B**, `prediction.py`/`calibration.py`/`pricing.py`/`market.py`/`gates.py`/`decision.py`/`orchestrator.py`/`types.py`/`reference_tables.py`/`reason_codes.py`) | Implemente (voir section 2.0 ci-dessous pour le detail complet - pipeline A->F derive de `docs/final_engine_specification.md`, aucune nouvelle hypothese scientifique, decision `NO_BET` par defaut tant qu'aucun seuil d'edge n'est valide) | Phase B |
| `live_betting_engine` | Non implemente | 6 (conditionnel) |

## 2.0 Moteur final - specification (Phase A) et implementation (Phase B)

La campagne E1->E16 etant close (section 2.1 ci-dessous), la construction
s'est faite en deux phases : **Phase A**, specification technique pure
(`docs/final_engine_specification.md`, aucun code ecrit) traduisant les
conclusions d'E1->E16 en un contrat d'implementation precis - pipeline en
6 niveaux (A Prediction / B Calibration / C Pricing / D Market comparison
/ E Qualification / F Decision), inventaire des primitives a reutiliser,
inputs exacts par categorie (la cloture restant exclue du chemin de
decision), gates scientifiques exhaustifs separes des operational
thresholds (marques `PARAMETRE OPERATIONNEL A VALIDER`), objet de sortie
structure, moteur minimal viable ; puis **Phase B**, implementation du MVP
strictement conforme a cette specification.

### Module `final_engine` (nouveau, Phase B)

`src/sys_foot_quant/final_engine/` - orchestrateur en 6 modules, un par
niveau, jamais un monolithe :

| Module | Niveau | Contenu |
|---|---|---|
| `prediction.py` | A - Prediction | `predict_match()` - reutilise SANS MODIFICATION `PoissonModel`/`DixonColesModel`/`XGModel` ; `PRIMARY_MODEL = "poisson_simple"` (**CHOIX ARCHITECTURAL - NON VALIDE COMME SOURCE D'EDGE**), `dixon_coles`/`xg_model` calcules en parallele comme modeles de controle, jamais fusionnes (aucun ensemble, aucune ponderation apprise - **HYPOTHESE FUTURE** non integree) |
| `calibration.py` | B - Calibration | `calibrate_prediction()` - applique la correction scalaire E7/E8 (**VALIDEE SCIENTIFIQUEMENT**, principe non modifie) puis derive la distribution de buts ET les probabilites O/U d'une seule matrice reconstruite |
| `pricing.py` | C - Pricing | `compute_fair_price()` - transformation deterministe `1/p`, aucune donnee de marche |
| `market.py` | D - Market comparison | `compare_over_under_to_market()` - reutilise SANS MODIFICATION `market_engine.model_vs_market.compare_model_to_market` et `value_engine.edge.{edge,expected_value}` ; n'accepte QUE des cotes d'ouverture (aucune reference de code a `closing_odds_1x2_by_bookmaker`/`closing_over_under_2_5_by_bookmaker`, verifie par test AST) |
| `gates.py` | E - Qualification | Gates scientifiques (`insufficient_data_gate`, `insufficient_calibration_history_gate`, `ambiguous_day_gate`, `incomplete_market_odds_gate`, `distribution_consistency_gate`, `calibration_zone_gate`, `discrimination_gate`) et operational gates (`OperationalThresholds` - **PARAMETRE OPERATIONNEL A VALIDER**, `min_edge_threshold` explicitement `None` par defaut, jamais fixe par E1-E16) |
| `decision.py` | F - Decision | `decide()` - `NO_BET` des qu'un gate se declenche, sinon `BET` (chemin de code atteignable mais jamais emprunte avec la configuration operationnelle par defaut du MVP, puisque `edge_threshold_gate` se declenche systematiquement tant que `min_edge_threshold` reste `None`) |
| `orchestrator.py` | A->F | `run_match_decision()` - assemble les 6 niveaux, produit `MatchDecisionOutput` |
| `types.py` | - | Dataclasses de sortie immuables par niveau (`ModelPrediction`, `CalibratedGoalDistribution`, `PricingResult`, `MarketComparisonResult`, `GateResult`, `QualificationResult`, `DecisionResult`, `MatchDecisionOutput`) |
| `reference_tables.py` | - | Tables FIGEES issues d'E4/E11/E15 (`discrimination_status` par championnat - Liga/Ligue 1 = DEMONTREE, Premier League = NON_DEMONTREE, tout autre championnat = NON_EVALUEE par defaut prudent ; `calibration_status_for` par seuil - zone [0.6,0.7) d'Over 2.5 = ZONE_BIAISEE_NON_CORRIGEE, seuils 0.5/4.5 = INSUFFICIENT_VALIDATION) - jamais recalculees en ligne |
| `reason_codes.py` | - | Codes `NO_BET` stables (section 14 de la specification) |

Primitives **portees verbatim** de `scripts/` vers `src/` (aucune nouvelle
logique, section 1 de la specification) :
`football_model/goal_distribution.py` (`over_under_probs`,
`total_goals_distribution`, `check_distribution_validity`,
`check_over_under_monotonic`, `check_over_under_matches_distribution` -
identiques a `scripts/run_stage15_e7_total_goals_distribution.py`) et
`calibration_engine/scalar_correction.py` (`fit_scale_correction_as_of`,
`attach_walk_forward_scale` - identiques a
`scripts/run_stage16_e8_walk_forward_validation.py`, verifie par un test
de non-regression numerique dedie).

### Exclusions verifiees (Etape 19 de la Phase B)

Le code du moteur final ne contient, comme source de signal ou de
decision : ni recalibration locale E14, ni mouvement de marche E16, ni
desaccord modele/marche comme signal, ni coefficient Premier League, ni
dispersion multi-bookmaker comme edge, ni ensemble de modeles non valide,
ni seuil de pari optimise, ni backtest de rentabilite - chacune de ces
exclusions est verifiee par un test dedie (`tests/unit/test_final_engine_scientific_non_regression.py`,
`tests/leakage/test_final_engine_point_in_time.py`), pas seulement
affirmee en commentaire.

### Ce que le moteur final EST et N'EST PAS

Le moteur final est un systeme d'analyse probabiliste et de qualification
de prix : il projette une distribution de buts calibree (E7/E8), la
compare a un prix de marche d'ouverture (benchmark, jamais un adversaire),
et qualifie la confiance de cette projection via des gates scientifiques
avant de rendre une decision. Il n'est **jamais** presente comme rentable,
predictif garanti, ou superieur au marche - aucune experience d'E1-E16 ne
demontre une telle propriete. Dans sa configuration MVP par defaut
(`docs/final_engine_specification.md` section 19), il ne produit **que**
des decisions `NO_BET` motivees, faute de regle de conversion edge->pari
validee - voir `docs/final_engine_user_guide.md` pour le detail cote
utilisateur.

### Phase C - cadrage methodologique de la decision BET/NO BET (terminee)

`docs/operational_validation_specification.md` cadre - sans fixer aucun
seuil, sans lancer aucun backtest, sans modifier le moteur - la maniere
dont un futur seuil operationnel (`min_edge_threshold`) pourrait un jour
etre valide scientifiquement : distinction stricte entre exactitude
probabiliste (A), existence d'un edge theorique (B) et rentabilite
operationnelle (C, jamais demontree par E1->E16) ; proprietes qu'un
seuil devrait demontrer (performance OOS, stabilite temporelle/
championnat/saison, robustesse, incertitude) ; protocole train/
validation/test pre-specifie unique (section 13 du document) ; regle de
selection de seuil qui exclut explicitement le critere "meilleur ROI
historique" (surajustement) ; distinction `estimated_edge` vs
`uncertainty_of_edge` (toute metrique combinee - ex. edge/incertitude -
marquee HYPOTHESE FUTURE, non implementee) ; traitement dedie de la
Premier League (E15) et de la zone [0.6,0.7) d'Over 2.5 (E14), sans
aucune decision ad hoc prise ici ; et les trois etats conceptuels de
decision (`NO BET - NO EDGE` / `NO BET - EDGE NON VALIDE` / `BET - EDGE
OPERATIONNELLEMENT VALIDE`, ce dernier explicitement indisponible tant
qu'aucun protocole OOS dedie ne l'a valide). Aucun code de production
n'a ete modifie a l'occasion de ce cadrage.

### Phase D - validation experimentale du mecanisme BET/NO BET (executee, verdict negatif)

`docs/operational_validation_report.md` documente la premiere et seule
experience destinee a determiner si le moteur peut produire des `BET` -
protocole pre-enregistre (grille de seuils et separation temporelle
derivees STRUCTURELLEMENT d'artefacts deja figes du projet - E9/E13 pour
la grille de raw_edge, E1 pour price_edge>0, split_burn_in_calibration_test
d'E2/E7/E8 pour la separation rodage/VALIDATION/TEST 40/30/30 - jamais
choisies en observant un resultat), execute UNE SEULE FOIS sur donnees
reelles (Liga+Ligue1, poisson_simple, Over 2.5 principal, Under 2.5 et
Premier League en controles secondaires jamais poolables). **Verdict :
`NO BET - EDGE NON VALIDE`** - les 3 candidats pre-enregistres
(raw_edge>=0.05, raw_edge>=0.10, price_edge>=0.0) sont tous rejetes sur
le segment VALIDATION (aucun IC95% de profit entierement positif ni
superieur a la baseline marche seul) ; le segment TEST n'a donc jamais
ete touche, conformement au protocole. Resultat explicatif cle : le
sous-ensemble de matchs qu'un seuil d'edge selectionnerait est
precisement celui ou le modele est SUR-CONFIANT (p_model moyen ~0.64-0.68
vs frequence reelle ~0.48-0.49) - confirmation, via une simulation directe
du moteur reel, du mecanisme deja identifie en E5/E10/E11/E12. `min_edge_
threshold` reste `None`, aucun code du moteur n'a ete modifie (seul un
bug de cle de championnat dans `reference_tables.py`, "ligue1" vs
"ligue_1", a ete corrige avant execution - voir l'annexe du rapport).
`BET` n'est pas active.

## 2.1 Synthese consolidee de la campagne experimentale E1 -> E16 (phase economique)

La campagne experimentale E1 -> E16 (phase economique, resumee ligne par
ligne dans les lignes `data_engine`/`calibration_engine`/`market_engine`
ci-dessus) est desormais close - voir `docs/research_synthesis_e1_e16.md`
pour la synthese consolidee complete (matrice E1->E16 classee
🟢 VALIDE / 🟡 PROMETTEUR-A CONFIRMER / 🔴 REJETE-NON DEMONTRE /
⚪ LIMITE-ABSENCE DE PREUVE, et `docs/research_framework.md` section AB
pour le pointeur). Conclusions architecturales principales de cette
synthese, retenues ici pour reference rapide :

- **Modele de buts** : `poisson_simple`, `dixon_coles` et `xg_model`
  restent tous les trois inchanges - aucune hierarchie n'est demontree
  entre eux (E11 : statistiquement indiscernables en Brier sur l'O/U apres
  correction E7/E8 ; `dixon_coles` est mathematiquement redondant avec
  `poisson_simple` sur Over 2.5/3.5 specifiquement, fait deja etabli en K).
  Aucun ensemble des trois modeles n'a ete teste - **hypothese future non
  validee**.
- **Distribution officielle** : la matrice de score unique corrigee par le
  facteur scalaire walk-forward d'E7/E8 (Verdict A) reste la seule couche
  de calibration validee pour la production ; **E14 (recalibration locale
  de la zone [0.6,0.7) d'Over 2.5) est explicitement exclue de la
  production** (gate de coherence inter-seuils viole, instabilite par
  championnat).
- **Marche** : le moteur ne doit **jamais** etre concu selon l'hypothese
  "modele > marche" - aucune des 16 experiences ne le demontre. Le marche
  (B365 ouverture) doit etre traite comme un **benchmark de prix**, jamais
  une cible a battre ; le desaccord modele/marche, le mouvement
  ouverture->cloture (E16) et la dispersion multi-bookmaker (E9/E13) sont
  tous rejetes comme sources d'edge.
- **Limites connues explicitement documentees** : zone [0.6,0.7) d'Over
  2.5 (sur-confiance demontree, non corrigee), Premier League (absence de
  discrimination confirmee 3x, calibration correcte, cause non identifiee
  - interdiction de creer un coefficient PL sans nouvelle experience).
- **Moteur minimal viable** (section 13 de la synthese) : projection,
  pricing, comparaison marche et gates de qualification sont livrables
  aujourd'hui sans hypothese nouvelle ; **aucune regle de conversion
  probabilite/edge -> decision de pari positive n'est validee** - la seule
  decision scientifiquement defendable a ce stade est une abstention
  conditionnelle aux gates (championnat, zone de calibration, disponibilite
  des donnees).
- **Verdict** : `RESEARCH PHASE CLOSED` pour la question centrale
  "existe-t-il un edge demontrable sur le marche d'ouverture" (posee sous
  6 angles independants, toujours negative ou contradictoire) ; un seul
  fil optionnel et non bloquant reste ouvert (mesure independante de la
  dispersion du niveau des equipes en Premier League).

**Aucun code de moteur de production n'a ete modifie ou ecrit a l'occasion
de cette synthese** - elle est strictement documentaire, en attente d'une
instruction separee avant implementation.

Detail des etapes : voir `docs/research_framework.md` (section H) pour le
protocole ayant guide l'etape 2, et les scripts `scripts/run_stage2_walk_forward.py`
/ `scripts/run_stage3_value_engine.py` pour les resultats empiriques (tous
sur donnees synthetiques - voir avertissements dans chaque script). Le
Risk Engine (etape 4) n'a pas de script de resultats empiriques dedie :
ses simulations Monte Carlo sont theoriques (comparaison de strategies de
mise sur un flux de paris hypothetique), pas une evaluation sur le
dataset synthetique des etapes 1-3 - voir rapport d'etape 4 (message de
livraison) pour le detail.

## 3. Ce qui est implemente a l'etape 1

- **Schemas de donnees** (`data_engine/schemas/entities.py`) : `Team`,
  `Match`, `MatchResult`, `OddsSnapshot`, valides par pydantic. Toute
  table de faits herite de `PointInTimeFact` et porte un
  `knowledge_time` obligatoire, timezone-aware (UTC). `Match` refuse une
  configuration ou `knowledge_time > kickoff_time`.
- **Generateur synthetique deterministe**
  (`data_engine/synthetic/generator.py`) : aucune source reelle
  configuree pour l'instant. Pour un `seed` donne, produit un dataset
  reproductible avec une structure temporelle realiste (fixtures connues
  bien avant le coup d'envoi, resultats connus apres, cotes publiees a
  plusieurs echeances avant le coup d'envoi).
- **Stockage** (`data_engine/storage/writer.py`) : ecriture Parquet,
  format canonique "au repos".
- **Repository point-in-time** (`data_engine/storage/repository.py`) :
  seul point d'acces autorise aux donnees pour tout module en aval.
  `get_as_of(entity, timestamp)` filtre strictement sur
  `knowledge_time <= timestamp`. Le nom de table est valide contre une
  liste blanche avant toute interpolation SQL ; le timestamp est toujours
  passe en parametre lie. Une methode `debug_get_full_table` existe
  explicitement pour les tests/diagnostics et ne doit jamais etre
  utilisee par un module de decision.
- **Backtester chronologique minimal**
  (`backtesting_engine/engine.py`) : itere une liste de
  `decision_times` strictement (non-decroissante), interroge le
  Repository a chaque instant, et delegue a un callback fourni par
  l'appelant. Aucune strategie n'est integree - le callback utilise dans
  les scripts est un stub de diagnostic explicitement documente comme
  tel.

## 4. Ce qui N'est PAS implemente (volontairement)

Aucun modele de prediction (Poisson, Elo, xG, Dixon-Coles), aucune
calibration, aucun retrait de marge/calcul d'EV, aucun Kelly/flat
betting, aucun live betting. Ces modules existent comme paquets Python
vides avec un docstring renvoyant a leur etape prevue, pour que
l'arborescence documentee soit visible sans que leur contenu preempte les
etapes suivantes.

## 5. Technologies utilisees a l'etape 1

- Python 3.11+, gestion de dependances via `uv`.
- DuckDB (moteur de requetage) + Parquet (stockage au repos).
- pydantic v2 (contrats de donnees).
- pandas / numpy (manipulation, generation synthetique).
- Typer (CLI des scripts).
- pytest + Hypothesis (tests, notamment property-based pour l'anti-look-ahead).

## 6. Prochaine etape (non commencee)

Etape 2 : modele Poisson simple + CalibrationEngine (Brier, log loss,
reliability diagrams) + benchmarks (naif, Elo, marche sans marge - avec
la prudence actee au point 1 ci-dessus).
