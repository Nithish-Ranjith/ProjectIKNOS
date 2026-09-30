import React from 'react'

interface CaseTimelineProps {
  status: string
}

export const CaseTimeline: React.FC<CaseTimelineProps> = ({ status }) => {
  const stages = [
    'Triggered',
    'Assigned',
    'Field Visit',
    'Officer Review',
    'Decision Made',
    'Record Updated'
  ]

  let currentIndex = 0
  if (status === 'open') currentIndex = 1
  if (status === 'field_verification') currentIndex = 2
  if (status === 'under_review') currentIndex = 3 // If added later
  if (status === 'closed' || status === 'resolved') currentIndex = 5

  return (
    <div style={{ padding: '1.5rem 2rem 2.5rem 2rem', width: '100%', background: '#fff', borderRadius: '8px', border: '1px solid var(--color-border)', marginBottom: '1.5rem' }}>
      <h3 style={{ fontSize: '0.85rem', textTransform: 'uppercase', color: 'var(--color-text-secondary)', marginBottom: '1.5rem', letterSpacing: '0.5px' }}>Case Lifecycle</h3>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', position: 'relative' }}>
        
        {/* Background line */}
        <div style={{ position: 'absolute', top: '8px', left: 0, right: 0, height: '4px', background: 'var(--color-bg)', zIndex: 0, borderRadius: '2px' }}></div>
        
        {/* Fill line */}
        <div style={{ position: 'absolute', top: '8px', left: 0, width: `${(currentIndex / (stages.length - 1)) * 100}%`, height: '4px', background: 'var(--color-sage)', zIndex: 0, borderRadius: '2px', transition: 'width 0.5s ease' }}></div>

        {stages.map((stage, idx) => {
          const isCompleted = idx <= currentIndex
          const isCurrent = idx === currentIndex
          return (
            <div key={stage} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', zIndex: 1, position: 'relative' }}>
              <div style={{ 
                width: '20px', height: '20px', borderRadius: '50%', 
                background: isCompleted ? 'var(--color-sage)' : '#fff',
                border: `3px solid ${isCompleted ? 'var(--color-sage)' : 'var(--color-border)'}`,
                boxShadow: isCurrent ? '0 0 0 6px rgba(107, 143, 113, 0.2)' : 'none',
                transition: 'all 0.3s ease'
              }}></div>
              <div style={{ 
                position: 'absolute', top: '28px', whiteSpace: 'nowrap', 
                fontSize: '0.75rem', fontWeight: isCurrent ? 700 : 500,
                color: isCompleted ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
                opacity: isCompleted ? 1 : 0.6
              }}>
                {stage}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
