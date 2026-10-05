import React from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { supabase } from '../../lib/supabase'
import { fetchCurrentUserProfile, fetchParcelSummary } from '../../services/api'
import type { CaseStatus } from '../../types'
import { MapPin, ShieldCheck, AlertTriangle, ShieldAlert, FileText, ChevronRight, Map as MapIcon, Compass } from 'lucide-react'
import styles from './UserHome.module.css'

const ParcelStatusBadge: React.FC<{ status: CaseStatus }> = ({ status }) => {
  const map = {
    open: { color: 'var(--amber)', bg: 'var(--amber-dim)', border: 'var(--amber)', icon: <AlertTriangle size={14} /> },
    field_verification: { color: 'var(--accent)', bg: 'var(--accent-dim)', border: 'var(--accent)', icon: <MapIcon size={14} /> },
    closed: { color: 'var(--green)', bg: 'var(--green-dim)', border: 'var(--green)', icon: <ShieldCheck size={14} /> },
  }
  const { color, bg, border, icon } = map[status] || map.open
  return (
    <span style={{
      background: bg, color: color, padding: '6px 12px', border: `1px solid ${border}`,
      borderRadius: '24px', fontSize: '12px', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '6px'
    }}>
      {icon} {status.replace('_', ' ').toUpperCase()}
    </span>
  )
}

export const UserHome: React.FC = () => {
  const navigate = useNavigate()
  
  const { data: parcels = [], isLoading, error } = useQuery({
    queryKey: ['user-parcels'],
    queryFn: async () => {
      const profile = await fetchCurrentUserProfile()
      return Promise.all(profile.linked_parcels.map((id: string) => fetchParcelSummary(id)))
    }
  })

  const handleLogout = async () => {
    await supabase.auth.signOut()
    navigate('/login')
  }

  return (
    <div className={styles.container}>
      
      {/* Premium Header */}
      <header className={styles.header}>
        <div className={styles.headerBrand}>
          <ShieldCheck color="var(--accent)" size={24} />
          <span>IKNOS Citizen</span>
        </div>
        <button onClick={handleLogout} className="btn btn-outline" style={{ padding: '6px 16px', fontSize: '13px' }}>Secure Logout</button>
      </header>

      {/* Hero Interactive Map Graphic */}
      <div className={styles.hero}>
        <Compass size={64} color="var(--accent)" style={{ marginBottom: '24px' }} />
        <h1 className={styles.heroTitle}>Verify and Protect Your Assets</h1>
        <p className={styles.heroSubtitle}>
          Government-backed drone surveying and machine learning boundary verification ensures your land records are mathematically immutable.
        </p>
      </div>

      <main className={styles.mainContent}>
        
        {isLoading ? (
          <div className={styles.emptyState}>
             <Compass className="spinner" size={32} color="var(--accent)" style={{ marginBottom: '16px' }} />
             <div style={{ color: 'var(--text-2)' }}>Loading secure profile...</div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', animation: 'fadeIn 0.4s ease' }}>
            
            <h2 style={{ fontSize: '20px', fontWeight: 600, color: 'var(--text-1)', margin: 0 }}>Registered Properties</h2>

            {error && (
              <div className={styles.errorState}>
                <ShieldAlert size={20} /> {error instanceof Error ? error.message : 'Failed to load parcels'}
              </div>
            )}

            {parcels.length === 0 && !error && (
              <div className={styles.emptyState}>
                <MapPin size={48} color="var(--text-3)" style={{ marginBottom: '16px', opacity: 0.5 }} />
                <h3 style={{ fontSize: '18px', color: 'var(--text-1)', marginBottom: '8px' }}>No Registered Properties</h3>
                <p style={{ color: 'var(--text-2)' }}>You do not have any land parcels linked to your government ID.</p>
              </div>
            )}

            <div className={styles.cardGrid}>
              {parcels.map(p => (
                <button key={p.parcel_id} onClick={() => navigate(`/user/parcel/${p.parcel_id}`)} className={styles.parcelCard}>
                  <div style={{ display: 'flex', gap: '24px', alignItems: 'center' }}>
                    <div className={styles.parcelCardIcon}>
                      <MapPin size={24} color="var(--accent)" />
                    </div>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                        <span className={styles.parcelCardTitle}>{p.parcel_id}</span>
                        <ParcelStatusBadge status={p.latest_status} />
                      </div>
                      <div className={styles.parcelCardMeta}>
                        <span className={styles.parcelCardMetaItem}><MapIcon size={14} /> {p.village}</span>
                        <span className={styles.parcelCardMetaItem}><FileText size={14} /> {p.area_sqm.toLocaleString()} sqm</span>
                      </div>
                    </div>
                  </div>
                  <ChevronRight size={24} color="var(--text-3)" />
                </button>
              ))}
            </div>
            
          </div>
        )}
      </main>
      <style>{`
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>
    </div>
  )
}