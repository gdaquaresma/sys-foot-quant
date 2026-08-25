# ADR 0004 - Reproductibilite deterministe, pas bit-a-bit

## Statut
Accepte (correction explicite apportee a la premiere version de
l'architecture).

## Contexte
La version initiale de l'architecture exigeait une reproductibilite
"bit-a-bit" des runs de backtest. C'est trop strict : selon la version de
pyarrow/DuckDB, la plateforme, ou l'ordre d'ecriture des row groups
Parquet, deux executions parfaitement correctes du meme code avec le
meme seed peuvent produire des fichiers differents octet pour octet, sans
que cela traduise le moindre probleme de fond.

## Decision
Le projet exige une reproductibilite **deterministe et verifiable**,
definie comme :

- pour une configuration et un `seed` donnes, deux generations
  independantes du dataset synthetique produisent un **contenu logique
  identique** (memes valeurs, ligne a ligne, une fois triees par cle
  primaire) ;
- pour un dataset et une sequence de `decision_times` donnes, deux
  executions independantes du backtester produisent une **trace de
  decision identique**.

La verification se fait par comparaison de contenu (`pandas.testing.
assert_frame_equal` apres tri, ou une empreinte de contenu -
`common/reproducibility.content_fingerprint`), jamais par diff de fichiers
bruts.

## Consequences
- `content_fingerprint` fournit une empreinte courte et stable, utile pour
  logger/comparer des runs sans stocker ni comparer les fichiers complets.
- Aucun test du projet ne doit comparer des fichiers Parquet octet pour
  octet, ni supposer un ordre physique des lignes stable sans tri
  explicite prealable.
- Cette regle s'applique aussi aux etapes futures (ex: entrainement d'un
  modele) : "reproductible" signifiera "memes resultats numeriques a une
  tolerance explicite pres", pas "memes fichiers".
