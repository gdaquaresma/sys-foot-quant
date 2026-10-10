/**
 * Étoile à cocher ("Mes paris", voir `../api/starredMatches.ts`) - bouton
 * pur, ne décide jamais lui-même de l'état : reçoit `starred` et appelle
 * `onToggle` au clic, le composant appelant reste seul responsable de lire
 * et d'écrire l'état réel (`useStarredMatches`).
 */
export function StarToggle({
  starred,
  onToggle,
  label,
}: {
  starred: boolean
  onToggle: () => void
  /** Nom du match, pour un libellé accessible précis (ex. "Lens – Lyon"). */
  label: string
}) {
  return (
    <button
      type="button"
      className={`star-toggle ${starred ? 'star-toggle-active' : ''}`}
      aria-pressed={starred}
      aria-label={starred ? `Retirer ${label} de mes paris` : `Ajouter ${label} à mes paris`}
      title={starred ? 'Retirer de mes paris' : 'Ajouter à mes paris'}
      onClick={(e) => {
        e.stopPropagation()
        onToggle()
      }}
    >
      {starred ? '★' : '☆'}
    </button>
  )
}
