import clsx from 'clsx'

interface RiskBadgeProps {
  score: number
  size?: 'sm' | 'md' | 'lg' | 'xl'
  showLabel?: boolean
}

function getRiskColor(score: number) {
  if (score >= 80) return 'text-red-400 border-red-500/40 bg-red-500/10'
  if (score >= 60) return 'text-orange-400 border-orange-500/40 bg-orange-500/10'
  if (score >= 40) return 'text-yellow-400 border-yellow-500/40 bg-yellow-500/10'
  return 'text-green-400 border-green-500/40 bg-green-500/10'
}

function getRiskLabel(score: number) {
  if (score >= 80) return 'CRITICAL'
  if (score >= 60) return 'HIGH'
  if (score >= 40) return 'MEDIUM'
  return 'LOW'
}

export function RiskBadge({ score, size = 'md', showLabel = false }: RiskBadgeProps) {
  const color = getRiskColor(score)
  const sizeClass = {
    sm: 'text-xs px-1.5 py-0.5',
    md: 'text-sm px-2 py-1',
    lg: 'text-base px-3 py-1.5',
    xl: 'text-2xl px-4 py-2 font-bold',
  }[size]

  return (
    <span className={clsx('inline-flex items-center gap-1.5 rounded border font-mono font-semibold', color, sizeClass)}>
      {score}
      {showLabel && <span className="text-2xs font-sans font-normal opacity-70">{getRiskLabel(score)}</span>}
    </span>
  )
}
