import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Map,
  Home,
  ListOrdered,
  ArrowRightLeft,
  FlaskConical,
  FileText,
  Database,
} from 'lucide-react'
import clsx from 'clsx'

const NAV_ITEMS = [
  { to: '/', icon: LayoutDashboard, label: 'Overview', exact: true },
  { to: '/risk', icon: Map, label: 'Risk' },
  { to: '/habitations', icon: Home, label: 'Habitations' },
  { to: '/priorities', icon: ListOrdered, label: 'Priorities' },
  { to: '/relocation', icon: ArrowRightLeft, label: 'Relocation' },
  { to: '/scenarios', icon: FlaskConical, label: 'Scenarios' },
  { to: '/reports', icon: FileText, label: 'Reports' },
  { to: '/data', icon: Database, label: 'Data' },
]

export function GlobalNav() {
  return (
    <nav
      className="fixed left-0 top-0 z-50 flex h-full w-[68px] flex-col items-center border-r border-slate-800 bg-slate-950 py-4"
      aria-label="Main navigation"
    >
      {/* Logo mark */}
      <div className="mb-6 flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600/20 border border-blue-500/30">
        <span className="text-xs font-bold text-blue-400 font-mono">SA</span>
      </div>

      {/* Nav items */}
      <div className="flex flex-1 flex-col items-center gap-1">
        {NAV_ITEMS.map(({ to, icon: Icon, label, exact }) => (
          <NavLink
            key={to}
            to={to}
            end={exact}
            title={label}
            className={({ isActive }) =>
              clsx(
                'group relative flex h-12 w-12 flex-col items-center justify-center rounded-lg transition-colors',
                isActive
                  ? 'bg-blue-600/20 text-blue-400'
                  : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300'
              )
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r bg-blue-500" />
                )}
                <Icon className="h-4 w-4" />
                <span className="mt-0.5 text-2xs leading-none">{label}</span>
              </>
            )}
          </NavLink>
        ))}
      </div>

      {/* Bottom — system status */}
      <div className="mt-auto flex flex-col items-center gap-1">
        <div className="h-1.5 w-1.5 rounded-full bg-amber-400" title="DEMO MODE" />
        <span className="text-2xs text-slate-600">DEMO</span>
      </div>
    </nav>
  )
}
