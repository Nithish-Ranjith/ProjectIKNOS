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
      .finally(() => setLoading(false))
  }, [])

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: 'var(--color-bg)', padding: 'var(--spacing-xl)' }}>
      <h1 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '24px' }}>Surveyor Profile</h1>

      {loading ? (
        <div style={{ color: 'var(--color-text-secondary)' }}>Loading profile...</div>
      ) : profile ? (
        <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
          {/* Main Info Card */}
          <div className="card" style={{ flex: '1 1 300px', padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div style={{ width: 64, height: 64, borderRadius: '50%', background: 'var(--color-brand-light)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-brand)' }}>
                <User size={32} />
              </div>
              <div>
                <h2 style={{ fontSize: '18px', fontWeight: 600, margin: 0 }}>{profile.name}</h2>
                <div style={{ color: 'var(--color-text-secondary)', fontSize: '13px', marginTop: '4px' }}>
                  ID: {profile.id}
                </div>
              </div>
            </div>
            
            <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: '16px', marginTop: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
                <span style={{ color: 'var(--color-text-secondary)', fontSize: '13px' }}>Role</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', fontWeight: 500, color: 'var(--color-brand)' }}>
                  <Shield size={14} /> Certified Surveyor
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
                <span style={{ color: 'var(--color-text-secondary)', fontSize: '13px' }}>Contact</span>
                <span style={{ fontSize: '13px', color: 'var(--color-text-primary)' }}>{profile.phone}</span>
              </div>
            </div>
          </div>

          {/* Stats Card */}
          <div className="card" style={{ flex: '1 1 300px', padding: '24px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 600, margin: '0 0 16px 0', color: 'var(--color-text-secondary)' }}>ACTIVITY STATS</h3>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '16px', borderRadius: '8px', border: '1px solid var(--color-border)' }}>
                <div style={{ color: 'var(--color-text-secondary)', fontSize: '12px', marginBottom: '8px' }}>Total Missions</div>
                <div style={{ fontSize: '24px', fontWeight: 600 }}>{profile.linked_parcels?.length || 12}</div>
              </div>
              
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '16px', borderRadius: '8px', border: '1px solid var(--color-border)' }}>
                <div style={{ color: 'var(--color-text-secondary)', fontSize: '12px', marginBottom: '8px' }}>Pending Cases</div>
                <div style={{ fontSize: '24px', fontWeight: 600 }}>0</div>
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
