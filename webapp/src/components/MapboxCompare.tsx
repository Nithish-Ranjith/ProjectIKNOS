import React, { useEffect, useRef, useState } from 'react'
import mapboxgl from 'mapbox-gl'
import type { GeometryLayers } from '../types'

mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN as string

interface MapboxCompareProps {
  layers: GeometryLayers | null
  height?: string
}

export const MapboxCompare: React.FC<MapboxCompareProps> = ({ layers, height = '350px' }) => {
  const map1Container = useRef<HTMLDivElement>(null)
  const map2Container = useRef<HTMLDivElement>(null)
  
  const map1Ref = useRef<mapboxgl.Map | null>(null)
  const map2Ref = useRef<mapboxgl.Map | null>(null)
  
  const [sliderPos, setSliderPos] = useState(50)

  useEffect(() => {
    if (!map1Container.current || !map2Container.current || !mapboxgl.accessToken || map1Ref.current) return

    const center: [number, number] = [80.6445, 16.5032]

    // Base map (Right side / Cadastral)
    map1Ref.current = new mapboxgl.Map({
      container: map1Container.current,
      style: 'mapbox://styles/mapbox/satellite-streets-v12',
      center,
      zoom: 15.5,
      pitch: 0, 
    })

    // Top map (Left side / AI Boundary)
    map2Ref.current = new mapboxgl.Map({
      container: map2Container.current,
      style: 'mapbox://styles/mapbox/satellite-streets-v12',
      center,
      zoom: 15.5,
      pitch: 0,
      interactive: false // Only base map is interactive
    })

    const map1 = map1Ref.current
    const map2 = map2Ref.current

    // Sync maps
    map1.on('move', () => {
      map2.jumpTo({
        center: map1.getCenter(),
        zoom: map1.getZoom(),
        bearing: map1.getBearing(),
        pitch: map1.getPitch()
      })
    })

    // Wait for both to load
    let loadedCount = 0
    const onLoad = () => {
      loadedCount++
      if (loadedCount === 2 && layers) {
        map1.resize()
        map2.resize()
        // --- ADD CADASTRAL TO BASE MAP ---
        if (layers.cadastral) {
          map1.addSource('cadastral', { type: 'geojson', data: layers.cadastral as any })
          map1.addLayer({
            id: 'cadastral-fill', type: 'fill', source: 'cadastral',
            paint: { 'fill-color': '#6B8F71', 'fill-opacity': 0.3 }
          })
          map1.addLayer({
            id: 'cadastral-outline', type: 'line', source: 'cadastral',
            paint: { 'line-color': '#6B8F71', 'line-width': 3 }
          })
          
          try {
            const coords = (layers.cadastral.geometry.coordinates as number[][][])[0]
            if (coords && coords.length > 0) {
              const lons = coords.map(c => c[0])
              const lats = coords.map(c => c[1])
              const bounds = new mapboxgl.LngLatBounds(
                [Math.min(...lons), Math.min(...lats)],
                [Math.max(...lons), Math.max(...lats)]
              )
              map1.fitBounds(bounds, { padding: 50, duration: 0 })
              map2.fitBounds(bounds, { padding: 50, duration: 0 })
            }
          } catch (e) {}
        }

        // --- ADD AI BOUNDARY TO TOP MAP ---
        if (layers.ai_boundary) {
          map2.addSource('ai-boundary', { type: 'geojson', data: layers.ai_boundary as any })
          map2.addLayer({
            id: 'ai-outline', type: 'line', source: 'ai-boundary',
            paint: {
              'line-color': '#C97B4A',  // --color-terracotta
              'line-width': 3,
              'line-dasharray': [2, 2]
            }
          })
        }
      }
    }

    map1.on('load', onLoad)
    map2.on('load', onLoad)

    const resizeObserver = new ResizeObserver(() => {
      if (map1Ref.current) map1Ref.current.resize()
      if (map2Ref.current) map2Ref.current.resize()
    })
    
    if (map1Container.current) resizeObserver.observe(map1Container.current)
    if (map2Container.current) resizeObserver.observe(map2Container.current)

    return () => {
      resizeObserver.disconnect()
      map1.remove()
      map2.remove()
      map1Ref.current = null
      map2Ref.current = null
    }
  }, [layers])

  return (
    <div style={{ position: 'relative', height, width: '100%', borderRadius: '8px', overflow: 'hidden', background: '#000' }}>
      
      {/* Base Map (Cadastral) */}
      <div ref={map1Container} style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }} />
      
      {/* Top Map (AI) with Clip Path */}
      <div 
        ref={map2Container} 
        style={{ 
          position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
          clipPath: `inset(0 ${100 - sliderPos}% 0 0)` // Shows from left (0) up to sliderPos% width
        }} 
      />

      {/* Slider Overlay */}
      <input 
        type="range" min="0" max="100" value={sliderPos}
        onChange={(e) => setSliderPos(Number(e.target.value))}
        style={{
          position: 'absolute', top: '50%', left: 0, width: '100%',
          transform: 'translateY(-50%)', zIndex: 10,
          margin: 0, opacity: 0, cursor: 'ew-resize'
        }}
      />
      
      {/* Visual Slider Bar */}
      <div style={{
        position: 'absolute', top: 0, bottom: 0, left: `${sliderPos}%`, width: '4px',
        background: '#fff', transform: 'translateX(-50%)', zIndex: 5, pointerEvents: 'none',
        boxShadow: '0 0 10px rgba(0,0,0,0.5)'
      }}>
        {/* Thumb */}
        <div style={{
          position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
          width: '24px', height: '24px', borderRadius: '50%', background: '#fff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 2px 4px rgba(0,0,0,0.4)', color: 'var(--color-terracotta)'
        }}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <path d="M8 9l-4 3 4 3M16 15l4-3-4-3"/>
          </svg>
        </div>
      </div>

      {/* Labels */}
      <div style={{ position: 'absolute', top: '10px', left: '10px', background: 'rgba(255,255,255,0.9)', padding: '6px 10px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 600, zIndex: 2 }}>
        <span style={{ color: 'var(--color-terracotta)' }}>← Drone AI Boundary</span>
      </div>
      <div style={{ position: 'absolute', top: '10px', right: '10px', background: 'rgba(255,255,255,0.9)', padding: '6px 10px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 600, zIndex: 2 }}>
        <span style={{ color: '#4a7c59' }}>Official Record (RoR) →</span>
      </div>
    </div>
  )
}
