/**
 * Tableau de bord (Phase UI-2-E) - page d'entrée agrégeant uniquement des
 * COMPTAGES DESCRIPTIFS des données déjà retournées par /shadow et
 * /performance (jamais un recalcul métier, jamais une prédiction,
 * probabilité, cote, edge ou décision recréée côté frontend).
 *
 * LIMITE DE CONTRAT DOCUMENTÉE (héritée de UI-2-D, toujours vraie) :
 * GET /matches exige competition+season déjà connus et l'API n'expose
 * aucun endpoint d'énumération - le Dashboard ne peut donc PAS afficher
 * un nombre total de matchs "toutes compétitions confondues" ni une
 * liste de "prochains/derniers matchs" sans fabriquer un choix arbitraire
 * de compétition/saison. Cette limite est documentée à l'écran plutôt que
 * contournée.
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, getPerformance, getShadowJournal } from '../api/client'
import type { PerformanceResponse, ShadowObservation } from '../api/types'
import { ErrorState, LoadingState } from '../components/StateViews'

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
  // Comptages purement descriptifs, dérivés des données déjà retournées -
  // aucun recalcul métier (le champ `status` est déjà produit par l'API).
  const pendingCount = journal.filter((o) => o.status === 'PENDING').length
  const settledCount = journal.filter((o) => o.status === 'SETTLED').length

  return (
    <div className="page dashboard">
      <h1>Tableau de bord</h1>
      <p className="hint">
        Comptages descriptifs issus du journal Shadow Mode et de la performance déjà calculée par le moteur - rien n'est
        recalculé ici.
      </p>

      {/* Bloc 1 - Vue d'ensemble */}
      <section className="stat-grid">
        <div className="stat-card">
          <span className="stat-value">{journal.length}</span>
          <span className="stat-label">Observations Shadow Mode</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{pendingCount}</span>
          <span className="stat-label">En attente</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{settledCount}</span>
          <span className="stat-label">Réglées</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{performance.betting.n_bet}</span>
          <span className="stat-label">Paris réglés</span>
        </div>
      </section>

      {/* Bloc 2 - Accès rapide - "Analyser un match" EN PREMIER : c'est
          désormais l'entrée principale du produit (page `/`, Phase UI-1),
          ce tableau de bord ne doit pas donner l'impression d'un produit
          différent qui l'ignorerait (revue de cohérence produit). */}
      <section className="card">
        <h2>Accès rapide</h2>
        <div className="quick-links">
          <Link className="quick-link" to="/">
            Analyser un match
          </Link>
          <Link className="quick-link" to="/matches">
            Explorateur de matchs
          </Link>
          <Link className="quick-link" to="/shadow">
            Shadow Mode
          </Link>
          <Link className="quick-link" to="/performance">
            Performance
          </Link>
        </div>
      </section>

      {/* Bloc 3 - Matchs : limitation documentée, aucune donnée fabriquée */}
      <section className="card">
        <h2>Matchs</h2>
        <p className="state state-empty">
          Aucun aperçu de matchs n'est affiché ici : l'API ne fournit pas de moyen de lister les matchs disponibles
          sans connaître au préalable une compétition et une saison précises. Utilisez l'
          <Link to="/matches">Explorateur de matchs</Link> pour rechercher des matchs réels.
        </p>
      </section>

      {/* Bloc 4 - État du système. Pas de ligne "API accessible" ici : cette
          section ne se rend que si les deux appels ont déjà réussi (voir
          `state.status === 'ready'` plus haut) - un indicateur "accessible"
          systématiquement vrai dans ce cas n'informe de rien (revue de
          cohérence produit, aucun bloc décoratif sans utilité réelle). */}
      <section className="card">
        <h2>État du système</h2>
        <ul className="system-status">
          <li>{journal.length === 0 ? 'Aucune donnée Shadow Mode enregistrée' : `${journal.length} observation(s) Shadow Mode disponible(s)`}</li>
          <li>
            {performance.n_total === 0
              ? 'Aucune observation de performance disponible'
              : `${performance.n_total} observation(s) de performance disponible(s)`}
          </li>
          <li className="state-note">
            Limitation connue : aucun décompte global des matchs (voir section « Matchs » ci-dessus).
          </li>
        </ul>
      </section>
    </div>
  )
}
