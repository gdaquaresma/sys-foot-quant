"""Snapshot manuel de cotes (remplace la recherche/integration d'un
fournisseur PIT externe, abandonnee - voir
``research/free_historical_odds_sources.md``).

Principe (design valide) : ``decision_time = capture_timestamp``, et
``capture_timestamp`` est TOUJOURS genere par le systeme au moment de la
creation du snapshot (``snapshot_engine.schema.create_snapshot``) -
jamais une valeur saisie librement par l'appelant. Voir
``schema.py`` pour la garantie structurelle (validee dans
``OddsSnapshot.__post_init__``, donc impossible a contourner meme par
construction directe du dataclass).

Ce module ne modifie ni ``final_engine/`` ni la methodologie E1-E16 : il
fournit uniquement une entree structuree alternative aux deux cotes
manuelles deja acceptees par ``scripts/predict_match.py``
(``--market-odds-over-2-5``/``--market-odds-under-2-5``), jamais un
second moteur de calcul."""
