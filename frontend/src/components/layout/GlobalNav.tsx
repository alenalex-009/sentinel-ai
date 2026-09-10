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
  { to: '/data', icon: Database, label: 'Data & Sources' },
]

export function GlobalNav() {
  return (
    <nav
      className="fixed left-0 top-0 z-50 flex h-full w-[68px] flex-col items-center border-r border-slate-800/80 bg-slate-950 py-3"
      aria-label="Main navigation"
    >
      {/* Logo mark */}
      <div className="mb-5 flex h-7 w-7 items-center justify-center rounded-md bg-amber-500/10 border border-amber-500/25">
        <span className="text-[10px] font-bold font-mono tracking-widest text-amber-400">SA</span>
      </div>

      {/* Nav items */}
      <div className="flex flex-1 flex-col items-center gap-1">
        {NAV_ITEMS.map(({ to, icon: Icon, label, exact }) => (
          <NavLink
            key={to}
            to={to}
            end={exact}
            title={label}
            aria-label={label}
            className={({ isActive }) =>
              clsx(
                'nav-item group relative flex h-8 w-8 flex-col items-center justify-center rounded-md transition-colors',
                isActive && 'nav-item-active',
              )
            }
          >
            <Icon className="h-3.5 w-3.5" />
            <span className="sr-only">{label}</span>
          </NavLink>
        ))}
      </div>

      {/* Bottom — demo marker */}
      <div className="mt-auto flex flex-col items-center gap-1">
        <div className="h-1.5 w-1.5 rounded-full bg-amber-400" title="DEMO MODE" aria-hidden="true" />
        <span className="text-[10px] text-faint tracking-wide" aria-label="Demo mode">DEMO</span>
      </div>
    </nav>
  )
}
