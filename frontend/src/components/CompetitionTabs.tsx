/**
 * Onglets de sélection de compétition - réutilisé par AnalyzeMatch,
 * MatchExplorer et Shadow (un onglet par championnat disponible côté
 * catalogue, voir `../api/catalog.ts::COMPETITION_OPTIONS`, INCHANGÉ ici).
 * Pure présentation : ne fait aucun appel réseau, ne décide d'aucune
 * disponibilité de données - se contente de notifier le changement de
 * sélection au composant appelant, qui reste seul responsable de charger
 * les données correspondantes.
 */
import { COMPETITION_OPTIONS } from '../api/catalog'

/** Classe de couleur par compétition - purement cosmétique (teinte de
 * l'onglet actif), jamais une information fonctionnelle : aucune
 * compétition n'est "meilleure" ou "plus fiable" qu'une autre de ce seul
 * fait. */
const COMPETITION_TAB_CLASS: Record<string, string> = {
  ligue1: 'tab-ligue1',
  liga: 'tab-liga',
  premier_league: 'tab-premier_league',
}

export function CompetitionTabs({
  value,
  onChange,
  includeAll = false,
}: {
  value: string
  onChange: (competition: string) => void
  /** Ajoute un onglet "Tous" en tête - utilisé par Shadow (historique),
   * jamais par AnalyzeMatch/MatchExplorer (qui exigent toujours une
   * compétition précise pour interroger le catalogue). */
  includeAll?: boolean
}) {
  const options = includeAll ? [{ value: '', label: 'Tous' }, ...COMPETITION_OPTIONS] : COMPETITION_OPTIONS
  return (
    <div className="competition-tabs" role="tablist" aria-label="Compétition">
      {options.map((c) => (
        <button
          key={c.value || 'all'}
          type="button"
          role="tab"
          aria-selected={value === c.value}
          className={`competition-tab ${c.value ? (COMPETITION_TAB_CLASS[c.value] ?? '') : 'tab-all'} ${value === c.value ? 'active' : ''}`}
          onClick={() => onChange(c.value)}
        >
          {c.label}
        </button>
      ))}
    </div>
  )
}
