import React, { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { supabase } from '../../lib/supabase'
import { fetchActiveCaseForParcel, fetchCasePlainSummary, fetchGeometryLayers } from '../../services/api'
import { MapboxMap } from '../../components/MapboxMap'
import type { Case, GeometryLayers } from '../../types'

const PlainStatusBlock: React.FC<{ status: Case['status'] }> = ({ status }) => {
  if (status === 'open') {
    return (
      <div style={{ padding: '1rem', background: '#fff3e0', borderLeft: '4px solid var(--color-terracotta)', borderRadius: '4px' }}>
        <h4 style={{ color: 'var(--color-terracotta)', margin: '0 0 0.5rem 0' }}>Under Review</h4>
        <p style={{ margin: 0, fontSize: '0.9rem' }}>We've detected a potential discrepancy in your land records. A surveyor may be assigned to review this case.</p>
      </div>
    )
  }
  if (status === 'field_verification') {
    return (
      <div style={{ padding: '1rem', background: '#e3f2fd', borderLeft: '4px solid #1565c0', borderRadius: '4px' }}>
        <h4 style={{ color: '#1565c0', margin: '0 0 0.5rem 0' }}>Field Visit Scheduled</h4>
        <p style={{ margin: 0, fontSize: '0.9rem' }}>A government surveyor has been assigned to visit your parcel and verify the physical boundaries.</p>
      </div>
    )
  }
  return (
    <div style={{ padding: '1rem', background: '#e8f5e9', borderLeft: '4px solid #4a7c59', borderRadius: '4px' }}>
      <h4 style={{ color: '#4a7c59', margin: '0 0 0.5rem 0' }}>No Issues Found / Resolved</h4>
      <p style={{ margin: 0, fontSize: '0.9rem' }}>Your land records are up to date and match the physical boundaries.</p>
    </div>
  )
}

export const UserParcelDetail: React.FC = () => {
  const { id: parcelId } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [activeCase, setActiveCase] = useState<Case | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  const [summary, setSummary] = useState<{ changes: string[] } | null>(null)
  const [summaryOpen, setSummaryOpen] = useState(false)

  const [layers, setLayers] = useState<GeometryLayers | null>(null)

  useEffect(() => {
    if (!parcelId) return
    setLoading(true)
    
    // Fetch case info and map layers in parallel
    Promise.all([
      fetchActiveCaseForParcel(parcelId),
      fetchGeometryLayers('mock') // Stub: returns default geometry for demo
    ])
      .then(([c, l]) => {
        setActiveCase(c)
        setLayers(l)
        if (!c) {
           fetchCasePlainSummary('mock-closed-case').then(setSummary)
        }
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [parcelId])

  const handleLogout = async () => {
    await supabase.auth.signOut()
    navigate('/login')
  }

  if (loading) return (
    <div className="app-container" style={{ alignItems: 'center', justifyContent: 'center' }}>
      <span className="spinner" style={{ width: '2rem', height: '2rem', borderColor: 'var(--color-border)', borderTopColor: 'var(--color-terracotta)' }}></span>
    </div>
  )

  if (error) return (
    <div className="app-container" style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div className="error-msg"> {error}<br /><button className="btn btn-outline" style={{ marginTop: '0.75rem' }} onClick={() => navigate('/user/home')}>Back Home</button></div>
    </div>
  )

  // Derived status: if active case exists, use its status; else 'closed'
  const displayStatus = activeCase ? activeCase.status : 'closed'

  return (
    <div className="app-container">
      <header className="topbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button onClick={() => navigate('/user/home')} style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.7)', cursor: 'pointer', fontSize: '1.2rem' }}>←</button>
          <span style={{ fontFamily: 'var(--font-ui)', fontWeight: 700 }}>Parcel Detail</span>
        </div>
        <button onClick={handleLogout} className="btn btn-outline" style={{ color: 'white', borderColor: 'white', fontSize: '0.85rem' }}>Logout</button>
      </header>

      <main className="main-content" style={{ maxWidth: '800px' }}>
        <h2 style={{ marginBottom: '0.5rem', fontSize: '1.75rem' }}>{parcelId}</h2>
        
        <div className="card" style={{ marginBottom: '1.5rem', padding: '1.5rem' }}>
          <PlainStatusBlock status={displayStatus} />
        </div>

        {/* Cadastral Map §2.3 */}
        <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3 style={{ fontSize: '1.1rem', margin: 0 }}>Map View</h3>
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)', background: '#f4f6f8', padding: '2px 8px', borderRadius: '12px' }}>
              Only official boundaries are shown
            </span>
          </div>
          <MapboxMap layers={layers} showAILayer={false} height="250px" />
        </div>

        {/* Change Summary §2.3 */}
        {displayStatus === 'closed' && summary && (
          <div className="card" style={{ marginBottom: '1.5rem' }}>
            <button 
              onClick={() => setSummaryOpen(!summaryOpen)}
              style={{ background: 'none', border: 'none', width: '100%', textAlign: 'left', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', fontFamily: 'var(--font-ui)', fontSize: '1.1rem', color: 'var(--color-terracotta)' }}
            >
              What Changed in the Last Update?
              <span>{summaryOpen ? '' : ''}</span>
            </button>
            {summaryOpen && (
              <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--color-border)' }}>
                <ul style={{ paddingLeft: '1.5rem', margin: 0, color: 'var(--color-text-secondary)', fontSize: '0.95rem', lineHeight: '1.6' }}>
                  {summary.changes.map((change, i) => <li key={i} style={{ marginBottom: '0.5rem' }}>{change}</li>)}
                </ul>
              </div>
            )}
          </div>
        )}

        <div style={{ display: 'flex', gap: '1rem' }}>
          <button className="btn btn-outline" style={{ flex: 1 }}> View History</button>
          <button className="btn btn-primary" style={{ flex: 1 }} onClick={() => navigate(`/user/parcel/${parcelId}/grievance`)}> Raise a Concern</button>
        </div>
      </main>
    </div>
  )
}
