import { AlertTriangle, Database, MapPin, Users } from 'lucide-react'
import clsx from 'clsx'

type EmptyStateVariant =
  | 'no-data'
  | 'api-unavailable'
  | 'db-unavailable'
  | 'no-candidates'
  | 'insufficient-capacity'
  | 'optimization-infeasible'
  | 'stale-data'
  | 'missing-hazard-layer'

const VARIANTS: Record<EmptyStateVariant, {
  icon: React.ReactNode
  title: string
  description: string
  color: string
}> = {
  'no-data': {
    icon: <Database className="h-5 w-5" />,
    title: 'No data available',
    description: 'Data for this item is not available. Check data sources.',
    color: 'text-slate-500',
  },
  'api-unavailable': {
    icon: <AlertTriangle className="h-5 w-5" />,
    title: 'API unavailable',
    description: 'Backend API is not reachable. Showing demo fallback data where available.',
    color: 'text-amber-500',
  },
  'db-unavailable': {
    icon: <Database className="h-5 w-5" />,
    title: 'Database unavailable',
    description: 'PostGIS database is not reachable. Using demo seed data.',
    color: 'text-amber-500',
  },
  'no-candidates': {
    icon: <MapPin className="h-5 w-5" />,
    title: 'No technically suitable candidate sites',
    description: 'No candidate sites passed hard safety and feasibility constraints for this habitation.',
    color: 'text-red-500',
  },
  'insufficient-capacity': {
    icon: <Users className="h-5 w-5" />,
    title: 'Insufficient total capacity',
    description: 'Combined capacity of all candidate sites is less than relocation demand. Additional sites required.',
    color: 'text-orange-500',
  },
  'optimization-infeasible': {
    icon: <AlertTriangle className="h-5 w-5" />,
    title: 'Optimization infeasible',
    description: 'No feasible allocation found given current constraints. Review site eligibility and capacity.',
    color: 'text-red-500',
  },
  'stale-data': {
    icon: <AlertTriangle className="h-5 w-5" />,
    title: 'Data may be stale',
    description: 'Source data has not been updated recently. Results may not reflect current conditions.',
    color: 'text-orange-500',
  },
  'missing-hazard-layer': {
    icon: <MapPin className="h-5 w-5" />,
    title: 'Overlay unavailable',
    description: 'Bhuvan WMS overlay (Kerala 2019 event, ISRO/NRSC) could not be loaded. Map shows basemap only.',
    color: 'text-amber-500',
  },
}

interface EmptyStateProps {
  variant: EmptyStateVariant
  detail?: string
  onRetry?: () => void
  compact?: boolean
}

export function EmptyState({ variant, detail, onRetry, compact = false }: EmptyStateProps) {
  const v = VARIANTS[variant]
  return (
    <div className={clsx(
      'flex flex-col items-center justify-center gap-2 rounded border border-slate-800 bg-slate-900/50',
      compact ? 'px-3 py-4' : 'px-6 py-10'
    )}>
      <span className={clsx(v.color)}>{v.icon}</span>
      <div className="text-center">
        <div className={clsx('text-sm font-semibold', v.color)}>{v.title}</div>
        <p className="text-xs text-slate-500 mt-1 max-w-xs">{v.description}</p>
        {detail && <p className="text-2xs text-slate-600 mt-1">{detail}</p>}
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="text-xs text-blue-400 hover:text-blue-300 underline mt-1"
        >
          Retry
        </button>
      )}
    </div>
  )
}
