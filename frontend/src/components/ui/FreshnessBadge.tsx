import clsx from 'clsx'
import type { DataStatus } from '../../types'

interface FreshnessBadgeProps {
  status: DataStatus
  ageHours?: number | null
  source?: string
}

const STATUS_CLASS: Record<DataStatus, string> = {
  LIVE: 'border-green-500/30 text-green-400',
  DEMO: 'border-amber-500/30 text-amber-400',
  SIMULATION: 'border-cyan-500/30 text-cyan-400',
  UNAVAILABLE: 'border-red-500/30 text-red-400',
  STALE: 'border-orange-500/30 text-orange-400',
  EMPTY: 'border-slate-500/30 text-slate-400',
}

const DOT_CLASS = {
  LIVE: 'bg-green-400 animate-pulse',
  DEMO: 'bg-amber-400',
  SIMULATION: 'bg-cyan-400',
  UNAVAILABLE: 'bg-red-400',
  STALE: 'bg-orange-400',
  EMPTY: 'bg-slate-500',
}

export function FreshnessBadge({ status, ageHours, source }: FreshnessBadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded border px-1.5 py-0.5 text-2xs font-mono font-medium uppercase tracking-wider',
        STATUS_CLASS[status],
      )
    }
    >
      <span className={clsx('h-1.5 w-1.5 rounded-full', DOT_CLASS[status])} />
      <span className="text-current">{status === 'DEMO' ? 'DEMO' : status}</span>
      {ageHours != null && (
        <span className="opacity-60 text-faint">+{ageHours}h</span>
      )}
      {source && (
        <span className="opacity-50 normal-case font-sans text-faint">{source}</span>
      )}
    </span>
  )
}
