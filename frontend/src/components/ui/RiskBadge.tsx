import clsx from 'clsx'

interface RiskBadgeProps {
  score: number
  size?: 'sm' | 'md' | 'lg' | 'xl'
  showLabel?: boolean
}

function severityClass(score: number): string {
  if (score >= 80) return 'border-red-500/35 bg-red-500/10 text-red-400'
  if (score >= 60) return 'border-orange-500/35 bg-orange-500/10 text-orange-400'
  if (score >= 40) return 'border-yellow-500/35 bg-yellow-500/10 text-yellow-400'
  return 'border-green-500/35 bg-green-500/10 text-green-400'
}

function severityLabel(score: number): string {
  if (score >= 80) return 'CRITICAL'
  if (score >= 60) return 'HIGH'
  if (score >= 40) return 'MEDIUM'
  return 'LOW'
}

const SIZE_CLASS = {
  sm: 'px-1.5 py-0.5 text-xs',
  md: 'px-2 py-1 text-sm',
  lg: 'px-3 py-1.5 text-base',
  xl: 'px-4 py-2 text-xl font-bold',
}

export function RiskBadge({ score, size = 'md', showLabel = false }: RiskBadgeProps) {
  return (
    <span
      className={
        clsx(
          'inline-flex items-center gap-1.5 rounded border font-mono font-semibold',
          severityClass(score),
          SIZE_CLASS[size],
        )
      }
    >
      <span className="text-number">{score}</span>
      {showLabel && (
        <span className="text-2xs font-medium tracking-wide uppercase opacity-70">
          {severityLabel(score)}
        </span>
      )}
    </span>
  )
}
