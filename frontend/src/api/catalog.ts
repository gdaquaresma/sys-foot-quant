/**
 * Miroir EXACT (valeurs, pas structure) de `data_engine.market_odds.
 * match_catalog.COMPETITIONS`/`SEASONS` (backend, lecture seule, INCHANGÉ) -
 * vérifié directement contre le module Python, jamais deviné. Aucune route
 * API ne liste ces identifiants aujourd'hui ; les coder en dur ici (plutôt
 * que de forcer l'utilisateur à taper un identifiant technique comme
 * "ligue1"/"2024_25") est une pure amélioration de présentation frontend,
 * zéro changement backend. À tenir à jour à la main si le catalogue backend
 * change un jour.
 *
 * Source UNIQUE partagée par toutes les pages qui proposent une sélection
 * compétition/saison (AnalyzeMatch, MatchExplorer) - jamais une copie
 * locale qui pourrait diverger d'une page à l'autre.
 */
export const COMPETITION_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'ligue1', label: 'Ligue 1' },
  { value: 'liga', label: 'La Liga' },
  { value: 'premier_league', label: 'Premier League' },
]

export const SEASON_OPTIONS: Array<{ value: string; label: string }> = [
  { value: '2024_25', label: '2024/25' },
  { value: '2025_26', label: '2025/26' },
  { value: '2026_27', label: '2026/27' },
]

/** Libellé humain pour un identifiant technique de compétition/saison déjà
 * connu de l'utilisateur via les menus déroulants ci-dessus (jamais un
 * identifiant brut type "ligue1"/"2024_25" affiché à l'écran). Repli sur la
 * valeur brute UNIQUEMENT si elle ne correspond à aucune option connue (ne
 * devrait jamais arriver puisque ces valeurs proviennent toujours du
 * catalogue déjà sélectionné via ces mêmes menus) - jamais un texte masqué
 * ou une erreur silencieuse. */
export function competitionLabel(value: string): string {
  return COMPETITION_OPTIONS.find((c) => c.value === value)?.label ?? value
}

export function seasonLabel(value: string): string {
  return SEASON_OPTIONS.find((s) => s.value === value)?.label ?? value
}
