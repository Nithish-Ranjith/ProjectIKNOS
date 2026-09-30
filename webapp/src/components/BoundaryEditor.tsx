import React, { useEffect, useRef } from 'react';
import mapboxgl from 'mapbox-gl';
import MapboxDraw from '@mapbox/mapbox-gl-draw';
import '@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css';
import type { GeoJSONFeature } from '../types';

// Hardcoded demo token for local run
mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN || '';

interface BoundaryEditorProps {
  cadastral: GeoJSONFeature | null;
  aiBoundary: GeoJSONFeature | null;
  onBoundaryEdit?: (feature: GeoJSONFeature) => void;
}

export const BoundaryEditor: React.FC<BoundaryEditorProps> = ({ cadastral, aiBoundary, onBoundaryEdit }) => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<mapboxgl.Map | null>(null);
  const draw = useRef<MapboxDraw | null>(null);

  useEffect(() => {
    if (map.current || !mapContainer.current) return;

    // Use a center point based on cadastral or default
    let center: [number, number] = [80.648, 16.506];
    if (cadastral?.geometry.type === 'Polygon') {
      const coords = cadastral.geometry.coordinates as number[][][];
      if (coords[0] && coords[0][0]) {
        center = [coords[0][0][0], coords[0][0][1]];
      }
    }

    map.current = new mapboxgl.Map({
      container: mapContainer.current,
      style: 'mapbox://styles/mapbox/satellite-v9', // Satellite base
      center,
      zoom: 18,
      pitch: 0,
      bearing: 0,
    });

    // Initialize Mapbox Draw
    draw.current = new MapboxDraw({
      displayControlsDefault: false,
      controls: {
        polygon: true,
        trash: true
      },
      defaultMode: 'simple_select',
      styles: [
        // Active polygon fill
        {
          id: 'gl-draw-polygon-fill-active',
          type: 'fill',
          filter: ['all', ['==', '$type', 'Polygon'], ['==', 'active', 'true']],
          paint: {
            'fill-color': '#E8EDF4',
            'fill-opacity': 0.1
          }
        },
        // Active polygon stroke
        {
          id: 'gl-draw-polygon-stroke-active',
          type: 'line',
          filter: ['all', ['==', '$type', 'Polygon'], ['==', 'active', 'true']],
          layout: { 'line-cap': 'round', 'line-join': 'round' },
          paint: {
            'line-color': '#E8EDF4', // ink-100
            'line-dasharray': [2, 2],
            'line-width': 3
          }
        },
        // Inactive polygon stroke (edited boundary when deselected)
        {
          id: 'gl-draw-polygon-stroke-inactive',
          type: 'line',
          filter: ['all', ['==', '$type', 'Polygon'], ['==', 'active', 'false']],
          layout: { 'line-cap': 'round', 'line-join': 'round' },
          paint: {
            'line-color': '#E8EDF4',
            'line-dasharray': [2, 2],
            'line-width': 3
          }
        },
        // Vertex points
        {
          id: 'gl-draw-polygon-and-line-vertex-active',
          type: 'circle',
          filter: ['all', ['==', 'meta', 'vertex'], ['==', '$type', 'Point']],
          paint: {
            'circle-radius': 6,
            'circle-color': '#111520',
            'circle-stroke-width': 2,
            'circle-stroke-color': '#E8EDF4'
          }
        }
      ]
    });

    map.current.addControl(draw.current, 'top-left');

    const updateBoundary = () => {
      if (!draw.current) return;
      const data = draw.current.getAll();
      if (data.features.length > 0 && onBoundaryEdit) {
        onBoundaryEdit(data.features[0] as GeoJSONFeature);
      }
    };

    map.current.on('draw.create', updateBoundary);
    map.current.on('draw.delete', updateBoundary);
    map.current.on('draw.update', updateBoundary);

    return () => {
      map.current?.remove();
      map.current = null;
    };
  }, []); // Run ONLY once to initialize map

  // Second useEffect to handle data injection when API returns
  useEffect(() => {
    if (!map.current || !map.current.isStyleLoaded()) return;

    const mapInstance = map.current;

    const injectData = () => {
      if (cadastral && mapInstance && !mapInstance.getSource('cadastral-src')) {
        mapInstance.addSource('cadastral-src', {
          type: 'geojson',
          data: cadastral as any
        });
        mapInstance.addLayer({
          id: 'cadastral-layer',
          type: 'line',
          source: 'cadastral-src',
          paint: {
            'line-color': '#4A7CBF', // steel-blue
            'line-width': 2,
            'line-dasharray': [4, 4]
          }
        });
        
        // Center the map on the parcel
        try {
          const coords = (cadastral.geometry.coordinates as number[][][])[0];
          if (coords && coords.length > 0) {
            const lons = coords.map(c => c[0]);
            const lats = coords.map(c => c[1]);
            mapInstance.fitBounds([
              [Math.min(...lons), Math.min(...lats)], // SW
              [Math.max(...lons), Math.max(...lats)]  // NE
            ], { padding: 60 });
          }
        } catch (e) {
          // ignore parsing error
        }
      }

      if (aiBoundary && draw.current) {
        // Clear previous to avoid duplicates if it updates
        draw.current.deleteAll();
        const featureIds = draw.current.add(aiBoundary as any);
        if (featureIds && featureIds.length > 0) {
          draw.current.changeMode('direct_select', { featureId: featureIds[0] });
        }
      }
    };

    if (mapInstance.loaded()) {
      injectData();
    } else {
      mapInstance.on('load', injectData);
    }

  }, [cadastral, aiBoundary]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div ref={mapContainer} style={{ width: '100%', height: '100%' }} />
      
      {/* Legend */}
      <div style={{
        position: 'absolute',
        top: '1.5rem',
        right: '1.5rem',
        background: 'rgba(17, 21, 32, 0.85)',
        backdropFilter: 'blur(8px)',
        border: '1px solid var(--color-text-primary)',
        padding: '0.75rem',
        borderRadius: '4px',
        fontFamily: 'var(--font-ui)',
        fontSize: '0.75rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.5rem',
        zIndex: 1
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ width: '20px', borderBottom: '2px dashed var(--color-navy)' }}></div>
          <span style={{ color: 'var(--color-text-secondary)' }}>Cadastral (Old)</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ width: '20px', borderBottom: '2px dashed var(--color-border)' }}></div>
          <span style={{ color: 'var(--color-text-secondary)' }}>AI Boundary / Edited</span>
        </div>
      </div>
    </div>
  );
};
