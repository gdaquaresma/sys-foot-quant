/**
 * "Mes paris" - matchs que l'utilisateur a personnellement cochés (voir
 * `../api/starredMatches.ts`), avec le côté qu'il dit avoir choisi
 * (Over/Under 2.5) et le résultat de SON pari réel. PURE annotation
 * personnelle, saisie manuelle exclusivement : n'affiche jamais une
 * décision du moteur, ne crée aucune observation Shadow Mode, n'exécute
 * aucun pari réel - c'est un pense-bête, pas un journal du système, et
 * `my_pick`/`result` ne sont jamais déduits automatiquement (ni du
 * pronostic du modèle, ni d'un règlement Shadow Mode). Stocké uniquement
 * dans ce navigateur (localStorage) : ne survit pas à un autre appareil,
 * peut être vidé par l'utilisateur.
 */
import { Link } from 'react-router-dom'
import { competitionLabel, seasonLabel } from '../api/catalog'
import type { MyPick, MyResult } from '../api/starredMatches'
import { useStarredMatches } from '../api/useStarredMatches'
import { StarToggle } from '../components/StarToggle'
import { EmptyState } from '../components/StateViews'

export function StarredMatches() {
  const { starred, toggleStar, updateStar } = useStarredMatches()
  const sorted = [...starred].sort((a, b) => b.starred_at.localeCompare(a.starred_at))

  return (
    <div className="page">
      <h1>Mes paris</h1>
      <p className="hint">
        Les matchs que vous avez cochés pour les repérer (ex. un pari que vous avez placé vous-même, ailleurs) - une
        liste personnelle, enregistrée uniquement dans ce navigateur. Ce n'est ni une décision du moteur, ni un pari
        réellement exécuté par l'outil : le côté choisi et le résultat sont ce que VOUS renseignez ici, jamais déduits
        automatiquement.
      </p>
      {sorted.length === 0 ? (
        <EmptyState message="Aucun match coché pour l'instant. Cliquez l'étoile ☆ à côté d'un match dans l'explorateur pour l'ajouter ici." />
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th aria-label="Retirer"></th>
              <th>Compétition</th>
              <th>Saison</th>
              <th>Match</th>
              <th>Mon pari</th>
              <th>Résultat</th>
              <th>Ajouté le</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((m) => (
              <tr key={m.match_id}>
                <td>
                  <StarToggle starred label={`${m.home_team} – ${m.away_team}`} onToggle={() => toggleStar(m)} />
                </td>
                <td>{competitionLabel(m.competition)}</td>
                <td>{seasonLabel(m.season)}</td>
                <td>
                  {m.home_team} – {m.away_team}
                </td>
                <td>
                  <label className="sr-only" htmlFor={`pick-${m.match_id}`}>
                    Mon pari pour {m.home_team} – {m.away_team}
                  </label>
                  <select
                    id={`pick-${m.match_id}`}
                    value={m.my_pick ?? ''}
                    onChange={(e) => updateStar(m.match_id, { my_pick: (e.target.value || null) as MyPick | null })}
                  >
                    <option value="">— Non renseigné —</option>
                    <option value="Over">Over 2.5</option>
                    <option value="Under">Under 2.5</option>
                  </select>
                </td>
                <td>
                  <label className="sr-only" htmlFor={`result-${m.match_id}`}>
                    Résultat de mon pari pour {m.home_team} – {m.away_team}
                  </label>
                  <select
                    id={`result-${m.match_id}`}
                    className={m.result === 'won' ? 'result-won' : m.result === 'lost' ? 'result-lost' : ''}
                    value={m.result ?? ''}
                    onChange={(e) => updateStar(m.match_id, { result: (e.target.value || null) as MyResult | null })}
                  >
                    <option value="">En attente</option>
                    <option value="won">Gagné</option>
                    <option value="lost">Perdu</option>
                  </select>
                </td>
                <td>{new Date(m.starred_at).toLocaleString('fr-FR')}</td>
                <td>
                  <Link to={`/matches/${m.competition}/${m.season}/${m.match_id}`}>Voir détail</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
