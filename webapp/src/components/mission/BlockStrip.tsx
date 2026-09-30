import type { SurveyBlock } from '../../types/mission';

interface Props {
  blocks: SurveyBlock[];
  activeBlockId: string | null;
}

export function BlockStrip(_props: Props) {
  return (
    <div className="bottom-strip" style={{ display: 'flex', gap: '8px', padding: '12px var(--spacing-xl)', background: 'var(--color-bg)', borderTop: '1px solid var(--color-border)', overflowX: 'auto', flexShrink: 0 }}>
      {/* Generate B1 through B9 to match screenshot visually */}
      {[1, 2, 3, 4, 5, 6, 7, 8, 9].map(num => {
        const id = `B${num}`;
        const isActive = id === 'B3';
        const isCompleted = id === 'B1' || id === 'B2';

        return (
          <div key={id} style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '4px', borderRadius: 'var(--radius-md)', background: isActive ? 'rgba(47, 129, 247, 0.1)' : 'transparent', border: isActive ? '1px solid var(--color-active)' : '1px solid transparent' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', paddingLeft: '4px' }}>
              <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-primary)' }}>{id}</span>
              {isCompleted && <span style={{ color: 'var(--color-brand)', fontSize: '9px', fontWeight: 700, textTransform: 'uppercase' }}>DONE</span>}
              {isActive && <span style={{ color: 'var(--color-active)', fontSize: '9px', fontWeight: 700, textTransform: 'uppercase' }}>LIVE</span>}
            </div>
            
            <div style={{ 
              width: 90, height: 60, 
              background: 'var(--color-surface)',
              border: isActive ? '2px solid var(--color-active)' : '1px solid var(--color-border)',
              borderRadius: '2px',
              position: 'relative',
              backgroundImage: 'url("https://images.unsplash.com/photo-1595180453535-24268fa3d664?auto=format&fit=crop&q=80&w=200&h=150")',
              backgroundSize: 'cover'
            }}>
              {/* White polygon overlay to mock the block boundary */}
              <div style={{ width: '100%', height: '100%', border: '1px solid rgba(255,255,255,0.5)', clipPath: 'polygon(10% 20%, 90% 10%, 100% 90%, 20% 100%)' }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
