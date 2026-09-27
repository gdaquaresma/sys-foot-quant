import { useEffect, useState } from 'react'
import { ApiError, getShadowJournal } from '../api/client'
import type { ShadowObservation } from '../api/types'
import { DecisionBadge, EmptyState, ErrorState, LoadingState, StatusBadge } from '../components/StateViews'

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; observations: ShadowObservation[] }

export function Shadow() {
  const [state, setState] = useState<LoadState>({ status: 'loading' })

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

  if (state.status === 'loading') return <LoadingState label="Chargement du journal Shadow Mode..." />
  if (state.status === 'error') return <ErrorState message={state.message} />

  return (
    <div className="page shadow-page">
      <h1>Shadow Mode</h1>
      {state.observations.length === 0 ? (
        <EmptyState message="Aucune observation Shadow Mode enregistrée. Le journal est vide - aucune prédiction réelle n'a encore été journalisée." />
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Compétition</th>
              <th>Saison</th>
              <th>Match</th>
              <th>Décision</th>
              <th>Statut</th>
            </tr>
          </thead>
          <tbody>
            {state.observations.map((obs) => (
              <tr key={obs.prediction_id}>
                <td>{obs.competition}</td>
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
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
