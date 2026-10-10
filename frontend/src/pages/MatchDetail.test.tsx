import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import type { MatchDecisionOutput, MatchResponse } from '../api/types'
import { MatchDetail } from './MatchDetail'

const { getMatchMock, getPredictionMock } = vi.hoisted(() => ({
  getMatchMock: vi.fn(),
  getPredictionMock: vi.fn(),
}))

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client')
  return { ...actual, getMatch: getMatchMock, getPrediction: getPredictionMock }
})

// Fixtures de test explicitement identifiées comme telles - reproduisent
// la forme d'une réponse RÉELLE de l'API (match Brest–PSG, id 31975,
// capturée via l'API réelle pendant l'audit de cette étape), jamais une
// forme inventée.
const FIXTURE_MATCH: MatchResponse = {
  match_id: '31975',
  competition: 'ligue1',
  season: '2026_27',
  fixture_date: '2026-09-13',
  kickoff_local_naive: null,
  kickoff_utc: '2026-09-13T18:45:00Z',
  home_team: 'Brest',
  away_team: 'Paris Saint Germain',
  is_played: true,
}

const FIXTURE_PREDICTION_NO_MARKET: MatchDecisionOutput = {
  match_id: 'ligue1:2026_27:Brest_vs_Paris Saint Germain:2026-09-13T18:45:00',
  timestamp_decision: '2026-09-13T16:45:00',
  competition: 'ligue1',
  season: '2026_27',
  primary_model: 'poisson_simple',
  models: {
    poisson_simple: { model: 'poisson_simple', lam: 1.146, mu: 2.765, rho: null, n_train_matches: 646 },
    dixon_coles: { model: 'dixon_coles', lam: 1.15, mu: 2.77, rho: -0.05, n_train_matches: 646 },
    xg_model: { model: 'xg_model', lam: 1.12, mu: 2.71, rho: null, n_train_matches: 646 },
  },
  calibration: {
    poisson_simple: {
      model: 'poisson_simple',
      scale_c: 0.88,
      n_calibration_used: 637,
      goal_distribution: [0.03, 0.1, 0.19, 0.22, 0.19, 0.13, 0.14],
      probabilities: { '0.5': 0.964, '1.5': 0.863, '2.5': 0.671, '3.5': 0.454, '4.5': 0.266 },
    },
    dixon_coles: {
      model: 'dixon_coles',
      scale_c: 0.89,
      n_calibration_used: 637,
      goal_distribution: [0.03, 0.1, 0.19, 0.22, 0.19, 0.13, 0.14],
      probabilities: { '0.5': 0.965, '1.5': 0.864, '2.5': 0.672, '3.5': 0.455, '4.5': 0.267 },
    },
    xg_model: {
      model: 'xg_model',
      scale_c: 0.81,
      n_calibration_used: 629,
      goal_distribution: [0.03, 0.11, 0.19, 0.22, 0.18, 0.12, 0.12],
      probabilities: { '0.5': 0.965, '1.5': 0.847, '2.5': 0.65, '3.5': 0.43, '4.5': 0.246 },
    },
  },
  pricing: {
    poisson_simple: { fair_price: { '0.5': 1.03, '1.5': 1.16, '2.5': 1.49, '3.5': 2.2, '4.5': 3.76 } },
    dixon_coles: { fair_price: { '0.5': 1.04, '1.5': 1.16, '2.5': 1.49, '3.5': 2.2, '4.5': 3.76 } },
    xg_model: { fair_price: { '0.5': 1.04, '1.5': 1.18, '2.5': 1.54, '3.5': 2.33, '4.5': 4.07 } },
  },
  market: null,
  qualification: {
    calibration_status: { '0.5': 'INSUFFICIENT_VALIDATION', '1.5': 'OK', '2.5': 'ZONE_BIAISEE_NON_CORRIGEE', '3.5': 'OK', '4.5': 'INSUFFICIENT_VALIDATION' },
    discrimination_status: 'DEMONTREE',
    data_quality: ['MARKET_DATA_UNAVAILABLE'],
    scientific_gates: [
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
    operational_gates: [
      {
        name: 'calibration_confidence_gate',
        triggered: true,
        reason: 'Confiance de calibration insuffisante (seuil operationnel : calibration_status == OK requis).',
        metric: 'calibration_status',
        observed_value: 'ZONE_BIAISEE_NON_CORRIGEE',
        threshold: 'OK',
        failure_code: 'INSUFFICIENT_CONFIDENCE_CALIBRATION_ZONE',
      },
      {
        name: 'edge_threshold_gate',
        triggered: true,
        reason: "Aucun seuil d'edge minimal valide par E1-E16 (PARAMETRE OPERATIONNEL A VALIDER, jamais fixe).",
        metric: 'raw_edge',
        observed_value: null,
        threshold: null,
        failure_code: 'EDGE_BELOW_THRESHOLD',
      },
    ],
  },
  decision: {
    decision: 'NO_BET',
    decision_reason: ['EDGE_BELOW_THRESHOLD', 'INSUFFICIENT_CONFIDENCE_CALIBRATION_ZONE', 'MARKET_DATA_UNAVAILABLE'],
  },
  engine_version: 'final-engine-mvp-0.1.0',
  parameters_snapshot: {
    require_calibration_ok: true,
    require_discrimination_demontree: true,
    abstain_on_calibration_zone: true,
    min_edge_threshold: null,
    decision_offset_hours: 2.0,
  },
  kickoff_utc_estimated: false,
}

const FIXTURE_PREDICTION_WITH_MARKET: MatchDecisionOutput = {
  ...FIXTURE_PREDICTION_NO_MARKET,
  market: {
    market_odds: { Over: 1.9, Under: 1.9 },
    market_implied_probability_raw: { Over: 0.526, Under: 0.526 },
    market_implied_probability_normalized: { Over: 0.5, Under: 0.5 },
    market_overround: 0.0526,
    raw_edge: { Over: 0.171, Under: -0.171 },
    price_edge: { Over: 0.274, Under: -0.374 },
  },
  decision: {
    decision: 'NO_BET',
    decision_reason: ['EDGE_BELOW_THRESHOLD', 'INSUFFICIENT_CONFIDENCE_CALIBRATION_ZONE'],
  },
}

const FIXTURE_PREDICTION_INSUFFICIENT_DATA: MatchDecisionOutput = {
  ...FIXTURE_PREDICTION_NO_MARKET,
  models: {
    poisson_simple: null,
    dixon_coles: null,
    xg_model: null,
  },
  calibration: {
    poisson_simple: { model: 'poisson_simple', scale_c: null, n_calibration_used: 0, goal_distribution: null, probabilities: null },
    dixon_coles: { model: 'dixon_coles', scale_c: null, n_calibration_used: 0, goal_distribution: null, probabilities: null },
    xg_model: { model: 'xg_model', scale_c: null, n_calibration_used: 0, goal_distribution: null, probabilities: null },
  },
  pricing: { poisson_simple: null, dixon_coles: null, xg_model: null },
  decision: {
    decision: 'NO_BET',
    decision_reason: ['INSUFFICIENT_HISTORY'],
  },
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
  getPredictionMock.mockReset()
})

describe('MatchDetail', () => {
  it("affiche un état de chargement puis le match réel via le client API mocké", async () => {
    getMatchMock.mockResolvedValue(FIXTURE_MATCH)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_NO_MARKET)
    renderDetail('/matches/ligue1/2026_27/31975')

    expect(screen.getByText(/Chargement du match/)).toBeInTheDocument()

    await waitFor(() => expect(screen.getByText('Brest – Paris Saint Germain')).toBeInTheDocument())
    expect(screen.getByText('Compétition : ligue1')).toBeInTheDocument()
    expect(screen.getByText('Saison : 2026_27')).toBeInTheDocument()
    expect(screen.getByText('Identifiant : 31975')).toBeInTheDocument()
    expect(getMatchMock).toHaveBeenCalledWith('31975', 'ligue1', '2026_27')
  })

  it('affiche un message explicite quand le match est introuvable (404)', async () => {
    getMatchMock.mockRejectedValue(new ApiError(404, "Match '999999' introuvable pour competition='ligue1', season='2026_27'."))
    renderDetail('/matches/ligue1/2026_27/999999')

    await waitFor(() => expect(screen.getByText(/introuvable/)).toBeInTheDocument())
    expect(getPredictionMock).not.toHaveBeenCalled()
  })

  it('affiche un message d’erreur explicite sur une erreur API générique (match)', async () => {
    getMatchMock.mockRejectedValue(new ApiError(400, "Saison inconnue : '2099_00'."))
    renderDetail('/matches/ligue1/2099_00/31975')

    await waitFor(() => expect(screen.getByText(/Saison inconnue/)).toBeInTheDocument())
  })

  it('propose un lien de retour vers l’explorateur préservant compétition/saison', async () => {
    getMatchMock.mockResolvedValue(FIXTURE_MATCH)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_NO_MARKET)
    renderDetail('/matches/ligue1/2026_27/31975')

    await waitFor(() => expect(screen.getByText('Brest – Paris Saint Germain')).toBeInTheDocument())
    const back = screen.getByRole('link', { name: /Retour à l'explorateur/ })
    expect(back).toHaveAttribute('href', '/matches?competition=ligue1&season=2026_27')
  })

  // --- 1. appel correct de getPrediction() ------------------------------

  it('appelle getPrediction() avec le match/competition/saison réels, sans cote au chargement initial', async () => {
    getMatchMock.mockResolvedValue(FIXTURE_MATCH)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_NO_MARKET)
    renderDetail('/matches/ligue1/2026_27/31975')

    await waitFor(() => expect(getPredictionMock).toHaveBeenCalledWith('31975', 'ligue1', '2026_27', undefined))
  })

  // --- 8. état de chargement (prédiction) --------------------------------

  it('affiche un état de chargement pour la prédiction pendant l’appel API', async () => {
    getMatchMock.mockResolvedValue(FIXTURE_MATCH)
    let resolvePrediction: (value: MatchDecisionOutput) => void = () => {}
    getPredictionMock.mockReturnValue(new Promise((resolve) => (resolvePrediction = resolve)))
    renderDetail('/matches/ligue1/2026_27/31975')

    await waitFor(() => expect(screen.getByText('Brest – Paris Saint Germain')).toBeInTheDocument())
    expect(screen.getByText(/Calcul de la prédiction/)).toBeInTheDocument()

    resolvePrediction(FIXTURE_PREDICTION_NO_MARKET)
    await waitFor(() => expect(screen.queryByText(/Calcul de la prédiction/)).not.toBeInTheDocument())
  })

  // --- 2. affichage d'une prédiction valide + 3. probabilités -----------

  it('affiche une prédiction valide avec le modèle principal et les probabilités du moteur', async () => {
    getMatchMock.mockResolvedValue(FIXTURE_MATCH)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_NO_MARKET)
    renderDetail('/matches/ligue1/2026_27/31975')

    await waitFor(() => expect(screen.getAllByText('poisson_simple').length).toBeGreaterThan(0))
    expect(screen.getByText(/final-engine-mvp-0.1.0/)).toBeInTheDocument()
    // Probabilité réelle du fixture (0.671 -> "67.1 %"), jamais recalculée.
    expect(screen.getByText('67.1 %')).toBeInTheDocument()
    expect(screen.getAllByText(/entraîné sur 646 matchs/).length).toBeGreaterThan(0)
  })

  // --- 4. affichage de NO_BET ---------------------------------------------

  it('affiche fidèlement la décision NO_BET renvoyée par le moteur', async () => {
    getMatchMock.mockResolvedValue(FIXTURE_MATCH)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_NO_MARKET)
    renderDetail('/matches/ligue1/2026_27/31975')

    await waitFor(() => expect(screen.getByText('NO_BET')).toBeInTheDocument())
    expect(screen.queryByText('BET')).not.toBeInTheDocument()
  })

  // --- 5. affichage du decision_reason traduit ---------------------------

  it('traduit les codes de decision_reason en texte lisible, sans masquer le code brut', async () => {
    getMatchMock.mockResolvedValue(FIXTURE_MATCH)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_NO_MARKET)
    renderDetail('/matches/ligue1/2026_27/31975')

    await waitFor(() => expect(screen.getByText('EDGE_BELOW_THRESHOLD')).toBeInTheDocument())
    expect(screen.getByText(/Aucun seuil d'edge minimal validé scientifiquement/)).toBeInTheDocument()
    expect(screen.getByText('MARKET_DATA_UNAVAILABLE')).toBeInTheDocument()
    expect(screen.getByText('Aucune cote de marché disponible pour ce match.', { exact: true, selector: 'span' })).toBeInTheDocument()
  })

  // --- 6. absence de données de marché ------------------------------------

  it('indique explicitement l’absence de données de marché sans afficher d’edge', async () => {
    getMatchMock.mockResolvedValue(FIXTURE_MATCH)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_NO_MARKET)
    renderDetail('/matches/ligue1/2026_27/31975')

    await waitFor(() => expect(screen.getByText(/Données de marché non fournies/)).toBeInTheDocument())
    expect(screen.queryByText('Edge brut')).not.toBeInTheDocument()
  })

  it('affiche le marché, la probabilité implicite et l’edge quand des cotes sont fournies', async () => {
    getMatchMock.mockResolvedValue(FIXTURE_MATCH)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_WITH_MARKET)
    renderDetail('/matches/ligue1/2026_27/31975')

    await waitFor(() => expect(screen.getByText('Edge brut')).toBeInTheDocument())
    expect(screen.getAllByText('1.90').length).toBeGreaterThan(0)
    expect(screen.getAllByText('50.0 %').length).toBeGreaterThan(0)
  })

  // --- 7. erreur API (prédiction) -----------------------------------------

  it('affiche un message d’erreur explicite si l’appel de prédiction échoue', async () => {
    getMatchMock.mockResolvedValue(FIXTURE_MATCH)
    getPredictionMock.mockRejectedValue(new ApiError(400, "Cotes incoherentes : Over=0.5, Under=1.9."))
    renderDetail('/matches/ligue1/2026_27/31975')

    await waitFor(() => expect(screen.getByText(/Cotes incoherentes/)).toBeInTheDocument())
  })

  // --- 9. données insuffisantes -------------------------------------------

  it('affiche les modèles indisponibles sans planter quand l’historique est insuffisant', async () => {
    getMatchMock.mockResolvedValue(FIXTURE_MATCH)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_INSUFFICIENT_DATA)
    renderDetail('/matches/ligue1/2026_27/31975')

    await waitFor(() => expect(screen.getByText('INSUFFICIENT_HISTORY')).toBeInTheDocument())
    expect(screen.getByText(/Historique d'entraînement insuffisant pour ce match\./)).toBeInTheDocument()
    expect(screen.getAllByText(/indisponible \(historique d'entraînement insuffisant\)/).length).toBe(3)
    expect(screen.getAllByText(/Probabilités indisponibles/).length).toBe(3)
  })

  // --- saisie des cotes de marché ------------------------------------------

  it('renseigner les deux cotes déclenche un nouvel appel getPrediction avec ces cotes', async () => {
    getMatchMock.mockResolvedValue(FIXTURE_MATCH)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_NO_MARKET)
    renderDetail('/matches/ligue1/2026_27/31975')

    await waitFor(() => expect(getPredictionMock).toHaveBeenCalledWith('31975', 'ligue1', '2026_27', undefined))

    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_WITH_MARKET)
    fireEvent.change(screen.getByLabelText('Cote Over 2.5'), { target: { value: '1.9' } })
    fireEvent.change(screen.getByLabelText('Cote Under 2.5'), { target: { value: '1.9' } })
    fireEvent.click(screen.getByRole('button', { name: 'Appliquer les cotes' }))

    await waitFor(() =>
      expect(getPredictionMock).toHaveBeenCalledWith('31975', 'ligue1', '2026_27', { over_2_5: 1.9, under_2_5: 1.9 }),
    )
  })

  it('refuse de soumettre une seule cote sans appeler l’API avec une valeur partielle', async () => {
    getMatchMock.mockResolvedValue(FIXTURE_MATCH)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_NO_MARKET)
    renderDetail('/matches/ligue1/2026_27/31975')

    await waitFor(() => expect(getPredictionMock).toHaveBeenCalledWith('31975', 'ligue1', '2026_27', undefined))
    getPredictionMock.mockClear()

    fireEvent.change(screen.getByLabelText('Cote Over 2.5'), { target: { value: '1.9' } })
    fireEvent.click(screen.getByRole('button', { name: 'Appliquer les cotes' }))

    expect(screen.getByText(/Erreur : Renseignez les deux cotes/)).toBeInTheDocument()
    expect(getPredictionMock).not.toHaveBeenCalled()
  })

  // --- hiérarchie visuelle (phase finition UX) ----------------------------

  it('distingue visuellement le modèle principal (badge) sans altérer les autres modèles', async () => {
    getMatchMock.mockResolvedValue(FIXTURE_MATCH)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_NO_MARKET)
    renderDetail('/matches/ligue1/2026_27/31975')

    await waitFor(() => expect(screen.getAllByText('poisson_simple').length).toBeGreaterThan(0))
    // Exactement 2 badges "Principal" attendus : un dans "Modèles utilisés",
    // un dans la table des probabilités - jamais sur dixon_coles/xg_model.
    expect(screen.getAllByLabelText('Modèle principal')).toHaveLength(2)
  })

  it('replie les détails d’audit par défaut sans supprimer l’information (accessible au clic)', async () => {
    getMatchMock.mockResolvedValue(FIXTURE_MATCH)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_NO_MARKET)
    renderDetail('/matches/ligue1/2026_27/31975')

    await waitFor(() => expect(screen.getByText('Qualification / calibration')).toBeInTheDocument())

    const qualificationDetails = screen.getByText('Qualification / calibration').closest('details')
    expect(qualificationDetails).not.toBeNull()
    expect(qualificationDetails).not.toHaveAttribute('open')

    // Toujours présent dans le DOM (jamais supprimé), uniquement replié.
    expect(screen.getByText(/Discrimination du modèle principal/)).toBeInTheDocument()

    fireEvent.click(screen.getByText('Qualification / calibration'))
    expect(qualificationDetails).toHaveAttribute('open')
  })

  it('n’affecte pas la décision/les raisons, qui restent visibles sans ouvrir de détail', async () => {
    getMatchMock.mockResolvedValue(FIXTURE_MATCH)
    getPredictionMock.mockResolvedValue(FIXTURE_PREDICTION_NO_MARKET)
    renderDetail('/matches/ligue1/2026_27/31975')

    await waitFor(() => expect(screen.getByText('NO_BET')).toBeInTheDocument())
    // La décision et ses raisons ne sont jamais dans un <details> replié.
    expect(screen.getByText('NO_BET').closest('details')).toBeNull()
    expect(screen.getByText('EDGE_BELOW_THRESHOLD').closest('details')).toBeNull()
  })

  // --- EXTENSION fixtures futures 2026/27 ---------------------------------

  describe('fixtures futures (B/C) - heure estimée (B, Ligue 1) ou analyse indisponible (C)', () => {
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

    it('affiche l’heure locale explicitement comme telle (jamais comme UTC) pour une fixture B Ligue 1, ET lance l’analyse avec une heure UTC estimée (demande produit explicite : l’heure ne doit jamais bloquer)', async () => {
      getMatchMock.mockResolvedValue(FIXTURE_MATCH_STATE_B)
      getPredictionMock.mockResolvedValue({ ...FIXTURE_PREDICTION_NO_MARKET, kickoff_utc_estimated: true })
      renderDetail('/matches/ligue1/2026_27/ligue1:2026_27:Lens_vs_Lyon:2026-10-09T20:45:00')

      await waitFor(() => expect(screen.getByText('Lens – Lyon')).toBeInTheDocument())
      expect(screen.getByText(/Coup d'envoi \(heure locale\) : 9 octobre 2026 · 20:45/)).toBeInTheDocument()
      expect(screen.getByText('Heure locale publiée par la source - conversion UTC non encore confirmée.')).toBeInTheDocument()
      expect(screen.getByText('Statut : Match à venir')).toBeInTheDocument()
      // L'analyse n'est plus bloquée pour une fixture Ligue 1 à heure locale
      // connue : l'API estime l'UTC (conversion CET/CEST) et la prédiction
      // s'affiche normalement, avec un rappel explicite que l'heure est
      // estimée - jamais masqué silencieusement.
      await waitFor(() => expect(getPredictionMock).toHaveBeenCalled())
      expect(
        screen.getByText(
          "Prédiction basée sur une heure de coup d'envoi estimée (conversion CET/CEST depuis l'heure locale publiée) - non confirmée par une seconde source indépendante.",
        ),
      ).toBeInTheDocument()
      expect(screen.queryByText('Analyse indisponible : heure connue localement, mais conversion UTC non confirmée.')).not.toBeInTheDocument()
      expect(screen.getByText('Cotes de marché')).toBeInTheDocument()
    })

    it('affiche "heure non publiée" pour une fixture C, sans jamais appeler getPrediction', async () => {
      getMatchMock.mockResolvedValue(FIXTURE_MATCH_STATE_C)
      renderDetail('/matches/ligue1/2026_27/ligue1:2026_27:Lens_vs_Le Havre:2026-12-05')

      await waitFor(() => expect(screen.getByText('Lens – Le Havre')).toBeInTheDocument())
      expect(screen.getByText('Date : 5 décembre 2026')).toBeInTheDocument()
      expect(screen.getByText('Heure non publiée.')).toBeInTheDocument()
      await waitFor(() =>
        expect(screen.getByText('Analyse indisponible : heure de coup d’envoi non publiée.')).toBeInTheDocument(),
      )
      expect(getPredictionMock).not.toHaveBeenCalled()
    })

    it('traite un HTTP 409 (KickoffUnavailableError) comme un cas propre et distinct, jamais comme une erreur serveur générique', async () => {
      // Garde défensive : même si l'appel était malgré tout déclenché (ne
      // devrait pas arriver, voir les deux tests ci-dessus), un 409 ne doit
      // jamais être rendu via le composant d'erreur générique.
      getMatchMock.mockResolvedValue(FIXTURE_MATCH)
      getPredictionMock.mockRejectedValue(new ApiError(409, "Match non analysable : kickoff_utc indisponible."))
      renderDetail('/matches/ligue1/2026_27/31975')

      await waitFor(() => expect(screen.getByText(/kickoff_utc indisponible/)).toBeInTheDocument())
      expect(screen.queryByText(/Erreur :/)).not.toBeInTheDocument()
      expect(document.querySelector('.state-error')).toBeNull()
    })

    it('un 404 (match introuvable) reste distinct d’un 409 (fixture non analysable)', async () => {
      getMatchMock.mockRejectedValue(new ApiError(404, "Match '999999' introuvable."))
      renderDetail('/matches/ligue1/2026_27/999999')

      await waitFor(() => expect(screen.getByText(/introuvable/)).toBeInTheDocument())
      expect(getPredictionMock).not.toHaveBeenCalled()
    })
  })
})
