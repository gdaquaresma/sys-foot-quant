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
    fixture_date: '2026-09-13',
    kickoff_local_naive: null,
    kickoff_utc: '2026-09-13T18:45:00Z',
    home_team: 'Brest',
    away_team: 'Paris Saint Germain',
    is_played: true,
  },
  {
    match_id: '31940',
    competition: 'ligue1',
    season: '2026_27',
    fixture_date: '2026-08-21',
    kickoff_local_naive: null,
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
    expect(screen.getByText(/Choisissez une compétition et une saison/)).toBeInTheDocument()
    expect(getMatchesMock).not.toHaveBeenCalled()
  })

  it('propose des menus déroulants à libellés humains (cohérence avec Analyser un match), jamais un identifiant technique à taper', () => {
    // Revue de cohérence produit : cette page utilisait auparavant deux
    // champs texte libres avec le placeholder "identifiant technique" -
    // incohérent avec AnalyzeMatch.tsx, qui n'expose jamais d'identifiant
    // brut. Les deux pages partagent désormais la même source
    // (`../api/catalog`).
    renderExplorer()
    const competitionSelect = screen.getByLabelText('Compétition') as HTMLSelectElement
    const seasonSelect = screen.getByLabelText('Saison') as HTMLSelectElement
    expect(competitionSelect.tagName).toBe('SELECT')
    expect(seasonSelect.tagName).toBe('SELECT')
    expect(screen.getByRole('option', { name: 'Ligue 1' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'La Liga' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Premier League' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: '2026/27' })).toBeInTheDocument()
    expect(screen.queryByPlaceholderText('identifiant technique')).not.toBeInTheDocument()
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
    getMatchesMock.mockRejectedValue(new ApiError(400, "Aucune donnee pour la saison '2024_25' de 'ligue1'."))
    renderExplorer()

    fireEvent.change(screen.getByLabelText('Compétition'), { target: { value: 'ligue1' } })
    fireEvent.change(screen.getByLabelText('Saison'), { target: { value: '2024_25' } })
    fireEvent.click(screen.getByRole('button', { name: 'Rechercher' }))

    await waitFor(() => expect(screen.getByText(/Aucune donnee pour la saison/)).toBeInTheDocument())
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

  // --- EXTENSION fixtures futures 2026/27 ---------------------------------

  describe('fixtures futures (B/C)', () => {
    const FIXTURE_MATCH_STATE_B: MatchResponse = {
      match_id: 'ligue1:2026_27:Lens_vs_Lyon:2026-10-09T20:45:00',
      competition: 'ligue1',
      season: '2026_27',
      fixture_date: '2026-10-09',
      kickoff_local_naive: '2026-10-09T20:45:00',
      kickoff_utc: null,
      home_team: 'Lens',
      away_team: 'Lyon',
      is_played: false,
    }

    const FIXTURE_MATCH_STATE_C: MatchResponse = {
      match_id: 'ligue1:2026_27:Lens_vs_Le Havre:2026-12-05',
      competition: 'ligue1',
      season: '2026_27',
      fixture_date: '2026-12-05',
      kickoff_local_naive: null,
      kickoff_utc: null,
      home_team: 'Lens',
      away_team: 'Le Havre',
      is_played: false,
    }

    async function searchLigue1_2026_27() {
      fireEvent.change(screen.getByLabelText('Compétition'), { target: { value: 'ligue1' } })
      fireEvent.change(screen.getByLabelText('Saison'), { target: { value: '2026_27' } })
      fireEvent.click(screen.getByRole('button', { name: 'Rechercher' }))
    }

    it('affiche les matchs joués ET les fixtures futures ensemble, jamais confondus (statut distinct)', async () => {
      getMatchesMock.mockResolvedValue([...FIXTURE_MATCHES, FIXTURE_MATCH_STATE_B])
      renderExplorer()
      await searchLigue1_2026_27()

      await waitFor(() => expect(screen.getByText('Brest')).toBeInTheDocument())
      expect(screen.getByText('Lens')).toBeInTheDocument()
      const playedRow = screen.getByText('Brest').closest('tr')!
      const futureRow = screen.getByText('Lens').closest('tr')!
      expect(playedRow.textContent).toContain('Joué — voir détail')
      expect(futureRow.textContent).toContain('À venir — voir détail')
      expect(playedRow.textContent).not.toContain('À venir')
      expect(futureRow.textContent).not.toContain('Joué')
    })

    it('affiche l’heure locale d’une fixture B explicitement comme telle (jamais comme une heure UTC confirmée)', async () => {
      getMatchesMock.mockResolvedValue([FIXTURE_MATCH_STATE_B])
      renderExplorer()
      await searchLigue1_2026_27()

      await waitFor(() => expect(screen.getByText('Lens')).toBeInTheDocument())
      expect(screen.getByText(/9 octobre 2026 · 20:45 \(heure locale\)/)).toBeInTheDocument()
      expect(screen.getByText(/analyse indisponible/)).toBeInTheDocument()
    })

    it('affiche "heure non publiée" pour une fixture C, sans heure fabriquée', async () => {
      getMatchesMock.mockResolvedValue([FIXTURE_MATCH_STATE_C])
      renderExplorer()
      await searchLigue1_2026_27()

      await waitFor(() => expect(screen.getByText('Le Havre')).toBeInTheDocument())
      expect(screen.getByText(/5 décembre 2026 \(heure non publiée\)/)).toBeInTheDocument()
      expect(screen.getByText(/analyse indisponible/)).toBeInTheDocument()
    })

    it('affiche les fixtures dans l’ordre renvoyé par l’API, sans re-trier localement (déterminisme garanti côté backend)', async () => {
      getMatchesMock.mockResolvedValue([FIXTURE_MATCH_STATE_C, FIXTURE_MATCH_STATE_B, FIXTURE_MATCHES[0]])
      renderExplorer()
      await searchLigue1_2026_27()

      await waitFor(() => expect(screen.getByText('Brest')).toBeInTheDocument())
      const rows = screen.getAllByRole('row').slice(1) // écarte l'en-tête
      expect(rows.map((r) => r.textContent?.includes('Le Havre') ? 'C' : r.textContent?.includes('Lyon') ? 'B' : 'D')).toEqual([
        'C',
        'B',
        'D',
      ])
    })
  })
})
