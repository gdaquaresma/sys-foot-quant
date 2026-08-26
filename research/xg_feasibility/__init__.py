"""Outillage de recherche pour la phase de faisabilite B3 (xG) -
docs/research_framework.md section B3.

IMPORTANT - ce paquet est DELIBEREMENT ISOLE du Football Model :
- N'est JAMAIS importe par ``src/sys_foot_quant`` (verifie : aucun module
  de ``src/`` ne reference ``research``).
- N'est PAS inclus dans le paquet distribue (voir ``[tool.hatch.build...]``
  dans ``pyproject.toml`` : seul ``src/sys_foot_quant`` est empaquete).
- Ne modifie, n'importe, ni n'affecte aucun modele existant
  (``PoissonModel``, ``DixonColesModel``, ``RecentFormModel``,
  ``HeadToHeadModel``, ``BayesianSequentialModel``), aucun script
  ``scripts/run_stage*``, aucune donnee synthetique de ``data/``.

Objectif unique : mesurer empiriquement le risque de revision historique
des valeurs xG d'Understat (docs/research_framework.md section B3, point
3 du protocole valide par l'utilisateur), PAS entrainer ou tester un
modele xG - voir le README.md de ce dossier pour le mode d'emploi complet.
"""
