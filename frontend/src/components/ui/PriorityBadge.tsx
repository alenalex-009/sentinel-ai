import clsx from 'clsx'
import type { Priority } from '../../types'

interface PriorityBadgeProps {
  priority: Priority
  size?: 'sm' | 'md' | 'lg'
}

const PRIORITY_CLASS: Record<Priority, string> = {
  IMMEDIATE: 'border-red-500/35  bg-red-500/10   text-red-400',
  'SHORT-TERM': 'border-orange-500/35 bg-orange-500/10 text-orange-400',
  'MEDIUM-TERM': 'border-yellow-500/35 bg-yellow-500/10 text-yellow-400',
  MONITOR: 'border-green-500/35  bg-green-500/10   text-green-400',
  NONE: 'border-slate-600/40     bg-slate-800/40    text-slate-400',
}

const SIZE_CLASS = {
  sm: 'px-1.5 py-0.5 text-2xs',
  md: 'px-2 py-0.5 text-xs',
  lg: 'px-2.5 py-1 text-sm',
}

export function PriorityBadge({ priority, size = 'md' }: PriorityBadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded border font-semibold tracking-wide uppercase',
        PRIORITY_CLASS[priority],
        SIZE_CLASS[size],
      )
    }
    >
      {priority}
    </span>
  )
}
