# ADR 0003 - Prudence sur le benchmark marche (closing line)

## Statut
Accepte (principe de conception - module concerne, `market_engine` /
`value_engine`, pas encore implemente ; ce document fixe la regle avant
implementation).

## Contexte
Le prix de cloture ("closing line") est generalement considere comme
l'estimateur le plus efficient disponible sur un match. Il est tentant de
l'utiliser comme benchmark universel pour juger un modele. C'est une
erreur si on l'utilise pour evaluer une decision qui, historiquement,
n'aurait pas pu disposer de ce prix au moment ou elle etait prise.

## Decision
1. Le prix de cloture ne peut etre utilise comme **benchmark de
   probabilite** d'une decision pre-match que si son `knowledge_time`
   (l'instant de cette cotation) est anterieur ou egal au
   `decision_time` evalue - exactement la meme regle point-in-time
   appliquee a toute autre donnee (ADR 0001). Concretement : si le modele
   decide a T-24h avant le coup d'envoi, la cloture (T-quelques minutes)
   **n'est pas** un benchmark valide pour cette decision-la, puisqu'elle
   integre de l'information de marche accumulee entre T-24h et le coup
   d'envoi que le modele n'avait pas.
2. Pour un modele dont le point de decision est proche de la cloture
   (ou a la cloture elle-meme), la comparaison directe redevient legitime.
3. Dans tous les autres cas, la cloture sert a une chose different et
   toujours legitime : mesurer le **CLV** (closing line value) de nos
   propres prix pris, c'est-a-dire evaluer a posteriori la qualite de nos
   decisions par rapport a l'estimateur de marche le plus efficient
   disponible - un indicateur de qualite du processus, pas une
   pretention a avoir pu connaitre ce prix au moment de decider.

## Consequences
- Le futur Value/Market Engine devra exposer separement :
  - un **benchmark de decision** (marche sans marge, disponible au
    `decision_time` exact, via le Repository point-in-time comme toute
    autre donnee) ;
  - une **mesure de CLV** (comparaison a la cloture, explicitement
    labellisee comme une metrique de qualite post-hoc, jamais melangee
    au calcul d'edge pre-match).
- Toute metrique de performance qui utiliserait implicitement la cloture
  comme "vrai prix" pour calculer un edge pre-match doit etre consideree
  comme suspecte et documentee comme telle si elle est neanmoins
  utilisee a des fins d'analyse exploratoire.
