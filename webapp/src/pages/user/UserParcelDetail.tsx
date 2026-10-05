import React, { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { supabase } from '../../lib/supabase'
import { fetchActiveCaseForParcel, fetchGeometryLayers } from '../../services/api'
import { MapboxMap } from '../../components/MapboxMap'
import { TemporalSlider } from '../../components/TemporalSlider'
import { ShieldCheck, MapPin, FileText, ChevronRight, AlertTriangle, ArrowLeft } from 'lucide-react'
import styles from './UserParcelDetail.module.css'

export const UserParcelDetail: React.FC = () => {
  const { id: parcelId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [sliderYear, setSliderYear] = useState(2026)

  const { data, isLoading } = useQuery({
    queryKey: ['parcel-detail', parcelId],
    queryFn: async () => {
      if (!parcelId) throw new Error("No parcel ID")
      const [activeCase, layers] = await Promise.all([
        fetchActiveCaseForParcel(parcelId),
        fetchGeometryLayers('mock') // Stub
      ])
      return { activeCase, layers }
    },
    enabled: !!parcelId
  })

  const handleLogout = async () => {
    await supabase.auth.signOut()
    navigate('/login')
  }

  if (isLoading) return (
    <div className={styles.loadingGis}>
      <span className={`spinner ${styles.loadingSpinner}`}></span>
    </div>
  )

  const activeCase = data?.activeCase
  const layers = data?.layers
  const status = activeCase ? activeCase.status : 'closed'

  return (
    <div className={styles.container}>
      
      {/* Header */}
      <header className={styles.header}>
        <div className={styles.headerBrand}>
          <button onClick={() => navigate('/user/home')} className={styles.backBtn}>
            <ArrowLeft size={24} />
          </button>
          <div className={styles.divider} />
          <ShieldCheck color="var(--accent)" size={24} />
          <span className={styles.headerTitle}>Parcel Record</span>
        </div>
        <button onClick={handleLogout} className="btn btn-outline" style={{ padding: '6px 16px', fontSize: '13px' }}>Logout</button>
      </header>

      {/* Main Content Layout */}
      <div className={styles.mainLayout}>
        
        {/* Sidebar Info */}
        <div className={styles.sidebar}>
          <div>
            <h1 className={styles.parcelTitle}>{parcelId}</h1>
            <p className={styles.parcelMeta}><MapPin size={16} /> District 4, Village</p>
          </div>

          {status === 'open' && (
            <div className={`${styles.statusCard} ${styles.statusOpen}`}>
              <h4 className={`${styles.statusTitle} ${styles.statusTitleOpen}`}><AlertTriangle size={18} /> Under Review</h4>
              <p className={styles.statusDesc}>Our AI has detected a potential discrepancy between the 1950s cadastral record and modern drone satellite boundaries. An official surveyor has been notified.</p>
            </div>
          )}
          
          {status === 'field_verification' && (
            <div className={`${styles.statusCard} ${styles.statusField}`}>
              <h4 className={`${styles.statusTitle} ${styles.statusTitleField}`}><MapPin size={18} /> Drone Survey Scheduled</h4>
              <p className={styles.statusDesc}>A government drone surveyor is en route to verify the physical boundaries of this parcel.</p>
            </div>
          )}

          {status === 'closed' && (
            <div className={`${styles.statusCard} ${styles.statusClosed}`}>
              <h4 className={`${styles.statusTitle} ${styles.statusTitleClosed}`}><ShieldCheck size={18} /> Verified & Immutable</h4>
              <p className={styles.statusDesc}>Your land boundaries exactly match the government records and have been cryptographically secured.</p>
              <div style={{ marginTop: '12px', background: 'var(--bg)', padding: '8px 12px', borderRadius: '6px', fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-2)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span title="3a7b9ce8d9f1a2c3b4e5d6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7">SHA256: 3a7b9c...f1a2</span>
                <button onClick={() => navigator.clipboard.writeText('3a7b9ce8d9f1a2c3b4e5d6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7')} style={{ background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', padding: 0, fontSize: '11px' }}>Copy</button>
              </div>
            </div>
          )}

          <div className={styles.horizontalDivider} />
          
          <h3 className={styles.legalSectionTitle}>Legal Evidence</h3>
          <div className={styles.legalActionList}>
            <button className={`btn btn-outline ${styles.legalActionBtn}`}>
              <span className={styles.legalActionText}><FileText size={16} /> Encumbrance Certificate</span>
              <ChevronRight size={16} />
            </button>
            <button className={`btn btn-outline ${styles.legalActionBtn}`}>
              <span className={styles.legalActionText}><FileText size={16} /> Adangal / Pahani</span>
              <ChevronRight size={16} />
            </button>
          </div>
        </div>

        {/* 4D Map Interface */}
        <div className={styles.mapContainer}>
          {layers ? (
            <MapboxMap 
              layers={layers} 
              interactive={true} 
              mapStyle={sliderYear < 2020 ? 'mapbox://styles/mapbox/satellite-v9' : 'mapbox://styles/mapbox/satellite-streets-v12'} 
            />
          ) : (
             <div className={styles.loadingGis}>Loading GIS...</div>
          )}
          
          <TemporalSlider year={sliderYear} onChange={setSliderYear} />
        </div>
      </div>
    </div>
  )
}