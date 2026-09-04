import clsx from 'clsx'
import type { DataType } from '../../types'

interface DataTypeBadgeProps {
  type: DataType
  size?: 'sm' | 'md'
}

const STYLES: Record<DataType, string> = {
  OBSERVED: 'text-blue-400 border-blue-500/30 bg-blue-500/8',
  DERIVED: 'text-violet-400 border-violet-500/30 bg-violet-500/8',
  ESTIMATED: 'text-amber-400 border-amber-500/30 bg-amber-500/8',
  SIMULATED: 'text-cyan-400 border-cyan-500/30 bg-cyan-500/8',
  RECOMMENDATION: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/8',
}

export function DataTypeBadge({ type, size = 'sm' }: DataTypeBadgeProps) {
  const sizeClass = size === 'sm' ? 'text-2xs px-1.5 py-0.5' : 'text-xs px-2 py-0.5'
  return (
    <span className={clsx(
      'inline-flex items-center rounded border font-mono font-medium tracking-wider uppercase',
      STYLES[type],
      sizeClass
    )}>
      {type}
    </span>
  )
}
