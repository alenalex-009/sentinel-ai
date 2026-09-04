import { useEffect, useRef, useCallback } from "react";
import maplibregl from "maplibre-gl";
import type { HabitationListItem } from "../../types";
import { DEMO_HABITATIONS } from "../../data/idukki-seed";

// Risk score → color
function riskColor(score: number): string {
  if (score >= 80) return "#ef4444";
  if (score >= 60) return "#f97316";
  if (score >= 40) return "#eab308";
  return "#22c55e";
}

interface MapContainerProps {
  habitations?: HabitationListItem[];
  selectedHabitationId?: string | null;
  onHabitationSelect?: (id: string) => void;
  showHazardLayer?: boolean;
  className?: string;
}

export function MapContainer({
  habitations = DEMO_HABITATIONS,
  selectedHabitationId,
  onHabitationSelect,
  showHazardLayer = false,
  className = "",
}: MapContainerProps) {
  const mapRef = useRef<maplibregl.Map | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);

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
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution:
              '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
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
      // --- Bhuvan WMS: Flood Hazard Layer (ISRO/NRSC) ---
      // Added as WMS source — will show UNAVAILABLE if Bhuvan is unreachable
      map.addSource("bhuvan-flood", {
        type: "raster",
        tiles: [
          "https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap&LAYERS=flood_hazard&STYLES=&FORMAT=image/png&TRANSPARENT=true&SRS=EPSG:3857&WIDTH=256&HEIGHT=256&BBOX={bbox-epsg-3857}",
        ],
        tileSize: 256,
        attribution: "Bhuvan / ISRO-NRSC (DEMO)",
      });

      map.addLayer({
        id: "bhuvan-flood-layer",
        type: "raster",
        source: "bhuvan-flood",
        paint: { "raster-opacity": showHazardLayer ? 0.5 : 0 },
        layout: { visibility: showHazardLayer ? "visible" : "none" },
      });

      // --- Idukki district boundary (approximate GeoJSON) ---
      map.addSource("idukki-boundary", {
        type: "geojson",
        data: {
          type: "Feature",
          geometry: {
            type: "Polygon",
            // Approximate Idukki district boundary for demo
            coordinates: [
              [
                [76.7, 9.8],
                [77.4, 9.8],
                [77.4, 10.45],
                [76.7, 10.45],
                [76.7, 9.8],
              ],
            ],
          },
          properties: { name: "Idukki District" },
        },
      });

      map.addLayer({
        id: "idukki-boundary-line",
        type: "line",
        source: "idukki-boundary",
        paint: {
          "line-color": "#3b82f6",
          "line-width": 1.5,
          "line-opacity": 0.6,
          "line-dasharray": [4, 2],
        },
      });

      // --- Habitation points ---
      const geojson: GeoJSON.FeatureCollection = {
        type: "FeatureCollection",
        features: habitations.map((h) => ({
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
      };

      map.addSource("habitations", { type: "geojson", data: geojson });

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
          "text-font": ["Open Sans Regular"],
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
        handleSelect(id);

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

  // Toggle hazard layer
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    if (!map.getLayer("bhuvan-flood-layer")) return;
    map.setLayoutProperty(
      "bhuvan-flood-layer",
      "visibility",
      showHazardLayer ? "visible" : "none",
    );
    map.setPaintProperty(
      "bhuvan-flood-layer",
      "raster-opacity",
      showHazardLayer ? 0.5 : 0,
    );
  }, [showHazardLayer]);

  return (
    <div className={`relative ${className}`}>
      <div ref={containerRef} className="h-full w-full" />
      {/* Map attribution overlay */}
      <div className="absolute bottom-6 left-2 flex flex-col gap-1">
        <span className="rounded bg-slate-950/80 px-1.5 py-0.5 text-2xs text-slate-600">
          Basemap: OpenStreetMap
        </span>
        <span className="rounded bg-slate-950/80 px-1.5 py-0.5 text-2xs text-amber-600">
          ● DEMO — Habitation points are illustrative
        </span>
      </div>
    </div>
  );
}
