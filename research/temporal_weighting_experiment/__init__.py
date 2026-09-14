"""Etude de recherche isolee : la ponderation temporelle des matchs
d'entrainement (poids decroissant avec l'age) ameliore-t-elle la
prediction Over/Under 2.5 hors echantillon par rapport au modele de
production actuel, qui pondere tous les matchs a egalite ?

IMPORTANT - ce paquet est DELIBEREMENT ISOLE (meme discipline que
``research/xg_feasibility``) :
- N'est JAMAIS importe par ``src/sys_foot_quant`` (donc jamais par
  ``final_engine/``, ``scripts/predict_match.py``, ni aucun module de
  production).
- Ne modifie, n'importe en ecriture, ni n'affecte ``football_model/weighting.py``,
  ``football_model/recent_form.py``, ``PoissonModel``/``DixonColesModel``/
  ``XGModel``, ``calibration_engine/scalar_correction.py``, ni aucun gate
  de ``final_engine/gates.py`` - tous reutilises EN LECTURE SEULE, jamais
  modifies.
- Ne reactive PAS ``recent_form.py`` dans un quelconque chemin de
  production - toute comparaison avec ce module reste une experience
  secondaire explicitement etiquetee comme telle.

Objectif unique : mesurer, PAS decider - voir ``README.md`` de ce
dossier pour le protocole complet et le rapport de resultats."""
