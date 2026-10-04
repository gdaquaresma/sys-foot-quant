import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import type { MatchDecisionOutput, MatchResponse } from '../api/types'
import { AnalyzeMatch } from './AnalyzeMatch'

const { getMatchesMock, getPredictionMock } = vi.hoisted(() => ({
  getMatchesMock: vi.fn(),
  getPredictionMock: vi.fn(),
}))

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client')
  return { ...actual, getMatches: getMatchesMock, getPrediction: getPredictionMock }
})

// Fixtures de test explicitement identifiées comme telles - même forme que
// les fixtures déjà validées dans MatchDetail.test.tsx/MatchExplorer.test.tsx,
// jamais une forme inventée. probabilities['2.5'] = 0.438 reprend
// volontairement l'exemple chiffré fourni dans la demande (Over 2.5 : 43,8 %
// -> cote juste 2,28 ; Under 2.5 complémentaire : 56,2 % -> cote juste 1,78).
const FIXTURE_MATCHES: MatchResponse[] = [
  {
    match_id: '31940',
    competition: 'ligue1',
    season: '2026_27',
    kickoff_utc: '2026-08-21T18:45:00Z',
    home_team: 'Marseille',
    away_team: 'Strasbourg',
    is_played: true,
  },
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

const FIXTURE_PREDICTION_NO_MARKET: MatchDecisionOutput = {
  match_id: 'ligue1:2026_27:Marseille_vs_Strasbourg:2026-08-21T18:45:00',
  timestamp_decision: '2026-08-21T16:45:00',
  competition: 'ligue1',
  season: '2026_27',
  primary_model: 'poisson_simple',
  models: {
    poisson_simple: { model: 'poisson_simple', lam: 1.3, mu: 1.1, rho: null, n_train_matches: 200 },
    dixon_coles: { model: 'dixon_coles', lam: 1.3, mu: 1.1, rho: -0.04, n_train_matches: 200 },
    xg_model: { model: 'xg_model', lam: 1.25, mu: 1.05, rho: null, n_train_matches: 190 },
  },
  calibration: {
    poisson_simple: {
      model: 'poisson_simple',
      scale_c: 0.9,
      n_calibration_used: 180,
      goal_distribution: [0.1, 0.1, 0.2, 0.2, 0.2, 0.1, 0.1],
      probabilities: { '0.5': 0.8, '1.5': 0.6, '2.5': 0.438, '3.5': 0.2, '4.5': 0.1 },
    },
    dixon_coles: {
      model: 'dixon_coles',
      scale_c: 0.9,
      n_calibration_used: 180,
      goal_distribution: [0.1, 0.1, 0.2, 0.2, 0.2, 0.1, 0.1],
      probabilities: { '0.5': 0.8, '1.5': 0.6, '2.5': 0.44, '3.5': 0.2, '4.5': 0.1 },
    },
    xg_model: {
      model: 'xg_model',
      scale_c: 0.85,
      n_calibration_used: 175,
      goal_distribution: [0.1, 0.11, 0.19, 0.2, 0.19, 0.11, 0.1],
      probabilities: { '0.5': 0.79, '1.5': 0.58, '2.5': 0.42, '3.5': 0.19, '4.5': 0.09 },
    },
  },
  pricing: {
    poisson_simple: { fair_price: { '0.5': 1.25, '1.5': 1.67, '2.5': 2.28, '3.5': 5.0, '4.5': 10.0 } },
    dixon_coles: { fair_price: { '0.5': 1.25, '1.5': 1.67, '2.5': 2.27, '3.5': 5.0, '4.5': 10.0 } },
    xg_model: { fair_price: { '0.5': 1.27, '1.5': 1.72, '2.5': 2.38, '3.5': 5.26, '4.5': 11.11 } },
  },
  market: null,
  qualification: {
    calibration_status: { '0.5': 'OK', '1.5': 'OK', '2.5': 'OK', '3.5': 'OK', '4.5': 'OK' },
    discrimination_status: 'DEMONTREE',
    data_quality: ['MARKET_DATA_UNAVAILABLE'],
    scientific_gates: [],
    operational_gates: [
      {
        name: 'incomplete_market_odds_gate',
        triggered: true,
        reason: 'Aucune cote de marche disponible a decision_time.',
        metric: 'market_odds',
        observed_value: null,
        threshold: 'cote complete requise',
        failure_code: 'MARKET_DATA_UNAVAILABLE',
      },
    ],
  },
  decision: { decision: 'NO_BET', decision_reason: ['MARKET_DATA_UNAVAILABLE'] },
  engine_version: 'final-engine-mvp-0.1.0',
  parameters_snapshot: { require_calibration_ok: true, min_edge_threshold: null, decision_offset_hours: 2.0 },
}

const FIXTURE_PREDICTION_WITH_MARKET: MatchDecisionOutput = {
  ...FIXTURE_PREDICTION_NO_MARKET,
  market: {
    market_odds: { Over: 2.2, Under: 1.67 },
    market_implied_probability_raw: { Over: 0.4545, Under: 0.5988 },
    market_implied_probability_normalized: { Over: 0.432, Under: 0.568 },
    market_overround: 0.0533,
    raw_edge: { Over: 0.006, Under: -0.006 },
    price_edge: { Over: -0.037, Under: 0.047 },
  },
  decision: { decision: 'NO_BET', decision_reason: ['EDGE_BELOW_THRESHOLD'] },
}

const FIXTURE_PREDICTION_BET: MatchDecisionOutput = {
  ...FIXTURE_PREDICTION_WITH_MARKET,
  decision: { decision: 'BET', decision_reason: [] },
}

const FIXTURE_PREDICTION_INSUFFICIENT_DATA: MatchDecisionOutput = {
  ...FIXTURE_PREDICTION_NO_MARKET,
  pricing: { poisson_simple: null, dixon_coles: null, xg_model: null },
  calibration: {
    poisson_simple: { model: 'poisson_simple', scale_c: null, n_calibration_used: 0, goal_distribution: null, probabilities: null },
    dixon_coles: { model: 'dixon_coles', scale_c: null, n_calibration_used: 0, goal_distribution: null, probabilities: null },
    xg_model: { model: 'xg_model', scale_c: null, n_calibration_used: 0, goal_distribution: null, probabilities: null },
  },
  decision: { decision: 'NO_BET', decision_reason: ['INSUFFICIENT_HISTORY'] },
}

function renderPage() {
  return render(
    <MemoryRouter>
      <AnalyzeMatch />
    </MemoryRouter>,
  )
}

async function searchAndSelectMatch() {
  fireEvent.change(screen.getByLabelText('Compétition'), { target: { value: 'ligue1' } })
  fireEvent.change(screen.getByLabelText('Saison'), { target: { value: '2026_27' } })
  fireEvent.click(screen.getByRole('button', { name: 'Rechercher les matchs' }))
  await waitFor(() => expect(screen.getByLabelText('Équipe à domicile')).toBeInTheDocument())
  fireEvent.change(screen.getByLabelText('Équipe à domicile'), { target: { value: 'Marseille' } })
  fireEvent.change(screen.getByLabelText("Équipe à l'extérieur"), { target: { value: 'Strasbourg' } })
}

afterEach(() => {
  getMatchesMock.mockReset()
  getPredictionMock.mockReset()
})

describe('AnalyzeMatch', () => {
  it('ne résout aucun match et désactive "Analyser le match" avant sélection', async () => {
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    renderPage()

    fireEvent.change(screen.getByLabelText('Compétition'), { target: { value: 'ligue1' } })
    fireEvent.change(screen.getByLabelText('Saison'), { target: { value: '2026_27' } })
    fireEvent.click(screen.getByRole('button', { name: 'Rechercher les matchs' }))

    await waitFor(() => expect(screen.getByLabelText('Équipe à domicile')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'Analyser le match' })).toBeDisabled()
    expect(getPredictionMock).not.toHaveBeenCalled()
  })

  it('résout un match réel du catalogue via la sélection domicile/extérieur puis lance l’analyse', async () => {
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_NO_MARKET)
    renderPage()
    await searchAndSelectMatch()

    const analyzeButton = screen.getByRole('button', { name: 'Analyser le match' })
    expect(analyzeButton).not.toBeDisabled()
    fireEvent.click(analyzeButton)

    await waitFor(() => expect(getPredictionMock).toHaveBeenCalledWith('31940', 'ligue1', '2026_27', undefined))
    expect(screen.getByText('Marseille – Strasbourg')).toBeInTheDocument()
  })

  it('affiche un état de chargement pendant l’analyse', async () => {
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    let resolvePrediction: (value: MatchDecisionOutput) => void = () => {}
    getPredictionMock.mockReturnValue(new Promise((resolve) => (resolvePrediction = resolve)))
    renderPage()
    await searchAndSelectMatch()
    fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))

    expect(screen.getByText(/Analyse en cours/)).toBeInTheDocument()
    resolvePrediction(FIXTURE_PREDICTION_NO_MARKET)
    await waitFor(() => expect(screen.queryByText(/Analyse en cours/)).not.toBeInTheDocument())
  })

  it('affiche un message d’erreur explicite si l’analyse échoue', async () => {
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    getPredictionMock.mockRejectedValue(new ApiError(400, 'Cotes incoherentes.'))
    renderPage()
    await searchAndSelectMatch()
    fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))

    await waitFor(() => expect(screen.getByText(/Cotes incoherentes/)).toBeInTheDocument())
  })

  it('affiche NO_BET avec la phrase humaine "Pas de Value Bet actuellement."', async () => {
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_NO_MARKET)
    renderPage()
    await searchAndSelectMatch()
    fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))

    await waitFor(() => expect(screen.getByText('NO_BET')).toBeInTheDocument())
    expect(screen.getByText('Pas de Value Bet actuellement.')).toBeInTheDocument()
    expect(screen.queryByText('BET')).not.toBeInTheDocument()
  })

  it('affiche BET avec une phrase humaine citant le côté en Value', async () => {
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_BET)
    renderPage()
    await searchAndSelectMatch()
    fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))

    await waitFor(() => expect(screen.getByText('BET')).toBeInTheDocument())
    expect(screen.getByText('Value Bet détecté sur Under 2.5.')).toBeInTheDocument()
  })

  it('cas sans cote : affiche probabilité/cote juste/seuil de Value sans badge VALUE/NO VALUE', async () => {
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_NO_MARKET)
    renderPage()
    await searchAndSelectMatch()
    fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))

    await waitFor(() => expect(screen.getByText('Over 2.5')).toBeInTheDocument())
    expect(screen.getByText('Under 2.5')).toBeInTheDocument()
    // Probabilité modèle (Over 43.8 %, Under complémentaire 56.2 %). "43.8 %"
    // apparaît aussi dans le tableau technique replié (même probabilité
    // Over du modèle principal au seuil 2.5) - au moins 1 occurrence visible
    // suffit à vérifier l'affichage du bloc Value Bet.
    expect(screen.getAllByText('43.8 %').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('56.2 %')).toBeInTheDocument()
    // Cote juste (Over 2.28, Under 1.78) - au moins 1 occurrence visible par
    // côté (potentiellement une 2e fois pour Over dans le tableau technique
    // replié, qui ne couvre jamais le côté Under).
    expect(screen.getAllByText('2.28').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('1.78').length).toBeGreaterThanOrEqual(1)
    // Seuil Value (Phase UI-2) : min_edge_threshold vaut null dans la
    // fixture -> jamais de cote fabriquée, uniquement le texte honnête,
    // une fois par bloc Over/Under.
    expect(screen.getAllByText('Non défini par le moteur')).toHaveLength(2)
    expect(
      screen.getAllByText(
        "Le moteur ne dispose pas encore d'un seuil d'edge minimal validé permettant de définir une cote minimale de Value.",
      ),
    ).toHaveLength(2)
    expect(screen.queryByText('Value à partir de')).not.toBeInTheDocument()
    expect(screen.getAllByText('Entrez une cote de marché pour vérifier si une Value Bet est actuellement présente.')).toHaveLength(2)
    expect(screen.queryByText('VALUE')).not.toBeInTheDocument()
    expect(screen.queryByText('NO VALUE')).not.toBeInTheDocument()
    expect(screen.queryByText('Cote actuelle')).not.toBeInTheDocument()
  })

  it('cas avec cote : affiche la cote actuelle et un badge VALUE/NO VALUE par côté', async () => {
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_WITH_MARKET)
    renderPage()
    await searchAndSelectMatch()
    fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))

    await waitFor(() => expect(screen.getAllByText('Cote actuelle').length).toBe(2))
    expect(screen.getByText('NO VALUE')).toBeInTheDocument()
    expect(screen.getByText('VALUE')).toBeInTheDocument()
    expect(screen.getAllByText('2.20').length).toBeGreaterThan(0)
    expect(screen.getAllByText('1.67').length).toBeGreaterThan(0)
  })

  it('renseigner les deux cotes déclenche un nouvel appel getPrediction avec ces cotes', async () => {
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_NO_MARKET)
    renderPage()
    await searchAndSelectMatch()
    fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))
    await waitFor(() => expect(getPredictionMock).toHaveBeenCalledWith('31940', 'ligue1', '2026_27', undefined))

    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_WITH_MARKET)
    fireEvent.change(screen.getByLabelText('Cote Over 2.5'), { target: { value: '2.20' } })
    fireEvent.change(screen.getByLabelText('Cote Under 2.5'), { target: { value: '1.67' } })
    fireEvent.click(screen.getByRole('button', { name: 'Appliquer les cotes' }))

    await waitFor(() =>
      expect(getPredictionMock).toHaveBeenCalledWith('31940', 'ligue1', '2026_27', { over_2_5: 2.2, under_2_5: 1.67 }),
    )
  })

  it('indique explicitement l’absence de Value Bet exploitable quand l’historique est insuffisant', async () => {
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_INSUFFICIENT_DATA)
    renderPage()
    await searchAndSelectMatch()
    fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))

    await waitFor(() =>
      expect(screen.getByText(/Probabilités indisponibles pour ce match/)).toBeInTheDocument(),
    )
    expect(screen.queryByText('Over 2.5')).not.toBeInTheDocument()
  })

  it('ouvre les détails techniques repliés par défaut sans perdre d’information', async () => {
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_NO_MARKET)
    renderPage()
    await searchAndSelectMatch()
    fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))

    await waitFor(() => expect(screen.getByText('Probabilités détaillées par modèle')).toBeInTheDocument())
    const details = screen.getByText('Probabilités détaillées par modèle').closest('details')
    expect(details).not.toBeNull()
    expect(details).not.toHaveAttribute('open')

    fireEvent.click(screen.getByText('Probabilités détaillées par modèle'))
    expect(details).toHaveAttribute('open')
  })
})
