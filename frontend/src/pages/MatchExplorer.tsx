/**
 * Explorateur de matchs (Phase UI-2-D) - consomme GET /matches via le
 * client API centralisé.
 *
 * Compétition/saison sont sélectionnées via les MÊMES menus déroulants à
 * libellés humains que `AnalyzeMatch.tsx` (`../api/catalog`, source
 * unique partagée) - jamais une saisie libre d'identifiant technique brut
 * type "ligue1"/"2024_25" (revue de cohérence produit : cette page, bien
 * que plus technique dans son usage - recherche large, filtrage par nom
 * d'équipe -, doit rester reconnaissable comme faisant partie du même
 * produit que la page d'analyse principale). La validité réelle reste
 * déterminée par la vraie réponse de l'API (succès ou erreur 400
 * explicite), jamais supposée côté frontend : ces options sont un confort
 * de présentation, pas une validation.
 */
import { type FormEvent, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { COMPETITION_OPTIONS, SEASON_OPTIONS } from '../api/catalog'
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
      <p className="hint">Recherchez tous les matchs d'une compétition et d'une saison, puis filtrez par équipe.</p>

      <form className="filters" onSubmit={handleSubmit}>
        <label>
          Compétition
          <select value={competition} onChange={(e) => setCompetition(e.target.value)} required>
            <option value="">— Choisir —</option>
            {COMPETITION_OPTIONS.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Saison
          <select value={season} onChange={(e) => setSeason(e.target.value)} required>
            <option value="">— Choisir —</option>
            {SEASON_OPTIONS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
        <button type="submit">Rechercher</button>
      </form>

      {state.status === 'ready' && (
        <label className="team-filter">
          Filtrer par équipe
          <input type="text" value={teamFilter} onChange={(e) => setTeamFilter(e.target.value)} placeholder="nom d'équipe" />
        </label>
      )}

      {state.status === 'idle' && <EmptyState message="Choisissez une compétition et une saison puis lancez la recherche." />}
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
