import { Route, Routes } from 'react-router-dom'
import { AppLayout } from './layout/AppLayout'
import { AnalyzeMatch } from './pages/AnalyzeMatch'
import { Dashboard } from './pages/Dashboard'
import { MatchDetail } from './pages/MatchDetail'
import { MatchExplorer } from './pages/MatchExplorer'
import { Performance } from './pages/Performance'
import { Shadow } from './pages/Shadow'

export function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<AnalyzeMatch />} />
        {/* Ancien tableau de bord - conservé, non supprimé, retiré de la
            navigation principale au profit d'"Analyser un match" (Phase
            UI-1) - toujours accessible directement via /dashboard. */}
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="matches" element={<MatchExplorer />} />
        <Route path="matches/:competition/:season/:matchId" element={<MatchDetail />} />
        <Route path="shadow" element={<Shadow />} />
        <Route path="performance" element={<Performance />} />
      </Route>
    </Routes>
  )
}
