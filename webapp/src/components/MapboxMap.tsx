import React, { useEffect, useRef, useState } from 'react'
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css'
import type { GeometryLayers } from '../types'
import type { FlightPlan } from '../services/api'


// Retrieve token from env variables
mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN as string

interface MapboxMapProps {
  layers: GeometryLayers | null
  showAILayer?: boolean // true for admin/surveyor, false for users
  height?: string
  flightPlan?: FlightPlan | null
  achievedPoints?: [number, number][] | null
  actualPath?: [number, number][] | null
  telemetry?: any | null
  /** Optional: array of {id, visible} from left-panel toggle state */
  visibleLayers?: { id: string; visible: boolean }[]
}

// Maps our LayerId → all Mapbox GL layer IDs that should be toggled together
const LAYER_ID_MAP: Record<string, string[]> = {
  satellite:         [], // satellite is the base style, can't toggle individual layers
  cadastral:         ['cadastral-fill', 'cadastral-outline'],
  ai_boundary:       ['ai-boundary-outline'],
  approved_boundary: ['ai-boundary-outline'],
  grid:              ['flight-plan-line', 'flight-plan-points', 'flight-plan-labels'],
  photo_points:      ['achieved-coverage-circles'],
  actual_path:       ['actual-path-line'],
  blocks:            [],
  adjacent:          [],
}

export const MapboxMap: React.FC<MapboxMapProps> = ({ layers, showAILayer = false, height = '300px', flightPlan = null, achievedPoints = null, actualPath = null, telemetry = null, visibleLayers }) => {
  const mapContainer = useRef<HTMLDivElement>(null)
  const mapRef = useRef<mapboxgl.Map | null>(null)
  const [mapLoaded, setMapLoaded] = useState(false)

  const droneMarkerRef = useRef<mapboxgl.Marker | null>(null)

  useEffect(() => {
    if (!mapContainer.current || !mapboxgl.accessToken || mapRef.current) return

    // Initialize Mapbox map
    mapRef.current = new mapboxgl.Map({
      container: mapContainer.current,
      style: 'mapbox://styles/mapbox/satellite-v9',
      center: [80.6445, 16.5032], // Default fallback center (Andhra Pradesh area)
      zoom: 15,
      pitch: 45, // Slight 3D pitch
    })

    const map = mapRef.current

    map.on('load', () => {
      setMapLoaded(true)
    })

    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!mapLoaded || !mapRef.current || !layers) return
    const map = mapRef.current

    // Helper to safely remove layer and source
    const removeSourceAndLayers = (sourceId: string, layerIds: string[]) => {
      layerIds.forEach(id => {
        if (map.getLayer(id)) map.removeLayer(id)
      })
      if (map.getSource(sourceId)) map.removeSource(sourceId)
    }

    removeSourceAndLayers('cadastral', ['cadastral-fill', 'cadastral-outline'])
    removeSourceAndLayers('ai-boundary', ['ai-boundary-outline'])

    // --- CADASTRAL BOUNDARY (Official Record) ---
    if (layers.cadastral) {
      map.addSource('cadastral', {
        type: 'geojson',
        data: layers.cadastral as any,
      })

      // Cadastral fill (Sage green, semitransparent)
      map.addLayer({
        id: 'cadastral-fill',
        type: 'fill',
        source: 'cadastral',
        paint: {
          'fill-color': '#6B8F71',  // --color-sage
          'fill-opacity': 0.2,
        },
      })

      // Cadastral outline
      map.addLayer({
        id: 'cadastral-outline',
        type: 'line',
        source: 'cadastral',
        paint: {
          'line-color': '#6B8F71',  // --color-sage
          'line-width': 2,
        },
      })
      
      // Fit bounds to cadastral geometry if it exists
      try {
        const coords = (layers.cadastral.geometry.coordinates as number[][][])[0]
        if (coords && coords.length > 0) {
          const lons = coords.map(c => c[0])
          const lats = coords.map(c => c[1])
          map.fitBounds([
            [Math.min(...lons), Math.min(...lats)], // SW
            [Math.max(...lons), Math.max(...lats)]  // NE
          ], { padding: 40 })
        }
      } catch (e) {
        // Fallback if geometry parsing fails
      }
    }

    // --- AI BOUNDARY (U-Net Prediction) ---
    if (showAILayer && layers.ai_boundary) {
      map.addSource('ai-boundary', {
        type: 'geojson',
        data: layers.ai_boundary as any,
      })

      // AI outline (Terracotta red, dashed)
      map.addLayer({
        id: 'ai-boundary-outline',
        type: 'line',
        source: 'ai-boundary',
        paint: {
          'line-color': '#C97B4A',  // --color-terracotta
          'line-width': 2,
          'line-dasharray': [2, 2], // Dashed to indicate predicted
        },
      })
    }

    // --- FLIGHT PLAN (Surveyor Drone Mission) ---
    removeSourceAndLayers('flight-plan', ['flight-plan-line'])
    removeSourceAndLayers('flight-waypoints', ['flight-plan-points', 'flight-plan-labels'])

    if (flightPlan && flightPlan.waypoints && flightPlan.waypoints.length > 0) {
      const lineGeoJSON = {
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: flightPlan.waypoints }
      }
      
      map.addSource('flight-plan', {
        type: 'geojson',
        data: lineGeoJSON as any
      })
      
      map.addLayer({
        id: 'flight-plan-line',
        type: 'line',
        source: 'flight-plan',
        paint: {
          'line-color': '#111827', // --color-navy for aviation path
          'line-width': 2,
          'line-dasharray': [3, 3]
        }
      })
      
      const pointsGeoJSON = {
        type: 'FeatureCollection',
        features: flightPlan.waypoints.map((wp, i) => ({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: wp },
          properties: { label: `${i + 1}` }
        }))
      }
      
      map.addSource('flight-waypoints', {
        type: 'geojson',
        data: pointsGeoJSON as any
      })
      
      map.addLayer({
        id: 'flight-plan-points',
        type: 'circle',
        source: 'flight-waypoints',
        paint: {
          'circle-radius': 10,
          'circle-color': '#C97B4A', // --color-terracotta
          'circle-stroke-width': 2,
          'circle-stroke-color': '#ffffff'
        }
      })
      
      map.addLayer({
        id: 'flight-plan-labels',
        type: 'symbol',
        source: 'flight-waypoints',
        layout: {
          'text-field': ['get', 'label'],
          'text-size': 12,
          'text-allow-overlap': true
        },
        paint: {
          'text-color': '#ffffff'
        }
      })

      // Fit bounds to flight plan if available (overrides cadastral bounds if both exist)
      const lons = flightPlan.waypoints.map(c => c[0])
      const lats = flightPlan.waypoints.map(c => c[1])
      map.fitBounds([
        [Math.min(...lons), Math.min(...lats)],
        [Math.max(...lons), Math.max(...lats)]
      ], { padding: 60 })
    }

    removeSourceAndLayers('achieved-coverage', ['achieved-coverage-circles'])
    if (achievedPoints && achievedPoints.length > 0) {
      const achievedGeoJSON = {
        type: 'FeatureCollection',
        features: achievedPoints.map((wp) => ({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: wp },
          properties: {}
        }))
      }
      
      map.addSource('achieved-coverage', {
        type: 'geojson',
        data: achievedGeoJSON as any
      })
      
      map.addLayer({
        id: 'achieved-coverage-circles',
        type: 'circle',
        source: 'achieved-coverage',
        paint: {
          'circle-radius': 40, // Large radius for coverage shading
          'circle-color': '#2ea043', // Green tint
          'circle-opacity': 0.3,
          'circle-blur': 0.5
        }
      })
    }

    removeSourceAndLayers('actual-path', ['actual-path-line'])
    if (actualPath && actualPath.length > 1) {
      const actualPathGeoJSON = {
        type: 'Feature',
        geometry: {
          type: 'LineString',
          coordinates: actualPath
        },
        properties: {}
      }

      map.addSource('actual-path', {
        type: 'geojson',
        data: actualPathGeoJSON as any
      })

      map.addLayer({
        id: 'actual-path-line',
        type: 'line',
        source: 'actual-path',
        layout: {
          'line-join': 'round',
          'line-cap': 'round'
        },
        paint: {
          'line-color': '#00ff00', // Green dashed line
          'line-width': 2,
          'line-dasharray': [2, 2]
        }
      })
    }

  }, [layers, showAILayer, mapLoaded, flightPlan, achievedPoints, actualPath])

  // ── Layer visibility toggle ─────────────────────────────────────────────────
  useEffect(() => {
    if (!mapRef.current || !mapLoaded || !visibleLayers) return
    const map = mapRef.current
    visibleLayers.forEach(({ id, visible }) => {
      const mapboxIds = LAYER_ID_MAP[id] || []
      mapboxIds.forEach(mbId => {
        if (map.getLayer(mbId)) {
          map.setLayoutProperty(mbId, 'visibility', visible ? 'visible' : 'none')
        }
      })
    })
  }, [visibleLayers, mapLoaded])

  useEffect(() => {
    if (!mapRef.current || !mapLoaded || !telemetry) return

    if (!droneMarkerRef.current) {
      const el = document.createElement('div');
      el.className = 'live-pulse';
      el.style.width = '24px';
      el.style.height = '24px';
      el.style.background = 'var(--color-brand)';
      el.style.borderRadius = '50%';
      el.style.display = 'flex';
      el.style.alignItems = 'center';
      el.style.justifyContent = 'center';
      el.style.color = '#fff';
      el.style.fontSize = '14px';
      el.innerHTML = '<span>⬆</span>';

      droneMarkerRef.current = new mapboxgl.Marker({ element: el })
        .setLngLat([telemetry.lon, telemetry.lat])
        .setRotation(telemetry.headingDeg || 0)
        .addTo(mapRef.current);
    } else {
      droneMarkerRef.current.setLngLat([telemetry.lon, telemetry.lat])
      droneMarkerRef.current.setRotation(telemetry.headingDeg || 0)
    }

  }, [telemetry, mapLoaded])

  if (!mapboxgl.accessToken) {
    return (
      <div style={{ height, background: 'var(--color-navy)', borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'rgba(255,255,255,0.7)' }}>
        Mapbox token not configured in .env
      </div>
    )
  }

  return (
    <div style={{ position: 'relative', height, width: '100%', borderRadius: '6px', overflow: 'hidden' }}>
      <div ref={mapContainer} style={{ position: 'absolute', top: 0, bottom: 0, left: 0, right: 0 }} />
      {/* Map Legend Overlay */}
      <div style={{
        position: 'absolute', top: '10px', left: '10px', background: 'rgba(255,255,255,0.9)',
        padding: '8px 12px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 600,
        boxShadow: '0 2px 4px rgba(0,0,0,0.2)', zIndex: 1
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
          <div style={{ width: '12px', height: '12px', background: 'var(--color-sage)', border: '1px solid var(--color-sage)', opacity: 0.5 }}></div>
          <span>Cadastral (RoR)</span>
        </div>
        {showAILayer && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{ width: '12px', height: '0', borderTop: '2px dashed var(--color-terracotta)' }}></div>
            <span>AI Boundary (U-Net)</span>
          </div>
        )}
      </div>
      
      {/* Simulated Badge Overlay */}
      {(flightPlan as any)?.simulated && (
        <div style={{
          position: 'absolute', bottom: '20px', left: '50%', transform: 'translateX(-50%)',
          background: 'var(--color-terracotta)', color: 'white',
          padding: '6px 12px', borderRadius: '20px', fontSize: '0.75rem', fontWeight: 800,
          letterSpacing: '0.05em', boxShadow: '0 2px 8px rgba(201, 123, 74, 0.4)', zIndex: 1
        }}>
          SIMULATED
        </div>
      )}
    </div>
  )
}
