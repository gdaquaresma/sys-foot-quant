# xg_feasibility — mesure du risque de révision xG (Understat)

Outillage de recherche pour la phase de faisabilité **B3** (xG) —
`docs/research_framework.md` section B3. **Ceci n'est pas un connecteur
de production et ne fait partie d'aucun modèle** : voir la note
d'isolation dans `__init__.py`.

## Objectif unique

Répondre à une seule question, empiriquement plutôt que par hypothèse :
**les valeurs xG publiées par Understat pour un match donné sont-elles
stables dans le temps, ou révisées silencieusement ?** C'est le point 3
du protocole B3 validé — condition nécessaire avant d'envisager toute
utilisation du xG comme feature prédictive (voir
`docs/research_framework.md` section B3 et l'échange de validation du
protocole).

## Avertissement — non exécuté en direct depuis ce dépôt

Cette session de développement n'a **aucun accès réseau** à
`understat.com` (bloqué par la politique de l'environnement d'exécution
— confirmé via le proxy, 403 "policy denial"). Le module
`understat_source.py` a donc été écrit contre le format documenté par
plusieurs bibliothèques communautaires indépendantes (paquet PyPI
`understat`, projet `UnderData`), **jamais vérifié contre une réponse
HTTP réelle**. Toute la logique qui ne touche pas le réseau (décodage,
parsing, échantillonnage, stockage, comparaison) est couverte par des
tests unitaires avec fixtures (`tests/`, 20 tests, tous passants, aucun
réseau requis). **La première exécution réelle doit se faire sur une
machine avec accès internet** (voir Utilisation ci-dessous) — vérifiez
que `fetch_match_records` retourne des enregistrements non vides avant
de faire confiance à l'extraction.

## Protocole (2 extractions espacées dans le temps)

```
uv run python -m research.xg_feasibility.cli_extract \
    --league EPL --season 2024 --n-matches 200 --seed 20260826 \
    --out research/xg_feasibility/runs/extraction_1.json

# ... attendre 4-6 semaines, ne PAS changer --league/--season/--n-matches/--seed ...

uv run python -m research.xg_feasibility.cli_extract \
    --league EPL --season 2024 --n-matches 200 --seed 20260826 \
    --out research/xg_feasibility/runs/extraction_2.json

uv run python -m research.xg_feasibility.cli_compare \
    --first research/xg_feasibility/runs/extraction_1.json \
    --second research/xg_feasibility/runs/extraction_2.json
```

Le même `--seed` doit être réutilisé pour la deuxième extraction : avec
la même liste source de matchs déjà joués, il garantit un tirage
identique — condition nécessaire pour comparer exactement les mêmes
matchs. Ne JAMAIS changer les paramètres entre les deux extractions, et
ne jamais choisir l'échantillon après avoir vu un résultat (même
discipline que partout ailleurs dans ce projet — A1, B1, B2).

`cli_compare` rapporte, séparément pour xG domicile et extérieur : le
nombre de matchs communs, le nombre/proportion jugés "modifiés" (écart
absolu > `epsilon`, 0.005 par défaut — tolérance pour ignorer le bruit
d'arrondi, pas une vraie révision), l'écart absolu moyen/médian/p90/p99.

**Ne prétendez à aucune conclusion sur la stabilité d'Understat tant que
cette commande n'a pas tourné sur deux extractions réellement collectées
à des dates différentes** — c'est la règle explicitement posée par
l'utilisateur pour ce protocole.

## Fichiers

| Fichier | Rôle | Touche le réseau ? |
|---|---|---|
| `understat_source.py` | fetch + parse + normalisation | Oui (une seule fonction : `fetch_league_season_html`) |
| `sampling.py` | tirage fixe déterministe | Non |
| `storage.py` | sérialisation datée (JSON) | Non |
| `compare.py` | statistiques de révision | Non |
| `cli_extract.py` | CLI : une extraction | Oui (via `understat_source`) |
| `cli_compare.py` | CLI : compare deux extractions | Non |

## Ce que ce dossier NE fait PAS

- Aucun modèle xG, aucun `XGModel`, aucune hybridation xG/buts réels.
- Aucune modification de `poisson_simple`, d'aucun modèle existant, ni
  d'aucun résultat des étapes 1 à 5.
- Aucun calibrage, aucune sélection de paramètre sur des résultats.
- Aucune connexion à FootyStats (écarté pour raison de coût — voir
  échange de validation), ni à aucune autre source.

## Légalité — à lire avant d'exécuter

Understat n'a pas d'API publique officielle et ne publie pas, à notre
connaissance, de conditions d'utilisation explicites sur le scraping.
Ce n'est ni clairement permis ni clairement interdit. Avant la première
exécution : vérifiez `understat.com/robots.txt` depuis un navigateur, et
gardez un usage personnel, non commercial, à volume raisonnable (ce
protocole ne demande que quelques centaines de requêtes au total, pas un
crawl massif). C'est un choix qui reste le vôtre, pas une garantie
juridique de ce module.
