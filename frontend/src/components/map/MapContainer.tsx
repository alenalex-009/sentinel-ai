import { useEffect, useRef, useCallback } from "react";
import maplibregl from "maplibre-gl";
import type {
  DataStatus,
  GeoJsonFeatureCollection,
  HabitationListItem,
  OSMFeatureCategory,
  Priority,
} from "../../types";
import { DEMO_HABITATIONS } from "../../data/idukki-seed";

// Risk score → color
function riskColor(score: number): string {
  if (score >= 80) return "#ef4444";
  if (score >= 60) return "#f97316";
  if (score >= 40) return "#eab308";
  return "#22c55e";
}

const EMPTY_FC: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

interface MapContainerProps {
  habitations?: HabitationListItem[];
  selectedHabitationId?: string | null;
  onHabitationSelect?: (id: string) => void;
  showHazardLayer?: boolean;
  /** PostGIS-backed GeoJSON FeatureCollection (habitation points). When present,
   *  marker geometry is taken from this API-provided data instead of the seed. */
  habitationGeoJSON?: GeoJsonFeatureCollection | null;
  /** Attribution label shown under the map describing the point source. */
  pointsSourceLabel?: string;
  /** When false, clicking a marker only selects the habitation — it does NOT
   *  also open the map popup. Pages that render their own selection card (e.g.
   *  Risk Intelligence) set this so one click never shows two overlapping
   *  popups with the same content. */
  clickPopup?: boolean;
  /** Extra GeoJSON features to draw on top (e.g. road-network routes from
   *  OSRM/GraphHopper/Valhalla). Lines use cyan; areas are filled amber. */
  routeFeature?: GeoJSON.Feature | null;
  /** Label for the route legend chip (e.g. "OSRM · 12.4 km · 18 min"). */
  routeLabel?: string | null;
  /** Active hazard polygons (from /api/v1/hazards/current feature_collection).
   *  Filled by severity_level; hidden behind the same showHazardLayer toggle
   *  as the Bhuvan historical overlay. */
  hazardGeoJSON?: GeoJSON.FeatureCollection | null;
  /** Safe-zone candidates (from GET /api/v1/spatial/safe-zones). Point layer
   *  colored by status (green/yellow/red = technically suitable / caution /
   *  exclusion). Slice 4. */
  safeZonesGeoJSON?: GeoJSON.FeatureCollection | null;
  showSafeZonesLayer?: boolean;
  /** Live OSM feature layers (Phase 6 — /api/v1/osm/{category}). Keyed by
   *  category; each value is the GeoJSON FeatureCollection to draw. When
   *  null the source stays empty; visibility follows showOsmLayers. */
  osmLayers?: Partial<Record<OSMFeatureCategory, GeoJSON.FeatureCollection | null>>;
  showOsmLayers?: boolean;
  className?: string;
}

export function MapContainer({
  habitations = DEMO_HABITATIONS,
  selectedHabitationId,
  onHabitationSelect,
  showHazardLayer = false,
  habitationGeoJSON = null,
  pointsSourceLabel = "\u25CF DEMO — Habitation points are illustrative",
  clickPopup = true,
  routeFeature = null,
  routeLabel = null,
  hazardGeoJSON = null,
  safeZonesGeoJSON = null,
  showSafeZonesLayer = false,
  osmLayers = {},
  showOsmLayers = false,
  className = "",
}: MapContainerProps) {
  const mapRef = useRef<maplibregl.Map | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);

  // Marker geometry source: PostGIS GeoJSON (API) when provided, else the
  // habitation props (seed). Missing display attributes are filled from the
  // seed so popups/labels never render undefined values.
  const markerItems: HabitationListItem[] = (() => {
    if (habitationGeoJSON && habitationGeoJSON.features?.length) {
      return habitationGeoJSON.features.map((f) => {
        const p = f.properties ?? {}
        const [lon, lat] = f.geometry.coordinates
        const seed = DEMO_HABITATIONS.find((x) => x.id === p.id)
        return {
          id: p.id,
          name: p.name ?? seed?.name ?? p.id,
          ward: p.ward ?? seed?.ward ?? "",
          taluk: p.taluk ?? seed?.taluk ?? "",
          district: seed?.district ?? "idukki",
          population: p.population ?? seed?.population ?? 0,
          risk_score: p.risk_score ?? seed?.risk_score ?? 0,
          risk_change: p.risk_change ?? 0,
          priority: (p.priority as Priority) ?? seed?.priority ?? "MONITOR",
          primary_hazard: seed?.primary_hazard ?? "LANDSLIDE",
          latitude: lat,
          longitude: lon,
          data_status: (p.data_status as DataStatus) ?? "DEMO",
        } as HabitationListItem
      })
    }
    return habitations
  })()

  const geojsonData: GeoJSON.FeatureCollection = {
    type: "FeatureCollection",
    features: markerItems.map((h) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [h.longitude, h.latitude] },
      properties: {
        id: h.id,
        name: h.name,
        ward: h.ward,
        taluk: h.taluk,
        population: h.population,
        risk_score: h.risk_score,
        risk_change: h.risk_change,
        priority: h.priority,
        primary_hazard: h.primary_hazard,
        color: riskColor(h.risk_score),
      },
    })),
  }

  const handleSelect = useCallback(
    (id: string) => onHabitationSelect?.(id),
    [onHabitationSelect],
  );

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,

      // OpenStreetMap — free raster basemap
      style: {
        version: 8,
        // CARTO Dark Matter — keyless (no API key required) basemap,
        // per instructions.md §3. OpenStreetMap was the previous
        // choice; CARTO is now the canonical keyless source.
        glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
        sources: {
          osm: {
            type: "raster",
            tiles: [
              "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
            ],
            tileSize: 256,
            attribution:
              '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
            maxzoom: 19,
          },
        },
        layers: [
          {
            id: "osm-layer",
            type: "raster",
            source: "osm",
            minzoom: 0,
            maxzoom: 22,
          },
        ],
      },
      center: [77.0595, 10.0889], // Munnar Central
      zoom: 10,
      attributionControl: false,
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");
    map.addControl(
      new maplibregl.AttributionControl({ compact: true }),
      "bottom-right",
    );

    map.on("load", () => {
      // --- Bhuvan WMS (ISRO/NRSC geospatial platform): Kerala 2019 disaster
      // event overlay. Layer `disaster:Kerala_2019_Event` was verified against
      // the live capabilities document; the previous `flood_hazard` layer name
      // never existed and the WMS returned LayerNotDefined for every tile.
      // Historical event overlay only — visual context, not a numeric risk input.
      map.addSource("bhuvan-2019", {
        type: "raster",
        tiles: [
          "https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap&LAYERS=disaster:Kerala_2019_Event&STYLES=&FORMAT=image/png&TRANSPARENT=true&SRS=EPSG:3857&WIDTH=256&HEIGHT=256&BBOX={bbox-epsg-3857}",
        ],
        tileSize: 256,
        attribution: "Bhuvan / ISRO-NRSC — Kerala 2019 event layer",
      });

      map.addLayer({
        id: "bhuvan-2019-layer",
        type: "raster",
        source: "bhuvan-2019",
        paint: { "raster-opacity": showHazardLayer ? 0.5 : 0 },
        layout: { visibility: showHazardLayer ? "visible" : "none" },
      });

      // NOTE: no district/habitation boundary polygons are drawn. The seed
      // dataset contains points only; no real boundary geometry exists yet, so
      // no approximate/decorative boundary layer is rendered.

      // --- Route overlay (multi-engine routing, Phase 5C) ---
      map.addSource("route", { type: "geojson", data: EMPTY_FC });
      map.addLayer({
        id: "route-casing",
        type: "line",
        source: "route",
        filter: ["==", ["geometry-type"], "LineString"],
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#0a0f1a", "line-width": 7, "line-opacity": 0.9 },
      });
      map.addLayer({
        id: "route-line",
        type: "line",
        source: "route",
        filter: ["==", ["geometry-type"], "LineString"],
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": "#00b4d8",
          "line-width": 4,
          "line-opacity": 0.95,
        },
      });

      // --- Active hazard polygons (Slice 2: live /api/v1/hazards/current) ---
      map.addSource("hazards", {
        type: "geojson",
        data: hazardGeoJSON ?? EMPTY_FC,
      });
      map.addLayer({
        id: "hazards-fill",
        type: "fill",
        source: "hazards",
        filter: ["==", ["geometry-type"], "Polygon"],
        paint: {
          "fill-color": [
            "match",
            ["get", "severity_level"],
            "SEVERE", "#ef4444",
            "HIGH", "#f97316",
            "MODERATE", "#eab308",
            "LOW", "#3b82f6",
            "#94a3b8",
          ],
          "fill-opacity": 0.22,
        },
        layout: { visibility: showHazardLayer ? "visible" : "none" },
      });
      map.addLayer({
        id: "hazards-outline",
        type: "line",
        source: "hazards",
        filter: ["==", ["geometry-type"], "Polygon"],
        paint: {
          "line-color": [
            "match",
            ["get", "severity_level"],
            "SEVERE", "#ef4444",
            "HIGH", "#f97316",
            "MODERATE", "#eab308",
            "LOW", "#3b82f6",
            "#94a3b8",
          ],
          "line-width": 1.5,
          "line-opacity": 0.8,
        },
        layout: { visibility: showHazardLayer ? "visible" : "none" },
      });

      // --- Safe-zone candidates (Slice 4: /api/v1/spatial/safe-zones) ---
      map.addSource("safe-zones", {
        type: "geojson",
        data: safeZonesGeoJSON ?? EMPTY_FC,
      });
      map.addLayer({
        id: "safe-zones-ring",
        type: "circle",
        source: "safe-zones",
        filter: ["==", ["geometry-type"], "Point"],
        paint: {
          "circle-radius": [
            "interpolate",
            ["linear"],
            ["zoom"],
            8,
            7,
            12,
            11,
            14,
            15,
          ],
          "circle-color": [
            "match",
            ["get", "status"],
            "green", "#22c55e",
            "yellow", "#eab308",
            "red", "#ef4444",
            "#94a3b8",
          ],
          "circle-opacity": 0.25,
          "circle-stroke-width": 1.6,
          "circle-stroke-color": [
            "match",
            ["get", "status"],
            "green", "#22c55e",
            "yellow", "#eab308",
            "red", "#ef4444",
            "#94a3b8",
          ],
        },
        layout: { visibility: showSafeZonesLayer ? "visible" : "none" },
      });

      // --- Live OpenStreetMap feature layers (Phase 6 /api/v1/osm/*) ---
      // Roads (casing + line colored by kind), buildings (fills), facilities
      // (points), water (fills + outline). Visibility is driven by the
      // showOsmLayers toggle; data arrives async via props → setData effects.
      map.addSource("osm-roads", { type: "geojson", data: (osmLayers.roads as GeoJSON.FeatureCollection) ?? EMPTY_FC });
      map.addLayer({
        id: "osm-roads-casing",
        type: "line",
        source: "osm-roads",
        filter: ["==", ["geometry-type"], "LineString"],
        layout: { "line-cap": "round", "line-join": "round", visibility: "none" },
        paint: {
          "line-color": ["match", ["get", "kind"],
            "motorway", "#f59e0b", "trunk", "#f59e0b", "primary", "#fbbf24",
            "secondary", "#a8a29e", "tertiary", "#a8a29e",
            "#cbd5e1"],
          "line-width": 5, "line-opacity": 0.35,
        },
      });
      map.addLayer({
        id: "osm-roads-line",
        type: "line",
        source: "osm-roads",
        filter: ["==", ["geometry-type"], "LineString"],
        layout: { "line-cap": "round", "line-join": "round", visibility: "none" },
        paint: {
          "line-color": ["match", ["get", "kind"],
            "motorway", "#f59e0b", "trunk", "#f59e0b", "primary", "#fbbf24",
            "secondary", "#94a3b8", "tertiary", "#94a3b8",
            "residential", "#64748b", "service", "#475569", "track", "#475569",
            "#cbd5e1"],
          "line-width": ["interpolate", ["linear"], ["zoom"], 8, 1.4, 12, 3, 15, 5.5],
          "line-opacity": 0.9,
        },
      });

      map.addSource("osm-buildings", { type: "geojson", data: (osmLayers.buildings as GeoJSON.FeatureCollection) ?? EMPTY_FC });
      map.addLayer({
        id: "osm-buildings-fill",
        type: "fill",
        source: "osm-buildings",
        filter: ["==", ["geometry-type"], "Polygon"],
        paint: { "fill-color": "#f8fafc", "fill-opacity": 0.28 },
        layout: { visibility: "none" },
      });

      map.addSource("osm-facilities", { type: "geojson", data: (osmLayers.facilities as GeoJSON.FeatureCollection) ?? EMPTY_FC });
      map.addLayer({
        id: "osm-facilities-dot",
        type: "circle",
        source: "osm-facilities",
        filter: ["==", ["geometry-type"], "Point"],
        paint: {
          "circle-radius": 4.5,
          "circle-color": "#22d3ee",
          "circle-stroke-width": 1,
          "circle-stroke-color": "#0e7490",
        },
        layout: { visibility: "none" },
      });

      map.addSource("osm-water", { type: "geojson", data: (osmLayers.water as GeoJSON.FeatureCollection) ?? EMPTY_FC });
      map.addLayer({
        id: "osm-water-fill",
        type: "fill",
        source: "osm-water",
        filter: ["==", ["geometry-type"], "Polygon"],
        paint: { "fill-color": "#38bdf8", "fill-opacity": 0.45 },
        layout: { visibility: "none" },
      });
      map.addLayer({
        id: "osm-water-outline",
        type: "line",
        source: "osm-water",
        filter: ["==", ["geometry-type"], "Polygon"],
        paint: { "line-color": "#0ea5e9", "line-width": 1.4 },
        layout: { visibility: "none" },
      });
      map.addSource("habitations", { type: "geojson", data: geojsonData });

      // Outer glow for high-risk
      map.addLayer({
        id: "habitations-glow",
        type: "circle",
        source: "habitations",
        paint: {
          "circle-radius": 18,
          "circle-color": ["get", "color"],
          "circle-opacity": 0.12,
          "circle-blur": 1,
        },
      });

      // Main circle
      map.addLayer({
        id: "habitations-circle",
        type: "circle",
        source: "habitations",
        paint: {
          "circle-radius": [
            "interpolate",
            ["linear"],
            ["zoom"],
            8,
            6,
            12,
            10,
            14,
            14,
          ],
          "circle-color": ["get", "color"],
          "circle-opacity": 0.9,
          "circle-stroke-width": 1.5,
          "circle-stroke-color": "#0a0f1a",
        },
      });

      // Labels
      map.addLayer({
        id: "habitations-label",
        type: "symbol",
        source: "habitations",
        layout: {
          "text-field": ["get", "name"],
          "text-font": ["Open Sans Semibold"],
          "text-size": 11,
          "text-offset": [0, 1.4],
          "text-anchor": "top",
        },
        paint: {
          "text-color": "#cbd5e1",
          "text-halo-color": "#0a0f1a",
          "text-halo-width": 1.5,
        },
      });

      // Click handler
      map.on("click", "habitations-circle", (e) => {
        const feature = e.features?.[0];
        if (!feature) return;
        const props = feature.properties as Record<string, unknown>;
        const id = props.id as string;
        // Selection is handled by the page (list + selection card). Only open
        // the inline map popup when the page does not render its own card,
        // otherwise one click shows two popups with identical content.
        handleSelect(id);
        if (!clickPopup) return;

        if (popupRef.current) popupRef.current.remove();

        const coords = (feature.geometry as GeoJSON.Point).coordinates as [
          number,
          number,
        ];
        const riskChange = props.risk_change as number;
        const changeStr = riskChange > 0 ? `+${riskChange}` : `${riskChange}`;
        const changeColor = riskChange > 0 ? "#ef4444" : "#22c55e";

        popupRef.current = new maplibregl.Popup({
          closeButton: true,
          maxWidth: "260px",
        })
          .setLngLat(coords)
          .setHTML(
            `
            <div style="padding:12px;font-family:Inter,sans-serif;">
              <div style="font-size:11px;color:#64748b;margin-bottom:4px;">${props.ward} · ${props.taluk}</div>
              <div style="font-size:14px;font-weight:600;color:#e2e8f0;margin-bottom:8px;">${props.name}</div>
              <div style="display:flex;gap:12px;margin-bottom:8px;">
                <div>
                  <div style="font-size:10px;color:#64748b;">RISK</div>
                  <div style="font-size:20px;font-weight:700;color:${riskColor(props.risk_score as number)};font-family:monospace;">${props.risk_score}</div>
                </div>
                <div>
                  <div style="font-size:10px;color:#64748b;">CHANGE</div>
                  <div style="font-size:20px;font-weight:700;color:${changeColor};font-family:monospace;">${changeStr}</div>
                </div>
                <div>
                  <div style="font-size:10px;color:#64748b;">POPULATION</div>
                  <div style="font-size:14px;font-weight:600;color:#cbd5e1;">${(props.population as number).toLocaleString()}</div>
                </div>
              </div>
              <div style="font-size:10px;color:#64748b;margin-bottom:8px;">Primary hazard: ${props.primary_hazard}</div>
              <button
                onclick="window.sentinelSelectHabitation('${id}')"
                style="width:100%;padding:6px;background:#1d4ed8;color:#fff;border:none;border-radius:4px;font-size:12px;cursor:pointer;font-family:Inter,sans-serif;"
              >Investigate →</button>
            </div>
          `,
          )
          .addTo(map);
      });

      map.on("mouseenter", "habitations-circle", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "habitations-circle", () => {
        map.getCanvas().style.cursor = "";
      });
    });

    mapRef.current = map;

    // Global handler for popup button
    (window as unknown as Record<string, unknown>).sentinelSelectHabitation = (
      id: string,
    ) => {
      handleSelect(id);
      if (popupRef.current) popupRef.current.remove();
    };

    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update selected habitation highlight
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    if (!map.getLayer("habitations-circle")) return;

    if (selectedHabitationId) {
      map.setPaintProperty("habitations-circle", "circle-stroke-width", [
        "case",
        ["==", ["get", "id"], selectedHabitationId],
        3,
        1.5,
      ]);
      map.setPaintProperty("habitations-circle", "circle-stroke-color", [
        "case",
        ["==", ["get", "id"], selectedHabitationId],
        "#ffffff",
        "#0a0f1a",
      ]);

      const selected = habitations.find((h) => h.id === selectedHabitationId);
      if (selected) {
        map.flyTo({
          center: [selected.longitude, selected.latitude],
          zoom: 13,
          duration: 1200,
        });
      }
    }
  }, [selectedHabitationId, habitations]);

  // Replace marker geometry when a PostGIS GeoJSON payload arrives/updates
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    const source = map.getSource("habitations") as maplibregl.GeoJSONSource | undefined;
    if (!source) return;
    source.setData(geojsonData);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [habitationGeoJSON, habitations]);

  // Route overlay: swap geometry when a new route arrives, fit bounds to it.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    const source = map.getSource("route") as maplibregl.GeoJSONSource | undefined;
    if (!source) return;

    if (routeFeature) {
      source.setData({ type: "FeatureCollection", features: [routeFeature] });
      const geom = routeFeature.geometry as GeoJSON.LineString;
      if (geom?.coordinates?.length > 1) {
        const bounds = geom.coordinates.reduce(
          (b, c) => [
            Math.min(b[0], c[0]), Math.min(b[1], c[1]),
            Math.max(b[2], c[2]), Math.max(b[3], c[3]),
          ],
          [Infinity, Infinity, -Infinity, -Infinity] as [number, number, number, number],
        );
        map.fitBounds(
          [[bounds[0], bounds[1]], [bounds[2], bounds[3]]],
          { padding: 60, duration: 900, maxZoom: 14 },
        );
      }
    } else {
      source.setData(EMPTY_FC);
    }
  }, [routeFeature]);

  // Replace active hazard geometry when the live event payload arrives/updates
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    const source = map.getSource("hazards") as maplibregl.GeoJSONSource | undefined;
    if (!source) return;
    source.setData(hazardGeoJSON ?? EMPTY_FC);
    const anyFeatures = (hazardGeoJSON?.features?.length ?? 0) > 0;
    const visibility = anyFeatures && showHazardLayer ? "visible" : "none";
    for (const layerId of ["hazards-fill", "hazards-outline"]) {
      if (!map.getLayer(layerId)) continue;
      map.setLayoutProperty(layerId, "visibility", visibility);
    }
  }, [hazardGeoJSON, showHazardLayer]);

  // Toggle hazard layer (Bhuvan historical overlay)
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    if (!map.getLayer("bhuvan-2019-layer")) return;
    map.setLayoutProperty(
      "bhuvan-2019-layer",
      "visibility",
      showHazardLayer ? "visible" : "none",
    );
    map.setPaintProperty(
      "bhuvan-2019-layer",
      "raster-opacity",
      showHazardLayer ? 0.5 : 0,
    );
  }, [showHazardLayer]);

  // Safe-zone candidates: swap geometry + toggle visibility when payload/flag
  // changes (Slice 4).
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    const source = map.getSource("safe-zones") as maplibregl.GeoJSONSource | undefined;
    if (!source) return;
    source.setData(safeZonesGeoJSON ?? EMPTY_FC);
    const anyFeatures = (safeZonesGeoJSON?.features?.length ?? 0) > 0;
    const visibility = anyFeatures && showSafeZonesLayer ? "visible" : "none";
    if (map.getLayer("safe-zones-ring")) {
      map.setLayoutProperty("safe-zones-ring", "visibility", visibility);
    }
  }, [safeZonesGeoJSON, showSafeZonesLayer]);

  // Live OSM layers: swap geometry + visibility when data or toggle changes
  // (Phase 6). Layer ids per category, hidden until the user enables the layer.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const LAYER_IDS: Record<OSMFeatureCategory, string[]> = {
      roads: ["osm-roads-casing", "osm-roads-line"],
      buildings: ["osm-buildings-fill"],
      facilities: ["osm-facilities-dot"],
      water: ["osm-water-fill", "osm-water-outline"],
    };

    for (const cat of Object.keys(LAYER_IDS) as OSMFeatureCategory[]) {
      const source = map.getSource(`osm-${cat}`) as maplibregl.GeoJSONSource | undefined;
      if (!source) continue;
      source.setData((osmLayers[cat] as GeoJSON.FeatureCollection) ?? EMPTY_FC);
      const anyFeatures = (osmLayers[cat]?.features?.length ?? 0) > 0;
      const visibility = anyFeatures && showOsmLayers ? "visible" : "none";
      for (const layerId of LAYER_IDS[cat]) {
        if (!map.getLayer(layerId)) continue;
        map.setLayoutProperty(layerId, "visibility", visibility);
      }
    }
  }, [osmLayers, showOsmLayers]);

  return (
    <div className={`relative ${className}`}>
      <div ref={containerRef} className="h-full w-full" />
      {/* Route legend chip */}
      {routeLabel && (
        <div className="absolute right-2 top-2 rounded border border-cyan-500/40 bg-slate-950/90 px-2 py-1 text-2xs font-semibold text-cyan-300">
          ⤳ {routeLabel}
        </div>
      )}
      {/* Safe-zone legend chip */}
      {showSafeZonesLayer && (safeZonesGeoJSON?.features?.length ?? 0) > 0 && (
        <div className="absolute right-2 top-10 flex items-center gap-2 rounded border border-emerald-500/40 bg-slate-950/90 px-2 py-1 text-2xs text-slate-300">
          <span className="h-2 w-2 rounded-full bg-emerald-500" />
          optional
          <span className="h-2 w-2 rounded-full bg-yellow-500" />
          caution
          <span className="h-2 w-2 rounded-full bg-red-500" />
          excluded
        </div>
      )}
      {/* OSM feature legend chip */}
      {showOsmLayers && (
        <div aria-label="OSM legend" className="absolute right-2 top-20 flex flex-col gap-1 rounded border border-cyan-500/40 bg-slate-950/90 px-2 py-1 text-2xs text-slate-300">
          <span className="flex items-center gap-1.5">
            <span className="h-1 w-4 rounded bg-amber-500" /> roads
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 bg-slate-100/70" /> buildings
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-cyan-400" /> facilities
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 bg-sky-400" /> water
          </span>
        </div>
      )}
      {/* Map attribution overlay */}
      <div className="absolute bottom-6 left-2 flex flex-col gap-1">
        <span className="rounded bg-slate-950/80 px-1.5 py-0.5 text-2xs text-slate-600">
          Basemap: CARTO Dark Matter (OpenStreetMap data)
        </span>
        <span className="rounded bg-slate-950/80 px-1.5 py-0.5 text-2xs text-amber-600">
          {pointsSourceLabel}
        </span>
      </div>
    </div>
  );
}
