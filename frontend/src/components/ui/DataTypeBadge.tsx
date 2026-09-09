import clsx from 'clsx'
import type { DataType } from '../../types'

interface DataTypeBadgeProps {
  type: DataType
  size?: 'sm' | 'md'
}

const TYPE_CLASS: Record<DataType, string> = {
  OBSERVED: 'border-blue-500/30 bg-blue-500/8   text-blue-300',
  DERIVED: 'border-violet-500/30 bg-violet-500/8 text-violet-300',
  ESTIMATED: 'border-amber-500/30 bg-amber-500/8 text-amber-300',
  SIMULATED: 'border-cyan-500/30 bg-cyan-500/8 text-cyan-300',
  RECOMMENDATION: 'border-emerald-500/30 bg-emerald-500/8 text-emerald-300',
}

const SIZE_CLASS = {
  sm: 'px-1.5 py-0.5 text-2xs',
  md: 'px-2 py-0.5 text-xs',
}

export function DataTypeBadge({ type, size = 'sm' }: DataTypeBadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded border font-mono font-medium tracking-wider uppercase',
        TYPE_CLASS[type],
        SIZE_CLASS[size],
      )
    }
    >
      {type}
    </span>
  )
}
