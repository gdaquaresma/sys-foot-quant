/**
 * Détail d'un match (Phase UI-2-D) - consomme GET /matches/{match_id} via
 * le client API centralisé.
 *
 * IMPORTANT (garde-fou explicite) : cette page N'AFFICHE JAMAIS de
 * prédiction, probabilité, cote, edge, décision BET/NO_BET ou graphique -
 * aucune route de prédiction n'existe côté API (GET /matches/{match_id}
 * ne retourne QUE des métadonnées de catalogue : compétition, saison,
 * date, équipes, statut joué/non-joué). La section "Prédiction"
 * ci-dessous est un texte STATIQUE indiquant l'absence de cette
 * fonctionnalité, jamais une valeur calculée ou approchée.
 */
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError, getMatch } from '../api/client'
import type { MatchResponse } from '../api/types'
import { ErrorState, LoadingState } from '../components/StateViews'

type LoadState =
  | { status: 'loading' }
  | { status: 'invalid-params' }
  | { status: 'not-found'; message: string }
  | { status: 'error'; message: string }
  | { status: 'ready'; match: MatchResponse }

function formatKickoff(iso: string): string {
  try {
    return new Intl.DateTimeFormat('fr-FR', { dateStyle: 'full', timeStyle: 'short' }).format(new Date(iso))
  } catch {
    return iso
  }
}

export function MatchDetail() {
  const { competition, season, matchId } = useParams()
  const [state, setState] = useState<LoadState>({ status: 'loading' })

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
            <h2>Prédiction</h2>
            <p className="state state-empty">
              Les informations de prédiction (probabilités, cote, edge, décision) ne sont pas disponibles dans cette
              version : aucune route de prédiction n'existe côté API.
            </p>
          </section>
        </>
      )}
    </div>
  )
}
