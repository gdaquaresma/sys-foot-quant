/**
 * Explorateur de matchs (Phase UI-2-D) - consomme GET /matches via le
 * client API centralisé.
 *
 * Compétition (onglets, `../components/CompetitionTabs`) et saison (menu
 * déroulant) sont sélectionnées via les MÊMES composants à libellés
 * humains que `AnalyzeMatch.tsx` (`../api/catalog`, source unique
 * partagée) - jamais une saisie libre d'identifiant technique brut
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
import { SEASON_OPTIONS } from '../api/catalog'
import { ApiError, getMatches } from '../api/client'
import { analysisAvailability, formatFixtureDate, formatLocalKickoffTime } from '../api/fixtureTiming'
import type { MatchResponse } from '../api/types'
import { useStarredMatches } from '../api/useStarredMatches'
import { CompetitionTabs } from '../components/CompetitionTabs'
import { StarToggle } from '../components/StarToggle'
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

/** Date/heure d'une fixture pour la colonne "Date" - EXTENSION fixtures
 * futures 2026/27. Jamais une heure locale (kickoff_local_naive)
 * présentée comme une heure UTC confirmée, ni une heure fabriquée pour
 * une fixture sans heure publiée (voir ../api/fixtureTiming.ts). */
function formatMatchDateTime(match: MatchResponse): string {
  if (match.kickoff_utc !== null) return formatKickoff(match.kickoff_utc)
  if (match.kickoff_local_naive !== null) {
    return `${formatFixtureDate(match.fixture_date)} · ${formatLocalKickoffTime(match.kickoff_local_naive)} (heure locale)`
  }
  return `${formatFixtureDate(match.fixture_date)} (heure non publiée)`
}

export function MatchExplorer() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [competition, setCompetition] = useState(searchParams.get('competition') ?? '')
  const [season, setSeason] = useState(searchParams.get('season') ?? '')
  const [teamFilter, setTeamFilter] = useState('')
  const [state, setState] = useState<LoadState>({ status: 'idle' })
  const { isStarred, toggleStar } = useStarredMatches()

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

      <CompetitionTabs value={competition} onChange={setCompetition} />
      <form className="filters" onSubmit={handleSubmit}>
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
              <th aria-label="Mes paris"></th>
              <th>Date</th>
              <th>Domicile</th>
              <th>Extérieur</th>
              <th>Statut</th>
            </tr>
          </thead>
          <tbody>
            {visibleMatches.map((m) => (
              <tr key={m.match_id}>
                <td>
                  <StarToggle
                    starred={isStarred(m.match_id)}
                    label={`${m.home_team} – ${m.away_team}`}
                    onToggle={() =>
                      toggleStar({ match_id: m.match_id, competition: m.competition, season: m.season, home_team: m.home_team, away_team: m.away_team })
                    }
                  />
                </td>
                <td>{formatMatchDateTime(m)}</td>
                <td>{m.home_team}</td>
                <td>{m.away_team}</td>
                <td>
                  <Link to={`/matches/${m.competition}/${m.season}/${m.match_id}`}>
                    {m.is_played ? 'Joué — voir détail' : 'À venir — voir détail'}
                  </Link>
                  {/* EXTENSION fixtures futures 2026/27 : signale, SANS
                      empêcher la navigation, qu'une fixture future n'est
                      pas encore analysable (aucune heure publiée, ou
                      compétition hors du périmètre de l'estimation
                      CET/CEST) - jamais confondu avec un résultat déjà
                      joué. Pour une fixture Ligue 1 analysable par heure
                      ESTIMÉE (voir fixtureTiming.ts), un rappel distinct
                      le signale plutôt que de la faire passer pour une
                      heure confirmée. */}
                  {!m.is_played &&
                    (() => {
                      const availability = analysisAvailability(m)
                      if (!availability.available) return <span className="hint"> (analyse indisponible)</span>
                      if (availability.estimated) return <span className="hint"> (heure estimée)</span>
                      return null
                    })()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
