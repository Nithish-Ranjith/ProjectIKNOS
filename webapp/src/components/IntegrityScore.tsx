import React, { useEffect, useState } from 'react';

interface BreakdownItem { label: string; valuePct: number }
interface Props { score: number; breakdown: BreakdownItem[] }

export const IntegrityScore: React.FC<Props> = ({ score, breakdown }) => {
  const [animated, setAnimated] = useState(0);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    let cur = 0;
    const iv = setInterval(() => {
      cur += 2;
      if (cur >= score) { setAnimated(score); clearInterval(iv); }
      else setAnimated(cur);
    }, 14);
    return () => clearInterval(iv);
  }, [score]);

  const R = 58;
  const SW = 8;
  const circ = Math.PI * R;
  const offset = circ - (animated / 100) * circ;

  const label =
    score >= 90 ? 'EXCELLENT'
    : score >= 70 ? 'GOOD'
    : score >= 50 ? 'FAIR'
    : 'POOR';

  return (
    <div>
      <div className="panel-label" style={{ marginBottom: '16px' }}>OPERATOR ANALYTICS</div>

      {/* Gauge + label row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '20px', marginBottom: '20px' }}>
        {/* SVG arc — 140 × 90, arc center at (70, 88), top at y≈30 */}
        <div style={{ position: 'relative', width: '140px', height: '90px', flexShrink: 0 }}>
          <svg width="140" height="78" viewBox="0 0 140 78" style={{ overflow: 'visible', display: 'block' }}>
            {/* track */}
            <path d="M 12 74 A 58 58 0 0 1 128 74"
              fill="none" stroke="var(--color-border-mid)" strokeWidth={SW} strokeLinecap="round" />
            {/* fill */}
            <path d="M 12 74 A 58 58 0 0 1 128 74"
              fill="none" stroke="var(--color-navy)" strokeWidth={SW} strokeLinecap="round"
              strokeDasharray={circ} strokeDashoffset={mounted ? offset : circ}
              style={{ transition: 'stroke-dashoffset 0.12s linear' }}
            />
          </svg>
          {/* Score number sits cleanly in the 12px gap below the arc */}
          <div style={{
            position: 'absolute', bottom: '0', left: 0, right: 0,
            textAlign: 'center'
          }}>
            <span style={{ fontSize: '1.75rem', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--color-text-primary)', lineHeight: 1 }}>
              {animated}
            </span>
          </div>
        </div>

        <div>
          <div style={{ fontSize: '0.65rem', fontWeight: 600, letterSpacing: '0.14em', color: 'var(--color-navy)', textTransform: 'uppercase' }}>
            {label}
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--color-sage)', fontFamily: 'var(--font-mono)', marginTop: '4px' }}>
            ↑ +3 this week
          </div>
        </div>
      </div>

      {/* Breakdown bars */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {breakdown.map((item, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', fontSize: '0.7rem' }}>
            <span style={{ width: '96px', color: 'var(--color-text-secondary)', fontFamily: 'var(--font-mono)', flexShrink: 0 }}>
              {item.label}
            </span>
            <div style={{ flex: 1, height: '3px', background: 'var(--color-border-mid)', borderRadius: '2px', overflow: 'hidden', margin: '0 10px' }}>
              <div style={{
                height: '100%',
                background: 'var(--color-navy)',
                width: mounted ? `${item.valuePct}%` : '0%',
                transition: 'width 1s cubic-bezier(0.4, 0, 0.2, 1) 0.15s'
              }} />
            </div>
            <span style={{ width: '28px', textAlign: 'right', color: 'var(--color-text-secondary)', fontFamily: 'var(--font-mono)' }}>
              {item.valuePct}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};
