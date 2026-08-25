# ADR 0001 - Modele temporel : event_time vs knowledge_time

## Statut
Accepte.

## Contexte
Le projet exige explicitement l'absence de look-ahead bias : aucune
donnee non disponible au moment T ne doit pouvoir influencer une decision
prise a T.

## Decision
Toute table de faits consommee par un module en aval du Data Engine porte
deux temps distincts :

- `event_time` (implicite ou explicite selon la table, ex : `kickoff_time`) :
  quand l'evenement s'est reellement produit.
- `knowledge_time` : quand le systeme aurait pu, au plus tot, avoir
  connaissance de cette information.

Le Repository est l'unique composant autorise a filtrer sur
`knowledge_time`. Aucun autre module ne doit lire les fichiers de donnees
directement.

## Consequences
- Une meme "verite" (ex: un score final) peut exister dans le stockage
  avant qu'elle soit "visible" pour le systeme a un instant donne - c'est
  voulu.
- Cela impose que chaque nouvelle source de donnees, a partir de l'etape
  ulterieure d'ingestion reelle, documente explicitement comment son
  `knowledge_time` est determine (timestamp de publication, delai de
  latence connu du fournisseur, etc.). Une source qui ne peut pas fournir
  cette information de facon fiable ne doit pas etre integree sans
  hypothese conservatrice explicite sur son delai de disponibilite.
