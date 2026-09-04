/**
 * useApiWithFallback — fetches from API, falls back to local seed data if unavailable.
 * Never silently replaces missing values with zeros.
 * Always shows data source (api | demo_fallback | error).
 */

import { useState, useEffect, useCallback } from 'react'

export type DataSource = 'api' | 'demo_fallback' | 'loading' | 'error'

interface UseApiWithFallbackState<T> {
  data: T | null
  loading: boolean
  error: string | null
  source: DataSource
  refetch: () => void
}

export function useApiWithFallback<T>(
  apiFetcher: () => Promise<T>,
  fallbackData: T,
  deps: unknown[] = [],
): UseApiWithFallbackState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [source, setSource] = useState<DataSource>('loading')

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    setSource('loading')
    try {
      const result = await apiFetcher()
      setData(result)
      setSource('api')
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'API unavailable'
      // Do not silently use fallback — log and label clearly
      console.warn(`[Sentinel AI] API unavailable, using demo fallback: ${msg}`)
      setData(fallbackData)
      setSource('demo_fallback')
      setError(`API unavailable — showing demo data. (${msg})`)
    } finally {
      setLoading(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => { fetch() }, [fetch])

  return { data, loading, error, source, refetch: fetch }
}
