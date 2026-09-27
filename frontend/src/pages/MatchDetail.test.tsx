import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import type { MatchResponse } from '../api/types'
import { MatchDetail } from './MatchDetail'

const { getMatchMock } = vi.hoisted(() => ({ getMatchMock: vi.fn() }))

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client')
  return { ...actual, getMatch: getMatchMock }
})

// Fixture de test explicitement identifiée comme telle.
const FIXTURE_MATCH: MatchResponse = {
  match_id: '31975',
  competition: 'ligue1',
  season: '2026_27',
  kickoff_utc: '2026-09-13T18:45:00Z',
  home_team: 'Brest',
  away_team: 'Paris Saint Germain',
  is_played: true,
}

function renderDetail(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/matches/:competition/:season/:matchId" element={<MatchDetail />} />
      </Routes>
    </MemoryRouter>,
  )
}

afterEach(() => {
  getMatchMock.mockReset()
})

describe('MatchDetail', () => {
  it("affiche un état de chargement puis le match réel via le client API mocké", async () => {
    getMatchMock.mockResolvedValue(FIXTURE_MATCH)
    renderDetail('/matches/ligue1/2026_27/31975')

    expect(screen.getByText(/Chargement du match/)).toBeInTheDocument()

    await waitFor(() => expect(screen.getByText('Brest – Paris Saint Germain')).toBeInTheDocument())
    expect(screen.getByText('Compétition : ligue1')).toBeInTheDocument()
    expect(screen.getByText('Saison : 2026_27')).toBeInTheDocument()
    expect(screen.getByText('Identifiant : 31975')).toBeInTheDocument()
    expect(getMatchMock).toHaveBeenCalledWith('31975', 'ligue1', '2026_27')
  })

  it('affiche explicitement l’absence de prédiction, sans aucune valeur fabriquée', async () => {
    getMatchMock.mockResolvedValue(FIXTURE_MATCH)
    renderDetail('/matches/ligue1/2026_27/31975')

    await waitFor(() => expect(screen.getByText('Brest – Paris Saint Germain')).toBeInTheDocument())
    // Le texte explicatif mentionne en toutes lettres les concepts absents
    // (probabilités, cote, edge, décision) - c'est attendu et honnête. Le
    // garde-fou reel porte sur l'absence de toute VALEUR fabriquee : aucun
    // badge de décision (BET/NO_BET) ni aucune valeur numérique de cote/
    // probabilité ne doit être rendu à l'écran.
    expect(screen.getByText(/ne sont pas disponibles dans cette version/)).toBeInTheDocument()
    expect(screen.queryByText('BET')).not.toBeInTheDocument()
    expect(screen.queryByText('NO_BET')).not.toBeInTheDocument()
    expect(screen.queryByRole('img', { name: /graphique/i })).not.toBeInTheDocument()
  })

  it('affiche un message explicite quand le match est introuvable (404)', async () => {
    getMatchMock.mockRejectedValue(new ApiError(404, "Match '999999' introuvable pour competition='ligue1', season='2026_27'."))
    renderDetail('/matches/ligue1/2026_27/999999')

    await waitFor(() => expect(screen.getByText(/introuvable/)).toBeInTheDocument())
  })

  it('affiche un message d’erreur explicite sur une erreur API générique', async () => {
    getMatchMock.mockRejectedValue(new ApiError(400, "Saison inconnue : '2099_00'."))
    renderDetail('/matches/ligue1/2099_00/31975')

    await waitFor(() => expect(screen.getByText(/Saison inconnue/)).toBeInTheDocument())
  })

  it('propose un lien de retour vers l’explorateur préservant compétition/saison', async () => {
    getMatchMock.mockResolvedValue(FIXTURE_MATCH)
    renderDetail('/matches/ligue1/2026_27/31975')

    await waitFor(() => expect(screen.getByText('Brest – Paris Saint Germain')).toBeInTheDocument())
    const back = screen.getByRole('link', { name: /Retour à l'explorateur/ })
    expect(back).toHaveAttribute('href', '/matches?competition=ligue1&season=2026_27')
  })
})
