import type { MissionViewState, MissionState } from '../../types/mission';
import { useNavigate, useParams } from 'react-router-dom';

interface Props {
  state: MissionViewState;
  onTransition: (newState: MissionState) => void;
}

export function RightOperationsPanel({ state, onTransition }: Props) {
  const navigate = useNavigate();
  const { id } = useParams();
  
  return (
    <div className="panel-right" style={{ width: 360, display: 'flex', flexDirection: 'column', gap: '0', background: 'var(--color-bg)', borderLeft: '1px solid var(--color-border)', overflowY: 'auto' }}>
      
      {/* Live Drone Status */}
      <div className="card" style={{ padding: 'var(--spacing-lg) var(--spacing-xl)', background: 'transparent', border: 'none', borderRadius: 0, borderBottom: '1px solid var(--color-border)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--spacing-md)' }}>
          <h3 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-primary)' }}>Live Drone Status</h3>
          <span style={{ 
            display: 'flex', alignItems: 'center', gap: '4px',
            background: 'transparent', border: '1px solid var(--color-brand)', color: 'var(--color-brand)', 
            padding: '2px 8px', borderRadius: 'var(--radius-pill)', 
            fontSize: '10px', fontWeight: 600 
          }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--color-brand)' }} />
            ON TRACK
          </span>
        </div>
        
        <div style={{ display: 'flex', gap: 'var(--spacing-lg)' }}>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span className="text-muted">Lat</span>
              <span className="font-mono">{state.telemetry?.lat?.toFixed(6) || '16.306521'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span className="text-muted">Lon</span>
              <span className="font-mono">{state.telemetry?.lon?.toFixed(6) || '79.986732'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span className="text-muted">Alt</span>
              <span className="font-mono">{state.telemetry?.altM?.toFixed(1) || '62.3'} m</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span className="text-muted">Speed</span>
              <span className="font-mono">{state.telemetry?.speedMps?.toFixed(1) || '4.8'} m/s</span>
            </div>
          </div>

          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', borderLeft: '1px solid var(--color-border)' }}>
             <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-primary)' }}>DRIFT: 1.2M</div>
             <div style={{ fontSize: '10px', color: 'var(--color-text-secondary)', textTransform: 'uppercase' }}>To Next Point</div>
          </div>
        </div>

        {/* Capture Target */}
        <div style={{ marginTop: 'var(--spacing-xl)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <div style={{ width: 12, height: 24, background: 'var(--color-active)', borderRadius: '2px' }} />
            <div>
              <div className="text-muted" style={{ fontSize: '10px' }}>Next Photo Point</div>
              <div style={{ fontWeight: 600, fontSize: '13px' }}>B5-3</div>
            </div>
          </div>
          <div>
            <div className="text-muted" style={{ fontSize: '10px' }}>Distance</div>
            <div style={{ fontWeight: 600, fontSize: '13px' }}>18 m</div>
          </div>
          <div>
            <div className="text-muted" style={{ fontSize: '10px' }}>ETA</div>
            <div style={{ fontWeight: 600, fontSize: '13px' }}>6 s</div>
          </div>
        </div>
      </div>

      {/* AI Boundary (U-Net) Map Card */}
      <div className="card" style={{ padding: 'var(--spacing-lg) var(--spacing-xl)', background: 'transparent', border: 'none', borderRadius: 0, borderBottom: '1px solid var(--color-border)' }}>
        <h3 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: 'var(--spacing-md)' }}>AI Boundary (U-Net)</h3>
        <div style={{ display: 'flex', gap: '16px' }}>
          <div style={{ width: 120, height: 80, background: 'var(--color-border)', borderRadius: 'var(--radius-sm)', backgroundSize: 'cover', backgroundImage: 'url("https://images.unsplash.com/photo-1595180453535-24268fa3d664?auto=format&fit=crop&q=80&w=200&h=150")' }}>
             <div style={{ width: '100%', height: '100%', border: '2px solid var(--color-brand)', clipPath: 'polygon(10% 20%, 90% 10%, 100% 90%, 20% 100%)', background: 'rgba(46, 160, 67, 0.2)' }} />
          </div>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '12px' }}>
             <div>
               <div className="text-muted" style={{ fontSize: '10px' }}>Confidence</div>
               <div className="text-brand" style={{ fontWeight: 700, fontSize: '18px' }}>0.87</div>
             </div>
             <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '10px' }}>
               <div style={{ width: 16, height: 6, background: 'var(--color-brand)', borderRadius: '2px' }} /> Detected Boundary
             </div>
             <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '10px' }}>
               <div style={{ width: 16, height: 0, borderBottom: '2px dashed var(--color-text-secondary)' }} /> Cadastral (Old)
             </div>
             <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '10px' }}>
               <div style={{ width: 16, height: 2, background: 'var(--color-brand)' }} /> Adjusted (Approved)
             </div>
          </div>
        </div>
      </div>

      {/* Survey Plan Summary */}
      <div className="card" style={{ padding: 'var(--spacing-lg) var(--spacing-xl)', background: 'transparent', border: 'none', borderRadius: 0, borderBottom: '1px solid var(--color-border)' }}>
        <h3 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: 'var(--spacing-md)' }}>Lawnmower Plan</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '13px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span className="text-muted">Total Blocks</span>
            <span style={{ fontWeight: 500 }}>9</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span className="text-muted">Photo Points</span>
            <span style={{ fontWeight: 500 }}>54</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span className="text-muted">Flight Lines</span>
            <span style={{ fontWeight: 500 }}>6</span>
          </div>
          <div style={{ display: 'flex', gap: '16px', marginTop: '4px' }}>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '6px' }}>
                <span className="text-muted">Coverage (Est.)</span>
                <span className="text-brand" style={{ fontWeight: 700 }}>98%</span>
              </div>
              <div style={{ height: '4px', background: 'var(--color-surface)', borderRadius: '2px', overflow: 'hidden' }}>
                <div style={{ height: '100%', width: '98%', background: 'var(--color-brand)' }} />
              </div>
            </div>
            <div style={{ width: '80px', textAlign: 'right' }}>
              <div className="text-muted" style={{ fontSize: '11px', marginBottom: '2px' }}>Est. Time</div>
              <div style={{ fontWeight: 600, fontSize: '13px' }}>12 min</div>
            </div>
          </div>
        </div>
      </div>

      {/* Block Sequence */}
      <div className="card" style={{ padding: 'var(--spacing-lg) var(--spacing-xl)', flex: 1, display: 'flex', flexDirection: 'column', background: 'transparent', border: 'none', borderRadius: 0 }}>
        <h3 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: 'var(--spacing-md)' }}>Block Sequence</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', overflowY: 'auto' }}>
          {[
            { id: 'B1', status: 'Completed', progress: 100 },
            { id: 'B2', status: 'Completed', progress: 100 },
            { id: 'B3', status: 'In Progress', progress: 60 },
            { id: 'B4', status: 'Pending', progress: 0 },
            { id: 'B5', status: 'Pending', progress: 0 },
          ].map(block => {
            const isCompleted = block.status === 'Completed';
            const isInProgress = block.status === 'In Progress';
            return (
              <div key={block.id} style={{ display: 'flex', alignItems: 'center', gap: '16px', padding: '6px 0', background: 'transparent' }}>
                <div style={{ 
                  width: 32, height: 20, borderRadius: '2px', 
                  background: isCompleted ? 'var(--color-brand)' : isInProgress ? 'var(--color-active)' : 'transparent',
                  border: isCompleted || isInProgress ? 'none' : '1px solid var(--color-text-secondary)',
                  color: isCompleted ? '#000' : '#fff', fontSize: '9px', fontWeight: 700, 
                  display: 'flex', alignItems: 'center', justifyContent: 'center', textTransform: 'uppercase'
                }}>
                  {isCompleted ? 'OK' : isInProgress ? 'ON' : 'NO'}
                </div>
                <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--color-text-primary)' }}>{block.id}</div>
                <div style={{ width: '80px', fontSize: '12px', color: isCompleted ? 'var(--color-brand)' : isInProgress ? 'var(--color-active)' : 'var(--color-text-secondary)' }}>
                  {block.status}
                </div>
                <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div style={{ flex: 1, height: '4px', background: 'var(--color-surface)', borderRadius: '2px', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${block.progress}%`, background: isCompleted ? 'var(--color-brand)' : 'var(--color-active)' }} />
                  </div>
                  <span style={{ color: 'var(--color-text-secondary)', fontSize: '11px', fontWeight: 600, cursor: 'pointer', textTransform: 'uppercase' }}>Clear</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── PRIMARY MISSION CTA — Full state machine, every transition covered ── */}
      <div style={{ padding: 'var(--spacing-lg) var(--spacing-xl)', borderTop: '1px solid var(--color-border)', display: 'flex', flexDirection: 'column', gap: 8 }}>

        {/* Pre-flight */}
        {state.state === 'BOUNDARY_APPROVED' && (
          <button className="btn btn-primary" style={{ width: '100%' }} onClick={() => onTransition('PLANNING')}>
            Generate Survey Plan
          </button>
        )}
        {state.state === 'PLANNING' && (
          <button className="btn btn-primary" style={{ width: '100%' }} onClick={() => onTransition('READY')}>
            Review &amp; Approve Plan
          </button>
        )}
        {state.state === 'READY' && (
          <button className="btn btn-primary" style={{ width: '100%' }} onClick={() => onTransition('FLYING')}>
            Start Mission
          </button>
        )}

        {/* ── KEY TRANSITION: Flying → Coverage QC ── */}
        {state.state === 'FLYING' && (
          <>
            <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.4)', textAlign: 'center' }}>
              Flight complete? Land the drone and proceed to QC review.
            </div>
            <button
              className="btn btn-primary"
              style={{ width: '100%', background: 'linear-gradient(90deg,#2f81f7,#7c3aed)', border: 'none', fontWeight: 700, letterSpacing: '0.04em' }}
              onClick={() => {
                onTransition('CAPTURING');
                navigate(`/surveyor/mission/${id}/capture`);
              }}
            >
              ✓ End Flight — Go to Coverage &amp; QC
            </button>
          </>
        )}

        {/* Capture → Process */}
        {(state.state === 'CAPTURING' || state.state === 'QC') && (
          <button
            className="btn btn-primary"
            style={{ width: '100%' }}
            onClick={() => {
              onTransition('PROCESSING');
              navigate(`/surveyor/mission/${id}/process`);
            }}
          >
            → Start Processing Pipeline
          </button>
        )}

        {/* Process done → Report */}
        {state.state === 'PROCESSING' && (
          <button
            className="btn btn-outline"
            style={{ width: '100%' }}
            onClick={() => navigate(`/surveyor/mission/${id}/report`)}
          >
            → View Final Report
          </button>
        )}
      </div>
      
    </div>
  );
}
