import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchSurveyorAssignments, type Assignment } from '../../services/api'
import { Search } from 'lucide-react'

export const SurveyorHome: React.FC = () => {
  const navigate = useNavigate()
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'mission' | 'field_visit'>('mission')

  useEffect(() => {
    setLoading(true);
    fetchSurveyorAssignments(activeTab)
      .then(setAssignments)
      .finally(() => setLoading(false))
  }, [activeTab])

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: 'var(--color-bg)' }}>
      {/* HEADER */}
      <div style={{ 
        display: 'flex', justifyContent: 'space-between', alignItems: 'center', 
        padding: 'var(--spacing-xl)', borderBottom: '1px solid var(--color-border)' 
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <h1 style={{ fontSize: '20px', fontWeight: 600, margin: 0 }}>Cases</h1>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <div style={{ position: 'relative' }}>
            <span style={{ position: 'absolute', left: 12, top: 8, opacity: 0.5 }}><Search size={16} /></span>
            <input 
              type="text" 
              placeholder="Search cases..." 
              style={{ 
                padding: '8px 12px 8px 36px', borderRadius: 'var(--radius-pill)',
                border: '1px solid var(--color-border)', outline: 'none', width: '250px'
              }} 
            />
          </div>
          <button className="btn btn-primary">+ New Case</button>
        </div>
      </div>

      {/* FILTERS */}
      <div style={{ padding: 'var(--spacing-xl) var(--spacing-xl) 0' }}>
        <div style={{ display: 'flex', gap: '12px', borderBottom: '1px solid var(--color-border)' }}>
          <div 
            onClick={() => setActiveTab('mission')}
            style={{ 
              padding: '12px 16px', cursor: 'pointer', fontWeight: activeTab === 'mission' ? 600 : 500,
              color: activeTab === 'mission' ? 'var(--color-brand)' : 'var(--color-text-secondary)',
              borderBottom: activeTab === 'mission' ? '2px solid var(--color-brand)' : '2px solid transparent'
            }}
          >
            Assigned Missions
          </div>
          <div 
            onClick={() => setActiveTab('field_visit')}
            style={{ 
              padding: '12px 16px', cursor: 'pointer', fontWeight: activeTab === 'field_visit' ? 600 : 500,
              color: activeTab === 'field_visit' ? 'var(--color-brand)' : 'var(--color-text-secondary)',
              borderBottom: activeTab === 'field_visit' ? '2px solid var(--color-brand)' : '2px solid transparent'
            }}
          >
            Assigned Field Visits
          </div>
        </div>
      </div>

      {/* TABLE */}
      <div style={{ padding: 'var(--spacing-xl)', flex: 1, overflow: 'auto' }}>
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
            <thead style={{ background: 'var(--color-bg)', borderBottom: '1px solid var(--color-border)' }}>
              <tr>
                <th style={{ padding: '12px 16px', color: 'var(--color-text-secondary)', fontWeight: 500 }}>Parcel</th>
                <th style={{ padding: '12px 16px', color: 'var(--color-text-secondary)', fontWeight: 500 }}>ID</th>
                <th style={{ padding: '12px 16px', color: 'var(--color-text-secondary)', fontWeight: 500 }}>Village</th>
                <th style={{ padding: '12px 16px', color: 'var(--color-text-secondary)', fontWeight: 500 }}>Status</th>
                <th style={{ padding: '12px 16px', color: 'var(--color-text-secondary)', fontWeight: 500 }}>Assigned To</th>
                <th style={{ padding: '12px 16px', color: 'var(--color-text-secondary)', fontWeight: 500 }}>Priority</th>
                <th style={{ padding: '12px 16px', color: 'var(--color-text-secondary)', fontWeight: 500 }}>Updated</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} style={{ padding: '24px', textAlign: 'center' }}>Loading...</td></tr>
              ) : assignments.map(a => (
                <tr 
                  key={a.assignment_id} 
                  onClick={() => {
                    if (a.type === 'field_visit') {
                      navigate(`/surveyor/field-visit/${a.case_id}`)
                    } else {
                      navigate(`/surveyor/mission/${a.case_id}/parcel`)
                    }
                  }}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  <td style={{ padding: '12px 16px' }}>
                    <div style={{ width: 32, height: 32, background: 'var(--color-border)', borderRadius: 'var(--radius-sm)' }} />
                  </td>
                  <td style={{ padding: '12px 16px', fontWeight: 600 }}>{a.parcel_id}</td>
                  <td style={{ padding: '12px 16px', color: 'var(--color-text-secondary)' }}>{a.village}</td>
                  <td style={{ padding: '12px 16px' }}>
                    <span className={`badge ${a.status === 'in_progress' ? 'badge--warning' : 'badge--success'}`}>
                      {a.status === 'in_progress' ? 'Field Visit' : 'Decision'}
                    </span>
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    <div style={{ display: 'flex', alignItems: 'center' }}>
                      <div style={{ width: 24, height: 24, borderRadius: '50%', background: '#E5E7EB', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '9px', fontWeight: 600, border: '2px solid #fff' }}>P</div>
                      <div style={{ width: 24, height: 24, borderRadius: '50%', background: '#E5E7EB', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '9px', fontWeight: 600, border: '2px solid #fff', marginLeft: '-8px' }}>R</div>
                    </div>
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    <span style={{ color: 'var(--color-danger)', fontWeight: 600 }}>High</span>
                  </td>
                  <td style={{ padding: '12px 16px', color: 'var(--color-text-secondary)' }}>2h ago</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
