import { Routes, Route } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { Overview } from './pages/Overview'
import { RiskIntelligence } from './pages/RiskIntelligence'
import { Habitations } from './pages/Habitations'
import { HabitationInvestigation } from './pages/HabitationInvestigation'
import { DecisionIntelligence } from './pages/DecisionIntelligence'
import { Priorities } from './pages/Priorities'
import { RelocationIntelligence } from './pages/RelocationIntelligence'
import { ScenarioAnalysis } from './pages/ScenarioAnalysis'
import { DataSources } from './pages/DataSources'
import { Placeholder } from './pages/Placeholder'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        {/* Screen 01 — Command Overview */}
        <Route index element={<Overview />} />

        {/* Screen 08 — Risk & GIS Intelligence */}
        <Route path="/risk" element={<RiskIntelligence />} />

        {/* Habitations list */}
        <Route path="/habitations" element={<Habitations />} />

        {/* Screen 09 — Habitation Investigation */}
        <Route path="/habitations/:id" element={<HabitationInvestigation />} />

        {/* Screen 10 — Decision Intelligence */}
        <Route path="/habitations/:id/decision" element={<DecisionIntelligence />} />

        {/* Risk & Priorities — district-wide RPI ranking */}
        <Route path="/priorities" element={<Priorities />} />

        {/* Relocation Intelligence — sites, suitability, capacity, allocation */}
        <Route path="/relocation" element={<RelocationIntelligence />} />

        {/* Scenario Analysis */}
        <Route path="/scenarios" element={<ScenarioAnalysis />} />

        {/* Reports (Phase 3) */}
        <Route
          path="/reports"
          element={
            <Placeholder
              title="Reports"
              description="District, habitation, risk, evidence, candidate sites, capacity, relocation and scenario reports. Scheduled for Phase 3."
            />
          }
        />

        {/* Data & Sources */}
        <Route path="/data" element={<DataSources />} />
      </Route>
    </Routes>
  )
}
