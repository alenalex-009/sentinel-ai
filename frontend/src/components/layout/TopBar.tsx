import { useLocation } from 'react-router-dom'
import { Bell } from 'lucide-react'
import clsx from 'clsx'
import { DemoModeBanner } from '../ui/DemoModeBanner'
import { useApiWithFallback } from '../../hooks/useApiWithFallback'
import { api } from '../../api/client'

const PAGE_TITLES: Record<string, string> = {
  '/': 'Command Overview',
  '/risk': 'Risk & GIS Intelligence',
  '/habitations': 'Habitation Investigation',
  '/priorities': 'Risk & Relocation Priorities',
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
    <div
      className={clsx(
        'inline-flex items-center gap-1.5 rounded border px-1.5 py-0.5 text-2xs font-mono font-medium uppercase tracking-wider',
        apiOk ? (dbOk ? 'border-green-500/30 text-green-400' : 'border-cyan-500/30 text-cyan-400') : 'border-amber-500/30 text-amber-400',
      )
    }
    >
      <span className={clsx(
        'h-1.5 w-1.5 rounded-full',
        dbOk ? 'bg-green-400 animate-pulse' : apiOk ? 'bg-cyan-400' : 'bg-amber-400',
      )} />
      {dbOk ? 'API+DB' : apiOk ? 'API' : 'DEMO'}
    </div>
  )
}

export function TopBar() {
  const { pathname } = useLocation()
  const basePath = '/' + pathname.split('/')[1]
  const title = PAGE_TITLES[basePath] || 'Sentinel AI'

  return (
    <header className="flex h-12 items-center justify-between border-b border-slate-800/80 bg-slate-950 px-4">
      <div className="flex items-center gap-3">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-amber-500/10 border border-amber-500/25">
          <span className="text-2xs font-bold font-mono tracking-widest text-amber-400">SA</span>
        </div>
        <span className="text-sm font-medium text-slate-200">{title}</span>
        <span className="text-2xs text-faint border-l border-slate-800 pl-3">
          Idukki, Kerala
        </span>
      </div>

      <div className="flex items-center gap-2.5">
        <SystemStatus />
        <DemoModeBanner />
        <button
          className="relative flex h-7 w-7 items-center justify-center rounded-md text-faint transition-colors hover:bg-slate-800/70 hover:text-amber-400"
          aria-label="Notifications"
        >
          <Bell className="h-3.5 w-3.5" />
          <span className="absolute right-0.5 top-0.5 h-1.5 w-1.5 rounded-full bg-red-500" />
        </button>
      </div>
    </header>
  )
}
