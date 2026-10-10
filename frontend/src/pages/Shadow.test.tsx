/** Tests ciblés pour `Shadow.tsx` - couvre uniquement le NOUVEAU
 * comportement : filtrage par onglet de compétition (présentation pure,
 * aucune nouvelle requête réseau) et affichage du résultat réel d'une
 * observation RÉGLÉE (lecture directe de `settlement`, jamais recalculé). */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ShadowObservation } from '../api/types'
import { Shadow } from './Shadow'

const { getShadowJournalMock } = vi.hoisted(() => ({ getShadowJournalMock: vi.fn() }))

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client')
  return { ...actual, getShadowJournal: getShadowJournalMock }
})

function observation(overrides: Partial<ShadowObservation>): ShadowObservation {
  return {
    prediction_id: 'id-' + Math.random(),
    recorded_at: '2026-09-26T14:21:17.550135',
    decision_time: '2026-10-09T16:45:00',
    competition: 'ligue1',
    season: '2026_27',
    home_team: 'Lens',
    away_team: 'Lyon',
    kickoff_utc: '2026-10-09T18:45:00',
    decision_offset_hours: 2.0,
    market_odds_over_2_5: null,
    market_odds_under_2_5: null,
    odds_bookmaker: null,
    odds_market: null,
    odds_line: null,
    primary_model: 'poisson_simple',
    models: {},
    market_comparison: null,
    calibration_status_over_2_5: 'OK',
    discrimination_status: 'DEMONTREE',
    data_quality: [],
    triggered_gates: [],
    decision: 'NO_BET',
    decision_reason: ['EDGE_BELOW_THRESHOLD'],
    engine_version: 'final-engine-mvp-0.1.0',
    status: 'PENDING',
    settlement: null,
    ...overrides,
  }
}

function renderShadow() {
  return render(
    <MemoryRouter>
      <Shadow />
    </MemoryRouter>,
  )
}

afterEach(() => {
  getShadowJournalMock.mockReset()
})

describe('Shadow', () => {
  it('affiche le score réel et le résultat de marché pour une observation RÉGLÉE, jamais pour une PENDING', async () => {
    const settled = observation({
      prediction_id: 'settled-1',
      status: 'SETTLED',
      settlement: {
        settled_at: '2026-10-09T21:00:00',
        home_goals_actual: 2,
        away_goals_actual: 1,
        total_goals_actual: 3,
        market_result_over_2_5: 'Over',
        pnl_theoretical: null,
      },
    })
    const pending = observation({ prediction_id: 'pending-1', home_team: 'Monaco', away_team: 'Toulouse' })
    getShadowJournalMock.mockResolvedValue([settled, pending])
    renderShadow()

    await waitFor(() => expect(screen.getByText('Lens – Lyon')).toBeInTheDocument())
    expect(screen.getByText('2-1 (Over)')).toBeInTheDocument()
    // La ligne PENDING n'affiche aucun résultat fabriqué - un tiret neutre.
    const pendingRow = screen.getByText('Monaco – Toulouse').closest('tr')!
    expect(pendingRow.textContent).toContain('—')
  })

  it('filtre les observations par onglet de compétition, sans nouvelle requête réseau', async () => {
    const ligue1Obs = observation({ prediction_id: 'l1', competition: 'ligue1', home_team: 'Lens', away_team: 'Lyon' })
    const ligaObs = observation({ prediction_id: 'liga1', competition: 'liga', home_team: 'Real Madrid', away_team: 'Barcelona' })
    getShadowJournalMock.mockResolvedValue([ligue1Obs, ligaObs])
    renderShadow()

    await waitFor(() => expect(screen.getByText('Lens – Lyon')).toBeInTheDocument())
    expect(screen.getByText('Real Madrid – Barcelona')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: 'Ligue 1' }))
    expect(screen.getByText('Lens – Lyon')).toBeInTheDocument()
    expect(screen.queryByText('Real Madrid – Barcelona')).not.toBeInTheDocument()
    // Un seul appel réseau au total - le filtrage est une pure dérivation
    // du journal déjà chargé, jamais une nouvelle requête par onglet.
    expect(getShadowJournalMock).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByRole('tab', { name: 'Tous' }))
    expect(screen.getByText('Real Madrid – Barcelona')).toBeInTheDocument()
  })

  it('rappelle explicitement qu’aucun pari réel n’a jamais été engagé', async () => {
    getShadowJournalMock.mockResolvedValue([observation({})])
    renderShadow()

    await waitFor(() => expect(screen.getByText(/SANS AUCUN PARI RÉEL ENGAGÉ/)).toBeInTheDocument())
  })
})
