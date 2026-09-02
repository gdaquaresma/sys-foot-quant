# Méthodologie : compétence trader individuelle sans survivorship / look-ahead bias

Document méthodologique, pas un nouvel audit empirique. Construit exclusivement
sur les 21 marchés / 7 matchs / 1 672 trades / 529 wallets déjà collectés.
Aucun nouveau fetch, aucune modification du code de production, **aucun
classement de traders par performance** (aucun P&L, ROI, win rate ou score de
qualité n'est calculé nulle part dans ce document).

## 1. Faisabilité d'un score individuel PIT — EX ANTE vs POSTÉRIEUR

Un score wallet ne peut servir de signal walk-forward que s'il est
**calculable au moment du kickoff du match courant, en n'utilisant que des
matchs antérieurs**. Distinction stricte :

### Variables EX ANTE (connues avant le prochain match, walk-forward valide)

- nombre de matchs historiques tradés (PIT, avant N) ;
- nombre de matchs historiques avec exposition nette non nulle avant kickoff ;
- volume PIT cumulé historique (notionnel $) ;
- nombre de trades PIT cumulé historique ;
- répartition BUY/SELL historique ;
- type d'exposition historique (mono- vs multi-issue par match) ;
- prix moyen d'entrée historique (VWAP des trades passés — dit seulement
  *où* le wallet est entré, rien sur si c'était "juste") ;
- délai entre dernier trade et kickoff, pour un match déjà passé (recency) ;
- nombre de matchs/marchés distincts tradés ;
- fréquence d'apparition (matchs tradés / matchs disponibles depuis sa
  première apparition dans le panel).

Toutes ces variables sont **des faits d'activité passée**, disponibles avant
le match N. Elles décrivent *combien* et *comment* un wallet a été actif —
jamais *s'il a eu raison*.

### Variables POSTÉRIEURES (nécessitent le résultat ou une info future)

- tout P&L, ROI, win rate, Sharpe, cumulés ou par match ;
- CLV (closing line value) — nécessite le prix de clôture du marché, connu
  seulement après l'entrée du wallet, donc non disponible au moment de
  décider de suivre ce wallet sur le match courant ;
- "qualité de timing" au sens *a bien anticipé le mouvement de prix / le
  résultat* — par construction, seulement calculable après coup ;
- toute étiquette "smart money" / "dumb money" dérivée du résultat.

**Piège à noter explicitement** : "délai avant kickoff" et "prix moyen
d'entrée" sont EX ANTE en tant que *données* (le nombre existe avant le
résultat), mais leur **valeur prédictive** (est-ce que "trader tôt à bon
prix" veut dire quelque chose) est une question empirique qui, elle,
nécessite le résultat pour être évaluée — seulement en rétrospective, jamais
pour sélectionner un wallet avant coup. On peut calculer la variable en
walk-forward ; on ne peut pas valider son utilité en walk-forward avec 7
matchs.

## 2. "Trader historique" — définition non optimisée

Règles simples fixées a priori, pas choisies pour maximiser un résultat sur
ces 7 matchs :

| Seuil | Définition |
|---|---|
| ≥1 match historique | a eu ≥1 exposition PIT non nulle sur ≥1 match antérieur |
| ≥2 matchs historiques | idem, sur ≥2 matchs antérieurs distincts |
| ≥3 matchs historiques | idem, sur ≥3 matchs antérieurs distincts |
| ≥5 matchs historiques | idem, sur ≥5 matchs antérieurs distincts |
| Seuil d'activité (optionnel, à combiner) | ≥5 $ de notionnel PIT cumulé historique **et** ≥2 trades PIT cumulés historiques — seuil "activité non symbolique", pas un seuil de performance |

Le seuil d'activité (5 $ / 2 trades) reprend simplement la limite "quasi
symbolique" déjà identifiée dans l'audit de profondeur (28 % des observations
wallet × match pesaient < 5 $) — un plancher de bruit, pas un filtre de
qualité.

## 3. Profondeur réelle observée (7 matchs, ordre chronologique des kickoffs)

Pour chaque match, wallets **éligibles** (historique suffisant avant ce
match) vs wallets **effectivement actifs** (≥1 trade PIT) sur ce match :

| Match | Actifs PIT sur N | Éligibles ≥1 / actifs | Éligibles ≥2 / actifs | Éligibles ≥3 / actifs | Éligibles ≥5 / actifs |
|---|---|---|---|---|---|
| Liepaja vs Riga (1er) | 33 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Gagra vs Iberia (2e, ex æquo) | 9 | 33 / 4 | 0 / 0 | 0 / 0 | 0 / 0 |
| Torpedo vs Meshakhte (2e, ex æquo) | 18 | 33 / 8 | 0 / 0 | 0 / 0 | 0 / 0 |
| Sumqayit vs Qarabag | 13 | 45 / 8 | 13 / 5 | 2 / 2 | 0 / 0 |
| Tbilisi vs Dila Gori | 28 | 50 / 8 | 16 / 4 | 5 / 2 | 0 / 0 |
| Lanzhou vs Beijing (dernier, ex æquo) | 213 | 70 / 11 | 20 / 7 | 7 / 4 | 1 / 0 |
| Dalian vs Shanghai (dernier, ex æquo) | 80 | 70 / 6 | 20 / 4 | 7 / 4 | 1 / 0 |

**Diagnostic du goulot d'étranglement — les trois causes coexistent, à des
degrés différents selon le seuil :**

1. **Historique insuffisant, c'est la contrainte dominante en volume.** Les 3
   premiers matchs de la chronologie n'ont structurellement aucun wallet
   éligible ≥1 (aucune donnée antérieure n'existe encore) — inévitable avec
   seulement 7 matchs, indépendant de tout choix de seuil.
2. **Historique suffisant mais taux de conversion en activité faible, à
   ≥1 et ≥2.** Même une fois éligible, seuls 16-24 % des wallets ≥1-éligibles
   retradent effectivement le match suivant (8/50, 11/70, 6/70…) ; à ≥2, le
   taux monte à 25-38 % (5/13, 4/16, 7/20) — mieux, mais toujours minoritaire.
3. **À ≥3, le taux de conversion redevient élevé (40-100 %)** mais sur une
   base éligible minuscule (2, 5, 7, 7 wallets) — la vraie contrainte se
   déplace alors du "vont-ils revenir" au "sont-ils assez nombreux pour dire
   quoi que ce soit".
4. **Notionnel : même parmi les ≥2-éligibles actifs, la majorité des
   positions restent triviales.** Sur les 7 wallets ≥2-éligibles actifs au
   dernier match (Lanzhou/Beijing), 5 pèsent entre 2 $ et 13 $ de notionnel ;
   **seuls 2 wallets** (`0x9e3ed7b6…` et `0xe9076a87…`, ce dernier étant déjà
   identifié comme `suntori` dans les rapports précédents) affichent un
   notionnel substantiel et répété (2 174 $ et 3 327 $ sur ce seul match, avec
   un historique de trading sur plusieurs matchs). C'est la même paire de
   wallets qui domine le volume "récurrent" sur pratiquement tous les
   matchs tardifs de la chronologie.

**Conclusion du diagnostic** : le goulot n'est pas une seule cause isolée —
c'est un entonnoir à 3 étages (peu de retour → peu d'activité substantielle
parmi ceux qui reviennent → notionnel dérisoire sauf pour 1-2 wallets). Un
score de compétence individuelle basé sur "≥2 ou ≥3 matchs historiques" seul,
sans filtre d'activité, resterait dominé par du bruit à 2-13 $ de notionnel.

## 4. Pas de classement de performance

Aucun calcul de ce type n'a été fait dans ce document — uniquement des
comptages d'éligibilité, d'activité et de notionnel, tous fondés sur des
variables EX ANTE (section 1). Les deux wallets cités en section 3 le sont
pour leur **volume et leur récurrence observables**, jamais pour avoir
"gagné" un pari.

## 5. Méthodologie proposée pour ~50 matchs (walk-forward strict)

Boucle à appliquer match par match, dans l'ordre chronologique des kickoffs
(`endDate`/`startTime`, déjà validé) :

```
matchs = trier(tous les matchs, par kickoff croissant)
pour chaque match N dans matchs:
    historique = matchs[0 .. N-1]                     # jamais N ni après
    pour chaque wallet actif dans historique:
        calculer les variables EX ANTE (section 1) à partir de "historique" seul
    wallets_eligibles = filtrer selon la règle de "trader historique" (section 2),
                        fixée AVANT de lancer la boucle, jamais réajustée en cours de route
    positions_pit_N = trades du wallet sur N avec timestamp < kickoff(N)
    signal_N = agréger positions_pit_N des wallets_eligibles (même construction
               que le pilote précédent : imbalance BUY/SELL -> pseudo-probabilité,
               PLUS une variante pondérée par notionnel pour corriger le biais
               "1 wallet minoritaire domine" observé en section 3)
    comparer signal_N au prix de marché PIT (même méthode que le pilote)
    enregistrer le résultat de N (Brier, log loss, direction) -- SANS reboucler
    passer à N+1
apres la boucle: agréger les résultats enregistrés (jamais avant)
```

Points non négociables (déjà validés dans le pilote précédent, à conserver
sans changement) : kickoff = `endDate`/`startTime` ; exclusion stricte des
trades ≥ kickoff ; règle de combinaison marché+trader fixée a priori, jamais
réajustée sur les résultats observés ; unité d'évaluation match (pas market)
pour tout ce qui touche à la dépendance intra-match.

## 6. Que faut-il tester ?

| Hypothèse | Description | Verdict méthodologique |
|---|---|---|
| A — tous les traders | déjà testée dans le pilote (perd contre le marché) | à garder **uniquement comme ligne de référence**, pas comme objet d'étude principal |
| B — traders récurrents (≥2 ou ≥3) | filtre sur historique seul | insuffisant seul (section 3 : dominé par du bruit à faible notionnel) |
| **C — traders récurrents + activité significative** | filtre historique **et** seuil de notionnel/trades non symbolique (section 2) | **recommandé comme hypothèse prioritaire** — c'est la seule des options A-D qui répond directement au goulot à 3 étages identifié en section 3 |
| D — sélection par performance historique walk-forward | pondérer/sélectionner les wallets selon leur exactitude passée | **à ne pas tester avant ≥100 matchs** : avec 2-7 matchs d'historique maximum par wallet sur ce panel, toute estimation de "justesse passée" par wallet est du pur bruit — la tester maintenant reviendrait à sélectionner sur du hasard, précisément le survivorship bias que ce document cherche à éviter |
| E — autre méthode | non identifiée dans les données actuelles | rien dans les 7 matchs ne suggère une meilleure construction que C à ce stade |

**Recommandation unique pour l'expérience à 50 matchs : tester l'hypothèse
C (traders récurrents ≥2 matchs, filtrés par un seuil d'activité non
symbolique fixé a priori), avec A comme seule ligne de référence. Ne pas
tester D avant un panel nettement plus grand.**

## 7. Décision

### **Option 2 — Collecter ~50 matchs supplémentaires et appliquer la méthodologie ci-dessus (hypothèse C prioritaire, A en référence).**

Justification, à partir des données déjà observées :

- **Pas Option 1 (abandonner)** : le pilote précédent n'a testé que
  l'hypothèse A (tous les wallets, non filtrés par activité) — la plus
  simple et, d'après ce document, la plus polluée par du bruit à faible
  notionnel. L'hypothèse C, plus ciblée, n'a encore jamais été testée.
  Abandonner maintenant reviendrait à conclure sur une hypothèse qu'on n'a
  pas encore mise à l'épreuve.
- **Pas Option 3 (>100 matchs directement)** : la collecte reste manuelle et
  lente (un marché à la fois). Sans point de contrôle intermédiaire, rien ne
  garantit que la population de wallets ≥3-historique-et-actifs grandisse
  suffisamment ; c'est exactement le risque déjà signalé dans l'audit de
  profondeur précédent.
- **Pas Option 4 maintenant (changer d'hypothèse)** : prématuré tant que
  l'hypothèse C — la seule construite spécifiquement pour contourner le
  goulot identifié ici — n'a pas été testée sur un échantillon assez grand
  pour trancher.

**Règle de décision pré-enregistrée pour la suite** (à appliquer une fois les
50 matchs collectés et l'audit de profondeur reproduit, avant tout nouveau
test de signal) : si la population de wallets ≥3-matchs-historiques **et**
notionnel non symbolique reste de l'ordre de quelques unités (comme
aujourd'hui : 2 à 7 wallets selon le match), ce sera le signal qu'il faut
basculer vers l'**Option 4** (chercher un autre signal dérivé du comportement
Polymarket, pas la compétence individuelle des wallets) plutôt que
d'enchaîner sur l'Option 3. Cette règle est fixée maintenant, avant de voir
les 50 matchs, pour éviter toute décision biaisée a posteriori.
