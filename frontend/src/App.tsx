import { Route, Routes } from 'react-router-dom'
import { AppLayout } from './layout/AppLayout'
import { Dashboard } from './pages/Dashboard'
import { MatchDetail } from './pages/MatchDetail'
import { MatchExplorer } from './pages/MatchExplorer'
import { Performance } from './pages/Performance'
import { Shadow } from './pages/Shadow'

export function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="matches" element={<MatchExplorer />} />
        <Route path="matches/:competition/:season/:matchId" element={<MatchDetail />} />
        <Route path="shadow" element={<Shadow />} />
        <Route path="performance" element={<Performance />} />
      </Route>
    </Routes>
  )
}
