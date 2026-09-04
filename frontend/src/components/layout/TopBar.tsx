import { useLocation } from 'react-router-dom'
import { Shield, Bell, Wifi, WifiOff } from 'lucide-react'
import { FreshnessBadge } from '../ui/FreshnessBadge'
import { DemoModeBanner } from '../ui/DemoModeBanner'
import { useApiWithFallback } from '../../hooks/useApiWithFallback'
import { api } from '../../api/client'

const PAGE_TITLES: Record<string, string> = {
  '/': 'Command Overview — Idukki, Kerala',
  '/risk': 'Risk & GIS Intelligence',
  '/habitations': 'Habitation Investigation',
  '/priorities': 'Risk & Priorities',
  '/relocation': 'Relocation Intelligence',
  '/scenarios': 'Scenario Analysis',
  '/reports': 'Reports',
  '/data': 'Data & Sources',
}

function SystemStatus() {
  const { data, source } = useApiWithFallback<{ status: string; database: string }>(
    () => api.health(),
    { status: 'unknown', database: 'unknown' },
  )

  const apiOk = source === 'api' && data?.status === 'ok'
  const dbOk = apiOk && data?.database === 'ok'

  return (
    <div className="flex items-center gap-2" title={`API: ${source} | DB: ${data?.database ?? 'unknown'}`}>
      {apiOk ? (
        <Wifi className="h-3.5 w-3.5 text-green-500" />
      ) : (
        <WifiOff className="h-3.5 w-3.5 text-amber-500" />
      )}
      <span className="text-2xs text-slate-600">
        {apiOk ? (dbOk ? 'API+DB' : 'API only') : 'DEMO'}
      </span>
    </div>
  )
}

export function TopBar() {
  const { pathname } = useLocation()
  const basePath = '/' + pathname.split('/')[1]
  const title = PAGE_TITLES[basePath] || 'Sentinel AI'

  return (
    <header className="flex h-12 items-center justify-between border-b border-slate-800 bg-slate-950 px-4">
      <div className="flex items-center gap-3">
        <Shield className="h-4 w-4 text-blue-400" />
        <span className="text-sm font-medium text-slate-200">{title}</span>
      </div>

      <div className="flex items-center gap-3">
        <SystemStatus />
        <DemoModeBanner />
        <FreshnessBadge status="DEMO" ageHours={3} />
        <button className="relative flex h-7 w-7 items-center justify-center rounded text-slate-500 hover:bg-slate-800 hover:text-slate-300">
          <Bell className="h-4 w-4" />
          <span className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-red-500" />
        </button>
      </div>
    </header>
  )
}
