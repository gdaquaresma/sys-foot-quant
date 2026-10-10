/**
 * Analyser un match (Phase UI-1) - nouvelle page d'entrée principale de
 * l'application. Remplace le Dashboard comme point d'entrée : l'utilisateur
 * choisit un match réel du catalogue puis lance l'analyse.
 *
 * GARDE-FOU EXPLICITE (identique à MatchDetail.tsx) : cette page n'effectue
 * AUCUN calcul de probabilité, d'edge ou de décision - elle consomme
 * exclusivement GET /matches et GET /matches/{match_id}/prediction via le
 * client API centralisé, et réutilise les composants déjà testés de
 * MatchDetail.tsx (ProbabilitiesTable, ModelsSummary, MarketSection,
 * formatters, libellés de raisons) pour la section technique détaillée.
 *
 * SEULE DÉRIVATION DE PRÉSENTATION (documentée précisément dans
 * `buildPrimaryModelMarketView` ci-dessous) : la probabilité/cote juste du
 * côté "Under 2.5" n'est pas exposée comme champ nommé séparé par l'API -
 * elle est reconstruite ici avec EXACTEMENT les deux formules déjà
 * utilisées en interne par le moteur (`final_engine/market.py` :
 * `1 - p_over` ; `final_engine/pricing.py::compute_fair_price` : `1 / p`),
 * jamais une nouvelle statistique ni un nouveau modèle.
 *
 * (Phase UI-2) « Seuil Value » : lit `parameters_snapshot.min_edge_threshold`
 * tel quel (voir `extractMinEdgeThreshold`) - n'affiche une cote minimale de
 * Value QUE si le moteur a réellement validé un seuil d'edge (actuellement
 * toujours `None` - voir `final_engine/gates.py::OperationalThresholds`).
 * Jamais de `1 / probabilité` ni de recalcul de `raw_edge` pour fabriquer un
 * chiffre : `raw_edge` dépend de la probabilité implicite normalisée du
 * marché (les deux côtés Over/Under conjointement), jamais recalculée ici.
 */
import { type FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import { SEASON_OPTIONS, competitionLabel, seasonLabel } from '../api/catalog'
import { ApiError, getMatches, getPrediction } from '../api/client'
import { analysisAvailability, formatFixtureDate, formatLocalKickoffTime } from '../api/fixtureTiming'
import type { MatchDecisionOutput, MatchResponse } from '../api/types'
import { CompetitionTabs } from '../components/CompetitionTabs'
import { EmptyState, ErrorState, LoadingState } from '../components/StateViews'
import {
  MarketSection,
  ModelsSummary,
  ProbabilitiesTable,
  describeReason,
  formatKickoff,
  formatOdds,
  formatParamValue,
  formatProbability,
} from './MatchDetail'

/** Résumé lisible de la date/heure d'une fixture, quelle que soit
 * l'information temporelle réellement connue - EXTENSION fixtures
 * futures 2026/27. Jamais une heure locale présentée comme une heure UTC
 * (voir `../api/fixtureTiming.ts`), ni une heure fabriquée pour les
 * fixtures sans heure publiée. */
function describeMatchDateTime(match: MatchResponse): string {
  if (match.kickoff_utc !== null) return formatKickoff(match.kickoff_utc)
  if (match.kickoff_local_naive !== null) {
    return `${formatFixtureDate(match.fixture_date)} · ${formatLocalKickoffTime(match.kickoff_local_naive)} (heure locale, UTC non confirmée)`
  }
  return `${formatFixtureDate(match.fixture_date)} (heure non publiée)`
}

/** Seul marché Over/Under pour lequel une cote réelle existe dans le corpus
 * (Football-Data ne publie une cote O/U que pour la ligne 2.5 - voir
 * `final_engine/market.py::compare_over_under_to_market`, INCHANGÉ) -
 * jamais une prétention à supporter un marché que le moteur ne calcule
 * pas réellement. */
const MARKET_THRESHOLD = '2.5'

type SearchState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; matches: MatchResponse[] }

type PredictionState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  // EXTENSION fixtures futures 2026/27 : fixture connue (B/C) mais
  // kickoff_utc absent - jamais un HTTP 409 rendu comme une erreur
  // serveur générique (voir handleAnalyze/runPrediction ci-dessous, qui
  // évite déjà d'appeler l'API dans ce cas - garde défensive pour le
  // `catch`).
  | { status: 'unavailable'; message: string }
  | { status: 'ready'; prediction: MatchDecisionOutput }

interface SideView {
  probability: number
  fairPrice: number
}

/** Dérive la vue Over/Under 2.5 du modèle PRINCIPAL. `over` vient
 * directement de `calibration.probabilities`/`pricing.fair_price` (API,
 * aucune transformation). `under` est son complément - voir le
 * commentaire d'en-tête du fichier. Retourne `null` si le modèle principal
 * n'a pas de probabilités disponibles (historique insuffisant), jamais une
 * valeur inventée. */
function buildPrimaryModelMarketView(prediction: MatchDecisionOutput): { over: SideView; under: SideView } | null {
  const calibration = prediction.calibration[prediction.primary_model]
  const pricing = prediction.pricing[prediction.primary_model]
  const overProbability = calibration?.probabilities?.[MARKET_THRESHOLD]
  if (overProbability === undefined || overProbability === null || !pricing) return null
  const overFairPrice = pricing.fair_price[MARKET_THRESHOLD]

  // Complément direct - même convention que `model_probs["Under"] = 1.0 -
  // model_probability_over` déjà calculée par `compare_over_under_to_market`
  // (final_engine/market.py) - et même transformation `1 / p` que
  // `compute_fair_price` (final_engine/pricing.py) pour la cote juste.
  const underProbability = 1 - overProbability
  const underFairPrice = underProbability > 0 ? 1 / underProbability : Number.POSITIVE_INFINITY

  return {
    over: { probability: overProbability, fairPrice: overFairPrice },
    under: { probability: underProbability, fairPrice: underFairPrice },
  }
}

/** Seuil d'edge minimal réellement validé par le moteur (`final_engine/
 * gates.py::OperationalThresholds.min_edge_threshold`, INCHANGÉ) - lu tel
 * quel dans `parameters_snapshot`, déjà transporté par l'API mais jusqu'ici
 * jamais lu explicitement ici. Vaut `None` tant qu'aucune valeur d'edge
 * minimal n'a été validée scientifiquement (E1-E16) - ce qui est le cas
 * aujourd'hui, systématiquement (voir `gates.py::edge_threshold_gate`).
 * Retourne `null` dans ce cas, JAMAIS une valeur fabriquée côté frontend :
 * pas de `1 / probabilité`, pas de recalcul de `raw_edge`, pas d'hypothèse
 * sur un seuil qui n'existe pas. */
function extractMinEdgeThreshold(parametersSnapshot: Record<string, unknown>): number | null {
  const value = parametersSnapshot['min_edge_threshold']
  return typeof value === 'number' ? value : null
}

/** Phrase humaine de synthèse - recompose la décision/les raisons/l'edge
 * déjà produits par le moteur, n'invente aucune donnée. Pour NO_BET, la
 * raison PRINCIPALE est intégrée directement dans la phrase (plutôt que
 * de forcer la lecture de la liste de raisons en dessous) - toujours le
 * même texte déjà fourni par `describeReason`, jamais reformulé. */
function buildDecisionPhrase(prediction: MatchDecisionOutput): string {
  if (prediction.decision.decision === 'BET') {
    if (prediction.market) {
      const bestSide = (Object.entries(prediction.market.price_edge) as Array<[string, number]>).sort((a, b) => b[1] - a[1])[0]
      if (bestSide && bestSide[1] > 0) {
        return `Value Bet détecté sur ${bestSide[0]} 2.5.`
      }
    }
    return 'Value Bet détecté.'
  }
  const [firstReason] = prediction.decision.decision_reason
  return firstReason ? `Pas de Value Bet actuellement. ${describeReason(firstReason)}` : 'Pas de Value Bet actuellement.'
}

/** Badge Value/No Value - JAMAIS indépendant de la décision globale du
 * moteur : le signe brut de `price_edge` seul ne suffit pas à afficher
 * "VALUE" (c'est précisément le type de sur-confiance identifié par
 * Phase D - edge apparent positif sans validation scientifique). Un badge
 * "VALUE" n'est donc affiché QUE si le moteur a réellement décidé BET
 * pour ce match - jamais une Value inventée côté présentation qui
 * contredirait la décision globale déjà affichée au-dessus. */
function isValueSide(decision: 'BET' | 'NO_BET', priceEdge: number): boolean {
  return decision === 'BET' && priceEdge > 0
}

function ValueBadge({ decision, priceEdge }: { decision: 'BET' | 'NO_BET'; priceEdge: number }) {
  const isValue = isValueSide(decision, priceEdge)
  return <span className={`badge ${isValue ? 'badge-bet' : 'badge-no_bet'}`}>{isValue ? 'VALUE' : 'NO VALUE'}</span>
}

/** Côté (Over/Under 2.5) que le modèle juge le plus probable pour CE match
 * - dérivé directement de `marketView.over.probability`/`under.probability`
 * (les deux sommant à 1 par construction, voir `buildPrimaryModelMarketView`),
 * jamais une nouvelle statistique. C'est une lecture de la probabilité déjà
 * affichée, PAS une recommandation de pari : la décision BET/NO_BET du
 * moteur reste strictement indépendante de ce seul critère (même principe
 * que le seuil mathématique de Value Bet déjà affiché par carte). */
function favoredSide(marketView: { over: SideView; under: SideView }): 'Over' | 'Under' {
  return marketView.over.probability >= marketView.under.probability ? 'Over' : 'Under'
}

function MarketBlock({
  label,
  side,
  marketOdds,
  priceEdge,
  decision,
  favored,
}: {
  label: string
  side: SideView
  marketOdds?: number
  priceEdge?: number
  decision: 'BET' | 'NO_BET'
  favored: boolean
}) {
  // "Pourquoi c'est intéressant" (section 6 de la demande) : UNIQUEMENT
  // affiché pour le côté réellement en Value (jamais pour NO VALUE, qui n'a
  // rien à expliquer) - une phrase factuelle qui ne fait que mettre en mots
  // les deux chiffres DÉJÀ affichés juste au-dessus (cote renseignée, cote
  // juste) - jamais un recalcul de `price_edge` lui-même. Le sens de la
  // comparaison ("plus"/"moins généreuse") est dérivé DIRECTEMENT de ces
  // deux mêmes chiffres (`marketOdds` vs `side.fairPrice`), jamais supposé
  // fixe : pour une donnée réelle et cohérente, `price_edge > 0` implique
  // mathématiquement `marketOdds > fairPrice` (même `model_prob` des deux
  // côtés du calcul backend, `value_engine.edge.expected_value`), mais la
  // phrase ne doit jamais AFFIRMER un sens qu'elle n'a pas elle-même vérifié
  // sur les valeurs réellement à l'écran.
  const showsValueExplanation = priceEdge !== undefined && isValueSide(decision, priceEdge) && marketOdds !== undefined
  const isOddsMoreGenerousThanFair = showsValueExplanation && marketOdds! > side.fairPrice

  return (
    <div className={`card value-bet-card${favored ? ' value-bet-card-favored' : ''}`}>
      <h3>
        {label}
        {favored && <span className="favored-badge">Favori du modèle</span>}
      </h3>
      <dl className="value-bet-stats">
        <div>
          <dt>Probabilité modèle</dt>
          <dd>{formatProbability(side.probability)}</dd>
        </div>
        <div>
          <dt>Cote juste</dt>
          <dd>{formatOdds(side.fairPrice)}</dd>
        </div>
        {marketOdds !== undefined && (
          <div>
            {/* "Renseignée" et non "actuelle" : cette valeur est TOUJOURS
                celle saisie par l'utilisateur dans le formulaire ci-dessous
                - l'API n'interroge jamais un bookmaker en direct et ne lit
                jamais de cote historique ici. Jamais laisser penser à un
                suivi de marché en temps réel. */}
            <dt>Cote renseignée</dt>
            <dd>{formatOdds(marketOdds)}</dd>
          </div>
        )}
      </dl>
      {/* Seuil MATHÉMATIQUE de Value Bet - rend explicite ce que le moteur
          calcule DÉJÀ (Niveau C, `fair_price = 1 / p_model`, AUCUN nouveau
          calcul ici) : `expected_value = p * odds - 1 > 0 ⟺ odds >
          fair_price` (`value_engine.edge.expected_value`, INCHANGÉ).
          Affiché INCONDITIONNELLEMENT (même avant toute saisie de cote) -
          c'est une propriété du seul `fair_price`, indépendante de
          `marketOdds`/`priceEdge`. Distingue EXPLICITEMENT ce seuil
          mathématique de la décision finale du moteur (Niveau F) : la
          phrase ne doit jamais laisser entendre que dépasser ce seuil
          déclenche un BET - `min_edge_threshold` reste `None` et
          `edge_threshold_gate` reste déclenché systématiquement, la
          décision affichée (NO_BET aujourd'hui) n'est jamais modifiée par
          ce texte, uniquement expliquée. */}
      <p className="hint value-threshold">
        Value Bet mathématique si la cote proposée dépasse {formatOdds(side.fairPrice)}. La décision du moteur reste
        indépendante de ce seul critère.
      </p>
      {priceEdge !== undefined ? (
        <>
          <ValueBadge decision={decision} priceEdge={priceEdge} />
          {showsValueExplanation && (
            <p className="hint value-explanation">
              Cote renseignée ({formatOdds(marketOdds!)}){' '}
              {isOddsMoreGenerousThanFair ? 'plus généreuse' : 'différente'} que la cote juste du modèle (
              {formatOdds(side.fairPrice)}).
            </p>
          )}
        </>
      ) : (
        <p className="hint">Entrez une cote de marché pour vérifier si une Value Bet est actuellement présente.</p>
      )}
    </div>
  )
}

function DecisionBlock({ prediction }: { prediction: MatchDecisionOutput }) {
  const decision = prediction.decision.decision
  // La toute première raison est déjà intégrée dans la phrase ci-dessus
  // (`buildDecisionPhrase`) - ne jamais la répéter ici. Les raisons
  // SUIVANTES (s'il y en a) sont listées en phrases lisibles, SANS le code
  // technique brut (ex. "AMBIGUOUS_COLLECTION_DAY") : ce niveau (NIVEAU 3 -
  // explication) doit rester compréhensible par un utilisateur non
  // technique. Le code brut n'est jamais supprimé de l'application - il
  // reste visible, pour chaque raison déclenchée, dans « Contrôles / Gates »
  // (NIVEAU 4 - détails techniques, voir AnalysisAccordions ci-dessous) où
  // il a sa place légitime.
  const [, ...otherReasons] = prediction.decision.decision_reason
  return (
    <div className="decision-hero">
      <span className={`decision-hero-pill decision-hero-pill-${decision.toLowerCase()}`}>{decision}</span>
      <div className="decision-meta">
        <p className="decision-phrase">{buildDecisionPhrase(prediction)}</p>
        {otherReasons.length > 0 && (
          <ul className="reason-list decision-reasons-secondary">
            {otherReasons.map((code) => (
              <li key={code}>{describeReason(code)}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

/** Détails de l'analyse : repliés par défaut, jamais masqués - le moteur
 * reste complet (Poisson, Dixon-Coles, XG, calibration, gates, paramètres),
 * uniquement déplacé derrière des sections secondaires. Réutilise les
 * mêmes composants que MatchDetail.tsx (ProbabilitiesTable/ModelsSummary/
 * MarketSection), jamais une seconde implémentation de ce rendu. */
function AnalysisAccordions({ prediction, matchId }: { prediction: MatchDecisionOutput; matchId: string }) {
  const triggeredGates = [...prediction.qualification.scientific_gates, ...prediction.qualification.operational_gates].filter(
    (gate) => gate.triggered,
  )

  return (
    <div className="audit-section">
      <h2>Détails de l'analyse</h2>

      <details className="audit-accordion">
        <summary>
          <span className="chevron" aria-hidden="true">
            ›
          </span>
          Probabilités détaillées par modèle
        </summary>
        <div className="audit-accordion-content">
          <ProbabilitiesTable
            models={prediction.models}
            calibration={prediction.calibration}
            pricing={prediction.pricing}
            primaryModel={prediction.primary_model}
          />
        </div>
      </details>

      <details className="audit-accordion">
        <summary>
          <span className="chevron" aria-hidden="true">
            ›
          </span>
          Modèles utilisés (Poisson / Dixon-Coles / XG)
        </summary>
        <div className="audit-accordion-content">
          <ModelsSummary models={prediction.models} primaryModel={prediction.primary_model} />
        </div>
      </details>

      <details className="audit-accordion">
        <summary>
          <span className="chevron" aria-hidden="true">
            ›
          </span>
          Données de marché
        </summary>
        <div className="audit-accordion-content">
          {prediction.market === null ? (
            <p className="state state-empty">Données de marché non fournies — aucun edge exploitable ne peut être affiché.</p>
          ) : (
            <MarketSection market={prediction.market} />
          )}
        </div>
      </details>

      <details className="audit-accordion">
        <summary>
          <span className="chevron" aria-hidden="true">
            ›
          </span>
          Qualification / calibration
        </summary>
        <div className="audit-accordion-content">
          <p>Discrimination du modèle principal : {prediction.qualification.discrimination_status}</p>
          <ul className="reason-list">
            {Object.entries(prediction.qualification.calibration_status).map(([threshold, status]) => (
              <li key={threshold}>
                Seuil {threshold} : {status}
              </li>
            ))}
          </ul>
          {prediction.qualification.data_quality.length > 0 && (
            <p>Qualité des données : {prediction.qualification.data_quality.join(', ')}</p>
          )}
        </div>
      </details>

      <details className="audit-accordion">
        <summary>
          <span className="chevron" aria-hidden="true">
            ›
          </span>
          Contrôles / Gates{triggeredGates.length > 0 ? ` (${triggeredGates.length})` : ''}
        </summary>
        <div className="audit-accordion-content">
          {triggeredGates.length === 0 ? (
            <p>Aucun contrôle déclenché.</p>
          ) : (
            <ul className="reason-list">
              {triggeredGates.map((gate) => (
                // Le code technique brut (ex. "EDGE_BELOW_THRESHOLD") est
                // affiché ICI, au niveau détails techniques - jamais masqué
                // (même principe que MatchDetail.tsx) - mais plus dans la
                // phrase de décision ci-dessus, qui reste lisible par un
                // utilisateur non technique (voir DecisionBlock).
                <li key={gate.name}>
                  {gate.failure_code && <code>{gate.failure_code}</code>} {gate.failure_code ? '— ' : ''}
                  {gate.reason}
                </li>
              ))}
            </ul>
          )}
        </div>
      </details>

      <details className="audit-accordion">
        <summary>
          <span className="chevron" aria-hidden="true">
            ›
          </span>
          Données utilisées
        </summary>
        <div className="audit-accordion-content">
          <ul className="reason-list">
            <li>
              <code>match_id</code> (catalogue) : {matchId}
            </li>
            <li>
              <code>engine_version</code> : {prediction.engine_version}
            </li>
            {Object.entries(prediction.parameters_snapshot).map(([key, value]) => (
              <li key={key}>
                <code>{key}</code> : {formatParamValue(value)}
              </li>
            ))}
          </ul>
        </div>
      </details>
    </div>
  )
}

export function AnalyzeMatch() {
  const [competition, setCompetition] = useState('')
  const [season, setSeason] = useState('')
  const [searchState, setSearchState] = useState<SearchState>({ status: 'idle' })

  const [homeTeam, setHomeTeam] = useState('')
  const [awayTeam, setAwayTeam] = useState('')
  const [selectedMatchId, setSelectedMatchId] = useState('')

  const [activeMatch, setActiveMatch] = useState<MatchResponse | null>(null)
  const [predictionState, setPredictionState] = useState<PredictionState | null>(null)
  const [overOdds, setOverOdds] = useState('')
  const [underOdds, setUnderOdds] = useState('')
  const [appliedOdds, setAppliedOdds] = useState<{ over_2_5: number; under_2_5: number } | undefined>(undefined)
  const [oddsFormError, setOddsFormError] = useState<string | null>(null)

  // Garde-fou anti-course (identique en esprit au `cancelled` de
  // MatchDetail.tsx, adapté à un appel impératif plutôt qu'un useEffect) :
  // `runPrediction` est déclenché depuis plusieurs gestionnaires d'événement
  // (analyse initiale, application/retrait de cote) - sans ce compteur, une
  // réponse LENTE d'un match/cote déjà abandonné pourrait arriver APRÈS une
  // réponse plus rapide d'une analyse plus récente et écraser silencieusement
  // la décision affichée par celle, périmée, du match précédent. Seule la
  // réponse dont l'identifiant correspond encore à la dernière requête émise
  // est jamais appliquée à l'état affiché.
  const predictionRequestIdRef = useRef(0)

  // Chargement AUTOMATIQUE des matchs dès que compétition ET saison sont
  // choisies - plus de bouton "Rechercher les matchs" à cliquer séparément :
  // le parcours devient directement compétition → saison → match →
  // analyser (audit parcours), sans étape intermédiaire qui ressemble à la
  // soumission d'un formulaire technique. Garde-fou anti-course identique en
  // esprit à `MatchDetail.tsx` (`cancelled`) : un changement rapide de
  // compétition/saison avant la fin d'une requête précédente ne doit jamais
  // appliquer une liste de matchs qui ne correspond plus à la sélection
  // actuelle.
  useEffect(() => {
    setHomeTeam('')
    setAwayTeam('')
    setSelectedMatchId('')
    resetActiveAnalysis()

    if (!competition || !season) {
      setSearchState({ status: 'idle' })
      return
    }

    let cancelled = false
    setSearchState({ status: 'loading' })
    getMatches(competition, season)
      .then((matches) => {
        if (!cancelled) setSearchState({ status: 'ready', matches })
      })
      .catch((err) => {
        if (!cancelled) setSearchState({ status: 'error', message: err instanceof ApiError ? err.detail : String(err) })
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [competition, season])

  const matches = searchState.status === 'ready' ? searchState.matches : []
  const homeTeams = useMemo(() => Array.from(new Set(matches.map((m) => m.home_team))).sort((a, b) => a.localeCompare(b)), [matches])
  const awayTeams = useMemo(
    () =>
      Array.from(new Set(matches.filter((m) => m.home_team === homeTeam).map((m) => m.away_team))).sort((a, b) => a.localeCompare(b)),
    [matches, homeTeam],
  )
  // Un couple domicile/extérieur résolu dans le catalogue réel - jamais un
  // match libre non vérifié (voir contrainte section 2 de la demande).
  const candidates = useMemo(() => matches.filter((m) => m.home_team === homeTeam && m.away_team === awayTeam), [matches, homeTeam, awayTeam])
  const resolvedMatch = candidates.length === 1 ? candidates[0] : (candidates.find((m) => m.match_id === selectedMatchId) ?? null)
  // EXTENSION fixtures futures 2026/27 : règle produit UNIQUE (jamais
  // dupliquée localement) - une fixture n'est analysable que si
  // `kickoff_utc` est connu (voir ../api/fixtureTiming.ts).
  const resolvedMatchAvailability = resolvedMatch ? analysisAvailability(resolvedMatch) : null

  function resetActiveAnalysis() {
    // Invalide toute requête de prédiction encore en vol : si elle
    // aboutit malgré tout, `runPrediction` la reconnaîtra comme périmée
    // (voir `predictionRequestIdRef`) et l'ignorera.
    predictionRequestIdRef.current += 1
    setActiveMatch(null)
    setPredictionState(null)
    setOverOdds('')
    setUnderOdds('')
    setAppliedOdds(undefined)
    setOddsFormError(null)
  }

  function handleHomeTeamChange(value: string) {
    setHomeTeam(value)
    setAwayTeam('')
    setSelectedMatchId('')
    resetActiveAnalysis()
  }

  function handleAwayTeamChange(value: string) {
    setAwayTeam(value)
    setSelectedMatchId('')
    resetActiveAnalysis()
  }

  function runPrediction(match: MatchResponse, odds?: { over_2_5: number; under_2_5: number }) {
    // EXTENSION fixtures futures 2026/27 : une fixture B/C (kickoff_utc
    // absent) n'est jamais envoyée à `run_prediction` - le bouton
    // "Analyser" est déjà désactivé pour ce cas (voir le rendu
    // ci-dessous), garde redondante pour ne jamais dépendre uniquement du
    // rendu désactivé.
    const availability = analysisAvailability(match)
    if (!availability.available) {
      predictionRequestIdRef.current += 1
      setPredictionState({ status: 'unavailable', message: availability.reason })
      return
    }
    const requestId = ++predictionRequestIdRef.current
    setPredictionState({ status: 'loading' })
    getPrediction(match.match_id, match.competition, match.season, odds)
      .then((prediction) => {
        if (predictionRequestIdRef.current === requestId) setPredictionState({ status: 'ready', prediction })
      })
      .catch((err) => {
        if (predictionRequestIdRef.current !== requestId) return
        // Garde défensive (ne devrait pas se produire, voir ci-dessus) :
        // un HTTP 409 reste traité comme un cas "indisponible" propre,
        // jamais comme une erreur serveur générique.
        if (err instanceof ApiError && err.status === 409) {
          setPredictionState({ status: 'unavailable', message: err.detail })
        } else {
          setPredictionState({ status: 'error', message: err instanceof ApiError ? err.detail : String(err) })
        }
      })
  }

  function handleAnalyze() {
    // Garde explicite indépendante du rendu (le `disabled` du bouton suffit
    // déjà en pratique, mais deux clics synchrones avant le prochain rendu -
    // par ex. un double-clic très rapide - ne doivent jamais déclencher deux
    // requêtes de prédiction concurrentes pour le même match).
    if (!resolvedMatch || predictionState?.status === 'loading') return
    setActiveMatch(resolvedMatch)
    setAppliedOdds(undefined)
    setOverOdds('')
    setUnderOdds('')
    setOddsFormError(null)
    runPrediction(resolvedMatch)
  }

  function handleOddsSubmit(event: FormEvent) {
    event.preventDefault()
    if (!activeMatch) return
    const over = Number(overOdds)
    const under = Number(underOdds)
    if (!overOdds.trim() || !underOdds.trim() || Number.isNaN(over) || Number.isNaN(under)) {
      setOddsFormError('Renseignez les deux cotes (Over 2.5 et Under 2.5) pour les appliquer - les deux sont requises ensemble.')
      return
    }
    setOddsFormError(null)
    const odds = { over_2_5: over, under_2_5: under }
    setAppliedOdds(odds)
    runPrediction(activeMatch, odds)
  }

  function handleClearOdds() {
    if (!activeMatch) return
    setOverOdds('')
    setUnderOdds('')
    setOddsFormError(null)
    setAppliedOdds(undefined)
    runPrediction(activeMatch)
  }

  const marketView = predictionState?.status === 'ready' ? buildPrimaryModelMarketView(predictionState.prediction) : null
  const market = predictionState?.status === 'ready' ? predictionState.prediction.market : null

  return (
    <div className="page analyze-match">
      <h1>Analyser un match</h1>
      <p className="hint">
        Choisissez un match réel du catalogue puis lancez l'analyse - le moteur quantitatif (Poisson, Dixon-Coles, XG,
        calibration, gates) s'exécute sans modification.
      </p>

      <section className="card">
        <h2>1. Choisir le match</h2>
        <CompetitionTabs value={competition} onChange={setCompetition} />
        <div className="filters">
          <label>
            Saison
            <select value={season} onChange={(e) => setSeason(e.target.value)}>
              <option value="">— Choisir —</option>
              {SEASON_OPTIONS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        {searchState.status === 'idle' && (
          <EmptyState message="Choisissez une compétition et une saison pour voir les matchs disponibles." />
        )}
        {searchState.status === 'loading' && <LoadingState label="Chargement des matchs..." />}
        {searchState.status === 'error' && <ErrorState message={searchState.message} />}
        {searchState.status === 'ready' && matches.length === 0 && (
          <EmptyState message="Aucun match disponible pour cette compétition et cette saison." />
        )}

        {searchState.status === 'ready' && matches.length > 0 && (
          <>
            <div className="filters">
              <label>
                Équipe à domicile
                <select value={homeTeam} onChange={(e) => handleHomeTeamChange(e.target.value)}>
                  <option value="">— Choisir —</option>
                  {homeTeams.map((team) => (
                    <option key={team} value={team}>
                      {team}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Équipe à l'extérieur
                <select value={awayTeam} onChange={(e) => handleAwayTeamChange(e.target.value)} disabled={!homeTeam}>
                  <option value="">— Choisir —</option>
                  {awayTeams.map((team) => (
                    <option key={team} value={team}>
                      {team}
                    </option>
                  ))}
                </select>
              </label>
              {candidates.length > 1 && (
                <label>
                  Date
                  <select value={selectedMatchId} onChange={(e) => setSelectedMatchId(e.target.value)}>
                    <option value="">— Choisir —</option>
                    {candidates.map((m) => (
                      <option key={m.match_id} value={m.match_id}>
                        {describeMatchDateTime(m)}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>
            {homeTeam && awayTeam && candidates.length === 0 && (
              <EmptyState message="Aucun match trouvé dans le catalogue pour cette combinaison domicile/extérieur." />
            )}
            {/* Résumé humain du match choisi, affiché DÈS la résolution -
                donc AVANT même de cliquer "Analyser" (bullet 7 de l'audit
                parcours) : jamais d'identifiant technique, uniquement les
                équipes et des libellés de compétition/saison déjà lisibles.
                EXTENSION fixtures futures 2026/27 : "Match à venir" pour une
                fixture non jouée, jamais confondu avec un résultat déjà
                connu - et un rappel explicite quand l'analyse n'est pas
                encore possible (heure/UTC non confirmée). */}
            {resolvedMatch && (
              <>
                <p className="match-preview">
                  <span className="match-summary-teams">
                    {resolvedMatch.home_team} – {resolvedMatch.away_team}
                  </span>
                  <span className="hint">
                    {competitionLabel(resolvedMatch.competition)} · {seasonLabel(resolvedMatch.season)} ·{' '}
                    {describeMatchDateTime(resolvedMatch)}
                    {!resolvedMatch.is_played && ' · Match à venir'}
                  </span>
                </p>
                {resolvedMatchAvailability && !resolvedMatchAvailability.available && (
                  <EmptyState message={resolvedMatchAvailability.reason} />
                )}
                {resolvedMatchAvailability?.available && resolvedMatchAvailability.estimated && (
                  <p className="hint kickoff-estimated-hint">
                    Heure de coup d'envoi estimée (conversion CET/CEST depuis l'heure locale publiée) - non confirmée
                    par une seconde source indépendante.
                  </p>
                )}
              </>
            )}
            <button
              type="button"
              className="button-primary"
              disabled={!resolvedMatch || !resolvedMatchAvailability?.available || predictionState?.status === 'loading'}
              onClick={handleAnalyze}
            >
              {predictionState?.status === 'loading' ? 'Analyse en cours…' : 'Analyser le match'}
            </button>
          </>
        )}
      </section>

      {activeMatch && (
        <>
          <section className="card card-elevated">
            <h2>2. Décision</h2>
            {/* Le match reste identifiable sans avoir à remonter à l'étape 1,
                même en faisant défiler la page jusqu'au résultat. */}
            <p className="match-summary-teams decision-match-name">
              {activeMatch.home_team} – {activeMatch.away_team}
            </p>
            {predictionState?.status === 'loading' && <LoadingState label="Analyse en cours..." />}
            {predictionState?.status === 'error' && <ErrorState message={predictionState.message} />}
            {predictionState?.status === 'unavailable' && <EmptyState message={predictionState.message} />}
            {predictionState?.status === 'ready' && (
              <div className="fade-in">
                {predictionState.prediction.kickoff_utc_estimated && (
                  <p className="hint kickoff-estimated-hint">
                    Analyse basée sur une heure de coup d'envoi estimée (conversion CET/CEST depuis l'heure locale
                    publiée) - non confirmée par une seconde source indépendante.
                  </p>
                )}
                <DecisionBlock prediction={predictionState.prediction} />

                {marketView === null ? (
                  <EmptyState message="Probabilités indisponibles pour ce match (historique de calibration insuffisant) - aucune donnée de Value Bet ne peut être affichée." />
                ) : (
                  <>
                    <h2>Value Bet</h2>
                    {/* Reponse explicite a "sur quel marche ?" - le seul marche
                        Over/Under pour lequel une cote reelle existe dans le
                        corpus (voir MARKET_THRESHOLD en tete de fichier), jamais
                        seulement implicite via les deux titres de carte en dessous. */}
                    <p className="market-analyzed">
                      Marché analysé : <strong>Over/Under 2.5 buts</strong>
                    </p>
                    {/* Synthèse immédiate : quel côté le modèle favorise pour
                        CE match - simple lecture de la probabilité déjà
                        affichée par carte ci-dessous (over.probability vs
                        under.probability, qui somment à 1), jamais une
                        nouvelle statistique ni une recommandation de pari -
                        la décision BET/NO_BET au-dessus reste la seule
                        décision du moteur. */}
                    <p className="favored-side-summary">
                      Pronostic du modèle :{' '}
                      <strong>
                        {favoredSide(marketView) === 'Over' ? 'OVER' : 'UNDER'} 2.5 (
                        {formatProbability(favoredSide(marketView) === 'Over' ? marketView.over.probability : marketView.under.probability)}
                        )
                      </strong>
                    </p>
                    {extractMinEdgeThreshold(predictionState.prediction.parameters_snapshot) === null && (
                      // Fait valable pour le match entier (pas un côté en particulier) :
                      // affiché UNE SEULE FOIS ici, jamais dupliqué par carte Over/Under.
                      <p className="hint">
                        Le moteur ne dispose pas encore d'un seuil d'edge minimal validé scientifiquement : aucune cote
                        minimale de Value ne peut donc être affichée (voir « Contrôles / Gates » ci-dessous).
                      </p>
                    )}
                    <div className="value-bet-grid">
                      <MarketBlock
                        label="Over 2.5"
                        side={marketView.over}
                        marketOdds={market?.market_odds['Over']}
                        priceEdge={market?.price_edge['Over']}
                        decision={predictionState.prediction.decision.decision}
                        favored={favoredSide(marketView) === 'Over'}
                      />
                      <MarketBlock
                        label="Under 2.5"
                        side={marketView.under}
                        marketOdds={market?.market_odds['Under']}
                        priceEdge={market?.price_edge['Under']}
                        decision={predictionState.prediction.decision.decision}
                        favored={favoredSide(marketView) === 'Under'}
                      />
                    </div>
                  </>
                )}

                <h3>Cote de marché</h3>
                <p className="hint">
                  L'API n'invente jamais de cote : par défaut l'analyse est calculée sans marché. Renseignez les deux
                  cotes réelles (Over 2.5 / Under 2.5) pour vérifier la Value Bet avec ce marché.
                </p>
                <form className="filters" onSubmit={handleOddsSubmit}>
                  <label>
                    Cote Over 2.5
                    <input
                      type="number"
                      step="0.01"
                      min="1.01"
                      value={overOdds}
                      onChange={(e) => setOverOdds(e.target.value)}
                      placeholder="ex. 1.90"
                    />
                  </label>
                  <label>
                    Cote Under 2.5
                    <input
                      type="number"
                      step="0.01"
                      min="1.01"
                      value={underOdds}
                      onChange={(e) => setUnderOdds(e.target.value)}
                      placeholder="ex. 1.90"
                    />
                  </label>
                  <button type="submit" className="button-primary">
                    Appliquer les cotes
                  </button>
                  {appliedOdds && (
                    <button type="button" onClick={handleClearOdds}>
                      Retirer les cotes
                    </button>
                  )}
                </form>
                {oddsFormError && <ErrorState message={oddsFormError} />}

                <AnalysisAccordions prediction={predictionState.prediction} matchId={activeMatch.match_id} />
              </div>
            )}
          </section>
        </>
      )}
    </div>
  )
}
