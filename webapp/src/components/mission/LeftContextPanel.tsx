import type { MissionViewState, MapLayer } from '../../types/mission';

interface Props {
  state: MissionViewState;
  onUpdateState: (setter: (prev: MissionViewState) => MissionViewState) => void;
  onApproveBoundary?: () => void;
  onProceedToPlan?: () => void;
  isApproving?: boolean;
}

export function LeftContextPanel({ state, onUpdateState, onApproveBoundary, onProceedToPlan, isApproving }: Props) {
  
  const toggleLayer = (id: string) => {
    onUpdateState(prev => ({
      ...prev,
      layers: prev.layers.map(l => l.id === id ? { ...l, visible: !l.visible } : l)
    }));
  };

  return (
    <div className="panel-left">
      
      {/* Parcel Information */}
      {state.parcel && (
        <div className="card" style={{ padding: 'var(--spacing-lg) var(--spacing-xl)', background: 'transparent', border: 'none', borderRadius: 0, borderBottom: '1px solid var(--color-border)' }}>
          <h3 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: 'var(--spacing-md)' }}>Parcel Information</h3>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span className="text-muted">Parcel ID</span>
              <span style={{ fontWeight: 500 }}>{state.parcel.parcelId}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span className="text-muted">Village</span>
              <span style={{ fontWeight: 500 }}>{state.parcel.villageName}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span className="text-muted">Area (Cadastral)</span>
              <span style={{ fontWeight: 500 }}>{(state.parcel.cadastralAreaSqM / 10000).toFixed(2)} ha</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span className="text-muted">Area (Adjusted)</span>
              <span style={{ fontWeight: 500 }}>
                {(state.parcel.workingAreaSqM / 10000).toFixed(2)} ha 
                <span className="text-brand" style={{ marginLeft: 6 }}>
                  (+{(((state.parcel.workingAreaSqM / state.parcel.cadastralAreaSqM) - 1) * 100).toFixed(1)}%)
                </span>
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
              <span className="text-muted">Status</span>
              <span style={{ 
                display: 'flex', alignItems: 'center', gap: '6px',
                background: 'var(--color-brand-light)', color: 'var(--color-brand)', 
                padding: '4px 10px', borderRadius: 'var(--radius-pill)', 
                fontSize: '9px', fontWeight: 700, textTransform: 'uppercase'
              }}>
                Approved
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Layers */}
      <div className="card" style={{ padding: 'var(--spacing-lg) var(--spacing-xl)', background: 'transparent', border: 'none', borderRadius: 0, borderBottom: '1px solid var(--color-border)' }}>
        <h3 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: 'var(--spacing-md)' }}>Layers</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {state.layers.map((layer: MapLayer) => (
            <label key={layer.id} onClick={() => toggleLayer(layer.id)} style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '13px', cursor: 'pointer', color: 'var(--color-text-secondary)' }}>
              <div style={{
                width: 16, height: 16, borderRadius: '4px',
                border: layer.visible ? 'none' : '1px solid var(--color-text-secondary)',
                background: layer.visible ? 'var(--color-active)' : 'transparent',
                display: 'flex', alignItems: 'center', justifyContent: 'center'
              }}>
                {layer.visible && <span style={{ color: '#fff', fontSize: '8px', fontWeight: 700 }}>ON</span>}
              </div>
              {layer.label}
            </label>
          ))}
        </div>
      </div>

      {/* Boundary Tools */}
      {(state.state === 'BOUNDARY_REVIEW' || state.state === 'BOUNDARY_APPROVED') && (
        <div className="card" style={{ padding: 'var(--spacing-lg) var(--spacing-xl)', background: 'transparent', border: 'none', borderRadius: 0 }}>
          <h3 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: 'var(--spacing-md)' }}>Boundary Tools</h3>
          <div style={{ display: 'flex', gap: '12px' }}>
            {state.parcel?.boundaryStatus === 'BOUNDARY_APPROVED' ? (
              <button 
                className="btn btn-primary" 
                style={{ width: '100%', padding: '8px', fontSize: '13px' }}
                onClick={() => { if (onProceedToPlan) onProceedToPlan(); }}
              >
                Proceed to Plan →
              </button>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '100%' }}>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button className="btn btn-outline" style={{ flex: 1, padding: '8px', fontSize: '13px' }}>Adjust Boundary</button>
                  <button 
                    className="btn btn-primary" 
                    style={{ flex: 1, padding: '8px', fontSize: '13px' }}
                    disabled={isApproving}
                    onClick={() => {
                      if (onApproveBoundary) onApproveBoundary();
                      else {
                        onUpdateState(prev => ({
                          ...prev, 
                          state: 'BOUNDARY_APPROVED',
                          parcel: prev.parcel ? { ...prev.parcel, boundaryStatus: 'BOUNDARY_APPROVED' } : null
                        }))
                      }
                    }}
                  >
                    {isApproving ? 'Approving...' : 'Approve Boundary'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Inference */}
      {state.inference && (
        <div className="card" style={{ margin: '0 var(--spacing-xl)', padding: 'var(--spacing-md)', background: 'rgba(255,255,255,0.02)', borderColor: 'var(--color-border)', borderRadius: 'var(--radius-lg)' }}>
          <div style={{ display: 'flex', gap: '16px' }}>
            <div style={{ width: 64, height: 48, background: 'var(--color-border)', borderRadius: 'var(--radius-sm)', clipPath: 'polygon(10% 20%, 90% 10%, 100% 90%, 20% 100%)', backgroundSize: 'cover', backgroundImage: 'url("https://images.unsplash.com/photo-1595180453535-24268fa3d664?auto=format&fit=crop&q=80&w=200&h=150")' }} />
            <div style={{ flex: 1 }}>
               <h3 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 4px 0' }}>U-Net Boundary (AI)</h3>
               <div style={{ display: 'flex', gap: '8px', fontSize: '12px' }}>
                 <span className="text-muted">Confidence</span>
                 <span className="text-brand" style={{ fontWeight: 600 }}>{state.inference.confidence}</span>
               </div>
               <div style={{ display: 'flex', gap: '8px', fontSize: '12px', marginTop: '2px' }}>
                 <span className="text-muted">Last run: 10:15 AM</span>
               </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
