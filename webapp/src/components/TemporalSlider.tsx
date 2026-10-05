import React from 'react';
import { Clock } from 'lucide-react';

export const TemporalSlider: React.FC<{ year: number, onChange: (y: number) => void }> = ({ year, onChange }) => {
  return (
    <div style={{
      position: 'absolute', bottom: '32px', left: '50%', transform: 'translateX(-50%)',
      background: 'rgba(22, 27, 34, 0.9)', backdropFilter: 'blur(10px)', border: '1px solid var(--color-border)',
      padding: '16px 32px', borderRadius: '32px', display: 'flex', alignItems: 'center', gap: '24px', zIndex: 10,
      boxShadow: '0 10px 30px rgba(0,0,0,0.5)'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-text-secondary)' }}>
        <Clock size={18} color="var(--color-active)" />
        <span style={{ fontSize: '12px', textTransform: 'uppercase', letterSpacing: '1px', fontWeight: 600 }}>4D TIMELINE</span>
      </div>
      <input 
        type="range" min="2015" max="2026" value={year} 
        onChange={(e) => onChange(parseInt(e.target.value))}
        style={{ width: '300px', accentColor: 'var(--color-active)' }}
      />
      <div style={{ background: 'var(--color-active)', color: '#fff', padding: '4px 12px', borderRadius: '16px', fontSize: '16px', fontWeight: 800, fontFamily: 'var(--font-mono)' }}>
        {year}
      </div>
    </div>
  );
}
