# Note PIT — cas Le Mans–Lens (13/09/2026 15:15 UTC), comportement intentionnel

## Constat

Dans le calcul BASELINE vs CURRENT pour Brest–PSG (`decision_time =
2026-09-13 16:45:00 UTC`), le match **Le Mans 2-2 Lens** (coup d'envoi
2026-09-13 15:15:00 UTC, déjà terminé au moment du coup d'envoi de
Brest–PSG) est **exclu** de l'historique d'entraînement CURRENT — sur
648 matchs combinés (612 historique + 36 saison 2026/27), seuls **646**
sont réellement utilisés.

## Explication (comportement existant, INCHANGÉ)

`backtesting_engine.real_data_walk_forward.build_real_match_records`
attribue à chaque match un `goals_knowledge_time = kickoff_utc +
DEFAULT_GOALS_KNOWLEDGE_DELAY_HOURS` (= kickoff + 2h, constante déjà
existante, jamais modifiée par les travaux récents). `_goals_train_df`
filtre ensuite strictement sur `goals_knowledge_time <= decision_time`.

Pour Le Mans–Lens :

```
kickoff_utc            = 2026-09-13 15:15:00
goals_knowledge_time   = kickoff_utc + 2h = 2026-09-13 17:15:00
decision_time (cible)  = 2026-09-13 16:45:00
17:15 > 16:45  =>  EXCLU
```

Le match a bien eu lieu avant `decision_time`, mais le délai de 2h avant
que son score soit considéré "connu" par le système repousse sa
disponibilité après `decision_time`. C'est un choix de modélisation
délibéré et documenté depuis l'origine de `real_data_walk_forward.py` :
un score n'est jamais supposé connu instantanément au coup de sifflet
final, un délai réaliste de publication/confirmation est appliqué.

## Vérification de conformité

Ce comportement est **exactement celui déjà utilisé par E7/E8/`final_engine`**
sur l'ensemble du corpus historique — aucune règle nouvelle n'a été
introduite pour ce cas. Il a été observé ici pour la première fois avec
des données 2026/27 réelles simplement parce que c'est la première fois
qu'un match cible et un match d'entraînement potentiel tombent le même
jour avec un écart de moins de 2h.

## Décision

**Convention non modifiée.** Ce comportement est correct et doit être
conservé tel quel pour tout calcul futur impliquant des matchs
rapprochés dans le temps.
