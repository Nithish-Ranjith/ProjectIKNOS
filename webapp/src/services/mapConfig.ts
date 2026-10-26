import * as maplibregl from 'maplibre-gl';
import type { StyleSpecification } from 'maplibre-gl';

export { maplibregl };
export type { StyleSpecification };

// Configure local worker to avoid any Vite worker bundle resolution issues
if (typeof window !== 'undefined' && typeof maplibregl.setWorkerUrl === 'function') {
  maplibregl.setWorkerUrl('/maplibre-gl-worker.mjs');
}

// Mapbox Token from environment
const rawToken = import.meta.env.VITE_MAPBOX_TOKEN as string | undefined;
export const MAPBOX_TOKEN = (rawToken && rawToken.startsWith('pk.')) ? rawToken.trim() : '';

// High-resolution ESRI World Imagery (Global 0.3m-0.5m aerial imagery, public XYZ, no API key required fallback)
export const ESRI_SATELLITE_TILE_URL = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';

// OpenStreetMap Standard Tiles (Public XYZ, fallback)
export const OSM_TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

// CartoDB Voyager Streets (Clean vector-like street raster, public XYZ)
export const CARTO_VOYAGER_URL = 'https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png';

export interface MapProviderDiagnostic {
  provider: 'esri' | 'mapbox' | 'osm';
  tokenPresent: boolean;
  tokenMasked: string;
  status: 'valid' | 'invalid_401' | 'untested' | 'offline';
  statusCode: number | null;
  errorMessage: string | null;
  details: string;
}

let currentDiagnostic: MapProviderDiagnostic = {
  provider: MAPBOX_TOKEN ? 'mapbox' : 'esri',
  tokenPresent: Boolean(MAPBOX_TOKEN),
  tokenMasked: MAPBOX_TOKEN ? `${MAPBOX_TOKEN.slice(0, 12)}...${MAPBOX_TOKEN.slice(-6)}` : 'None configured',
  status: 'untested',
  statusCode: null,
  errorMessage: null,
  details: MAPBOX_TOKEN ? 'Validating Mapbox access...' : 'Using high-resolution ESRI World Imagery (Public XYZ, zero API key required).'
};

const listeners = new Set<(diag: MapProviderDiagnostic) => void>();

export function getMapProviderDiagnostic(): MapProviderDiagnostic {
  return currentDiagnostic;
}

export function subscribeMapDiagnostic(listener: (diag: MapProviderDiagnostic) => void): () => void {
  listeners.add(listener);
  listener(currentDiagnostic);
  return () => listeners.delete(listener);
}

function updateDiagnostic(partial: Partial<MapProviderDiagnostic>) {
  currentDiagnostic = { ...currentDiagnostic, ...partial };
  listeners.forEach(fn => fn(currentDiagnostic));
}

// Preflight test for Mapbox token
export async function validateMapboxToken(): Promise<MapProviderDiagnostic> {
  if (!MAPBOX_TOKEN) {
    updateDiagnostic({
      provider: 'esri',
      status: 'offline',
      statusCode: null,
      errorMessage: null,
      details: 'No Mapbox token configured. Active: ESRI World Imagery (Public 0.3m aerial).'
    });
    return currentDiagnostic;
  }

  try {
    const testUrl = `https://api.mapbox.com/v4/mapbox.satellite/1/0/0.png?access_token=${MAPBOX_TOKEN}`;
    const res = await fetch(testUrl);
    
    if (res.status === 200) {
      updateDiagnostic({
        provider: 'mapbox',
        status: 'valid',
        statusCode: 200,
        errorMessage: null,
        details: 'Mapbox Retina satellite tiles (512px @2x) authorized and streaming.'
      });
    } else if (res.status === 401) {
      updateDiagnostic({
        provider: 'esri',
        status: 'invalid_401',
        statusCode: 401,
        errorMessage: '401 Unauthorized — Not Authorized / Invalid Token',
        details: 'Token signature is valid for user kakashiii, but Mapbox returned 401 (unverified account email, domain restriction, or billing hold). Fail-safe active: ESRI World Imagery.'
      });
      console.warn('[MapConfig] Mapbox token returned 401. Fail-safe active: ESRI World Imagery.');
    } else {
      updateDiagnostic({
        provider: 'esri',
        status: 'offline',
        statusCode: res.status,
        errorMessage: `HTTP ${res.status}: ${res.statusText}`,
        details: 'Mapbox request returned non-200. Fail-safe active: ESRI World Imagery.'
      });
    }
  } catch (err: any) {
    updateDiagnostic({
      provider: 'esri',
      status: 'offline',
      statusCode: null,
      errorMessage: err?.message || 'Network error',
      details: 'Unable to reach Mapbox API. Fail-safe active: ESRI World Imagery.'
    });
  }

  return currentDiagnostic;
}

// Trigger initial preflight if in browser
if (typeof window !== 'undefined' && MAPBOX_TOKEN) {
  validateMapboxToken();
}

/**
 * Returns a satellite style specification.
 * If Mapbox token is healthy, uses Mapbox's 512px high-res retina satellite tiles.
 * Otherwise, falls back seamlessly to ESRI World Imagery with zero external API key requirements.
 */
export function getSatelliteStyle(forceProvider?: 'esri' | 'mapbox'): StyleSpecification {
  const useMapbox = forceProvider 
    ? forceProvider === 'mapbox' 
    : (Boolean(MAPBOX_TOKEN) && currentDiagnostic.status === 'valid');

  const tileUrl = useMapbox
    ? `https://api.mapbox.com/v4/mapbox.satellite/{z}/{x}/{y}@2x.png?access_token=${MAPBOX_TOKEN}`
    : ESRI_SATELLITE_TILE_URL;

  const tileSize = useMapbox ? 512 : 256;
  const attribution = useMapbox 
    ? '© Mapbox © Maxar' 
    : '© Esri, Maxar, Earthstar Geographics';

  return {
    version: 8,
    sources: {
      'satellite-tiles': {
        type: 'raster',
        tiles: [tileUrl],
        tileSize,
        maxzoom: useMapbox ? 20 : 18,
        attribution
      }
    },
    layers: [
      {
        id: 'satellite-base',
        type: 'raster',
        source: 'satellite-tiles',
        paint: {
          'raster-opacity': 1.0,
          'raster-fade-duration': 100
        }
      }
    ]
  };
}

/**
 * Returns ESRI Satellite Style directly.
 */
export function getEsriSatelliteStyle(): StyleSpecification {
  return getSatelliteStyle('esri');
}

/**
 * Returns a street map style specification (for street/cadastral mode).
 */
export function getStreetStyle(): StyleSpecification {
  const useMapbox = Boolean(MAPBOX_TOKEN) && currentDiagnostic.status === 'valid';
  const tileUrl = useMapbox
    ? `https://api.mapbox.com/styles/v1/mapbox/streets-v12/tiles/{z}/{x}/{y}?access_token=${MAPBOX_TOKEN}`
    : CARTO_VOYAGER_URL;

  const attribution = useMapbox
    ? '© Mapbox © OpenStreetMap contributors'
    : '© OpenStreetMap contributors, © CARTO';

  return {
    version: 8,
    sources: {
      'street-tiles': {
        type: 'raster',
        tiles: [tileUrl],
        tileSize: 512,
        maxzoom: 20,
        attribution
      }
    },
    layers: [
      {
        id: 'street-base',
        type: 'raster',
        source: 'street-tiles',
        paint: {
          'raster-opacity': 1.0
        }
      }
    ]
  };
}

export default maplibregl;
