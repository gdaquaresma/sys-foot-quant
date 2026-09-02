# Collecte panel élargi — ~50 nouveaux matchs football (checkpoint à 25)

Suite du protocole validé (`research/polymarket_universe_collection_report.md`,
`research/polymarket_trader_depth_audit.md`, `research/polymarket_trader_signal_pilot.md`,
`research/polymarket_trader_skill_methodology.md`). Décision : **Option 2** —
collecter ~50 nouveaux matchs, checkpoint obligatoire à ~25.

**Règles rappelées (contraintes contraignantes pour toute cette collecte)** :
- Sélection des matchs **avant** tout examen des trades — jamais en fonction
  d'un wallet, d'un nombre de trades/wallets, ou d'un résultat.
- Les 7 matchs déjà collectés restent le "seed historique" ; ne pas les
  utiliser pour orienter le choix des nouveaux matchs (ni par résultat, ni
  par fréquence de wallets).
- Marchés moneyline uniquement (Home win / Draw / Away win) — pas
  d'Over/Under, Asian Handicap, props.
- Aucune analyse trader pendant la collecte (pas de classement, P&L, ROI,
  "smart money").
- Accès réseau direct bloqué pour cet agent — protocole manuel navigateur
  inchangé : URL fournie ici → utilisateur fetch → colle le JSON → agent
  sauvegarde + dédup (`transactionHash`) + QC.
- Payloads bruts dans `research/polymarket_raw_exports/` (gitignored).
- Provenance conservée pour chaque match : event id/slug, market id,
  conditionId, token IDs, outcomes, startTime, endDate, resolution, URL de
  fetch, date de collecte.

## Étape 1 — Découverte des événements (sélection neutre, avant tout trade)

Même endpoint et mêmes filtres neutres que pour le premier panel (sport +
statut + tri chronologique uniquement, aucun critère trader) :

```
https://gamma-api.polymarket.com/events?tag_slug=soccer&closed=true&limit=40&order=startDate&ascending=false&offset=<N>
```

Le premier panel (7 matchs) provenait de `offset=0` (40 événements les plus
récents au 2026-09-01, résolus, tag `soccer`). Pour obtenir des matchs
**différents**, on avance `offset` par pas de 40 (événements plus anciens,
même filtre neutre, aucune sélection sur les trades).

| Batch offset | Statut | Événements reçus | Matchs distincts identifiés |
|---|---|---|---|
| 40 | à faire | — | — |

## Étape 2 — Matchs sélectionnés pour le nouveau panel

| # | Match | Compétition | Date | Home | Away | Moneyline markets | conditionIds | Trades | Wallets | QC |
|---|---|---|---|---|---|---:|---|---:|---:|---|

*(rempli au fur et à mesure — checkpoint obligatoire après ~25 matchs)*

## Étape 3 — Journal de collecte détaillé (QC par marché)

Voir `research/polymarket_raw_exports/COLLECTION_LOG.md` (fichiers numérotés
en continuité avec la collecte des 7 matchs initiaux, à partir du Fichier 31).

## Checkpoint à ~25 matchs — à calculer, PAS de test de skill

- nombre de matchs, marchés, trades, wallets ;
- wallet × match PIT ;
- wallets ≥2 matchs historiques, ≥3, ≥5 ;
- nombre de traders récurrents actifs ;
- notionnel des positions PIT ;
- distribution des trades par observation ;
- comparaison avec les 7 matchs initiaux.

**STOP obligatoire à ce stade. Pas de classement, pas de P&L, pas de test de
compétence. Décision de continuer jusqu'à ~50 prise avec l'utilisateur après
le checkpoint.**
