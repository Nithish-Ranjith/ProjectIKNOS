import React, { useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import MapboxDraw from '@mapbox/mapbox-gl-draw';
import 'maplibre-gl/dist/maplibre-gl.css';
import '@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css';
import type { GeoJSONFeature } from '../types';
import { getSatelliteStyle } from '../services/mapConfig';
import { MapProviderBadge } from './MapProviderBadge';

// Maps our UI layer IDs → Mapbox/MapLibre GL layer IDs that exist on this map instance
const BOUNDARY_LAYER_ID_MAP: Record<string, string[]> = {
  satellite:         [], // satellite is the base style — cannot toggle individual layers
  cadastral:         ['cadastral-layer'],
  ai_boundary:       [
    'gl-draw-polygon-stroke-inactive.cold', 
    'gl-draw-polygon-stroke-inactive.hot',
    'gl-draw-polygon-fill-inactive.cold', 
    'gl-draw-polygon-fill-inactive.hot', 
    'gl-draw-polygon-stroke-active.cold',
    'gl-draw-polygon-stroke-active.hot'
  ],
  approved_boundary: [
    'gl-draw-polygon-stroke-inactive.cold', 
    'gl-draw-polygon-stroke-inactive.hot',
    'gl-draw-polygon-fill-inactive.cold', 
    'gl-draw-polygon-fill-inactive.hot'
  ],
  grid:              [],
  photo_points:      [],
  actual_path:       [],
  blocks:            [],
  adjacent:          [],
};

interface BoundaryEditorProps {
  cadastral: GeoJSONFeature | null;
  aiBoundary: GeoJSONFeature | null;
  onBoundaryEdit?: (feature: GeoJSONFeature) => void;
  /** Passed from LeftContextPanel toggle state — drives layer visibility on the WebGL canvas */
  visibleLayers?: { id: string; visible: boolean }[];
}

export const BoundaryEditor: React.FC<BoundaryEditorProps> = ({
  cadastral,
  aiBoundary,
  onBoundaryEdit,
  visibleLayers,
}) => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef       = useRef<maplibregl.Map | null>(null);
  const drawRef      = useRef<MapboxDraw | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);
  const onBoundaryEditRef = useRef(onBoundaryEdit);
  
  useEffect(() => {
    onBoundaryEditRef.current = onBoundaryEdit;
  }, [onBoundaryEdit]);

  // ── EFFECT 1: Initialize map canvas (runs once on mount) ────────────────
  useEffect(() => {
    if (mapRef.current || !mapContainer.current) return;

    const mapInstance = new maplibregl.Map({
      container: mapContainer.current,
      style: getSatelliteStyle(),
      center: [80.648, 16.506],
      zoom: 17,
      pitch: 0,
      bearing: 0,
    });

    // Wire Draw plugin for polygon editing
    const drawInstance = new MapboxDraw({
      displayControlsDefault: false,
      controls: { polygon: true, trash: true },
      defaultMode: 'simple_select',
      styles: [
        {
          id: 'gl-draw-polygon-fill-inactive',
          type: 'fill',
          filter: ['all', ['==', '$type', 'Polygon'], ['==', 'active', 'false']],
          paint: { 'fill-color': '#E8EDF4', 'fill-opacity': 0.12 },
        },
        {
          id: 'gl-draw-polygon-fill-active',
          type: 'fill',
          filter: ['all', ['==', '$type', 'Polygon'], ['==', 'active', 'true']],
          paint: { 'fill-color': '#E8EDF4', 'fill-opacity': 0.18 },
        },
        {
          id: 'gl-draw-polygon-stroke-active',
          type: 'line',
          filter: ['all', ['==', '$type', 'Polygon'], ['==', 'active', 'true']],
          layout: { 'line-cap': 'round', 'line-join': 'round' },
          paint: { 'line-color': '#58A6FF', 'line-dasharray': [2, 2], 'line-width': 3 },
        },
        {
          id: 'gl-draw-polygon-stroke-inactive',
          type: 'line',
          filter: ['all', ['==', '$type', 'Polygon'], ['==', 'active', 'false']],
          layout: { 'line-cap': 'round', 'line-join': 'round' },
          paint: { 'line-color': '#E8EDF4', 'line-dasharray': [2, 2], 'line-width': 3 },
        },
        {
          id: 'gl-draw-polygon-and-line-vertex-active',
          type: 'circle',
          filter: ['all', ['==', 'meta', 'vertex'], ['==', '$type', 'Point']],
          paint: {
            'circle-radius': 6,
            'circle-color': '#111520',
            'circle-stroke-width': 2,
            'circle-stroke-color': '#58A6FF',
          },
        },
      ],
    });

    mapInstance.addControl(drawInstance as unknown as maplibregl.IControl, 'top-left');

    // Emit boundary edits back to parent (ParcelStep → SurveyorMission state)
    const emitEdit = () => {
      if (!drawInstance) return;
      const collection = drawInstance.getAll();
      if (collection.features.length > 0 && onBoundaryEditRef.current) {
        onBoundaryEditRef.current(collection.features[0] as GeoJSONFeature);
      }
    };
    mapInstance.on('draw.create' as any, emitEdit);
    mapInstance.on('draw.delete' as any, emitEdit);
    mapInstance.on('draw.update' as any, emitEdit);

    mapInstance.on('load', () => {
      setMapLoaded(true);
      mapInstance.resize();
    });

    mapRef.current  = mapInstance;
    drawRef.current = drawInstance;

    const resizeObserver = new ResizeObserver(() => {
      if (mapRef.current) mapRef.current.resize();
    });
    if (mapContainer.current) {
      resizeObserver.observe(mapContainer.current);
    }

    return () => {
      resizeObserver.disconnect();
      mapRef.current?.remove();
      mapRef.current  = null;
      drawRef.current = null;
    };
  }, []);

  // ── EFFECT 2: Layer visibility toggling ──────────────────────────────────────
  useEffect(() => {
    if (!mapRef.current || !mapLoaded || !visibleLayers) return;
    const map = mapRef.current;

    visibleLayers.forEach(({ id, visible }) => {
      const glLayerIds = BOUNDARY_LAYER_ID_MAP[id] ?? [];
      glLayerIds.forEach((glId) => {
        if (map.getLayer(glId)) {
          map.setLayoutProperty(glId, 'visibility', visible ? 'visible' : 'none');
        }
      });
    });
  }, [visibleLayers, mapLoaded]);

  // ── EFFECT 3: Data injection — runs when cadastral / AI data arrives from API ─
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded) return;

    const injectData = () => {
      // Add cadastral boundary as a styled line layer
      if (cadastral) {
        if (map.getLayer('cadastral-layer')) map.removeLayer('cadastral-layer');
        if (map.getSource('cadastral-src')) map.removeSource('cadastral-src');

        map.addSource('cadastral-src', { type: 'geojson', data: cadastral as any });
        map.addLayer({
          id: 'cadastral-layer',
          type: 'line',
          source: 'cadastral-src',
          paint: {
            'line-color': '#4A7CBF', // steel-blue
            'line-width': 2.5,
            'line-dasharray': [4, 4],
          },
        });

        // Fly to parcel bounding box after data loads
        try {
          const coords = (cadastral.geometry.coordinates as number[][][])[0];
          if (coords?.length > 0) {
            const lons = coords.map((c) => c[0]);
            const lats = coords.map((c) => c[1]);
            map.fitBounds(
              [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
              { padding: 60, duration: 800, maxZoom: 18 }
            );
          }
        } catch (_) {
          // Non-fatal — map stays at initial center
        }
      }

      // Populate Draw plugin with AI boundary for user to edit
      if (aiBoundary && drawRef.current) {
        drawRef.current.deleteAll();
        const ids = drawRef.current.add(aiBoundary as any);
        if (ids?.length > 0) {
          drawRef.current.changeMode('direct_select', { featureId: ids[0] });
        }
      }
    };

    if (map.isStyleLoaded()) {
      injectData();
    } else {
      map.on('load', injectData);
      return () => { map.off('load', injectData); };
    }
  }, [cadastral, aiBoundary, mapLoaded]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div ref={mapContainer} style={{ width: '100%', height: '100%' }} />

      {/* Map Satellite Provider & Diagnostic Badge */}
      <MapProviderBadge />

      {/* Map Legend */}
      <div style={{
        position: 'absolute', top: '1.5rem', right: '1.5rem',
        background: 'rgba(17, 21, 32, 0.85)', backdropFilter: 'blur(8px)',
        border: '1px solid rgba(232,237,244,0.2)', padding: '0.75rem',
        borderRadius: '6px', fontFamily: 'var(--font-ui)', fontSize: '0.75rem',
        display: 'flex', flexDirection: 'column', gap: '0.5rem', zIndex: 1,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ width: '20px', borderBottom: '2px dashed #4A7CBF' }} />
          <span style={{ color: 'var(--color-text-secondary)' }}>Cadastral (Old)</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ width: '20px', borderBottom: '2px dashed #E8EDF4' }} />
          <span style={{ color: 'var(--color-text-secondary)' }}>AI Boundary / Edited</span>
        </div>
      </div>
    </div>
  );
};
export default BoundaryEditor;
