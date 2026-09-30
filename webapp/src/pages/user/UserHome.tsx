import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '../../lib/supabase'
import { fetchCurrentUserProfile, fetchParcelSummary } from '../../services/api'
import type { CaseStatus } from '../../types'

const ParcelStatusBadge: React.FC<{ status: CaseStatus }> = ({ status }) => {
  const map = {
    open: { color: 'var(--color-terracotta)', label: 'Action Needed / Under Review' },
    field_verification: { color: '#1565C0', label: 'Field Visit Scheduled' },
    closed: { color: '#4a7c59', label: 'No Issues / Resolved' },
  }
  const { color, label } = map[status] || { color: 'gray', label: 'Unknown' }
  return (
    <span style={{
      background: color, color: '#fff', padding: '4px 12px',
      borderRadius: '16px', fontSize: '0.8rem', fontWeight: 600, display: 'inline-block'
    }}>
      {label}
    </span>
  )
}

export const UserHome: React.FC = () => {
  const navigate = useNavigate()
  const [profileLoading, setProfileLoading] = useState(true)
  const [profileError, setProfileError] = useState<string | null>(null)
  
  const [parcels, setParcels] = useState<any[]>([])
  const [parcelsLoading, setParcelsLoading] = useState(false)
  const [parcelsError, setParcelsError] = useState<string | null>(null)

  useEffect(() => {
    setProfileLoading(true)
    fetchCurrentUserProfile()
      .then(async (profile) => {
        setParcelsLoading(true)
        try {
          const parcelDetails = await Promise.all(
            profile.linked_parcels.map(id => fetchParcelSummary(id))
          )
          setParcels(parcelDetails)
        } catch (e: any) {
          setParcelsError(e.message)
        } finally {
          setParcelsLoading(false)
        }
      })
      .catch(e => setProfileError(e.message))
      .finally(() => setProfileLoading(false))
  }, [])

  const handleLogout = async () => {
    await supabase.auth.signOut()
    navigate('/login')
  }

  return (
    <div className="app-container">
      <header className="topbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <span style={{ fontFamily: 'var(--font-ui)', fontSize: '1.25rem', fontWeight: 700 }}>
             TerraTrace
          </span>
          <span style={{ opacity: 0.5 }}>|</span>
          <span style={{ opacity: 0.8 }}>Landowner Dashboard</span>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button onClick={handleLogout} className="btn btn-outline" style={{ color: 'white', borderColor: 'white', fontSize: '0.85rem' }}>Logout</button>
        </div>
      </header>

      <div style={{ position: 'relative', width: '100%', height: '450px', overflow: 'hidden' }}>
        <iframe src="/interactive_globe.html" style={{ width: '100%', height: '100%', border: 'none', position: 'absolute', top: 0, left: 0 }} title="Decorative Globe" />
        <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', background: 'linear-gradient(to bottom, transparent 60%, var(--color-bg) 100%)' }} />
      </div>

      <main className="main-content" style={{ maxWidth: '900px', marginTop: '-60px', position: 'relative', zIndex: 10 }}>
        <h2 style={{ marginBottom: '1.5rem' }}>My Parcels</h2>

        {profileLoading && (
          <div style={{ padding: '3rem', textAlign: 'center' }}>
             <span className="spinner" style={{ borderColor: 'var(--color-border)', borderTopColor: 'var(--color-terracotta)' }}></span> Loading profile...
          </div>
        )}
        
        {profileError && <div className="error-msg"> {profileError}</div>}
        {parcelsError && <div className="error-msg"> {parcelsError}</div>}

        {!profileLoading && !profileError && (
          <>
            {parcelsLoading ? (
              <div style={{ padding: '2rem', textAlign: 'center' }}>
                 <span className="spinner" style={{ borderColor: 'var(--color-border)', borderTopColor: 'var(--color-terracotta)' }}></span> Fetching parcel status...
              </div>
            ) : parcels.length === 0 ? (
              <div className="card" style={{ textAlign: 'center', padding: '3rem', color: 'var(--color-text-secondary)' }}>
                <p style={{ marginBottom: '1rem' }}>No parcels linked to your account yet.</p>
                <button className="btn btn-primary">Link a Parcel</button>
              </div>
            ) : (
              <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))' }}>
                {parcels.map(p => (
                  <div key={p.parcel_id} className="card" style={{ cursor: 'pointer', transition: 'box-shadow 0.2s' }} onClick={() => navigate(`/user/parcel/${p.parcel_id}`)}
                       onMouseEnter={e => e.currentTarget.style.boxShadow = '0 6px 12px rgba(31, 45, 61, 0.15)'}
                       onMouseLeave={e => e.currentTarget.style.boxShadow = '0 2px 4px rgba(31, 45, 61, 0.08)'}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
                      <h3 style={{ margin: 0, fontSize: '1.2rem' }}>{p.parcel_id}</h3>
                    </div>
                    <p style={{ margin: '0 0 0.5rem 0', color: 'var(--color-text-secondary)', fontSize: '0.9rem' }}>{p.village}</p>
                    <p style={{ margin: '0 0 1rem 0', fontFamily: 'var(--font-mono)', fontSize: '0.9rem' }}>Area: {p.area_sqm.toLocaleString()} m²</p>
                    <ParcelStatusBadge status={p.latest_status} />
                  </div>
                ))}
              </div>
            )}
            
            <div style={{ marginTop: '2rem' }}>
               <button className="btn btn-outline">Link Another Parcel</button>
            </div>
          </>
        )}
      </main>
    </div>
  )
}
