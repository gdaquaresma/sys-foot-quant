import { NavLink, Outlet } from 'react-router-dom'

// Navigation réduite autour de l'intention principale (Phase UI-1) :
// "Analyser un match" est l'entrée principale, en premier.
const NAV_ITEMS = [
  { to: '/', label: 'Analyser un match', end: true },
  { to: '/matches', label: 'Historique' },
  { to: '/performance', label: 'Performance' },
  { to: '/shadow', label: 'Shadow Mode' },
]

export function AppLayout() {
  return (
    <div className="app-shell">
      <nav className="app-nav">
        <div className="app-nav-title">sys-foot-quant</div>
        <ul>
          {NAV_ITEMS.map((item) => (
            <li key={item.to}>
              <NavLink to={item.to} end={item.end} className={({ isActive }) => (isActive ? 'active' : '')}>
                {item.label}
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
