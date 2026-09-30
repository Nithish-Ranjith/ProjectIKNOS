import type { MissionViewState } from '../../types/mission';

interface Props {
  state: MissionViewState;
}

export function MapWorkspace({ state }: Props) {
  return (
    <div className="panel-center" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
      
      {/* Map Background with Satellite Base */}
      <div style={{ 
        flex: 1, position: 'relative', overflow: 'hidden',
        background: 'url("https://images.unsplash.com/photo-1595180453535-24268fa3d664?auto=format&fit=crop&q=80&w=1200&h=800")',
        backgroundSize: 'cover'
      }}>
        
        {/* Dark overlay to simulate drone view contrast */}
        <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.3)' }} />
        
        {/* Placeholder for Mapbox GL Canvas overlays */}
        <div style={{ 
          position: 'absolute', inset: 0, 
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'rgba(255,255,255,0.2)', fontSize: '14px', pointerEvents: 'none'
        }}>
          [Map Rendering Abstraction]
        </div>

        {/* Top Left Compass */}
        <div style={{
          position: 'absolute', top: 'var(--spacing-xl)', left: 'var(--spacing-xl)',
          width: 32, height: 32, borderRadius: '50%', background: 'rgba(22, 27, 34, 0.7)',
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          color: '#fff', fontSize: '12px', fontWeight: 600, border: '1px solid rgba(255,255,255,0.1)'
        }}>
          N
        </div>

        {/* Mock Drone Overlay */}
        {state.state === 'FLYING' && state.telemetry && (
          <div className="live-pulse" style={{ 
            position: 'absolute', 
            top: '50%', left: '50%', 
            transform: `translate(-50%, -50%) rotate(${state.telemetry.headingDeg}deg)`,
            width: 24, height: 24,
            background: 'var(--color-brand)',
            borderRadius: '50%',
            display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <span style={{ fontSize: '14px' }}>⬆</span>
          </div>
        )}

        {/* Map Legend */}
        <div style={{ 
          position: 'absolute', bottom: 'var(--spacing-xl)', left: 'var(--spacing-xl)',
          background: 'rgba(22, 27, 34, 0.85)', backdropFilter: 'blur(10px)',
          border: '1px solid var(--color-border)',
          padding: 'var(--spacing-lg)', borderRadius: 'var(--radius-md)',
          boxShadow: 'var(--shadow-subtle)',
          fontSize: '11px', display: 'flex', flexDirection: 'column', gap: '8px', color: 'var(--color-text-primary)'
        }}>
          <div style={{ fontWeight: 600, marginBottom: '6px' }}>Legend</div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
             <div style={{ width: 16, height: 0, borderBottom: '2px dashed var(--map-cadastral)' }} />
             <span>Cadastral Boundary (Old)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
             <div style={{ width: 16, height: 2, background: 'var(--map-approved)' }} />
             <span>Adjusted Boundary (U-Net)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
             <div style={{ width: 16, height: 0, borderBottom: '1px dashed var(--color-text-secondary)' }} />
             <span>Parcel Split Block</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
             <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--map-point-planned)', marginLeft: 4 }} />
             <span style={{ marginLeft: 4 }}>Planned Photo Point</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
             <div style={{ width: 10, height: 10, borderRadius: '50%', background: 'var(--map-point-next)', border: '2px solid #000', marginLeft: 3 }} />
             <span style={{ marginLeft: 3 }}>Next Photo Point</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
             <span style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '1px' }}>DRN</span>
             <span>Drone (Live)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
             <div style={{ width: 16, height: 2, background: 'var(--map-planned-path)' }} />
             <span>Planned Path</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
             <div style={{ width: 16, height: 0, borderBottom: '2px dashed var(--map-actual-path)' }} />
             <span>Actual Path</span>
          </div>
        </div>

        {/* Map Scale */}
        <div style={{
          position: 'absolute', bottom: 'var(--spacing-xl)', right: 'var(--spacing-xl)',
          display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px',
          color: '#fff', fontSize: '10px'
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-end', borderBottom: '1px solid #fff', height: '6px', width: '200px' }}>
            <div style={{ flex: 1, borderLeft: '1px solid #fff', height: '6px' }} />
            <div style={{ flex: 1, borderLeft: '1px solid #fff', height: '6px' }} />
            <div style={{ flex: 1, borderLeft: '1px solid #fff', height: '6px' }} />
            <div style={{ flex: 1, borderLeft: '1px solid #fff', borderRight: '1px solid #fff', height: '6px' }} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', width: '200px', transform: 'translateX(4px)' }}>
            <span>0</span><span>50</span><span>100</span><span>200 m</span>
          </div>
        </div>

        {/* Map Controls Stack */}
        <div style={{ 
          position: 'absolute', top: 'var(--spacing-xl)', right: 'var(--spacing-xl)',
          display: 'flex', flexDirection: 'column', gap: '8px'
        }}>
          <button style={{ width: 40, height: 40, padding: 0, background: 'rgba(22, 27, 34, 0.8)', backdropFilter: 'blur(8px)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 'var(--radius-md)', color: '#fff', fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', cursor: 'pointer' }}>
            Lyr
          </button>
          <button style={{ width: 40, height: 40, padding: 0, background: 'rgba(22, 27, 34, 0.8)', backdropFilter: 'blur(8px)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 'var(--radius-md)', color: '#fff', fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', cursor: 'pointer' }}>
            Tgt
          </button>
          <div style={{ display: 'flex', flexDirection: 'column', background: 'rgba(22, 27, 34, 0.8)', backdropFilter: 'blur(8px)', borderRadius: 'var(--radius-md)', overflow: 'hidden', marginTop: '16px', border: '1px solid rgba(255,255,255,0.1)' }}>
            <button style={{ width: 40, height: 40, padding: 0, background: 'transparent', border: 'none', borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#fff', fontSize: '18px', cursor: 'pointer' }}>
              +
            </button>
            <button style={{ width: 40, height: 40, padding: 0, background: 'transparent', border: 'none', color: '#fff', fontSize: '18px', cursor: 'pointer' }}>
              -
            </button>
          </div>
        </div>

      </div>

    </div>
  );
}
