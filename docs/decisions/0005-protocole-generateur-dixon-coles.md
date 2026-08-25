# ADR 0005 - Protocole de generation d'un scenario a correlation basse-score (prealable a B1 / Dixon-Coles)

## Statut
**Propose - NON implemente, en attente de validation explicite.** Aucun
code n'a ete modifie pour produire ce document (`data_engine/synthetic/generator.py`
reste exactement dans l'etat valide aux etapes 2-5).

## Contexte
`docs/research_framework.md` (section B1) classe la correction Dixon-Coles
"Interessante" et prevoit un protocole de test hors echantillon cible sur
le sous-ensemble des scores bas (0-0, 1-0, 0-1, 1-1). Ce protocole n'est
pas exploitable en l'etat : le generateur synthetique
(`data_engine/synthetic/generator.py`, lignes 174-175) tire les buts par
DEUX appels independants a `rng.poisson()` :

```python
home_goals = int(rng.poisson(lam=lam_home))
away_goals = int(rng.poisson(lam=lam_away))
```

Aucune correlation entre les deux tirages n'existe donc, par construction,
dans les scenarios "constant" et "drift" deja valides (etapes 2-5).
Tester Dixon-Coles sur ces donnees ne peut mecaniquement produire qu'un
resultat non informatif (H0 non rejetee par absence du phenomene cible,
pas par refutation du mecanisme) - constat deja pose lors de la
proposition du protocole etape 5 et confirme par votre decision de ne pas
implementer B1 avant d'avoir statue sur ce point.

## Le mecanisme Dixon-Coles exact (rappel, Dixon & Coles 1997)

Le modele ne remplace pas les lois marginales (buts domicile/exterieur
restent chacun Poisson(lambda)/Poisson(mu)) : il pondere la loi JOINTE
par un facteur correctif tau, defini uniquement sur les quatre cellules
bas-score :

```
tau(0,0) = 1 - lambda*mu*rho
tau(0,1) = 1 + lambda*rho
tau(1,0) = 1 + mu*rho
tau(1,1) = 1 - rho
tau(x,y) = 1                    pour x>=2 ou y>=2

P(X=x, Y=y) = tau(x,y) * Poisson(x; lambda) * Poisson(y; mu)
```

`rho` est un scalaire unique (typiquement negatif, de l'ordre de -0.1 a
-0.2 dans les ajustements empiriques originaux de Dixon & Coles sur le
football anglais) : `rho < 0` rend 0-0 et 1-1 MOINS probables, et 1-0/0-1
PLUS probables que sous l'hypothese d'independance - la lecture
qualitative donnee par les auteurs est qu'une equipe qui prend l'avantage
tot change la dynamique du match (l'equipe menee attaque davantage),
rendant les scores serres asymetriques moins frequents que ne le predit
un Poisson pur.

Contrainte de validite : tau(x,y) >= 0 pour les quatre cellules impose
`rho` dans l'intervalle `[max(-1/lambda, -1/mu), 1/(lambda*mu)]`. Pour nos
lambda/mu typiques (base 1.35/1.10, multiplies par des ratios
attaque/defense centres sur 1.0), un `rho` negatif modere (ex. -0.10 a
-0.15) reste valide dans l'immense majorite des cas, mais PAS
garanti dans la queue extreme de la distribution log-normale des forces
d'equipe (derive cumulee + tirage extreme -> lambda tres eleve peut
violer `rho >= -1/lambda`). Ceci doit etre valide explicitement a
l'execution, pas suppose.

## Modifications precises requises dans le generateur

Cinq changements, localises et minimaux - **aucun changement au reste du
pipeline** (schemas, Repository, knowledge_time, backtesting_engine ne
sont pas concernes) :

1. **Nouveau parametre de configuration**, `dixon_coles_rho: float = 0.0`
   dans `SyntheticDataConfig` (`common/config.py`). Valeur par defaut 0.0
   = comportement actuel INCHANGE (retro-compatible : les configs
   `stage2_walk_forward*.yaml` deja valides continuent de produire
   exactement les memes donnees si le champ n'est pas renseigne).

2. **Remplacement du tirage des buts** (generator.py lignes 174-175) :
   au lieu de deux `rng.poisson()` independants, construire la matrice de
   score jointe tronquee (reutiliser `football_model.scoring.score_matrix(lam_home,
   lam_away, max_goals=...)`, deja testee), appliquer tau(x,y; rho) aux
   quatre cellules bas-score, RENORMALISER la matrice entiere (la somme
   change legerement puisque tau ne modifie que 4 cellules sur
   `(max_goals+1)^2` - la version academique originale ne renormalise pas
   pour de petits rho car l'ecart est negligeable, mais pour un
   generateur qui doit rester une distribution de probabilite EXACTE,
   nous renormalisons explicitement et documentons que notre `rho`
   synthetique n'est donc pas identique bit-a-bit au rho d'un ajustement
   MLE reel - c'est un analogue controle, pas une replication), puis
   tirer UN SEUL couple (home_goals, away_goals) par echantillonnage
   discret 2D pondere par cette matrice (`rng.choice` sur les indices
   aplatis, puis `np.unravel_index`) - remplace les deux tirages
   independants.

3. **Garde-fou de validite explicite** : avant d'appliquer tau, verifier
   `rho` dans `[max(-1/lam_home, -1/lam_away), 1/(lam_home*lam_away)]`
   pour CE match. Si viole (queue extreme), lever une erreur explicite
   plutot que d'ecreter silencieusement `rho` au vol (un ecretage
   silencieux serait indiscernable, plus tard, d'un ajustement fait pour
   "faire marcher" le scenario - a eviter absolument). Un echec sur un cas
   extreme rare doit se traiter en amont (choix d'un `rho` plus modere
   ou de bornes de derive/force plus resserrees pour ce scenario
   specifique), jamais par un correctif silencieux dans la boucle de
   generation.

4. **Coherence du marche synthetique ("informe mais imparfait")** :
   `_true_outcome_probabilities` (utilisee pour centrer le marche sur les
   vraies probabilites d'issue, principe deja acte a l'etape 2) doit-elle
   integrer la meme correction tau, ou rester une approximation
   independante-Poisson comme aujourd'hui ? **Question ouverte, a
   trancher AVANT implementation** :
   - Option A (marche pleinement informe) : `_true_outcome_probabilities`
     applique aussi tau(x,y; rho) - coherent avec le principe deja etabli
     "le marche est centre sur les VRAIES probabilites", puisque la vraie
     distribution generatrice inclut desormais la correlation.
     Recommandee par defaut pour rester coherent avec la decision deja
     prise a l'etape 2 (correction du marche synthetique).
   - Option B (marche naif) : le marche continue de pricer sur
     l'hypothese d'independance, ignorant la correlation reelle - cree un
     scenario ou meme le "marche informe" laisse un edge structurel
     exploitable sur les scores bas. Interessant en soi (mecanisme proche
     d'un biais de pricing reel), mais c'est un AJOUT d'hypothese
     distincte (le marche est imparfait d'une facon specifique et
     nouvelle), pas neutre pour l'interpretation du test B1 lui-meme -
     risquerait de brouiller la question testee (Dixon-Coles ameliore-t-il
     le MODELE, independamment de ce que fait le marche ?).
   Recommandation : Option A pour le scenario dedie a B1, en gardant
   Option B comme extension separee et explicitement etiquetee si elle
   est un jour voulue (pas la meme question de recherche).

5. **Nouveau scenario dedie, configs existants non touches** : creer
   `configs/stage5_dixon_coles.yaml`, copie du scenario "constant" deja
   valide (`stage2_walk_forward.yaml`) avec `dixon_coles_rho` fixe a une
   valeur unique choisie AVANT toute execution (candidat : -0.13, ordre de
   grandeur cite par Dixon & Coles 1997 sur le football anglais - a
   documenter comme choix litteraire, pas ajuste sur nos donnees). Prevoir
   aussi une variante `dixon_coles_rho: 0.0` sur le meme scenario (donc
   strictement identique au scenario "constant" existant) comme
   controle negatif complementaire, sur le modele des controles E1/E7 :
   Dixon-Coles ne doit PAS ameliorer significativement sur Poisson simple
   quand `rho=0` est vraiment nul, sans quoi le pipeline de test lui-meme
   serait suspect. `stage2_walk_forward.yaml` et
   `stage2_walk_forward_drift.yaml` restent inchanges (deja valides,
   utilises par A1/A2/B2).

## Consequences pour le protocole de test B1 (rappel, deja pre-enregistre en etape 5)

- Metrique cible : Brier restreint au sous-ensemble bas-score {0-0, 1-0,
  0-1, 1-1} ET Brier global, rapportes separement.
- Le diagnostic Chi-Deux (`calibration_engine/goodness_of_fit.py`) devra
  etre applique avec les lambda/mu VRAIS reconstruits depuis
  `true_team_strength` comme reference (meme technique d'attribution
  "modele vs generateur" que le diagnostic etape 2), mais la distribution
  de reference elle-meme doit desormais integrer tau(x,y; rho) - sinon la
  comparaison serait faite contre une distribution theorique erronee.
- Aucune modification des scenarios "constant"/"drift" deja valides
  (A1/A2/B2 restent calcules sur des donnees inchangees) : le nouveau
  scenario est additif, jamais un remplacement.
- `dixon_coles_rho` (valeur retenue) et la borne de validite (point 3)
  sont geles avant tout walk-forward - aucun ajustement post-hoc,
  identique a la discipline deja appliquee a la demi-lie A1 (45j) et au
  `prior_strength` B2 (10.0).

## Ce que ce document NE decide PAS

- Ne lance aucune implementation de Dixon-Coles (parametres tau/xi,
  estimation MLE) : c'est l'etape suivante, distincte, une fois ce
  protocole de generateur valide.
- Ne tranche pas Option A vs B (point 4) sans validation explicite.
- Ne modifie aucun fichier de code.
