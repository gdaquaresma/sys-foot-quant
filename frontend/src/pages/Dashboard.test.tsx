import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import type { PerformanceResponse, ShadowObservation } from '../api/types'
import { Dashboard } from './Dashboard'

const { getPerformanceMock, getShadowJournalMock } = vi.hoisted(() => ({
  getPerformanceMock: vi.fn(),
  getShadowJournalMock: vi.fn(),
}))

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client')
  return { ...actual, getPerformance: getPerformanceMock, getShadowJournal: getShadowJournalMock }
})

// Fixtures de test explicitement identifiées comme telles - jamais
// présentées comme des données réelles dans l'application elle-même.
const EMPTY_PERFORMANCE: PerformanceResponse = {
  n_total: 0,
  n_pending: 0,
  n_settled: 0,
  decision_distribution: {},
  models: {
    poisson_simple: { n: 0, brier: null, log_loss: null, calibration_bins: null },
    dixon_coles: { n: 0, brier: null, log_loss: null, calibration_bins: null },
    xg_model: { n: 0, brier: null, log_loss: null, calibration_bins: null },
  },
  betting: { n_bet: 0, message: '0 BET — echantillon insuffisant pour evaluer une strategie de mise.' },
  calibration_min_observations: 20,
}

const FIXTURE_SHADOW_OBSERVATION: ShadowObservation = {
  prediction_id: 'abc123',
  recorded_at: '2026-09-26T14:21:17.550135',
  decision_time: '2024-10-26T13:00:00',
  competition: 'liga',
  season: '2024_25',
  home_team: 'Real Madrid',
  away_team: 'Barcelona',
  kickoff_utc: '2024-10-26T15:00:00',
  decision_offset_hours: 2.0,
  market_odds_over_2_5: 1.9,
  market_odds_under_2_5: 1.9,
  odds_bookmaker: null,
  odds_market: null,
  odds_line: null,
  primary_model: 'poisson_simple',
  models: {},
  market_comparison: null,
  calibration_status_over_2_5: 'ZONE_BIAISEE_NON_CORRIGEE',
  discrimination_status: 'DEMONTREE',
  data_quality: ['OK'],
  triggered_gates: [],
  decision: 'NO_BET',
  decision_reason: ['EDGE_BELOW_THRESHOLD'],
  engine_version: 'final-engine-mvp-0.1.0',
  status: 'SETTLED',
  settlement: {
    settled_at: '2026-09-26T14:21:17.551858',
    home_goals_actual: 2,
    away_goals_actual: 1,
    total_goals_actual: 3,
    market_result_over_2_5: 'Over',
    pnl_theoretical: null,
  },
}

function renderDashboard() {
  return render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>,
  )
}

afterEach(() => {
  getPerformanceMock.mockReset()
  getShadowJournalMock.mockReset()
})

describe('Dashboard', () => {
  it('affiche un état de chargement initial', () => {
    getPerformanceMock.mockReturnValue(new Promise(() => {}))
    getShadowJournalMock.mockReturnValue(new Promise(() => {}))
    renderDashboard()
    expect(screen.getByText(/Chargement du tableau de bord/)).toBeInTheDocument()
  })

  it('affiche des comptages à zéro quand le journal Shadow et la performance sont vides', async () => {
    getPerformanceMock.mockResolvedValue(EMPTY_PERFORMANCE)
    getShadowJournalMock.mockResolvedValue([])
    renderDashboard()

    await waitFor(() => expect(screen.getByText('Aucune donnée Shadow Mode enregistrée')).toBeInTheDocument())
    expect(screen.getByText('Aucune observation de performance disponible')).toBeInTheDocument()
    // 4 stat-cards, toutes à 0.
    const zeros = screen.getAllByText('0')
    expect(zeros.length).toBe(4)
  })

  it('dérive correctement les comptages PENDING/SETTLED à partir du journal réel', async () => {
    const pendingObservation: ShadowObservation = { ...FIXTURE_SHADOW_OBSERVATION, prediction_id: 'pending-1', status: 'PENDING', settlement: null }
    getPerformanceMock.mockResolvedValue({ ...EMPTY_PERFORMANCE, n_total: 2, n_pending: 1, n_settled: 1 })
    getShadowJournalMock.mockResolvedValue([FIXTURE_SHADOW_OBSERVATION, pendingObservation])
    renderDashboard()

    await waitFor(() => expect(screen.getByText('2 observation(s) Shadow Mode disponible(s)')).toBeInTheDocument())
    // 1 en attente, 1 reglee - verifie les valeurs des stat-cards correspondantes.
    expect(screen.getByText('En attente').previousSibling).toHaveTextContent('1')
    expect(screen.getByText('Réglées').previousSibling).toHaveTextContent('1')
  })

  it('affiche des liens réels vers les pages principales dans le bloc accès rapide', async () => {
    getPerformanceMock.mockResolvedValue(EMPTY_PERFORMANCE)
    getShadowJournalMock.mockResolvedValue([])
    const { container } = renderDashboard()

    await waitFor(() => expect(container.querySelector('.quick-links')).toBeInTheDocument())
    const quickLinks = container.querySelector('.quick-links')!
    const links = Array.from(quickLinks.querySelectorAll('a')).map((a) => a.getAttribute('href'))
    expect(links).toEqual(['/', '/matches', '/shadow', '/performance'])
  })

  it('documente la limitation sur les matchs sans fabriquer de données', async () => {
    getPerformanceMock.mockResolvedValue(EMPTY_PERFORMANCE)
    getShadowJournalMock.mockResolvedValue([])
    renderDashboard()

    await waitFor(() => expect(screen.getByText(/ne fournit pas de moyen de lister les matchs/)).toBeInTheDocument())
  })

  it('affiche un message d’erreur explicite si l’API échoue', async () => {
    getPerformanceMock.mockRejectedValue(new ApiError(500, 'Erreur serveur inattendue.'))
    getShadowJournalMock.mockResolvedValue([])
    renderDashboard()

    await waitFor(() => expect(screen.getByText(/Erreur serveur inattendue/)).toBeInTheDocument())
  })
})
