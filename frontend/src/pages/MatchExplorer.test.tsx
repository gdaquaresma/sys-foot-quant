import { render, screen, waitFor } from '@testing-library/react'
import { fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import type { MatchResponse } from '../api/types'
import { MatchExplorer } from './MatchExplorer'

const { getMatchesMock } = vi.hoisted(() => ({ getMatchesMock: vi.fn() }))

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client')
  return { ...actual, getMatches: getMatchesMock }
})

// Fixture de test - donnée explicitement identifiée comme fixture, jamais
// une donnée présentée comme réelle dans l'application elle-même.
const FIXTURE_MATCHES: MatchResponse[] = [
  {
    match_id: '31975',
    competition: 'ligue1',
    season: '2026_27',
    kickoff_utc: '2026-09-13T18:45:00Z',
    home_team: 'Brest',
    away_team: 'Paris Saint Germain',
    is_played: true,
  },
  {
    match_id: '31940',
    competition: 'ligue1',
    season: '2026_27',
    kickoff_utc: '2026-08-21T18:45:00Z',
    home_team: 'Marseille',
    away_team: 'Strasbourg',
    is_played: true,
  },
]

function renderExplorer(initialEntries = ['/matches']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <MatchExplorer />
    </MemoryRouter>,
  )
}

afterEach(() => {
  getMatchesMock.mockReset()
})

describe('MatchExplorer', () => {
  it('affiche un état initial sans appeler l’API', () => {
    renderExplorer()
    expect(screen.getByText(/Renseignez une compétition et une saison/)).toBeInTheDocument()
    expect(getMatchesMock).not.toHaveBeenCalled()
  })

  it('affiche un état de chargement puis les matchs après sélection et soumission', async () => {
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    renderExplorer()

    fireEvent.change(screen.getByLabelText('Compétition'), { target: { value: 'ligue1' } })
    fireEvent.change(screen.getByLabelText('Saison'), { target: { value: '2026_27' } })
    fireEvent.click(screen.getByRole('button', { name: 'Rechercher' }))

    expect(screen.getByText(/Chargement des matchs/)).toBeInTheDocument()

    await waitFor(() => expect(screen.getByText('Brest')).toBeInTheDocument())
    expect(screen.getByText('Paris Saint Germain')).toBeInTheDocument()
    expect(screen.getByText('Marseille')).toBeInTheDocument()
    expect(getMatchesMock).toHaveBeenCalledWith('ligue1', '2026_27')
  })

  it('affiche un état vide quand l’API retourne une liste vide', async () => {
    getMatchesMock.mockResolvedValue([])
    renderExplorer()

    fireEvent.change(screen.getByLabelText('Compétition'), { target: { value: 'ligue1' } })
    fireEvent.change(screen.getByLabelText('Saison'), { target: { value: '2026_27' } })
    fireEvent.click(screen.getByRole('button', { name: 'Rechercher' }))

    await waitFor(() => expect(screen.getByText(/Aucun match ne correspond/)).toBeInTheDocument())
  })

  it('affiche le message d’erreur réel renvoyé par l’API', async () => {
    getMatchesMock.mockRejectedValue(new ApiError(400, "Competition inconnue pour la saison '2024_25' : 'bundesliga'."))
    renderExplorer()

    fireEvent.change(screen.getByLabelText('Compétition'), { target: { value: 'bundesliga' } })
    fireEvent.change(screen.getByLabelText('Saison'), { target: { value: '2024_25' } })
    fireEvent.click(screen.getByRole('button', { name: 'Rechercher' }))

    await waitFor(() => expect(screen.getByText(/Competition inconnue pour la saison/)).toBeInTheDocument())
  })

  it('génère un lien de navigation vers le détail avec les identifiants réels du match', async () => {
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    renderExplorer()

    fireEvent.change(screen.getByLabelText('Compétition'), { target: { value: 'ligue1' } })
    fireEvent.change(screen.getByLabelText('Saison'), { target: { value: '2026_27' } })
    fireEvent.click(screen.getByRole('button', { name: 'Rechercher' }))

    await waitFor(() => expect(screen.getByText('Brest')).toBeInTheDocument())
    const brestRow = screen.getByText('Brest').closest('tr')
    expect(brestRow).not.toBeNull()
    const link = brestRow!.querySelector('a')
    expect(link).toHaveAttribute('href', '/matches/ligue1/2026_27/31975')
  })

  it('pré-remplit et relance la recherche à partir des paramètres d’URL (retour depuis le détail)', async () => {
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    renderExplorer(['/matches?competition=ligue1&season=2026_27'])

    await waitFor(() => expect(getMatchesMock).toHaveBeenCalledWith('ligue1', '2026_27'))
    await waitFor(() => expect(screen.getByText('Brest')).toBeInTheDocument())
  })

  it('filtre les résultats par équipe côté client sans nouvel appel API', async () => {
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    renderExplorer()

    fireEvent.change(screen.getByLabelText('Compétition'), { target: { value: 'ligue1' } })
    fireEvent.change(screen.getByLabelText('Saison'), { target: { value: '2026_27' } })
    fireEvent.click(screen.getByRole('button', { name: 'Rechercher' }))
    await waitFor(() => expect(screen.getByText('Brest')).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('Filtrer par équipe'), { target: { value: 'Marseille' } })

    expect(screen.queryByText('Brest')).not.toBeInTheDocument()
    expect(screen.getByText('Marseille')).toBeInTheDocument()
    expect(getMatchesMock).toHaveBeenCalledTimes(1)
  })
})
