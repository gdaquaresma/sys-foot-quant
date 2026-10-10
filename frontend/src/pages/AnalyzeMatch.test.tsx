import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
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
    fixture_date: '2026-08-21',
    kickoff_local_naive: null,
    kickoff_utc: '2026-08-21T18:45:00Z',
    home_team: 'Marseille',
    away_team: 'Strasbourg',
    is_played: true,
  },
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
]

// EXTENSION fixtures futures 2026/27 - formes réelles capturées sur l'API
// (voir tests/integration/test_future_fixture_catalog_real_files.py côté
// backend) : état B (heure locale publiée, kickoff_utc absent) et état C
// (aucune heure publiée, kickoff_utc absent).
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
  kickoff_utc_estimated: false,
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

// Fixture dédiée, NUMÉRIQUEMENT COHÉRENTE (contrairement à
// FIXTURE_PREDICTION_BET ci-dessus, dont les valeurs sont arbitraires et ne
// respectent pas `price_edge = model_prob * odds - 1`,
// `value_engine.edge.expected_value`, INCHANGÉ) : ici, la cote Under
// renseignée (2.00) est réellement SUPÉRIEURE à la cote juste du modèle
// (1/(1-0.438) ≈ 1.78) - le cas réaliste où "plus généreuse" doit
// s'afficher, jamais seulement le texte de repli neutre.
const FIXTURE_PREDICTION_BET_GENEROUS_ODDS: MatchDecisionOutput = {
  ...FIXTURE_PREDICTION_NO_MARKET,
  market: {
    market_odds: { Over: 1.95, Under: 2.0 },
    market_implied_probability_raw: { Over: 0.5128, Under: 0.5 },
    market_implied_probability_normalized: { Over: 0.49, Under: 0.51 },
    market_overround: 0.025,
    raw_edge: { Over: -0.052, Under: 0.052 },
    price_edge: { Over: -0.146, Under: 0.124 }, // 0.562 * 2.00 - 1 = 0.124
  },
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

// Fixture dédiée à la hiérarchie NIVEAU 3 (explication lisible) / NIVEAU 4
// (détails techniques) : DEUX raisons de blocage, avec les gates déclenchés
// correspondants (même `failure_code` que `decision_reason`, comme produit
// réellement par le moteur - voir `final_engine/gates.py`, INCHANGÉ).
const FIXTURE_PREDICTION_NO_BET_MULTI_REASON: MatchDecisionOutput = {
  ...FIXTURE_PREDICTION_NO_MARKET,
  decision: { decision: 'NO_BET', decision_reason: ['EDGE_BELOW_THRESHOLD', 'MARKET_DATA_UNAVAILABLE'] },
  qualification: {
    ...FIXTURE_PREDICTION_NO_MARKET.qualification,
    operational_gates: [
      {
        name: 'edge_threshold_gate',
        triggered: true,
        reason: "Aucun seuil d'edge minimal validé scientifiquement (protection opérationnelle du moteur).",
        metric: 'min_edge_threshold',
        observed_value: null,
        threshold: null,
        failure_code: 'EDGE_BELOW_THRESHOLD',
      },
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
}

function renderPage() {
  return render(
    <MemoryRouter>
      <AnalyzeMatch />
    </MemoryRouter>,
  )
}

async function searchAndSelectMatch() {
  // Le chargement des matchs est désormais automatique dès que compétition
  // ET saison sont choisies - plus de bouton "Rechercher" intermédiaire à
  // cliquer (voir le `useEffect` dédié dans AnalyzeMatch.tsx).
  fireEvent.click(screen.getByRole('tab', { name: 'Ligue 1' }))
  fireEvent.change(screen.getByLabelText('Saison'), { target: { value: '2026_27' } })
  await waitFor(() => expect(screen.getByLabelText('Équipe à domicile')).toBeInTheDocument())
  fireEvent.change(screen.getByLabelText('Équipe à domicile'), { target: { value: 'Marseille' } })
  fireEvent.change(screen.getByLabelText("Équipe à l'extérieur"), { target: { value: 'Strasbourg' } })
}

afterEach(() => {
  getMatchesMock.mockReset()
  getPredictionMock.mockReset()
})

describe('AnalyzeMatch', () => {
  it('propose des libellés lisibles pour la compétition (onglets) et la saison (menu), jamais un identifiant technique à taper', async () => {
    // Audit UX : l'utilisateur ne doit pas avoir à connaître/saisir
    // "ligue1"/"2024_25" - des onglets de compétition (un par championnat
    // disponible) et un menu déroulant de saison, avec des libellés
    // humains, remplacent les anciens champs texte libres.
    renderPage()

    const seasonSelect = screen.getByLabelText('Saison') as HTMLSelectElement
    expect(seasonSelect.tagName).toBe('SELECT')
    expect(screen.getByRole('tab', { name: 'Ligue 1' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'La Liga' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Premier League' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: '2024/25' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: '2026/27' })).toBeInTheDocument()
    expect(screen.queryByPlaceholderText('identifiant technique')).not.toBeInTheDocument()
  })

  it('ne résout aucun match et désactive "Analyser le match" avant sélection', async () => {
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    renderPage()

    fireEvent.click(screen.getByRole('tab', { name: 'Ligue 1' }))
    fireEvent.change(screen.getByLabelText('Saison'), { target: { value: '2026_27' } })

    await waitFor(() => expect(screen.getByLabelText('Équipe à domicile')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'Analyser le match' })).toBeDisabled()
    expect(getPredictionMock).not.toHaveBeenCalled()
  })

  it('charge automatiquement les matchs dès que compétition ET saison sont choisies, sans bouton "Rechercher" séparé', async () => {
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    renderPage()

    expect(screen.queryByRole('button', { name: 'Rechercher les matchs' })).not.toBeInTheDocument()
    expect(getMatchesMock).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('tab', { name: 'Ligue 1' }))
    expect(getMatchesMock).not.toHaveBeenCalled() // saison manquante

    fireEvent.change(screen.getByLabelText('Saison'), { target: { value: '2026_27' } })
    await waitFor(() => expect(getMatchesMock).toHaveBeenCalledWith('ligue1', '2026_27'))
    await waitFor(() => expect(screen.getByLabelText('Équipe à domicile')).toBeInTheDocument())
  })

  it('affiche un résumé humain du match choisi AVANT de lancer l’analyse, sans identifiant technique', async () => {
    // Bullet 7 de l'audit parcours : dès que domicile+extérieur résolvent un
    // match unique, un résumé lisible apparaît - PAS besoin de cliquer
    // "Analyser" pour le voir, et jamais d'identifiant technique affiché
    // (match_id de catalogue, "ligue1", "2026_27").
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    renderPage()
    await searchAndSelectMatch()

    expect(screen.getByText('Marseille – Strasbourg')).toBeInTheDocument()
    expect(screen.getByText(/^Ligue 1 · 2026\/27 ·/)).toBeInTheDocument()
    expect(screen.queryByText('31940')).not.toBeInTheDocument()
    expect(screen.queryByText('ligue1')).not.toBeInTheDocument()
    expect(screen.queryByText('2026_27')).not.toBeInTheDocument()
    // L'analyse n'a pas encore été lancée : pas de section "2. Décision".
    expect(screen.queryByText('2. Décision')).not.toBeInTheDocument()
    expect(getPredictionMock).not.toHaveBeenCalled()
  })

  it('empêche un double lancement : un clic sur le bouton désactivé pendant le chargement ne déclenche pas de second appel', async () => {
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    let resolvePrediction: (value: MatchDecisionOutput) => void = () => {}
    getPredictionMock.mockReturnValue(new Promise((resolve) => (resolvePrediction = resolve)))
    renderPage()
    await searchAndSelectMatch()

    const analyzeButton = screen.getByRole('button', { name: 'Analyser le match' })
    fireEvent.click(analyzeButton)
    expect(getPredictionMock).toHaveBeenCalledTimes(1)

    // Pendant le chargement, le bouton est désactivé et son libellé change -
    // un second clic (double-clic accidentel) ne doit déclencher aucun
    // appel supplémentaire au moteur.
    const busyButton = screen.getByRole('button', { name: 'Analyse en cours…' })
    expect(busyButton).toBeDisabled()
    fireEvent.click(busyButton)
    expect(getPredictionMock).toHaveBeenCalledTimes(1)

    resolvePrediction(FIXTURE_PREDICTION_NO_MARKET)
    await waitFor(() => expect(screen.queryByText(/Analyse en cours/)).not.toBeInTheDocument())
  })

  it('permet de revenir au choix d’un autre match après une analyse (réinitialise la décision affichée)', async () => {
    // Bullet 5 de l'audit parcours : changer d'équipe après une analyse doit
    // faire disparaître la décision/le résultat précédents, pas les laisser
    // affichés à côté d'un match qui ne correspond plus à la sélection.
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_NO_MARKET)
    renderPage()
    await searchAndSelectMatch() // Marseille - Strasbourg
    fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))
    await waitFor(() => expect(screen.getByText('NO_BET')).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('Équipe à domicile'), { target: { value: 'Brest' } })

    expect(screen.queryByText('2. Décision')).not.toBeInTheDocument()
    expect(screen.queryByText('NO_BET')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Analyser le match' })).toBeDisabled()
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
    // Le nom du match reste visible à deux endroits une fois l'analyse
    // lancée : le résumé de l'étape 1 et le rappel compact dans la carte
    // "2. Décision" (le match reste identifiable sans remonter la page).
    expect(screen.getAllByText('Marseille – Strasbourg').length).toBe(2)
  })

  it('affiche un état de chargement pendant l’analyse', async () => {
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    let resolvePrediction: (value: MatchDecisionOutput) => void = () => {}
    getPredictionMock.mockReturnValue(new Promise((resolve) => (resolvePrediction = resolve)))
    renderPage()
    await searchAndSelectMatch()
    fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))

    // Le libellé "Analyse en cours" apparaît à deux endroits pendant le
    // chargement : le bouton principal (désactivé) et le bloc de chargement
    // de la section "2. Décision".
    expect(screen.getAllByText(/Analyse en cours/).length).toBe(2)
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

  it('affiche NO_BET avec la phrase humaine intégrant la raison principale', async () => {
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_NO_MARKET)
    renderPage()
    await searchAndSelectMatch()
    fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))

    await waitFor(() => expect(screen.getByText('NO_BET')).toBeInTheDocument())
    // La raison principale (MARKET_DATA_UNAVAILABLE dans cette fixture) est
    // désormais intégrée directement dans la phrase de tête, pas seulement
    // dans la liste de raisons en dessous - l'utilisateur comprend le "pourquoi"
    // sans avoir à lire plus loin.
    expect(screen.getByText('Pas de Value Bet actuellement. Aucune cote de marché disponible pour ce match.')).toBeInTheDocument()
    expect(screen.queryByText('BET')).not.toBeInTheDocument()
    // Raison unique : jamais de liste secondaire vide/redondante répétant la
    // même raison que la phrase de tête (NIVEAU 3 - voir DecisionBlock).
    expect(document.querySelector('.decision-reasons-secondary')).toBeNull()
  })

  it('NO_BET à raisons multiples : la liste secondaire ne répète jamais la raison principale et reste lisible sans code technique, le code brut restant accessible uniquement dans les détails techniques', async () => {
    // Hiérarchie demandée : NIVEAU 3 (explication) doit être compréhensible
    // par un utilisateur non technique - jamais de code brut type
    // "EDGE_BELOW_THRESHOLD" à ce niveau, et jamais une répétition de la
    // raison déjà intégrée dans la phrase de tête. Le code brut n'est pour
    // autant JAMAIS supprimé de l'application : il reste visible dans
    // « Contrôles / Gates » (NIVEAU 4 - détails techniques).
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_NO_BET_MULTI_REASON)
    renderPage()
    await searchAndSelectMatch()
    fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))

    await waitFor(() => expect(screen.getByText('NO_BET')).toBeInTheDocument())
    expect(
      screen.getByText(
        "Pas de Value Bet actuellement. Aucun seuil d'edge minimal validé scientifiquement (protection opérationnelle du moteur).",
      ),
    ).toBeInTheDocument()

    const secondaryList = document.querySelector('.decision-reasons-secondary')
    expect(secondaryList).not.toBeNull()
    expect(secondaryList?.textContent).toBe('Aucune cote de marché disponible pour ce match.')
    expect(secondaryList?.querySelector('code')).toBeNull()
    expect(secondaryList?.textContent).not.toContain('EDGE_BELOW_THRESHOLD')
    expect(secondaryList?.textContent).not.toContain('MARKET_DATA_UNAVAILABLE')

    // Les deux codes bruts restent accessibles - uniquement dans les
    // détails techniques repliés (NIVEAU 4).
    fireEvent.click(screen.getByText('Contrôles / Gates', { exact: false, selector: 'summary' }))
    expect(screen.getByText('EDGE_BELOW_THRESHOLD')).toBeInTheDocument()
    expect(screen.getByText('MARKET_DATA_UNAVAILABLE')).toBeInTheDocument()
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
    // fixture -> jamais de cote fabriquée, uniquement le texte honnête -
    // affiché UNE SEULE FOIS pour le match entier (plus de duplication par
    // bloc Over/Under, voir audit UX).
    expect(
      screen.getByText(
        "Le moteur ne dispose pas encore d'un seuil d'edge minimal validé scientifiquement : aucune cote minimale de Value ne peut donc être affichée (voir « Contrôles / Gates » ci-dessous).",
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText('Value à partir de')).not.toBeInTheDocument()
    expect(screen.getAllByText('Entrez une cote de marché pour vérifier si une Value Bet est actuellement présente.')).toHaveLength(2)
    expect(screen.queryByText('VALUE')).not.toBeInTheDocument()
    expect(screen.queryByText('NO VALUE')).not.toBeInTheDocument()
    expect(screen.queryByText('Cote renseignée')).not.toBeInTheDocument()
  })

  it('cas avec cote sur un match NO_BET : jamais de badge VALUE, même si un côté a un price_edge positif', async () => {
    // FIXTURE_PREDICTION_WITH_MARKET a price_edge Under=+0.047 (positif) mais
    // decision=NO_BET (EDGE_BELOW_THRESHOLD) - avant le correctif, le badge
    // par côté affichait "VALUE" sur Under malgré la décision globale NO_BET,
    // une contradiction directe entre le haut et le bas de la page (trouvée
    // lors de l'audit visuel). Le badge ne doit plus JAMAIS afficher "VALUE"
    // quand la décision globale n'est pas BET, quel que soit le signe brut.
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_WITH_MARKET)
    renderPage()
    await searchAndSelectMatch()
    fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))

    await waitFor(() => expect(screen.getAllByText('Cote renseignée').length).toBe(2))
    expect(screen.getAllByText('NO VALUE')).toHaveLength(2)
    expect(screen.queryByText('VALUE')).not.toBeInTheDocument()
    expect(screen.getAllByText('2.20').length).toBeGreaterThan(0)
    expect(screen.getAllByText('1.67').length).toBeGreaterThan(0)
  })

  it('cas BET : le côté en Value affiche bien le badge VALUE', async () => {
    // Contre-épreuve du test précédent : quand la décision globale EST
    // BET, le côté dont le price_edge est positif doit afficher "VALUE" -
    // le correctif ne doit pas supprimer le cas positif légitime.
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_BET)
    renderPage()
    await searchAndSelectMatch()
    fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))

    await waitFor(() => expect(screen.getByText('BET')).toBeInTheDocument())
    expect(screen.getByText('VALUE')).toBeInTheDocument()
    expect(screen.getByText('NO VALUE')).toBeInTheDocument()
  })

  it('affiche explicitement le marché analysé (Over/Under 2.5 buts)', async () => {
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_NO_MARKET)
    renderPage()
    await searchAndSelectMatch()
    fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))

    await waitFor(() => expect(screen.getByText('Over 2.5')).toBeInTheDocument())
    expect(screen.getByText('Marché analysé :')).toBeInTheDocument()
    expect(screen.getByText('Over/Under 2.5 buts')).toBeInTheDocument()
  })

  it('cas BET avec cote renseignée réellement plus généreuse que la cote juste : explique pourquoi', async () => {
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_BET_GENEROUS_ODDS)
    renderPage()
    await searchAndSelectMatch()
    fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))

    await waitFor(() => expect(screen.getByText('VALUE')).toBeInTheDocument())
    // Under 2.5 est le côté en Value ici (price_edge=+0.124, cote renseignée
    // 2.00 > cote juste ≈1.78) - la phrase doit dire "plus généreuse", jamais
    // le texte de repli neutre, puisque la relation numérique est bien celle-là.
    expect(screen.getByText(/plus généreuse que la cote juste du modèle/)).toBeInTheDocument()
    // Over 2.5 (NO VALUE) ne doit porter AUCUNE explication - rien à justifier.
    const overCard = screen.getByText('Over 2.5').closest('.value-bet-card')
    expect(overCard?.textContent).not.toMatch(/généreuse|différente que la cote juste/)
  })

  it('cas BET avec fixture non cohérente numériquement : jamais une fausse affirmation "plus généreuse"', async () => {
    // FIXTURE_PREDICTION_BET a une cote Under renseignée (1.67) INFÉRIEURE à
    // sa cote juste (≈1.78) alors que price_edge.Under est positif (fixture
    // arbitraire, non recalculée depuis la formule réelle) - la phrase ne
    // doit JAMAIS prétendre "plus généreuse" dans ce cas, seulement le texte
    // de repli neutre, factuellement toujours vrai.
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_BET)
    renderPage()
    await searchAndSelectMatch()
    fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))

    await waitFor(() => expect(screen.getByText('VALUE')).toBeInTheDocument())
    expect(screen.queryByText(/plus généreuse/)).not.toBeInTheDocument()
    expect(screen.getByText(/différente que la cote juste du modèle/)).toBeInTheDocument()
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

  it('ignore une réponse de prédiction périmée arrivant après celle d’une analyse plus récente', async () => {
    // Garde-fou anti-course (audit UX) : analyser Marseille–Strasbourg
    // (reponse LENTE, gardee en attente), puis changer de match et analyser
    // Brest–PSG (reponse RAPIDE, resolue en premier) - si la reponse lente
    // arrivait ensuite et ecrasait l'etat affiche, l'utilisateur verrait une
    // decision qui ne correspond plus au match affiche a l'ecran.
    getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
    let resolveStale: (value: MatchDecisionOutput) => void = () => {}
    const stalePromise = new Promise<MatchDecisionOutput>((resolve) => {
      resolveStale = resolve
    })
    getPredictionMock.mockReturnValueOnce(stalePromise)
    renderPage()
    await searchAndSelectMatch() // Marseille - Strasbourg
    fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))
    await waitFor(() => expect(getPredictionMock).toHaveBeenCalledWith('31940', 'ligue1', '2026_27', undefined))
    expect(screen.getByRole('button', { name: 'Analyse en cours…' })).toBeInTheDocument()

    // Changement de match AVANT que la première réponse n'arrive.
    getPredictionMock.mockResolvedValueOnce(FIXTURE_PREDICTION_BET)
    fireEvent.change(screen.getByLabelText('Équipe à domicile'), { target: { value: 'Brest' } })
    fireEvent.change(screen.getByLabelText("Équipe à l'extérieur"), { target: { value: 'Paris Saint Germain' } })
    fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))
    await waitFor(() => expect(getPredictionMock).toHaveBeenCalledWith('31975', 'ligue1', '2026_27', undefined))
    await waitFor(() => expect(screen.getByText('BET')).toBeInTheDocument())
    expect(screen.getAllByText('Brest – Paris Saint Germain').length).toBe(2)

    // La réponse périmée (Marseille–Strasbourg, NO_BET) arrive maintenant,
    // APRÈS la réponse de l'analyse plus récente - elle ne doit RIEN changer
    // à l'écran : ni la décision affichée, ni l'équipe affichée. `act` força
    // explicitement React à appliquer tout effet du `.then()` résolu avant
    // les assertions (sans ça, un `setState` ignoré à tort passerait quand
    // même le test faute d'avoir été réellement flush).
    await act(async () => {
      resolveStale(FIXTURE_PREDICTION_NO_MARKET)
      await stalePromise
      await Promise.resolve()
    })
    expect(screen.getByText('BET')).toBeInTheDocument()
    expect(screen.queryByText('NO_BET')).not.toBeInTheDocument()
    expect(screen.getAllByText('Brest – Paris Saint Germain').length).toBe(2)
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

  // --- EXTENSION UI - seuil explicite de Value Bet ------------------------
  //
  // Rend explicite ce que le moteur calcule DÉJÀ (fair_price = 1/p_model,
  // final_engine/pricing.py, INCHANGÉ) - AUCUN nouveau calcul côté
  // frontend. Over 2.5 : p=0.438 -> fair=2.28 ; Under 2.5 (complément) :
  // p=0.562 -> fair=1.78 (mêmes valeurs déjà utilisées par les tests
  // existants ci-dessus, jamais recalculées différemment ici).

  describe('seuil explicite de Value Bet (fair_price)', () => {
    it('affiche la formulation "Value Bet mathématique" avec la cote juste correcte, pour Over ET Under, même sans cote renseignée', async () => {
      getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
      getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_NO_MARKET)
      renderPage()
      await searchAndSelectMatch()
      fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))

      await waitFor(() => expect(screen.getByText('Over 2.5')).toBeInTheDocument())
      expect(screen.getByText('Value Bet mathématique si la cote proposée dépasse 2.28. La décision du moteur reste indépendante de ce seul critère.')).toBeInTheDocument()
      expect(screen.getByText('Value Bet mathématique si la cote proposée dépasse 1.78. La décision du moteur reste indépendante de ce seul critère.')).toBeInTheDocument()
    })

    it('ne modifie ni n’affecte la décision NO_BET déjà affichée (le moteur, pas ce texte, reste seul décideur)', async () => {
      getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
      getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_NO_MARKET)
      renderPage()
      await searchAndSelectMatch()
      fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))

      await waitFor(() => expect(screen.getByText('NO_BET')).toBeInTheDocument())
      expect(screen.getByText(/Value Bet mathématique si la cote proposée dépasse 2\.28/)).toBeInTheDocument()
      // La décision reste NO_BET - jamais basculée en BET par la seule
      // présence du texte de seuil mathématique.
      expect(screen.queryByText('BET')).not.toBeInTheDocument()
    })

    it('n’affirme jamais qu’une cote dépassant le seuil déclenche automatiquement un pari (BET)', async () => {
      getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
      getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_WITH_MARKET)
      renderPage()
      await searchAndSelectMatch()
      fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))

      // FIXTURE_PREDICTION_WITH_MARKET : decision=NO_BET (EDGE_BELOW_THRESHOLD)
      // malgré un price_edge positif sur Under - cas réel où la cote
      // renseignée dépasse déjà la cote juste, sans que cela ne déclenche BET.
      await waitFor(() => expect(screen.getAllByText('Cote renseignée').length).toBe(2))
      expect(screen.getByText('NO_BET')).toBeInTheDocument()
      expect(screen.queryByText('BET')).not.toBeInTheDocument()
      const thresholdTexts = screen.getAllByText(/Value Bet mathématique si la cote proposée dépasse/)
      for (const node of thresholdTexts) {
        expect(node.textContent).not.toMatch(/recommand|automatiquement|déclenche (un |le )?(pari|bet)/i)
      }
    })

    it('reste absent quand les probabilités/fair_price sont indisponibles (historique insuffisant) - aucune régression', async () => {
      getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
      getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_INSUFFICIENT_DATA)
      renderPage()
      await searchAndSelectMatch()
      fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))

      await waitFor(() => expect(screen.getByText(/Probabilités indisponibles pour ce match/)).toBeInTheDocument())
      expect(screen.queryByText(/Value Bet mathématique si la cote proposée dépasse/)).not.toBeInTheDocument()
    })
  })

  describe('pronostic du modèle (Over/Under favori)', () => {
    it('désigne le côté dont la probabilité est la plus haute, avec sa probabilité exacte, et le signale visuellement sur sa carte', async () => {
      getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
      getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_NO_MARKET)
      renderPage()
      await searchAndSelectMatch()
      fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))

      // FIXTURE_PREDICTION_NO_MARKET : P(Over 2.5)=0.438 -> P(Under 2.5)=0.562,
      // Under est donc le côté favori.
      await waitFor(() => expect(screen.getByText('UNDER 2.5 (56.2 %)')).toBeInTheDocument())
      const underCard = screen.getByText('Under 2.5').closest('.value-bet-card')!
      const overCard = screen.getByText('Over 2.5').closest('.value-bet-card')!
      expect(underCard.className).toContain('value-bet-card-favored')
      expect(overCard.className).not.toContain('value-bet-card-favored')
      // Le badge "Favori du modèle" n'apparaît que sur la carte favorite (Under) -
      // d'autres cartes de projection (3.5/4.5) portent aussi ce badge, voir le
      // bloc "pronostic par seuil supplémentaire" plus bas, d'où une vérification
      // scopée à CETTE carte plutôt qu'un `getByText` global.
      expect(underCard.textContent).toContain('Favori du modèle')
      expect(overCard.textContent).not.toContain('Favori du modèle')
    })

    it('n’affiche jamais le pronostic comme une recommandation de pari (BET) - texte factuel uniquement', async () => {
      getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
      getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_NO_MARKET)
      renderPage()
      await searchAndSelectMatch()
      fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))

      await waitFor(() => expect(screen.getByText('UNDER 2.5 (56.2 %)')).toBeInTheDocument())
      const summary = screen.getByText('UNDER 2.5 (56.2 %)').closest('p.favored-side-summary')!
      expect(summary.textContent).not.toMatch(/recommand|pariez|misez|jouez/i)
      expect(screen.getByText('NO_BET')).toBeInTheDocument()
    })
  })

  describe('autres lignes de buts (3.5, 4.5 - projection seule, demande explicite)', () => {
    it('affiche la probabilité et la cote juste pour 3.5 ET 4.5, avec le côté favori signalé par carte', async () => {
      getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
      getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_NO_MARKET)
      renderPage()
      await searchAndSelectMatch()
      fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))

      // FIXTURE_PREDICTION_NO_MARKET : P(Over 3.5)=0.2 -> P(Under 3.5)=0.8 ;
      // P(Over 4.5)=0.1 -> P(Under 4.5)=0.9 - Under favori dans les deux cas.
      await waitFor(() => expect(screen.getByText('Autres lignes de buts')).toBeInTheDocument())
      expect(screen.getByText('UNDER 3.5 (80.0 %)')).toBeInTheDocument()
      expect(screen.getByText('UNDER 4.5 (90.0 %)')).toBeInTheDocument()

      const under35Card = screen.getByText('Under 3.5').closest('.value-bet-card')!
      const over35Card = screen.getByText('Over 3.5').closest('.value-bet-card')!
      expect(under35Card.textContent).toContain('80.0 %')
      expect(under35Card.textContent).toContain('1.25') // cote juste Under = 1 / 0.8
      expect(under35Card.textContent).toContain('Favori du modèle')
      expect(over35Card.textContent).not.toContain('Favori du modèle')

      const under45Card = screen.getByText('Under 4.5').closest('.value-bet-card')!
      expect(under45Card.textContent).toContain('90.0 %')
    })

    it('n’affiche jamais de cote renseignée, de badge VALUE ni de champ de saisie pour ces seuils - aucun marché réel à comparer', async () => {
      getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
      getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_NO_MARKET)
      renderPage()
      await searchAndSelectMatch()
      fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))

      await waitFor(() => expect(screen.getByText('Autres lignes de buts')).toBeInTheDocument())
      const under35Card = screen.getByText('Under 3.5').closest('.value-bet-card')!
      expect(under35Card.textContent).not.toContain('Cote renseignée')
      expect(under35Card.textContent).not.toMatch(/VALUE/)
      expect(under35Card.querySelector('input')).toBeNull()
    })

    it('reste absent quand les probabilités sont indisponibles (historique insuffisant) - aucune régression', async () => {
      getMatchesMock.mockResolvedValue(FIXTURE_MATCHES)
      getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_INSUFFICIENT_DATA)
      renderPage()
      await searchAndSelectMatch()
      fireEvent.click(screen.getByRole('button', { name: 'Analyser le match' }))

      await waitFor(() => expect(screen.getByText(/Probabilités indisponibles pour ce match/)).toBeInTheDocument())
      expect(screen.queryByText('Autres lignes de buts')).not.toBeInTheDocument()
    })
  })

  // --- EXTENSION fixtures futures 2026/27 ---------------------------------

  describe('fixtures futures (B/C) - heure estimée (B, Ligue 1) ou analyse indisponible (C)', () => {
    it('autorise "Analyser le match" pour une fixture B Ligue 1 (heure locale connue, kickoff_utc absent) avec une heure UTC estimée - demande produit explicite : l’heure ne doit jamais bloquer', async () => {
      getMatchesMock.mockResolvedValue([FIXTURE_MATCH_STATE_B])
      getPredictionMock.mockResolvedValue({ ...FIXTURE_PREDICTION_NO_MARKET, kickoff_utc_estimated: true })
      renderPage()

      fireEvent.click(screen.getByRole('tab', { name: 'Ligue 1' }))
      fireEvent.change(screen.getByLabelText('Saison'), { target: { value: '2026_27' } })
      await waitFor(() => expect(screen.getByLabelText('Équipe à domicile')).toBeInTheDocument())
      fireEvent.change(screen.getByLabelText('Équipe à domicile'), { target: { value: 'Lens' } })
      fireEvent.change(screen.getByLabelText("Équipe à l'extérieur"), { target: { value: 'Lyon' } })

      expect(screen.getByText('Lens – Lyon')).toBeInTheDocument()
      // Heure locale affichée explicitement comme telle, jamais comme UTC.
      expect(screen.getByText(/9 octobre 2026 · 20:45 \(heure locale, UTC non confirmée\)/)).toBeInTheDocument()
      expect(screen.getByText(/Match à venir/)).toBeInTheDocument()
      // Rappel explicite AVANT même de cliquer "Analyser" : l'heure utilisée
      // sera une estimation, jamais un fait masqué.
      expect(
        screen.getByText(
          "Heure de coup d'envoi estimée (conversion CET/CEST depuis l'heure locale publiée) - non confirmée par une seconde source indépendante.",
        ),
      ).toBeInTheDocument()
      const analyzeButton = screen.getByRole('button', { name: 'Analyser le match' })
      expect(analyzeButton).not.toBeDisabled()

      fireEvent.click(analyzeButton)
      await waitFor(() => expect(getPredictionMock).toHaveBeenCalled())
      expect(screen.getByText('NO_BET')).toBeInTheDocument()
    })

    it('désactive "Analyser le match" pour une fixture C (aucune heure publiée) et explique pourquoi', async () => {
      getMatchesMock.mockResolvedValue([FIXTURE_MATCH_STATE_C])
      renderPage()

      fireEvent.click(screen.getByRole('tab', { name: 'Ligue 1' }))
      fireEvent.change(screen.getByLabelText('Saison'), { target: { value: '2026_27' } })
      await waitFor(() => expect(screen.getByLabelText('Équipe à domicile')).toBeInTheDocument())
      fireEvent.change(screen.getByLabelText('Équipe à domicile'), { target: { value: 'Lens' } })
      fireEvent.change(screen.getByLabelText("Équipe à l'extérieur"), { target: { value: 'Le Havre' } })

      expect(screen.getByText('Lens – Le Havre')).toBeInTheDocument()
      expect(screen.getByText(/5 décembre 2026 \(heure non publiée\)/)).toBeInTheDocument()
      expect(
        screen.getByText('Analyse indisponible : heure de coup d’envoi non publiée.'),
      ).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Analyser le match' })).toBeDisabled()
      expect(getPredictionMock).not.toHaveBeenCalled()
    })

    it('ne laisse jamais entendre qu’une heure précise rendra le match analysable plus tard', async () => {
      // Garde-fou explicite du cadrage : le texte ne doit jamais fabriquer
      // une promesse d'heure/UTC future - uniquement un fait présent.
      getMatchesMock.mockResolvedValue([FIXTURE_MATCH_STATE_B, FIXTURE_MATCH_STATE_C])
      renderPage()

      fireEvent.click(screen.getByRole('tab', { name: 'Ligue 1' }))
      fireEvent.change(screen.getByLabelText('Saison'), { target: { value: '2026_27' } })
      await waitFor(() => expect(screen.getByLabelText('Équipe à domicile')).toBeInTheDocument())
      fireEvent.change(screen.getByLabelText('Équipe à domicile'), { target: { value: 'Lens' } })
      fireEvent.change(screen.getByLabelText("Équipe à l'extérieur"), { target: { value: 'Le Havre' } })

      const message = screen.getByText('Analyse indisponible : heure de coup d’envoi non publiée.')
      expect(message.textContent).not.toMatch(/bientôt|prochainement|à \d{1,2}:\d{2}|sera analysable/i)
    })
  })
})
