import React, { useEffect, useState } from 'react'
import { fetchSurveyorHistory, type Assignment } from '../../services/api'
import { CheckCircle } from 'lucide-react'

export const SurveyorHistory: React.FC = () => {
  const [history, setHistory] = useState<Assignment[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    fetchSurveyorHistory()
      .then(setHistory)
      .finally(() => setLoading(false))
  }, [])

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: 'var(--color-bg)', padding: 'var(--spacing-xl)' }}>
      <h1 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '24px' }}>Surveyor History</h1>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
          <thead style={{ background: 'var(--color-bg)', borderBottom: '1px solid var(--color-border)' }}>
            <tr>
              <th style={{ padding: '12px 16px', color: 'var(--color-text-secondary)', fontWeight: 500 }}>Assignment ID</th>
              <th style={{ padding: '12px 16px', color: 'var(--color-text-secondary)', fontWeight: 500 }}>Case ID</th>
              <th style={{ padding: '12px 16px', color: 'var(--color-text-secondary)', fontWeight: 500 }}>Parcel ID</th>
              <th style={{ padding: '12px 16px', color: 'var(--color-text-secondary)', fontWeight: 500 }}>Type</th>
              <th style={{ padding: '12px 16px', color: 'var(--color-text-secondary)', fontWeight: 500 }}>Status</th>
              <th style={{ padding: '12px 16px', color: 'var(--color-text-secondary)', fontWeight: 500 }}>Assigned Date</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} style={{ padding: '24px', textAlign: 'center' }}>Loading history...</td></tr>
            ) : history.length === 0 ? (
              <tr><td colSpan={6} style={{ padding: '24px', textAlign: 'center', color: 'var(--color-text-secondary)' }}>No history found.</td></tr>
            ) : history.map(h => (
              <tr key={h.assignment_id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                <td style={{ padding: '12px 16px', fontWeight: 500, color: 'var(--color-text-primary)' }}>{h.assignment_id}</td>
                <td style={{ padding: '12px 16px', color: 'var(--color-text-secondary)' }}>{h.case_id}</td>
                <td style={{ padding: '12px 16px', color: 'var(--color-text-secondary)' }}>{h.parcel_id}</td>
                <td style={{ padding: '12px 16px', color: 'var(--color-text-secondary)' }}>
                  <span style={{ 
                    padding: '4px 8px', borderRadius: '12px', fontSize: '11px', fontWeight: 600,
                    background: 'rgba(255,255,255,0.05)', color: 'var(--color-text-primary)' 
                  }}>
                    {h.type === 'mission' ? 'Drone Mission' : 'Field Visit'}
                  </span>
                </td>
                <td style={{ padding: '12px 16px' }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: 'var(--color-success)', fontSize: '12px', fontWeight: 500 }}>
                    <CheckCircle size={14} /> Completed
                  </span>
                </td>
                <td style={{ padding: '12px 16px', color: 'var(--color-text-secondary)' }}>
                  {new Date(h.assigned_at).toLocaleDateString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
