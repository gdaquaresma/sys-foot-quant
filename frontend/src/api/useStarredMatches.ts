import { useCallback, useSyncExternalStore } from 'react'
import { listStarredMatches, subscribeStarredMatches, toggleStarredMatch, updateStarredMatch } from './starredMatches'

/** Source de vérité réactive pour "Mes paris" (voir `starredMatches.ts`) -
 * `useSyncExternalStore` garde tout composant abonné synchronisé dès
 * qu'une étoile est ajoutée/retirée/modifiée n'importe où dans
 * l'application, sans prop drilling ni état dupliqué. */
export function useStarredMatches() {
  const starred = useSyncExternalStore(subscribeStarredMatches, listStarredMatches, listStarredMatches)

  const isStarred = useCallback((matchId: string) => starred.some((m) => m.match_id === matchId), [starred])

  return { starred, isStarred, toggleStar: toggleStarredMatch, updateStar: updateStarredMatch }
}
