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
 */
import { type FormEvent, useMemo, useState } from 'react'
import { ApiError, getMatches, getPrediction } from '../api/client'
import type { MatchDecisionOutput, MatchResponse } from '../api/types'
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

/** Phrase humaine de synthèse - recompose la décision/les raisons/l'edge
 * déjà produits par le moteur, n'invente aucune donnée. */
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
  return 'Pas de Value Bet actuellement.'
}

function ValueBadge({ priceEdge }: { priceEdge: number }) {
  const isValue = priceEdge > 0
  return <span className={`badge ${isValue ? 'badge-bet' : 'badge-no_bet'}`}>{isValue ? 'VALUE' : 'NO VALUE'}</span>
}

function MarketBlock({
  label,
  side,
  marketOdds,
  priceEdge,
}: {
  label: string
  side: SideView
  marketOdds?: number
  priceEdge?: number
}) {
  return (
    <div className="card value-bet-card">
      <h3>{label}</h3>
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
            <dt>Cote actuelle</dt>
            <dd>{formatOdds(marketOdds)}</dd>
          </div>
        )}
        <div>
          <dt>Value à partir de</dt>
          <dd>{formatOdds(side.fairPrice)}</dd>
        </div>
      </dl>
      {priceEdge !== undefined ? (
        <ValueBadge priceEdge={priceEdge} />
      ) : (
        <p className="hint">Entrez une cote de marché pour vérifier si une Value Bet est actuellement présente.</p>
      )}
    </div>
  )
}

function DecisionBlock({ prediction }: { prediction: MatchDecisionOutput }) {
  const decision = prediction.decision.decision
  return (
    <div className="decision-hero">
      <span className={`decision-hero-pill decision-hero-pill-${decision.toLowerCase()}`}>{decision}</span>
      <div className="decision-meta">
        <p className="decision-phrase">{buildDecisionPhrase(prediction)}</p>
        {prediction.decision.decision_reason.length > 0 && (
          <ul className="reason-list decision-reasons-secondary">
            {prediction.decision.decision_reason.map((code) => (
              <li key={code}>
                <code>{code}</code> — <span>{describeReason(code)}</span>
              </li>
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
                <li key={gate.name}>{gate.reason}</li>
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

  async function handleSearchSubmit(event: FormEvent) {
    event.preventDefault()
    if (!competition.trim() || !season.trim()) return
    setSearchState({ status: 'loading' })
    setHomeTeam('')
    setAwayTeam('')
    setSelectedMatchId('')
    setActiveMatch(null)
    setPredictionState(null)
    try {
      const matches = await getMatches(competition.trim(), season.trim())
      setSearchState({ status: 'ready', matches })
    } catch (err) {
      setSearchState({ status: 'error', message: err instanceof ApiError ? err.detail : String(err) })
    }
  }

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

  function resetActiveAnalysis() {
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
    setPredictionState({ status: 'loading' })
    getPrediction(match.match_id, match.competition, match.season, odds)
      .then((prediction) => setPredictionState({ status: 'ready', prediction }))
      .catch((err) => setPredictionState({ status: 'error', message: err instanceof ApiError ? err.detail : String(err) }))
  }

  function handleAnalyze() {
    if (!resolvedMatch) return
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
        <form className="filters" onSubmit={handleSearchSubmit}>
          <label>
            Compétition
            <input type="text" value={competition} onChange={(e) => setCompetition(e.target.value)} placeholder="identifiant technique" required />
          </label>
          <label>
            Saison
            <input type="text" value={season} onChange={(e) => setSeason(e.target.value)} placeholder="identifiant technique" required />
          </label>
          <button type="submit" className="button-primary">
            Rechercher les matchs
          </button>
        </form>

        {searchState.status === 'idle' && (
          <EmptyState message="Renseignez une compétition et une saison (identifiants techniques réels) pour charger les matchs disponibles." />
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
                        {formatKickoff(m.kickoff_utc)}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>
            {homeTeam && awayTeam && candidates.length === 0 && (
              <EmptyState message="Aucun match trouvé dans le catalogue pour cette combinaison domicile/extérieur." />
            )}
            <button type="button" className="button-primary" disabled={!resolvedMatch} onClick={handleAnalyze}>
              Analyser le match
            </button>
          </>
        )}
      </section>

      {activeMatch && (
        <>
          <section className="card match-summary">
            <p className="match-summary-teams">
              {activeMatch.home_team} – {activeMatch.away_team}
            </p>
            <p className="hint">
              {activeMatch.competition} · {formatKickoff(activeMatch.kickoff_utc)}
            </p>
          </section>

          <section className="card card-elevated">
            <h2>2. Décision</h2>
            {predictionState?.status === 'loading' && <LoadingState label="Analyse en cours..." />}
            {predictionState?.status === 'error' && <ErrorState message={predictionState.message} />}
            {predictionState?.status === 'ready' && (
              <div className="fade-in">
                <DecisionBlock prediction={predictionState.prediction} />

                {marketView === null ? (
                  <EmptyState message="Probabilités indisponibles pour ce match (historique de calibration insuffisant) - aucune donnée de Value Bet ne peut être affichée." />
                ) : (
                  <>
                    <h2>Value Bet</h2>
                    <div className="value-bet-grid">
                      <MarketBlock
                        label="Over 2.5"
                        side={marketView.over}
                        marketOdds={market?.market_odds['Over']}
                        priceEdge={market?.price_edge['Over']}
                      />
                      <MarketBlock
                        label="Under 2.5"
                        side={marketView.under}
                        marketOdds={market?.market_odds['Under']}
                        priceEdge={market?.price_edge['Under']}
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
