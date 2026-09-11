import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search } from 'lucide-react'
import { RiskBadge } from '../components/ui/RiskBadge'
import { PriorityBadge } from '../components/ui/PriorityBadge'
import { FreshnessBadge } from '../components/ui/FreshnessBadge'
import { ApiStatusBanner } from '../components/ui/ApiStatusBanner'
import { useApiWithFallback } from '../hooks/useApiWithFallback'
import { api } from '../api/client'
import type { HabitationsResponse } from '../types'
import { DEMO_HABITATIONS } from '../data/idukki-seed'

export function Habitations() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')

  const { data: payload, error, source } = useApiWithFallback<HabitationsResponse>(
    () => api.getHabitations('idukki') as Promise<HabitationsResponse>,
    { data_status: 'DEMO', _source: 'demo_fallback', district_id: 'idukki', total: DEMO_HABITATIONS.length, habitations: DEMO_HABITATIONS },
  )
  // The API returns { data_status, habitations: [...] } — unwrap or fall back.
  const list = payload?.habitations?.length ? payload.habitations : DEMO_HABITATIONS

  const filtered = list.filter(h =>
    h.name.toLowerCase().includes(search.toLowerCase()) ||
    h.ward.toLowerCase().includes(search.toLowerCase()) ||
    h.taluk.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="flex h-full flex-col overflow-hidden p-4">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-base font-semibold text-slate-200">Habitations — Idukki</h1>
          <p className="text-xs text-slate-500">{list.length} habitations · Pilot region</p>
        </div>
        <FreshnessBadge status="DEMO" />
      </div>

      {error && <ApiStatusBanner source={source} error={error} className="mb-4" />}

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
        <input
          type="text"
          placeholder="Search habitations..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full rounded border border-slate-700 bg-slate-900 py-2 pl-9 pr-3 text-sm text-slate-200 placeholder-slate-600 focus:border-blue-500 focus:outline-none"
        />
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto rounded-lg border border-slate-800">
        <table className="w-full">
          <thead className="sticky top-0 bg-slate-900">
            <tr className="border-b border-slate-800">
              {['Habitation', 'Ward / Taluk', 'Population', 'Risk', 'Change', 'Priority', 'Hazard', ''].map(col => (
                <th key={col} className="px-3 py-2 text-left text-2xs font-semibold uppercase tracking-wide text-slate-500">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map(h => (
              <tr
                key={h.id}
                className="border-b border-slate-800/50 hover:bg-slate-900 cursor-pointer"
                onClick={() => navigate(`/habitations/${h.id}`)}
              >
                <td className="px-3 py-2.5">
                  <span className="text-sm font-medium text-slate-200">{h.name}</span>
                </td>
                <td className="px-3 py-2.5">
                  <div className="text-xs text-slate-400">{h.ward}</div>
                  <div className="text-2xs text-slate-600">{h.taluk}</div>
                </td>
                <td className="px-3 py-2.5 text-sm font-mono text-slate-300">
                  {h.population.toLocaleString()}
                </td>
                <td className="px-3 py-2.5">
                  <RiskBadge score={h.risk_score} size="sm" />
                </td>
                <td className="px-3 py-2.5">
                  <span className={`text-xs font-mono font-semibold ${
                    h.risk_change > 0 ? 'text-red-400' : h.risk_change < 0 ? 'text-green-400' : 'text-slate-500'
                  }`}>
                    {h.risk_change > 0 ? '+' : ''}{h.risk_change}
                  </span>
                </td>
                <td className="px-3 py-2.5">
                  <PriorityBadge priority={h.priority} size="sm" />
                </td>
                <td className="px-3 py-2.5">
                  <span className="text-xs text-slate-500">{h.primary_hazard}</span>
                </td>
                <td className="px-3 py-2.5">
                  <button className="text-xs text-blue-400 hover:text-blue-300">Investigate →</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
