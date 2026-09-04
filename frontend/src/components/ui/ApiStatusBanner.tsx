import type { DataSource } from '../../hooks/useApiWithFallback'
import clsx from 'clsx'

interface ApiStatusBannerProps {
  source: DataSource
  error?: string | null
  className?: string
}

export function ApiStatusBanner({ source, error, className }: ApiStatusBannerProps) {
  if (source === 'loading' || source === 'api') return null

  return (
    <div className={clsx(
      'flex items-start gap-2 rounded border px-3 py-2 text-xs',
      source === 'demo_fallback'
        ? 'border-amber-500/30 bg-amber-500/8 text-amber-400'
        : 'border-red-500/30 bg-red-500/8 text-red-400',
      className
    )}>
      <span className="h-1.5 w-1.5 rounded-full mt-1 flex-shrink-0 bg-current" />
      <div>
        <span className="font-semibold">
          {source === 'demo_fallback' ? 'API unavailable — showing demo data' : 'Error'}
        </span>
        {error && <span className="ml-1 opacity-70">{error}</span>}
      </div>
    </div>
  )
}
