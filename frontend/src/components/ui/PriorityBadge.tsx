import clsx from 'clsx'
import type { Priority } from '../../types'

interface PriorityBadgeProps {
  priority: Priority
  size?: 'sm' | 'md' | 'lg'
}

const PRIORITY_STYLES: Record<Priority, string> = {
  'IMMEDIATE': 'text-red-400 border-red-500/40 bg-red-500/10',
  'SHORT-TERM': 'text-orange-400 border-orange-500/40 bg-orange-500/10',
  'MEDIUM-TERM': 'text-yellow-400 border-yellow-500/40 bg-yellow-500/10',
  'MONITOR': 'text-green-400 border-green-500/40 bg-green-500/10',
  'NONE': 'text-slate-400 border-slate-500/40 bg-slate-500/10',
}

export function PriorityBadge({ priority, size = 'md' }: PriorityBadgeProps) {
  const sizeClass = {
    sm: 'text-2xs px-1.5 py-0.5',
    md: 'text-xs px-2 py-0.5',
    lg: 'text-sm px-2.5 py-1',
  }[size]

  return (
    <span className={clsx(
      'inline-flex items-center rounded border font-semibold tracking-wide uppercase',
      PRIORITY_STYLES[priority],
      sizeClass
    )}>
      {priority}
    </span>
  )
}
