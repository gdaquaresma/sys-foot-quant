/** Tests ciblés pour `starredMatches.ts` - stockage localStorage pur,
 * aucun appel réseau, aucun lien avec le moteur ou le journal Shadow Mode. */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { isMatchStarred, listStarredMatches, subscribeStarredMatches, toggleStarredMatch, updateStarredMatch } from './starredMatches'

const MATCH = { match_id: 'm1', competition: 'ligue1', season: '2026_27', home_team: 'Lens', away_team: 'Lyon' }

beforeEach(() => {
  window.localStorage.clear()
})

describe('toggleStarredMatch / listStarredMatches / isMatchStarred', () => {
  it('ajoute un match non encore étoilé', () => {
    expect(isMatchStarred('m1')).toBe(false)
    toggleStarredMatch(MATCH)
    expect(isMatchStarred('m1')).toBe(true)
    expect(listStarredMatches()).toHaveLength(1)
    expect(listStarredMatches()[0].match_id).toBe('m1')
  })

  it('retire un match déjà étoilé (bascule), jamais un doublon', () => {
    toggleStarredMatch(MATCH)
    toggleStarredMatch(MATCH)
    expect(isMatchStarred('m1')).toBe(false)
    expect(listStarredMatches()).toHaveLength(0)
  })

  it('horodate l’ajout', () => {
    toggleStarredMatch(MATCH)
    expect(listStarredMatches()[0].starred_at).toBeTruthy()
    expect(() => new Date(listStarredMatches()[0].starred_at).toISOString()).not.toThrow()
  })

  it('gère plusieurs matchs indépendamment', () => {
    toggleStarredMatch(MATCH)
    toggleStarredMatch({ ...MATCH, match_id: 'm2', home_team: 'Monaco', away_team: 'Toulouse' })
    expect(listStarredMatches()).toHaveLength(2)
    toggleStarredMatch(MATCH)
    expect(listStarredMatches()).toHaveLength(1)
    expect(listStarredMatches()[0].match_id).toBe('m2')
  })

  it('démarre avec my_pick/result à null - jamais une valeur devinée à l’ajout', () => {
    toggleStarredMatch(MATCH)
    expect(listStarredMatches()[0].my_pick).toBeNull()
    expect(listStarredMatches()[0].result).toBeNull()
  })
})

describe('updateStarredMatch', () => {
  it('enregistre le côté choisi et le résultat déclarés par l’utilisateur', () => {
    toggleStarredMatch(MATCH)
    updateStarredMatch('m1', { my_pick: 'Under' })
    expect(listStarredMatches()[0].my_pick).toBe('Under')
    expect(listStarredMatches()[0].result).toBeNull()

    updateStarredMatch('m1', { result: 'won' })
    expect(listStarredMatches()[0].my_pick).toBe('Under') // préservé, pas écrasé
    expect(listStarredMatches()[0].result).toBe('won')
  })

  it('n’a aucun effet sur un match qui n’est plus étoilé - jamais une exception', () => {
    expect(() => updateStarredMatch('does-not-exist', { result: 'won' })).not.toThrow()
    expect(listStarredMatches()).toHaveLength(0)
  })
})

describe('subscribeStarredMatches', () => {
  it('notifie les abonnés à chaque ajout/retrait', () => {
    const callback = vi.fn()
    const unsubscribe = subscribeStarredMatches(callback)

    toggleStarredMatch(MATCH)
    expect(callback).toHaveBeenCalledTimes(1)
    toggleStarredMatch(MATCH)
    expect(callback).toHaveBeenCalledTimes(2)

    unsubscribe()
    toggleStarredMatch(MATCH)
    expect(callback).toHaveBeenCalledTimes(2) // plus notifié après désabonnement
  })
})
