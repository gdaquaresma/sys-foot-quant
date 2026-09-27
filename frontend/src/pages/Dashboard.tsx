import { useEffect, useState } from 'react'
import { ApiError, getPerformance, getShadowJournal } from '../api/client'
import type { PerformanceResponse, ShadowObservation } from '../api/types'
import { EmptyState, ErrorState, LoadingState } from '../components/StateViews'

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; performance: PerformanceResponse; journal: ShadowObservation[] }

export function Dashboard() {
  const [state, setState] = useState<LoadState>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [performance, journal] = await Promise.all([getPerformance(), getShadowJournal()])
        if (!cancelled) setState({ status: 'ready', performance, journal })
      } catch (err) {
        if (!cancelled) {
          setState({ status: 'error', message: err instanceof ApiError ? err.detail : String(err) })
        }
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  if (state.status === 'loading') return <LoadingState label="Chargement du tableau de bord..." />
  if (state.status === 'error') return <ErrorState message={state.message} />

  const { performance, journal } = state

  return (
    <div className="page dashboard">
      <h1>Tableau de bord</h1>

      <section className="card">
        <h2>Journal Shadow Mode</h2>
        {journal.length === 0 ? (
          <EmptyState message="Aucune observation Shadow Mode enregistrée pour le moment." />
        ) : (
          <p>{journal.length} observation(s) enregistrée(s).</p>
        )}
      </section>

      <section className="card">
        <h2>Performance</h2>
        <p>
          {performance.n_total} observation(s) au total — {performance.n_pending} en attente,{' '}
          {performance.n_settled} réglée(s).
        </p>
        <p>{performance.betting.message ?? `${performance.betting.n_bet} pari(s) réglé(s).`}</p>
      </section>

      <section className="card">
        <h2>Accès principaux</h2>
        <ul>
          <li>Explorateur de matchs (voir « Matchs »)</li>
          <li>Journal Shadow Mode complet (voir « Shadow Mode »)</li>
          <li>Détail de performance (voir « Performance »)</li>
        </ul>
      </section>
    </div>
  )
}
