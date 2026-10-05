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
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: 'var(--bg)', padding: '32px', animation: 'fadeIn 0.3s ease' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-1)', margin: 0 }}>Mission History</h1>
        <div style={{ padding: '8px 16px', background: 'rgba(52,168,105,0.1)', color: 'var(--green)', borderRadius: '24px', fontSize: '13px', fontWeight: 600 }}>
          {history.length} Total Missions
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden', background: 'var(--panel)', border: '1px solid var(--border)' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
          <thead style={{ background: 'var(--bg-raised)', borderBottom: '1px solid var(--border-mid)' }}>
            <tr>
              <th style={{ padding: '16px 24px', color: 'var(--text-3)', fontWeight: 600, fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Assignment ID</th>
              <th style={{ padding: '16px 24px', color: 'var(--text-3)', fontWeight: 600, fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Case / Parcel</th>
              <th style={{ padding: '16px 24px', color: 'var(--text-3)', fontWeight: 600, fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Type</th>
              <th style={{ padding: '16px 24px', color: 'var(--text-3)', fontWeight: 600, fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Status</th>
              <th style={{ padding: '16px 24px', color: 'var(--text-3)', fontWeight: 600, fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.05em', textAlign: 'right' }}>Date</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={5} style={{ padding: '48px', textAlign: 'center', color: 'var(--text-3)' }}>Loading history...</td></tr>
            ) : history.length === 0 ? (
              <tr><td colSpan={5} style={{ padding: '48px', textAlign: 'center', color: 'var(--text-3)' }}>No history found.</td></tr>
            ) : history.map((h, i) => (
              <tr key={h.assignment_id} style={{ borderBottom: '1px solid var(--border)', background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)', transition: 'background 0.2s' }}>
                <td style={{ padding: '16px 24px', fontWeight: 600, color: 'var(--text-1)', fontFamily: 'var(--font-mono)' }}>{h.assignment_id.split('-').pop()}</td>
                <td style={{ padding: '16px 24px' }}>
                  <div style={{ color: 'var(--text-1)', fontWeight: 500 }}>{h.case_id}</div>
                  <div style={{ color: 'var(--text-3)', fontSize: '11px', fontFamily: 'var(--font-mono)', marginTop: '4px' }}>{h.parcel_id}</div>
                </td>
                <td style={{ padding: '16px 24px' }}>
                  <span style={{ 
                    padding: '6px 12px', borderRadius: '4px', fontSize: '11px', fontWeight: 600,
                    background: h.type === 'mission' ? 'var(--accent-dim)' : 'var(--amber-dim)', 
                    color: h.type === 'mission' ? 'var(--accent)' : 'var(--amber)',
                    textTransform: 'uppercase', letterSpacing: '0.05em'
                  }}>
                    {h.type === 'mission' ? 'UAV Flight' : 'Field Audit'}
                  </span>
                </td>
                <td style={{ padding: '16px 24px' }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: 'var(--green)', fontSize: '13px', fontWeight: 500 }}>
                    <CheckCircle size={14} /> Finalized
                  </span>
                </td>
                <td style={{ padding: '16px 24px', color: 'var(--text-2)', textAlign: 'right', fontFamily: 'var(--font-mono)' }}>
                  {new Date(h.assigned_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
