import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { MapboxMap } from '../components/MapboxMap'
import styles from './BrowseMap.module.css'
import type { GeometryLayers } from '../types'
import { MapPin } from 'lucide-react'
import { fetchMapParcels } from '../services/api'
import { toast } from 'sonner'

export const BrowseMap: React.FC = () => {
  const navigate = useNavigate()
  const [layers, setLayers] = useState<GeometryLayers | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedParcel, setSelectedParcel] = useState<any>(null)

  useEffect(() => {
    const fetchParcels = async () => {
      try {
        const data = await fetchMapParcels()
        setLayers({ cadastral: data } as any)
      } catch (err: any) {
        toast.error(`Failed to load parcels: ${err.message}`)
        console.error('Failed to fetch map parcels', err)
      } finally {
        setLoading(false)
      }
    }
    fetchParcels()
  }, [])

  const handleParcelClick = (parcelId: string) => {
    if (layers?.cadastral && (layers.cadastral as any).type === 'FeatureCollection') {
      const feature = (layers.cadastral as any).features.find((f: any) => f.properties?.parcel_id === parcelId)
      if (feature) {
        setSelectedParcel(feature.properties)
      }
    }
  }

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <div className={styles.title}><MapPin size={20} style={{ marginRight: '12px' }} /> IKNOS Explorer</div>
        <button onClick={() => navigate(-1)} className="btn btn-outline" style={{ padding: '6px 16px' }}>Back</button>
      </header>
      
      <div className={styles.mapArea}>
        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-2)' }}>
            Loading geographic data...
          </div>
        ) : (
          <>
            <MapboxMap 
              layers={layers} 
              height="100%" 
              onParcelClick={handleParcelClick} 
            />
            {selectedParcel && (
              <div className={styles.overlay}>
                <h3 className={styles.overlayTitle}>Parcel Details</h3>
                <div className={styles.statRow}>
                  <span className={styles.statLabel}>ID</span>
                  <span className={styles.statValue}>{selectedParcel.parcel_id}</span>
                </div>
                <div className={styles.statRow}>
                  <span className={styles.statLabel}>ULPIN</span>
                  <span className={styles.statValue}>{selectedParcel.ulpin || 'N/A'}</span>
                </div>
                <div className={styles.statRow}>
                  <span className={styles.statLabel}>Owner</span>
                  <span className={styles.statValue}>{selectedParcel.owner_name || 'Unknown'}</span>
                </div>
                <div className={styles.statRow}>
                  <span className={styles.statLabel}>Area (sqm)</span>
                  <span className={styles.statValue}>{selectedParcel.area_sqm?.toLocaleString() || 'N/A'}</span>
                </div>
                <div className={styles.statRow}>
                  <span className={styles.statLabel}>Source</span>
                  <span className={styles.statValue} style={{ textTransform: 'capitalize' }}>{selectedParcel.source}</span>
                </div>
                <button 
                  className="btn btn-primary" 
                  style={{ width: '100%', marginTop: '16px' }}
                  onClick={() => navigate(`/admin/cases`)} // Or another dynamic route based on role
                >
                  View Cases
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
