import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, getMatch, getMatches } from './client'

function mockFetchOnce(status: number, body: unknown, ok = status >= 200 && status < 300) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok,
      status,
      json: () => Promise.resolve(body),
    }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('getMatches', () => {
  it('construit l’URL avec les paramètres competition/season', async () => {
    mockFetchOnce(200, [])
    await getMatches('ligue1', '2026_27')
    const calledUrl = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
    expect(calledUrl).toContain('/api/matches')
    expect(calledUrl).toContain('competition=ligue1')
    expect(calledUrl).toContain('season=2026_27')
  })

  it('retourne les données telles que fournies par la réponse (fixture de test)', async () => {
    const fixture = [
      {
        match_id: '31975',
        competition: 'ligue1',
        season: '2026_27',
        kickoff_utc: '2026-09-13T18:45:00Z',
        home_team: 'Brest',
        away_team: 'Paris Saint Germain',
        is_played: true,
      },
    ]
    mockFetchOnce(200, fixture)
    const result = await getMatches('ligue1', '2026_27')
    expect(result).toEqual(fixture)
  })

  it('lève une ApiError avec le detail exact sur une erreur 400', async () => {
    mockFetchOnce(400, { detail: "Competition inconnue pour la saison '2024_25' : 'bundesliga'." })
    await expect(getMatches('bundesliga', '2024_25')).rejects.toMatchObject({
      status: 400,
      detail: "Competition inconnue pour la saison '2024_25' : 'bundesliga'.",
    })
  })

  it('lève une ApiError pour une erreur de validation 422 (detail liste)', async () => {
    mockFetchOnce(422, { detail: [{ type: 'missing', loc: ['query', 'season'], msg: 'Field required' }] })
    const error = await getMatches('ligue1', '').catch((e) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(422)
    expect((error as ApiError).detail).toContain('Field required')
  })
})

describe('getMatch', () => {
  it('construit l’URL avec l’identifiant de match encodé et les paramètres requis', async () => {
    mockFetchOnce(200, {
      match_id: '31975',
      competition: 'ligue1',
      season: '2026_27',
      kickoff_utc: '2026-09-13T18:45:00Z',
      home_team: 'Brest',
      away_team: 'Paris Saint Germain',
      is_played: true,
    })
    await getMatch('31975', 'ligue1', '2026_27')
    const calledUrl = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
    expect(calledUrl).toContain('/api/matches/31975')
    expect(calledUrl).toContain('competition=ligue1')
    expect(calledUrl).toContain('season=2026_27')
  })

  it('lève une ApiError 404 sur un match introuvable', async () => {
    mockFetchOnce(404, { detail: "Match '999999' introuvable pour competition='ligue1', season='2026_27'." })
    const error = await getMatch('999999', 'ligue1', '2026_27').catch((e) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(404)
  })
})
