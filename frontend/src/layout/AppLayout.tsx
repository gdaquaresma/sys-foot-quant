import { NavLink, Outlet } from 'react-router-dom'
import { useStarredMatches } from '../api/useStarredMatches'

// Navigation réduite autour de l'intention principale (Phase UI-1) :
// "Analyser un match" est l'entrée principale, en premier. Le libellé de
// chaque entrée reprend EXACTEMENT le titre (`<h1>`) de la page qu'elle
// ouvre - "Historique" désignait auparavant `/matches`, qui s'intitule en
// réalité "Explorateur de matchs" (et sert à chercher N'IMPORTE quel match
// d'une compétition/saison, pas seulement un historique) : un utilisateur
// cliquant "Historique" atterrissait sur une page qui se présentait
// autrement, revue de cohérence produit.
const NAV_ITEMS = [
  { to: '/', label: 'Analyser un match', end: true },
  { to: '/matches', label: 'Explorateur de matchs' },
  { to: '/performance', label: 'Performance' },
  { to: '/shadow', label: 'Shadow Mode' },
  { to: '/mes-paris', label: 'Mes paris' },
]

export function AppLayout() {
  const { starred } = useStarredMatches()
  return (
    <div className="app-shell">
      <nav className="app-nav">
        <div className="app-nav-title">sys-foot-quant</div>
        <ul>
          {NAV_ITEMS.map((item) => (
            <li key={item.to}>
              <NavLink to={item.to} end={item.end} className={({ isActive }) => (isActive ? 'active' : '')}>
                {item.label}
                {item.to === '/mes-paris' && starred.length > 0 && <span className="nav-count-badge">{starred.length}</span>}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <main className="app-content">
        <Outlet />
      </main>
    </div>
  )
}
