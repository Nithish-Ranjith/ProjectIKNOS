import React from 'react'
import type { Case } from '../../types'

interface Props {
  score: number
}

export const ConfidenceBadge: React.FC<Props> = ({ score }) => {
  let color = '#4a7c59'
  let label = 'Low Risk'
  if (score >= 70) { color = '#d32f2f'; label = 'High Risk' }
  else if (score >= 45) { color = 'var(--color-terracotta)'; label = 'Medium Risk' }

  return (
    <span style={{
      background: color,
      color: '#fff',
      padding: '2px 8px',
      borderRadius: '12px',
      fontSize: '0.75rem',
      fontWeight: 700,
      fontFamily: 'var(--font-mono)',
      whiteSpace: 'nowrap',
    }}>
      {score} · {label}
    </span>
  )
}

interface StatusBadgeProps { status: Case['status'] }
export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const map: Record<Case['status'], { color: string; label: string }> = {
    open: { color: 'var(--color-terracotta)', label: 'Open' },
    field_verification: { color: '#1565C0', label: 'In Field Visit' },
    closed: { color: '#4a7c59', label: 'Closed' },
  }
  const { color, label } = map[status]
  return (
    <span style={{
      border: `1px solid ${color}`,
      color,
      padding: '2px 8px',
      borderRadius: '12px',
      fontSize: '0.75rem',
      fontWeight: 600,
      whiteSpace: 'nowrap',
    }}>
      {label}
    </span>
  )
}

