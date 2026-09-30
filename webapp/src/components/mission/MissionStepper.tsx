import React from 'react';
import { useNavigate } from 'react-router-dom';
import type { MissionState, DroneTelemetry } from '../../types/mission';

const STEPS = [
  { id: '1', label: 'Parcel',   subLabel: 'Load & Verify',     states: ['PARCEL_LOAD', 'BOUNDARY_REVIEW', 'BOUNDARY_APPROVED'], route: 'parcel'  },
  { id: '2', label: 'Plan',     subLabel: 'Split & Optimize',  states: ['PLANNING', 'READY'],                                    route: 'plan'    },
  { id: '3', label: 'Fly',      subLabel: 'Live Guidance',     states: ['FLYING'],                                               route: 'fly'     },
  { id: '4', label: 'Capture',  subLabel: 'Coverage & QC',     states: ['CAPTURING', 'QC'],                                      route: 'capture' },
  { id: '5', label: 'Process',  subLabel: 'Stitch & Analyze',  states: ['PROCESSING', 'COMPLETE'],                               route: 'process' },
];

interface MissionStepperProps {
  currentState: MissionState;
  missionId: string;
  telemetry?: DroneTelemetry;
  onEndMission: () => void;
}

export const MissionStepper: React.FC<MissionStepperProps> = ({ currentState, missionId, telemetry, onEndMission }) => {
  const navigate = useNavigate();
  const currentStepIndex = STEPS.findIndex(s => s.states.includes(currentState));
  
  return (
    <header style={{ 
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      height: '64px', padding: '0 var(--spacing-xl)',
      background: 'var(--color-surface)',
      borderBottom: '1px solid var(--color-border)',
      boxShadow: 'var(--shadow-subtle)',
      flexShrink: 0, zIndex: 10
    }}>
      {/* ── LEFT: Logo & Context ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-xl)' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
          <div style={{ fontSize: '16px', fontWeight: 700, letterSpacing: '1px' }}>IKNOS</div>
          <div style={{ fontSize: '10px', color: 'var(--color-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Field Ops</div>
        </div>

        <div style={{ width: 1, height: 16, background: 'var(--color-border)' }} />

        <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
           <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-primary)' }}>Surveyor Drone</div>
           <div style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>ID: {missionId}</div>
        </div>
      </div>

      {/* ── CENTER: 5-Step Progress ── */}
      <div style={{ display: 'flex', gap: '8px' }}>
        {STEPS.map((step, idx) => {
          const isActive = idx === currentStepIndex;
          const isPast = idx < currentStepIndex;
          const isAccessible = idx <= currentStepIndex; // can navigate to past+current steps
          
          let bgColor = 'transparent';
          let textColor = 'var(--color-text-secondary)';
          let numberBg = 'rgba(255, 255, 255, 0.05)';
          let numberColor = 'var(--color-text-secondary)';

          if (isActive) {
            bgColor = 'var(--color-active-light)';
            textColor = 'var(--color-text-primary)';
            numberBg = 'var(--color-active)';
            numberColor = '#fff';
          } else if (isPast) {
            textColor = 'var(--color-text-primary)';
            numberBg = 'var(--color-brand-light)';
            numberColor = 'var(--color-brand)';
          }

          return (
            <div
              key={step.id}
              onClick={() => isAccessible && navigate(`/surveyor/mission/${missionId}/${step.route}`)}
              title={isAccessible ? `Go to ${step.label}` : `Complete previous steps first`}
              style={{
                display: 'flex', alignItems: 'center', gap: '10px',
                padding: '6px 16px 6px 6px',
                borderRadius: 'var(--radius-pill)',
                background: bgColor,
                border: isActive ? '1px solid rgba(47, 129, 247, 0.2)' : '1px solid transparent',
                cursor: isAccessible ? 'pointer' : 'not-allowed',
                opacity: isAccessible ? 1 : 0.4,
                transition: 'all 0.15s ease',
                userSelect: 'none',
              }}
              onMouseEnter={e => { if (isAccessible && !isActive) e.currentTarget.style.background = 'rgba(255,255,255,0.05)'; }}
              onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = bgColor; }}
            >
              <div style={{
                width: 28, height: 28, borderRadius: '2px',
                background: numberBg, color: numberColor,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '10px', fontWeight: 700
              }}>
                {isPast ? 'OK' : step.id}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span style={{ fontSize: '13px', fontWeight: 600, color: textColor, lineHeight: 1 }}>{step.label}</span>
                <span style={{ fontSize: '10px', color: 'var(--color-text-secondary)' }}>{step.subLabel}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* ── RIGHT: Telemetry & Actions ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-lg)' }}>
        {telemetry && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', color: 'var(--color-text-secondary)' }}>
            <span style={{ color: 'var(--color-brand)' }}>
               {telemetry.positioningState.replace('_', ' ')}
            </span>
            <span>Signal: Strong</span>
            <span style={{ color: 'var(--color-brand)' }}>Bat: {Math.round(telemetry.batteryPercent || 0)}%</span>
            <span>11:24 AM</span>
          </div>
        )}
        
        <button style={{ background: 'transparent', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', color: 'var(--color-text-primary)', padding: '4px 12px', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', cursor: 'pointer' }}>Settings</button>
        
        <button style={{ background: 'var(--color-danger)', border: 'none', borderRadius: 'var(--radius-sm)', color: '#fff', padding: '4px 16px', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', cursor: 'pointer' }} onClick={onEndMission}>
          End Mission
        </button>
      </div>
    </header>
  );
};
