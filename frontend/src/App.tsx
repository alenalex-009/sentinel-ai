import { Routes, Route } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { Overview } from './pages/Overview'
import { Habitations } from './pages/Habitations'
import { HabitationInvestigation } from './pages/HabitationInvestigation'
import { DecisionIntelligence } from './pages/DecisionIntelligence'
import { Placeholder } from './pages/Placeholder'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        {/* Screen 01 — Command Overview */}
        <Route index element={<Overview />} />

        {/* Screen 08 — Risk & GIS Intelligence (Phase 2) */}
        <Route
          path="/risk"
          element={
            <Placeholder
              title="Risk & GIS Intelligence"
              description="District-wide risk map with current/baseline/change controls, layer filters, and risk intelligence panel. Scheduled for Phase 2."
            />
          }
        />

        {/* Habitations list */}
        <Route path="/habitations" element={<Habitations />} />

        {/* Screen 09 — Habitation Investigation */}
        <Route path="/habitations/:id" element={<HabitationInvestigation />} />

        {/* Screen 10 — Decision Intelligence */}
        <Route path="/habitations/:id/decision" element={<DecisionIntelligence />} />

        {/* Priorities (Phase 2) */}
        <Route
          path="/priorities"
          element={
            <Placeholder
              title="Risk & Priorities"
              description="District-wide ranking of habitations requiring attention, with RPI scores and priority classification. Scheduled for Phase 2."
            />
          }
        />

        {/* Relocation Intelligence (Phase 2) */}
        <Route
          path="/relocation"
          element={
            <Placeholder
              title="Relocation Intelligence"
              description="Candidate sites, suitability scoring, carrying capacity assessment, and multi-site relocation planning. Scheduled for Phase 2."
            />
          }
        />

        {/* Scenarios (Phase 2) */}
        <Route
          path="/scenarios"
          element={
            <Placeholder
              title="Scenario Analysis"
              description="What-if scenarios for rainfall, population, capacity, and road disruption changes. All results labelled SIMULATED. Scheduled for Phase 2."
            />
          }
        />

        {/* Reports (Phase 2) */}
        <Route
          path="/reports"
          element={
            <Placeholder
              title="Reports"
              description="District, habitation, risk, evidence, candidate sites, capacity, relocation and scenario reports. Scheduled for Phase 2."
            />
          }
        />

        {/* Data & Sources (Phase 2) */}
        <Route
          path="/data"
          element={
            <Placeholder
              title="Data & Sources"
              description="Dataset registry: source, year, update time, type, model/version, limitations. ISRO/NRSC, Bhuvan, IMD, CWC, Census, KSDMA. Scheduled for Phase 2."
            />
          }
        />
      </Route>
    </Routes>
  )
}
