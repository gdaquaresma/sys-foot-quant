import { useEffect, useMemo, useState } from 'react'
import { competitionLabel } from '../api/catalog'
import { ApiError, getShadowJournal } from '../api/client'
import type { ShadowObservation } from '../api/types'
import { CompetitionTabs } from '../components/CompetitionTabs'
import { DecisionBadge, EmptyState, ErrorState, LoadingState, StatusBadge } from '../components/StateViews'

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; observations: ShadowObservation[] }

/** Résumé lisible du résultat réel d'une observation RÉGLÉE - lecture
 * directe de `settlement` (API, jamais recalculé ici) : score final et
 * résultat réel du marché Over/Under 2.5. `null` tant que l'observation
 * est PENDING, jamais une valeur devinée avant le règlement réel. */
function formatSettlementResult(obs: ShadowObservation): string | null {
  if (obs.settlement === null) return null
  const s = obs.settlement
  return `${s.home_goals_actual}-${s.away_goals_actual} (${s.market_result_over_2_5})`
}

export function Shadow() {
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const [competition, setCompetition] = useState('')

  useEffect(() => {
    let cancelled = false
    getShadowJournal()
      .then((observations) => {
        if (!cancelled) setState({ status: 'ready', observations })
      })
      .catch((err) => {
        if (!cancelled) setState({ status: 'error', message: err instanceof ApiError ? err.detail : String(err) })
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Filtrage par compétition PUREMENT côté présentation (l'API /shadow ne
  // prend aucun paramètre de filtre) - le journal complet reste chargé une
  // seule fois, jamais une nouvelle requête par onglet.
  const observations = state.status === 'ready' ? state.observations : []
  const visibleObservations = useMemo(
    () => (competition === '' ? observations : observations.filter((o) => o.competition === competition)),
    [observations, competition],
  )

  if (state.status === 'loading') return <LoadingState label="Chargement du journal Shadow Mode..." />
  if (state.status === 'error') return <ErrorState message={state.message} />

  return (
    <div className="page shadow-page">
      <h1>Shadow Mode</h1>
      <p className="hint">
        Historique des prédictions du moteur sur des matchs réels, SANS AUCUN PARI RÉEL ENGAGÉ (0 pari réel à ce
        jour - le moteur n'a encore jamais atteint la décision BET, voir « Contrôles / Gates ») : chaque décision est
        enregistrée avant le match puis comparée au résultat réel une fois le match terminé.
      </p>
      {observations.length === 0 ? (
        <EmptyState message="Aucune observation Shadow Mode enregistrée. Le journal est vide - aucune prédiction réelle n'a encore été journalisée." />
      ) : (
        <>
          <CompetitionTabs value={competition} onChange={setCompetition} includeAll />
          {visibleObservations.length === 0 ? (
            <EmptyState message="Aucune observation pour cette compétition." />
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Compétition</th>
                  <th>Saison</th>
                  <th>Match</th>
                  <th>Décision</th>
                  <th>Statut</th>
                  <th>Résultat réel</th>
                </tr>
              </thead>
              <tbody>
                {visibleObservations.map((obs) => (
                  <tr key={obs.prediction_id}>
                    <td>{competitionLabel(obs.competition)}</td>
                    <td>{obs.season}</td>
                    <td>
                      {obs.home_team} – {obs.away_team}
                    </td>
                    <td>
                      <DecisionBadge decision={obs.decision} />
                    </td>
                    <td>
                      <StatusBadge status={obs.status} />
                    </td>
                    <td>{formatSettlementResult(obs) ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </div>
  )
}
