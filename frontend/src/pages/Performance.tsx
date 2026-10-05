import { useEffect, useState } from 'react'
import { ApiError, getPerformance } from '../api/client'
import type { PerformanceResponse } from '../api/types'
import { EmptyState, ErrorState, LoadingState } from '../components/StateViews'

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; performance: PerformanceResponse }

export function Performance() {
  const [state, setState] = useState<LoadState>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false
    getPerformance()
      .then((performance) => {
        if (!cancelled) setState({ status: 'ready', performance })
      })
      .catch((err) => {
        if (!cancelled) setState({ status: 'error', message: err instanceof ApiError ? err.detail : String(err) })
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (state.status === 'loading') return <LoadingState label="Chargement de la performance..." />
  if (state.status === 'error') return <ErrorState message={state.message} />

  const { performance } = state

  return (
    <div className="page performance-page">
      <h1>Performance</h1>
      <p className="hint">
        Statistiques agrégées à partir des prédictions déjà journalisées en Shadow Mode - décisions, modèles et pari
        théorique, jamais un recalcul côté frontend.
      </p>

      <section className="stat-grid">
        <div className="stat-card">
          <span className="stat-value">{performance.n_total}</span>
          <span className="stat-label">Total</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{performance.n_pending}</span>
          <span className="stat-label">En attente</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{performance.n_settled}</span>
          <span className="stat-label">Réglées</span>
        </div>
      </section>

      <section className="card">
        <h2>Répartition des décisions</h2>
        {Object.keys(performance.decision_distribution).length === 0 ? (
          <EmptyState message="Aucune décision enregistrée pour le moment." />
        ) : (
          <ul>
            {Object.entries(performance.decision_distribution).map(([decision, count]) => (
              <li key={decision}>
                {decision} : {count}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="card">
        <h2>Pari (Shadow Mode)</h2>
        {performance.betting.n_bet === 0 ? (
          <EmptyState message={performance.betting.message ?? 'Aucun pari réglé.'} />
        ) : (
          <ul>
            <li>Nombre de paris : {performance.betting.n_bet}</li>
            {performance.betting.win_rate !== undefined && <li>Taux de réussite : {performance.betting.win_rate}</li>}
            {performance.betting.roi_theoretical !== undefined && (
              <li>ROI théorique : {performance.betting.roi_theoretical}</li>
            )}
          </ul>
        )}
      </section>

      <section className="card">
        <h2>Modèles</h2>
        <table className="table">
          <thead>
            <tr>
              <th>Modèle</th>
              <th>n</th>
              <th>Brier</th>
              <th>Log-loss</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(performance.models).map(([model, evalResult]) => (
              <tr key={model}>
                <td>{model}</td>
                <td>{evalResult.n}</td>
                <td>{evalResult.brier ?? '—'}</td>
                <td>{evalResult.log_loss ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}
