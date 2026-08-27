"""Infrastructure d'import des cotes de marche REELLES (Football-Data.co.uk,
docs/decisions/0006-football-data-point-in-time.md) - phase economique du
projet, distincte de la campagne de modelisation A1-C7 (close).

Sous-modules :
- ``team_mapping`` : correspondance deterministe des noms d'equipe
  Football-Data <-> Understat, aucun fuzzy matching.
- ``time_resolution`` : conversion des horaires Football-Data (heure
  civile Royaume-Uni) vers UTC, et regle point-in-time conservatrice
  documentee (jamais un timestamp verifie).
- ``football_data_loader`` : lecture des CSV Football-Data, marche 1X2
  Bet365 uniquement, provenance explicite.
- ``matching`` : appariement Understat <-> Football-Data via cle de match
  normalisee.
"""
