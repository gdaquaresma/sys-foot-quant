/**
 * Détail d'un match (Phase UI-2-D) + section prédiction (Phase
 * "intégration du moteur dans le site") - consomme GET /matches/{match_id}
 * et GET /matches/{match_id}/prediction via le client API centralisé.
 *
 * GARDE-FOU EXPLICITE : cette page n'effectue AUCUN calcul de probabilité,
 * d'edge ou de décision - elle affiche exclusivement les valeurs telles
 * que renvoyées par l'API (mise en forme de présentation uniquement :
 * dates, pourcentages, arrondis d'affichage - jamais une nouvelle valeur
 * statistique). La décision BET/NO_BET et sa/ses raison(s) sont affichées
 * telles que produites par le moteur, jamais transformées.
 */
import { type FormEvent, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError, getMatch, getPrediction } from '../api/client'
import type { CalibratedGoalDistribution, MarketComparisonResult, MatchDecisionOutput, MatchResponse, ModelPrediction, PricingResult } from '../api/types'
import { ErrorState, LoadingState } from '../components/StateViews'

type LoadState =
  | { status: 'loading' }
  | { status: 'invalid-params' }
  | { status: 'not-found'; message: string }
  | { status: 'error'; message: string }
  | { status: 'ready'; match: MatchResponse }

type PredictionState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; prediction: MatchDecisionOutput }

function formatKickoff(iso: string): string {
  try {
    return new Intl.DateTimeFormat('fr-FR', { dateStyle: 'full', timeStyle: 'short' }).format(new Date(iso))
  } catch {
    return iso
  }
}

function formatProbability(value: number): string {
  return `${(value * 100).toFixed(1)} %`
}

function formatOdds(value: number): string {
  return value.toFixed(2)
}

function formatParamValue(value: unknown): string {
  if (value === null || value === undefined) return 'non fixé'
  if (typeof value === 'boolean') return value ? 'oui' : 'non'
  if (typeof value === 'number') return String(value)
  return JSON.stringify(value)
}

/** Libellés lisibles des codes de raison stables du moteur
 * (final_engine/reason_codes.py, INCHANGE) - un texte d'affichage par
 * code connu, jamais une réinterprétation de sa portée scientifique. Un
 * code non répertorié reste affiché tel quel (son code brut), jamais
 * masqué. */
const DECISION_REASON_LABELS: Record<string, string> = {
  INSUFFICIENT_HISTORY: "Historique d'entraînement insuffisant pour ce match.",
  AMBIGUOUS_COLLECTION_DAY: 'Jour de collecte des données ambigu (lundi/mardi/vendredi exclu).',
  MARKET_DATA_UNAVAILABLE: 'Aucune cote de marché disponible pour ce match.',
  DISTRIBUTION_INCONSISTENT: 'Incohérence interne de la distribution de buts (anomalie technique).',
  INSUFFICIENT_CONFIDENCE_CALIBRATION_ZONE: 'Confiance de calibration insuffisante pour ce seuil.',
  DISCRIMINATION_NOT_DEMONSTRATED: "Pouvoir discriminant du modèle non démontré.",
  EDGE_BELOW_THRESHOLD: "Aucun seuil d'edge minimal validé scientifiquement (protection opérationnelle du moteur).",
  UNCERTAINTY_TOO_HIGH: 'Incertitude trop élevée sur la prédiction.',
  MARKET_NOT_USABLE: 'Marché non utilisable pour cette décision.',
  OTHER_BLOCKING_CONDITION: 'Autre condition bloquante détectée par le moteur.',
}

function describeReason(code: string): string {
  return DECISION_REASON_LABELS[code] ?? 'Code de raison non documenté côté interface.'
}

/** Badge discret signalant le `primary_model` (donnée déjà fournie par
 * l'API, jamais déduite ici) - distinction purement visuelle entre le
 * modèle principal et les modèles de contrôle, aucune donnée modifiée. */
function PrimaryModelBadge() {
  return (
    <span className="model-badge-primary" aria-label="Modèle principal">
      Principal
    </span>
  )
}

function ModelsSummary({ models, primaryModel }: { models: Record<string, ModelPrediction | null>; primaryModel: string }) {
  return (
    <ul className="reason-list">
      {Object.entries(models).map(([key, model]) => (
        <li key={key}>
          {model === null ? (
            <>
              <strong>{key}</strong>
              {key === primaryModel && <PrimaryModelBadge />} — indisponible (historique d'entraînement insuffisant).
            </>
          ) : (
            <>
              <strong>{key}</strong>
              {key === primaryModel && <PrimaryModelBadge />} — λ={model.lam.toFixed(3)}, μ={model.mu.toFixed(3)}
              {model.rho !== null && <>, ρ={model.rho.toFixed(3)}</>}, entraîné sur {model.n_train_matches} matchs.
            </>
          )}
        </li>
      ))}
    </ul>
  )
}

function ProbabilitiesTable({
  models,
  calibration,
  pricing,
  primaryModel,
}: {
  models: Record<string, ModelPrediction | null>
  calibration: Record<string, CalibratedGoalDistribution>
  pricing: Record<string, PricingResult | null>
  primaryModel: string
}) {
  return (
    <table className="table">
      <thead>
        <tr>
          <th>Modèle</th>
          <th>Seuil de buts (Over/Under)</th>
          <th>Probabilité (Under le seuil)</th>
          <th>Cote juste du modèle</th>
        </tr>
      </thead>
      <tbody>
        {Object.keys(models).map((key) => {
          const modelCalibration = calibration[key]
          const modelPricing = pricing[key]
          const modelLabel = (
            <>
              <span>{key}</span>
              {key === primaryModel && <PrimaryModelBadge />}
            </>
          )
          if (!modelCalibration?.probabilities) {
            return (
              <tr key={key}>
                <td>{modelLabel}</td>
                <td colSpan={3}>Probabilités indisponibles (historique de calibration insuffisant).</td>
              </tr>
            )
          }
          const thresholds = Object.keys(modelCalibration.probabilities)
          return thresholds.map((threshold, index) => (
            <tr key={`${key}-${threshold}`}>
              {index === 0 && <td rowSpan={thresholds.length}>{modelLabel}</td>}
              <td>{threshold}</td>
              <td>{formatProbability(modelCalibration.probabilities![threshold])}</td>
              <td>{modelPricing ? formatOdds(modelPricing.fair_price[threshold]) : '—'}</td>
            </tr>
          ))
        })}
      </tbody>
    </table>
  )
}

function MarketSection({ market }: { market: MarketComparisonResult }) {
  return (
    <table className="table">
      <thead>
        <tr>
          <th>Marché</th>
          <th>Cote fournie</th>
          <th>Probabilité implicite (normalisée)</th>
          <th>Edge brut</th>
          <th>Edge sur cote</th>
        </tr>
      </thead>
      <tbody>
        {Object.keys(market.market_odds).map((side) => (
          <tr key={side}>
            <td>{side}</td>
            <td>{formatOdds(market.market_odds[side])}</td>
            <td>{formatProbability(market.market_implied_probability_normalized[side])}</td>
            <td>{formatProbability(market.raw_edge[side])}</td>
            <td>{formatProbability(market.price_edge[side])}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function PredictionSection({ prediction }: { prediction: MatchDecisionOutput }) {
  const triggeredGates = [...prediction.qualification.scientific_gates, ...prediction.qualification.operational_gates].filter(
    (gate) => gate.triggered,
  )
  const decision = prediction.decision.decision

  return (
    <>
      {/* --- Synthèse : ce qu'il faut comprendre immédiatement --------- */}

      <div className="decision-hero">
        <span className={`decision-hero-pill decision-hero-pill-${decision.toLowerCase()}`}>{decision}</span>
        <div className="decision-meta">
          <p className="decision-meta-line">
            Modèle principal : <strong>{prediction.primary_model}</strong> — moteur {prediction.engine_version}
          </p>
          <p className="decision-meta-line hint">Décision calculée le {formatKickoff(`${prediction.timestamp_decision}Z`)}</p>
        </div>
      </div>

      <h3>Raison(s) de la décision</h3>
      {prediction.decision.decision_reason.length === 0 ? (
        <p className="state state-empty">Aucune raison de blocage (BET).</p>
      ) : (
        <ul className="reason-list">
          {prediction.decision.decision_reason.map((code) => (
            <li key={code}>
              <code>{code}</code> — <span>{describeReason(code)}</span>
            </li>
          ))}
        </ul>
      )}

      <h3>Modèles utilisés</h3>
      <ModelsSummary models={prediction.models} primaryModel={prediction.primary_model} />

      <h3>Probabilités</h3>
      <ProbabilitiesTable
        models={prediction.models}
        calibration={prediction.calibration}
        pricing={prediction.pricing}
        primaryModel={prediction.primary_model}
      />

      <h3>Données de marché</h3>
      {prediction.market === null ? (
        <p className="state state-empty">Données de marché non fournies — aucun edge exploitable ne peut être affiché.</p>
      ) : (
        <div className="fade-in">
          <MarketSection market={prediction.market} />
        </div>
      )}

      {/* --- Détails d'audit : repliés par défaut, jamais masqués ------ */}

      <div className="audit-section">
        <h2>Détails d'audit</h2>

        <details className="audit-accordion">
          <summary>
            <span className="chevron" aria-hidden="true">
              ›
            </span>
            Contrôles déclenchés{triggeredGates.length > 0 ? ` (${triggeredGates.length})` : ''}
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
            Paramètres du moteur
          </summary>
          <div className="audit-accordion-content">
            <ul className="reason-list">
              {Object.entries(prediction.parameters_snapshot).map(([key, value]) => (
                <li key={key}>
                  <code>{key}</code> : {formatParamValue(value)}
                </li>
              ))}
            </ul>
          </div>
        </details>
      </div>
    </>
  )
}

export function MatchDetail() {
  const { competition, season, matchId } = useParams()
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const [predictionState, setPredictionState] = useState<PredictionState>({ status: 'loading' })
  const [overOdds, setOverOdds] = useState('')
  const [underOdds, setUnderOdds] = useState('')
  const [appliedOdds, setAppliedOdds] = useState<{ over_2_5: number; under_2_5: number } | undefined>(undefined)
  const [oddsFormError, setOddsFormError] = useState<string | null>(null)

  useEffect(() => {
    if (!competition || !season || !matchId) {
      setState({ status: 'invalid-params' })
      return
    }
    let cancelled = false
    setState({ status: 'loading' })
    getMatch(matchId, competition, season)
      .then((match) => {
        if (!cancelled) setState({ status: 'ready', match })
      })
      .catch((err) => {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 404) {
          setState({ status: 'not-found', message: err.detail })
        } else {
          setState({ status: 'error', message: err instanceof ApiError ? err.detail : String(err) })
        }
      })
    return () => {
      cancelled = true
    }
  }, [competition, season, matchId])

  useEffect(() => {
    if (state.status !== 'ready' || !competition || !season || !matchId) return
    let cancelled = false
    setPredictionState({ status: 'loading' })
    getPrediction(matchId, competition, season, appliedOdds)
      .then((prediction) => {
        if (!cancelled) setPredictionState({ status: 'ready', prediction })
      })
      .catch((err) => {
        if (!cancelled) setPredictionState({ status: 'error', message: err instanceof ApiError ? err.detail : String(err) })
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.status, competition, season, matchId, appliedOdds])

  function handleOddsSubmit(event: FormEvent) {
    event.preventDefault()
    const over = Number(overOdds)
    const under = Number(underOdds)
    if (!overOdds.trim() || !underOdds.trim() || Number.isNaN(over) || Number.isNaN(under)) {
      setOddsFormError('Renseignez les deux cotes (Over 2.5 et Under 2.5) pour les appliquer - les deux sont requises ensemble.')
      return
    }
    setOddsFormError(null)
    setAppliedOdds({ over_2_5: over, under_2_5: under })
  }

  function handleClearOdds() {
    setOverOdds('')
    setUnderOdds('')
    setOddsFormError(null)
    setAppliedOdds(undefined)
  }

  const backLink =
    competition && season ? `/matches?competition=${encodeURIComponent(competition)}&season=${encodeURIComponent(season)}` : '/matches'

  return (
    <div className="page">
      <h1>Détail du match</h1>
      <p>
        <Link to={backLink}>← Retour à l'explorateur</Link>
      </p>

      {state.status === 'loading' && <LoadingState label="Chargement du match..." />}
      {state.status === 'invalid-params' && <ErrorState message="Paramètres de route invalides (compétition, saison ou identifiant de match manquant)." />}
      {state.status === 'not-found' && <ErrorState message={state.message} />}
      {state.status === 'error' && <ErrorState message={state.message} />}

      {state.status === 'ready' && (
        <>
          <section className="card">
            <h2>
              {state.match.home_team} – {state.match.away_team}
            </h2>
            <p>Compétition : {state.match.competition}</p>
            <p>Saison : {state.match.season}</p>
            <p>Coup d'envoi : {formatKickoff(state.match.kickoff_utc)}</p>
            <p>Statut : {state.match.is_played ? 'Joué' : 'À venir'}</p>
            <p>Identifiant : {state.match.match_id}</p>
          </section>

          <section className="card">
            <h2>Cotes de marché</h2>
            <p className="hint">
              L'API n'invente jamais de cote : par défaut la prédiction est calculée sans marché. Renseignez les deux
              cotes réelles (Over 2.5 / Under 2.5) ci-dessous pour recalculer la prédiction avec ce marché.
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
              <button type="submit">Appliquer les cotes</button>
              {appliedOdds && (
                <button type="button" onClick={handleClearOdds}>
                  Retirer les cotes
                </button>
              )}
            </form>
            {oddsFormError && <ErrorState message={oddsFormError} />}
          </section>

          <section className="card card-elevated">
            <h2>Prédiction</h2>
            {predictionState.status === 'loading' && <LoadingState label="Calcul de la prédiction..." />}
            {predictionState.status === 'error' && <ErrorState message={predictionState.message} />}
            {predictionState.status === 'ready' && (
              <div className="fade-in">
                <PredictionSection prediction={predictionState.prediction} />
              </div>
            )}
          </section>
        </>
      )}
    </div>
  )
}
