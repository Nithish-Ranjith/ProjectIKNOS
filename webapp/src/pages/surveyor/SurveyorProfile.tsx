import React, { useEffect, useState } from 'react'
import { fetchCurrentUserProfile } from '../../services/api'
import { User, Shield } from 'lucide-react'

export const SurveyorProfile: React.FC = () => {
  const [profile, setProfile] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    fetchCurrentUserProfile()
      .then(setProfile)
      .catch(err => {
        console.error('Failed to load profile:', err)
        setProfile(null)
      })
      .finally(() => setLoading(false))
  }, [])

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: 'var(--color-bg)', padding: 'var(--spacing-xl)' }}>
      <h1 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '24px' }}>Surveyor Profile</h1>

      {loading ? (
        <div style={{ color: 'var(--color-text-secondary)' }}>Loading profile...</div>
      ) : profile ? (
        <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap', animation: 'fadeIn 0.3s ease' }}>
          {/* Main Info Card */}
          <div className="card" style={{ flex: '1 1 300px', padding: '32px', display: 'flex', flexDirection: 'column', gap: '24px', background: 'var(--panel)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
              <div style={{ width: 80, height: 80, borderRadius: '50%', background: 'rgba(62,155,247,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent)', boxShadow: 'inset 0 0 0 1px var(--border)' }}>
                <User size={40} />
              </div>
              <div>
                <h2 style={{ fontSize: '22px', fontWeight: 600, margin: 0, color: 'var(--text-1)' }}>{profile.name}</h2>
                <div style={{ color: 'var(--text-3)', fontSize: '13px', marginTop: '4px', fontFamily: 'var(--font-mono)' }}>
                  ID: {profile.id}
                </div>
              </div>
            </div>
            
            <div style={{ borderTop: '1px solid var(--border)', paddingTop: '20px', marginTop: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
                <span style={{ color: 'var(--text-3)', fontSize: '13px' }}>Clearance Level</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', fontWeight: 500, color: 'var(--green)', background: 'var(--green-dim)', padding: '4px 8px', borderRadius: '4px' }}>
                  <Shield size={14} /> Certified Surveyor (Level 3)
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
                <span style={{ color: 'var(--text-3)', fontSize: '13px' }}>Contact Phone</span>
                <span style={{ fontSize: '13px', color: 'var(--text-2)', fontFamily: 'var(--font-mono)' }}>{profile.phone}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
                <span style={{ color: 'var(--text-3)', fontSize: '13px' }}>Drone Model</span>
                <span style={{ fontSize: '13px', color: 'var(--text-2)', fontFamily: 'var(--font-mono)' }}>DJI Mavic 3 Enterprise</span>
              </div>
            </div>
          </div>

          {/* Stats Card */}
          <div className="card" style={{ flex: '1 1 300px', padding: '32px', background: 'var(--panel)' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 600, margin: '0 0 24px 0', color: 'var(--text-3)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>ACTIVITY STATS</h3>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '24px', borderRadius: '8px', border: '1px solid var(--border)' }}>
                <div style={{ color: 'var(--text-3)', fontSize: '13px', marginBottom: '12px' }}>Total Missions</div>
                <div style={{ fontSize: '32px', fontWeight: 600, color: 'var(--text-1)', fontFamily: 'var(--font-mono)' }}>{profile.linked_parcels?.length || 12}</div>
              </div>
              
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '24px', borderRadius: '8px', border: '1px solid var(--border)' }}>
                <div style={{ color: 'var(--text-3)', fontSize: '13px', marginBottom: '12px' }}>Active Flights</div>
                <div style={{ fontSize: '32px', fontWeight: 600, color: 'var(--text-1)', fontFamily: 'var(--font-mono)' }}>0</div>
              </div>

              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '24px', borderRadius: '8px', border: '1px solid var(--border)', gridColumn: 'span 2' }}>
                <div style={{ color: 'var(--text-3)', fontSize: '13px', marginBottom: '12px' }}>Flight Hours YTD</div>
                <div style={{ fontSize: '32px', fontWeight: 600, color: 'var(--text-1)', fontFamily: 'var(--font-mono)' }}>142.5h</div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div style={{ color: 'var(--color-error)' }}>Failed to load profile.</div>
      )}
    </div>
  )
}
