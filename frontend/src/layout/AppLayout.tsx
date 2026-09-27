import { NavLink, Outlet } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/matches', label: 'Matchs' },
  { to: '/shadow', label: 'Shadow Mode' },
  { to: '/performance', label: 'Performance' },
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
