import { describe, expect, it } from 'vitest'
import { analysisAvailability, fixtureTimingState, formatFixtureDate, formatLocalKickoffTime } from './fixtureTiming'
import type { MatchResponse } from './types'

function match(overrides: Partial<MatchResponse>): MatchResponse {
  return {
    match_id: 'm1',
    competition: 'ligue1',
    season: '2026_27',
    fixture_date: '2026-10-09',
    kickoff_local_naive: null,
    kickoff_utc: null,
    home_team: 'Lens',
    away_team: 'Lyon',
    is_played: false,
    ...overrides,
  }
}

describe('formatFixtureDate', () => {
  it('formate une date YYYY-MM-DD en date longue française, sans passer par Date (évite tout décalage de fuseau horaire)', () => {
    expect(formatFixtureDate('2026-10-09')).toBe('9 octobre 2026')
    expect(formatFixtureDate('2027-05-16')).toBe('16 mai 2027')
    expect(formatFixtureDate('2026-01-01')).toBe('1 janvier 2026')
  })

  it('retourne la chaîne telle quelle si le format ne correspond pas (jamais un plantage silencieux)', () => {
    expect(formatFixtureDate('not-a-date')).toBe('not-a-date')
  })
})

describe('formatLocalKickoffTime', () => {
  it('extrait HH:mm directement de la chaîne, sans jamais passer par Date (évite une réinterprétation comme heure locale du navigateur)', () => {
    expect(formatLocalKickoffTime('2026-10-09T20:45:00')).toBe('20:45')
    expect(formatLocalKickoffTime('2026-12-05T09:05:00')).toBe('09:05')
  })

  it('retourne la chaîne telle quelle si le format ne correspond pas', () => {
    expect(formatLocalKickoffTime('not-a-datetime')).toBe('not-a-datetime')
  })
})

describe('fixtureTimingState', () => {
  it('"utc_confirmed" dès que kickoff_utc est connu, quelle que soit kickoff_local_naive', () => {
    expect(fixtureTimingState(match({ kickoff_utc: '2026-08-21T18:45:00Z', is_played: true }))).toBe('utc_confirmed')
  })

  it('"local_only" quand seule l’heure locale est connue (état B)', () => {
    expect(fixtureTimingState(match({ kickoff_local_naive: '2026-10-09T20:45:00', kickoff_utc: null }))).toBe('local_only')
  })

  it('"unpublished" quand aucune heure n’est connue (état C)', () => {
    expect(fixtureTimingState(match({ kickoff_local_naive: null, kickoff_utc: null }))).toBe('unpublished')
  })
})

describe('analysisAvailability', () => {
  it('disponible, heure CONFIRMÉE, quand kickoff_utc est connu (match D/A)', () => {
    const result = analysisAvailability(match({ kickoff_utc: '2026-08-21T18:45:00Z', is_played: true }))
    expect(result.available).toBe(true)
    expect(result.available && result.estimated).toBe(false)
  })

  // Demande produit explicite (LOT retravail UI) : une fixture Ligue 1 à
  // heure locale connue n'est plus bloquée - l'API estime l'UTC par
  // conversion CET/CEST (routes_prediction.py, INCHANGÉ ici) - signalé par
  // `estimated: true`, jamais masqué.
  it('disponible, heure ESTIMÉE, pour un match Ligue 1 B (heure locale connue, kickoff_utc absent)', () => {
    const result = analysisAvailability(match({ competition: 'ligue1', kickoff_local_naive: '2026-10-09T20:45:00', kickoff_utc: null }))
    expect(result.available).toBe(true)
    expect(result.available && result.estimated).toBe(true)
  })

  it('indisponible pour un match B hors Ligue 1 (heure locale connue mais estimation UTC non prise en charge pour cette compétition)', () => {
    const result = analysisAvailability(match({ competition: 'liga', kickoff_local_naive: '2026-10-09T20:45:00', kickoff_utc: null }))
    expect(result.available).toBe(false)
    expect(!result.available && result.reason).toBe(
      'Analyse indisponible : heure connue localement, mais estimation UTC non prise en charge pour cette compétition.',
    )
  })

  it('indisponible pour un match C (aucune heure publiée), quelle que soit la compétition', () => {
    const result = analysisAvailability(match({ kickoff_local_naive: null, kickoff_utc: null }))
    expect(result.available).toBe(false)
    expect(!result.available && result.reason).toBe('Analyse indisponible : heure de coup d’envoi non publiée.')
  })

  it('ne fabrique jamais de promesse sur une heure future précise dans le message d’indisponibilité (B hors Ligue 1, ou C)', () => {
    const bHorsLigue1 = analysisAvailability(match({ competition: 'liga', kickoff_local_naive: '2026-10-09T20:45:00', kickoff_utc: null }))
    const c = analysisAvailability(match({ kickoff_local_naive: null, kickoff_utc: null }))
    for (const result of [bHorsLigue1, c]) {
      expect(!result.available && result.reason).not.toMatch(/bientôt|prochainement|sera analysable|à \d{1,2}:\d{2}/i)
    }
  })
})
