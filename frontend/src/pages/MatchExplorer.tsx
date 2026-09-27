/**
 * Explorateur de matchs (Phase UI-2-D) - consomme GET /matches via le
 * client API centralisé.
 *
 * LIMITE DE CONTRAT DOCUMENTÉE : l'API n'expose aucun endpoint
 * d'énumération des compétitions/saisons (seuls GET /matches et
 * GET /matches/{match_id} existent, tous deux exigeant ces valeurs en
 * entrée - voir match_catalog.list_competitions()/list_seasons(), qui
 * existent côté backend mais ne sont câblées à aucune route HTTP). La
 * sélection se fait donc par SAISIE LIBRE, jamais par une liste codée en
 * dur qui prétendrait provenir des données - la validité réelle est
 * déterminée par la vraie réponse de l'API (succès ou erreur 400
 * explicite), jamais supposée côté frontend.
 */
import { type FormEvent, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ApiError, getMatches } from '../api/client'
import type { MatchResponse } from '../api/types'
import { EmptyState, ErrorState, LoadingState } from '../components/StateViews'

type LoadState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; matches: MatchResponse[] }

function formatKickoff(iso: string): string {
  try {
    return new Intl.DateTimeFormat('fr-FR', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(iso))
  } catch {
    return iso
  }
}

export function MatchExplorer() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [competition, setCompetition] = useState(searchParams.get('competition') ?? '')
  const [season, setSeason] = useState(searchParams.get('season') ?? '')
  const [teamFilter, setTeamFilter] = useState('')
  const [state, setState] = useState<LoadState>({ status: 'idle' })

  async function runSearch(comp: string, seas: string) {
    if (!comp.trim() || !seas.trim()) return
    setState({ status: 'loading' })
    try {
      const matches = await getMatches(comp.trim(), seas.trim())
      setState({ status: 'ready', matches })
    } catch (err) {
      setState({ status: 'error', message: err instanceof ApiError ? err.detail : String(err) })
    }
  }

  // Pré-remplit et relance la recherche si l'URL porte déjà
  // competition/season (retour naturel depuis la page détail).
  useEffect(() => {
    const c = searchParams.get('competition')
    const s = searchParams.get('season')
    if (c && s) {
      runSearch(c, s)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSearchParams({ competition: competition.trim(), season: season.trim() })
    runSearch(competition, season)
  }

  const visibleMatches =
    state.status === 'ready'
      ? state.matches.filter((m) => {
          if (!teamFilter.trim()) return true
          const needle = teamFilter.trim().toLowerCase()
          return m.home_team.toLowerCase().includes(needle) || m.away_team.toLowerCase().includes(needle)
        })
      : []

  return (
    <div className="page">
      <h1>Explorateur de matchs</h1>

      <form className="filters" onSubmit={handleSubmit}>
        <label>
          Compétition
          <input
            type="text"
            value={competition}
            onChange={(e) => setCompetition(e.target.value)}
            placeholder="identifiant technique"
            required
          />
        </label>
        <label>
          Saison
          <input
            type="text"
            value={season}
            onChange={(e) => setSeason(e.target.value)}
            placeholder="identifiant technique"
            required
          />
        </label>
        <button type="submit">Rechercher</button>
      </form>

      {state.status === 'ready' && (
        <label className="team-filter">
          Filtrer par équipe
          <input type="text" value={teamFilter} onChange={(e) => setTeamFilter(e.target.value)} placeholder="nom d'équipe" />
        </label>
      )}

      {state.status === 'idle' && (
        <EmptyState message="Renseignez une compétition et une saison (identifiants techniques réels, ex. valeurs déjà utilisées côté backend) puis lancez la recherche." />
      )}
      {state.status === 'loading' && <LoadingState label="Chargement des matchs..." />}
      {state.status === 'error' && <ErrorState message={state.message} />}
      {state.status === 'ready' && visibleMatches.length === 0 && (
        <EmptyState message="Aucun match ne correspond à cette recherche." />
      )}
      {state.status === 'ready' && visibleMatches.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Domicile</th>
              <th>Extérieur</th>
              <th>Statut</th>
            </tr>
          </thead>
          <tbody>
            {visibleMatches.map((m) => (
              <tr key={m.match_id}>
                <td>{formatKickoff(m.kickoff_utc)}</td>
                <td>{m.home_team}</td>
                <td>{m.away_team}</td>
                <td>
                  <Link to={`/matches/${m.competition}/${m.season}/${m.match_id}`}>
                    {m.is_played ? 'Joué — voir détail' : 'À venir — voir détail'}
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
