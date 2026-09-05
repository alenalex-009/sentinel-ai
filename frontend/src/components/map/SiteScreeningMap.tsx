// Sentinel AI — Phase 5B SiteScreeningMap
// GIS screening-range visualization for candidate relocation sites.
// Zones are DERIVED screening ranges (PostGIS ST_Buffer via the API, demo
// fallback locally) — never official hazard boundaries. The historical
// selector shows only what actually exists per region/period.

import { useCallback, useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import { api } from '../../api/client'
import { useApiWithFallback } from '../../hooks/useApiWithFallback'
import {
  DEMO_HISTORICAL_PERIODS,
  DEMO_SCREENING_ZONES,
  DEMO_SITES_GEOJSON,
} from '../../data/screening-zone'
import type {
  HistoricalPeriod,
  HistoricalPeriodsResponse,
  ScreeningZonesResponse,
  ScreeningZoneStatus,
} from '../../types'
import clsx from 'clsx'

const ZONE_LABEL: Record<ScreeningZoneStatus, string> = {
  red: 'Exclusion / High Risk',
  yellow: 'Caution / Limited Suitability',
  green: 'Technically Suitable',
}

const STATUS_DOT: Record<ScreeningZoneStatus, string> = {
  red: 'bg-red-500',
  yellow: 'bg-yellow-500',
  green: 'bg-green-500',
}

// Minimal evented surface MapLibre raster sources expose at runtime (not
// present on the shipped `Source` typings).
type EventedSource = {
  on(type: string, listener: (e: unknown) => void): void
  off(type: string, listener: (e: unknown) => void): void
}

interface SiteScreeningMapProps {
  region?: string
  selectedSiteId?: string | null
  onSiteSelect?: (siteId: string) => void
  className?: string
}

export function SiteScreeningMap({
  region = 'kerala',
  selectedSiteId = null,
  onSiteSelect,
  className = '',
}: SiteScreeningMapProps) {
  const mapRef = useRef<maplibregl.Map | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const popupRef = useRef<maplibregl.Popup | null>(null)
  const attributionRef = useRef<maplibregl.AttributionControl | null>(null)
  const mapReadyRef = useRef(false)
  const wmsErrorRef = useRef<((e: unknown) => void) | null>(null)

  // mapReady is state (not only a ref) so effects can re-run once the map's
  // own 'load' event has fired. It must NOT be derived from
  // map.isStyleLoaded(): that stays false while a WMS raster source has
  // pending/failing tiles, which would strand period changes forever.
  const [mapReady, setMapReady] = useState(false)
  const [selectedPeriod, setSelectedPeriod] = useState<string>('current')
  const [wmsFailed, setWmsFailed] = useState(false)
  const [wmsError, setWmsError] = useState<string | null>(null)

  const zones = useApiWithFallback<ScreeningZonesResponse>(
    () => api.getScreeningZones(),
    DEMO_SCREENING_ZONES,
    [],
  )
  const history = useApiWithFallback<HistoricalPeriodsResponse>(
    () => api.getHistoricalPeriods(region),
    DEMO_HISTORICAL_PERIODS[region] ??
      { region, status: 'UNAVAILABLE', periods: [], reason: 'Unknown region.' },
    [region],
  )

  const periods = history.data?.periods ?? []
  const currentPeriod: HistoricalPeriod | undefined =
    periods.find((p) => p.period === selectedPeriod) ?? periods[0]
  const isHistorical = selectedPeriod !== 'current'
  const historicalLayer = isHistorical ? (currentPeriod?.spatial_layer ?? null) : null
  const regionUnavailable = history.data?.status === 'UNAVAILABLE'


  // ─── Map lifecycle ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
        sources: {
          osm: {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution:
              '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxzoom: 19,
          },
        },
        layers: [
          { id: 'osm-layer', type: 'raster', source: 'osm', minzoom: 0, maxzoom: 22 },
        ],
      },
      center: [77.08, 10.08],
      zoom: 11,
      attributionControl: false,
    })

    map.addControl(new maplibregl.NavigationControl(), 'top-right')
    attributionRef.current = new maplibregl.AttributionControl({ compact: true })
    map.addControl(attributionRef.current, 'bottom-right')

    map.on('load', () => {
      map.addSource('screening-zones', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      })
      map.addLayer({
        id: 'zones-fill',
        type: 'fill',
        source: 'screening-zones',
        paint: {
          'fill-color': ['match', ['get', 'status'], 'red', '#dc2626', 'yellow', '#eab308', 'green', '#16a34a', '#16a34a'],
          'fill-opacity': ['match', ['get', 'status'], 'red', 0.18, 'yellow', 0.16, 'green', 0.14, 0.14],
        },
      })
      map.addLayer({
        id: 'zones-outline',
        type: 'line',
        source: 'screening-zones',
        paint: {
          'line-color': ['match', ['get', 'status'], 'red', '#ef4444', 'yellow', '#facc15', 'green', '#4ade80', '#4ade80'],
          'line-width': 1,
          'line-opacity': 0.5,
          'line-dasharray': [2, 1.5],
        },
      })

      // Candidate-site points
      map.addSource('sites', { type: 'geojson', data: DEMO_SITES_GEOJSON })
      map.addLayer({
        id: 'sites-circle',
        type: 'circle',
        source: 'sites',
        paint: {
          'circle-radius': 7,
          'circle-color': '#0ea5e9',
          'circle-stroke-width': 2,
          'circle-stroke-color': '#f8fafc',
        },
      })
      map.addLayer({
        id: 'sites-selected',
        type: 'circle',
        source: 'sites',
        filter: ['==', ['get', 'id'], selectedSiteId ?? ''],
        paint: {
          'circle-radius': 11,
          'circle-color': 'transparent',
          'circle-stroke-width': 3,
          'circle-stroke-color': '#ffffff',
        },
      })

      // Zone click → contextual info popup
      map.on('click', 'zones-fill', (e) => {
        const f = e.features?.[0]
        if (!f) return
        const p = f.properties as Record<string, unknown>
        // MapLibre's worker stringifies nested properties — parse basis back.
        let basis: Record<string, unknown>
        const rawBasis = p.basis
        if (typeof rawBasis === 'string') {
          try { basis = JSON.parse(rawBasis) as Record<string, unknown> } catch { basis = {} }
        } else if (rawBasis && typeof rawBasis === 'object') {
          basis = rawBasis as Record<string, unknown>
        } else {
          basis = {}
        }
        const siteId = p.site_id as string
        if (popupRef.current) popupRef.current.remove()
        popupRef.current = new maplibregl.Popup({ closeButton: true, maxWidth: '300px' })
          .setLngLat(e.lngLat)
          .setHTML(
            `<div style="padding:10px;font-family:Inter,sans-serif;">
              <div style="font-size:10px;color:#64748b;margin-bottom:2px;">DERIVED SCREENING RANGE</div>
              <div style="font-size:13px;font-weight:600;color:#e2e8f0;margin-bottom:6px;">${String(p.label)}</div>
              <div style="font-size:11px;color:#cbd5e1;margin-bottom:6px;">${String(p.site_name)}</div>
              <div style="font-size:10px;color:#94a3b8;">Suitability ${String(basis.suitability_score ?? '—')} · Safety ${String(basis.safety_score ?? '—')} · C_safe ${String(basis.c_safe ?? '—')}${basis.bottleneck ? ` · Bottleneck ${String(basis.bottleneck)}` : ''}</div>
              <div style="font-size:10px;color:#64748b;margin-top:4px;">Radius ${String(p.radius_km)} km (derived)</div>
              <div style="font-size:9px;color:#475569;margin-top:4px;">${String(p.method)}</div>
              <div style="font-size:9px;color:#b45309;margin-top:4px;">NOT an official danger zone or government land approval.</div>
              ${onSiteSelect ? `<button onclick="window.sentinelInspectSite('${siteId}')" style="width:100%;margin-top:8px;padding:5px;background:#1d4ed8;color:#fff;border:none;border-radius:4px;font-size:11px;cursor:pointer;">Inspect site details →</button>` : ''}
            </div>`,
          )
          .addTo(map)
      })

      // Site point click → existing site selection
      map.on('click', 'sites-circle', (e) => {
        const id = e.features?.[0]?.properties?.id as string | undefined
        if (id) onSiteSelect?.(id)
      })
      map.on('mouseenter', 'sites-circle', () => { map.getCanvas().style.cursor = 'pointer' })
      map.on('mouseleave', 'sites-circle', () => { map.getCanvas().style.cursor = '' })
      map.on('mouseenter', 'zones-fill', () => { map.getCanvas().style.cursor = 'pointer' })
      map.on('mouseleave', 'zones-fill', () => { map.getCanvas().style.cursor = '' })
      mapReadyRef.current = true
      setMapReady(true)
    })

    ;(window as unknown as Record<string, unknown>).sentinelInspectSite = (id: string) => {
      onSiteSelect?.(id)
      if (popupRef.current) popupRef.current.remove()
    }

    mapRef.current = map
    return () => {
      map.remove()
      mapRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ─── Data / selection / period effects ──────────────────────────────────────
  const fittedRef = useRef(false)

  const applyZones = useCallback(
    (map: maplibregl.Map) => {
      if (!zones.data || !zones.data.features.length) return
      const src = map.getSource('screening-zones') as maplibregl.GeoJSONSource | undefined
      if (!src) return
      src.setData(zones.data)
      if (!fittedRef.current) {
        fittedRef.current = true
        const bounds = new maplibregl.LngLatBounds()
        zones.data.features.forEach((f) => {
          const ring = (f.geometry as GeoJSON.Polygon).coordinates[0]
          ring.forEach(([lon, lat]) => bounds.extend([lon, lat]))
        })
        map.fitBounds(bounds, { padding: 40, maxZoom: 13, duration: 600 })
      }
    },
    [zones.data],
  )

  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady) return
    applyZones(map)
  }, [applyZones, mapReady])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady) return
    if (!map.getLayer('sites-selected')) return
    map.setFilter('sites-selected', ['==', ['get', 'id'], selectedSiteId ?? ''])
  }, [selectedSiteId, mapReady])

  // Changing region must never carry a stale historical period across regions
  // (a Kerala 2019 selection must not linger when the region becomes Vizag).
  useEffect(() => {
    setSelectedPeriod('current')
  }, [region])

  // Historical period: real WMS layer when available; otherwise context only.
  // Current suitability layers are hidden for ANY historical period so current
  // and historical evidence are never mixed on the same view.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady) return

    // 1) Tear down any previous WMS overlay first (period → period, or a re-run
    //    after readiness flips). A stale 2019 Bhuvan layer/source must never
    //    survive on 2018/2021/CURRENT.
    const oldSource = map.getSource('historical-wms') as EventedSource | undefined
    if (oldSource) {
      const oldHandler = wmsErrorRef.current
      if (oldHandler) oldSource.off('error', oldHandler)
      wmsErrorRef.current = null
    }
    if (map.getLayer('historical-wms-layer')) map.removeLayer('historical-wms-layer')
    if (oldSource) {
      map.removeSource('historical-wms')
      // MapLibre recomputes attribution when a source is removed (the control
      // reacts to the source-removal data event); the explicit refresh below
      // guarantees no stale "Bhuvan / ISRO …" entry survives on context-only
      // or CURRENT periods. _updateAttributions is part of the public class
      // surface in the shipped maplibre-gl typings.
      attributionRef.current?._updateAttributions()
    }

    // 2) Show the period's real WMS overlay only when the registry actually
    //    provides one. Never synthesize a spatial layer for context-only
    //    periods (2018/2021) or for regions without historical layers.
    setWmsFailed(false)
    setWmsError(null)
    if (historicalLayer && historicalLayer.type === 'wms') {
      map.addSource('historical-wms', {
        type: 'raster',
        tiles: [historicalLayer.url],
        tileSize: 256,
        attribution: historicalLayer.attribution,
      })
      map.addLayer(
        {
          id: 'historical-wms-layer',
          type: 'raster',
          source: 'historical-wms',
          paint: { 'raster-opacity': 0.55 },
        },
        'zones-fill',
      )
      // MapLibre v4 reports non-404 tile failures on the source object itself.
      // Failure must never block period switching, but the UI must not keep
      // claiming a LIVE overlay while tiles are failing — surface it honestly.
      const onWmsError = (e: unknown) => {
        const err = (e as { error?: { status?: number; message?: string } }).error
        if (err && err.status === 404) return // 404s are handled by MapLibre internally
        setWmsError(err?.message ?? 'Bhuvan WMS tile request failed')
        setWmsFailed(true)
      }
      const src = map.getSource('historical-wms') as EventedSource | undefined
      if (src) {
        src.on('error', onWmsError)
        wmsErrorRef.current = onWmsError
      }
    }

    // 3) Current evidence vs historical evidence are never mixed: hide the
    //    derived CURRENT screening layers while a historical period is shown.
    const showCurrent = !isHistorical
    for (const layer of ['zones-fill', 'zones-outline', 'sites-circle', 'sites-selected']) {
      if (!map.getLayer(layer)) continue
      map.setLayoutProperty(layer, 'visibility', showCurrent ? 'visible' : 'none')
    }
  }, [historicalLayer, isHistorical, mapReady])

  return (
    <div className={clsx('relative overflow-hidden rounded-lg border border-slate-800', className)}>
      <div ref={containerRef} className="h-[420px] w-full" />

      {/* Legend */}
      <div className="absolute left-2 top-2 rounded bg-slate-950/85 px-2.5 py-2 text-2xs text-slate-300">
        <div className="mb-1 font-semibold uppercase tracking-wide text-slate-200">Screening Range</div>
        {(Object.keys(ZONE_LABEL) as ScreeningZoneStatus[]).map((s) => (
          <div key={s} className="flex items-center gap-1.5">
            <span className={clsx('h-2 w-2 rounded-full', STATUS_DOT[s])} />{ZONE_LABEL[s]}
          </div>
        ))}
        <div className="mt-1 flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-sky-500" />Candidate site</div>
        <div className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full ring-2 ring-white" />Selected site</div>
        <div className="mt-1.5 text-2xs text-amber-600/80">Derived ranges — not official boundaries</div>
      </div>

      {/* Historical period selector */}
      <div className="absolute right-2 top-2 flex flex-col items-end gap-1">
        <span className="rounded bg-slate-950/85 px-2 py-0.5 text-2xs font-semibold uppercase tracking-wide text-slate-400">
          Data Period · {region}
        </span>
        {periods.length > 0 && (
          <div className="flex gap-1">
            {periods.map((p) => (
              <button
                key={p.period}
                onClick={() => setSelectedPeriod(p.period)}
                className={clsx(
                  'rounded px-2 py-1 text-2xs font-medium transition-colors',
                  selectedPeriod === p.period
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-950/85 text-slate-300 hover:text-white',
                )}
              >
                {p.period === 'current' ? 'CURRENT' : p.period}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Period info card (historical selection) */}
      {currentPeriod && selectedPeriod !== 'current' && (
        <div className="absolute bottom-2 left-1/2 w-[92%] max-w-md -translate-x-1/2 rounded border border-slate-700 bg-slate-950/90 p-2.5">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-200">{currentPeriod.label}</span>
            <span className={clsx(
              'rounded px-1.5 py-0.5 text-2xs font-medium',
              historicalLayer && !wmsFailed
                ? 'bg-emerald-500/15 text-emerald-400'
                : historicalLayer && wmsFailed
                  ? 'bg-red-500/15 text-red-400'
                  : 'bg-amber-500/15 text-amber-400',
            )}>
              {historicalLayer && !wmsFailed
                ? 'LIVE OVERLAY'
                : historicalLayer && wmsFailed
                  ? 'OVERLAY FAILING'
                  : 'CONTEXT ONLY'}
            </span>
            <span className="text-2xs text-slate-500">{currentPeriod.classification}</span>
          </div>
          {currentPeriod.source && (
            <div className="mt-1 text-2xs text-slate-400">Source: {currentPeriod.source}</div>
          )}
          <p className="mt-1 text-2xs leading-relaxed text-slate-400">{currentPeriod.note}</p>
          {wmsFailed && historicalLayer && (
            <p className="mt-1 text-2xs font-medium text-red-400/90">
              Bhuvan WMS tiles failed to load ({wmsError ?? 'request error'}). The period stays
              selected and current layers stay hidden, but the overlay may be incomplete or
              unreachable.
            </p>
          )}
          {!historicalLayer && (
            <p className="mt-1 text-2xs font-medium text-amber-500/80">
              No spatial layer for this period — current suitability layers are hidden (current and historical evidence are never mixed).
            </p>
          )}
        </div>
      )}

      {/* Region unavailable note */}
      {regionUnavailable && !currentPeriod && (
        <div className="absolute bottom-2 left-1/2 w-[92%] max-w-md -translate-x-1/2 rounded border border-slate-700 bg-slate-950/90 p-2.5">
          <p className="text-2xs leading-relaxed text-slate-400">{history.data?.reason}</p>
        </div>
      )}

      {/* Attribution chips */}
      <div className="absolute bottom-1 left-2 flex flex-col gap-0.5">
        <span className="rounded bg-slate-950/80 px-1.5 py-0.5 text-2xs text-slate-600">Basemap: OpenStreetMap</span>
        <span className="rounded bg-slate-950/80 px-1.5 py-0.5 text-2xs text-amber-600">
          Zones: {zones.source === 'api' ? 'PostGIS ST_Buffer (API)' : 'DEMO fallback'} · DERIVED
        </span>
      </div>
    </div>
  )
}
