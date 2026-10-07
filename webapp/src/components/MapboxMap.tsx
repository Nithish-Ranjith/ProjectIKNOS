import React, { useEffect, useRef, useState } from 'react'
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css'
import type { GeometryLayers } from '../types'
import type { FlightPlan } from '../services/api'
import { BASE, reverseGeocode } from '../services/api'

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
  onParcelClick?: (parcelId: string) => void
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

export const MapboxMap: React.FC<MapboxMapProps> = ({ layers, showAILayer = false, height = '300px', flightPlan = null, achievedPoints = null, actualPath = null, telemetry = null, visibleLayers, onParcelClick }) => {
  const mapContainer = useRef<HTMLDivElement>(null)
  const mapRef = useRef<mapboxgl.Map | null>(null)
  const [mapLoaded, setMapLoaded] = useState(false)

  const droneMarkerRef = useRef<mapboxgl.Marker | null>(null)

  useEffect(() => {
    if (!mapboxgl.accessToken) {
      console.error('Mapbox token is missing from environment variables!');
      return;
    }
    if (!mapContainer.current || mapRef.current) return;

    const initMap = (center: [number, number]) => {
      if (mapRef.current) return;
      mapRef.current = new mapboxgl.Map({
        container: mapContainer.current!,
        style: {
          version: 8,
          sources: {
            'backend-wmts': {
              type: 'raster',
              tiles: [`${BASE}/api/wmts/{z}/{x}/{y}.png`],
              tileSize: 256,
              maxzoom: 17
            }
          },
          layers: [
            {
              id: 'backend-wmts-layer',
              type: 'raster',
              source: 'backend-wmts',
              paint: { 'raster-opacity': 1.0 }
            }
          ]
        },
        center,
        zoom: 15,
        pitch: 45, // Slight 3D pitch
      });

      const map = mapRef.current;
      map.on('load', () => {
        setMapLoaded(true);
        map.resize();
      });
      
      // Wire up reverse geocode on map tap
      map.on('click', async (e) => {
        try {
          const lat = e.lngLat.lat;
          const lng = e.lngLat.lng;
          // Add a loading popup
          const popup = new mapboxgl.Popup({ closeButton: false })
            .setLngLat([lng, lat])
            .setHTML('<div style="padding: 8px; font-size: 12px; color: var(--text-2);">Loading address...</div>')
            .addTo(map);

          try {
            const data = await reverseGeocode(lat, lng);
            const address = data.address || `${data.village || ''}, ${data.mandal || ''}, ${data.district || ''}`.replace(/^, | , | ,$/g, '');
            popup.setHTML(`<div style="padding: 8px; font-size: 13px; font-weight: 500; color: #111;">
              <div style="font-size: 11px; text-transform: uppercase; color: #666; margin-bottom: 4px;">Location Info</div>
              ${address || 'Address not found'}
              <div style="font-size: 10px; color: #999; margin-top: 4px;">${lat.toFixed(5)}, ${lng.toFixed(5)}</div>
            </div>`);
          } catch (apiErr) {
            popup.setHTML('<div style="padding: 8px; font-size: 12px; color: red;">Failed to load</div>');
          }
        } catch (err) {
          console.error(err);
        }
      });
    };

    // Do not wait for geolocation (it hangs indefinitely if user ignores the prompt)
    // The layers effect will automatically fly the camera to the correct parcel bounds anyway.
    initMap([80.6445, 16.5032]);

    const resizeObserver = new ResizeObserver(() => {
      if (mapRef.current) mapRef.current.resize();
    });
    if (mapContainer.current) {
      resizeObserver.observe(mapContainer.current);
    }

    return () => {
      resizeObserver.disconnect();
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

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
    removeSourceAndLayers('ai-boundary', ['ai-boundary-fill', 'ai-boundary-outline'])

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

      if (onParcelClick) {
        map.on('click', 'cadastral-fill', (e) => {
          if (e.features && e.features[0] && e.features[0].properties) {
            // Stop the general map click event from firing the reverse geocoder
            e.preventDefault();
            onParcelClick(e.features[0].properties.parcel_id);
          }
        });
        map.on('mouseenter', 'cadastral-fill', () => {
          map.getCanvas().style.cursor = 'pointer';
        });
        map.on('mouseleave', 'cadastral-fill', () => {
          map.getCanvas().style.cursor = '';
        });
      }

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
    }
      
    // --- Fit bounds to encompass BOTH cadastral and AI boundary ---
    try {
      let allCoords: number[][] = []

      const extractCoords = (feature: any) => {
        const geom = feature?.geometry
        if (!geom) return
        const rings = geom.type === 'MultiPolygon'
          ? geom.coordinates.flat(1)
          : geom.coordinates
        rings?.forEach((ring: number[][]) => { allCoords = allCoords.concat(ring) })
      }

      extractCoords(layers.cadastral)
      if (showAILayer) extractCoords(layers.ai_boundary)

      if (allCoords.length > 0) {
        const lons = allCoords.map(c => c[0])
        const lats = allCoords.map(c => c[1])
        map.fitBounds(
          [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
          { padding: 60, duration: 800, maxZoom: 19 }
        )
      }
    } catch (e) {
      console.error('Error fitting bounds:', e)
    }

    // --- AI BOUNDARY (Spectral / U-Net Prediction) ---
    if (showAILayer && layers.ai_boundary) {
      const provenance = (layers.ai_boundary as any).properties?.provenance as string | undefined
      const isSpectral = provenance === 'SPECTRAL_EDGE_DETECTION'
      const fillColor = isSpectral ? '#E8A838' : '#C97B4A'   // amber for spectral, terracotta for ONNX

      map.addSource('ai-boundary', {
        type: 'geojson',
        data: layers.ai_boundary as any,
      })

      // Semi-transparent fill so it's clearly visible
      map.addLayer({
        id: 'ai-boundary-fill',
        type: 'fill',
        source: 'ai-boundary',
        paint: {
          'fill-color': fillColor,
          'fill-opacity': 0.18,
        },
      })

      // Dashed outline
      map.addLayer({
        id: 'ai-boundary-outline',
        type: 'line',
        source: 'ai-boundary',
        paint: {
          'line-color': fillColor,
          'line-width': 2.5,
          'line-dasharray': [3, 2],
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
      {(() => {
        const provenance = (layers?.ai_boundary as any)?.properties?.provenance as string | undefined
        const isSpectral = provenance === 'SPECTRAL_EDGE_DETECTION'
        const aiColor = isSpectral ? '#E8A838' : '#C97B4A'
        const aiLabel = isSpectral
          ? 'AI Boundary (Spectral)'
          : provenance === 'SIMULATED_PRECOMPUTED'
            ? 'AI Boundary (Simulated)'
            : 'AI Boundary (ONNX)'
        return (
          <div style={{
            position: 'absolute', top: '10px', left: '10px',
            background: 'rgba(255,255,255,0.92)',
            padding: '8px 12px', borderRadius: '6px', fontSize: '0.73rem', fontWeight: 600,
            boxShadow: '0 2px 8px rgba(0,0,0,0.18)', zIndex: 1, lineHeight: 1.6
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
              <div style={{ width: '14px', height: '14px', background: '#6B8F71', opacity: 0.5, borderRadius: '2px' }}></div>
              <span>Cadastral (RoR)</span>
            </div>
            {showAILayer && layers?.ai_boundary && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <div style={{ width: '14px', height: '0', borderTop: `3px dashed ${aiColor}` }}></div>
                <span style={{ color: aiColor }}>{aiLabel}</span>
              </div>
            )}
          </div>
        )
      })()}
      
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
