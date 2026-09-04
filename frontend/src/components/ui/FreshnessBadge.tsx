import clsx from 'clsx'
import type { DataStatus } from '../../types'

interface FreshnessBadgeProps {
  status: DataStatus
  ageHours?: number | null
  source?: string
}

const STATUS_STYLES: Record<DataStatus, string> = {
  LIVE: 'text-green-400 border-green-500/30',
  DEMO: 'text-amber-400 border-amber-500/30',
  SIMULATION: 'text-cyan-400 border-cyan-500/30',
  UNAVAILABLE: 'text-red-400 border-red-500/30',
  STALE: 'text-orange-400 border-orange-500/30',
}

export function FreshnessBadge({ status, ageHours, source }: FreshnessBadgeProps) {
  return (
    <span className={clsx(
      'inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-2xs font-mono font-medium uppercase tracking-wider',
      STATUS_STYLES[status]
    )}>
      <span className={clsx(
        'h-1.5 w-1.5 rounded-full',
        status === 'LIVE' ? 'bg-green-400 animate-pulse' :
        status === 'DEMO' ? 'bg-amber-400' :
        status === 'SIMULATION' ? 'bg-cyan-400' :
        'bg-red-400'
      )} />
      {status}
      {ageHours != null && <span className="opacity-60">+{ageHours}h</span>}
      {source && <span className="opacity-50 normal-case font-sans">{source}</span>}
    </span>
  )
}
