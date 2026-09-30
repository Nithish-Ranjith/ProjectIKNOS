import React, { useState, useEffect, useRef } from 'react';
import { fetchSatelliteTimeseries } from '../services/api';
import { AlertTriangle } from 'lucide-react';

// Map NDVI to HSL colour (green→amber→red gradient)
function ndviToHSL(ndvi: number): string {
  const hue = Math.round(ndvi * 90);        // 0→red(0), 0.6→green(54), 1→green(90)
  const sat = 40;
  const lig = Math.round(8 + ndvi * 12);    // 8–20% lightness keeps it dark
  return `hsl(${hue}, ${sat}%, ${lig}%)`;
}

// Map SAR VH to HSL colour (dark→bright)
function sarToHSL(sar: number): string {
  // Typical SAR VH range: -25 (smooth/dark) to -5 (rough/bright)
  const normalized = Math.max(0, Math.min(1, (sar + 25) / 20));
  const lig = Math.round(10 + normalized * 60);
  return `hsl(0, 0%, ${lig}%)`;
}

// Mini sparkline for Trend
function Sparkline({ data, color }: { data: number[], color: string }) {
  const W = 120, H = 28;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 0.01;

  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * W;
    const y = H - ((v - min) / range) * (H - 4) - 2;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  const area = `M 0,${H} L ${pts.split(' ').map(p => {
    const [x, y] = p.split(',');
    return `${x},${y}`;
  }).join(' L ')} L ${W},${H} Z`;

  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ overflow: 'visible' }}>
      <defs>
        <linearGradient id={`gradient-${color.replace(/[^\w-]/g, '')}`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor={color} stopOpacity="0.1" />
          <stop offset="100%" stopColor={color} stopOpacity="0.4" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#gradient-${color.replace(/[^\w-]/g, '')})`} />
      <polyline
        points={pts}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {/* Last point dot */}
      {(() => {
        const last = pts.split(' ').pop()!.split(',');
        return <circle cx={last[0]} cy={last[1]} r="2.5" fill={color} />;
      })()}
    </svg>
  );
}

interface Props { parcelId: string }

export const SentinelTimelapse: React.FC<Props> = ({ parcelId }) => {
  const [index, setIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [activeBand, setActiveBand] = useState<'NDVI' | 'SAR'>('NDVI');
  const [timeseries, setTimeseries] = useState<any[]>([]);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (parcelId) {
      fetchSatelliteTimeseries(parcelId)
        .then(data => {
          setTimeseries(data);
          setIndex(data.length - 1);
        })
        .catch(console.error);
    }
  }, [parcelId]);

  // Playback
  useEffect(() => {
    if (isPlaying && timeseries.length > 0) {
      intervalRef.current = setInterval(() => {
        setIndex(i => i >= timeseries.length - 1 ? 0 : i + 1);
      }, 300);
    } else {
      clearInterval(intervalRef.current ?? undefined);
    }
    return () => clearInterval(intervalRef.current ?? undefined);
  }, [isPlaying, timeseries.length]);

  if (timeseries.length === 0) return <div style={{ padding: '20px', color: 'var(--color-text-secondary)', textAlign: 'center', fontSize: '12px' }}>Loading Satellite Data...</div>;

  const currentData = timeseries[index];
  const dateStr = currentData.date.substring(0, 7); // YYYY-MM

  const ndviValues = timeseries.map(d => d.ndvi);
  const sarValues = timeseries.map(d => d.sar_vh);

  const prevNDVI = timeseries[Math.max(0, index - 1)].ndvi;
  const currentNDVI = currentData.ndvi;
  const deltaNDVI = ((currentNDVI - prevNDVI) / prevNDVI * 100).toFixed(1);
  const trendNDVIColor = currentNDVI < prevNDVI ? 'var(--color-warning)' : 'var(--color-sage)';


  const currentSAR = currentData.sar_vh;

  
  // Pixel grid visualisation — 8×6 grid simulating satellite tile
  const COLS = 12, ROWS = 8;
  const cells = Array.from({ length: ROWS * COLS }, (_, i) => {
    const row = Math.floor(i / COLS);
    const col = i % COLS;
    
    // Fake spatial variation using deterministic noise
    const noise = Math.sin(row * 1.7 + col * 2.3) * 0.12 + Math.cos(row * 0.8 - col * 1.4) * 0.08;
    
    if (activeBand === 'NDVI') {
        const v = Math.max(0.05, Math.min(0.99, currentNDVI + noise));
        return ndviToHSL(v);
    } else {
        const v = currentSAR + (noise * 5);
        return sarToHSL(v);
    }
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <div style={{ fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.05em', color: 'var(--color-text-secondary)' }}>SATELLITE TIMELAPSE</div>
        
        {/* Toggle NDVI / SAR */}
        <div style={{ display: 'flex', background: 'var(--color-bg)', borderRadius: 'var(--radius-pill)', padding: '2px', border: '1px solid var(--color-border)' }}>
          <button 
            onClick={() => setActiveBand('NDVI')}
            style={{ 
              background: activeBand === 'NDVI' ? 'var(--color-surface)' : 'transparent',
              color: activeBand === 'NDVI' ? 'var(--color-brand)' : 'var(--color-text-secondary)',
              border: 'none', padding: '2px 8px', fontSize: '10px', borderRadius: 'var(--radius-pill)', cursor: 'pointer', fontWeight: 600
            }}
          >
            OPTICAL (NDVI)
          </button>
          <button 
            onClick={() => setActiveBand('SAR')}
            style={{ 
              background: activeBand === 'SAR' ? 'var(--color-surface)' : 'transparent',
              color: activeBand === 'SAR' ? 'var(--color-active)' : 'var(--color-text-secondary)',
              border: 'none', padding: '2px 8px', fontSize: '10px', borderRadius: 'var(--radius-pill)', cursor: 'pointer', fontWeight: 600
            }}
          >
            RADAR (SAR)
          </button>
        </div>
      </div>

      {/* ── Satellite Tile Viewer ───────────────────── */}
      <div style={{
        position: 'relative',
        borderRadius: '4px',
        overflow: 'hidden',
        border: '1px solid var(--color-border)',
        marginBottom: '12px',
      }}>
        {/* Pixel grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${COLS}, 1fr)`,
          height: '110px',
          gap: '1px',
          background: 'var(--color-border)',
          transition: 'opacity 0.4s',
        }}>
          {cells.map((color, i) => (
            <div
              key={i}
              style={{
                background: color,
                transition: 'background 0.3s ease',
              }}
            />
          ))}
        </div>

        {/* Date overlay */}
        <div style={{
          position: 'absolute', top: '8px', left: '10px',
          fontFamily: 'var(--font-mono)', fontSize: '1.1rem',
          fontWeight: 700, color: 'rgba(230,237,246,0.85)',
          textShadow: '0 1px 4px rgba(0,0,0,0.8)',
          letterSpacing: '0.05em'
        }}>{dateStr}</div>
      </div>

      {/* ── Playback controls + scrubber ──────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
        <button
          onClick={() => setIsPlaying(p => !p)}
          style={{
            background: isPlaying ? 'transparent' : 'var(--color-surface)',
            border: `1px solid ${isPlaying ? 'var(--color-active)' : 'var(--color-border)'}`,
            color: isPlaying ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
            padding: '4px 10px', borderRadius: '3px',
            fontSize: '0.68rem', fontFamily: 'var(--font-mono)',
            cursor: 'pointer', flexShrink: 0
          }}
        >
          {isPlaying ? '⏸ PAUSE' : '▶ PLAY'}
        </button>

        <input
          type="range" min="0" max={timeseries.length - 1} step="1" value={index}
          onChange={e => { setIndex(Number(e.target.value)); setIsPlaying(false); }}
          style={{ flex: 1, accentColor: 'var(--color-active)', cursor: 'pointer' }}
        />

        <span style={{ fontSize: '0.65rem', fontFamily: 'var(--font-mono)', color: 'var(--color-text-secondary)', flexShrink: 0 }}>
          {dateStr}
        </span>
      </div>

      {/* ── Trend sparkline ───────────────────── */}
      <div style={{
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: '4px',
        padding: '10px 12px',
        marginBottom: '10px'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
          <div>
            <div style={{ fontSize: '0.6rem', color: 'var(--color-text-secondary)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '2px' }}>
              {activeBand === 'NDVI' ? 'NDVI Trend' : 'SAR VH Backscatter Trend'}
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
              <span style={{ fontSize: '1.2rem', fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--color-text-primary)' }}>
                {activeBand === 'NDVI' ? currentNDVI.toFixed(2) : currentSAR.toFixed(1)}
              </span>
              <span style={{ fontSize: '0.65rem', color: activeBand === 'NDVI' ? trendNDVIColor : 'var(--color-text-primary)', fontFamily: 'var(--font-mono)' }}>
                {activeBand === 'NDVI' ? `${parseFloat(deltaNDVI) > 0 ? '+' : ''}${deltaNDVI}%` : `${currentSAR.toFixed(1)} dB`}
              </span>
            </div>
          </div>
        </div>

        {/* Sparkline */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Sparkline 
             data={activeBand === 'NDVI' ? ndviValues : sarValues} 
             color={activeBand === 'NDVI' ? 'var(--color-brand)' : 'var(--color-active)'} 
          />
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginLeft: '12px' }}>
            {['2019', '2024'].map((y, i) => (
              <div key={y} style={{ fontSize: '0.6rem', fontFamily: 'var(--font-mono)', color: 'var(--color-text-secondary)' }}>
                {y}: <span style={{ color: 'var(--color-text-secondary)' }}>
                  {activeBand === 'NDVI' 
                    ? ndviValues[i === 0 ? 0 : ndviValues.length - 1].toFixed(2) 
                    : sarValues[i === 0 ? 0 : sarValues.length - 1].toFixed(1)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
      
      {/* ── Instability alert ──────────────────────── */}
      {currentNDVI < 0.4 && (
        <div style={{
          background: 'transparent',
          border: '1px solid var(--color-warning)',
          borderRadius: '4px',
          padding: '8px 12px',
          fontSize: '0.72rem',
          color: 'var(--color-warning)',
          display: 'flex',
          alignItems: 'center',
          gap: '6px'
        }}>
          <AlertTriangle size={14} />
          <span>Significant vegetation drop detected. Field verification recommended.</span>
        </div>
      )}
    </div>
  );
};
